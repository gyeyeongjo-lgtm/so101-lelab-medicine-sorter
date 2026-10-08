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

    def __init__(self, session_dir: Path):
        ticket = os.environ.get("LELAB_TELEOP_TRACE_ONCE_TICKET")
        if ticket:
            # An exact, single-use ticket makes later teleop starts fail closed
            # before any robot bus is opened. A failed session needs re-arming.
            Path(ticket).unlink()
        self.session_dir = Path(session_dir)
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
            "capture_kind": "human_operated_teleop_full_cycle_evidence",
            "cycle_count": self.count,
            "error_count": self.error_count,
            "stop_reason": stop_reason,
            "cycle_sha256": digest.hexdigest(),
            "phase_markers_in_order": phase_complete,
            "data_complete": (
                self.count > 0 and self.error_count == 0 and phase_complete
                and stop_reason == "teleoperation_inactive"
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
