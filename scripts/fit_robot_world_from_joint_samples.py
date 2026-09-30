#!/usr/bin/env python3
"""Offline SO-101 touch fit from LeLab joint broadcasts and an installed URDF.

This script only reads saved files. It never opens a camera or robot serial bus,
and its result never authorizes motion.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from scripts.fit_robot_world_tcp_transform import build_result
from scripts.urdf_forward_kinematics import UrdfKinematics


JOINT_NAMES = ("Rotation", "Pitch", "Elbow", "Wrist_Pitch", "Wrist_Roll", "Jaw")


def load_reviewed_pairs(path: Path, urdf_path: Path) -> tuple[dict, list[float]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("robot_enabled") is not False or document.get("motion_authorized") is not False:
        raise ValueError("source pair file must explicitly block robot motion")
    records = document.get("pairs")
    if not isinstance(records, list) or not 4 <= len(records) <= 16:
        raise ValueError("4 to 16 touch records are required")
    kinematics = UrdfKinematics.from_file(urdf_path)
    jaws: list[float] = []
    for record in records:
        sample = record.get("joint_sample")
        if not isinstance(sample, dict) or sample.get("source") != "LeLab /ws/joint-data":
            raise ValueError(f"missing LeLab broadcast sample: {record.get('name')}")
        if sample.get("serial_access") is not False or int(sample.get("samples", 0)) < 10:
            raise ValueError(f"unreviewed or too-short sample: {record.get('name')}")
        stability = float(sample.get("max_std_rad", math.inf))
        if not math.isfinite(stability) or stability > 0.01:
            raise ValueError(f"unstable sample: {record.get('name')}")
        joints = sample.get("joints_mean")
        if not isinstance(joints, dict) or any(name not in joints for name in JOINT_NAMES):
            raise ValueError(f"incomplete joints: {record.get('name')}")
        joints = {name: float(joints[name]) for name in JOINT_NAMES}
        if not all(math.isfinite(value) for value in joints.values()):
            raise ValueError(f"non-finite joints: {record.get('name')}")
        transform = kinematics.forward(joints, "base", "gripper")
        record["gripper_link_origin_mm"] = (transform[:3, 3] * 1000.0).tolist()
        record["gripper_link_rotation"] = transform[:3, :3].tolist()
        jaws.append(joints["Jaw"])
    if max(jaws) - min(jaws) > 0.02:
        raise ValueError("Jaw changed too much for a fixed-tip teach")
    return document, jaws


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pairs", required=True, type=Path)
    parser.add_argument("--urdf", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output already exists; never overwrite a teach result")
    if not args.output.parent.is_dir():
        parser.error("output parent does not exist")
    document, jaws = load_reviewed_pairs(args.pairs, args.urdf)
    result = build_result(
        document,
        {
            "max_rmse_mm": 5.0,
            "max_error_mm": 8.0,
            "max_condition_number": 1000.0,
            "max_tcp_offset_mm": 200.0,
        },
    )
    result["source_pairs_sha256"] = hashlib.sha256(args.pairs.read_bytes()).hexdigest()
    result["source_urdf_sha256"] = hashlib.sha256(args.urdf.read_bytes()).hexdigest()
    result["jaw_span_rad"] = max(jaws) - min(jaws)
    result["robot_enabled"] = False
    result["motion_authorized"] = False
    result["note"] += " Input joint samples came only from LeLab /ws/joint-data."
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        f"{result['status']} pairs={result['source_pairs']} "
        f"rmse_mm={result['rmse_mm']:.3f} max_error_mm={result['max_error_mm']:.3f} "
        f"condition={result['condition_number']:.1f} robot_enabled=false"
    )
    return 0 if not result["rejection_reasons"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
