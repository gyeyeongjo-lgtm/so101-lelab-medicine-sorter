#!/usr/bin/env python3
"""Collect changed, steady Astra ROI frames for human review (no YOLO labels).

Reads the existing MJPEG preview; it never opens a camera or imports robot code.
All saved frames are unreviewed proposals, not training or motion targets.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from urllib.request import urlopen


REFERENCE_IDS = {0, 1, 2, 3}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8010/astra.mjpg")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--seconds", type=float, default=30.0)
    parser.add_argument("--max-samples", type=int, default=20)
    parser.add_argument("--sample-every-s", type=float, default=0.5)
    parser.add_argument("--min-save-interval-s", type=float, default=2.0)
    parser.add_argument("--stable-frames", type=int, default=3)
    parser.add_argument("--stable-diff", type=float, default=2.0)
    parser.add_argument("--novel-diff", type=float, default=3.0)
    parser.add_argument("--max-marker-shift-px", type=float, default=5.0)
    parser.add_argument("--crop-320", nargs=4, type=int, default=(128, 85, 215, 140))
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    x1, y1, x2, y2 = args.crop_320
    if not (0 <= x1 < x2 <= 320 and 0 <= y1 < y2 <= 240):
        raise ValueError("--crop-320 must be inside 320x240")
    if args.seconds <= 0 or args.max_samples < 1 or args.sample_every_s <= 0:
        raise ValueError("duration, sample interval and max samples must be positive")
    if args.min_save_interval_s < 0 or args.stable_frames < 2:
        raise ValueError("save interval must be non-negative; stable frames >= 2")
    if args.stable_diff < 0 or args.novel_diff <= args.stable_diff:
        raise ValueError("novel-diff must exceed stable-diff >= 0")
    if args.max_marker_shift_px <= 0:
        raise ValueError("max-marker-shift-px must be positive")
    if args.output.exists():
        raise ValueError("output already exists; review runs never overwrite data")


def iter_mjpeg_jpegs(response):
    """Read bounded JPEG parts using the preview service's Content-Length header."""
    while True:
        boundary = response.readline(256)
        if not boundary:
            return
        if not boundary.startswith(b"--frame"):
            continue
        headers = {}
        while True:
            line = response.readline(1024)
            if not line:
                return
            if line in (b"\r\n", b"\n"):
                break
            key, separator, value = line.partition(b":")
            if separator:
                headers[key.strip().lower()] = value.strip()
        length = int(headers.get(b"content-length", b"0"))
        if not 0 < length <= 5_000_000:
            raise ValueError("invalid MJPEG frame length")
        jpeg = response.read(length)
        if len(jpeg) != length:
            return
        yield jpeg


def marker_centers(frame, detector, cv2):
    found = {}
    for scale in (1, 2, 3):
        view = frame if scale == 1 else cv2.resize(
            frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR
        )
        corners, ids, _ = detector.detectMarkers(view)
        if ids is None:
            continue
        for corner, marker_id in zip(corners, ids.flatten()):
            marker_id = int(marker_id)
            if marker_id in REFERENCE_IDS and marker_id not in found:
                center = corner.reshape(4, 2).mean(axis=0) / scale
                found[marker_id] = tuple(float(value) for value in center)
        if set(found) == REFERENCE_IDS:
            break
    return found


def max_marker_shift(current, baseline) -> float:
    return max(
        ((current[marker_id][0] - baseline[marker_id][0]) ** 2
         + (current[marker_id][1] - baseline[marker_id][1]) ** 2) ** 0.5
        for marker_id in REFERENCE_IDS
    )


def difference(a, b, cv2) -> float:
    return float(cv2.absdiff(a, b).mean())


def main() -> int:
    args = parse_args()
    validate_args(args)
    import cv2
    import numpy as np

    detector = cv2.aruco.ArucoDetector(
        cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50),
        cv2.aruco.DetectorParameters(),
    )
    started = time.monotonic()
    deadline = started + args.seconds
    last_checked = float("-inf")
    last_saved = float("-inf")
    previous_roi = None
    steady_count = 0
    baseline_markers = None
    accepted_rois = []
    records = []
    counters = {"decoded": 0, "checked": 0, "missing_reference": 0,
                "marker_shift": 0, "unstable": 0, "duplicate": 0}
    crop = tuple(args.crop_320)
    x1, y1, x2, y2 = crop
    args.output.mkdir(parents=True)
    (args.output / "roi").mkdir()
    (args.output / "context").mkdir()
    (args.output / "roi_640").mkdir()
    (args.output / "context_640").mkdir()
    try:
        with urlopen(args.url, timeout=5) as response:
            if response.status != 200:
                raise RuntimeError(f"preview returned HTTP {response.status}")
            for jpeg in iter_mjpeg_jpegs(response):
                now = time.monotonic()
                if now >= deadline or len(records) >= args.max_samples:
                    break
                counters["decoded"] += 1
                if now - last_checked < args.sample_every_s:
                    continue
                last_checked = now
                frame = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
                if frame is None or frame.shape[:2] != (480, 640):
                    raise RuntimeError("Astra preview must be 640x480 BGR")
                counters["checked"] += 1
                centers = marker_centers(frame, detector, cv2)
                if set(centers) != REFERENCE_IDS:
                    counters["missing_reference"] += 1
                    previous_roi = None
                    steady_count = 0
                    continue
                if baseline_markers is None:
                    baseline_markers = centers
                shift = max_marker_shift(centers, baseline_markers)
                if shift > args.max_marker_shift_px:
                    counters["marker_shift"] += 1
                    previous_roi = None
                    steady_count = 0
                    continue
                small = cv2.resize(frame, (320, 240), interpolation=cv2.INTER_AREA)
                roi = small[y1:y2, x1:x2].copy()
                gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                if previous_roi is None:
                    steady_count = 1
                elif difference(gray, previous_roi, cv2) <= args.stable_diff:
                    steady_count += 1
                else:
                    steady_count = 1
                previous_roi = gray
                if steady_count < args.stable_frames:
                    counters["unstable"] += 1
                    continue
                if now - last_saved < args.min_save_interval_s:
                    continue
                min_difference = min(
                    (difference(gray, saved, cv2) for saved in accepted_rois),
                    default=None,
                )
                if min_difference is not None and min_difference < args.novel_diff:
                    counters["duplicate"] += 1
                    continue
                stem = f"candidate_{len(records) + 1:03d}"
                if not cv2.imwrite(str(args.output / "roi" / f"{stem}.png"), roi):
                    raise OSError("could not save ROI")
                if not cv2.imwrite(str(args.output / "context" / f"{stem}.png"), small):
                    raise OSError("could not save context")
                highres_roi = frame[y1 * 2:y2 * 2, x1 * 2:x2 * 2]
                if highres_roi.shape[:2] != ((y2 - y1) * 2, (x2 - x1) * 2):
                    raise RuntimeError("high-resolution ROI shape mismatch")
                if not cv2.imwrite(str(args.output / "roi_640" / f"{stem}.png"), highres_roi):
                    raise OSError("could not save high-resolution ROI")
                if not cv2.imwrite(str(args.output / "context_640" / f"{stem}.png"), frame):
                    raise OSError("could not save high-resolution context")
                accepted_rois.append(gray.copy())
                last_saved = now
                records.append({"stem": stem, "elapsed_s": round(now - started, 3),
                                "reference_marker_shift_px": round(shift, 3),
                                "min_roi_difference": None if min_difference is None else round(min_difference, 3),
                                "review_status": "pending_human_review", "label": None})
                print(f"CANDIDATE {stem} elapsed={now - started:.1f}s review=pending", flush=True)
    finally:
        manifest = {
            "source": args.url,
            "scope": "pickup_roi_only",
            "crop_xyxy_320px": list(crop),
            "preview_resolution": [640, 480],
            "roi_640_resolution": [(x2 - x1) * 2, (y2 - y1) * 2],
            "high_resolution_context_saved": True,
            "training_ready": False,
            "labels_generated": False,
            "robot_enabled": False,
            "note": "Distinct-looking camera frames only; duplicates and labels require human review. No depth or medicine identity verification.",
            "thresholds": {"stable_diff": args.stable_diff, "novel_diff": args.novel_diff,
                           "stable_frames": args.stable_frames,
                           "max_marker_shift_px": args.max_marker_shift_px},
            "counters": counters,
            "candidates": records,
        }
        (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        print(f"SUMMARY candidates={len(records)} checked={counters['checked']} "
              f"missing_reference={counters['missing_reference']} "
              f"marker_shift={counters['marker_shift']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
