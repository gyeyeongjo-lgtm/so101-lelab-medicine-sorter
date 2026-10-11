#!/usr/bin/env python3
"""Compare offline-only Wrist-Flex delay schedules on a fixed coupled path.

The Shoulder-Lift/Elbow/Pan/Roll geometry and the final endpoint are inherited
from an existing balanced coupled path.  Only Wrist Flex timing is changed.
This module has no robot transport dependency.
"""

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


def _mapping(values: np.ndarray) -> dict[str, float]:
    return {name: round(float(value), 6) for name, value in zip(JOINTS, values)}


def plan(document: dict, kinematics: UrdfKinematics) -> dict:
    start = _vector(document["start_joint_deg"])
    anchor = _vector(document["balanced_anchor_joint_deg"])
    endpoint = _vector(document["endpoint_joint_deg"])
    bounds = np.asarray([document["servo_bounds_deg"][name] for name in JOINTS], dtype=float)
    offset = np.asarray(document["tcp_offset_gripper_mm"], dtype=float)
    object_xy = np.asarray(document["object_xy_mm"], dtype=float)
    max_step = float(document.get("maximum_joint_step_deg", 1.0))
    rate_scale = float(document.get("wrist_progress_rate_scale", 0.75))
    fractions = np.asarray(document.get("schedule_fractions", [0.25, 0.5, 0.75, 1.0]), dtype=float)
    delay_fractions = [float(value) for value in document["wrist_delay_fractions"]]

    lift_span = endpoint[1] - anchor[1]
    start_progress = (start[1] - anchor[1]) / lift_span
    if (bounds.shape != (5, 2) or offset.shape != (3,) or object_xy.shape != (2,) or
            not np.isfinite(bounds).all() or not np.isfinite(offset).all() or
            not np.isfinite(object_xy).all() or not 0 < max_step <= 1.0 or
            not 0 < rate_scale <= 1.0 or not math.isfinite(start_progress) or
            not 0 <= start_progress < 1 or fractions.ndim != 1 or len(fractions) == 0 or
            not np.all((fractions > start_progress) & (fractions <= 1.0)) or
            not np.all(np.diff(fractions) > 0) or not delay_fractions or
            not all(start_progress < value < 1.0 for value in delay_fractions)):
        raise ValueError("invalid delayed-wrist request")

    start_tcp = tcp_position_mm(kinematics, start, offset)
    start_distance = float(np.linalg.norm(start_tcp[:2] - object_xy))
    legacy_wrist_delta = endpoint[3] - anchor[3]
    candidates = []

    for delay in delay_fractions:
        schedule = []
        stage_progress = []
        candidate_fractions = sorted(set([*fractions.tolist(), delay]))
        for fraction in candidate_fractions:
            target = anchor + (endpoint - anchor) * fraction
            wrist_progress = max(0.0, fraction - delay) * rate_scale
            target[3] = start[3] + legacy_wrist_delta * wrist_progress
            schedule.append(target)
            stage_progress.append(float(fraction))
        # Exact endpoint is a separate final stage: Wrist reaches it only after
        # the load-relieving Shoulder/Elbow coupled path has completed.
        if not np.allclose(schedule[-1], endpoint, rtol=0.0, atol=1e-12):
            schedule.append(endpoint)
            stage_progress.append(1.0)

        dense_parts = []
        bounded_parts = []
        coupled_wrist_steps = []
        stages = []
        previous = start
        for index, (target, progress) in enumerate(zip(schedule, stage_progress)):
            dense_segment = interpolate(previous, target, 0.1)
            bounded_segment = interpolate(previous, target, max_step)
            dense_parts.append(dense_segment[1:])
            bounded_parts.append(bounded_segment[1:])
            if index < len(schedule) - 1:
                coupled_wrist_steps.extend(np.abs(np.diff(bounded_segment[:, 3])).tolist())
            tcp = tcp_position_mm(kinematics, target, offset)
            is_final = index == len(schedule) - 1
            stages.append({
                "stage": "EXISTING_PRE_APPROACH" if is_final else f"COUPLED_{int(round(progress * 100)):03d}",
                "coupled_progress": round(progress, 6),
                "joints_deg": _mapping(target),
                "fk_tcp_xyz_mm": [round(float(value), 6) for value in tcp],
                "object_xy_distance_mm": round(float(np.linalg.norm(tcp[:2] - object_xy)), 6),
            })
            previous = target

        dense = np.vstack(dense_parts)
        bounded = np.vstack([start, *bounded_parts])
        positions = np.asarray([tcp_position_mm(kinematics, sample, offset) for sample in dense])
        distances = np.linalg.norm(positions[:, :2] - object_xy, axis=1)
        margin = np.minimum(dense - bounds[:, 0], bounds[:, 1] - dense)
        max_actual_step = float(np.max(np.abs(np.diff(bounded, axis=0))))
        monotonic_xy = bool(np.all(np.diff(distances) <= 1e-6))
        endpoint_exact = bool(np.allclose(schedule[-1], endpoint, rtol=0.0, atol=1e-12))
        in_bounds = bool(np.all(margin >= -1e-9))
        valid = bool(in_bounds and endpoint_exact and monotonic_xy and
                     max_actual_step <= max_step + 1e-9)
        candidates.append({
            "candidate": f"WRIST_DELAY_{int(round(delay * 100)):02d}",
            "wrist_delay_fraction": delay,
            "wrist_progress_rate_scale": rate_scale,
            "valid": valid,
            "waypoint_schedule": stages,
            "bounded_targets": int(sum(len(part) for part in bounded_parts)),
            "path_minimum_tcp_z_mm": round(float(np.min(positions[:, 2])), 6),
            "start_object_xy_distance_mm": round(start_distance, 6),
            "minimum_object_xy_distance_mm": round(float(np.min(distances)), 6),
            "object_xy_distance_monotonic": monotonic_xy,
            "maximum_joint_step_deg": round(max_actual_step, 6),
            "maximum_coupled_wrist_step_deg": round(float(max(coupled_wrist_steps)), 6),
            "final_wrist_only_delta_deg": round(float(abs(schedule[-2][3] - endpoint[3])), 6),
            "minimum_servo_margin_deg": round(float(np.min(margin)), 6),
            "endpoint_exact": endpoint_exact,
        })

    valid_candidates = [candidate for candidate in candidates if candidate["valid"]]
    if not valid_candidates:
        raise ValueError("no valid delayed-wrist path")
    selected = min(valid_candidates, key=lambda item: item["wrist_delay_fraction"])
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
        "start_object_xy_distance_mm": round(start_distance, 6),
        "balanced_anchor_joint_deg": document["balanced_anchor_joint_deg"],
        "existing_endpoint_joint_deg": document["endpoint_joint_deg"],
        "candidates": candidates,
        "recommended_candidate": selected["candidate"],
        "selection_rule": "smallest Wrist-Flex delay among bounded, exact-endpoint, servo-in-bounds, monotonic-C TCP FK paths",
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
