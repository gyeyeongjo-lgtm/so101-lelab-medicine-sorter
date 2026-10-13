#!/usr/bin/env python3
"""Execute one approved live-C move to the pre-approach joint target only.

Dry-run is the default. Live mode owns only the canonical follower bus, reads
the actual start pose, holds the fresh gripper position, and sends bounded
joint interpolation. It never starts/stops LeLab or advances to grasp/lift.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import time

if __package__:
    from scripts.continuous_following_execution import (
        ContinuousFollowingCycle, FollowingTelemetry,
    )
    from scripts.so101_exclusive_bus import ExclusiveFollowerLease, SystemBusProbe
    from scripts.so101_follower_transport import ARM_LIMITS_DEG, SO101FollowerTransport
    from scripts.staged_cycle_execution import JOINT_UNITS, StagedCycle
else:
    from continuous_following_execution import ContinuousFollowingCycle, FollowingTelemetry
    from so101_exclusive_bus import ExclusiveFollowerLease, SystemBusProbe
    from so101_follower_transport import ARM_LIMITS_DEG, SO101FollowerTransport
    from staged_cycle_execution import JOINT_UNITS, StagedCycle


ARM_NAMES = tuple(name for name in JOINT_UNITS if name != "gripper")
EXPECTED_URDF_SHA256 = "443d38d756e01bac7d3455b24430047ddc6427105e0d3454b2003116f5f67236"
EXPECTED_SERIAL = "5AE6058306"
PRE_APPROACH_SCOPE = "live_c_pre_approach_only"
RETURN_TO_PICK_READY_SCOPE = "live_c_return_to_pick_ready_only"
LEGACY_APPROACH_ONLY_SCOPE = "live_c_approach_only"
CURRENT_TO_C_START_POSE = "C_RETURN_ACTUAL_ATTEMPT2"
STRICT_POSE_TOLERANCES_DEG = {
    "shoulder_pan": 0.5,
    "shoulder_lift": 1.5,
    "elbow_flex": 1.5,
    "wrist_flex": 0.5,
    "wrist_roll": 0.5,
}
WRIST_LEAD_PHASE_NAME = "WRIST_LEAD_2DEG"
WRIST_LEAD_PHASE_WAYPOINTS = 2
WRIST_LEAD_PHASE_GATE_POLICY = {
    "commanded_joint": "wrist_flex",
    "target_tolerance_deg": 0.5,
    "non_commanded_drift_limit_deg": 1.0,
    "require_moving_zero": True,
    "require_tcp_z_increase": True,
    "maximum_temperature_c": 55,
    "feedback_max_age_s": 0.5,
}
RUN_PHRASES = frozenset((
    "RUN LIVE C APPROACH",
    "RUN SAFE HIGH TO C PRE APPROACH",
    "RUN HOME TO C PRE APPROACH",
    "RUN PICK READY TO C PRE APPROACH",
    "RUN C PRE APPROACH TO PICK READY",
    "RUN CURRENT TO C PRE APPROACH",
))
START_POSE_RUN_PHRASES = {
    None: "RUN LIVE C APPROACH",
    "SAFE_HIGH": "RUN SAFE HIGH TO C PRE APPROACH",
    "HOME": "RUN HOME TO C PRE APPROACH",
    "PICK_READY": "RUN PICK READY TO C PRE APPROACH",
    "C_PRE_APPROACH_ACTUAL_ATTEMPT1": "RUN C PRE APPROACH TO PICK READY",
    CURRENT_TO_C_START_POSE: "RUN CURRENT TO C PRE APPROACH",
}
SCOPE_CONTRACTS = {
    PRE_APPROACH_SCOPE: {
        "start_pose_names": {
            None, "HOME", "SAFE_HIGH", "PICK_READY", CURRENT_TO_C_START_POSE,
        },
        "stage": "approach",
        "reached_marker": "APPROACH_REACHED",
        "completion_prompt": (
            "Physical TCP above C and scene safe? Type APPROACH CONFIRMED: "
        ),
        "completion_phrase": "APPROACH CONFIRMED",
        "pass_marker": "PRE_APPROACH_PASS",
    },
    RETURN_TO_PICK_READY_SCOPE: {
        "start_pose_names": {"C_PRE_APPROACH_ACTUAL_ATTEMPT1"},
        # StagedCycle is a fresh one-shot controller here, so its first and
        # only internal stage must remain the existing "approach" stage. The
        # scope, prompts, markers, and target pose keep the return operation
        # externally distinct without expanding the controller state machine.
        "stage": "approach",
        "reached_marker": "PICK_READY_REACHED",
        "completion_prompt": (
            "Physical PICK_READY reached and scene safe? "
            "Type PICK_READY CONFIRMED: "
        ),
        "completion_phrase": "PICK_READY CONFIRMED",
        "pass_marker": "PICK_READY_RETURN_PASS",
    },
}


def load_plan(path: Path, *,
              expected_scope: str | tuple[str, ...] = PRE_APPROACH_SCOPE) -> dict:
    plan = json.loads(path.read_text(encoding="utf-8"))
    expected_scopes = ((expected_scope,) if isinstance(expected_scope, str)
                       else tuple(expected_scope))
    legacy_approach_only = (
        isinstance(expected_scope, str) and
        expected_scope == LEGACY_APPROACH_ONLY_SCOPE and
        plan.get("scope") == LEGACY_APPROACH_ONLY_SCOPE
    )
    required = {
        "schema_version", "scope", "source_frame_sha256", "c_robot_xy_mm",
        "target_robot_xyz_mm", "target_arm_deg", "ik_position_residual_mm",
        "urdf_sha256", "follower_port", "follower_serial_short",
        "maximum_joint_step_deg", "holds_fresh_gripper_position",
        "orientation_solved", "collision_checked", "motion_authorized",
    }
    if not required.issubset(plan):
        raise ValueError("approach_plan_fields_missing")
    if (plan["schema_version"] != 1 or plan["scope"] not in expected_scopes or
            (plan["scope"] not in SCOPE_CONTRACTS and not legacy_approach_only) or
            plan["urdf_sha256"] != EXPECTED_URDF_SHA256 or
            plan["follower_port"] != "/dev/ttyACM1" or
            plan["follower_serial_short"] != EXPECTED_SERIAL or
            plan["holds_fresh_gripper_position"] is not True or
            plan["motion_authorized"] is not False or
            set(plan["target_arm_deg"]) != set(ARM_NAMES)):
        raise ValueError("approach_plan_contract_mismatch")
    numeric = [*plan["c_robot_xy_mm"], *plan["target_robot_xyz_mm"],
               *plan["target_arm_deg"].values(), plan["ik_position_residual_mm"],
               plan["maximum_joint_step_deg"]]
    if any(not isinstance(value, (int, float)) or not math.isfinite(value)
           for value in numeric):
        raise ValueError("approach_plan_nonfinite")
    if (len(plan["c_robot_xy_mm"]) != 2 or len(plan["target_robot_xyz_mm"]) != 3 or
            not 0 < plan["maximum_joint_step_deg"] <= 2.0 or
            plan["ik_position_residual_mm"] > 1.0):
        raise ValueError("approach_plan_geometry_invalid")
    refine_last = plan.get("refine_last_waypoints", 0)
    refinement_factor = plan.get("final_refinement_factor", 1)
    final_timeout_s = plan.get("final_waypoint_timeout_s", 3.0)
    if (type(refine_last) is not int or not 0 <= refine_last <= 5 or
            type(refinement_factor) is not int or not 1 <= refinement_factor <= 4 or
            not isinstance(final_timeout_s, (int, float)) or
            not math.isfinite(final_timeout_s) or not 3.0 <= final_timeout_s <= 10.0):
        raise ValueError("approach_convergence_policy_invalid")
    plan["refine_last_waypoints"] = refine_last
    plan["final_refinement_factor"] = refinement_factor
    plan["final_waypoint_timeout_s"] = float(final_timeout_s)
    execution_mode = plan.get("execution_mode", "stop_and_wait")
    if execution_mode not in {"stop_and_wait", "bounded_continuous_following"}:
        raise ValueError("approach_execution_mode_invalid")
    plan["execution_mode"] = execution_mode
    if execution_mode == "bounded_continuous_following":
        limits = plan.get("following_error_limits_deg")
        expected_limits = {name: (4.0 if name == "elbow_flex" else 2.5)
                           for name in ARM_NAMES}
        cadence_s = plan.get("following_cadence_s")
        no_progress_s = plan.get("following_no_progress_timeout_s")
        progress_epsilon = plan.get("following_progress_epsilon_deg")
        if (plan["maximum_joint_step_deg"] > 1.0 or
                limits != expected_limits or
                not isinstance(cadence_s, (int, float)) or
                not math.isfinite(cadence_s) or not 0.15 <= cadence_s <= 0.3 or
                not isinstance(no_progress_s, (int, float)) or
                not math.isfinite(no_progress_s) or no_progress_s <= cadence_s or
                not isinstance(progress_epsilon, (int, float)) or
                not math.isfinite(progress_epsilon) or not 0 < progress_epsilon <= 0.25):
            raise ValueError("continuous_following_plan_invalid")
        plan["following_cadence_s"] = float(cadence_s)
        plan["following_no_progress_timeout_s"] = float(no_progress_s)
        plan["following_progress_epsilon_deg"] = float(progress_epsilon)
    for name, value in plan["target_arm_deg"].items():
        lower, upper = ARM_LIMITS_DEG[name]
        if not lower <= value <= upper:
            raise ValueError("approach_target_outside_installed_urdf")
    intermediates = plan.get("staged_intermediate_arm_deg", [])
    reference_start = plan.get("staged_reference_start_arm_deg")
    if intermediates or reference_start is not None:
        if (not isinstance(intermediates, list) or not 1 <= len(intermediates) <= 6 or
                not isinstance(reference_start, dict) or
                set(reference_start) != set(ARM_NAMES)):
            raise ValueError("staged_approach_contract_invalid")
        for stage in [reference_start, *intermediates]:
            if (not isinstance(stage, dict) or set(stage) != set(ARM_NAMES) or
                    any(not isinstance(value, (int, float)) or not math.isfinite(value)
                        for value in stage.values())):
                raise ValueError("staged_approach_joint_shape_invalid")
            for name, value in stage.items():
                lower, upper = ARM_LIMITS_DEG[name]
                if not lower <= value <= upper:
                    raise ValueError("staged_approach_joint_outside_installed_urdf")
    plan["staged_intermediate_arm_deg"] = intermediates
    plan["staged_reference_start_arm_deg"] = reference_start
    phase_fields = {
        "wrist_lead_phase", "wrist_lead_phase_waypoints",
        "wrist_lead_phase_target_arm_deg", "wrist_lead_phase_gate",
    }
    if legacy_approach_only:
        if (intermediates or reference_start is not None or
                plan.get("start_pose_name") is not None or
                phase_fields.intersection(plan)):
            raise ValueError("legacy_approach_only_contract_invalid")
        return plan
    run_phrase = plan.get("run_phrase", "RUN LIVE C APPROACH")
    start_pose_name = plan.get("start_pose_name")
    start_pose_tolerance = plan.get("start_pose_tolerance_deg", 1.0)
    per_axis_start_tolerance = isinstance(start_pose_tolerance, dict)
    if per_axis_start_tolerance:
        if (set(start_pose_tolerance) != set(ARM_NAMES) or
                any(not isinstance(value, (int, float)) or
                    not math.isfinite(value) or not 0 < value <= 1.5
                    for value in start_pose_tolerance.values())):
            raise ValueError("approach_start_contract_invalid")
        start_pose_tolerance = {
            name: float(start_pose_tolerance[name]) for name in ARM_NAMES
        }
    elif (not isinstance(start_pose_tolerance, (int, float)) or
          not math.isfinite(start_pose_tolerance) or
          not 0 < start_pose_tolerance <= 1.0):
        raise ValueError("approach_start_contract_invalid")
    else:
        start_pose_tolerance = float(start_pose_tolerance)
    scope_contract = SCOPE_CONTRACTS[plan["scope"]]
    if (run_phrase not in RUN_PHRASES or
            start_pose_name not in scope_contract["start_pose_names"] or
            START_POSE_RUN_PHRASES.get(start_pose_name) != run_phrase or
            (start_pose_name is not None and reference_start is None) or
            (start_pose_name == "PICK_READY" and
             not per_axis_start_tolerance) or
            (start_pose_name == CURRENT_TO_C_START_POSE and
             start_pose_tolerance != STRICT_POSE_TOLERANCES_DEG) or
            (plan["scope"] == RETURN_TO_PICK_READY_SCOPE and
             (plan.get("target_pose_name") != "PICK_READY" or
              not per_axis_start_tolerance))):
        raise ValueError("approach_start_contract_invalid")
    present_phase_fields = phase_fields.intersection(plan)
    if start_pose_name == CURRENT_TO_C_START_POSE:
        phase_target = plan.get("wrist_lead_phase_target_arm_deg")
        gate_policy = plan.get("wrist_lead_phase_gate")
        tcp_offset = plan.get("tcp_offset_gripper_mm")
        if (present_phase_fields != phase_fields or
                plan.get("wrist_lead_phase") != WRIST_LEAD_PHASE_NAME or
                type(plan.get("wrist_lead_phase_waypoints")) is not int or
                plan["wrist_lead_phase_waypoints"] != WRIST_LEAD_PHASE_WAYPOINTS or
                not isinstance(phase_target, dict) or
                set(phase_target) != set(ARM_NAMES) or
                any(not isinstance(value, (int, float)) or not math.isfinite(value)
                    for value in phase_target.values()) or
                len(intermediates) != 1 or phase_target != intermediates[0] or
                not isinstance(gate_policy, dict) or
                gate_policy != WRIST_LEAD_PHASE_GATE_POLICY or
                any(type(gate_policy[key]) is not type(expected)
                    for key, expected in WRIST_LEAD_PHASE_GATE_POLICY.items()) or
                not isinstance(tcp_offset, list) or len(tcp_offset) != 3 or
                any(not isinstance(value, (int, float)) or not math.isfinite(value)
                    for value in tcp_offset) or
                not isinstance(plan.get("minimum_fresh_gripper_open_percent"),
                               (int, float)) or
                not math.isclose(plan["minimum_fresh_gripper_open_percent"], 35.0,
                                 rel_tol=0.0, abs_tol=1e-12) or
                execution_mode != "bounded_continuous_following" or
                not math.isclose(plan["maximum_joint_step_deg"], 1.0,
                                 rel_tol=0.0, abs_tol=1e-12)):
            raise ValueError("wrist_lead_phase_contract_invalid")
        phase_delta = {
            name: float(phase_target[name]) - float(reference_start[name])
            for name in ARM_NAMES
        }
        if (not math.isclose(phase_delta["wrist_flex"], -2.0,
                             rel_tol=0.0, abs_tol=1e-9) or
                any(not math.isclose(phase_delta[name], 0.0,
                                     rel_tol=0.0, abs_tol=1e-9)
                    for name in ARM_NAMES if name != "wrist_flex")):
            raise ValueError("wrist_lead_phase_geometry_invalid")
    elif present_phase_fields:
        raise ValueError("wrist_lead_phase_scope_invalid")
    plan["run_phrase"] = run_phrase
    plan["start_pose_name"] = start_pose_name
    plan["start_pose_tolerance_deg"] = start_pose_tolerance
    return plan


def interpolate_goals(start: dict[str, float], target_arm: dict[str, float],
                      max_step_deg: float, *, refine_last_waypoints: int = 0,
                      final_refinement_factor: int = 1) -> list[dict[str, float]]:
    if set(start) != set(JOINT_UNITS) or set(target_arm) != set(ARM_NAMES):
        raise ValueError("interpolation_joint_shape_mismatch")
    if (not math.isfinite(max_step_deg) or not 0 < max_step_deg <= 2.0 or
            type(refine_last_waypoints) is not int or refine_last_waypoints < 0 or
            type(final_refinement_factor) is not int or final_refinement_factor < 1 or
            any(not isinstance(value, (int, float)) or not math.isfinite(value)
                for value in [*start.values(), *target_arm.values()])):
        raise ValueError("interpolation_input_invalid")
    largest = max(abs(target_arm[name] - start[name]) for name in ARM_NAMES)
    steps = max(1, math.ceil(largest / max_step_deg))
    base_goals = []
    for index in range(1, steps + 1):
        fraction = index / steps
        goal = {
            name: start[name] + (target_arm[name] - start[name]) * fraction
            for name in ARM_NAMES
        }
        goal["gripper"] = start["gripper"]
        base_goals.append(goal)
    if refine_last_waypoints == 0 or final_refinement_factor == 1:
        return base_goals

    # Subdivide only the tail of the already validated linear route. This adds
    # smaller final elbow steps without changing the joint-space line or target.
    refined = []
    segment_start = dict(start)
    first_refined = max(0, len(base_goals) - refine_last_waypoints)
    for index, segment_end in enumerate(base_goals):
        factor = final_refinement_factor if index >= first_refined else 1
        for part in range(1, factor + 1):
            fraction = part / factor
            goal = {
                name: segment_start[name] +
                      (segment_end[name] - segment_start[name]) * fraction
                for name in ARM_NAMES
            }
            goal["gripper"] = start["gripper"]
            refined.append(goal)
        segment_start = segment_end
    return refined


def interpolate_staged_goals(
    start: dict[str, float],
    intermediate_arm: list[dict[str, float]],
    target_arm: dict[str, float],
    max_step_deg: float,
    *,
    refine_last_waypoints: int = 0,
    final_refinement_factor: int = 1,
) -> list[dict[str, float]]:
    """Concatenate bounded linear stages while preserving one final endpoint."""
    previous = dict(start)
    goals = []
    targets = [*intermediate_arm, target_arm]
    for index, target in enumerate(targets):
        final_segment = index == len(targets) - 1
        segment = interpolate_goals(
            previous, target, max_step_deg,
            refine_last_waypoints=(refine_last_waypoints if final_segment else 0),
            final_refinement_factor=(final_refinement_factor if final_segment else 1),
        )
        goals.extend(segment)
        previous = dict(segment[-1])
    return goals


def validate_staged_reference_start(
    fresh: dict[str, float], reference_arm: dict[str, float] | None,
    *, tolerance_deg: float | dict[str, float] = 1.0,
) -> None:
    if reference_arm is None:
        return
    if set(fresh) != set(JOINT_UNITS) or set(reference_arm) != set(ARM_NAMES):
        raise ValueError("staged_reference_start_shape_invalid")
    if isinstance(tolerance_deg, dict):
        if set(tolerance_deg) != set(ARM_NAMES):
            raise ValueError("staged_reference_start_tolerance_shape_invalid")
        tolerances = tolerance_deg
    else:
        tolerances = {name: tolerance_deg for name in ARM_NAMES}
    errors = {name: fresh[name] - reference_arm[name] for name in ARM_NAMES}
    if any(abs(errors[name]) > tolerances[name] for name in ARM_NAMES):
        detail = ",".join(f"{name}={value:+.3f}" for name, value in errors.items())
        raise RuntimeError(f"staged_reference_start_mismatch:{detail}")


def verify_final_feedback(transport, goal: dict[str, float],
                          tolerances: dict[str, float], *,
                          max_age_s: float) -> tuple[dict[str, float], dict[str, float]]:
    feedback = transport.read_feedback()
    now = time.monotonic()
    if (feedback is None or set(feedback.positions) != set(goal) or
            not feedback.received_monotonic <= now or
            now - feedback.received_monotonic > max_age_s or
            any(not math.isfinite(feedback.positions[name]) for name in goal)):
        raise RuntimeError("final_fresh_feedback_invalid")
    positions = dict(feedback.positions)
    errors = {name: positions[name] - goal[name] for name in goal}
    if any(abs(errors[name]) > tolerances[name] for name in goal):
        detail = ",".join(f"{name}={error:+.3f}" for name, error in errors.items())
        raise RuntimeError(f"final_fresh_feedback_outside_tolerance:{detail}")
    return positions, errors


def final_tolerances_for_plan(plan: dict) -> dict[str, float]:
    """Return strict terminal contracts without changing historical scopes.

    The return scope ends at the canonical PICK_READY pose, so it must use the
    same per-axis pose tolerances as the recorded PICK_READY gate.  The short
    attempt-2-current route also uses its exact per-axis start contract at the
    C PRE_APPROACH endpoint.  Other historical scopes retain their existing
    terminal policy.
    """
    if plan["scope"] == RETURN_TO_PICK_READY_SCOPE:
        arm_tolerances = plan["start_pose_tolerance_deg"]
        if not isinstance(arm_tolerances, dict):
            raise ValueError("pick_ready_return_final_tolerance_invalid")
        return {**arm_tolerances, "gripper": 2.0}
    if (plan["scope"] == PRE_APPROACH_SCOPE and
            plan["start_pose_name"] == CURRENT_TO_C_START_POSE):
        arm_tolerances = plan["start_pose_tolerance_deg"]
        if arm_tolerances != STRICT_POSE_TOLERANCES_DEG:
            raise ValueError("current_to_c_final_tolerance_invalid")
        return {**arm_tolerances, "gripper": 2.0}
    return {name: (2.0 if name == "gripper" else 1.6)
            for name in JOINT_UNITS}


def load_verified_fk_kinematics(path: Path | None, expected_sha256: str):
    """Load the existing offline URDF model without touching robot hardware."""
    if path is None:
        raise ValueError("wrist_lead_fk_urdf_required")
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected_sha256:
        raise ValueError("wrist_lead_fk_urdf_sha256_mismatch")
    if __package__:
        from scripts.urdf_forward_kinematics import UrdfKinematics
    else:
        from urdf_forward_kinematics import UrdfKinematics
    return UrdfKinematics.from_file(path)


def grasp_tcp_xyz_mm(kinematics, joints: dict[str, float],
                     offset_mm: list[float]) -> tuple[float, float, float]:
    """Evaluate the configured GRASP opening-center TCP from follower joints."""
    import numpy as np

    urdf_names = ("Rotation", "Pitch", "Elbow", "Wrist_Pitch", "Wrist_Roll")
    q_rad = np.deg2rad([joints[name] for name in ARM_NAMES])
    transform = kinematics.forward(
        dict(zip(urdf_names, q_rad)), "base", "gripper")
    xyz = (transform[:3, 3] * 1000.0 +
           transform[:3, :3] @ np.asarray(offset_mm, dtype=float))
    return tuple(float(value) for value in xyz)


def wrist_lead_phase_goals(
    fresh_start: dict[str, float], plan: dict,
) -> list[dict[str, float]]:
    """Build exactly two fresh-relative Wrist Flex -1 degree commands."""
    if (plan["start_pose_name"] != CURRENT_TO_C_START_POSE or
            set(fresh_start) != set(JOINT_UNITS)):
        raise ValueError("wrist_lead_phase_start_invalid")
    goals = []
    for step in range(1, WRIST_LEAD_PHASE_WAYPOINTS + 1):
        goal = dict(fresh_start)
        goal["wrist_flex"] = fresh_start["wrist_flex"] - float(step)
        goals.append(goal)
    for previous, goal in zip([fresh_start, *goals[:-1]], goals):
        deltas = {name: goal[name] - previous[name] for name in JOINT_UNITS}
        if (not math.isclose(deltas["wrist_flex"], -1.0,
                             rel_tol=0.0, abs_tol=1e-12) or
                any(not math.isclose(deltas[name], 0.0,
                                     rel_tol=0.0, abs_tol=1e-12)
                    for name in JOINT_UNITS if name != "wrist_flex")):
            raise RuntimeError("wrist_lead_phase_step_invalid")
    return goals


def verify_wrist_lead_phase_gate(
    telemetry: FollowingTelemetry,
    *,
    fresh_start: dict[str, float],
    phase_target: dict[str, float],
    gate_policy: dict,
    kinematics,
    tcp_offset_mm: list[float],
) -> dict:
    """Fail closed before any coupled target after the Wrist-only phase."""
    now = time.monotonic()
    mappings = (
        telemetry.positions, telemetry.goal_raw, telemetry.present_raw,
        telemetry.moving, telemetry.present_load,
    ) if isinstance(telemetry, FollowingTelemetry) else ()
    if (not isinstance(telemetry, FollowingTelemetry) or
            gate_policy != WRIST_LEAD_PHASE_GATE_POLICY or
            any(set(mapping) != set(JOINT_UNITS) for mapping in mappings) or
            not isinstance(telemetry.temperature_c, dict) or
            set(telemetry.temperature_c) != set(JOINT_UNITS) or
            not telemetry.received_monotonic <= now or
            now - telemetry.received_monotonic > gate_policy["feedback_max_age_s"] or
            any(not math.isfinite(float(telemetry.positions[name]))
                for name in JOINT_UNITS) or
            any(type(telemetry.temperature_c[name]) is not int
                for name in JOINT_UNITS)):
        raise RuntimeError("wrist_lead_phase_feedback_invalid_or_stale")
    if any(telemetry.temperature_c[name] > gate_policy["maximum_temperature_c"]
           for name in JOINT_UNITS):
        raise RuntimeError("wrist_lead_phase_temperature_limit_exceeded")
    if any(telemetry.moving[name] != 0 for name in JOINT_UNITS):
        raise RuntimeError("wrist_lead_phase_not_settled")

    commanded = gate_policy["commanded_joint"]
    commanded_delta = phase_target[commanded] - fresh_start[commanded]
    achieved_delta = telemetry.positions[commanded] - fresh_start[commanded]
    if (commanded_delta == 0.0 or achieved_delta * commanded_delta <= 0.0 or
            abs(telemetry.positions[commanded] - phase_target[commanded]) >
            gate_policy["target_tolerance_deg"]):
        raise RuntimeError("wrist_lead_phase_direction_or_target_failed")
    drift = {
        name: telemetry.positions[name] - fresh_start[name]
        for name in JOINT_UNITS if name != commanded
    }
    if any(abs(value) > gate_policy["non_commanded_drift_limit_deg"]
           for value in drift.values()):
        raise RuntimeError("wrist_lead_phase_non_commanded_drift_exceeded")

    tcp_before = grasp_tcp_xyz_mm(kinematics, fresh_start, tcp_offset_mm)
    tcp_after = grasp_tcp_xyz_mm(
        kinematics, dict(telemetry.positions), tcp_offset_mm)
    if not tcp_after[2] > tcp_before[2]:
        raise RuntimeError("wrist_lead_phase_tcp_z_not_increased")
    return {
        "phase": WRIST_LEAD_PHASE_NAME,
        "present": dict(telemetry.positions),
        "goal_raw": dict(telemetry.goal_raw),
        "present_raw": dict(telemetry.present_raw),
        "moving": dict(telemetry.moving),
        "present_load_diagnostic": dict(telemetry.present_load),
        "temperature_c": dict(telemetry.temperature_c),
        "commanded_delta_deg": commanded_delta,
        "achieved_delta_deg": achieved_delta,
        "non_commanded_drift": drift,
        "grasp_tcp_before_mm": tcp_before,
        "grasp_tcp_after_mm": tcp_after,
        "grasp_tcp_delta_z_mm": tcp_after[2] - tcp_before[2],
        "pass": True,
    }


def persist_elbow_diagnostic(transport, output_path: Path | None) -> dict | None:
    if output_path is None:
        return None
    report = transport.elbow_diagnostic_report()
    if report is None:
        return None
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def run(plan_path: Path, *, live: bool, confirm_scope: str | None,
        elbow_diagnostic_output: Path | None = None,
        following_log_output: Path | None = None,
        fk_urdf_path: Path | None = None,
        input_fn=input, transport_factory=None) -> int:
    plan = load_plan(plan_path, expected_scope=tuple(SCOPE_CONTRACTS))
    scope_contract = SCOPE_CONTRACTS[plan["scope"]]
    final_tolerances = final_tolerances_for_plan(plan)
    wrist_lead_enabled = plan["start_pose_name"] == CURRENT_TO_C_START_POSE
    kinematics = None
    if live and wrist_lead_enabled:
        kinematics = load_verified_fk_kinematics(
            fk_urdf_path, plan["urdf_sha256"])
    print(json.dumps({
        "scope": plan["scope"],
        "source_frame_sha256": plan["source_frame_sha256"],
        "target_robot_xyz_mm": plan["target_robot_xyz_mm"],
        "target_arm_deg": plan["target_arm_deg"],
        "orientation_solved": plan["orientation_solved"],
        "collision_checked": plan["collision_checked"],
        "start_pose_name": plan["start_pose_name"],
        "start_pose_tolerance_deg": plan["start_pose_tolerance_deg"],
        "run_phrase": plan["run_phrase"],
        "refine_last_waypoints": plan["refine_last_waypoints"],
        "final_refinement_factor": plan["final_refinement_factor"],
        "final_waypoint_timeout_s": plan["final_waypoint_timeout_s"],
        "execution_mode": plan["execution_mode"],
        "following_cadence_s": plan.get("following_cadence_s"),
        "following_error_limits_deg": plan.get("following_error_limits_deg"),
        "staged_reference_start_arm_deg": plan["staged_reference_start_arm_deg"],
        "staged_intermediate_arm_deg": plan["staged_intermediate_arm_deg"],
        "final_tolerances": final_tolerances,
        "wrist_lead_phase": plan.get("wrist_lead_phase"),
        "wrist_lead_phase_waypoints": plan.get("wrist_lead_phase_waypoints"),
        "wrist_lead_phase_gate": plan.get("wrist_lead_phase_gate"),
        "fk_urdf": str(fk_urdf_path) if fk_urdf_path is not None else None,
        "following_log_output": (str(following_log_output)
                                 if following_log_output is not None else None),
        "elbow_diagnostic_output": (str(elbow_diagnostic_output)
                                    if elbow_diagnostic_output is not None else None),
        "dry_run": not live,
    }, separators=(",", ":")), flush=True)
    if not live:
        print("DRY_RUN: no port opened; no send_action", flush=True)
        return 0
    if confirm_scope != plan["scope"]:
        raise ValueError("live_scope_mismatch")
    if (plan["execution_mode"] == "bounded_continuous_following" and
            following_log_output is None):
        raise ValueError("continuous_following_log_required")
    if (following_log_output is not None and following_log_output.exists()):
        raise ValueError("continuous_following_log_already_exists")
    phrase = plan["run_phrase"]
    if input_fn(f"C unchanged, path clear, site stop ready. Type {phrase}: ") != phrase:
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
        if (wrist_lead_enabled and
                start["gripper"] < plan["minimum_fresh_gripper_open_percent"]):
            raise RuntimeError(
                "fresh_gripper_below_minimum_open:"
                f"present={start['gripper']:.6f},"
                f"minimum={plan['minimum_fresh_gripper_open_percent']:.6f}")
        verified_start = transport.verify_start_pose(
            start, {name: (2.0 if name == "gripper" else 1.0) for name in JOINT_UNITS})
        if (wrist_lead_enabled and
                (verified_start is None or
                 set(verified_start.positions) != set(JOINT_UNITS) or
                 verified_start.positions["gripper"] <
                 plan["minimum_fresh_gripper_open_percent"])):
            raise RuntimeError("verified_fresh_gripper_below_minimum_open")
        validate_staged_reference_start(
            start, plan["staged_reference_start_arm_deg"],
            tolerance_deg=plan["start_pose_tolerance_deg"])
        if plan["start_pose_name"] is not None:
            print(f"START_POSE_CONFIRMED={plan['start_pose_name']}", flush=True)
        if wrist_lead_enabled:
            phase_goals = wrist_lead_phase_goals(start, plan)
            nominal_coupled_goals = interpolate_staged_goals(
                phase_goals[-1], plan["staged_intermediate_arm_deg"][1:],
                plan["target_arm_deg"], plan["maximum_joint_step_deg"],
                refine_last_waypoints=plan["refine_last_waypoints"],
                final_refinement_factor=plan["final_refinement_factor"])
            goals = phase_goals
            total_waypoints = len(phase_goals) + len(nominal_coupled_goals)
        else:
            goals = interpolate_staged_goals(
                start, plan["staged_intermediate_arm_deg"], plan["target_arm_deg"],
                plan["maximum_joint_step_deg"],
                refine_last_waypoints=plan["refine_last_waypoints"],
                final_refinement_factor=plan["final_refinement_factor"])
            total_waypoints = len(goals)
        if (elbow_diagnostic_output is not None and
                plan["execution_mode"] == "stop_and_wait"):
            transport.configure_elbow_diagnostic(
                total_waypoints=len(goals), tail_waypoints=min(10, len(goals)))
        print(json.dumps({"fresh_start": start, "waypoints": total_waypoints,
                          "wrist_lead_phase_waypoints": (
                              len(phase_goals) if wrist_lead_enabled else 0),
                          "gripper_hold": start["gripper"]},
                         separators=(",", ":")), flush=True)
        tolerances = final_tolerances
        if plan["execution_mode"] == "bounded_continuous_following":
            assert following_log_output is not None
            following_log_output.parent.mkdir(parents=True, exist_ok=True)

            def make_log_sink(execution_phase: str | None):
                def write_following_row(row: dict) -> None:
                    payload = ({**row, "execution_phase": execution_phase}
                               if execution_phase is not None else row)
                    with following_log_output.open("a", encoding="utf-8") as stream:
                        stream.write(json.dumps(
                            payload, separators=(",", ":")) + "\n")
                        stream.flush()
                return write_following_row

            def make_following_controller(
                planned_start: dict[str, float],
                terminal_tolerances: dict[str, float],
                execution_phase: str | None,
            ):
                return ContinuousFollowingCycle(
                    transport, terminal_tolerances,
                    planned_start=planned_start,
                    following_limits=plan["following_error_limits_deg"],
                    max_joint_step_deg=plan["maximum_joint_step_deg"],
                    cadence_s=plan["following_cadence_s"],
                    no_progress_timeout_s=plan["following_no_progress_timeout_s"],
                    progress_epsilon_deg=plan["following_progress_epsilon_deg"],
                    final_timeout_s=plan["final_waypoint_timeout_s"],
                    feedback_max_age_s=0.5, stable_s=0.1, poll_s=0.05,
                    log_sink=make_log_sink(execution_phase))

            def wait_for_controller(active_controller, expected_waypoints: int) -> None:
                wait_timeout_s = (
                    expected_waypoints *
                    (plan["following_cadence_s"] +
                     plan["following_no_progress_timeout_s"]) +
                    plan["final_waypoint_timeout_s"] + 10.0)
                if not active_controller.wait_worker(wait_timeout_s):
                    raise RuntimeError("approach_worker_timeout")
                if (active_controller.reach_state != "GOAL_REACHED" or
                        active_controller.task_state !=
                        "USER_CONFIRMATION_REQUIRED" or
                        active_controller.waypoints_reached != expected_waypoints):
                    raise RuntimeError(
                        f"approach_failed:{active_controller.failure}")

            if wrist_lead_enabled:
                assert kinematics is not None
                phase_tolerances = {name: 1.0 for name in JOINT_UNITS}
                phase_tolerances["wrist_flex"] = (
                    plan["wrist_lead_phase_gate"]["target_tolerance_deg"])
                controller = make_following_controller(
                    start, phase_tolerances, WRIST_LEAD_PHASE_NAME)
                pre_send_telemetry = controller._read_telemetry()
                if (pre_send_telemetry.positions["gripper"] <
                        plan["minimum_fresh_gripper_open_percent"]):
                    raise RuntimeError("pre_send_gripper_below_minimum_open")
                controller.start_stage(
                    scope_contract["stage"], phase_goals, approved=True)
                wait_for_controller(controller, len(phase_goals))
                phase_telemetry = controller._read_telemetry()
                try:
                    phase_report = verify_wrist_lead_phase_gate(
                        phase_telemetry,
                        fresh_start=start,
                        phase_target=phase_goals[-1],
                        gate_policy=plan["wrist_lead_phase_gate"],
                        kinematics=kinematics,
                        tcp_offset_mm=plan["tcp_offset_gripper_mm"],
                    )
                except Exception as error:
                    controller._abort(
                        reason=("wrist_lead_phase_gate_failed:"
                                f"{type(error).__name__}:{error}"),
                        waypoint_index=len(phase_goals),
                        goal=phase_goals[-1], telemetry=phase_telemetry)
                    raise
                controller._emit(
                    action="RESUME", waypoint_index=len(phase_goals),
                    goal=phase_goals[-1], telemetry=phase_telemetry,
                    detail="wrist_lead_phase_gate_pass")
                print(json.dumps(
                    {"wrist_lead_phase_gate": phase_report},
                    separators=(",", ":")), flush=True)
                print("WRIST_LEAD_PHASE_GATE_PASS", flush=True)

                coupled_start = dict(phase_telemetry.positions)
                coupled_start["gripper"] = start["gripper"]
                coupled_goals = interpolate_staged_goals(
                    coupled_start, plan["staged_intermediate_arm_deg"][1:],
                    plan["target_arm_deg"], plan["maximum_joint_step_deg"],
                    refine_last_waypoints=plan["refine_last_waypoints"],
                    final_refinement_factor=plan["final_refinement_factor"])
                if not coupled_goals:
                    raise RuntimeError("wrist_lead_coupled_path_empty")
                total_waypoints = len(phase_goals) + len(coupled_goals)
                controller = make_following_controller(
                    coupled_start, tolerances, "COUPLED_FINISH")
                controller.start_stage(
                    scope_contract["stage"], coupled_goals, approved=True)
                wait_for_controller(controller, len(coupled_goals))
                goals = coupled_goals
                expected_controller_waypoints = len(coupled_goals)
            else:
                controller = make_following_controller(start, tolerances, None)
                controller.start_stage(scope_contract["stage"], goals, approved=True)
                wait_for_controller(controller, len(goals))
                expected_controller_waypoints = len(goals)
        else:
            controller = StagedCycle(
                transport, tolerances, timeout_s=3.0,
                final_timeout_s=plan["final_waypoint_timeout_s"],
                feedback_max_age_s=0.5, stable_s=0.1, poll_s=0.02)
            controller.start_stage(scope_contract["stage"], goals, approved=True)
            wait_timeout_s = (len(goals) * 3.0 +
                              max(0.0, plan["final_waypoint_timeout_s"] - 3.0) + 10.0)
            if not controller.wait_worker(wait_timeout_s):
                raise RuntimeError("approach_worker_timeout")
            expected_controller_waypoints = len(goals)
        if (elbow_diagnostic_output is not None and
                plan["execution_mode"] == "stop_and_wait"):
            transport.collect_final_elbow_settle(duration_s=3.0, interval_s=0.15)
            report = persist_elbow_diagnostic(transport, elbow_diagnostic_output)
            for row in report["samples"] if report is not None else []:
                print(json.dumps({"elbow_diagnostic": row}, separators=(",", ":")),
                      flush=True)
            print(f"ELBOW_DIAGNOSTIC_SAVED={elbow_diagnostic_output}", flush=True)
        if (controller.reach_state != "GOAL_REACHED" or
                controller.task_state != "USER_CONFIRMATION_REQUIRED" or
                controller.waypoints_reached != expected_controller_waypoints):
            raise RuntimeError(f"approach_failed:{controller.failure}")
        final_positions, final_errors = verify_final_feedback(
            transport, goals[-1], tolerances, max_age_s=0.5)
        print(json.dumps({
            "final_fresh_feedback": final_positions,
            "final_error_deg_or_pp": final_errors,
            "within_tolerance": True,
        }, separators=(",", ":")), flush=True)
        print(f"{scope_contract['reached_marker']} waypoints={total_waypoints}",
              flush=True)
        if (input_fn(scope_contract["completion_prompt"]) !=
                scope_contract["completion_phrase"]):
            raise RuntimeError("approach_site_result_not_confirmed")
        controller.confirm_task_result(
            stage=scope_contract["stage"], human_observed=True, result=True)
        print(scope_contract["pass_marker"], flush=True)
        outcome = 0
    except (KeyboardInterrupt, Exception) as error:
        print(f"ABORT: {type(error).__name__}: {error}", file=sys.stderr, flush=True)
    finally:
        try:
            persist_elbow_diagnostic(transport, elbow_diagnostic_output)
        except Exception as error:
            outcome = 1
            print(f"elbow_diagnostic_save_failed:{type(error).__name__}:{error}",
                  file=sys.stderr, flush=True)
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
                    transport.close_after_site_confirmation(controller, object_supported=True)
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
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--live", action="store_true")
    mode.add_argument(
        "--dry-run", action="store_true",
        help="explicitly keep the follower port closed and send no target",
    )
    parser.add_argument("--confirm-scope", choices=tuple(SCOPE_CONTRACTS))
    parser.add_argument("--elbow-diagnostic-output", type=Path)
    parser.add_argument("--following-log-output", type=Path)
    parser.add_argument("--fk-urdf", type=Path)
    args = parser.parse_args(argv)
    try:
        return run(args.plan, live=args.live, confirm_scope=args.confirm_scope,
                   elbow_diagnostic_output=args.elbow_diagnostic_output,
                   following_log_output=args.following_log_output,
                   fk_urdf_path=args.fk_urdf)
    except (OSError, ValueError) as error:
        parser.exit(2, f"APPROACH_NOT_STARTED: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
