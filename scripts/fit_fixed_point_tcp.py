#!/usr/bin/env python3
"""Offline fixed-point TCP pivot diagnostic; never authorizes robot motion.

Fit the first N-1 captures of one physical X, reserving the last capture as an
independent posture holdout. All captures must use the same rigid fingertip.
The selected link is a URDF gripper or jaw frame, not a proven physical
fingertip. On the user's parallel gripper both fingers move; neither link may
be assumed to represent a rigid fingertip without physical validation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from scripts.urdf_forward_kinematics import UrdfKinematics


JOINT_NAMES = ("Rotation", "Pitch", "Elbow", "Wrist_Pitch", "Wrist_Roll", "Jaw")


def load_capture(folder: Path, kinematics: UrdfKinematics, tip_link: str) -> dict:
    metadata_path = folder / "metadata.json"
    raw = metadata_path.read_bytes()
    document = json.loads(raw)
    if any(document.get(key) is not False for key in
           ("use_for_robot_world_fit", "robot_enabled", "motion_authorized")):
        raise ValueError(f"{folder.name}: motion-blocking flags are missing")
    if not isinstance(document.get("point"), str) or not document["point"]:
        raise ValueError(f"{folder.name}: missing point label")
    if document.get("contact") != "user asserted; visual review pending":
        raise ValueError(f"{folder.name}: unexpected contact status")
    samples = document.get("joint_samples")
    if not isinstance(samples, list) or len(samples) < 10:
        raise ValueError(f"{folder.name}: fewer than 10 joint samples")
    joints = document.get("joint_mean_rad")
    if not isinstance(joints, dict) or any(name not in joints for name in JOINT_NAMES):
        raise ValueError(f"{folder.name}: incomplete joints")
    if not all(math.isfinite(float(joints[name])) for name in JOINT_NAMES):
        raise ValueError(f"{folder.name}: non-finite joints")
    std = float(document.get("joint_max_std_rad", math.inf))
    if not math.isfinite(std) or std > 0.01:
        raise ValueError(f"{folder.name}: unstable joints")
    images = document.get("images")
    gaps = document.get("frame_joint_receive_gap_ms")
    if not isinstance(images, dict) or not isinstance(gaps, dict):
        raise ValueError(f"{folder.name}: missing synchronized images")
    for camera in ("ceiling", "oblique"):
        if camera not in images or camera not in gaps:
            raise ValueError(f"{folder.name}: missing required {camera} image")
    for camera, image in images.items():
        filename = image.get("filename") if isinstance(image, dict) else None
        if not isinstance(filename, str) or Path(filename).name != filename:
            raise ValueError(f"{folder.name}: invalid {camera} filename")
        if hashlib.sha256((folder / filename).read_bytes()).hexdigest() != image.get("sha256"):
            raise ValueError(f"{folder.name}: {camera} image hash mismatch")
        gap = float(gaps.get(camera, math.inf))
        if not math.isfinite(gap) or gap > 250:
            raise ValueError(f"{folder.name}: {camera} receive-time gap too large")
    transform = kinematics.forward(joints, "base", tip_link)
    return {
        "name": folder.name,
        "point": document["point"],
        "metadata_sha256": hashlib.sha256(raw).hexdigest(),
        "origin_mm": transform[:3, 3] * 1000.0,
        "rotation": transform[:3, :3],
        "jaw_rad": float(joints["Jaw"]),
        "joint_max_std_rad": std,
    }


def fit_fixed_point(
    captures: list[dict],
    *,
    max_rmse_mm: float = 5.0,
    max_error_mm: float = 8.0,
    max_condition_number: float = 1000.0,
    max_tcp_offset_mm: float = 200.0,
    min_holdout_rotation_deg: float = 10.0,
) -> dict:
    if len(captures) < 5:
        raise ValueError("at least four fit postures and one holdout are required")
    if len({capture["point"] for capture in captures}) != 1:
        raise ValueError("all captures must refer to one fixed X")
    fit = captures[:-1]
    holdout = captures[-1]
    design = np.vstack([
        np.hstack((capture["rotation"], -np.eye(3))) for capture in fit
    ])
    target = np.concatenate([-capture["origin_mm"] for capture in fit])
    solution = np.linalg.lstsq(design, target, rcond=None)[0]
    tip = solution[:3]
    fixed_point = solution[3:]
    errors = [
        float(np.linalg.norm(capture["origin_mm"] + capture["rotation"] @ tip - fixed_point))
        for capture in captures
    ]
    fit_rmse = float(np.sqrt(np.mean(np.square(errors[:-1]))))
    rank = int(np.linalg.matrix_rank(design))
    condition = float(np.linalg.cond(design))
    fit_jaws = [capture["jaw_rad"] for capture in fit]
    fit_jaw_span = max(fit_jaws) - min(fit_jaws)
    holdout_jaw_delta = abs(holdout["jaw_rad"] - float(np.mean(fit_jaws)))
    holdout_rotation_angles = [
        math.degrees(math.acos(float(np.clip(
            (np.trace(capture["rotation"].T @ holdout["rotation"]) - 1.0) / 2.0,
            -1.0, 1.0,
        ))))
        for capture in fit
    ]
    holdout_min_rotation = min(holdout_rotation_angles)
    reasons = []
    if rank < 6:
        reasons.append("pivot_rank_below_6")
    if condition > max_condition_number:
        reasons.append("pivot_condition_above_limit")
    if fit_rmse > max_rmse_mm:
        reasons.append("fit_rmse_above_limit")
    if max(errors[:-1]) > max_error_mm:
        reasons.append("fit_max_error_above_limit")
    if errors[-1] > max_error_mm:
        reasons.append("holdout_error_above_limit")
    if float(np.linalg.norm(tip)) > max_tcp_offset_mm:
        reasons.append("tcp_offset_above_limit")
    if holdout_min_rotation < min_holdout_rotation_deg:
        reasons.append("holdout_orientation_too_close_to_fit")
    return {
        "status": "REJECTED_DIAGNOSTIC" if reasons else "NUMERIC_PASS_PHYSICAL_QA_PENDING",
        "point": fit[0]["point"],
        "fit_capture_names": [capture["name"] for capture in fit],
        "holdout_capture_name": holdout["name"],
        "rank": rank,
        "condition_number": condition,
        "fit_errors_mm": errors[:-1],
        "fit_rmse_mm": fit_rmse,
        "holdout_error_mm": errors[-1],
        "fit_jaw_span_rad": fit_jaw_span,
        "holdout_jaw_delta_rad": holdout_jaw_delta,
        "holdout_rotation_from_fit_deg": holdout_rotation_angles,
        "holdout_min_rotation_deg": holdout_min_rotation,
        "minimum_required_holdout_rotation_deg": min_holdout_rotation_deg,
        "tcp_offset_link_mm": tip.tolist(),
        "tcp_offset_norm_mm": float(np.linalg.norm(tip)),
        "fixed_contact_base_mm": fixed_point.tolist(),
        "rejection_reasons": reasons,
        "contact_visual_qa": "NOT_VERIFIED",
        "physical_finger_link_validation": "NOT_VERIFIED",
        "physical_contact_model": "URDF link frame is not a verified rigid fingertip; both physical fingers may move",
        "use_for_robot_world_fit": False,
        "robot_enabled": False,
        "motion_authorized": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--urdf", required=True, type=Path)
    parser.add_argument("--expected-urdf-sha256", required=True)
    parser.add_argument("--tip-link", required=True, choices=("gripper", "jaw"),
                        help="URDF link frame only; neither choice proves a fixed physical finger")
    parser.add_argument("--captures", required=True, nargs="+", type=Path,
                        help="ordered capture folders; last is the holdout")
    args = parser.parse_args()
    urdf_hash = hashlib.sha256(args.urdf.read_bytes()).hexdigest()
    if urdf_hash != args.expected_urdf_sha256.lower():
        parser.error("URDF SHA-256 does not match the installed-source reference")
    kinematics = UrdfKinematics.from_file(args.urdf)
    captures = [load_capture(folder, kinematics, args.tip_link) for folder in args.captures]
    result = fit_fixed_point(captures)
    result["tip_link"] = args.tip_link
    result["source_urdf_sha256"] = urdf_hash
    result["capture_metadata_sha256"] = {
        capture["name"]: capture["metadata_sha256"] for capture in captures
    }
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if not result["rejection_reasons"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
