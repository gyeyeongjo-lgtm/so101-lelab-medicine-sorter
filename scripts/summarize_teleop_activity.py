#!/usr/bin/env python3
"""Summarize a verified passive teleop trace without producing replay data.

The activity window starts at the first sample departing from the initial pose.
Its end is conservatively the end of capture, not an inferred task completion.
Camera times are Mac receive times, not synchronized sensor exposure times.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path

from audit_teleop_trace import JOINT_NAMES, audit


def summarize(samples: list[dict], camera_indices: dict[str, list[dict]], threshold_rad: float) -> dict:
    if not samples or not math.isfinite(threshold_rad) or threshold_rad <= 0:
        raise ValueError("nonempty samples and positive finite threshold required")
    first_pose = samples[0]["joints_rad"]
    if set(first_pose) != set(JOINT_NAMES):
        raise ValueError("initial pose does not contain exactly six joints")
    receive_times = [int(sample["received_unix_ns"]) for sample in samples]
    if any(right <= left for left, right in zip(receive_times, receive_times[1:])):
        raise ValueError("joint receive timestamps must increase")
    first_active = next((index for index, sample in enumerate(samples)
                         if any(abs(float(sample["joints_rad"][name]) - float(first_pose[name]))
                                > threshold_rad for name in JOINT_NAMES)), None)
    final_pose = samples[-1]["joints_rad"]
    terminal_identical = 0
    for sample in reversed(samples):
        if sample["joints_rad"] != final_pose:
            break
        terminal_identical += 1
    start_ns = receive_times[first_active] if first_active is not None else None
    end_ns = receive_times[-1]
    camera_summary = {}
    for name, frames in camera_indices.items():
        times = [int(frame["received_unix_ns"]) for frame in frames]
        if any(right <= left for left, right in zip(times, times[1:])):
            raise ValueError(f"{name} frame receive timestamps must increase")
        active_times = [] if start_ns is None else [t for t in times if start_ns <= t <= end_ns]
        gaps = [(b - a) / 1e9 for a, b in zip(active_times, active_times[1:])]
        camera_summary[name] = {
            "total_frames": len(times),
            "frames_in_provisional_activity_window": len(active_times),
            "first_active_frame_delay_s": None if not active_times else round((active_times[0] - start_ns) / 1e9, 3),
            "last_active_frame_before_capture_end_s": None if not active_times else round((end_ns - active_times[-1]) / 1e9, 3),
            "max_interframe_gap_s": None if not gaps else round(max(gaps), 3),
            "median_interframe_gap_s": None if not gaps else round(statistics.median(gaps), 3),
        }
    return {
        "status": "NO_POSE_DEPARTURE" if first_active is None else "PROVISIONAL_ACTIVITY_WINDOW",
        "threshold_rad": threshold_rad,
        "sample_count": len(samples),
        "first_active_sample_index": first_active,
        "initial_idle_duration_s": None if start_ns is None else round((start_ns - receive_times[0]) / 1e9, 3),
        "provisional_activity_duration_s": None if start_ns is None else round((end_ns - start_ns) / 1e9, 3),
        "joint_samples_in_window": 0 if first_active is None else len(samples) - first_active,
        "terminal_identical_pose_samples": terminal_identical,
        "terminal_identical_pose_span_s": round(
            (receive_times[-1] - receive_times[-terminal_identical]) / 1e9, 3),
        "cameras": camera_summary,
        "training_ready": False,
        "use_for_replay": False,
        "robot_enabled": False,
        "motion_authorized": False,
        "limitations": [
            "Activity means pose departed from the initial pose; task phases and success were not inferred.",
            "Camera timestamps are Mac receive times, not synchronized sensor exposure times.",
            "This summary does not resolve URDF limits, robot-world calibration, or path clearance.",
            "Repeated identical joint broadcasts do not prove physical stillness or contact clearance.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace-dir", type=Path, required=True)
    parser.add_argument("--limits", type=Path,
                        default=Path("configs/so101_installed_urdf_limits_20261005.json"))
    parser.add_argument("--threshold-rad", type=float, default=0.01)
    args = parser.parse_args()
    try:
        integrity = audit(args.trace_dir, args.limits)
        samples = [json.loads(line) for line in (args.trace_dir / "joints.jsonl").read_text().splitlines()]
        manifest = json.loads((args.trace_dir / "manifest.json").read_text())
        camera_indices = {
            name: [json.loads(line) for line in (args.trace_dir / name / "frames.jsonl").read_text().splitlines()]
            for name in manifest.get("camera_evidence", {})
        }
        result = summarize(samples, camera_indices, args.threshold_rad)
        result["integrity_audit_status"] = integrity["status"]
        result["camera_evidence_complete"] = integrity["camera_evidence_complete"]
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        parser.exit(2, f"activity summary failed: {error}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
