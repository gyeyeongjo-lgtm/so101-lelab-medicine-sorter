"""Temporary manual Elbow guard using the follower's loaded servo calibration.

This is not an autonomous planning limit or proof of physical clearance.
Rejected targets are never clipped; URDF remains unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from logging import Logger
from math import isfinite
from typing import Literal


ELBOW_LOWER_DEG = -100.0
ELBOW_UPPER_DEG = 90.0
NEAR_LIMIT_DEG = 5.0
TOWARD_LIMIT_ALLOWANCE_DEG = 0.5
LIMIT_RESERVE_DEG = 2.0
MAX_COMMAND_STEP_DEG = 2.0
RECOVERY_MAX_CURRENT_DEG = 91.0
RECOVERY_TARGET_MIN_DEG = 88.8
RECOVERY_TARGET_MAX_DEG = 89.2
RECOVERY_OTHER_AXIS_MAX_ERROR_DEG = 2.0
RECOVERY_GRIPPER_MAX_ERROR_PP = 2.5
RECOVERY_OTHER_JOINTS = (
    "shoulder_pan", "shoulder_lift", "wrist_flex", "wrist_roll", "gripper"
)


@dataclass(frozen=True)
class ElbowGuardResult:
    current_deg: float
    target_deg: float
    delta_deg: float
    lower_margin_deg: float
    upper_margin_deg: float
    limit_direction: str
    limit_side: str
    action: Literal["SEND", "HOLD", "ABORT"]
    reason: str | None


def evaluate_elbow_target(
    current_deg: float,
    target_deg: float,
    previous_target_deg: float | None,
    *,
    lower_deg: float = ELBOW_LOWER_DEG,
    upper_deg: float = ELBOW_UPPER_DEG,
) -> ElbowGuardResult:
    """Classify one target before any motor command is sent.

    ``current_deg`` is fresh follower feedback. The 2-degree command-to-command
    step guard is explicit because this installation has max_relative_target=None.
    """
    delta = target_deg - current_deg
    lower_margin = current_deg - lower_deg
    upper_margin = upper_deg - current_deg
    if upper_margin <= NEAR_LIMIT_DEG:
        side = "upper"
        direction = "toward_limit" if delta > 0 else "away_from_limit" if delta < 0 else "stationary"
    elif lower_margin <= NEAR_LIMIT_DEG:
        side = "lower"
        direction = "toward_limit" if delta < 0 else "away_from_limit" if delta > 0 else "stationary"
    else:
        side = "none"
        direction = "inside_joint_range"
    decision: Literal["SEND", "HOLD", "ABORT"] = "SEND"
    reason = None

    if not all(isfinite(value) for value in (current_deg, target_deg, delta, lower_deg, upper_deg)) or lower_deg >= upper_deg:
        decision = "ABORT"
        reason = "non_finite"
    elif not lower_deg <= current_deg <= upper_deg:
        decision = "ABORT"
        reason = "feedback_outside_servo_calibration"
    elif not lower_deg <= target_deg <= upper_deg:
        decision = "ABORT"
        reason = "target_outside_servo_calibration"
    elif previous_target_deg is not None and (
        not isfinite(previous_target_deg)
        or abs(target_deg - previous_target_deg) > MAX_COMMAND_STEP_DEG
    ):
        decision = "ABORT"
        reason = "command_step_over_2_deg"
    elif upper_margin <= NEAR_LIMIT_DEG and delta > 0 and (
        delta > TOWARD_LIMIT_ALLOWANCE_DEG
        or target_deg > upper_deg - LIMIT_RESERVE_DEG
    ):
        decision = "HOLD"
        reason = "blocked_toward_upper_limit"
    elif lower_margin <= NEAR_LIMIT_DEG and delta < 0 and (
        -delta > TOWARD_LIMIT_ALLOWANCE_DEG
        or target_deg < lower_deg + LIMIT_RESERVE_DEG
    ):
        decision = "HOLD"
        reason = "blocked_toward_lower_limit"

    return ElbowGuardResult(
        current_deg=current_deg,
        target_deg=target_deg,
        delta_deg=delta,
        lower_margin_deg=lower_margin,
        upper_margin_deg=upper_margin,
        limit_direction=direction,
        limit_side=side,
        action=decision,
        reason=reason,
    )


def enforce_elbow_target(
    current_deg: float,
    target_deg: float,
    previous_target_deg: float | None,
    logger: Logger,
    *,
    lower_deg: float = ELBOW_LOWER_DEG,
    upper_deg: float = ELBOW_UPPER_DEG,
) -> ElbowGuardResult:
    """Log every decision before SEND/HOLD/ABORT acts on the target."""
    result = evaluate_elbow_target(current_deg, target_deg, previous_target_deg,
                                   lower_deg=lower_deg, upper_deg=upper_deg)
    level = {"SEND": "info", "HOLD": "warning", "ABORT": "error"}[result.action]
    getattr(logger, level)(
        "Temporary Elbow guard: joint=elbow_flex current=%.3f requested_target=%.3f "
        "delta=%.3f lower_margin=%.3f upper_margin=%.3f direction=%s limit=%s "
        "action=%s reason=%s",
        result.current_deg,
        result.target_deg,
        result.delta_deg,
        result.lower_margin_deg,
        result.upper_margin_deg,
        result.limit_direction,
        result.limit_side,
        result.action,
        result.reason or "within_limits",
    )
    if result.action == "ABORT":
        raise RuntimeError(f"Temporary Elbow guard blocked: {result.reason}")
    return result


def guarded_elbow_send(robot, action: dict, previous_target_deg: float | None,
                       logger: Logger) -> dict | None:
    """Read fresh feedback and the loaded servo calibration before each send."""
    calibration = robot.calibration["elbow_flex"]
    lower_raw = calibration.range_min if hasattr(calibration, "range_min") else calibration["range_min"]
    upper_raw = calibration.range_max if hasattr(calibration, "range_max") else calibration["range_max"]
    if (not isinstance(lower_raw, int) or not isinstance(upper_raw, int) or
            not 0 <= lower_raw < upper_raw < 4096):
        raise RuntimeError("Elbow servo calibration range unavailable")
    midpoint = (lower_raw + upper_raw) / 2
    lower_deg = (lower_raw - midpoint) * 360 / 4095
    upper_deg = (upper_raw - midpoint) * 360 / 4095
    current = robot.bus.read("Present_Position", "elbow_flex", num_retry=0)
    decision = enforce_elbow_target(current, action["elbow_flex.pos"], previous_target_deg,
                                    logger, lower_deg=lower_deg, upper_deg=upper_deg)
    if decision.action == "HOLD":
        return None
    return robot.send_action(action)


def evaluate_elbow_recovery_target(
    current_deg: float,
    target_deg: float,
    previous_target_deg: float | None,
) -> ElbowGuardResult:
    """One-shot, inward-only return to about +89 degrees; normal guard is unchanged."""
    delta = target_deg - current_deg
    lower_margin = current_deg - ELBOW_LOWER_DEG
    upper_margin = ELBOW_UPPER_DEG - current_deg
    action: Literal["SEND", "HOLD", "ABORT"] = "HOLD"
    reason = "recovery_waiting_for_inward_target"
    direction = "toward_limit" if delta > 0 else "away_from_limit" if delta < 0 else "stationary"

    if not all(isfinite(value) for value in (current_deg, target_deg)) or (
        previous_target_deg is not None and not isfinite(previous_target_deg)
    ):
        action, reason = "ABORT", "non_finite"
    elif not ELBOW_UPPER_DEG < current_deg <= RECOVERY_MAX_CURRENT_DEG and not (
        RECOVERY_TARGET_MIN_DEG <= current_deg <= ELBOW_UPPER_DEG
    ):
        action, reason = "ABORT", "recovery_feedback_outside_window"
    elif previous_target_deg is None or abs(target_deg - previous_target_deg) > MAX_COMMAND_STEP_DEG:
        action, reason = "ABORT", "command_step_over_2_deg"
    elif current_deg <= RECOVERY_TARGET_MAX_DEG:
        reason = "recovery_goal_reached"
    elif RECOVERY_TARGET_MIN_DEG <= previous_target_deg <= RECOVERY_TARGET_MAX_DEG:
        reason = "recovery_goal_already_sent"
    elif target_deg > ELBOW_UPPER_DEG:
        reason = "recovery_target_outside_urdf"
    elif target_deg > RECOVERY_TARGET_MAX_DEG or target_deg < RECOVERY_TARGET_MIN_DEG:
        reason = "recovery_target_outside_89_deg_window"
    elif delta >= 0:
        reason = "blocked_toward_upper_limit"
    elif current_deg - target_deg > MAX_COMMAND_STEP_DEG:
        action, reason = "ABORT", "command_step_over_2_deg"
    else:
        action, reason = "SEND", "recovery_inward_to_89_deg"

    return ElbowGuardResult(
        current_deg=current_deg,
        target_deg=target_deg,
        delta_deg=delta,
        lower_margin_deg=lower_margin,
        upper_margin_deg=upper_margin,
        limit_direction=direction,
        limit_side="upper",
        action=action,
        reason=reason,
    )


def guarded_elbow_recovery_send(robot, action: dict, previous_target_deg: float | None,
                                logger: Logger) -> dict | None:
    """Read all axes, keep the other five at fresh feedback, and send at most once."""
    feedback = robot.bus.sync_read("Present_Position", num_retry=0)
    current = feedback["elbow_flex"]
    target = action["elbow_flex.pos"]
    decision = evaluate_elbow_recovery_target(current, target, previous_target_deg)
    level = {"SEND": "info", "HOLD": "warning", "ABORT": "error"}[decision.action]
    getattr(logger, level)(
        "Manual Elbow recovery: joint=elbow_flex current=%.3f requested_target=%.3f "
        "delta=%.3f lower_margin=%.3f upper_margin=%.3f direction=%s "
        "action=%s reason=%s",
        decision.current_deg, decision.target_deg, decision.delta_deg,
        decision.lower_margin_deg, decision.upper_margin_deg,
        decision.limit_direction, decision.action, decision.reason,
    )
    if decision.action == "ABORT":
        raise RuntimeError(f"Manual Elbow recovery blocked: {decision.reason}")
    if decision.action == "HOLD":
        return None

    frozen_action = dict(action)
    for joint in RECOVERY_OTHER_JOINTS:
        observed = feedback[joint]
        requested = action[f"{joint}.pos"]
        tolerance = (RECOVERY_GRIPPER_MAX_ERROR_PP if joint == "gripper"
                     else RECOVERY_OTHER_AXIS_MAX_ERROR_DEG)
        if not all(isfinite(v) for v in (observed, requested)) or abs(requested - observed) > tolerance:
            raise RuntimeError(f"Manual Elbow recovery blocked: {joint}_alignment_or_feedback")
        frozen_action[f"{joint}.pos"] = observed
    logger.info("Manual Elbow recovery SEND: other five goals equal fresh feedback")
    return robot.send_action(frozen_action)
