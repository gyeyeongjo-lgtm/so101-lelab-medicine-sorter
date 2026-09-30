#!/usr/bin/env python3
"""Measure marked X centers in a saved Astra RGB frame without opening cameras.

This is camera-only QA. The output never authorizes robot motion.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_expected(value: str) -> tuple[str, tuple[float, float]]:
    name, x, y = value.split(",", 2)
    if not name:
        raise ValueError("point name must not be empty")
    return name, (float(x), float(y))


def marker_centers(image, cv2_module, np_module) -> dict[int, object]:
    aruco = cv2_module.aruco
    detector = aruco.ArucoDetector(
        aruco.getPredefinedDictionary(aruco.DICT_4X4_50), aruco.DetectorParameters()
    )
    gray = cv2_module.cvtColor(image, cv2_module.COLOR_BGR2GRAY)
    output = {}
    for candidate in (gray, cv2_module.equalizeHist(gray)):
        corners, ids, _ = detector.detectMarkers(candidate)
        if ids is None:
            continue
        for marker_id, marker_corners in zip(ids.flatten(), corners):
            output.setdefault(int(marker_id), np_module.asarray(marker_corners).reshape(4, 2).mean(axis=0))
    return output


def black_x_centroid(gray, expected: tuple[float, float], cv2_module, np_module, radius: int = 14):
    x, y = expected
    x0, x1 = max(0, round(x) - radius), min(gray.shape[1], round(x) + radius + 1)
    y0, y1 = max(0, round(y) - radius), min(gray.shape[0], round(y) + radius + 1)
    roi = gray[y0:y1, x0:x1]
    if roi.shape[0] < 10 or roi.shape[1] < 10:
        raise ValueError(f"X ROI near image boundary: {expected}")
    _, mask = cv2_module.threshold(roi, 0, 255, cv2_module.THRESH_BINARY_INV + cv2_module.THRESH_OTSU)
    count, _, stats, centroids = cv2_module.connectedComponentsWithStats(mask)
    candidates = []
    for index in range(1, count):
        left, top, width, height, area = [int(value) for value in stats[index]]
        if 15 <= area <= 400 and 5 <= width <= 25 and 5 <= height <= 25:
            center = np_module.asarray(centroids[index]) + np_module.asarray([x0, y0])
            if np_module.linalg.norm(center - np_module.asarray(expected)) <= radius:
                candidates.append((area, center))
    if not candidates:
        raise ValueError(f"no isolated black X component near {expected}")
    return max(candidates, key=lambda item: item[0])[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--point", action="append", required=True, help="NAME,X_PIXEL,Y_PIXEL; repeat per X")
    args = parser.parse_args()
    import cv2
    import numpy as np

    image = cv2.imread(str(args.image))
    if image is None:
        parser.error("image could not be decoded")
    markers = marker_centers(image, cv2, np)
    required = (0, 1, 2, 3)
    if not all(marker_id in markers for marker_id in required):
        parser.error(f"not all reference marker IDs detected: {sorted(markers)}")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    world = config["markers"]["reference_centers_mm"]
    image_points = np.asarray([markers[index] for index in required], dtype=np.float64)
    world_points = np.asarray([world[str(index)][:2] for index in required], dtype=np.float64)
    homography, _ = cv2.findHomography(image_points, world_points, method=0)
    if homography is None:
        parser.error("four-marker homography failed")
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    observations = {}
    for raw_point in args.point:
        name, expected = parse_expected(raw_point)
        center = black_x_centroid(gray, expected, cv2, np)
        projected = homography @ np.asarray([center[0], center[1], 1.0])
        observations[name] = {
            "pixel": center.tolist(),
            "world_mm": (projected[:2] / projected[2]).tolist(),
            "expected_pixel": list(expected),
        }
    distances = {}
    for first, second in (("P1", "P2"), ("P1", "P4")):
        if first in observations and second in observations:
            a = np.asarray(observations[first]["world_mm"])
            b = np.asarray(observations[second]["world_mm"])
            distances[f"{first}-{second}"] = float(np.linalg.norm(a - b))
    print(json.dumps({
        "status": "CAMERA_ONLY_SINGLE_FRAME_NOT_FOR_MOTION",
        "marker_pixels": {str(index): markers[index].tolist() for index in required},
        "points": observations,
        "distances_mm": distances,
        "robot_enabled": False,
        "motion_authorized": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
