#!/usr/bin/env python3
"""Plan a read-only FK escape using joints that responded in the last trial.

This module never imports a robot transport and has no serial, torque, camera,
or Goal_Position path.  It preserves Lift and Elbow, uses the local FK
sensitivity to select Wrist Flex direction, and compares requested cumulative
GRASP-TCP Z gains under a two-degree waypoint bound.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np

if __package__:
    from scripts.plan_pick_grasp_tcp_ik import (
        JOINTS, URDF_JOINTS, _segment_distance, _transform, axis_error_deg,
        tcp_position_mm,
    )
    from scripts.urdf_forward_kinematics import UrdfKinematics
else:
    from plan_pick_grasp_tcp_ik import (
        JOINTS, URDF_JOINTS, _segment_distance, _transform, axis_error_deg,
        tcp_position_mm,
    )
    from urdf_forward_kinematics import UrdfKinematics


CHAIN_LINKS = ("base", "shoulder", "upper_arm", "lower_arm", "wrist", "gripper")
WRIST_FLEX_INDEX = JOINTS.index("wrist_flex")


def _vector(value: object, length: int, label: str) -> np.ndarray:
    result = np.asarray(value, dtype=float)
    if result.shape != (length,) or not np.isfinite(result).all():
        raise ValueError(f"{label} must contain {length} finite values")
    return result


def minimum_centerline_distance_mm(
    kinematics: UrdfKinematics, q_deg: np.ndarray,
) -> float:
    joint_map = dict(zip(URDF_JOINTS, np.deg2rad(q_deg)))
    points = np.asarray([
        kinematics.forward(joint_map, "base", link)[:3, 3] * 1000.0
        for link in CHAIN_LINKS
    ])
    result = float("inf")
    for first in range(len(points) - 1):
        for second in range(first + 2, len(points) - 1):
            result = min(result, _segment_distance(
                points[first], points[first + 1],
                points[second], points[second + 1],
            ))
    return result


def fk_z_sensitivity_mm_per_deg(
    kinematics: UrdfKinematics,
    q_deg: np.ndarray,
    grasp_offset_mm: np.ndarray,
    epsilon_deg: float,
) -> dict[str, float]:
    identity = np.eye(len(JOINTS))
    return {
        joint: float((
            tcp_position_mm(
                kinematics, q_deg + identity[index] * epsilon_deg,
                grasp_offset_mm,
            )[2]
            - tcp_position_mm(
                kinematics, q_deg - identity[index] * epsilon_deg,
                grasp_offset_mm,
            )[2]
        ) / (2.0 * epsilon_deg))
        for index, joint in enumerate(JOINTS)
    }


def find_wrist_endpoint(
    kinematics: UrdfKinematics,
    start: np.ndarray,
    grasp_offset: np.ndarray,
    bounds: np.ndarray,
    target_gain_mm: float,
    direction: float,
) -> np.ndarray | None:
    start_z = float(tcp_position_mm(kinematics, start, grasp_offset)[2])
    index = WRIST_FLEX_INDEX
    limit = bounds[index, 1] if direction > 0 else bounds[index, 0]
    maximum_delta = abs(float(limit - start[index]))
    low = 0.0
    high = min(1.0, maximum_delta)

    def gain(magnitude: float) -> float:
        q = start.copy()
        q[index] += direction * magnitude
        return float(tcp_position_mm(kinematics, q, grasp_offset)[2] - start_z)

    while high < maximum_delta and gain(high) < target_gain_mm:
        low = high
        high = min(maximum_delta, high * 2.0)
    if gain(high) < target_gain_mm:
        return None
    for _ in range(80):
        middle = (low + high) / 2.0
        if gain(middle) >= target_gain_mm:
            high = middle
        else:
            low = middle
    endpoint = start.copy()
    endpoint[index] += direction * high
    return endpoint


def _pose_metrics(
    kinematics: UrdfKinematics,
    q_deg: np.ndarray,
    grasp_offset: np.ndarray,
    bounds: np.ndarray,
    table_z_mm: float,
    reference_tool_axis: np.ndarray,
    reference_jaw_axis: np.ndarray,
) -> dict:
    xyz = tcp_position_mm(kinematics, q_deg, grasp_offset)
    transform = _transform(kinematics, q_deg)
    servo_margin = np.minimum(q_deg - bounds[:, 0], bounds[:, 1] - q_deg)
    centerline = minimum_centerline_distance_mm(kinematics, q_deg)
    return {
        "grasp_tcp_xyz_mm": [round(float(value), 6) for value in xyz],
        "table_proxy_margin_mm": round(float(xyz[2] - table_z_mm), 6),
        "self_collision_centerline_margin_mm": round(centerline, 6),
        "minimum_servo_margin_deg": round(float(np.min(servo_margin)), 6),
        "tool_axis_change_deg": round(axis_error_deg(
            -transform[:3, 2], reference_tool_axis,
        ), 6),
        "jaw_axis_change_deg": round(axis_error_deg(
            transform[:3, 0], reference_jaw_axis,
        ), 6),
    }


def _candidate(
    *,
    kinematics: UrdfKinematics,
    start: np.ndarray,
    endpoint: np.ndarray,
    grasp_offset: np.ndarray,
    bounds: np.ndarray,
    table_z_mm: float,
    maximum_step_deg: float,
    minimum_centerline_mm: float,
    target_gain_mm: float,
) -> dict:
    intervals = max(1, math.ceil(float(np.max(np.abs(endpoint - start))) /
                                 maximum_step_deg))
    samples = np.asarray([
        start + (endpoint - start) * progress
        for progress in np.linspace(0.0, 1.0, intervals + 1)
    ])
    start_xyz = tcp_position_mm(kinematics, start, grasp_offset)
    start_margin = float(start_xyz[2] - table_z_mm)
    reference_tool_axis = -_transform(kinematics, start)[:3, 2]
    reference_jaw_axis = _transform(kinematics, start)[:3, 0]
    waypoints = []
    previous = start
    z_values = []
    xy_drifts = []
    centerlines = []
    servo_margins = []
    table_margins = []
    for number, q_deg in enumerate(samples[1:], start=1):
        metrics = _pose_metrics(
            kinematics, q_deg, grasp_offset, bounds, table_z_mm,
            reference_tool_axis, reference_jaw_axis,
        )
        xyz = np.asarray(metrics["grasp_tcp_xyz_mm"], dtype=float)
        z_gain = float(xyz[2] - start_xyz[2])
        xy_drift = float(np.linalg.norm(xyz[:2] - start_xyz[:2]))
        delta = q_deg - previous
        waypoints.append({
            "waypoint": number,
            "joints_deg": {
                name: round(float(value), 6)
                for name, value in zip(JOINTS, q_deg)
            },
            "joint_delta_deg": {
                name: round(float(value), 6)
                for name, value in zip(JOINTS, delta)
            },
            **metrics,
            "delta_z_mm": round(
                float(xyz[2] - tcp_position_mm(
                    kinematics, previous, grasp_offset,
                )[2]), 6,
            ),
            "cumulative_z_gain_mm": round(z_gain, 6),
            "xy_drift_from_start_mm": round(xy_drift, 6),
        })
        previous = q_deg
        z_values.append(float(xyz[2]))
        xy_drifts.append(xy_drift)
        centerlines.append(float(metrics["self_collision_centerline_margin_mm"]))
        servo_margins.append(float(metrics["minimum_servo_margin_deg"]))
        table_margins.append(float(metrics["table_proxy_margin_mm"]))
    step = float(np.max(np.abs(np.diff(samples, axis=0))))
    monotonic = all(after > before for before, after in zip(
        [float(start_xyz[2]), *z_values[:-1]], z_values,
    ))
    table_not_worse = all(margin + 1e-9 >= start_margin for margin in table_margins)
    centerline_pass = min(centerlines) > minimum_centerline_mm
    servo_pass = min(servo_margins) >= 0.0
    achieved_gain = z_values[-1] - float(start_xyz[2])
    valid = all((
        step <= maximum_step_deg + 1e-12,
        monotonic,
        table_not_worse,
        centerline_pass,
        servo_pass,
        achieved_gain + 1e-6 >= target_gain_mm,
    ))
    return {
        "name": f"WRIST_ESCAPE_Z_PLUS_{int(target_gain_mm)}",
        "target_z_gain_mm": target_gain_mm,
        "predicted_cumulative_z_gain_mm": round(achieved_gain, 6),
        "endpoint_joints_deg": {
            name: round(float(value), 6)
            for name, value in zip(JOINTS, endpoint)
        },
        "waypoint_count": len(waypoints),
        "maximum_joint_step_deg": round(step, 6),
        "predicted_z_monotonic_increase": monotonic,
        "table_proxy_not_worse_than_start": table_not_worse,
        "minimum_table_proxy_margin_mm": round(min(table_margins), 6),
        "minimum_self_collision_centerline_margin_mm": round(min(centerlines), 6),
        "self_collision_centerline_proxy": "PASS" if centerline_pass else "FAIL",
        "minimum_servo_margin_deg": round(min(servo_margins), 6),
        "servo_range": "PASS" if servo_pass else "FAIL",
        "maximum_xy_drift_mm": round(max(xy_drifts), 6),
        "excessive_xy_drift_threshold_mm": "NOT_DEFINED",
        "lift_elbow_motion_required": False,
        "pan_roll_motion_required": False,
        "full_mesh_collision_status": "NOT_VERIFIED",
        "offline_constraints_pass": valid,
        "waypoints": waypoints,
    }


def plan(document: dict, kinematics: UrdfKinematics, urdf_sha256: str) -> dict:
    if document.get("urdf_sha256") != urdf_sha256:
        raise ValueError("URDF SHA mismatch")
    if document.get("motion_authorized") is not False:
        raise ValueError("offline request must not authorize motion")
    if document.get("full_mesh_collision_status") != "NOT_VERIFIED":
        raise ValueError("full mesh status must remain NOT_VERIFIED")
    start = _vector(document["current_arm_joints_deg"], 5, "current joints")
    grasp_offset = _vector(
        document["pick_grasp_tcp_offset_gripper_mm"], 3, "GRASP TCP offset",
    )
    bounds = np.asarray(document["servo_bounds_deg"], dtype=float)
    if bounds.shape != (5, 2) or not np.isfinite(bounds).all():
        raise ValueError("servo bounds must be a finite 5x2 matrix")
    requested_gains = np.asarray(document["requested_z_gains_mm"], dtype=float)
    if (requested_gains.ndim != 1 or len(requested_gains) == 0 or
            not np.isfinite(requested_gains).all()):
        raise ValueError("Z gains must be a nonempty finite vector")
    if any(value <= 0 for value in requested_gains):
        raise ValueError("requested Z gains must be positive")
    maximum_step = float(document["maximum_joint_step_deg"])
    epsilon = float(document["finite_difference_step_deg"])
    table_z = float(document["table_contact_reference_z_mm"])
    minimum_centerline = float(document["minimum_self_collision_centerline_mm"])
    recommended_first_gain = float(document["recommended_first_live_z_gain_mm"])
    phase_c_minimum_margin = float(
        document["phase_c_minimum_intermediate_table_margin_mm"])
    if not 0 < maximum_step <= 2.0 or not 0 < epsilon <= 0.1:
        raise ValueError("offline escape step policy invalid")

    sensitivity = fk_z_sensitivity_mm_per_deg(
        kinematics, start, grasp_offset, epsilon,
    )
    wrist_sensitivity = sensitivity["wrist_flex"]
    if abs(wrist_sensitivity) < 1e-9:
        direction = 0.0
    else:
        direction = math.copysign(1.0, wrist_sensitivity)
    # Move with the derivative's sign so delta_q * dZ/dq is positive.
    direction = direction

    candidates = []
    if direction != 0.0:
        for gain in requested_gains:
            endpoint = find_wrist_endpoint(
                kinematics, start, grasp_offset, bounds,
                float(gain), direction,
            )
            if endpoint is not None:
                candidates.append(_candidate(
                    kinematics=kinematics,
                    start=start,
                    endpoint=endpoint,
                    grasp_offset=grasp_offset,
                    bounds=bounds,
                    table_z_mm=table_z,
                    maximum_step_deg=maximum_step,
                    minimum_centerline_mm=minimum_centerline,
                    target_gain_mm=float(gain),
                ))

    eligible = [
        candidate for candidate in candidates
        if candidate["offline_constraints_pass"] and
        candidate["target_z_gain_mm"] + 1e-9 >= recommended_first_gain
    ]
    recommendation = min(
        eligible,
        key=lambda candidate: (
            candidate["waypoint_count"],
            abs(candidate["endpoint_joints_deg"]["wrist_flex"] -
                start[WRIST_FLEX_INDEX]),
            candidate["maximum_xy_drift_mm"],
        ),
        default=None,
    )
    start_xyz = tcp_position_mm(kinematics, start, grasp_offset)
    return {
        "status": "OFFLINE_DRY_RUN_ONLY",
        "current_pose_source": document.get("current_pose_source"),
        "current_arm_joints_deg": {
            name: round(float(value), 6)
            for name, value in zip(JOINTS, start)
        },
        "current_grasp_tcp_xyz_mm": [round(float(value), 6) for value in start_xyz],
        "current_table_proxy_margin_mm": round(float(start_xyz[2] - table_z), 6),
        "fk_z_sensitivity_mm_per_deg": {
            name: round(value, 9) for name, value in sensitivity.items()
        },
        "selected_responsive_joint": "wrist_flex",
        "selected_direction_deg_sign": int(direction),
        "selection_reason": (
            "Wrist Flex moved 79.121% in SAFE_ESCAPE_2DEG; FK sign chooses monotonic Z increase. "
            "Lift and Elbow are held; Pan and Roll are unnecessary for Z."
        ),
        "candidates": candidates,
        "recommended_first_live_z_gain_mm": recommended_first_gain,
        "phase_c_minimum_intermediate_table_margin_mm": phase_c_minimum_margin,
        "recommended_candidate": (
            None if recommendation is None else recommendation["name"]
        ),
        "responsive_joint_escape": (
            "NOT_FOUND" if recommendation is None else "FOUND_OFFLINE_ONLY"
        ),
        "full_mesh_collision_status": "NOT_VERIFIED",
        "actual_motor_command_count": 0,
        "follower_port_opened": False,
        "goal_or_torque_changed": False,
        "phase_c": "HOLD",
        "motion_authorized": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--urdf", required=True, type=Path)
    args = parser.parse_args()
    document = json.loads(args.request.read_text(encoding="utf-8"))
    digest = hashlib.sha256(args.urdf.read_bytes()).hexdigest()
    print(json.dumps(
        plan(document, UrdfKinematics.from_file(args.urdf), digest),
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
