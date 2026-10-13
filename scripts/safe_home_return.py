"""Fail-closed HOME return planning over existing bounded interpolation.

The module is hardware-disconnected.  ``go_home_safe`` orchestrates already
validated segment execution and never starts a later segment after an error.
Actual execution must be supplied by the repository's approved motion/safety
runner; this module does not open ports, change torque, or write servo gains.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Callable, Mapping, Sequence

if __package__:
    from scripts.live_c_approach import ARM_NAMES, interpolate_goals
    from scripts.staged_cycle_execution import JOINT_UNITS
else:
    from live_c_approach import ARM_NAMES, interpolate_goals
    from staged_cycle_execution import JOINT_UNITS


DEFAULT_MAX_RETURN_STEP_DEG = 2.0
LOW_TCP_CLEARANCE_MM = 40.0
MIN_MOVEMENT_FRACTION = 0.5
MAX_NONCOMMANDED_DRIFT_DEG_OR_PP = 1.0
MAX_TEMPERATURE_C = 55.0
SERVO_POSITION_RESOLUTION_DEG = 360.0 / 4095.0


@dataclass(frozen=True)
class ReturnSegment:
    name: str
    goals: tuple[dict[str, float], ...]


@dataclass(frozen=True)
class SafeReturnPlan:
    segments: tuple[ReturnSegment, ...]
    max_joint_step_deg: float
    tcp_was_low: bool
    gripper_held: float


def flatten_return_plan(plan: SafeReturnPlan) -> tuple[tuple[str, dict[str, float]], ...]:
    """Return ordered segment/goal pairs without changing the plan."""
    return tuple(
        (segment.name, dict(goal))
        for segment in plan.segments
        for goal in segment.goals
    )


def _pose(values: Mapping[str, float], label: str) -> dict[str, float]:
    if set(values) != set(JOINT_UNITS):
        raise ValueError(f"{label}_joint_shape_invalid")
    result = {name: float(values[name]) for name in JOINT_UNITS}
    if any(not math.isfinite(value) for value in result.values()):
        raise ValueError(f"{label}_nonfinite")
    return result


def _bounded_escape(current: Mapping[str, float], goals: Sequence[Mapping[str, float]],
                    *, max_step_deg: float) -> tuple[dict[str, float], ...]:
    previous = dict(current)
    checked = []
    if not goals:
        raise ValueError("low_tcp_requires_validated_safe_escape")
    for goal_value in goals:
        goal = _pose(goal_value, "safe_escape")
        if abs(goal["gripper"] - current["gripper"]) > 1e-9:
            raise ValueError("safe_escape_must_hold_gripper")
        if max(abs(goal[name] - previous[name]) for name in ARM_NAMES) > max_step_deg + 1e-9:
            raise ValueError("safe_escape_step_exceeds_limit")
        checked.append(goal)
        previous = goal
    return tuple(checked)


def _segment(start: dict[str, float], target_arm: dict[str, float],
             max_step_deg: float) -> tuple[dict[str, float], ...]:
    if all(abs(target_arm[name] - start[name]) <= 1e-12 for name in ARM_NAMES):
        return ()
    return tuple(interpolate_goals(start, target_arm, max_step_deg))


def build_go_home_safe_plan(
    *,
    current: Mapping[str, float],
    safe_high: Mapping[str, float],
    home: Mapping[str, float],
    current_grasp_tcp_z_mm: float,
    table_reference_z_mm: float,
    safe_escape_goals: Sequence[Mapping[str, float]] = (),
    max_joint_step_deg: float = DEFAULT_MAX_RETURN_STEP_DEG,
) -> SafeReturnPlan:
    """Build CURRENT→(ESCAPE)→SAFE_HIGH(no Pan)→Pan→HOME.

    The gripper is held throughout; opening/closing is a separately approved
    operation.  A low pose cannot be planned unless a Phase-A-validated escape
    segment is supplied.  No step above 2 degrees is accepted by this default
    production API.
    """
    current_pose = _pose(current, "current")
    safe_pose = _pose(safe_high, "safe_high")
    home_pose = _pose(home, "home")
    if (not math.isfinite(current_grasp_tcp_z_mm) or
            not math.isfinite(table_reference_z_mm) or
            not math.isfinite(max_joint_step_deg) or
            not 0 < max_joint_step_deg <= DEFAULT_MAX_RETURN_STEP_DEG):
        raise ValueError("safe_return_policy_invalid")

    tcp_low = current_grasp_tcp_z_mm < (
        table_reference_z_mm + LOW_TCP_CLEARANCE_MM)
    segments = []
    cursor = current_pose
    if tcp_low:
        escape = _bounded_escape(
            cursor, safe_escape_goals, max_step_deg=max_joint_step_deg)
        segments.append(ReturnSegment("SAFE_ESCAPE", escape))
        cursor = dict(escape[-1])
    elif safe_escape_goals:
        raise ValueError("safe_escape_not_allowed_when_tcp_not_low")

    # Raise/shape the arm first while preserving the current Pan and gripper.
    safe_without_pan = {
        name: (cursor[name] if name == "shoulder_pan" else safe_pose[name])
        for name in ARM_NAMES
    }
    goals = _segment(cursor, safe_without_pan, max_joint_step_deg)
    if goals:
        segments.append(ReturnSegment("SAFE_HIGH_EXCEPT_PAN", goals))
        cursor = dict(goals[-1])

    # Only after the non-Pan joints reach SAFE_HIGH may Pan align.
    safe_arm = {name: safe_pose[name] for name in ARM_NAMES}
    goals = _segment(cursor, safe_arm, max_joint_step_deg)
    if goals:
        segments.append(ReturnSegment("PAN_ALIGNMENT", goals))
        cursor = dict(goals[-1])

    # Return to the HOME arm posture while retaining SAFE_HIGH Pan.  Pan is
    # deliberately aligned last, matching the same arm-first rule used on the
    # outbound leg.
    home_without_pan = {
        name: (cursor[name] if name == "shoulder_pan" else home_pose[name])
        for name in ARM_NAMES
    }
    goals = _segment(cursor, home_without_pan, max_joint_step_deg)
    if goals:
        segments.append(ReturnSegment("HOME_EXCEPT_PAN", goals))
        cursor = dict(goals[-1])

    home_arm = {name: home_pose[name] for name in ARM_NAMES}
    goals = _segment(cursor, home_arm, max_joint_step_deg)
    if goals:
        segments.append(ReturnSegment("HOME_PAN_ALIGNMENT", goals))

    return SafeReturnPlan(
        segments=tuple(segments), max_joint_step_deg=max_joint_step_deg,
        tcp_was_low=tcp_low, gripper_held=current_pose["gripper"])


def evaluate_return_waypoint(
    *,
    present_before: Mapping[str, float],
    requested_target: Mapping[str, float],
    present_after: Mapping[str, float],
    moving: Mapping[str, int],
    present_load: Mapping[str, int],
    temperature_c: Mapping[str, int],
    calibrated_bounds: Mapping[str, tuple[float, float]],
    table_proxy_margin_mm: float,
    minimum_table_proxy_margin_mm: float,
    self_collision_proxy_mm: float,
    minimum_self_collision_proxy_mm: float,
    feedback_fresh: bool,
    communication_ok: bool,
) -> dict:
    """Verify one HOME round-trip waypoint from fresh settled feedback.

    Present_Load is retained as signed diagnostic data and never gates the
    result.  Movement checks use the existing 50% and one-degree drift policy.
    Deltas below one verified STS3215 position count are not classified as a
    material command because they cannot be independently observed in raw
    feedback.
    """
    before = _pose(present_before, "present_before")
    target = _pose(requested_target, "requested_target")
    after = _pose(present_after, "present_after")
    for label, values in (("moving", moving), ("present_load", present_load),
                          ("temperature_c", temperature_c)):
        if set(values) != set(JOINT_UNITS) or any(
                type(values[name]) is not int for name in JOINT_UNITS):
            raise ValueError(f"{label}_shape_or_value_invalid")
    if set(calibrated_bounds) != set(JOINT_UNITS):
        raise ValueError("calibrated_bounds_shape_invalid")
    for name, limits in calibrated_bounds.items():
        if (len(limits) != 2 or not all(math.isfinite(float(value)) for value in limits)
                or float(limits[0]) >= float(limits[1])):
            raise ValueError(f"calibrated_bounds_invalid:{name}")
    numeric = (
        table_proxy_margin_mm, minimum_table_proxy_margin_mm,
        self_collision_proxy_mm, minimum_self_collision_proxy_mm,
    )
    if any(not math.isfinite(float(value)) for value in numeric):
        raise ValueError("collision_proxy_nonfinite")

    requested_delta = {
        name: target[name] - before[name] for name in JOINT_UNITS
    }
    if (abs(requested_delta["gripper"]) > 1e-9 or
            any(abs(requested_delta[name]) > DEFAULT_MAX_RETURN_STEP_DEG + 1e-9
                for name in ARM_NAMES)):
        raise ValueError("return_step_or_gripper_invalid")
    material = tuple(
        name for name in ARM_NAMES
        if abs(requested_delta[name]) + 1e-12 >= SERVO_POSITION_RESOLUTION_DEG
    )
    if not material:
        raise ValueError("return_waypoint_has_no_observable_command")

    joint_motion = {}
    for name in material:
        actual_delta = after[name] - before[name]
        fraction = abs(actual_delta) / abs(requested_delta[name])
        direction_ok = actual_delta * requested_delta[name] > 0.0
        fraction_ok = fraction + 1e-12 >= MIN_MOVEMENT_FRACTION
        joint_motion[name] = {
            "requested_delta": requested_delta[name],
            "actual_delta": actual_delta,
            "movement_fraction": fraction,
            "direction_ok": direction_ok,
            "fraction_ok": fraction_ok,
            "pass": direction_ok and fraction_ok,
        }
    noncommanded = tuple(name for name in JOINT_UNITS if name not in material)
    noncommanded_drift = {
        name: after[name] - before[name] for name in noncommanded
    }
    noncommanded_drift_ok = all(
        abs(value) <= MAX_NONCOMMANDED_DRIFT_DEG_OR_PP
        for value in noncommanded_drift.values()
    )
    settled = all(moving[name] == 0 for name in JOINT_UNITS)
    temperature_ok = all(
        temperature_c[name] <= MAX_TEMPERATURE_C for name in JOINT_UNITS
    )
    servo_bounds_ok = all(
        float(calibrated_bounds[name][0]) <= after[name] <=
        float(calibrated_bounds[name][1]) for name in JOINT_UNITS
    )
    table_proxy_ok = (
        table_proxy_margin_mm + 1e-9 >= minimum_table_proxy_margin_mm)
    self_collision_proxy_ok = (
        self_collision_proxy_mm + 1e-9 >= minimum_self_collision_proxy_mm)
    movement_ok = all(item["pass"] for item in joint_motion.values())
    passed = all((
        movement_ok, noncommanded_drift_ok, settled, temperature_ok,
        servo_bounds_ok, table_proxy_ok, self_collision_proxy_ok,
        feedback_fresh is True, communication_ok is True,
    ))
    return {
        "pass": passed,
        "material_commanded_joints": list(material),
        "servo_position_resolution_deg": SERVO_POSITION_RESOLUTION_DEG,
        "joint_motion": joint_motion,
        "movement_ok": movement_ok,
        "noncommanded_drift": noncommanded_drift,
        "noncommanded_drift_ok": noncommanded_drift_ok,
        "moving": dict(moving),
        "settled": settled,
        "temperature_c": dict(temperature_c),
        "temperature_limit_c": MAX_TEMPERATURE_C,
        "temperature_ok": temperature_ok,
        "servo_bounds_ok": servo_bounds_ok,
        "table_proxy_margin_mm": table_proxy_margin_mm,
        "minimum_table_proxy_margin_mm": minimum_table_proxy_margin_mm,
        "table_proxy_ok": table_proxy_ok,
        "self_collision_proxy_mm": self_collision_proxy_mm,
        "minimum_self_collision_proxy_mm": minimum_self_collision_proxy_mm,
        "self_collision_proxy_ok": self_collision_proxy_ok,
        "present_load_diagnostic": dict(present_load),
        "present_load_numeric_gate": False,
        "feedback_fresh": feedback_fresh is True,
        "communication_ok": communication_ok is True,
    }


def go_home_safe(
    plan: SafeReturnPlan,
    *,
    approved: bool,
    execute_segment: Callable[[str, Sequence[Mapping[str, float]]], bool],
    stop_commands: Callable[[], None],
) -> dict:
    """Run approved segments in order, stopping permanently on first failure."""
    if approved is not True:
        raise ValueError("safe_home_user_approval_required")
    completed = []
    for segment in plan.segments:
        try:
            ok = execute_segment(segment.name, segment.goals)
        except Exception as error:
            stop_commands()
            return {
                "status": "STOPPED",
                "completed_segments": completed,
                "failed_segment": segment.name,
                "failure": f"{type(error).__name__}:{error}",
                "further_motion": False,
            }
        if ok is not True:
            stop_commands()
            return {
                "status": "STOPPED",
                "completed_segments": completed,
                "failed_segment": segment.name,
                "failure": "segment_safety_or_feedback_failed",
                "further_motion": False,
            }
        completed.append(segment.name)
    return {
        "status": "HOME_REACHED",
        "completed_segments": completed,
        "failed_segment": None,
        "failure": None,
        "further_motion": False,
    }


def attempt_safe_recovery(*, approved: bool, communication_ok: bool,
                          feedback_ok: bool, planning_failure_only: bool,
                          recovery: Callable[[], bool]) -> bool:
    """Explicitly separate optional recovery from exception handling."""
    if approved is not True:
        raise ValueError("safe_recovery_user_approval_required")
    if not (communication_ok is True and feedback_ok is True and
            planning_failure_only is True):
        raise RuntimeError("safe_recovery_preconditions_failed")
    return recovery() is True
