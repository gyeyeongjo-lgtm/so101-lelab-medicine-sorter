"""Hardware-disconnected contract for a human-gated, program-controlled cycle.

There is deliberately no LeRobot/serial/HTTP adapter here. A caller may supply a
test transport; connecting a real bus requires a separately reviewed adapter,
validated route, exclusive ownership, and a new motion approval.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import threading
import time
from typing import Mapping, Protocol


JOINT_UNITS = {
    "shoulder_pan": "deg", "shoulder_lift": "deg", "elbow_flex": "deg",
    "wrist_flex": "deg", "wrist_roll": "deg", "gripper": "0_to_100",
}
STAGES = ("approach", "grasp", "transfer", "place", "release", "retreat")


@dataclass(frozen=True)
class Feedback:
    positions: Mapping[str, float]
    received_monotonic: float


class TestTransport(Protocol):
    def send_goal(self, goal: Mapping[str, float]) -> Mapping[str, float]:
        """Return the actual transmitted goal (clipping must be visible)."""

    def read_feedback(self) -> Feedback | None:
        """Return follower feedback, not a leader request or commanded target."""

    def is_quiescent(self) -> bool:
        """True only if this transport has no pending write or command producer."""


class StagedCycle:
    """Validated goal sequence per approved stage; stages never auto-advance."""

    def __init__(self, transport: TestTransport, tolerances: Mapping[str, float], *,
                 timeout_s: float, feedback_max_age_s: float, stable_s: float = 0.1,
                 poll_s: float = 0.01, final_timeout_s: float | None = None):
        resolved_final_timeout_s = timeout_s if final_timeout_s is None else final_timeout_s
        if (set(tolerances) != set(JOINT_UNITS) or
                any(not math.isfinite(v) or v <= 0 for v in tolerances.values()) or
                not all(math.isfinite(v) and v > 0 for v in
                        (timeout_s, feedback_max_age_s, poll_s,
                         resolved_final_timeout_s)) or
                not math.isfinite(stable_s) or stable_s < 0):
            raise ValueError("invalid_reach_policy")
        self.transport = transport
        self.tolerances = dict(tolerances)
        self.timeout_s = timeout_s
        self.final_timeout_s = resolved_final_timeout_s
        self.feedback_max_age_s = feedback_max_age_s
        self.stable_s = stable_s
        self.poll_s = poll_s
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._worker: threading.Thread | None = None
        self._inflight = False
        self.stage_index = 0
        self.stage: str | None = None
        self.command_state = "NOT_SENT"
        self.reach_state = "NOT_REACHED"
        self.task_state = "UNVERIFIED"
        self.command_stop_state = "NOT_REQUESTED"
        # No encoder/visual stop verification is available from this fake-only
        # execution contract. Command quiescence must never imply arm stillness.
        self.arm_stop_state = "NOT_VERIFIED"
        self.failure: str | None = None
        self.waypoints_transmitted = 0
        self.waypoints_reached = 0
        self._last_reached_goal: dict[str, float] | None = None

    def start_stage(self, stage: str,
                    goals: Mapping[str, float] | list[Mapping[str, float]], *,
                    approved: bool) -> None:
        if approved is not True:
            raise ValueError("human_stage_approval_required")
        if (self._worker is not None and self._worker.is_alive()) or self._stop.is_set():
            raise ValueError("worker_active_or_stop_requested")
        if self.stage is not None and self.task_state != "HUMAN_CONFIRMED":
            raise ValueError("previous_task_result_unverified")
        if self.stage_index >= len(STAGES) or stage != STAGES[self.stage_index]:
            raise ValueError("stage_order_or_cycle_complete")
        goals = [goals] if isinstance(goals, Mapping) else goals
        if (not isinstance(goals, list) or not goals or
                any(not isinstance(goal, Mapping) or set(goal) != set(JOINT_UNITS) or
                    any(not isinstance(v, (int, float)) or not math.isfinite(v)
                        for v in goal.values()) for goal in goals)):
            raise ValueError("invalid_joint_goal")
        self.stage = stage
        self.command_state = "NOT_SENT"
        self.reach_state = "NOT_REACHED"
        self.task_state = "UNVERIFIED"
        self.failure = None
        self.waypoints_transmitted = 0
        self.waypoints_reached = 0
        self._worker = threading.Thread(target=self._run,
                                        args=([dict(goal) for goal in goals],), daemon=True)
        self._worker.start()

    def _run(self, goals: list[dict[str, float]]) -> None:
        try:
            last_index = len(goals) - 1
            for index, goal in enumerate(goals):
                timeout_s = self.final_timeout_s if index == last_index else self.timeout_s
                if self._stop.is_set() or not self._run_goal(goal, timeout_s=timeout_s):
                    return
            if not self._stop.is_set():
                self.task_state = "USER_CONFIRMATION_REQUIRED"
        except Exception as error:
            self.failure = f"transport_error:{type(error).__name__}:{error}"
            if self.command_state == "SENDING":
                self.command_state = "SEND_FAILED"
            elif self.reach_state != "GOAL_REACHED":
                self.reach_state = "FEEDBACK_FAILED"

    def _run_goal(self, goal: dict[str, float], *, timeout_s: float) -> bool:
        self.command_state = "NOT_SENT"
        self.reach_state = "NOT_REACHED"
        # A stop requested after the send gate may leave one in-flight write;
        # STOP_COMPLETED must wait for it to finish.
        with self._lock:
            if self._stop.is_set():
                return False
            if self._last_reached_goal is not None:
                current = self.transport.read_feedback()
                now = time.monotonic()
                valid = (current is not None and
                         set(current.positions) == set(self._last_reached_goal) and
                         current.received_monotonic <= now and
                         now - current.received_monotonic <= self.feedback_max_age_s and
                         all(math.isfinite(current.positions[name]) and
                             abs(current.positions[name] - value) <= self.tolerances[name]
                             for name, value in self._last_reached_goal.items()))
                if not valid:
                    self.failure = "current_pose_mismatch_or_stale"
                    return False
            if self._stop.is_set():
                return False
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
                self.failure = "actual_sent_goal_differs"
                return False
            self.command_state = "TRANSMITTED_UNACKNOWLEDGED"
            self.waypoints_transmitted += 1

        send_finished = time.monotonic()
        deadline = send_finished + timeout_s
        stable_since: float | None = None
        last_errors: dict[str, float] | None = None
        while not self._stop.is_set():
            now = time.monotonic()
            if now >= deadline:
                self.reach_state = "TIMED_OUT"
                detail = "unknown" if last_errors is None else ",".join(
                    f"{name}={error:+.3f}" for name, error in last_errors.items())
                self.failure = f"joint_target_timeout:last_error_deg_or_pp:{detail}"
                return False
            feedback = self.transport.read_feedback()
            now = time.monotonic()
            if self._stop.is_set():
                return False
            fresh = (feedback is not None and
                     send_finished < feedback.received_monotonic <= now and
                     now - feedback.received_monotonic <= self.feedback_max_age_s)
            if (fresh and set(feedback.positions) == set(goal) and
                    all(math.isfinite(feedback.positions[name]) for name in goal)):
                last_errors = {
                    name: feedback.positions[name] - goal[name] for name in goal
                }
            reached = (fresh and set(feedback.positions) == set(goal) and
                       all(math.isfinite(feedback.positions[name]) and
                           abs(feedback.positions[name] - goal[name]) <= self.tolerances[name]
                           for name in goal))
            if reached:
                if stable_since is None:
                    stable_since = now
                if now - stable_since >= self.stable_s:
                    self.reach_state = "GOAL_REACHED"
                    self.waypoints_reached += 1
                    self._last_reached_goal = dict(goal)
                    return True
            else:
                stable_since = None
            self._stop.wait(self.poll_s)
        return False

    def confirm_task_result(self, *, stage: str, human_observed: bool, result: bool) -> None:
        if (self._stop.is_set() or stage != self.stage or
                self._worker is None or self._worker.is_alive() or
                self.reach_state != "GOAL_REACHED" or
                self.task_state != "USER_CONFIRMATION_REQUIRED"):
            raise ValueError("stage_not_awaiting_result_confirmation")
        if human_observed is not True or type(result) is not bool:
            raise ValueError("independent_result_confirmation_required")
        if not result:
            self.task_state = "FAILED"
            self.failure = "human_reported_task_failure"
            return
        self.task_state = "HUMAN_CONFIRMED"
        self.stage_index += 1

    def request_stop(self) -> None:
        # No torque-disable or blind retreat. Stop is only a production gate;
        # physical hold/recovery remains a separately approved site procedure.
        self._stop.set()
        self.command_stop_state = "REQUESTED"
        stop_commands = getattr(self.transport, "stop_commands", None)
        if callable(stop_commands):
            stop_commands()

    def verify_stop_completed(self, *, timeout_s: float = 0.0) -> bool:
        if not self._stop.is_set():
            raise ValueError("stop_not_requested")
        if self._worker is not None:
            self._worker.join(timeout_s)
        # Worker exit, no in-flight send, and transport confirmation are all
        # required. A stop API response or flag alone is insufficient.
        acquired = self._lock.acquire(blocking=False)
        try:
            idle = acquired and not self._inflight
        finally:
            if acquired:
                self._lock.release()
        completed = (idle and (self._worker is None or not self._worker.is_alive())
                     and self.transport.is_quiescent())
        self.command_stop_state = "COMPLETED" if completed else "PENDING"
        return completed

    def verify_arm_stopped(self, *, motion_tolerances: Mapping[str, float],
                           window_s: float, timeout_s: float,
                           human_confirmed: bool) -> bool:
        """Read new encoder samples after command stop; still require site confirmation.

        This checks joint *stillness*, not that the arm reached a target or that
        a held object is supported. It sends no command and never changes torque.
        """
        if self.command_stop_state != "COMPLETED":
            raise ValueError("command_stop_not_completed")
        if (set(motion_tolerances) != set(JOINT_UNITS) or
                any(not math.isfinite(value) or value <= 0
                    for value in motion_tolerances.values()) or
                not math.isfinite(window_s) or window_s <= 0 or
                not math.isfinite(timeout_s) or timeout_s <= window_s):
            raise ValueError("invalid_stillness_policy")
        self.arm_stop_state = "NOT_VERIFIED"
        if human_confirmed is not True:
            return False
        deadline = time.monotonic() + timeout_s
        first: Feedback | None = None
        previous_time = -math.inf
        while time.monotonic() < deadline:
            sample = self.transport.read_feedback()
            now = time.monotonic()
            if (sample is None or set(sample.positions) != set(JOINT_UNITS) or
                    not previous_time < sample.received_monotonic <= now or
                    now - sample.received_monotonic > self.feedback_max_age_s or
                    any(not math.isfinite(sample.positions[name]) for name in JOINT_UNITS)):
                return False
            previous_time = sample.received_monotonic
            if first is None:
                first = sample
            elif any(abs(sample.positions[name] - first.positions[name]) >
                     motion_tolerances[name] for name in JOINT_UNITS):
                return False
            elif sample.received_monotonic - first.received_monotonic >= window_s:
                self.arm_stop_state = "FEEDBACK_AND_HUMAN_CONFIRMED"
                return True
            time.sleep(self.poll_s)
        return False

    def wait_worker(self, timeout_s: float) -> bool:
        if self._worker is None:
            return True
        self._worker.join(timeout_s)
        return not self._worker.is_alive()
