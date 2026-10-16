"""Pure relative-start teleoperation transforms for LeLab's SO-101 worker.

This module does not open a bus or send motor commands. Values are in the
calibrated action space returned by LeRobot: degrees for arm joints and
0--100 percent for the gripper.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Callable, Mapping


JOINTS = (
    "shoulder_pan",
    "shoulder_lift",
    "elbow_flex",
    "wrist_flex",
    "wrist_roll",
    "gripper",
)
ACTION_KEYS = tuple(f"{joint}.pos" for joint in JOINTS)
ARM_ACTION_KEYS = ACTION_KEYS[:-1]
SUPPORTED_MODES = ("absolute", "relative_start")
ARM_JOINTS = JOINTS[:-1]
MAX_ARM_COMMAND_STEP_DEG = 2.0


@dataclass(frozen=True)
class RelativeOrigins:
    leader: dict[str, float]
    follower: dict[str, float]


@dataclass(frozen=True)
class RelativeSendResult:
    sent: bool
    previous_elbow_target_deg: float | None
    previous_relative_target: dict[str, float]


def teleop_mode(environ: Mapping[str, str]) -> str:
    """Read a session-selectable mode; absolute remains the backwards default."""
    mode = environ.get("LELAB_TELEOP_MODE", "absolute").strip()
    if mode not in SUPPORTED_MODES:
        raise ValueError(f"unsupported LELAB_TELEOP_MODE: {mode!r}")
    return mode


def _finite_action(values: Mapping[str, float], *, source: str) -> dict[str, float]:
    missing = [key for key in ACTION_KEYS if key not in values]
    if missing:
        raise ValueError(f"{source} missing calibrated positions: {', '.join(missing)}")
    result = {key: float(values[key]) for key in ACTION_KEYS}
    if not all(isfinite(value) for value in result.values()):
        raise ValueError(f"{source} contains non-finite calibrated positions")
    return result


def capture_origins(
    read_leader: Callable[[], Mapping[str, float]],
    read_follower: Callable[[], Mapping[str, float]],
) -> RelativeOrigins:
    """Take fresh calibrated leader then follower snapshots without sending."""
    leader = _finite_action(read_leader(), source="leader origin")
    follower_raw = read_follower()
    follower_action = {}
    for joint in JOINTS:
        key = f"{joint}.pos"
        if key in follower_raw:
            follower_action[key] = follower_raw[key]
        elif joint in follower_raw:
            follower_action[key] = follower_raw[joint]
    follower = _finite_action(follower_action, source="follower origin")
    return RelativeOrigins(leader=leader, follower=follower)


def first_relative_target(origins: RelativeOrigins) -> dict[str, float]:
    """The first target is exactly the fresh follower origin, independent of lag."""
    return dict(origins.follower)


def relative_target(
    leader_now: Mapping[str, float], origins: RelativeOrigins
) -> dict[str, float]:
    """Map leader displacement onto follower origin in calibrated units."""
    current = _finite_action(leader_now, source="leader sample")
    return {
        key: origins.follower[key] + (current[key] - origins.leader[key])
        for key in ACTION_KEYS
    }


def arm_only_relative_target(
    leader_now: Mapping[str, float], origins: RelativeOrigins
) -> dict[str, float]:
    """Follow the leader's arm while keeping the gripper at its fresh origin.

    The gripper value remains in the validated target and trace, but an
    arm-only dispatch must omit it from the motor command altogether.
    """
    target = relative_target(leader_now, origins)
    target["gripper.pos"] = origins.follower["gripper.pos"]
    return target


def dispatch_guarded_relative_action(
    action: Mapping[str, float],
    previous_elbow_target_deg: float | None,
    previous_relative_target: Mapping[str, float],
    guarded_sender: Callable[
        [dict[str, float], float | None], Mapping[str, float] | None
    ],
    *,
    arm_only: bool = False,
) -> RelativeSendResult:
    """Send one validated relative target, or preserve state on HOLD.

    ``guarded_sender`` owns the single possible send. Returning ``None`` means
    HOLD, so this function does not call any fallback sender or touch motor
    registers. Exceptions (ABORT) propagate to the teleop worker.
    """
    target = _finite_action(action, source="guarded relative target")
    previous = _finite_action(
        previous_relative_target, source="previous relative target"
    )
    if arm_only:
        if target["gripper.pos"] != previous["gripper.pos"]:
            raise RuntimeError("arm-only relative target changed gripper hold value")
        send_target = {key: target[key] for key in ARM_ACTION_KEYS}
    else:
        send_target = target
    sent_action = guarded_sender(send_target, previous_elbow_target_deg)
    if sent_action is None:
        return RelativeSendResult(
            sent=False,
            previous_elbow_target_deg=previous_elbow_target_deg,
            previous_relative_target=previous,
        )
    if arm_only:
        if set(sent_action) != set(ARM_ACTION_KEYS):
            raise RuntimeError("arm-only dispatch returned unexpected motor keys")
        sent_action = {**sent_action, "gripper.pos": previous["gripper.pos"]}
    sent = _finite_action(sent_action, source="guarded sent action")
    return RelativeSendResult(
        sent=True,
        previous_elbow_target_deg=sent["elbow_flex.pos"],
        previous_relative_target=target,
    )


def calibrated_action_bounds(robot) -> dict[str, tuple[float, float]]:
    """Return loaded follower servo limits in the same units as send_action.

    LeRobot 0.6's bus normalization is the authoritative conversion for both
    degree-mode arm motors and the range_0_100 gripper. No target is clipped.
    """
    bus = getattr(robot, "bus", None)
    calibration = getattr(bus, "calibration", None)
    motors = getattr(bus, "motors", None)
    normalize = getattr(bus, "_normalize", None)
    if calibration is None or motors is None or not callable(normalize):
        raise RuntimeError("follower calibrated range conversion is unavailable")

    result: dict[str, tuple[float, float]] = {}
    for joint in JOINTS:
        try:
            motor_id = motors[joint].id
            item = calibration[joint]
            raw_min = item.range_min if hasattr(item, "range_min") else item["range_min"]
            raw_max = item.range_max if hasattr(item, "range_max") else item["range_max"]
            if int(raw_min) >= int(raw_max):
                raise ValueError("invalid calibrated raw endpoints")
            low_value = float(normalize({motor_id: int(raw_min)})[motor_id])
            high_value = float(normalize({motor_id: int(raw_max)})[motor_id])
        except Exception as exc:
            raise RuntimeError(f"cannot resolve follower servo range for {joint}") from exc
        if not isfinite(low_value) or not isfinite(high_value) or low_value == high_value:
            raise RuntimeError(f"invalid normalized follower servo range for {joint}")
        result[joint] = (min(low_value, high_value), max(low_value, high_value))
    return result


def out_of_range_targets(
    action: Mapping[str, float], bounds: Mapping[str, tuple[float, float]]
) -> dict[str, tuple[float, float, float]]:
    """Return invalid targets as joint -> (target, min, max); never clip."""
    values = _finite_action(action, source="follower target")
    violations: dict[str, tuple[float, float, float]] = {}
    for joint in JOINTS:
        if joint not in bounds:
            raise ValueError(f"calibrated follower range missing for {joint}")
        lower, upper = map(float, bounds[joint])
        target = values[f"{joint}.pos"]
        if not isfinite(lower) or not isfinite(upper) or lower >= upper:
            raise ValueError(f"invalid calibrated follower range for {joint}")
        if target < lower or target > upper:
            violations[joint] = (target, lower, upper)
    return violations


def oversized_arm_steps(
    action: Mapping[str, float],
    previous_action: Mapping[str, float],
    *,
    max_step_deg: float = MAX_ARM_COMMAND_STEP_DEG,
) -> dict[str, tuple[float, float, float]]:
    """Return arm command jumps over the existing 2-degree guard; never clip."""
    current = _finite_action(action, source="follower target")
    previous = _finite_action(previous_action, source="previous follower target")
    if not isfinite(max_step_deg) or max_step_deg <= 0:
        raise ValueError("max arm command step must be finite and positive")
    violations = {}
    for joint in ARM_JOINTS:
        key = f"{joint}.pos"
        step = current[key] - previous[key]
        if abs(step) > max_step_deg:
            violations[joint] = (previous[key], current[key], step)
    return violations
