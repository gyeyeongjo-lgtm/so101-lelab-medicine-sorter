#!/usr/bin/env python3
"""Offline PICK pose/path planner with explicit PIN and GRASP TCP frames.

This module has no robot, serial, service, camera, torque, or Goal_Position
dependency.  It keeps the calibration PIN TCP for diagnostics and uses the
separate GRASP opening-center TCP for PICK IK.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np

if __package__:
    from scripts.urdf_forward_kinematics import UrdfKinematics
else:
    from urdf_forward_kinematics import UrdfKinematics


URDF_JOINTS = ("Rotation", "Pitch", "Elbow", "Wrist_Pitch", "Wrist_Roll")
JOINTS = ("shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll")


def _vector(value: object, length: int, label: str) -> np.ndarray:
    result = np.asarray(value, dtype=float)
    if result.shape != (length,) or not np.isfinite(result).all():
        raise ValueError(f"{label} must contain {length} finite values")
    return result


def _transform(kinematics: UrdfKinematics, q_deg: np.ndarray) -> np.ndarray:
    return kinematics.forward(
        dict(zip(URDF_JOINTS, np.deg2rad(q_deg))), "base", "gripper"
    )


def tcp_position_mm(kinematics: UrdfKinematics, q_deg: np.ndarray,
                    offset_mm: np.ndarray) -> np.ndarray:
    transform = _transform(kinematics, q_deg)
    return transform[:3, 3] * 1000.0 + transform[:3, :3] @ offset_mm


def _rotation_vector_error(actual: np.ndarray, reference: np.ndarray) -> np.ndarray:
    return 0.5 * sum(
        (np.cross(actual[:, index], reference[:, index]) for index in range(3)),
        start=np.zeros(3),
    )


def rotation_error_deg(actual: np.ndarray, reference: np.ndarray) -> float:
    cosine = (float(np.trace(reference.T @ actual)) - 1.0) / 2.0
    return math.degrees(math.acos(float(np.clip(cosine, -1.0, 1.0))))


def axis_error_deg(actual: np.ndarray, reference: np.ndarray) -> float:
    return math.degrees(math.acos(float(np.clip(actual @ reference, -1.0, 1.0))))


def solve_pose_candidate(
    kinematics: UrdfKinematics,
    target_mm: np.ndarray,
    grasp_offset_mm: np.ndarray,
    reference_rotation: np.ndarray,
    seed_deg: np.ndarray,
    bounds_deg: np.ndarray,
) -> dict:
    """Orientation-seeded IK followed by exact position refinement.

    SO-101 has five arm axes, so arbitrary 6-DoF poses are over-constrained.
    The first pass minimizes position plus demonstrated-grasp orientation; the
    second makes position exact while retaining the closest branch found.
    """
    lower, upper = np.deg2rad(bounds_deg[:, 0]), np.deg2rad(bounds_deg[:, 1])
    q = np.clip(np.deg2rad(seed_deg), lower, upper)
    identity = np.eye(5)

    def pose_residual(q_rad: np.ndarray) -> np.ndarray:
        transform = kinematics.forward(
            dict(zip(URDF_JOINTS, q_rad)), "base", "gripper"
        )
        position = transform[:3, 3] * 1000.0 + transform[:3, :3] @ grasp_offset_mm
        return np.r_[position - target_mm,
                     30.0 * _rotation_vector_error(transform[:3, :3], reference_rotation)]

    def improve(residual_function, dimension: int, iterations: int,
                initial_damping: float, maximum_step_rad: float) -> None:
        nonlocal q
        damping = initial_damping
        for _ in range(iterations):
            residual = residual_function(q)
            cost = float(residual @ residual)
            epsilon = 2e-5
            jacobian = np.column_stack([
                (residual_function(np.clip(q + identity[index] * epsilon, lower, upper)) - residual)
                / epsilon
                for index in range(5)
            ])
            step = -np.linalg.solve(
                jacobian.T @ jacobian + damping * damping * np.eye(5),
                jacobian.T @ residual,
            )
            step = np.clip(step, -maximum_step_rad, maximum_step_rad)
            improved = False
            for scale in (1.0, 0.5, 0.25, 0.125, 0.0625):
                candidate = np.clip(q + scale * step, lower, upper)
                candidate_residual = residual_function(candidate)
                if float(candidate_residual @ candidate_residual) < cost - 1e-14:
                    q = candidate
                    damping = max(0.01, damping / 1.4)
                    improved = True
                    break
            if not improved:
                damping *= 3.0
                if damping > 1e8:
                    break

    improve(pose_residual, 6, 250, 5.0, math.radians(7.0))

    def position_residual(q_rad: np.ndarray) -> np.ndarray:
        transform = kinematics.forward(
            dict(zip(URDF_JOINTS, q_rad)), "base", "gripper"
        )
        return transform[:3, 3] * 1000.0 + transform[:3, :3] @ grasp_offset_mm - target_mm

    improve(position_residual, 3, 350, 3.0, math.radians(2.0))
    q_deg = np.rad2deg(q)
    transform = _transform(kinematics, q_deg)
    position = tcp_position_mm(kinematics, q_deg, grasp_offset_mm)
    margin = np.minimum(q_deg - bounds_deg[:, 0], bounds_deg[:, 1] - q_deg)
    return {
        "joints_deg": {name: round(float(value), 6) for name, value in zip(JOINTS, q_deg)},
        "fk_grasp_tcp_base_mm": [round(float(value), 6) for value in position],
        "grasp_tcp_position_error_mm": round(float(np.linalg.norm(position - target_mm)), 9),
        "full_orientation_error_deg": round(
            rotation_error_deg(transform[:3, :3], reference_rotation), 6
        ),
        "tool_axis_error_deg": round(axis_error_deg(
            -transform[:3, 2], -reference_rotation[:, 2]
        ), 6),
        "jaw_reference_x_axis_error_deg": round(axis_error_deg(
            transform[:3, 0], reference_rotation[:, 0]
        ), 6),
        "minimum_servo_margin_deg": round(float(np.min(margin)), 6),
    }


def _progress_path(start: np.ndarray, end: np.ndarray, *, maximum_step_deg: float,
                   wrist_delay_fraction: float) -> np.ndarray:
    intervals = max(1, math.ceil(float(np.max(np.abs(end - start))) / maximum_step_deg))
    while True:
        samples = []
        for s in np.linspace(0.0, 1.0, intervals + 1):
            progress = np.full(5, s)
            progress[1] = s ** 0.85       # Shoulder Lift leads slightly.
            progress[2] = s ** 1.15       # Elbow never leads Shoulder Lift.
            progress[3] = (0.0 if s <= wrist_delay_fraction else
                           (s - wrist_delay_fraction) / (1.0 - wrist_delay_fraction))
            samples.append(start + (end - start) * progress)
        result = np.asarray(samples)
        if float(np.max(np.abs(np.diff(result, axis=0)))) <= maximum_step_deg + 1e-12:
            return result
        intervals += 1


def _segment_distance(p1: np.ndarray, p2: np.ndarray,
                      q1: np.ndarray, q2: np.ndarray) -> float:
    # Closest distance between two finite centerline segments.
    u, v, w = p2 - p1, q2 - q1, p1 - q1
    a, b, c, d, e = u @ u, u @ v, v @ v, u @ w, v @ w
    denominator = a * c - b * b
    small = 1e-12
    s_numerator, s_denominator = 0.0, denominator
    t_numerator, t_denominator = 0.0, denominator
    if denominator < small:
        s_denominator = 1.0
        t_numerator, t_denominator = e, c
    else:
        s_numerator, t_numerator = b * e - c * d, a * e - b * d
        if s_numerator < 0.0:
            s_numerator, t_numerator, t_denominator = 0.0, e, c
        elif s_numerator > s_denominator:
            s_numerator, t_numerator, t_denominator = s_denominator, e + b, c
    if t_numerator < 0.0:
        t_numerator = 0.0
        if -d < 0.0:
            s_numerator = 0.0
        elif -d > a:
            s_numerator = s_denominator
        else:
            s_numerator, s_denominator = -d, a
    elif t_numerator > t_denominator:
        t_numerator = t_denominator
        if -d + b < 0.0:
            s_numerator = 0.0
        elif -d + b > a:
            s_numerator = s_denominator
        else:
            s_numerator, s_denominator = -d + b, a
    s = 0.0 if abs(s_numerator) < small else s_numerator / s_denominator
    t = 0.0 if abs(t_numerator) < small else t_numerator / t_denominator
    return float(np.linalg.norm(w + s * u - t * v))


def _path_report(kinematics: UrdfKinematics, samples: np.ndarray,
                 grasp_offset: np.ndarray, bounds: np.ndarray,
                 table_contact_z_mm: float) -> dict:
    tcp = np.asarray([tcp_position_mm(kinematics, q, grasp_offset) for q in samples])
    chain_links = ("base", "shoulder", "upper_arm", "lower_arm", "wrist", "gripper")
    minimum_centerline = float("inf")
    minimum_nonbase_origin_z = float("inf")
    for q in samples:
        positions = np.asarray([
            kinematics.forward(dict(zip(URDF_JOINTS, np.deg2rad(q))), "base", link)[:3, 3]
            * 1000.0 for link in chain_links
        ])
        minimum_nonbase_origin_z = min(minimum_nonbase_origin_z, float(np.min(positions[1:, 2])))
        for first in range(len(positions) - 1):
            for second in range(first + 2, len(positions) - 1):
                minimum_centerline = min(minimum_centerline, _segment_distance(
                    positions[first], positions[first + 1],
                    positions[second], positions[second + 1],
                ))
    margin = np.minimum(samples - bounds[:, 0], bounds[:, 1] - samples)
    minimum_tcp_z = float(np.min(tcp[:, 2]))
    minimum_sample_index = int(np.argmin(tcp[:, 2]))
    minimum_commanded_index = int(np.argmin(tcp[1:, 2])) + 1
    return {
        "sample_count": len(samples),
        "maximum_joint_step_deg": round(float(np.max(np.abs(np.diff(samples, axis=0)))), 6),
        "minimum_servo_margin_deg": round(float(np.min(margin)), 6),
        "minimum_grasp_tcp_z_mm": round(minimum_tcp_z, 6),
        "minimum_sample_index_zero_is_saved_start": minimum_sample_index,
        "minimum_sample_joints_deg": [
            round(float(value), 6) for value in samples[minimum_sample_index]
        ],
        "minimum_sample_grasp_tcp_xyz_mm": [
            round(float(value), 6) for value in tcp[minimum_sample_index]
        ],
        "minimum_commanded_waypoint_one_based": minimum_commanded_index,
        "minimum_commanded_waypoint_joints_deg": [
            round(float(value), 6) for value in samples[minimum_commanded_index]
        ],
        "minimum_commanded_waypoint_grasp_tcp_xyz_mm": [
            round(float(value), 6) for value in tcp[minimum_commanded_index]
        ],
        "minimum_commanded_waypoint_table_proxy_margin_mm": round(
            float(tcp[minimum_commanded_index, 2] - table_contact_z_mm), 6
        ),
        "minimum_nonbase_link_origin_z_mm": round(minimum_nonbase_origin_z, 6),
        "minimum_nonadjacent_centerline_distance_mm": round(minimum_centerline, 6),
        "table_contact_reference_z_mm": round(table_contact_z_mm, 6),
        "minimum_tcp_table_proxy_margin_mm": round(minimum_tcp_z - table_contact_z_mm, 6),
        "self_collision_centerline_proxy": "PASS" if minimum_centerline > 30.0 else "FAIL",
        "environment_collision_proxy": (
            "BLOCKED_START_BELOW_TABLE_CONTACT_REFERENCE"
            if minimum_tcp_z < table_contact_z_mm else "TCP_POINT_ONLY_PASS"
        ),
        "full_mesh_collision_status": "NOT_VERIFIED",
    }


def plan(document: dict, kinematics: UrdfKinematics, urdf_sha256: str) -> dict:
    if document.get("urdf_sha256") != urdf_sha256:
        raise ValueError("URDF SHA mismatch")
    pin_offset = _vector(document["calibration_pin_tcp_offset_gripper_mm"], 3, "PIN TCP")
    grasp_offset = _vector(document["pick_grasp_tcp_offset_gripper_mm"], 3, "GRASP TCP")
    if np.allclose(pin_offset, grasp_offset):
        raise ValueError("calibration PIN and PICK GRASP TCP must be distinct")
    current = _vector(document["saved_follower_joints_deg"], 5, "saved follower joints")
    reference = _vector(document["demonstrated_c_grasp_feedback_joints_deg"], 5,
                        "demonstrated grasp joints")
    bounds = np.asarray(document["servo_bounds_deg"], dtype=float)
    if bounds.shape != (5, 2) or not np.isfinite(bounds).all():
        raise ValueError("servo bounds must be a finite 5x2 matrix")
    c_xy = _vector(document["c_robot_xy_mm"], 2, "C robot XY")
    reference_rotation = _transform(kinematics, reference)[:3, :3]

    pre_target = np.r_[c_xy, float(document["pre_approach_z_mm"])]
    approach_target = np.r_[c_xy, float(document["approach_z_mm"])]
    pre = solve_pose_candidate(
        kinematics, pre_target, grasp_offset, reference_rotation, reference, bounds
    )
    approach = solve_pose_candidate(
        kinematics, approach_target, grasp_offset, reference_rotation, reference, bounds
    )
    pre_joints = np.asarray(list(pre["joints_deg"].values()))
    approach_joints = np.asarray(list(approach["joints_deg"].values()))
    maximum_step = float(document.get("maximum_joint_step_deg", 1.0))
    wrist_delay = float(document.get("wrist_delay_fraction", 0.10))
    current_to_pre = _progress_path(
        current, pre_joints, maximum_step_deg=maximum_step,
        wrist_delay_fraction=wrist_delay,
    )
    pre_to_approach = _progress_path(
        pre_joints, approach_joints, maximum_step_deg=maximum_step,
        wrist_delay_fraction=wrist_delay,
    )
    path = np.vstack([current_to_pre, pre_to_approach[1:]])
    path_report = _path_report(
        kinematics, path, grasp_offset, bounds,
        float(document["table_contact_reference_z_mm"]),
    )
    # Local-only escape candidate.  The direction is the sign of the GRASP
    # TCP Z gradient at the saved start, limited to one degree per joint.  It
    # does not erase the negative start sample and is never motion authority.
    epsilon_deg = 0.01
    start_tcp = tcp_position_mm(kinematics, current, grasp_offset)
    z_gradient = np.asarray([
        (tcp_position_mm(
            kinematics,
            current + np.eye(5)[index] * epsilon_deg,
            grasp_offset,
        )[2] - start_tcp[2]) / epsilon_deg
        for index in range(5)
    ])
    safe_escape = np.clip(
        current + np.sign(z_gradient) * maximum_step,
        bounds[:, 0], bounds[:, 1],
    )
    escape_to_pre = _progress_path(
        safe_escape, pre_joints, maximum_step_deg=maximum_step,
        wrist_delay_fraction=wrist_delay,
    )
    escape_path = np.vstack([
        current,
        safe_escape,
        escape_to_pre[1:],
        pre_to_approach[1:],
    ])
    escape_report = _path_report(
        kinematics, escape_path, grasp_offset, bounds,
        float(document["table_contact_reference_z_mm"]),
    )
    final_q = approach_joints
    final_target = approach_target
    final_transform = _transform(kinematics, final_q)
    final_pin = tcp_position_mm(kinematics, final_q, pin_offset)
    final_origin = final_transform[:3, 3] * 1000.0
    current_to_approach = approach_joints - current
    return {
        "status": "OFFLINE_DRY_RUN_ONLY",
        "tcp_frames": {
            "calibration_pin_tcp_offset_gripper_mm": pin_offset.tolist(),
            "pick_grasp_tcp_offset_gripper_mm": grasp_offset.tolist(),
            "frames_explicitly_separated": True,
        },
        "c_robot_xy_mm": c_xy.tolist(),
        "current_pose_source": document.get("saved_follower_pose_source"),
        "current_pose_is_fresh_live_feedback": False,
        "orientation_reference": {
            "source": document.get("demonstrated_c_grasp_source"),
            "method": "successful demonstrated C grasp; full rotation scored, position refined exactly",
        },
        "pre_approach": pre,
        "approach": approach,
        "final_frame_distances_mm": {
            "grasp_tcp_to_c_target": approach["grasp_tcp_position_error_mm"],
            "pin_tcp_to_c_target": round(float(np.linalg.norm(final_pin - final_target)), 6),
            "gripper_origin_to_c_target": round(float(np.linalg.norm(final_origin - final_target)), 6),
        },
        "current_to_approach_delta_deg": {
            name: round(float(value), 6) for name, value in zip(JOINTS, current_to_approach)
        },
        "current_to_approach_max_abs_delta_deg": round(
            float(np.max(np.abs(current_to_approach))), 6
        ),
        "path_policy": {
            "shoulder_lift_progress_exponent": 0.85,
            "elbow_progress_exponent": 1.15,
            "wrist_flex_delay_fraction": wrist_delay,
            "maximum_joint_step_deg": maximum_step,
            "principle": "Lift leads Elbow slightly; Wrist Flex starts later; no catch-up burst",
        },
        "path": path_report,
        "safe_escape_path_candidate": {
            "name": "SAFE_ESCAPE_1DEG",
            "first_target_joints_deg": [
                round(float(value), 6) for value in safe_escape
            ],
            "first_target_grasp_tcp_xyz_mm": [
                round(float(value), 6)
                for value in tcp_position_mm(kinematics, safe_escape, grasp_offset)
            ],
            "first_target_selected_from": "sign of local GRASP-TCP Z gradient, each joint bounded to 1 degree",
            "report": escape_report,
            "final_endpoint_unchanged": True,
            "status": "OFFLINE_CANDIDATE_REQUIRES_INITIAL_CLEARANCE_AND_FULL_MESH_VERIFICATION",
        },
        "collision_status": "NOT_VERIFIED_BLOCKED_PROXY",
        "actual_motor_command_count": 0,
        "follower_port_opened": False,
        "goal_or_torque_changed": False,
        "motion_authorized": False,
        "grasp_or_lift_run": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--urdf", required=True, type=Path)
    args = parser.parse_args()
    document = json.loads(args.request.read_text(encoding="utf-8"))
    digest = hashlib.sha256(args.urdf.read_bytes()).hexdigest()
    print(json.dumps(plan(document, UrdfKinematics.from_file(args.urdf), digest), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
