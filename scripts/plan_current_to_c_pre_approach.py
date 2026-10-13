#!/usr/bin/env python3
"""Offline CURRENT→C PRE_APPROACH Wrist-leading path comparison.

This planner is deliberately hardware disconnected.  It keeps the recorded
fresh post-stop pose and the existing C/GRASP-TCP endpoint fixed, compares a
small set of Wrist-leading schedules, and reports the exact bounded waypoint
geometry used by the live runner.
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


def _vector(value: object, length: int, label: str) -> np.ndarray:
    result = np.asarray(value, dtype=float)
    if result.shape != (length,) or not np.isfinite(result).all():
        raise ValueError(f"{label} must contain {length} finite values")
    return result


def _mapping(values: np.ndarray) -> dict[str, float]:
    return {name: round(float(value), 6)
            for name, value in zip(ARM_NAMES, values)}


def _candidate(
    *,
    kinematics: UrdfKinematics,
    start: np.ndarray,
    endpoint: np.ndarray,
    wrist_lead_delta_deg: float,
    grasp_offset: np.ndarray,
    bounds: np.ndarray,
    c_xy: np.ndarray,
    target_xyz: np.ndarray,
    table_z_mm: float,
    maximum_step_deg: float,
    demonstrated_rotation: np.ndarray,
) -> dict:
    wrist_delta = float(endpoint[3] - start[3])
    wrist_direction = math.copysign(1.0, wrist_delta)
    wrist_lead = start.copy()
    wrist_lead[3] += wrist_direction * wrist_lead_delta_deg
    if wrist_lead_delta_deg > abs(wrist_delta) + 1e-9:
        raise ValueError("Wrist lead exceeds endpoint delta")
    start_mapping = {**dict(zip(ARM_NAMES, start)), "gripper": 0.0}
    intermediates = (
        [] if wrist_lead_delta_deg == 0.0
        else [dict(zip(ARM_NAMES, wrist_lead))]
    )
    goals = interpolate_staged_goals(
        start_mapping,
        intermediates,
        dict(zip(ARM_NAMES, endpoint)),
        maximum_step_deg,
    )
    samples = np.vstack([
        start,
        *[[goal[name] for name in ARM_NAMES] for goal in goals],
    ])
    tcp = np.asarray([
        tcp_position_mm(kinematics, joints, grasp_offset)
        for joints in samples
    ])
    xy_distance = np.linalg.norm(tcp[:, :2] - c_xy, axis=1)
    report = _path_report(
        kinematics, samples, grasp_offset, bounds, table_z_mm)
    final_error = float(np.linalg.norm(tcp[-1] - target_xyz))
    current_z = float(tcp[0, 2])
    minimum_allowed_z = min(current_z, float(target_xyz[2])) - 1e-6
    delta_z = np.diff(tcp[:, 2])
    delta_xy_distance = np.diff(xy_distance)
    negative_z_steps = int(np.count_nonzero(delta_z < -1e-9))
    increasing_xy_steps = int(np.count_nonzero(delta_xy_distance > 1e-9))
    valid = all((
        report["maximum_joint_step_deg"] <= maximum_step_deg + 1e-9,
        report["minimum_grasp_tcp_z_mm"] >= minimum_allowed_z,
        negative_z_steps == 0,
        increasing_xy_steps == 0,
        report["minimum_tcp_table_proxy_margin_mm"] > 0.0,
        report["minimum_nonadjacent_centerline_distance_mm"] > 30.0,
        report["minimum_servo_margin_deg"] >= 0.0,
        final_error <= 1e-3,
    ))
    progression = []
    previous = samples[0]
    for index, (joints, xyz, distance) in enumerate(
            zip(samples, tcp, xy_distance)):
        progression.append({
            "sample_index": index,
            "joints_deg": _mapping(joints),
            "max_joint_delta_deg": round(
                float(np.max(np.abs(joints - previous))), 9),
            "grasp_tcp_xyz_mm": [round(float(value), 6) for value in xyz],
            "c_xy_distance_mm": round(float(distance), 6),
        })
        previous = joints
    final_rotation = _transform(kinematics, endpoint)[:3, :3]
    if wrist_lead_delta_deg == 0.0:
        label = "DIRECT_COUPLED"
    else:
        label = f"WRIST_LEAD_{int(round(wrist_lead_delta_deg))}DEG"
    return {
        "candidate": label,
        "valid": bool(valid),
        "wrist_lead_delta_deg": wrist_lead_delta_deg,
        "wrist_lead_endpoint_deg": round(float(wrist_lead[3]), 6),
        "staged_intermediate_arm_deg": (
            [] if wrist_lead_delta_deg == 0.0 else [_mapping(wrist_lead)]
        ),
        "waypoint_count": len(goals),
        "maximum_joint_step_deg": report["maximum_joint_step_deg"],
        "joint_delta_start_to_target_deg": _mapping(endpoint - start),
        "waypoint_progression": progression,
        "grasp_tcp_start_xyz_mm": [round(float(value), 6) for value in tcp[0]],
        "grasp_tcp_wrist_lead_xyz_mm": [round(float(value), 6) for value in (
            tcp[0] if wrist_lead_delta_deg == 0.0
            else tcp[int(math.ceil(wrist_lead_delta_deg / maximum_step_deg))]
        )],
        "grasp_tcp_end_xyz_mm": [round(float(value), 6) for value in tcp[-1]],
        "minimum_grasp_tcp_z_mm": report["minimum_grasp_tcp_z_mm"],
        "maximum_grasp_tcp_z_mm": round(float(np.max(tcp[:, 2])), 6),
        "negative_z_steps": negative_z_steps,
        "minimum_tcp_z_increase_per_waypoint_mm": round(
            float(np.min(delta_z)), 6),
        "minimum_tcp_table_proxy_margin_mm":
            report["minimum_tcp_table_proxy_margin_mm"],
        "minimum_nonbase_link_origin_table_margin_mm": round(
            report["minimum_nonbase_link_origin_z_mm"] - table_z_mm, 6),
        "minimum_self_collision_centerline_margin_mm":
            report["minimum_nonadjacent_centerline_distance_mm"],
        "self_collision_proxy": report["self_collision_centerline_proxy"],
        "minimum_servo_margin_deg": report["minimum_servo_margin_deg"],
        "start_c_xy_distance_mm": round(float(xy_distance[0]), 6),
        "maximum_c_xy_distance_mm": round(float(np.max(xy_distance)), 6),
        "increasing_c_xy_distance_steps": increasing_xy_steps,
        "final_c_xy_distance_mm": round(float(xy_distance[-1]), 9),
        "final_grasp_tcp_target_error_mm": round(final_error, 9),
        "full_orientation_error_deg": round(
            rotation_error_deg(final_rotation, demonstrated_rotation), 6),
        "tool_axis_error_deg": round(axis_error_deg(
            -final_rotation[:, 2], -demonstrated_rotation[:, 2]), 6),
        "jaw_axis_error_deg": round(axis_error_deg(
            final_rotation[:, 0], demonstrated_rotation[:, 0]), 6),
        "environment_collision_proxy": report["environment_collision_proxy"],
        "full_mesh_environment": "NOT_VERIFIED",
    }


def plan(document: dict, kinematics: UrdfKinematics, urdf_sha256: str) -> dict:
    if document.get("urdf_sha256") != urdf_sha256:
        raise ValueError("URDF SHA mismatch")
    start = _vector(document["fresh_current_joints_deg"], 5, "fresh current joints")
    endpoint = _vector(document["pre_approach_joints_deg"], 5, "endpoint joints")
    grasp_offset = _vector(document["grasp_tcp_offset_gripper_mm"], 3, "GRASP TCP")
    c_xy = _vector(document["c_robot_xy_mm"], 2, "C robot XY")
    target_xyz = _vector(document["target_robot_xyz_mm"], 3, "target XYZ")
    reference = _vector(
        document["demonstrated_c_grasp_joints_deg"], 5, "orientation reference")
    bounds = np.asarray(document["servo_bounds_deg"], dtype=float)
    lead_deltas = [float(value) for value in document["wrist_lead_deltas_deg"]]
    recommended_lead = float(document["recommended_wrist_lead_delta_deg"])
    maximum_step = float(document.get("maximum_joint_step_deg", 1.0))
    table_z = float(document["table_reference_z_mm"])
    numeric = [*bounds.flat, *lead_deltas, recommended_lead, maximum_step, table_z]
    if (
        bounds.shape != (5, 2)
        or not all(math.isfinite(value) for value in numeric)
        or lead_deltas != [0.0, 2.0, 3.0]
        or recommended_lead not in {0.0, 2.0}
        or not 0.0 < maximum_step <= 1.0
        or not np.allclose(target_xyz[:2], c_xy, atol=1e-9, rtol=0.0)
        or document.get("motion_authorized") is not False
    ):
        raise ValueError("invalid CURRENT path request")
    demonstrated_rotation = _transform(kinematics, reference)[:3, :3]
    candidates = [
        _candidate(
            kinematics=kinematics,
            start=start,
            endpoint=endpoint,
            wrist_lead_delta_deg=lead_delta,
            grasp_offset=grasp_offset,
            bounds=bounds,
            c_xy=c_xy,
            target_xyz=target_xyz,
            table_z_mm=table_z,
            maximum_step_deg=maximum_step,
            demonstrated_rotation=demonstrated_rotation,
        )
        for lead_delta in lead_deltas
    ]
    valid = [candidate for candidate in candidates if candidate["valid"]]
    if not valid:
        raise ValueError("no valid bounded CURRENT path")
    selected = next((candidate for candidate in valid
                     if candidate["wrist_lead_delta_deg"] == recommended_lead), None)
    if selected is None:
        raise ValueError("recommended Wrist policy is not proxy-valid")
    return {
        "status": "OFFLINE_DRY_RUN_ONLY",
        "fresh_start_pose": "C_RETURN_ACTUAL_ATTEMPT2",
        "fresh_start_source": document["fresh_current_pose_source"],
        "endpoint_policy": "FIXED_EXISTING_GRASP_TCP_C_PRE_APPROACH",
        "joint_delta_start_to_target_deg": _mapping(endpoint - start),
        "path_structure": [
            "CURRENT", "WRIST_FLEX_LEAD", "BOUNDED_COUPLED_FINISH",
            "C_PRE_APPROACH",
        ],
        "tracking_evidence": document["tracking_evidence"],
        "candidates": candidates,
        "recommended_candidate": selected["candidate"],
        "recommended": selected,
        "selection_rule": (
            "DIRECT_COUPLED is selected after the measured Wrist-only phase "
            "stalled and reduced TCP Z; it preserves bounded monotonic TCP-Z "
            "and C-XY progress without repeating the failed Wrist-only phase"
            if recommended_lead == 0.0 else
            "exact 2-degree Wrist lead is the smallest staged lead chosen from "
            "DIRECT/2DEG/3DEG that preserves monotonic TCP-Z and C-XY progress; "
            "it addresses measured Wrist lag without a 3-degree Wrist-only phase"
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
