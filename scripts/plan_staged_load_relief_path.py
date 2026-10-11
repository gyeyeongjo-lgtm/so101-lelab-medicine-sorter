#!/usr/bin/env python3
"""Offline-only staged joint-path analysis for an existing endpoint.

The module has no robot transport dependency.  It evaluates FK TCP clearance
proxies for staged joint paths and never opens a serial port or sends motion.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

if __package__:
    from scripts.urdf_forward_kinematics import UrdfKinematics
else:
    from urdf_forward_kinematics import UrdfKinematics


JOINTS = ("shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll")
URDF_JOINTS = ("Rotation", "Pitch", "Elbow", "Wrist_Pitch", "Wrist_Roll")


def _vector(mapping: dict, names: tuple[str, ...]) -> np.ndarray:
    if set(mapping) != set(names):
        raise ValueError("joint mapping does not match the five arm joints")
    result = np.asarray([mapping[name] for name in names], dtype=float)
    if result.shape != (5,) or not np.isfinite(result).all():
        raise ValueError("five finite arm joint values required")
    return result


def tcp_position_mm(kinematics: UrdfKinematics, joints_deg: np.ndarray,
                    tcp_offset_mm: np.ndarray) -> np.ndarray:
    transform = kinematics.forward(
        dict(zip(URDF_JOINTS, np.deg2rad(joints_deg))), "base", "gripper"
    )
    return transform[:3, 3] * 1000.0 + transform[:3, :3] @ tcp_offset_mm


def interpolate(start: np.ndarray, end: np.ndarray, max_step_deg: float) -> np.ndarray:
    maximum = float(np.max(np.abs(end - start)))
    count = max(1, math.ceil(maximum / max_step_deg))
    return np.linspace(start, end, count + 1)


def sample_segment(start: np.ndarray, end: np.ndarray) -> np.ndarray:
    """Dense FK sampling independent of the commanded waypoint spacing."""
    return interpolate(start, end, 0.1)


def _minimum_flex_for_nonlowering_tcp(
    kinematics: UrdfKinematics,
    start: np.ndarray,
    unload_lift_deg: float,
    tcp_offset_mm: np.ndarray,
    upper_flex_deg: float,
    max_step_deg: float,
) -> float:
    start_z = float(tcp_position_mm(kinematics, start, tcp_offset_mm)[2])
    first = math.ceil(start[3] * 4.0) / 4.0
    for flex in np.arange(first, upper_flex_deg + 1e-9, 0.25):
        stage = start.copy()
        stage[1] = unload_lift_deg
        stage[3] = flex
        samples = sample_segment(start, stage)
        minimum_z = min(float(tcp_position_mm(kinematics, q, tcp_offset_mm)[2])
                        for q in samples)
        if minimum_z >= start_z - 1e-6:
            return float(flex)
    raise ValueError("no wrist-flex value preserves start TCP height")


def _minimum_flex_for_prefinal_object_clearance(
    kinematics: UrdfKinematics,
    stage1: np.ndarray,
    unload_elbow_deg: float,
    tcp_offset_mm: np.ndarray,
    object_xy_mm: np.ndarray,
    minimum_object_distance_mm: float,
    upper_flex_deg: float,
    max_step_deg: float,
) -> float:
    first = math.ceil(stage1[3] * 4.0) / 4.0
    for flex in np.arange(first, upper_flex_deg + 1e-9, 0.25):
        stage2 = stage1.copy()
        stage2[2] = unload_elbow_deg
        stage2[3] = flex
        positions = np.asarray([
            tcp_position_mm(kinematics, q, tcp_offset_mm)
            for q in sample_segment(stage1, stage2)
        ])
        minimum_distance = float(np.min(
            np.linalg.norm(positions[:, :2] - object_xy_mm, axis=1)
        ))
        if minimum_distance >= minimum_object_distance_mm - 1e-6:
            return float(flex)
    raise ValueError("no wrist-flex value preserves pre-final object distance")


def _stage_report(
    name: str,
    kinematics: UrdfKinematics,
    previous: np.ndarray,
    target: np.ndarray,
    tcp_offset_mm: np.ndarray,
    object_xy_mm: np.ndarray,
    max_step_deg: float,
) -> tuple[dict, np.ndarray, np.ndarray]:
    bounded_samples = interpolate(previous, target, max_step_deg)
    samples = sample_segment(previous, target)
    positions = np.asarray([
        tcp_position_mm(kinematics, sample, tcp_offset_mm) for sample in samples
    ])
    report = {
        "stage": name,
        "joints_deg": {joint: round(float(value), 6) for joint, value in zip(JOINTS, target)},
        "joint_delta_deg": {
            joint: round(float(value), 6)
            for joint, value in zip(JOINTS, target - previous)
        },
        "fk_tcp_xyz_mm": [round(float(value), 6) for value in positions[-1]],
        "minimum_tcp_z_mm": round(float(np.min(positions[:, 2])), 6),
        "minimum_object_xy_distance_mm": round(float(np.min(
            np.linalg.norm(positions[:, :2] - object_xy_mm, axis=1)
        )), 6),
        "elbow_angle_deg": round(float(target[2]), 6),
        "bounded_intervals": len(bounded_samples) - 1,
        "maximum_joint_step_deg": round(
            float(np.max(np.abs(np.diff(bounded_samples, axis=0)))), 6
        ),
    }
    return report, samples, positions


def plan(document: dict, kinematics: UrdfKinematics) -> dict:
    start = _vector(document["start_joint_deg"], JOINTS)
    endpoint = _vector(document["endpoint_joint_deg"], JOINTS)
    failed_target = _vector(document["failed_waypoint_target_deg"], JOINTS)
    failed_feedback = _vector(document["failed_waypoint_feedback_deg"], JOINTS)
    bounds = np.asarray([document["servo_bounds_deg"][joint] for joint in JOINTS], dtype=float)
    offset = np.asarray(document["tcp_offset_gripper_mm"], dtype=float)
    object_xy = np.asarray(document["object_xy_mm"], dtype=float)
    max_step = float(document.get("maximum_joint_step_deg", 1.0))
    if (bounds.shape != (5, 2) or offset.shape != (3,) or object_xy.shape != (2,) or
            not np.isfinite(bounds).all() or not np.isfinite(offset).all() or
            not np.isfinite(object_xy).all() or not 0 < max_step <= 1.0):
        raise ValueError("invalid staged path request")

    start_tcp = tcp_position_mm(kinematics, start, offset)
    failed_target_tcp = tcp_position_mm(kinematics, failed_target, offset)
    failed_feedback_tcp = tcp_position_mm(kinematics, failed_feedback, offset)
    start_object_distance = float(np.linalg.norm(start_tcp[:2] - object_xy))
    candidates = []
    for specification in document["candidate_specs"]:
        stage1 = start.copy()
        stage1[1] = float(specification["unload_lift_deg"])
        stage1[3] = _minimum_flex_for_nonlowering_tcp(
            kinematics, start, stage1[1], offset, bounds[3, 1], max_step
        )
        stage2 = stage1.copy()
        stage2[2] = float(specification["unload_elbow_deg"])
        stage2[3] = _minimum_flex_for_prefinal_object_clearance(
            kinematics, stage1, stage2[2], offset, object_xy,
            start_object_distance, bounds[3, 1], max_step
        )
        targets = (
            ("UNLOAD_INTERMEDIATE_1", stage1),
            ("UNLOAD_INTERMEDIATE_2", stage2),
            ("EXISTING_PRE_APPROACH", endpoint),
        )
        previous = start
        stages = []
        all_samples = []
        all_positions = []
        for stage_name, target in targets:
            report, samples, positions = _stage_report(
                stage_name, kinematics, previous, target, offset, object_xy, max_step
            )
            stages.append(report)
            all_samples.append(samples)
            all_positions.append(positions)
            previous = target
        samples = np.vstack(all_samples)
        positions = np.vstack(all_positions)
        in_bounds = bool(np.all(samples >= bounds[:, 0] - 1e-9) and
                         np.all(samples <= bounds[:, 1] + 1e-9))
        pre_final_positions = np.vstack(all_positions[:2])
        pre_final_object_distance = float(np.min(
            np.linalg.norm(pre_final_positions[:, :2] - object_xy, axis=1)
        ))
        route_l2 = float(sum(np.linalg.norm(target - source) for source, target in (
            (start, stage1), (stage1, stage2), (stage2, endpoint)
        )))
        valid = bool(
            in_bounds and
            abs(stage1[2] - start[2]) <= 1e-9 and
            np.min(positions[:, 2]) >= start_tcp[2] - 1e-6 and
            pre_final_object_distance >= start_object_distance - 1e-6 and
            np.max(np.abs(np.diff(samples, axis=0))) <= max_step + 1e-9
        )
        candidates.append({
            "candidate": specification["candidate"],
            "valid": valid,
            "stages": stages,
            "path_minimum_tcp_z_mm": round(float(np.min(positions[:, 2])), 6),
            "pre_final_minimum_object_xy_distance_mm": round(pre_final_object_distance, 6),
            "start_object_xy_distance_mm": round(start_object_distance, 6),
            "joint_route_l2_deg": round(route_l2, 6),
            "servo_bounds_pass": in_bounds,
            "tcp_height_proxy_pass": bool(np.min(positions[:, 2]) >= start_tcp[2] - 1e-6),
            "pre_final_object_direction_proxy_pass": bool(
                pre_final_object_distance >= start_object_distance - 1e-6
            ),
        })

    valid_candidates = [candidate for candidate in candidates if candidate["valid"]]
    selected = min(valid_candidates, key=lambda candidate: candidate["joint_route_l2_deg"])
    return {
        "status": "DRY_RUN_ONLY",
        "motor_commands_sent": False,
        "follower_port_opened": False,
        "goal_or_torque_changed": False,
        "motion_authorized": False,
        "collision_checked": False,
        "joint_order": list(JOINTS),
        "start_joint_deg": document["start_joint_deg"],
        "start_fk_tcp_xyz_mm": [round(float(value), 6) for value in start_tcp],
        "existing_endpoint_joint_deg": document["endpoint_joint_deg"],
        "failed_waypoint": {
            "target_joint_deg": document["failed_waypoint_target_deg"],
            "feedback_joint_deg": document["failed_waypoint_feedback_deg"],
            "target_fk_tcp_xyz_mm": [round(float(value), 6) for value in failed_target_tcp],
            "feedback_fk_tcp_xyz_mm": [round(float(value), 6) for value in failed_feedback_tcp],
        },
        "candidates": candidates,
        "recommended_candidate": selected["candidate"],
        "selection_rule": "minimum total joint-space L2 route among candidates passing FK TCP safety proxies",
        "safety_scope": "TCP FK height/direction proxies only; environment and swept-link collision remain unverified",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--urdf", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    document = json.loads(args.request.read_text(encoding="utf-8"))
    print(json.dumps(plan(document, UrdfKinematics.from_file(args.urdf)), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
