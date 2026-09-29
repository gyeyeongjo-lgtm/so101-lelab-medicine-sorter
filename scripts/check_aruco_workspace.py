#!/usr/bin/env python3
"""Read one camera and report ArUco visibility; never opens robot serial ports.

Use this on the Jetson only after the printed markers are placed.  It opens the
specified V4L2 camera read-only through OpenCV and does not connect to LeLab,
the leader, or the follower arm.
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


def parse_ids(values: list[str]) -> list[int]:
    ids: list[int] = []
    for value in values:
        ids.extend(int(part) for part in value.split(",") if part)
    if not ids or any(marker_id < 0 or marker_id >= 50 for marker_id in ids):
        raise ValueError("expected IDs must be non-empty values in [0, 49]")
    return sorted(set(ids))


def build_detector(cv2: object) -> object:
    aruco = cv2.aruco
    dictionary = aruco.getPredefinedDictionary(aruco.DICT_4X4_50)
    if hasattr(aruco, "ArucoDetector"):
        return aruco.ArucoDetector(dictionary, aruco.DetectorParameters())
    return (dictionary, aruco.DetectorParameters_create())


def detect_ids(cv2: object, detector: object, frame: Any) -> list[int]:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    if isinstance(detector, tuple):
        corners, ids, _ = cv2.aruco.detectMarkers(gray, *detector)
    else:
        corners, ids, _ = detector.detectMarkers(gray)
    if ids is None:
        return []
    return [int(marker_id) for marker_id in ids.flatten()]


def normalize_camera_source(value: str | int) -> str | int:
    if isinstance(value, int):
        return value
    if value.isdecimal():
        return int(value)
    prefix = "/dev/video"
    if value.startswith(prefix) and value[len(prefix) :].isdecimal():
        return int(value[len(prefix) :])
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--camera", default="/dev/video0", help="V4L2 node; default: /dev/video0")
    parser.add_argument("--expected", nargs="+", default=["0,1,2,3"], help="marker IDs, comma-separated allowed")
    parser.add_argument("--frames", type=int, default=90, help="number of frames to sample")
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--fourcc", default="MJPG", help="four-character V4L2 pixel format")
    parser.add_argument("--calibration", type=Path, help="Optional intrinsic calibration JSON")
    args = parser.parse_args()

    if args.frames < 1:
        parser.error("--frames must be at least 1")
    if len(args.fourcc) != 4:
        parser.error("--fourcc must contain exactly four characters")
    try:
        expected = parse_ids(args.expected)
    except ValueError as exc:
        parser.error(str(exc))

    import cv2
    import numpy as np

    calibration = None
    if args.calibration:
        raw = json.loads(args.calibration.read_text(encoding="utf-8"))
        matrix = np.asarray(raw["camera_matrix"], dtype=np.float64)
        distortion = np.asarray(raw["dist_coeffs"], dtype=np.float64)
        calibration = (matrix, distortion)

    camera_source = normalize_camera_source(args.camera)
    cap = cv2.VideoCapture(camera_source, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*args.fourcc))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    cap.set(cv2.CAP_PROP_FPS, 30)
    if not cap.isOpened():
        print(json.dumps({"safety": "camera-only; no robot serial port opened", "status": "FAIL", "reason": "camera_open_failed", "camera": args.camera}, indent=2))
        return 2

    detector = build_detector(cv2)
    seen = Counter()
    captured = 0
    started = time.monotonic()
    try:
        for _ in range(args.frames):
            ok, frame = cap.read()
            if not ok:
                continue
            captured += 1
            if calibration is not None:
                matrix, distortion = calibration
                frame = cv2.undistort(frame, matrix, distortion, None, matrix)
            seen.update(detect_ids(cv2, detector, frame))
    finally:
        cap.release()

    missing = [marker_id for marker_id in expected if seen[marker_id] == 0]
    report = {
        "safety": "camera-only; no robot serial port opened",
        "camera": args.camera,
        "fourcc": args.fourcc,
        "requested_frames": args.frames,
        "captured_frames": captured,
        "elapsed_s": round(time.monotonic() - started, 3),
        "dictionary": "DICT_4X4_50",
        "undistorted": calibration is not None,
        "expected_ids": expected,
        "seen_counts": {str(marker_id): seen[marker_id] for marker_id in expected},
        "missing_ids": missing,
        "status": "PASS" if captured and not missing else "FAIL",
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
