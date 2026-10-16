"""Per-control-cycle evidence for a human-operated LeLab teleoperation session.

This module never opens a motor bus or creates a motor command. The caller owns
the existing leader read, follower send_action, and follower feedback read.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import time
from pathlib import Path
from typing import Callable, Mapping


MOTORS = (
    "shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper"
)
PHASES = ("approach", "grasp", "transport", "place", "retreat")
EVENTS = frozenset((*PHASES, "abort", "complete"))


def _validate_diagnostics(values: Mapping[str, object]) -> dict:
    """Validate same-owner telemetry; Load remains signed diagnostic only."""
    required = {
        "goal_raw", "present_raw", "goal_degree_or_percent",
        "present_degree_or_percent", "moving",
        "present_load_diagnostic", "temperature_c", "fk_grasp_tcp_mm",
    }
    if not isinstance(values, Mapping) or set(values) != required:
        raise ValueError("follower diagnostics shape invalid")
    result = {}
    for label in required - {"fk_grasp_tcp_mm"}:
        readings = values[label]
        if not isinstance(readings, Mapping) or set(readings) != set(MOTORS):
            raise ValueError(f"{label} motor shape invalid")
        parsed = {}
        for name in MOTORS:
            value = readings[name]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{label} contains invalid value")
            if label in {"goal_raw", "present_raw", "moving", "present_load_diagnostic", "temperature_c"}:
                if int(value) != value:
                    raise ValueError(f"{label} must contain integer register values")
                value = int(value)
            if label == "moving" and value not in (0, 1):
                raise ValueError("moving register invalid")
            if label == "temperature_c" and (value < 0 or value > 55):
                raise ValueError("temperature safety gate failed")
            parsed[name] = value
        result[label] = parsed
    xyz = values["fk_grasp_tcp_mm"]
    if not isinstance(xyz, (list, tuple)) or len(xyz) != 3 or any(
        isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
        for value in xyz
    ):
        raise ValueError("fk_grasp_tcp_mm invalid")
    result["fk_grasp_tcp_mm"] = [float(value) for value in xyz]
    return result


def read_same_owner_diagnostics(robot, fk_from_degrees: Callable[[dict[str, float]], object]) -> dict:
    """Read registers through the teleop worker's already-owned follower bus.

    The installed follower's grouped temperature path has produced mismatched
    packets, so temperatures deliberately use individual reads. No write API
    is used here; a failed read propagates and ends the traced cycle.
    """
    bus = robot.bus
    registers = {
        "goal_raw": "Goal_Position",
        "present_raw": "Present_Position",
        "moving": "Moving",
        "present_load_diagnostic": "Present_Load",
    }
    values = {
        label: bus.sync_read(register, normalize=False, num_retry=2)
        for label, register in registers.items()
    }
    values["temperature_c"] = {
        name: bus.read("Present_Temperature", name, normalize=False, num_retry=2)
        for name in MOTORS
    }
    for label in registers:
        if set(values[label]) != set(MOTORS):
            raise ValueError(f"{label} motor shape invalid")
    for label, source in (
        ("goal_degree_or_percent", "goal_raw"),
        ("present_degree_or_percent", "present_raw"),
    ):
        values[label] = {
            name: float(bus._normalize({bus.motors[name].id: int(values[source][name])})[
                bus.motors[name].id
            ])
            for name in MOTORS
        }
    degrees = {name: values["present_degree_or_percent"][name] for name in MOTORS[:-1]}
    values["fk_grasp_tcp_mm"] = fk_from_degrees(degrees)
    return _validate_diagnostics(values)


def load_grasp_fk(urdf_path: Path, tcp_config_path: Path) -> Callable[[dict[str, float]], list[float]]:
    """Pin the installed URDF and existing PICK TCP before a trace opens ports."""
    import numpy as np

    if __package__:
        from .urdf_forward_kinematics import UrdfKinematics
    else:
        from urdf_forward_kinematics import UrdfKinematics

    config = json.loads(Path(tcp_config_path).read_text(encoding="utf-8"))
    expected_sha = config["urdf_sha256"]
    actual_sha = hashlib.sha256(Path(urdf_path).read_bytes()).hexdigest()
    if actual_sha != expected_sha:
        raise ValueError("trace URDF SHA mismatch")
    offset = np.asarray(config["pick_grasp_tcp_offset_gripper_mm"], dtype=float)
    if offset.shape != (3,) or not np.isfinite(offset).all():
        raise ValueError("trace GRASP TCP offset invalid")
    kinematics = UrdfKinematics.from_file(Path(urdf_path))
    names = ("shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll")
    urdf_names = ("Rotation", "Pitch", "Elbow", "Wrist_Pitch", "Wrist_Roll")

    def fk(degrees: dict[str, float]) -> list[float]:
        if set(degrees) != set(names) or any(not math.isfinite(float(value)) for value in degrees.values()):
            raise ValueError("trace FK joint shape invalid")
        q = {urdf_name: math.radians(float(degrees[name]))
             for name, urdf_name in zip(names, urdf_names)}
        transform = kinematics.forward(q, "base", "gripper")
        xyz = transform[:3, 3] * 1000.0 + transform[:3, :3] @ offset
        if not np.isfinite(xyz).all():
            raise ValueError("trace FK nonfinite")
        return [float(value) for value in xyz]

    return fk


def verify_relative_start_stillness(
    *,
    read_leader: Callable[[], Mapping[str, float]],
    read_diagnostics: Callable[[], Mapping[str, object]],
    leader_origin: Mapping[str, float],
    duration_s: float = 3.0,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> dict:
    """Three-second no-send gate for an explicitly armed teaching trace."""
    if duration_s < 3.0:
        raise ValueError("startup stillness duration below three seconds")
    leader = _positions(leader_origin, suffix=".pos", source="leader origin")
    baseline = None
    count = 0
    deadline = monotonic() + duration_s
    while True:
        current = _positions(read_leader(), suffix=".pos", source="startup leader")
        if current != leader:
            raise RuntimeError("startup leader moved before teaching")
        diagnostics = _validate_diagnostics(read_diagnostics())
        present = diagnostics["present_raw"]
        if baseline is None:
            baseline = present
        if any(abs(present[name] - baseline[name]) > 1 for name in MOTORS):
            raise RuntimeError("startup follower jump before teaching")
        if any(value != 0 for value in diagnostics["moving"].values()):
            raise RuntimeError("startup follower moving before teaching")
        count += 1
        if monotonic() >= deadline:
            break
        sleep(0.1)
    return {"samples": count, "duration_s": duration_s, "present_raw_origin": dict(baseline)}


def load_pre_connect_snapshot(path: Path) -> dict:
    """Load the last independent, write-blocked follower sample (no bus open)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("motor_write_calls") != 0 or data.get("torque_change_calls") != 0:
        raise ValueError("pre-connect snapshot was not write-blocked")
    samples = data.get("samples")
    if not isinstance(samples, list) or not samples:
        raise ValueError("pre-connect follower snapshot missing")
    sample = _startup_sample(samples[-1])
    age_ns = time.time_ns() - sample.get("unix_ns", 0)
    if not 0 <= age_ns <= 60_000_000_000:
        raise ValueError("pre-connect follower snapshot is missing or stale")
    return sample


def _startup_sample(values: Mapping[str, object]) -> dict:
    """Keep raw and calibrated evidence, without requiring FK before arming."""
    if not isinstance(values, Mapping):
        raise ValueError("startup telemetry missing")
    fields = ("goal_raw", "present_raw", "goal_degree_or_percent",
              "present_degree_or_percent", "moving", "present_load_diagnostic",
              "temperature_c")
    checked = _validate_diagnostics({
        field: values[field] for field in fields
    } | {"fk_grasp_tcp_mm": [0.0, 0.0, 0.0]})
    result = {field: checked[field] for field in fields}
    if "unix_ns" in values:
        result["unix_ns"] = int(values["unix_ns"])
    return result


def pre_arm_settle(
    *,
    read_diagnostics: Callable[[], Mapping[str, object]],
    record: Callable[[str, Mapping[str, object]], None],
    pre_connect: Mapping[str, object],
    first_post_connect: Mapping[str, object],
    active: Callable[[], bool] = lambda: True,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    stable_s: float = 1.0,
    max_wait_s: float = 5.0,
) -> dict:
    """Read-only, bounded settle gate; no leader/follower target is generated."""
    if not 0.5 <= stable_s <= 1.0 or max_wait_s < stable_s:
        raise ValueError("invalid pre-arm settle duration")
    before = _startup_sample(pre_connect)
    first = _startup_sample(first_post_connect)
    # First post-connect data precedes LeRobot calibration/configuration writes.
    # A goal change after that point is unexpected and must fail closed.
    goal_baseline = first["goal_raw"]
    if first["goal_raw"] != before["goal_raw"]:
        raise RuntimeError("pre-arm unexpected Goal change at connect")
    if any(abs(first["present_degree_or_percent"][name]
               - before["present_degree_or_percent"][name]) >= 1.0
           for name in MOTORS[:-1]):
        raise RuntimeError("pre-arm Present drift >=1 degree at connect")
    start = monotonic()
    stable_since = None
    stable_anchor = None
    while active():
        if monotonic() - start > max_wait_s:
            raise RuntimeError("pre-arm settle timeout")
        current = _startup_sample(read_diagnostics())
        record("PRE_ARM_SETTLE", current)
        if current["goal_raw"] != goal_baseline:
            raise RuntimeError("pre-arm unexpected Goal change")
        if any(abs(current["present_degree_or_percent"][name]
                   - before["present_degree_or_percent"][name]) >= 1.0
               for name in MOTORS[:-1]):
            raise RuntimeError("pre-arm Present drift >=1 degree")
        if all(value == 0 for value in current["moving"].values()):
            if stable_since is None:
                stable_since = monotonic()
                stable_anchor = current
            elif any(abs(current["present_raw"][name] - stable_anchor["present_raw"][name]) > 1
                     for name in MOTORS):
                stable_since = monotonic()
                stable_anchor = current
            elif monotonic() - stable_since >= stable_s:
                record("SETTLED", current)
                return {"first": first, "settled": current, "drift_degree": {
                    name: current["present_degree_or_percent"][name]
                    - before["present_degree_or_percent"][name] for name in MOTORS[:-1]
                }}
        else:
            stable_since = None
            stable_anchor = None
        sleep(0.05)
    raise RuntimeError("pre-arm stopped before settle")


def _positions(values: Mapping[str, float], *, suffix: str, source: str) -> dict[str, float]:
    expected = {name + suffix for name in MOTORS}
    if set(values) != expected:
        raise ValueError(f"{source} has missing or extra motor keys")
    result = {name: float(values[name + suffix]) for name in MOTORS}
    if not all(math.isfinite(value) for value in result.values()):
        raise ValueError(f"{source} contains non-finite motor position")
    return result


class CycleTrace:
    """Append complete cycles only; incomplete calls are recorded as errors."""

    def __init__(self, session_dir: Path, *, capture_kind: str = "full_cycle"):
        if capture_kind not in {"full_cycle", "empirical_relative_teaching"}:
            raise ValueError("unsupported trace capture kind")
        ticket = os.environ.get("LELAB_TELEOP_TRACE_ONCE_TICKET")
        if ticket and capture_kind != "empirical_relative_teaching":
            # An exact, single-use ticket makes later teleop starts fail closed
            # before any robot bus is opened. A failed session needs re-arming.
            Path(ticket).unlink()
        if ticket and capture_kind == "empirical_relative_teaching" and not Path(ticket).is_file():
            raise FileNotFoundError(ticket)
        self.ticket = Path(ticket) if ticket else None
        self.session_dir = Path(session_dir)
        self.capture_kind = capture_kind
        self.session_dir.mkdir(parents=True, exist_ok=False)
        self.path = self.session_dir / "cycles.jsonl"
        self.errors_path = self.session_dir / "errors.jsonl"
        self.events_path = self.session_dir / "events.jsonl"
        self.requests_path = self.session_dir / "requests.jsonl"
        self._cycles = self.path.open("x", encoding="utf-8")
        self._errors = self.errors_path.open("x", encoding="utf-8")
        self.events_path.touch(exist_ok=False)
        self.requests_path.touch(exist_ok=False)
        self.startup_path = self.session_dir / "startup.jsonl"
        self.startup_path.touch(exist_ok=False)
        self._pre_connect_degrees = None
        self.armed = False
        self.started = False
        self.first_sent_goal_recorded = False
        self.count = 0
        self.error_count = 0
        self.closed = False
        self.first_cycle_monotonic_ns: int | None = None
        self.last_cycle_monotonic_ns: int | None = None

    def record_startup(self, phase: str, values: Mapping[str, object]) -> None:
        if self.closed or self.armed:
            raise RuntimeError("startup record after teaching arm")
        sample = _startup_sample(values)
        if phase == "PRE_CONNECT_PRESENT":
            self._pre_connect_degrees = sample["present_degree_or_percent"]
        drift = None if self._pre_connect_degrees is None else {
            name: sample["present_degree_or_percent"][name] - self._pre_connect_degrees[name]
            for name in MOTORS[:-1]
        }
        with self.startup_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"phase": phase, "recorded_unix_ns": time.time_ns(),
                                     "telemetry": sample, "drift_degree_from_pre_connect": drift},
                                    separators=(",", ":")) + "\n")

    def record_settle_result(self, result: Mapping[str, object]) -> None:
        if self.closed or self.armed:
            raise RuntimeError("settle result after teaching arm")
        first = _startup_sample(result["first"])
        settled = _startup_sample(result["settled"])
        summary = {
            "PRE_CONNECT_PRESENT": self._pre_connect_degrees,
            "FIRST_POST_CONNECT_PRESENT": first["present_degree_or_percent"],
            "FIRST_POST_CONNECT_GOAL": first["goal_degree_or_percent"],
            "FIRST_MOVING_STATE": first["moving"],
            "SETTLED_PRESENT": settled["present_degree_or_percent"],
            "SETTLED_GOAL": settled["goal_degree_or_percent"],
            "drift_degree_per_arm_joint": result["drift_degree"],
        }
        if "reference_exact_match" in result:
            summary["REFERENCE_EXACT_MATCH"] = bool(result["reference_exact_match"])
            summary["CURRENT_FRESH_STABILITY"] = bool(result["current_fresh_stability"])
            summary["reference_present_delta_raw"] = result["reference_present_delta_raw"]
            summary["reference_goal_delta_raw"] = result["reference_goal_delta_raw"]
        (self.session_dir / "startup_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    def record_startup_failure(self, error: Exception) -> None:
        if self.closed or self.armed:
            return
        with self.startup_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"phase": "PRE_ARM_ABORT", "recorded_unix_ns": time.time_ns(),
                                     "error_type": type(error).__name__, "message": str(error)[:200]},
                                    separators=(",", ":")) + "\n")

    def arm_teaching(self) -> None:
        if self.capture_kind != "empirical_relative_teaching" or self.closed or self.armed:
            raise RuntimeError("invalid teaching arm transition")
        self.armed = True
        with self.startup_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"phase": "TEACHING_ARMED", "recorded_unix_ns": time.time_ns()},
                                    separators=(",", ":")) + "\n")

    def start_teaching(self) -> None:
        if self.capture_kind != "empirical_relative_teaching" or self.closed or not self.armed or self.started:
            raise RuntimeError("invalid teaching start transition")
        if self.ticket is not None:
            consumed = self.ticket.with_name(self.ticket.name + f".consumed-{os.getpid()}-{time.time_ns()}")
            self.ticket.rename(consumed)
        self.started = True
        with self.startup_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"phase": "TEACHING_STARTED", "recorded_unix_ns": time.time_ns(),
                                     "ticket_consumed": self.ticket is not None},
                                    separators=(",", ":")) + "\n")

    def record_relative_request(
        self, *, leader_action: Mapping[str, float],
        relative_target: Mapping[str, float], previous_target: Mapping[str, float],
        step_violations: Mapping[str, tuple[float, float, float]],
        actual_diagnostics: Mapping[str, object],
    ) -> dict:
        """Durably log an empirical target before the worker acts on a guard.

        The caller computes the existing step violations, writes this row, and
        only then decides HOLD/ABORT/SEND. No bus writes happen here.
        """
        if self.capture_kind != "empirical_relative_teaching" or not self.started or self.closed:
            raise RuntimeError("empirical request outside active teaching")
        leader = _positions(leader_action, suffix=".pos", source="leader")
        target = _positions(relative_target, suffix=".pos", source="relative target")
        previous = _positions(previous_target, suffix=".pos", source="previous target")
        diagnostics = _validate_diagnostics(actual_diagnostics)
        deltas = {name: target[name] - previous[name] for name in MOTORS[:-1]}
        if not isinstance(step_violations, Mapping) or any(
            name not in MOTORS[:-1] or not isinstance(values, tuple) or len(values) != 3
            for name, values in step_violations.items()
        ):
            raise ValueError("step violations shape invalid")
        limited = {}
        for name, values in step_violations.items():
            before, after, delta = values
            if any(not math.isfinite(float(value)) for value in values):
                raise ValueError("step violation nonfinite")
            if not (math.isclose(before, previous[name], abs_tol=1e-9) and
                    math.isclose(after, target[name], abs_tol=1e-9) and
                    math.isclose(delta, deltas[name], abs_tol=1e-9)):
                raise ValueError("step violation disagrees with request")
            limited[name] = float(delta)
        row = {
            "phase": "PRE_GUARD_REQUEST", "recorded_unix_ns": time.time_ns(),
            "leader_position": leader, "requested_target": target,
            "previous_target": previous, "requested_delta_per_arm_joint": deltas,
            "limited_joint_step_degree": limited,
            "actual_present_raw": diagnostics["present_raw"],
            "actual_present_degree_or_percent": diagnostics["present_degree_or_percent"],
            "actual_grasp_tcp_xyz_mm": diagnostics["fk_grasp_tcp_mm"],
            "goal_raw_before_guard": diagnostics["goal_raw"],
        }
        with self.requests_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, separators=(",", ":")) + "\n")
            stream.flush()
        return row

    def record_first_sent_goal(
        self, *, requested_target: Mapping[str, float], goal_raw: Mapping[str, int]
    ) -> dict | None:
        """Persist the first successful arm Goal readback, never a planned send."""
        if self.capture_kind != "empirical_relative_teaching" or not self.started or self.closed:
            raise RuntimeError("first Goal outside active teaching")
        if self.first_sent_goal_recorded:
            return None
        target = _positions(requested_target, suffix=".pos", source="sent target")
        if not isinstance(goal_raw, Mapping) or set(goal_raw) != set(MOTORS) or any(
            type(value) is not int for value in goal_raw.values()
        ):
            raise ValueError("first Goal raw shape invalid")
        row = {"phase": "FIRST_SENT_GOAL", "recorded_unix_ns": time.time_ns(),
               "requested_target": target,
               "goal_raw_after_send": {name: goal_raw[name] for name in MOTORS}}
        with self.requests_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, separators=(",", ":")) + "\n")
            stream.flush()
        self.first_sent_goal_recorded = True
        return row

    def capture_cycle(
        self,
        read_leader: Callable[[], Mapping[str, float]],
        send_action: Callable[[Mapping[str, float]], Mapping[str, float]],
        read_feedback: Callable[[], Mapping[str, float]],
        read_diagnostics: Callable[[dict[str, float]], Mapping[str, object]] | None = None,
    ) -> dict:
        if self.closed:
            raise RuntimeError("cycle trace is closed")
        if self.capture_kind == "empirical_relative_teaching":
            raise RuntimeError("empirical relative teaching cannot use absolute send")
        seq = self.count + self.error_count
        stage = "leader_read"
        started_ns = time.time_ns()
        started_monotonic_ns = time.monotonic_ns()
        try:
            leader_action = read_leader()
            leader = _positions(leader_action, suffix=".pos", source="leader")
            leader_ns = time.time_ns()
            stage = "follower_send_action"
            command_action = send_action(leader_action)
            command_ns = time.time_ns()
            command = _positions(command_action, suffix=".pos", source="sent command")
            stage = "follower_present_position"
            feedback = _positions(read_feedback(), suffix="", source="follower feedback")
            feedback_ns = time.time_ns()
            feedback_monotonic_ns = time.monotonic_ns()
            diagnostics = None
            if read_diagnostics is not None:
                stage = "follower_diagnostics"
                diagnostics = _validate_diagnostics(read_diagnostics(feedback))
            stage = "trace_write"
            row = {
                "seq": seq,
                "started_unix_ns": started_ns,
                "started_monotonic_ns": started_monotonic_ns,
                "leader_read_unix_ns": leader_ns,
                "send_action_return_unix_ns": command_ns,
                "feedback_read_unix_ns": feedback_ns,
                "feedback_monotonic_ns": feedback_monotonic_ns,
                "leader_position": leader,
                "follower_command": command,
                "follower_feedback": feedback,
                "arm_unit": "degree",
                "gripper_unit": "percent_0_100",
                "command_evidence": "send_action_return_after_sync_write_no_motor_ack",
            }
            if diagnostics is not None:
                row["follower_diagnostics"] = diagnostics
            self._cycles.write(json.dumps(row, separators=(",", ":")) + "\n")
            self._cycles.flush()
            if self.first_cycle_monotonic_ns is None:
                self.first_cycle_monotonic_ns = started_monotonic_ns
            self.last_cycle_monotonic_ns = feedback_monotonic_ns
            self.count += 1
            return row
        except Exception as error:
            self._errors.write(json.dumps({
                "seq": seq, "unix_ns": time.time_ns(), "stage": stage,
                "error_type": type(error).__name__, "message": str(error)[:200],
            }, separators=(",", ":")) + "\n")
            self._errors.flush()
            self.error_count += 1
            raise

    def observe_relative_cycle(
        self,
        *,
        leader_action: Mapping[str, float],
        relative_target: Mapping[str, float],
        command_sent: bool,
        gripper_goal_sent: bool = True,
        read_feedback: Callable[[], Mapping[str, float]],
        read_diagnostics: Callable[[dict[str, float]], Mapping[str, object]],
    ) -> dict:
        """Trace an existing guarded relative-start cycle without sending.

        The teleop worker performs its original range/step/elbow guards first.
        This method only reads feedback and diagnostics through that same owner.
        HOLD cycles are explicitly marked and never mislabeled as sent targets.
        """
        if self.closed:
            raise RuntimeError("cycle trace is closed")
        if self.capture_kind == "empirical_relative_teaching" and not self.started:
            raise RuntimeError("teaching observation before start")
        seq = self.count + self.error_count
        stage = "leader_validation"
        started_ns = time.time_ns()
        started_monotonic_ns = time.monotonic_ns()
        try:
            leader = _positions(leader_action, suffix=".pos", source="leader")
            command = _positions(relative_target, suffix=".pos", source="relative target")
            if not isinstance(command_sent, bool):
                raise ValueError("command_sent must be boolean")
            if not isinstance(gripper_goal_sent, bool):
                raise ValueError("gripper_goal_sent must be boolean")
            stage = "follower_present_position"
            follower = _positions(read_feedback(), suffix="", source="follower feedback")
            feedback_ns = time.time_ns()
            feedback_monotonic_ns = time.monotonic_ns()
            stage = "follower_diagnostics"
            diagnostics = _validate_diagnostics(read_diagnostics(follower))
            stage = "trace_write"
            row = {
                "seq": seq,
                "started_unix_ns": started_ns,
                "started_monotonic_ns": started_monotonic_ns,
                "feedback_read_unix_ns": feedback_ns,
                "feedback_monotonic_ns": feedback_monotonic_ns,
                "leader_position": leader,
                "relative_target": command,
                "command_sent": command_sent,
                "gripper_goal_sent": command_sent and gripper_goal_sent,
                "follower_feedback": follower,
                "follower_diagnostics": diagnostics,
                "arm_unit": "degree",
                "gripper_unit": "percent_0_100",
                "command_evidence": "guarded_relative_dispatch_boolean_no_motor_ack",
            }
            self._cycles.write(json.dumps(row, separators=(",", ":")) + "\n")
            self._cycles.flush()
            if self.first_cycle_monotonic_ns is None:
                self.first_cycle_monotonic_ns = started_monotonic_ns
            self.last_cycle_monotonic_ns = feedback_monotonic_ns
            self.count += 1
            return row
        except Exception as error:
            self._errors.write(json.dumps({
                "seq": seq, "unix_ns": time.time_ns(), "stage": stage,
                "error_type": type(error).__name__, "message": str(error)[:200],
            }, separators=(",", ":")) + "\n")
            self._errors.flush()
            self.error_count += 1
            raise

    def finish(self, *, stop_reason: str) -> dict:
        if self.closed:
            raise RuntimeError("cycle trace is already closed")
        self._cycles.close()
        self._errors.close()
        self.closed = True
        events = [json.loads(line) for line in self.events_path.read_text(encoding="utf-8").splitlines()]
        phase_events = [event for event in events if event.get("phase") in PHASES]
        phase_complete = (
            [event["phase"] for event in phase_events] == list(PHASES)
            and self.first_cycle_monotonic_ns is not None
            and self.last_cycle_monotonic_ns is not None
            and all(
                self.first_cycle_monotonic_ns <= event["monotonic_ns"] <= self.last_cycle_monotonic_ns
                for event in phase_events
            )
            and all(
                before["monotonic_ns"] < after["monotonic_ns"]
                for before, after in zip(phase_events, phase_events[1:])
            )
        )
        digest = hashlib.sha256()
        with self.path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        manifest = {
            "schema_version": 1,
            "capture_kind": (
                "human_operated_relative_start_empirical_teaching"
                if self.capture_kind == "empirical_relative_teaching"
                else "human_operated_teleop_full_cycle_evidence"
            ),
            "cycle_count": self.count,
            "error_count": self.error_count,
            "stop_reason": stop_reason,
            "cycle_sha256": digest.hexdigest(),
            "phase_markers_in_order": phase_complete,
            "data_complete": (
                self.count > 0 and self.error_count == 0
                and stop_reason == "teleoperation_inactive"
                and (self.capture_kind == "empirical_relative_teaching" or phase_complete)
            ),
            "physical_task_success_verified": False,
            "automatic_replay_authorized": False,
        }
        (self.session_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return manifest


def append_event(session_dir: Path, phase: str, *, note: str = "") -> dict:
    """Timestamp a human phase marker on the same host clock as cycle records."""
    if phase not in EVENTS:
        raise ValueError(f"unknown event phase: {phase}")
    path = Path(session_dir) / "events.jsonl"
    if not path.is_file():
        raise FileNotFoundError("active trace events.jsonl not found")
    if (Path(session_dir) / "manifest.json").exists():
        raise RuntimeError("trace session is already finalized")
    row = {"unix_ns": time.time_ns(), "monotonic_ns": time.monotonic_ns(),
           "phase": phase, "note": note[:120]}
    payload = (json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
    fd = os.open(path, os.O_WRONLY | os.O_APPEND)
    try:
        if os.write(fd, payload) != len(payload):
            raise OSError("event marker was not fully written")
    finally:
        os.close(fd)
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description="Mark a human teleop demonstration phase")
    parser.add_argument("session_dir", type=Path)
    parser.add_argument("phase", choices=sorted(EVENTS))
    parser.add_argument("--note", default="")
    args = parser.parse_args()
    print(json.dumps(append_event(args.session_dir, args.phase, note=args.note), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
