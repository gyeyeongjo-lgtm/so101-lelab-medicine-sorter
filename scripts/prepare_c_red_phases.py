#!/usr/bin/env python3
"""Offline-only audit and fake-bus exercise of the recorded C-to-red phases.

This program has no live mode, serial import, motor adapter, or torque API.
The source follower_command points are sliced, never clipped or regenerated.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

try:  # Jetson trial root contains the deployed replay file.
    from replay_c_red_approach import (
        CANDIDATE_SHA, SOURCE_SHA, TRACKING_ABORT, run_timed_segment,
    )
except ModuleNotFoundError:  # Repository tests import scripts directly.
    from scripts.replay_c_red_approach import (
        CANDIDATE_SHA, SOURCE_SHA, TRACKING_ABORT, run_timed_segment,
    )
from scripts.so101_follower_transport import ARM_LIMITS_DEG, EXPECTED_URDF_SHA256
from scripts.staged_cycle_execution import Feedback, JOINT_UNITS


PHASE_END_SEQ = {
    "approach": 45133,
    "grasp": 60669,
    "transport": 72140,
    "place": 92158,
    "retreat": 94174,
}


def load_phases(path: Path) -> dict[str, list[dict]]:
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != CANDIDATE_SHA:
        raise ValueError("candidate_file_changed")
    data = json.loads(raw)
    if (data.get("source_cycle_sha256") != SOURCE_SHA or
            data.get("source_urdf_sha256") != EXPECTED_URDF_SHA256 or
            data.get("goal_source") != "follower_command_not_follower_feedback"):
        raise ValueError("candidate_provenance_changed")
    points = data["waypoints"]
    if not points or points[0]["seq"] != 28363 or points[-1]["seq"] != PHASE_END_SEQ["retreat"]:
        raise ValueError("candidate_boundary_changed")
    indices = {point["seq"]: i for i, point in enumerate(points)}
    if not all(seq in indices for seq in PHASE_END_SEQ.values()):
        raise ValueError("phase_anchor_missing")
    phases = {}
    start = 0
    previous_seq = -1
    previous_elapsed = -1.0
    for point in points:
        seq, elapsed = point["seq"], point["elapsed_from_safe_start_s"]
        if seq <= previous_seq or not math.isfinite(elapsed) or elapsed <= previous_elapsed:
            raise ValueError("invalid_point_order")
        if set(point["goal"]) != set(JOINT_UNITS) or set(point["observed_feedback"]) != set(JOINT_UNITS):
            raise ValueError("invalid_joint_shape")
        for position in (point["goal"], point["observed_feedback"]):
            if any(not math.isfinite(value) for value in position.values()):
                raise ValueError("nonfinite_position")
            if not 0.0 <= position["gripper"] <= 100.0:
                raise ValueError("gripper_outside_percent_range")
            if any(not low <= position[name] <= high
                   for name, (low, high) in ARM_LIMITS_DEG.items()):
                raise ValueError("point_outside_urdf")
        previous_seq, previous_elapsed = seq, elapsed
    for name, end_seq in PHASE_END_SEQ.items():
        end = indices[end_seq]
        if end <= start:
            raise ValueError("phase_order_invalid")
        # The previous phase's last point is this phase's start pose gate.
        selected = points[start:end + 1]
        t0 = selected[0]["elapsed_from_safe_start_s"]
        phases[name] = [{**point, "elapsed_from_safe_start_s":
                          point["elapsed_from_safe_start_s"] - t0}
                        for point in selected]
        start = end
    return phases


class FakeClock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now

    def sleep(self, seconds: float):
        self.now += seconds


class FakeFollower:
    """Ideal feedback plus measured 87 ms send/read latency, no bus access."""

    def __init__(self, clock: FakeClock):
        self.clock = clock
        self.goal = None
        self.sent = 0

    def verify_start_pose(self, goal, tolerances):
        return Feedback(dict(goal), self.clock())

    def send_goal(self, goal):
        self.goal = dict(goal)
        self.sent += 1
        self.clock.now += 0.040
        return dict(goal)

    def read_feedback(self):
        self.clock.now += 0.047
        return Feedback(dict(self.goal), self.clock())


def audit_phase(name: str, points: list[dict], *, time_scale: float = 4.0) -> dict:
    if not math.isfinite(time_scale) or time_scale < 2.0:
        raise ValueError("invalid_time_scale")
    margin = min(min(position[joint] - low, high - position[joint])
                 for point in points for position in (point["goal"], point["observed_feedback"])
                 for joint, (low, high) in ARM_LIMITS_DEG.items())
    arm_step = max(max(abs(b["goal"][joint] - a["goal"][joint])
                       for joint in ARM_LIMITS_DEG)
                   for a, b in zip(points, points[1:]))
    gripper_step = max(abs(b["goal"]["gripper"] - a["goal"]["gripper"])
                       for a, b in zip(points, points[1:]))
    if margin < 5.0 or arm_step > 2.0 + 1e-8 or gripper_step > 2.0 + 1e-8:
        raise ValueError(f"{name}_numeric_guard_failed")
    clock = FakeClock()
    fake = FakeFollower(clock)
    count = run_timed_segment(points, fake, time_scale=time_scale,
                              clock=clock, sleep=clock.sleep)
    if count != len(points) - 1 or count != fake.sent:
        raise ValueError(f"{name}_fake_replay_incomplete")
    gripper_values = [point["goal"]["gripper"] for point in points]
    recorded_error = {
        joint: max(abs(point["goal"][joint] - point["observed_feedback"][joint])
                   for point in points)
        for joint in JOINT_UNITS
    }
    outside_settle_threshold = sum(
        any(abs(point["goal"][joint] - point["observed_feedback"][joint]) >
            TRACKING_ABORT[joint] for joint in JOINT_UNITS)
        for point in points
    )
    return {
        "phase": name, "status": "DRY_RUN_ONLY", "start_seq": points[0]["seq"],
        "end_seq": points[-1]["seq"], "targets": count,
        "recorded_start_kst": points[0]["timestamp_kst"],
        "recorded_end_kst": points[-1]["timestamp_kst"],
        "nominal_duration_s": points[-1]["elapsed_from_safe_start_s"] * time_scale,
        "fake_bus_duration_s": clock.now - 100.0,
        "minimum_arm_urdf_margin_deg": margin,
        "max_adjacent_arm_target_change_deg": arm_step,
        "max_adjacent_gripper_change_pp": gripper_step,
        "gripper_start_percent": gripper_values[0],
        "gripper_end_percent": gripper_values[-1],
        "gripper_min_percent": min(gripper_values),
        "gripper_max_percent": max(gripper_values),
        "max_recorded_command_feedback_abs_error": recorded_error,
        "recorded_points_outside_approach_settle_threshold": outside_settle_threshold,
        "fake_feedback_model": "ideal_equals_command_after_87ms",
        "collision_verified": False, "physical_tracking_verified": False,
        "motion_authorized": False,
    }


def dry_run_cycle(candidate: Path, *, command: str | None = None) -> dict:
    if command is not None:
        from scripts.medicine_fixed_slot_command import parse_command
        if parse_command(command) != {"C": "red"}:
            raise ValueError("only_C_to_red_route_prepared")
    phases = load_phases(candidate)
    results = []
    for name, points in phases.items():
        # A failed phase raises immediately and prevents the next dry-run phase.
        results.append(audit_phase(name, points))
    return {"status": "DRY_RUN_ONLY", "route": "C_to_red",
            "phases": results, "total_fake_targets": sum(r["targets"] for r in results),
            "live_cycle_available": False, "motion_authorized": False}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--phase", choices=[*PHASE_END_SEQ, "all"], default="all")
    parser.add_argument("--command")
    args = parser.parse_args(argv)
    try:
        if args.phase == "all":
            result = dry_run_cycle(args.candidate, command=args.command)
        else:
            if args.command is not None:
                raise ValueError("command_requires_all_phases")
            result = audit_phase(args.phase, load_phases(args.candidate)[args.phase])
    except (OSError, ValueError) as error:
        parser.exit(2, f"DRY_RUN_BLOCKED: {error}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
