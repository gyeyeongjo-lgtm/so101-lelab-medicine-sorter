#!/usr/bin/env python3
"""Offline PICK_READY→C PRE_APPROACH staged-path comparison.

The planner starts from the measured PICK_READY pose and keeps the existing
C PRE_APPROACH endpoint unchanged.  It explores relative Lift-relief amounts
and delayed-Wrist schedules; it does not reuse the HOME-specific absolute Lift
anchors or any failed HOME path.  The module has no robot transport dependency
and never opens a serial port or changes Goal/Torque registers.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np

if __package__:
    from scripts.live_c_approach import ARM_NAMES, interpolate_staged_goals
    from scripts.plan_pick_grasp_tcp_ik import (
        _path_report,
        _transform,
        axis_error_deg,
        rotation_error_deg,
        tcp_position_mm,
    )
    from scripts.urdf_forward_kinematics import UrdfKinematics
else:
    from live_c_approach import ARM_NAMES, interpolate_staged_goals
    from plan_pick_grasp_tcp_ik import (
        _path_report,
        _transform,
        axis_error_deg,
        rotation_error_deg,
        tcp_position_mm,
    )
    from urdf_forward_kinematics import UrdfKinematics


SERVO_POSITION_RESOLUTION_DEG = 360.0 / 4095.0


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


def _stage_schedule(
    start: np.ndarray,
    endpoint: np.ndarray,
    *,
    lift_relief_delta_deg: float,
    wrist_delay_fraction: float,
    coupled_fractions: np.ndarray,
) -> tuple[list[str], list[np.ndarray]]:
    relief = start.copy()
    relief[1] += lift_relief_delta_deg
    stages = [relief]
    names = ["LIFT_RELIEF"]

    fractions = sorted(set([
        *[float(value) for value in coupled_fractions],
        float(wrist_delay_fraction),
    ]))
    for progress in fractions:
        target = relief + (endpoint - relief) * progress
        wrist_progress = (
            0.0 if progress <= wrist_delay_fraction else
            (progress - wrist_delay_fraction) / (1.0 - wrist_delay_fraction)
        )
        target[3] = relief[3] + (endpoint[3] - relief[3]) * wrist_progress
        stages.append(target)
        phase = "WRIST_HOLD" if wrist_progress == 0.0 else "DELAYED_WRIST"
        names.append(f"COUPLED_{phase}_{int(round(progress * 100)):03d}")
    return names, stages


def _candidate(
    *,
    kinematics: UrdfKinematics,
    start: np.ndarray,
    endpoint: np.ndarray,
    lift_relief_delta_deg: float,
    wrist_delay_fraction: float,
    coupled_fractions: np.ndarray,
    grasp_offset: np.ndarray,
    bounds: np.ndarray,
    c_xy: np.ndarray,
    target_xyz: np.ndarray,
    table_z_mm: float,
    maximum_step_deg: float,
    demonstrated_rotation: np.ndarray,
    minimum_effective_raw_delta: int,
) -> dict:
    stage_names, stage_joints = _stage_schedule(
        start,
        endpoint,
        lift_relief_delta_deg=lift_relief_delta_deg,
        wrist_delay_fraction=wrist_delay_fraction,
        coupled_fractions=coupled_fractions,
    )
    start_mapping = {**dict(zip(ARM_NAMES, start)), "gripper": 0.0}
    intermediate = [dict(zip(ARM_NAMES, values)) for values in stage_joints]
    goals = interpolate_staged_goals(
        start_mapping,
        intermediate,
        dict(zip(ARM_NAMES, endpoint)),
        maximum_step_deg,
    )
    samples = np.vstack([
        start,
        *[[goal[name] for name in ARM_NAMES] for goal in goals],
    ])
    tcp_samples = np.asarray([
        tcp_position_mm(kinematics, q_deg, grasp_offset)
        for q_deg in samples
    ])
    xy_distance = np.linalg.norm(tcp_samples[:, :2] - c_xy, axis=1)
    report = _path_report(
        kinematics, samples, grasp_offset, bounds, table_z_mm)
    expected_relief_raw_delta = int(round(
        abs(lift_relief_delta_deg) / SERVO_POSITION_RESOLUTION_DEG))
    effective_relief = expected_relief_raw_delta >= minimum_effective_raw_delta

    progression = []
    for stage_name, q_deg in zip(
            ["PICK_READY", *stage_names, "C_PRE_APPROACH"],
            [start, *stage_joints, endpoint]):
        xyz = tcp_position_mm(kinematics, q_deg, grasp_offset)
        rotation = _transform(kinematics, q_deg)[:3, :3]
        progression.append({
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

    final_error = float(np.linalg.norm(tcp_samples[-1] - target_xyz))
    route_l2 = float(sum(
        np.linalg.norm(target - source)
        for source, target in zip(
            [start, *stage_joints], [*stage_joints, endpoint])
    ))
    proxy_valid = all((
        effective_relief,
        report["maximum_joint_step_deg"] <= maximum_step_deg + 1e-9,
        report["minimum_tcp_table_proxy_margin_mm"] > 0.0,
        report["minimum_nonadjacent_centerline_distance_mm"] > 30.0,
        report["minimum_servo_margin_deg"] >= 0.0,
        final_error <= 1e-3,
    ))
    relief_label = str(lift_relief_delta_deg).replace(".", "P")
    label = (
        f"RELIEF_PLUS_{relief_label}_"
        f"WRIST_DELAY_{int(round(wrist_delay_fraction * 100)):02d}"
    )
    return {
        "candidate": label,
        "valid": bool(proxy_valid),
        "lift_relief_delta_deg": round(lift_relief_delta_deg, 6),
        "lift_relief_target_deg": round(float(start[1] + lift_relief_delta_deg), 6),
        "expected_lift_relief_raw_delta": expected_relief_raw_delta,
        "minimum_effective_raw_delta_from_logs": minimum_effective_raw_delta,
        "effective_relief_evidence": effective_relief,
        "wrist_delay_fraction": wrist_delay_fraction,
        "staged_intermediate_arm_deg": [_mapping(values) for values in stage_joints],
        "waypoint_count": len(goals),
        "maximum_joint_step_deg": report["maximum_joint_step_deg"],
        "joint_route_l2_deg": round(route_l2, 6),
        "tcp_orientation_progression": progression,
        "start_c_xy_distance_mm": round(float(xy_distance[0]), 6),
        "maximum_c_xy_distance_mm": round(float(np.max(xy_distance)), 6),
        "final_c_xy_distance_mm": round(float(xy_distance[-1]), 9),
        "final_grasp_tcp_target_error_mm": round(final_error, 9),
        "minimum_grasp_tcp_z_mm": report["minimum_grasp_tcp_z_mm"],
        "maximum_grasp_tcp_z_mm": round(float(np.max(tcp_samples[:, 2])), 6),
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
        "environment_collision_proxy": report["environment_collision_proxy"],
        "full_mesh_environment": "NOT_VERIFIED",
    }


def plan(document: dict, kinematics: UrdfKinematics, urdf_sha256: str) -> dict:
    if document.get("urdf_sha256") != urdf_sha256:
        raise ValueError("URDF SHA mismatch")
    start = _vector(document["pick_ready_joints_deg"], 5, "PICK_READY joints")
    endpoint = _vector(document["pre_approach_joints_deg"], 5, "endpoint joints")
    grasp_offset = _vector(document["grasp_tcp_offset_gripper_mm"], 3, "GRASP TCP")
    c_xy = _vector(document["c_robot_xy_mm"], 2, "C robot XY")
    target_xyz = _vector(document["target_robot_xyz_mm"], 3, "target XYZ")
    reference = _vector(
        document["demonstrated_c_grasp_joints_deg"], 5, "orientation reference")
    bounds = np.asarray(document["servo_bounds_deg"], dtype=float)
    relief_deltas = [float(value) for value in document["lift_relief_deltas_deg"]]
    wrist_delays = [float(value) for value in document["wrist_delay_fractions"]]
    coupled_fractions = np.asarray(document["coupled_fractions"], dtype=float)
    maximum_step = float(document.get("maximum_joint_step_deg", 1.0))
    minimum_effective_raw = int(document["minimum_effective_raw_delta"])
    table_z = float(document["table_reference_z_mm"])
    numeric = [
        *bounds.flat, *relief_deltas, *wrist_delays, *coupled_fractions,
        maximum_step, table_z,
    ]
    if (
        bounds.shape != (5, 2)
        or not all(math.isfinite(value) for value in numeric)
        or not relief_deltas
        or not all(value > 0.0 for value in relief_deltas)
        or not wrist_delays
        or not all(0.0 < value < 1.0 for value in wrist_delays)
        or coupled_fractions.ndim != 1
        or len(coupled_fractions) == 0
        or not np.all((coupled_fractions > 0.0) & (coupled_fractions < 1.0))
        or not np.all(np.diff(coupled_fractions) > 0.0)
        or not 0.0 < maximum_step <= 1.0
        or minimum_effective_raw <= 0
        or not np.allclose(target_xyz[:2], c_xy, atol=1e-9, rtol=0.0)
        or start[1] + max(relief_deltas) >= endpoint[1]
    ):
        raise ValueError("invalid PICK_READY path request")

    demonstrated_rotation = _transform(kinematics, reference)[:3, :3]
    candidates = [
        _candidate(
            kinematics=kinematics,
            start=start,
            endpoint=endpoint,
            lift_relief_delta_deg=relief_delta,
            wrist_delay_fraction=wrist_delay,
            coupled_fractions=coupled_fractions,
            grasp_offset=grasp_offset,
            bounds=bounds,
            c_xy=c_xy,
            target_xyz=target_xyz,
            table_z_mm=table_z,
            maximum_step_deg=maximum_step,
            demonstrated_rotation=demonstrated_rotation,
            minimum_effective_raw_delta=minimum_effective_raw,
        )
        for relief_delta in relief_deltas
        for wrist_delay in wrist_delays
    ]
    valid = [candidate for candidate in candidates if candidate["valid"]]
    if not valid:
        raise ValueError("no valid evidence-backed PICK_READY path")
    selected = min(valid, key=lambda candidate: (
        candidate["lift_relief_delta_deg"],
        -candidate["minimum_grasp_tcp_z_mm"],
        candidate["maximum_c_xy_distance_mm"],
        candidate["joint_route_l2_deg"],
        candidate["waypoint_count"],
    ))
    return {
        "status": "OFFLINE_DRY_RUN_ONLY",
        "canonical_start_pose": "PICK_READY",
        "start_pose_source": document.get("pick_ready_pose_source"),
        "endpoint_policy": "FIXED_EXISTING_GRASP_TCP_C_PRE_APPROACH",
        "home_path_or_absolute_lift_anchors_reused": False,
        "path_structure": [
            "PICK_READY", "RELATIVE_LIFT_RELIEF", "COUPLED_TRANSITION",
            "DELAYED_WRIST", "C_PRE_APPROACH",
        ],
        "load_evidence": document["load_evidence"],
        "candidates": candidates,
        "recommended_candidate": selected["candidate"],
        "recommended": selected,
        "selection_rule": (
            "smallest relative Lift relief exceeding measured effective raw motion; "
            "then highest minimum TCP Z, least XY excursion and shortest joint route "
            "among bounded FK/table/self-collision/servo-valid delayed-Wrist paths"
        ),
        "full_mesh_environment": "NOT_VERIFIED",
        "hardware_command_count": 0,
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
    urdf_sha256 = hashlib.sha256(args.urdf.read_bytes()).hexdigest()
    print(json.dumps(plan(
        document, UrdfKinematics.from_file(args.urdf), urdf_sha256), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
