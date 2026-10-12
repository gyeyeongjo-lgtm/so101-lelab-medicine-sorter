#!/usr/bin/env python3
"""Move only from the verified C pre-approach pose to the approach pose.

Dry-run is the default. Live mode holds the fresh gripper position, sends one
bounded arm segment, requires final feedback and human alignment confirmation,
then stops. It has no grasp or lift transition.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

if __package__:
    from scripts.continuous_following_execution import ContinuousFollowingCycle
    from scripts.live_c_approach import (
        ARM_NAMES, interpolate_staged_goals, load_plan,
        validate_staged_reference_start, verify_final_feedback,
    )
    from scripts.so101_exclusive_bus import ExclusiveFollowerLease, SystemBusProbe
    from scripts.so101_follower_transport import SO101FollowerTransport
    from scripts.staged_cycle_execution import JOINT_UNITS
else:
    from continuous_following_execution import ContinuousFollowingCycle
    from live_c_approach import (
        ARM_NAMES, interpolate_staged_goals, load_plan,
        validate_staged_reference_start, verify_final_feedback,
    )
    from so101_exclusive_bus import ExclusiveFollowerLease, SystemBusProbe
    from so101_follower_transport import SO101FollowerTransport
    from staged_cycle_execution import JOINT_UNITS


SCOPE = "live_c_approach_only"
RUN_PHRASE = "RUN C APPROACH ONLY"


def load_approach_plan(path: Path) -> dict:
    plan = load_plan(path, expected_scope=SCOPE)
    required_start = plan.get("required_start_arm_deg")
    tolerance = plan.get("start_gate_tolerance_deg")
    if (not isinstance(required_start, dict) or set(required_start) != set(ARM_NAMES) or
            any(not isinstance(value, (int, float)) or not math.isfinite(value)
                for value in required_start.values()) or
            not isinstance(tolerance, (int, float)) or not math.isfinite(tolerance) or
            not 0 < tolerance <= 1.6 or
            plan["staged_intermediate_arm_deg"] or
            plan["staged_reference_start_arm_deg"] is not None):
        raise ValueError("approach_only_start_contract_invalid")
    plan["start_gate_tolerance_deg"] = float(tolerance)
    return plan


def run(plan_path: Path, *, live: bool, confirm_scope: str | None,
        following_log_output: Path | None = None, input_fn=input,
        transport_factory=None) -> int:
    plan = load_approach_plan(plan_path)
    print(json.dumps({
        "scope": plan["scope"],
        "source_frame_sha256": plan["source_frame_sha256"],
        "target_robot_xyz_mm": plan["target_robot_xyz_mm"],
        "target_arm_deg": plan["target_arm_deg"],
        "required_start_arm_deg": plan["required_start_arm_deg"],
        "start_gate_tolerance_deg": plan["start_gate_tolerance_deg"],
        "maximum_joint_step_deg": plan["maximum_joint_step_deg"],
        "final_tolerance_deg": 1.6,
        "holds_fresh_gripper_position": True,
        "grasp_or_lift_enabled": False,
        "dry_run": not live,
    }, separators=(",", ":")), flush=True)
    if not live:
        print("DRY_RUN: no port opened; no send_action; grasp/lift unavailable", flush=True)
        return 0
    if confirm_scope != SCOPE:
        raise ValueError("live_scope_mismatch")
    if following_log_output is None:
        raise ValueError("continuous_following_log_required")
    if following_log_output.exists():
        raise ValueError("continuous_following_log_already_exists")
    if input_fn(f"C aligned from pre-approach; path clear; site stop ready. Type {RUN_PHRASE}: ") != RUN_PHRASE:
        print("NOT_RUN", flush=True)
        return 2

    factory = transport_factory or (lambda: SO101FollowerTransport.open_live(
        ExclusiveFollowerLease(
            SystemBusProbe(), port=Path(plan["follower_port"]),
            serial_short=plan["follower_serial_short"]),
        approval_confirmed=True))
    transport = factory()
    controller = None
    outcome = 1
    closed = False
    try:
        first = transport.read_feedback()
        if (set(first.positions) != set(JOINT_UNITS) or
                any(not math.isfinite(first.positions[name]) for name in JOINT_UNITS)):
            raise ValueError("fresh_start_feedback_invalid")
        start = dict(first.positions)
        transport.verify_start_pose(
            start, {name: (2.0 if name == "gripper" else 1.0) for name in JOINT_UNITS})
        validate_staged_reference_start(
            start, plan["required_start_arm_deg"],
            tolerance_deg=plan["start_gate_tolerance_deg"])
        goals = interpolate_staged_goals(
            start, [], plan["target_arm_deg"], plan["maximum_joint_step_deg"])
        print(json.dumps({
            "fresh_start": start,
            "waypoints": len(goals),
            "gripper_hold": start["gripper"],
        }, separators=(",", ":")), flush=True)

        following_log_output.parent.mkdir(parents=True, exist_ok=True)

        def write_row(row: dict) -> None:
            with following_log_output.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(row, separators=(",", ":")) + "\n")
                stream.flush()

        tolerances = {name: (2.0 if name == "gripper" else 1.6)
                      for name in JOINT_UNITS}
        controller = ContinuousFollowingCycle(
            transport, tolerances,
            planned_start=start,
            following_limits=plan["following_error_limits_deg"],
            max_joint_step_deg=plan["maximum_joint_step_deg"],
            cadence_s=plan["following_cadence_s"],
            no_progress_timeout_s=plan["following_no_progress_timeout_s"],
            progress_epsilon_deg=plan["following_progress_epsilon_deg"],
            final_timeout_s=plan["final_waypoint_timeout_s"],
            feedback_max_age_s=0.5, stable_s=0.1, poll_s=0.05,
            log_sink=write_row)
        controller.start_stage("approach", goals, approved=True)
        wait_timeout_s = (len(goals) *
                          (plan["following_cadence_s"] +
                           plan["following_no_progress_timeout_s"]) +
                          plan["final_waypoint_timeout_s"] + 10.0)
        if not controller.wait_worker(wait_timeout_s):
            raise RuntimeError("approach_worker_timeout")
        if (controller.reach_state != "GOAL_REACHED" or
                controller.task_state != "USER_CONFIRMATION_REQUIRED" or
                controller.waypoints_reached != len(goals)):
            raise RuntimeError(f"approach_failed:{controller.failure}")
        final_positions, final_errors = verify_final_feedback(
            transport, goals[-1], tolerances, max_age_s=0.5)
        print(json.dumps({
            "final_fresh_feedback": final_positions,
            "final_error_deg_or_pp": final_errors,
            "within_tolerance": True,
        }, separators=(",", ":")), flush=True)
        if input_fn("C/gripper aligned and no excessive contact? Type APPROACH CONFIRMED: ") != "APPROACH CONFIRMED":
            raise RuntimeError("approach_site_result_not_confirmed")
        controller.confirm_task_result(stage="approach", human_observed=True, result=True)
        print("APPROACH_PASS", flush=True)
        outcome = 0
    except (KeyboardInterrupt, Exception) as error:
        print(f"ABORT: {type(error).__name__}: {error}", file=sys.stderr, flush=True)
    finally:
        transport.stop_commands()
        try:
            if controller is not None:
                controller.request_stop()
                controller.verify_stop_completed(timeout_s=3.0)
                human_stopped = input_fn("Arm stopped and scene safe? Type STOPPED: ") == "STOPPED"
                stable = controller.verify_arm_stopped(
                    motion_tolerances={name: (2.0 if name == "gripper" else 1.0)
                                       for name in JOINT_UNITS},
                    window_s=0.5, timeout_s=3.0, human_confirmed=human_stopped)
                if stable:
                    transport.close_after_site_confirmation(
                        controller, object_supported=True)
                    closed = True
                    print("physical_stop=FEEDBACK_AND_HUMAN_CONFIRMED", flush=True)
                else:
                    outcome = 1
                    print("physical_stop=NOT_VERIFIED", file=sys.stderr, flush=True)
        except (KeyboardInterrupt, Exception) as error:
            outcome = 1
            print(f"shutdown_check_failed:{type(error).__name__}:{error}",
                  file=sys.stderr, flush=True)
        finally:
            if not closed:
                try:
                    transport.robot.bus.disconnect(disable_torque=False)
                finally:
                    transport.lease.release()
    return outcome


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-scope", choices=[SCOPE])
    parser.add_argument("--following-log-output", type=Path)
    args = parser.parse_args(argv)
    try:
        return run(
            args.plan, live=args.live, confirm_scope=args.confirm_scope,
            following_log_output=args.following_log_output)
    except (OSError, ValueError) as error:
        parser.exit(2, f"APPROACH_NOT_STARTED: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
