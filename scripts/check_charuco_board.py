#!/usr/bin/env python3
"""Check ChArUco marker/corner visibility from one camera without robot access."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics


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
    parser.add_argument("--camera", default="/dev/video4")
    parser.add_argument("--frames", type=int, default=90)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--fourcc", default="MJPG", help="four-character V4L2 pixel format")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.frames < 1:
        parser.error("--frames must be at least 1")
    if len(args.fourcc) != 4:
        parser.error("--fourcc must contain exactly four characters")

    import cv2
    import numpy as np

    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    board_ids = np.arange(10, 34, dtype=np.int32)
    board = cv2.aruco.CharucoBoard((6, 8), 30.0, 22.0, dictionary, board_ids)
    charuco_detector = cv2.aruco.CharucoDetector(board)

    source = normalize_camera_source(args.camera)
    capture = cv2.VideoCapture(source, cv2.CAP_V4L2)
    capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*args.fourcc))
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    capture.set(cv2.CAP_PROP_FPS, 30)
    if not capture.isOpened():
        print(json.dumps({"status": "FAIL", "reason": "camera_open_failed", "camera": args.camera}))
        return 2

    marker_counts: list[int] = []
    corner_counts: list[int] = []
    captured = 0
    last_annotated = None
    try:
        for _ in range(args.frames):
            ok, frame = capture.read()
            if not ok:
                continue
            captured += 1
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            charuco_corners, charuco_ids, marker_corners, marker_ids = (
                charuco_detector.detectBoard(gray)
            )
            marker_count = 0
            if marker_ids is not None:
                marker_count = sum(int(value) in set(board_ids.tolist()) for value in marker_ids.flatten())
            corner_count = 0 if charuco_ids is None else len(charuco_ids)
            marker_counts.append(marker_count)
            corner_counts.append(corner_count)

            last_annotated = frame.copy()
            if marker_ids is not None:
                cv2.aruco.drawDetectedMarkers(last_annotated, marker_corners, marker_ids)
            if charuco_corners is not None and charuco_ids is not None:
                cv2.aruco.drawDetectedCornersCharuco(
                    last_annotated, charuco_corners, charuco_ids, (0, 0, 255)
                )
    finally:
        capture.release()

    if args.output and last_annotated is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(args.output), last_annotated)

    frames_with_12 = sum(count >= 12 for count in corner_counts)
    report = {
        "safety": "camera-only; no robot serial port opened",
        "camera": args.camera,
        "fourcc": args.fourcc,
        "captured_frames": captured,
        "requested_frames": args.frames,
        "marker_ids": [10, 33],
        "marker_count_max": max(marker_counts, default=0),
        "marker_count_mean": round(statistics.fmean(marker_counts), 3) if marker_counts else 0.0,
        "charuco_corner_count_max": max(corner_counts, default=0),
        "charuco_corner_count_mean": round(statistics.fmean(corner_counts), 3) if corner_counts else 0.0,
        "frames_with_at_least_12_corners": frames_with_12,
        "status": "PASS" if captured and frames_with_12 >= max(1, captured // 2) else "FAIL",
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
