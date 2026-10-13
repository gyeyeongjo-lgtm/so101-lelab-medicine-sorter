#!/usr/bin/env python3
"""Offline load-aware HOME→C PRE_APPROACH candidate comparison.

The planner reuses the production runner's bounded staged interpolation but
never opens a robot port.  Lift moves alone first.  Pan/Lift/Elbow/Roll and
Wrist Flex then move together, so Wrist motion begins only after the explicit
Lift-relief stage.  Candidate Lift anchors come from the previously executed
LIFT_NEG50 trace; the known raw deadband evidence rejects an ineffective
sub-threshold relief.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

if __package__:
    from scripts.live_c_approach import ARM_NAMES, interpolate_staged_goals
    from scripts.plan_pick_grasp_tcp_ik import (
        _path_report, _transform, axis_error_deg, rotation_error_deg,
        tcp_position_mm,
    )
    from scripts.urdf_forward_kinematics import UrdfKinematics
else:
    from live_c_approach import ARM_NAMES, interpolate_staged_goals
    from plan_pick_grasp_tcp_ik import (
        _path_report, _transform, axis_error_deg, rotation_error_deg,
        tcp_position_mm,
    )
    from urdf_forward_kinematics import UrdfKinematics


SERVO_POSITION_RESOLUTION_DEG = 360.0 / 4095.0
COUPLED_FRACTIONS = (0.25, 0.50, 0.75)


def _vector(value: object, length: int, label: str) -> np.ndarray:
    result = np.asarray(value, dtype=float)
    if result.shape != (length,) or not np.isfinite(result).all():
        raise ValueError(f"{label} must contain {length} finite values")
    return result


def _mapping(values: np.ndarray) -> dict[str, float]:
    return {
        name: round(float(value), 6)
        for name, value in zip(ARM_NAMES, values)
    }


def _candidate(
    *,
    kinematics: UrdfKinematics,
    start: np.ndarray,
    endpoint: np.ndarray,
    relief_lift_deg: float,
    grasp_offset: np.ndarray,
    bounds: np.ndarray,
    c_xy: np.ndarray,
    table_z_mm: float,
    maximum_step_deg: float,
    demonstrated_rotation: np.ndarray,
    minimum_effective_raw_delta: int,
) -> dict:
    relief = start.copy()
    relief[1] = relief_lift_deg
    stage_joints = [relief]
    stage_names = ["LIFT_RELIEF"]
    for fraction in COUPLED_FRACTIONS:
        # Wrist is deliberately held during LIFT_RELIEF, then participates in
        # the same bounded coupled transition as the other arm joints.
        stage_joints.append(relief + (endpoint - relief) * fraction)
        stage_names.append(
            "COUPLED_TRANSITION" if fraction == 0.25 else
            ("WRIST_COUPLED" if fraction == 0.50 else "WRIST_COUPLED_FINAL")
        )

    start_mapping = {**dict(zip(ARM_NAMES, start)), "gripper": 0.0}
    intermediate = [dict(zip(ARM_NAMES, values)) for values in stage_joints]
    goals = interpolate_staged_goals(
        start_mapping, intermediate, dict(zip(ARM_NAMES, endpoint)),
        maximum_step_deg,
    )
    samples = np.vstack([
        start,
        *[[goal[name] for name in ARM_NAMES] for goal in goals],
    ])
    report = _path_report(
        kinematics, samples, grasp_offset, bounds, table_z_mm)
    tcp_samples = np.asarray([
        tcp_position_mm(kinematics, q_deg, grasp_offset)
        for q_deg in samples
    ])
    xy_distance = np.linalg.norm(tcp_samples[:, :2] - c_xy, axis=1)
    expected_relief_raw_delta = int(round(
        abs(relief_lift_deg - start[1]) / SERVO_POSITION_RESOLUTION_DEG))
    effective_relief = expected_relief_raw_delta >= minimum_effective_raw_delta

    stages = []
    for stage_name, q_deg in zip(
            [*stage_names, "C_PRE_APPROACH"], [*stage_joints, endpoint]):
        xyz = tcp_position_mm(kinematics, q_deg, grasp_offset)
        rotation = _transform(kinematics, q_deg)[:3, :3]
        stages.append({
            "stage": stage_name,
            "joints_deg": _mapping(q_deg),
            "grasp_tcp_xyz_mm": [round(float(value), 6) for value in xyz],
            "c_xy_distance_mm": round(
                float(np.linalg.norm(xyz[:2] - c_xy)), 6),
            "full_orientation_error_deg": round(
                rotation_error_deg(rotation, demonstrated_rotation), 6),
            "tool_axis_error_deg": round(axis_error_deg(
                -rotation[:, 2], -demonstrated_rotation[:, 2]), 6),
            "jaw_axis_error_deg": round(axis_error_deg(
                rotation[:, 0], demonstrated_rotation[:, 0]), 6),
        })

    proxy_valid = all((
        report["maximum_joint_step_deg"] <= maximum_step_deg + 1e-9,
        report["minimum_tcp_table_proxy_margin_mm"] > 0.0,
        report["minimum_nonadjacent_centerline_distance_mm"] > 30.0,
        report["minimum_servo_margin_deg"] >= 0.0,
    ))
    return {
        "candidate": f"LIFT_NEG{str(abs(relief_lift_deg)).replace('.', 'P')}",
        "relief_lift_deg": relief_lift_deg,
        "lift_relief_delta_deg": round(float(relief_lift_deg - start[1]), 6),
        "expected_lift_relief_raw_delta": expected_relief_raw_delta,
        "minimum_effective_raw_delta_from_logs": minimum_effective_raw_delta,
        "effective_relief_evidence": effective_relief,
        "valid": bool(effective_relief and proxy_valid),
        "waypoint_count": len(goals),
        "maximum_joint_step_deg": report["maximum_joint_step_deg"],
        "joint_tcp_orientation_progression": stages,
        "start_c_xy_distance_mm": round(float(xy_distance[0]), 6),
        "maximum_c_xy_distance_mm": round(float(np.max(xy_distance)), 6),
        "final_c_xy_distance_mm": round(float(xy_distance[-1]), 9),
        "minimum_grasp_tcp_z_mm": report["minimum_grasp_tcp_z_mm"],
        "minimum_tcp_table_proxy_margin_mm":
            report["minimum_tcp_table_proxy_margin_mm"],
        "minimum_nonbase_link_origin_z_mm":
            report["minimum_nonbase_link_origin_z_mm"],
        "minimum_nonbase_link_origin_table_margin_mm": round(
            report["minimum_nonbase_link_origin_z_mm"] - table_z_mm, 6),
        "minimum_self_collision_centerline_margin_mm":
            report["minimum_nonadjacent_centerline_distance_mm"],
        "self_collision_proxy": report["self_collision_centerline_proxy"],
        "minimum_servo_margin_deg": report["minimum_servo_margin_deg"],
        "full_mesh_environment": "NOT_VERIFIED",
    }


def plan(document: dict, kinematics: UrdfKinematics) -> dict:
    start = _vector(document["home_joints_deg"], 5, "HOME joints")
    endpoint = _vector(document["pre_approach_joints_deg"], 5, "endpoint joints")
    grasp_offset = _vector(document["grasp_tcp_offset_gripper_mm"], 3, "GRASP TCP")
    c_xy = _vector(document["c_robot_xy_mm"], 2, "C robot XY")
    reference = _vector(
        document["demonstrated_c_grasp_joints_deg"], 5, "orientation reference")
    bounds = np.asarray(document["servo_bounds_deg"], dtype=float)
    relief_values = [float(value) for value in document["lift_relief_candidates_deg"]]
    maximum_step = float(document.get("maximum_joint_step_deg", 1.0))
    minimum_effective_raw = int(document["minimum_effective_raw_delta"])
    table_z = float(document["table_reference_z_mm"])
    numeric = [*bounds.flat, *relief_values, maximum_step, table_z]
    if (bounds.shape != (5, 2) or not all(math.isfinite(value) for value in numeric)
            or not relief_values or not 0 < maximum_step <= 1.0
            or minimum_effective_raw <= 0):
        raise ValueError("invalid HOME path request")

    demonstrated_rotation = _transform(kinematics, reference)[:3, :3]
    candidates = [
        _candidate(
            kinematics=kinematics, start=start, endpoint=endpoint,
            relief_lift_deg=value, grasp_offset=grasp_offset, bounds=bounds,
            c_xy=c_xy, table_z_mm=table_z,
            maximum_step_deg=maximum_step,
            demonstrated_rotation=demonstrated_rotation,
            minimum_effective_raw_delta=minimum_effective_raw,
        )
        for value in relief_values
    ]
    valid = [candidate for candidate in candidates if candidate["valid"]]
    if not valid:
        raise ValueError("no valid evidence-backed HOME path")
    selected = min(valid, key=lambda candidate: (
        abs(candidate["lift_relief_delta_deg"]),
        -candidate["minimum_tcp_table_proxy_margin_mm"],
        candidate["waypoint_count"],
    ))
    return {
        "status": "OFFLINE_DRY_RUN_ONLY",
        "canonical_start_pose": "HOME",
        "safe_high_role": "RECOVERY_FALLBACK_OPTIONAL_TRANSPORT_ONLY",
        "path_structure": [
            "HOME", "LIFT_RELIEF", "COUPLED_TRANSITION",
            "WRIST_COUPLED", "C_PRE_APPROACH",
        ],
        "load_evidence": document["load_evidence"],
        "candidates": candidates,
        "recommended_candidate": selected["candidate"],
        "recommended": selected,
        "selection_rule": (
            "smallest Lift-only change that exceeds the measured effective raw "
            "step and passes bounded FK/table/self-collision/servo proxies; "
            "Wrist starts only after Lift relief"
        ),
        "motor_commands_sent": 0,
        "follower_port_opened": False,
        "goal_or_torque_changed": False,
        "motion_authorized": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--urdf", required=True, type=Path)
    args = parser.parse_args()
    document = json.loads(args.request.read_text(encoding="utf-8"))
    print(json.dumps(plan(
        document, UrdfKinematics.from_file(args.urdf)), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
