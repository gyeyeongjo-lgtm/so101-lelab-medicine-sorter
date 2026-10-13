"""Bounded continuous-following execution for one approved joint-space stage.

Unlike :class:`StagedCycle`, intermediate waypoints are not treated as poses
that must settle inside the final tolerance.  A new bounded target may be sent
only after fresh telemetry shows that the previous target remains inside the
configured following-error envelope.  Exceeding the envelope pauses command
production; recovery may resume it, while increasing error or no progress
aborts it.  The final waypoint still uses the ordinary stable reach tolerance.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import time
from typing import Callable, Mapping

if __package__:
    from scripts.staged_cycle_execution import JOINT_UNITS, StagedCycle
else:
    from staged_cycle_execution import JOINT_UNITS, StagedCycle


ARM_NAMES = tuple(name for name in JOINT_UNITS if name != "gripper")
MAX_TEMPERATURE_C = 55


@dataclass(frozen=True)
class FollowingTelemetry:
    positions: Mapping[str, float]
    received_monotonic: float
    goal_raw: Mapping[str, int]
    present_raw: Mapping[str, int]
    moving: Mapping[str, int]
    present_load: Mapping[str, int]
    temperature_c: Mapping[str, int] | None = None


class ContinuousFollowingCycle(StagedCycle):
    """Stream a bounded path without relaxing the final reach tolerance."""

    def __init__(
        self,
        transport,
        final_tolerances: Mapping[str, float],
        *,
        planned_start: Mapping[str, float],
        following_limits: Mapping[str, float],
        max_joint_step_deg: float,
        cadence_s: float,
        no_progress_timeout_s: float,
        progress_epsilon_deg: float,
        final_timeout_s: float,
        feedback_max_age_s: float,
        stable_s: float = 0.1,
        poll_s: float = 0.05,
        log_sink: Callable[[dict], None] | None = None,
    ) -> None:
        super().__init__(
            transport,
            final_tolerances,
            timeout_s=no_progress_timeout_s,
            final_timeout_s=final_timeout_s,
            feedback_max_age_s=feedback_max_age_s,
            stable_s=stable_s,
            poll_s=poll_s,
        )
        if (set(planned_start) != set(JOINT_UNITS) or
                set(following_limits) != set(ARM_NAMES) or
                any(not isinstance(value, (int, float)) or not math.isfinite(value)
                    for value in planned_start.values()) or
                any(not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0
                    for value in following_limits.values()) or
                not math.isfinite(max_joint_step_deg) or
                not 0 < max_joint_step_deg <= 1.0 or
                not math.isfinite(cadence_s) or cadence_s <= 0 or
                not math.isfinite(no_progress_timeout_s) or no_progress_timeout_s <= cadence_s or
                not math.isfinite(progress_epsilon_deg) or progress_epsilon_deg <= 0):
            raise ValueError("invalid_continuous_following_policy")
        self.planned_start = dict(planned_start)
        self.following_limits = dict(following_limits)
        self.max_joint_step_deg = float(max_joint_step_deg)
        self.cadence_s = float(cadence_s)
        self.no_progress_timeout_s = float(no_progress_timeout_s)
        self.progress_epsilon_deg = float(progress_epsilon_deg)
        self.log_sink = log_sink
        self.following_log: list[dict] = []

    def _emit(self, *, action: str, waypoint_index: int,
              goal: Mapping[str, float], telemetry: FollowingTelemetry | None,
              detail: str | None = None) -> None:
        if action not in {"SEND", "PAUSE", "RESUME", "ABORT"}:
            raise ValueError("invalid_following_action")
        errors = None if telemetry is None else {
            name: float(telemetry.positions[name] - goal[name]) for name in JOINT_UNITS
        }
        row = {
            "timestamp_monotonic": time.monotonic(),
            "waypoint": waypoint_index,
            "target_joints": {name: float(goal[name]) for name in JOINT_UNITS},
            "goal_raw": None if telemetry is None else dict(telemetry.goal_raw),
            "present_raw": None if telemetry is None else dict(telemetry.present_raw),
            "following_error": errors,
            "moving": None if telemetry is None else dict(telemetry.moving),
            "present_load": None if telemetry is None else dict(telemetry.present_load),
            "temperature_c": None if telemetry is None else dict(telemetry.temperature_c),
            "action": action,
            "detail": detail,
        }
        self.following_log.append(row)
        if self.log_sink is not None:
            self.log_sink(row)

    def _read_telemetry(self) -> FollowingTelemetry:
        reader = getattr(self.transport, "read_following_telemetry", None)
        if not callable(reader):
            raise RuntimeError("following_telemetry_unavailable")
        sample = reader()
        now = time.monotonic()
        if not isinstance(sample, FollowingTelemetry):
            raise RuntimeError("following_feedback_invalid_or_stale")
        mappings = (sample.positions, sample.goal_raw, sample.present_raw,
                    sample.moving, sample.present_load)
        if (any(set(mapping) != set(JOINT_UNITS) for mapping in mappings) or
                not sample.received_monotonic <= now or
                now - sample.received_monotonic > self.feedback_max_age_s or
                any(not math.isfinite(float(sample.positions[name])) for name in JOINT_UNITS)):
            raise RuntimeError("following_feedback_invalid_or_stale")
        if (not isinstance(sample.temperature_c, Mapping) or
                set(sample.temperature_c) != set(JOINT_UNITS) or
                any(type(sample.temperature_c[name]) is not int
                    for name in JOINT_UNITS)):
            raise RuntimeError("following_temperature_invalid")
        if any(sample.temperature_c[name] > MAX_TEMPERATURE_C
               for name in JOINT_UNITS):
            raise RuntimeError("following_temperature_limit_exceeded")
        return sample

    def _validate_path(self, goals: list[dict[str, float]]) -> None:
        previous = self.planned_start
        held_gripper = self.planned_start["gripper"]
        for goal in goals:
            if (abs(goal["gripper"] - held_gripper) > 1e-9 or
                    max(abs(goal[name] - previous[name]) for name in ARM_NAMES) >
                    self.max_joint_step_deg + 1e-9):
                raise ValueError("continuous_path_step_or_gripper_invalid")
            previous = goal

    def _inside_following_envelope(self, telemetry: FollowingTelemetry,
                                   goal: Mapping[str, float]) -> bool:
        return all(abs(telemetry.positions[name] - goal[name]) <= self.following_limits[name]
                   for name in ARM_NAMES)

    @staticmethod
    def _max_arm_error(telemetry: FollowingTelemetry,
                       goal: Mapping[str, float]) -> float:
        return max(abs(telemetry.positions[name] - goal[name]) for name in ARM_NAMES)

    def _abort(self, *, reason: str, waypoint_index: int,
               goal: Mapping[str, float], telemetry: FollowingTelemetry | None) -> bool:
        self.failure = reason
        self.reach_state = "TIMED_OUT" if "timeout" in reason or "no_progress" in reason else "FEEDBACK_FAILED"
        self._emit(action="ABORT", waypoint_index=waypoint_index,
                   goal=goal, telemetry=telemetry, detail=reason)
        return False

    def _pause_until_recovered(self, *, waypoint_index: int,
                               goal: Mapping[str, float],
                               telemetry: FollowingTelemetry) -> bool:
        self._emit(action="PAUSE", waypoint_index=waypoint_index,
                   goal=goal, telemetry=telemetry, detail="following_limit_exceeded")
        best_error = self._max_arm_error(telemetry, goal)
        previous_error = best_error
        last_progress = time.monotonic()
        increasing_samples = 0
        while not self._stop.wait(self.poll_s):
            try:
                sample = self._read_telemetry()
            except Exception as error:
                return self._abort(
                    reason=f"following_feedback_error:{type(error).__name__}:{error}",
                    waypoint_index=waypoint_index, goal=goal, telemetry=None)
            if self._inside_following_envelope(sample, goal):
                self._emit(action="RESUME", waypoint_index=waypoint_index,
                           goal=goal, telemetry=sample, detail="following_limit_recovered")
                return True
            current_error = self._max_arm_error(sample, goal)
            if current_error <= best_error - self.progress_epsilon_deg:
                best_error = current_error
                last_progress = time.monotonic()
            if current_error >= previous_error + self.progress_epsilon_deg:
                increasing_samples += 1
            else:
                increasing_samples = 0
            previous_error = current_error
            if increasing_samples >= 3:
                return self._abort(
                    reason="following_error_persistently_increasing",
                    waypoint_index=waypoint_index, goal=goal, telemetry=sample)
            if time.monotonic() - last_progress >= self.no_progress_timeout_s:
                return self._abort(
                    reason="following_no_progress_timeout",
                    waypoint_index=waypoint_index, goal=goal, telemetry=sample)
        return False

    def _verify_final(self, *, waypoint_index: int, goal: Mapping[str, float],
                      telemetry: FollowingTelemetry, send_finished: float) -> bool:
        stable_since: float | None = None
        sample = telemetry
        deadline = send_finished + self.final_timeout_s
        while not self._stop.is_set():
            now = time.monotonic()
            reached = (
                all(abs(sample.positions[name] - goal[name]) <= self.tolerances[name]
                    for name in JOINT_UNITS)
                and all(sample.moving[name] == 0 for name in JOINT_UNITS)
            )
            if reached:
                if stable_since is None:
                    stable_since = now
                if now - stable_since >= self.stable_s:
                    self.reach_state = "GOAL_REACHED"
                    self.waypoints_reached = waypoint_index
                    self._last_reached_goal = dict(goal)
                    return True
            else:
                stable_since = None
            if now >= deadline:
                return self._abort(
                    reason="final_joint_target_timeout",
                    waypoint_index=waypoint_index, goal=goal, telemetry=sample)
            self._emit(action="PAUSE", waypoint_index=waypoint_index,
                       goal=goal, telemetry=sample, detail="final_stable_verification")
            if self._stop.wait(self.poll_s):
                return False
            try:
                sample = self._read_telemetry()
            except Exception as error:
                return self._abort(
                    reason=f"final_feedback_error:{type(error).__name__}:{error}",
                    waypoint_index=waypoint_index, goal=goal, telemetry=None)
        return False

    def _run(self, goals: list[dict[str, float]]) -> None:
        try:
            self._validate_path(goals)
            initial = self._read_telemetry()
            if any(abs(initial.positions[name] - self.planned_start[name]) >
                   (2.0 if name == "gripper" else 1.0) for name in JOINT_UNITS):
                self._abort(reason="fresh_start_pose_mismatch", waypoint_index=0,
                            goal=self.planned_start, telemetry=initial)
                return
            last_send_finished: float | None = None
            for index, goal in enumerate(goals, start=1):
                if self._stop.is_set():
                    return
                if last_send_finished is not None:
                    remaining = self.cadence_s - (time.monotonic() - last_send_finished)
                    if remaining > 0 and self._stop.wait(remaining):
                        return
                with self._lock:
                    if self._stop.is_set():
                        return
                    self._inflight = True
                    self.command_state = "SENDING"
                    try:
                        sent = self.transport.send_goal(goal)
                    finally:
                        self._inflight = False
                    if set(sent) != set(goal) or any(
                        not math.isfinite(sent[name]) or abs(sent[name] - value) > 1e-9
                        for name, value in goal.items()
                    ):
                        self.command_state = "REJECTED_OR_CLIPPED"
                        self._abort(reason="actual_sent_goal_differs",
                                    waypoint_index=index, goal=goal, telemetry=None)
                        return
                    self.command_state = "TRANSMITTED_UNACKNOWLEDGED"
                    self.waypoints_transmitted += 1
                last_send_finished = time.monotonic()
                if self._stop.wait(self.cadence_s):
                    return
                try:
                    telemetry = self._read_telemetry()
                except Exception as error:
                    self._abort(
                        reason=f"following_feedback_error:{type(error).__name__}:{error}",
                        waypoint_index=index, goal=goal, telemetry=None)
                    return
                self._emit(action="SEND", waypoint_index=index,
                           goal=goal, telemetry=telemetry, detail="fresh_feedback_after_send")
                if index == len(goals):
                    if not self._verify_final(
                            waypoint_index=index, goal=goal,
                            telemetry=telemetry, send_finished=last_send_finished):
                        return
                elif not self._inside_following_envelope(telemetry, goal):
                    if not self._pause_until_recovered(
                            waypoint_index=index, goal=goal, telemetry=telemetry):
                        return
            if not self._stop.is_set() and self.reach_state == "GOAL_REACHED":
                self.task_state = "USER_CONFIRMATION_REQUIRED"
        except Exception as error:
            self.failure = f"transport_error:{type(error).__name__}:{error}"
            self.reach_state = "FEEDBACK_FAILED"
            fallback_goal = goals[min(self.waypoints_transmitted, len(goals) - 1)]
            self._emit(action="ABORT", waypoint_index=self.waypoints_transmitted,
                       goal=fallback_goal, telemetry=None, detail=self.failure)
