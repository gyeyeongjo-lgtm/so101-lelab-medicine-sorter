#!/usr/bin/env python3
"""Compare saved teleop observations with a dated follower calibration snapshot.

This is an offline diagnostic, not a motion, replay, or collision-clearance gate.
The current motor registers, torque, physical stops, and path are not read.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path

from scripts.audit_teleop_trace import JOINT_NAMES, audit as audit_urdf_trace


ARM_JOINTS = JOINT_NAMES[:-1]
DEFAULT_CALIBRATION = (
    Path(__file__).resolve().parents[1] / "configs/so101_follower_calibration_bounds_20261008.json"
)
DEFAULT_URDF = Path(__file__).resolve().parents[1] / "configs/so101_installed_urdf_limits_20261005.json"


def load_calibration_bounds(path: Path) -> tuple[dict[str, float], dict]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if (document.get("schema_version") != 1
            or document.get("motor_model") != "sts3215"
            or document.get("normalization_mode") != "DEGREES"
            or document.get("resolution_steps") != 4096):
        raise ValueError("unsupported calibration snapshot")
    source_hash = document.get("source_sha256")
    if not isinstance(source_hash, str) or re.fullmatch(r"[0-9a-f]{64}", source_hash) is None:
        raise ValueError("invalid calibration source SHA-256")
    ranges = document.get("arm_ranges_raw")
    if not isinstance(ranges, dict) or set(ranges) != set(ARM_JOINTS):
        raise ValueError("calibration snapshot must contain exactly five arm joints")
    bounds = {}
    for joint, raw in ranges.items():
        if (not isinstance(raw, list) or len(raw) != 2
                or any(type(value) is not int for value in raw)
                or not 0 <= raw[0] < raw[1] <= 4095):
            raise ValueError(f"invalid raw calibration range for {joint}")
        # LeRobot's installed DEGREES normalization is centred at the range midpoint.
        bounds[joint] = (raw[1] - raw[0]) * math.pi / 4095
    return bounds, document


def audit_calibration_trace(trace_dir: Path, calibration_file: Path,
                            urdf_limits_file: Path = DEFAULT_URDF,
                            near_limit_deg: float = 1.0) -> dict:
    if not math.isfinite(near_limit_deg) or near_limit_deg < 0:
        raise ValueError("near-limit threshold must be finite and nonnegative")
    bounds, calibration = load_calibration_bounds(calibration_file)
    # This also checks the joint SHA-256, record count, timestamps and any camera hashes.
    urdf_result = audit_urdf_trace(trace_dir, urdf_limits_file)
    positions = {joint: [] for joint in ARM_JOINTS}
    raw = (trace_dir / "joints.jsonl").read_bytes()
    if hashlib.sha256(raw).hexdigest() != urdf_result["trace_sha256"]:
        raise ValueError("joint trace changed after initial SHA-256 verification")
    for line in raw.splitlines():
        sample = json.loads(line)
        joints = sample["joints_rad"]
        for joint in ARM_JOINTS:
            value = float(joints[joint])
            if not math.isfinite(value):
                raise ValueError(f"nonfinite {joint} position")
            positions[joint].append(value)
    threshold = math.radians(near_limit_deg)
    envelope = {}
    for joint, values in positions.items():
        bound = bounds[joint]
        max_abs = max(map(abs, values))
        raw_min, raw_max = calibration["arm_ranges_raw"][joint]
        midpoint = (raw_min + raw_max) / 2
        implied_raw = [midpoint + value * (calibration["resolution_steps"] - 1) / (2 * math.pi)
                       for value in values]
        envelope[joint] = {
            "calibration_half_range_deg": round(math.degrees(bound), 6),
            "observed_min_deg": round(math.degrees(min(values)), 6),
            "observed_max_deg": round(math.degrees(max(values)), 6),
            "observed_min_implied_raw": round(min(implied_raw), 6),
            "observed_max_implied_raw": round(max(implied_raw), 6),
            "max_raw_quantization_residual_steps": round(
                max(abs(value - round(value)) for value in implied_raw), 9),
            "minimum_file_margin_deg": round(math.degrees(bound - max_abs), 6),
            "outside_file_range_samples": sum(abs(value) > bound for value in values),
            "within_near_limit_samples": sum(
                abs(value) <= bound and bound - abs(value) <= threshold for value in values
            ),
        }
    return {
        "status": "OFFLINE_CALIBRATION_FILE_COMPARISON_ONLY",
        "trace": trace_dir.name,
        "sample_count": urdf_result["sample_count"],
        "trace_sha256": urdf_result["trace_sha256"],
        "urdf_audit_status": urdf_result["status"],
        "calibration_source_sha256": calibration["source_sha256"],
        "calibration_snapshot_date": calibration["observed_on"],
        "near_limit_threshold_deg": near_limit_deg,
        "envelope": envelope,
        "current_registers_checked": False,
        "physical_clearance_verified": False,
        "use_for_replay": False,
        "robot_enabled": False,
        "motion_authorized": False,
        "caution": "File-range inclusion does not establish safe dynamic margin or reconcile URDF limits.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace-dir", type=Path, nargs="+", required=True)
    parser.add_argument("--calibration-bounds", type=Path, default=DEFAULT_CALIBRATION)
    parser.add_argument("--urdf-limits", type=Path, default=DEFAULT_URDF)
    parser.add_argument("--near-limit-deg", type=float, default=1.0)
    args = parser.parse_args()
    try:
        results = [audit_calibration_trace(path, args.calibration_bounds,
                                           args.urdf_limits, args.near_limit_deg)
                   for path in args.trace_dir]
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        parser.exit(2, f"offline calibration audit failed: {error}\n")
    print(json.dumps(results, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
