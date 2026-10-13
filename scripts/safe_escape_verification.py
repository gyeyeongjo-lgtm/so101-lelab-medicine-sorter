"""Pure SAFE_ESCAPE movement verification; importing never opens hardware."""

from __future__ import annotations

import math
from typing import Mapping, Sequence

if __package__:
    from scripts.staged_cycle_execution import JOINT_UNITS
else:
    from staged_cycle_execution import JOINT_UNITS


ARM_JOINTS = tuple(name for name in JOINT_UNITS if name != "gripper")
MAX_ESCAPE_STEP_DEG = 2.0
MIN_MOVEMENT_FRACTION = 0.5
MAX_NONCOMMANDED_DRIFT = 1.0
MAX_TEMPERATURE_C = 55.0


def _finite_mapping(values: Mapping[str, float], name: str) -> dict[str, float]:
    if set(values) != set(JOINT_UNITS):
        raise ValueError(f"{name}_shape_invalid")
    result = {joint: float(values[joint]) for joint in JOINT_UNITS}
    if any(not math.isfinite(value) for value in result.values()):
        raise ValueError(f"{name}_nonfinite")
    return result


def _xyz(values: Sequence[float], name: str) -> tuple[float, float, float]:
    if len(values) != 3:
        raise ValueError(f"{name}_shape_invalid")
    result = tuple(float(value) for value in values)
    if any(not math.isfinite(value) for value in result):
        raise ValueError(f"{name}_nonfinite")
    return result


def evaluate_escape_motion(
    *,
    present_before: Mapping[str, float],
    requested_target: Mapping[str, float],
    present_after: Mapping[str, float],
    grasp_tcp_before_mm: Sequence[float],
    grasp_tcp_after_mm: Sequence[float],
    present_load_before: Mapping[str, int],
    present_load: Mapping[str, int],
    temperature_c: Mapping[str, int],
    terminal_tolerances: Mapping[str, float],
    verified_abs_load_limit: float | None,
    feedback_fresh: bool,
    communication_ok: bool,
    settled: bool,
) -> dict:
    """Decide whether an escape produced sufficient motion in its safe direction.

    Terminal target tolerance is reported separately and never substitutes for
    movement verification.  Present_Load is always retained as signed
    diagnostic telemetry.  When no verified absolute threshold exists, it is
    explicitly non-gating instead of inventing a threshold.
    """
    before = _finite_mapping(present_before, "present_before")
    target = _finite_mapping(requested_target, "requested_target")
    after = _finite_mapping(present_after, "present_after")
    tolerances = _finite_mapping(terminal_tolerances, "terminal_tolerances")
    if any(value <= 0 for value in tolerances.values()):
        raise ValueError("terminal_tolerance_invalid")
    tcp_before = _xyz(grasp_tcp_before_mm, "grasp_tcp_before")
    tcp_after = _xyz(grasp_tcp_after_mm, "grasp_tcp_after")
    for name, values in (("present_load_before", present_load_before),
                         ("present_load", present_load),
                         ("temperature_c", temperature_c)):
        if set(values) != set(JOINT_UNITS):
            raise ValueError(f"{name}_shape_invalid")
        if any(type(values[joint]) is not int for joint in JOINT_UNITS):
            raise ValueError(f"{name}_value_invalid")

    requested_delta = {
        joint: target[joint] - before[joint] for joint in JOINT_UNITS
    }
    if any(abs(requested_delta[joint]) > MAX_ESCAPE_STEP_DEG + 1e-12
           for joint in ARM_JOINTS):
        raise ValueError("escape_step_exceeds_two_degrees")
    commanded = tuple(
        joint for joint in JOINT_UNITS if abs(requested_delta[joint]) > 1e-12
    )
    if not commanded or "gripper" in commanded:
        raise ValueError("escape_commanded_joint_set_invalid")

    joint_motion = {}
    for joint in commanded:
        actual_delta = after[joint] - before[joint]
        fraction = abs(actual_delta) / abs(requested_delta[joint])
        direction_ok = actual_delta * requested_delta[joint] > 0.0
        fraction_ok = fraction + 1e-12 >= MIN_MOVEMENT_FRACTION
        joint_motion[joint] = {
            "requested_delta": requested_delta[joint],
            "actual_delta": actual_delta,
            "movement_fraction": fraction,
            "direction_ok": direction_ok,
            "fraction_ok": fraction_ok,
            "pass": direction_ok and fraction_ok,
        }

    noncommanded_drift = {
        joint: after[joint] - before[joint]
        for joint in JOINT_UNITS if joint not in commanded
    }
    noncommanded_drift_ok = all(
        abs(value) <= MAX_NONCOMMANDED_DRIFT
        for value in noncommanded_drift.values()
    )
    terminal_error = {
        joint: after[joint] - target[joint] for joint in JOINT_UNITS
    }
    terminal_within_tolerance = {
        joint: abs(terminal_error[joint]) <= tolerances[joint]
        for joint in JOINT_UNITS
    }

    if verified_abs_load_limit is None:
        load_limit_status = "NOT_DEFINED"
        load_gate_enabled = False
        load_gate_result = "NOT_APPLICABLE_NOT_DEFINED"
        load_ok = None
    else:
        limit = float(verified_abs_load_limit)
        if not math.isfinite(limit) or limit <= 0:
            raise ValueError("verified_load_limit_invalid")
        load_limit_status = "DEFINED"
        load_gate_enabled = True
        load_ok = all(abs(present_load[joint]) <= limit for joint in JOINT_UNITS)
        load_gate_result = "PASS" if load_ok else "FAIL"
    load_delta = {
        joint: int(present_load[joint]) - int(present_load_before[joint])
        for joint in JOINT_UNITS
    }
    temperature_ok = all(
        temperature_c[joint] <= MAX_TEMPERATURE_C for joint in JOINT_UNITS
    )
    tcp_z_increased = tcp_after[2] > tcp_before[2]
    movement_ok = all(item["pass"] for item in joint_motion.values())
    safety_gates = (
        movement_ok,
        tcp_z_increased,
        temperature_ok,
        noncommanded_drift_ok,
        feedback_fresh is True,
        communication_ok is True,
        settled is True,
    )
    passed = all(safety_gates) and (load_ok is not False)
    return {
        "pass": passed,
        "commanded_joints": list(commanded),
        "joint_motion": joint_motion,
        "movement_ok": movement_ok,
        "grasp_tcp_before_mm": list(tcp_before),
        "grasp_tcp_after_mm": list(tcp_after),
        "grasp_tcp_z_delta_mm": tcp_after[2] - tcp_before[2],
        "grasp_tcp_z_increased": tcp_z_increased,
        "noncommanded_drift": noncommanded_drift,
        "noncommanded_drift_ok": noncommanded_drift_ok,
        "terminal_error": terminal_error,
        "terminal_within_tolerance": terminal_within_tolerance,
        "terminal_tolerance_gates_escape_pass": False,
        "present_load_before": dict(present_load_before),
        "present_load": dict(present_load),
        "present_load_delta": load_delta,
        "verified_abs_load_limit": verified_abs_load_limit,
        "load_limit_status": load_limit_status,
        "load_gate_enabled": load_gate_enabled,
        "load_gate_result": load_gate_result,
        "load_ok": load_ok,
        "temperature_c": dict(temperature_c),
        "temperature_limit_c": MAX_TEMPERATURE_C,
        "temperature_ok": temperature_ok,
        "feedback_fresh": feedback_fresh is True,
        "communication_ok": communication_ok is True,
        "settled": settled is True,
    }
