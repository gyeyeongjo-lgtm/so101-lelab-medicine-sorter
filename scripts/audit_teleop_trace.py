#!/usr/bin/env python3
"""Offline integrity and installed-URDF-limit audit of a passive teleop trace.

The result is a rejection gate, never permission to command or replay a robot.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

JOINT_NAMES = ("Rotation", "Pitch", "Elbow", "Wrist_Pitch", "Wrist_Roll", "Jaw")


def audit(trace_dir: Path, limits_file: Path) -> dict:
    manifest = json.loads((trace_dir / "manifest.json").read_text(encoding="utf-8"))
    limits = json.loads(limits_file.read_text(encoding="utf-8"))
    if set(limits["joints"]) != set(JOINT_NAMES):
        raise ValueError("limits must contain exactly the six known joints")
    for name in JOINT_NAMES:
        bounds = limits["joints"][name]
        if (not isinstance(bounds, list) or len(bounds) != 2 or
                not all(isinstance(v, (int, float)) and math.isfinite(v) for v in bounds) or
                bounds[0] >= bounds[1]):
            raise ValueError(f"invalid {name} limits")
    if manifest.get("joint_file") != "joints.jsonl":
        raise ValueError("unexpected joint file name")
    raw = (trace_dir / "joints.jsonl").read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != manifest.get("joint_file_sha256"):
        raise ValueError("joint trace SHA-256 does not match manifest")
    violations = {name: {"below": 0, "above": 0, "max_excess_rad": 0.0} for name in JOINT_NAMES}
    first_source = previous_source = None
    previous_receive = None
    duplicate_or_reverse_source = 0
    non_increasing_receive = 0
    max_receive_gap_ms = 0.0
    count = 0
    for line in raw.splitlines():
        sample = json.loads(line)
        positions = sample["joints_rad"]
        if set(positions) != set(JOINT_NAMES):
            raise ValueError("trace sample has missing or unknown joints")
        source = float(sample["source_unix"])
        received = int(sample["received_unix_ns"])
        if not math.isfinite(source) or received <= 0:
            raise ValueError("trace sample has invalid timestamps")
        if previous_source is not None and source <= previous_source:
            duplicate_or_reverse_source += 1
        if previous_receive is not None:
            if received <= previous_receive:
                non_increasing_receive += 1
            else:
                max_receive_gap_ms = max(max_receive_gap_ms, (received - previous_receive) / 1e6)
        if first_source is None:
            first_source = source
        previous_source, previous_receive = source, received
        for name in JOINT_NAMES:
            value = float(positions[name])
            if not math.isfinite(value):
                raise ValueError(f"nonfinite {name} position")
            lower, upper = limits["joints"][name]
            if value < lower:
                violations[name]["below"] += 1
                violations[name]["max_excess_rad"] = max(
                    violations[name]["max_excess_rad"], lower - value)
            elif value > upper:
                violations[name]["above"] += 1
                violations[name]["max_excess_rad"] = max(
                    violations[name]["max_excess_rad"], value - upper)
        count += 1
    if count != manifest.get("sample_count") or count == 0:
        raise ValueError("trace sample count is empty or disagrees with manifest")
    for row in violations.values():
        row["max_excess_rad"] = round(row["max_excess_rad"], 6)
    mismatched = any(row["below"] or row["above"] for row in violations.values())
    return {
        "status": "URDF_LIMIT_MISMATCH" if mismatched else "NO_URDF_LIMIT_MISMATCH_DETECTED",
        "trace_sha256": digest,
        "source_urdf_sha256": limits["source_sha256"],
        "sample_count": count,
        "source_span_s": round(previous_source - first_source, 3),
        "max_receive_gap_ms": round(max_receive_gap_ms, 3),
        "duplicate_or_reverse_source_times": duplicate_or_reverse_source,
        "non_increasing_receive_times": non_increasing_receive,
        "violations": violations,
        "use_for_replay": False,
        "robot_enabled": False,
        "motion_authorized": False,
        "caution": "URDF vs broadcast mismatch is not proof of physical hard-stop violation; neither outcome certifies safe motion",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace-dir", type=Path, required=True)
    parser.add_argument("--limits", type=Path,
                        default=Path("configs/so101_installed_urdf_limits_20261005.json"))
    args = parser.parse_args()
    try:
        result = audit(args.trace_dir, args.limits)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        parser.exit(2, f"trace audit failed: {error}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 2 if result["status"] == "URDF_LIMIT_MISMATCH" else 0


if __name__ == "__main__":
    raise SystemExit(main())
