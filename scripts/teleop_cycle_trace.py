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

    if __package__ == "scripts":
        from scripts.urdf_forward_kinematics import UrdfKinematics
    else:
        from .urdf_forward_kinematics import UrdfKinematics

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
        if ticket:
            # An exact, single-use ticket makes later teleop starts fail closed
            # before any robot bus is opened. A failed session needs re-arming.
            Path(ticket).unlink()
        self.session_dir = Path(session_dir)
        self.capture_kind = capture_kind
        self.session_dir.mkdir(parents=True, exist_ok=False)
        self.path = self.session_dir / "cycles.jsonl"
        self.errors_path = self.session_dir / "errors.jsonl"
        self.events_path = self.session_dir / "events.jsonl"
        self._cycles = self.path.open("x", encoding="utf-8")
        self._errors = self.errors_path.open("x", encoding="utf-8")
        self.events_path.touch(exist_ok=False)
        self.count = 0
        self.error_count = 0
        self.closed = False
        self.first_cycle_monotonic_ns: int | None = None
        self.last_cycle_monotonic_ns: int | None = None

    def capture_cycle(
        self,
        read_leader: Callable[[], Mapping[str, float]],
        send_action: Callable[[Mapping[str, float]], Mapping[str, float]],
        read_feedback: Callable[[], Mapping[str, float]],
        read_diagnostics: Callable[[dict[str, float]], Mapping[str, object]] | None = None,
    ) -> dict:
        if self.closed:
            raise RuntimeError("cycle trace is closed")
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
        seq = self.count + self.error_count
        stage = "leader_validation"
        started_ns = time.time_ns()
        started_monotonic_ns = time.monotonic_ns()
        try:
            leader = _positions(leader_action, suffix=".pos", source="leader")
            command = _positions(relative_target, suffix=".pos", source="relative target")
            if not isinstance(command_sent, bool):
                raise ValueError("command_sent must be boolean")
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
