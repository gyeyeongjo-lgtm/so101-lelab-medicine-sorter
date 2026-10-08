#!/usr/bin/env python3
"""Offline-only C→ID4 waypoint limits/FK comparison; never sends commands."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from scripts.urdf_forward_kinematics import UrdfKinematics


MOTOR_TO_URDF = {
    "shoulder_pan": "Rotation", "shoulder_lift": "Pitch",
    "elbow_flex": "Elbow", "wrist_flex": "Wrist_Pitch",
    "wrist_roll": "Wrist_Roll", "gripper": "Jaw",
}


def inspect_candidate(document: dict, limits: dict, kinematics: UrdfKinematics,
                      observations: list[dict]) -> dict:
    if (document.get("status") != "OFFLINE_CANDIDATE_ONLY" or
            document.get("motion_authorized") is not False or
            document.get("collision_verified") is not False):
        raise ValueError("candidate_must_remain_non_executable")
    if not observations:
        raise ValueError("reference_trace_missing")
    t0 = observations[0]["received_unix_ns"]
    result = []
    all_limits = True
    segments = []
    previous_goal = None
    previous_name = None
    for waypoint in document["waypoints"]:
        goal = waypoint["goal"]
        if set(goal) != set(MOTOR_TO_URDF):
            raise ValueError("joint_goal_shape_mismatch")
        q = {urdf: math.radians(goal[motor]) for motor, urdf in MOTOR_TO_URDF.items()}
        margins = {name: round(math.degrees(min(q[name] - limits[name][0],
                                                limits[name][1] - q[name])), 3)
                   for name in MOTOR_TO_URDF.values()}
        within = all(value > 0 for value in margins.values())
        all_limits &= within
        sample = min(observations,
                     key=lambda row: abs((row["received_unix_ns"] - t0) / 1e9 -
                                         waypoint["reference_elapsed_s"]))
        delta = {name: round(abs(goal[motor] - math.degrees(sample["joints_rad"][name])), 3)
                 for motor, name in MOTOR_TO_URDF.items()}
        transform = kinematics.forward(q, "base", "gripper")
        result.append({"name": waypoint["name"], "stage": waypoint["stage"],
                       "within_urdf_limits": within, "joint_margin_deg": margins,
                       "minimum_margin_deg": min(margins.values()),
                       "max_reference_difference_deg_or_gripper_points": max(delta.values()),
                       "reference_difference": delta,
                       "model_gripper_origin_mm": [round(float(x) * 1000, 2)
                                                   for x in transform[:3, 3]]})
        if previous_goal is not None:
            minimum_margin = math.inf
            minimum_gripper_z_mm = math.inf
            for index in range(21):
                fraction = index / 20
                interpolated = {
                    motor: previous_goal[motor] * (1 - fraction) + goal[motor] * fraction
                    for motor in MOTOR_TO_URDF
                }
                q_segment = {urdf: math.radians(interpolated[motor])
                             for motor, urdf in MOTOR_TO_URDF.items()}
                minimum_margin = min(minimum_margin, *(
                    math.degrees(min(q_segment[name] - limits[name][0],
                                     limits[name][1] - q_segment[name]))
                    for name in MOTOR_TO_URDF.values()))
                pose = kinematics.forward(q_segment, "base", "gripper")
                minimum_gripper_z_mm = min(minimum_gripper_z_mm,
                                          float(pose[2, 3]) * 1000)
            all_limits &= minimum_margin > 0
            segments.append({"from": previous_name, "to": waypoint["name"],
                             "sampled_linear_minimum_margin_deg": round(minimum_margin, 3),
                             "sampled_model_gripper_origin_min_z_mm": round(minimum_gripper_z_mm, 2),
                             "collision_verified": False})
        previous_goal = goal
        previous_name = waypoint["name"]
    return {"status": "LIMITS_ONLY_PASS" if all_limits else "LIMITS_FAIL",
            "waypoints": result, "segments": segments, "motion_authorized": False,
            "collision_verified": False, "physical_axes_verified": False,
            "note": "Sparse candidate goals, not a replay or verified continuous path; FK link origin is not TCP."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--limits", type=Path, required=True)
    parser.add_argument("--urdf", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    args = parser.parse_args()
    document = json.loads(args.candidate.read_text())
    digest = hashlib.sha256(args.urdf.read_bytes()).hexdigest()
    if digest != document["urdf_sha256"]:
        raise ValueError("installed_urdf_sha_mismatch")
    limit_file = json.loads(args.limits.read_text())
    if limit_file["source_sha256"] != digest:
        raise ValueError("limit_snapshot_sha_mismatch")
    observations = [json.loads(line) for line in args.reference.open()]
    result = inspect_candidate(document, limit_file["joints"],
                               UrdfKinematics.from_file(args.urdf), observations)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "LIMITS_ONLY_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
