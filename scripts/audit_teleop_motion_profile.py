#!/usr/bin/env python3
"""Describe saved joint-broadcast changes without authorizing robot motion.

Finite differences are observations at broadcast timestamps, not measured motor
velocity, a collision check, or a replay trajectory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from scripts.audit_teleop_trace import JOINT_NAMES, audit as audit_urdf_trace


DEFAULT_URDF = Path(__file__).resolve().parents[1] / "configs/so101_installed_urdf_limits_20261005.json"


def audit_motion_profile(trace_dir: Path, limits_file: Path = DEFAULT_URDF) -> dict:
    integrity = audit_urdf_trace(trace_dir, limits_file)
    raw = (trace_dir / "joints.jsonl").read_bytes()
    if hashlib.sha256(raw).hexdigest() != integrity["trace_sha256"]:
        raise ValueError("joint trace changed after integrity check")
    samples = [json.loads(line) for line in raw.splitlines()]
    source = [float(row["source_unix"]) for row in samples]
    receive = [int(row["received_unix_ns"]) for row in samples]
    valid_pairs = [index for index in range(1, len(samples))
                   if source[index] > source[index - 1]
                   and receive[index] > receive[index - 1]]
    source_gaps = [source[index] - source[index - 1] for index in valid_pairs]
    profiles = {}
    for joint in JOINT_NAMES:
        positions = [float(row["joints_rad"][joint]) for row in samples]
        steps = [abs(positions[index] - positions[index - 1]) for index in valid_pairs]
        rates = [step / gap for step, gap in zip(steps, source_gaps)]
        profiles[joint] = {
            "start_rad": round(positions[0], 6),
            "end_rad": round(positions[-1], 6),
            "net_change_deg": round(math.degrees(positions[-1] - positions[0]), 3),
            "total_sampled_change_deg": round(math.degrees(sum(steps)), 3),
            "max_adjacent_change_deg": round(math.degrees(max(steps, default=0)), 3),
            "max_observed_finite_difference_deg_s": round(math.degrees(max(rates, default=0)), 3),
            "unchanged_adjacent_pairs": sum(step == 0 for step in steps),
        }
    return {
        "status": "OFFLINE_BROADCAST_PROFILE_ONLY",
        "trace": trace_dir.name,
        "trace_sha256": integrity["trace_sha256"],
        "sample_count": integrity["sample_count"],
        "urdf_audit_status": integrity["status"],
        "valid_adjacent_pairs": len(valid_pairs),
        "invalid_timestamp_pairs": len(samples) - 1 - len(valid_pairs),
        "source_gaps_over_200ms": sum(gap > 0.2 for gap in source_gaps),
        "max_source_gap_ms": round(max(source_gaps, default=0) * 1000, 3),
        "joints": profiles,
        "actual_motor_velocity_measured": False,
        "continuous_path_verified": False,
        "use_for_replay": False,
        "robot_enabled": False,
        "motion_authorized": False,
        "caution": "Broadcast finite differences omit motion between samples and do not measure motor response or clearance.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace-dir", type=Path, nargs="+", required=True)
    parser.add_argument("--limits", type=Path, default=DEFAULT_URDF)
    args = parser.parse_args()
    try:
        results = [audit_motion_profile(path, args.limits) for path in args.trace_dir]
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        parser.exit(2, f"offline motion profile failed: {error}\n")
    print(json.dumps(results, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
