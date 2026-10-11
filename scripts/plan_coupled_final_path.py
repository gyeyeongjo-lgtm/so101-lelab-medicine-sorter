#!/usr/bin/env python3
"""Offline FK comparison for coupled Shoulder-Lift/Elbow final paths."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

if __package__:
    from scripts.plan_staged_load_relief_path import interpolate, tcp_position_mm
    from scripts.urdf_forward_kinematics import UrdfKinematics
else:
    from plan_staged_load_relief_path import interpolate, tcp_position_mm
    from urdf_forward_kinematics import UrdfKinematics


JOINTS = ("shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll")


def _vector(mapping: dict) -> np.ndarray:
    if set(mapping) != set(JOINTS):
        raise ValueError("joint mapping mismatch")
    result = np.asarray([mapping[name] for name in JOINTS], dtype=float)
    if result.shape != (5,) or not np.isfinite(result).all():
        raise ValueError("five finite joints required")
    return result


def _joint_mapping(values: np.ndarray) -> dict[str, float]:
    return {name: round(float(value), 6) for name, value in zip(JOINTS, values)}


def plan(document: dict, kinematics: UrdfKinematics) -> dict:
    start = _vector(document["start_joint_deg"])
    anchor = _vector(document["safe_anchor_joint_deg"])
    endpoint = _vector(document["endpoint_joint_deg"])
    bounds = np.asarray([document["servo_bounds_deg"][name] for name in JOINTS], dtype=float)
    offset = np.asarray(document["tcp_offset_gripper_mm"], dtype=float)
    object_xy = np.asarray(document["object_xy_mm"], dtype=float)
    max_step = float(document.get("maximum_joint_step_deg", 1.0))
    fractions = np.asarray(document.get("schedule_fractions", [0.25, 0.5, 0.75]), dtype=float)
    if (bounds.shape != (5, 2) or offset.shape != (3,) or object_xy.shape != (2,) or
            not np.isfinite(bounds).all() or not np.isfinite(offset).all() or
            not np.isfinite(object_xy).all() or not 0 < max_step <= 1.0 or
            fractions.ndim != 1 or len(fractions) == 0 or
            not np.all((fractions > 0) & (fractions < 1)) or
            not np.all(np.diff(fractions) > 0)):
        raise ValueError("invalid coupled-path request")

    candidates = []
    for specification in document["candidate_specs"]:
        exponent = float(specification["elbow_progress_exponent"])
        if not math.isfinite(exponent) or exponent < 1.0:
            raise ValueError("elbow progress must not lead shoulder lift")
        schedule = [anchor]
        for fraction in fractions:
            target = anchor + (endpoint - anchor) * fraction
            target[2] = anchor[2] + (endpoint[2] - anchor[2]) * (fraction ** exponent)
            schedule.append(target)
        schedule.append(endpoint)

        dense = []
        bounded = []
        stages = []
        previous = start
        for index, target in enumerate(schedule):
            dense_segment = interpolate(previous, target, 0.1)
            bounded_segment = interpolate(previous, target, max_step)
            dense.extend(dense_segment[1:])
            bounded.extend(bounded_segment[1:])
            tcp = tcp_position_mm(kinematics, target, offset)
            stages.append({
                "stage": "SAFE_ANCHOR" if index == 0 else (
                    "EXISTING_PRE_APPROACH" if index == len(schedule) - 1
                    else f"COUPLED_{int(round(fractions[index - 1] * 100)):02d}"
                ),
                "joints_deg": _joint_mapping(target),
                "fk_tcp_xyz_mm": [round(float(value), 6) for value in tcp],
                "object_xy_distance_mm": round(float(np.linalg.norm(tcp[:2] - object_xy)), 6),
            })
            previous = target

        dense_array = np.asarray(dense)
        bounded_array = np.vstack([start, *bounded])
        positions = np.asarray([
            tcp_position_mm(kinematics, sample, offset) for sample in dense_array
        ])
        distances = np.linalg.norm(positions[:, :2] - object_xy, axis=1)
        margin = np.minimum(dense_array - bounds[:, 0], bounds[:, 1] - dense_array)
        route_l2 = float(sum(np.linalg.norm(target - source) for source, target in zip(
            [start, *schedule[:-1]], schedule
        )))
        in_bounds = bool(np.all(margin >= -1e-9))
        max_actual_step = float(np.max(np.abs(np.diff(bounded_array, axis=0))))
        monotonic_xy = bool(np.all(np.diff(distances) <= 1e-6))
        valid = bool(in_bounds and monotonic_xy and max_actual_step <= max_step + 1e-9)
        candidates.append({
            "candidate": specification["candidate"],
            "elbow_progress_exponent": exponent,
            "valid": valid,
            "joint_schedule": stages,
            "bounded_targets": len(bounded),
            "path_minimum_tcp_z_mm": round(float(np.min(positions[:, 2])), 6),
            "object_xy_distance_monotonic": monotonic_xy,
            "maximum_joint_step_deg": round(max_actual_step, 6),
            "minimum_servo_margin_deg": round(float(np.min(margin)), 6),
            "joint_route_l2_deg": round(route_l2, 6),
        })

    valid = [candidate for candidate in candidates if candidate["valid"]]
    if not valid:
        raise ValueError("no valid coupled path")
    selected = min(valid, key=lambda item: (
        item["joint_route_l2_deg"], -item["path_minimum_tcp_z_mm"]
    ))
    return {
        "status": "DRY_RUN_ONLY",
        "motor_commands_sent": False,
        "follower_port_opened": False,
        "goal_or_torque_changed": False,
        "motion_authorized": False,
        "collision_checked": False,
        "joint_order": list(JOINTS),
        "start_joint_deg": document["start_joint_deg"],
        "safe_anchor_joint_deg": document["safe_anchor_joint_deg"],
        "existing_endpoint_joint_deg": document["endpoint_joint_deg"],
        "candidates": candidates,
        "recommended_candidate": selected["candidate"],
        "selection_rule": "minimum joint-route L2, then highest TCP minimum Z, among bounded monotonic-C FK paths where elbow progress never leads lift",
        "safety_scope": "TCP FK and joint-limit proxies only; environment and swept-link collision remain unverified",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--urdf", required=True, type=Path)
    args = parser.parse_args()
    document = json.loads(args.request.read_text(encoding="utf-8"))
    print(json.dumps(plan(document, UrdfKinematics.from_file(args.urdf)), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
