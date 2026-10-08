#!/usr/bin/env python3
"""Post-hoc white-cap candidate check in the current fixed red basket.

This image-only diagnostic is calibrated on two saved C demonstrations. It is
not a completion verifier, a robot target, or a permission to move or replay.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np


def cap_components(image: np.ndarray, marker_center: tuple[float, float]) -> list[dict]:
    """Find large low-saturation cap-like blobs above ID4's marker board."""
    if image.shape[:2] != (480, 640):
        raise ValueError("expected 640x480 ceiling image")
    cx, cy = marker_center
    x1, x2 = round(cx - 30), round(cx + 28)
    y1, y2 = round(cy - 82), round(cy - 22)
    if not (0 <= x1 < x2 <= 640 and 0 <= y1 < y2 <= 480):
        raise ValueError("red basket diagnostic ROI outside image")
    hsv = cv2.cvtColor(image[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    white = cv2.inRange(hsv, np.array([0, 0, 125], np.uint8),
                        np.array([179, 80, 255], np.uint8))
    _, _, stats, _ = cv2.connectedComponentsWithStats(white)
    candidates = []
    for x, y, width, height, area in stats[1:]:
        if (area >= 300 and 15 <= width <= 45 and 18 <= height <= 40
                and y + height < y2 - y1 - 10):
            candidates.append({"area_px": int(area),
                               "bbox_xywh_px": [int(x + x1), int(y + y1),
                                                int(width), int(height)]})
    return sorted(candidates, key=lambda row: row["area_px"], reverse=True)


def id4_center(image: np.ndarray) -> tuple[float, float] | None:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    detector = cv2.aruco.ArucoDetector(
        cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50),
        cv2.aruco.DetectorParameters())
    corners, ids, _ = detector.detectMarkers(gray)
    if ids is None:
        return None
    for corner, marker_id in zip(corners, ids.flatten()):
        if int(marker_id) == 4:
            center = corner.reshape(4, 2).mean(axis=0)
            return float(center[0]), float(center[1])
    return None


def audit_frames(paths: list[Path], window: int = 20) -> dict:
    if not paths or window < 1 or len(paths) < 2 * window:
        raise ValueError("need nonempty frames and disjoint first/last windows")
    rows = []
    for path in paths:
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None or image.shape[:2] != (480, 640):
            raise ValueError(f"missing or wrong-sized ceiling frame: {path}")
        center = id4_center(image)
        candidates = [] if center is None else cap_components(image, center)
        rows.append({"marker_present": center is not None,
                     "candidate": bool(candidates),
                     "largest_area_px": None if not candidates else candidates[0]["area_px"]})
    first, last = rows[:window], rows[-window:]
    return {
        "status": "POSTHOC_CAP_CANDIDATE_DIAGNOSTIC",
        "frame_count": len(rows), "window_size": window,
        "id4_detected_frames": sum(row["marker_present"] for row in rows),
        "first_window_candidate_frames": sum(row["candidate"] for row in first),
        "last_window_candidate_frames": sum(row["candidate"] for row in last),
        "first_window_marker_frames": sum(row["marker_present"] for row in first),
        "last_window_marker_frames": sum(row["marker_present"] for row in last),
        "robot_enabled": False, "motion_authorized": False,
        "completion_verified": False,
        "warning": "Post-hoc two-scene HSV/shape heuristic; no independent performance or 3D clearance validation",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace-dir", type=Path, required=True)
    parser.add_argument("--window", type=int, default=20)
    args = parser.parse_args()
    paths = sorted((args.trace_dir / "ceiling").glob("*.jpg"))
    try:
        result = audit_frames(paths, args.window)
    except (OSError, ValueError) as error:
        parser.exit(2, f"cap diagnostic failed: {error}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
