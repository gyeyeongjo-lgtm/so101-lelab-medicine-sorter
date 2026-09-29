#!/usr/bin/env python3
"""Recalculate ChArUco intrinsics from saved views and reject high-error views."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--calibration-out", type=Path, required=True)
    parser.add_argument("--camera", required=True)
    parser.add_argument("--fourcc", required=True)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--min-corners", type=int, default=12)
    parser.add_argument("--max-view-rms", type=float, default=1.0)
    args = parser.parse_args()

    import cv2
    import numpy as np

    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    marker_ids = np.arange(10, 34, dtype=np.int32)
    board = cv2.aruco.CharucoBoard((6, 8), 30.0, 22.0, dictionary, marker_ids)
    detector = cv2.aruco.CharucoDetector(board)
    board_corners = board.getChessboardCorners().astype(np.float32)

    object_points = []
    image_points = []
    corner_counts = []
    filenames = []
    for path in sorted(args.input_dir.glob("*.jpg")):
        frame = cv2.imread(str(path))
        if frame is None or frame.shape[:2] != (args.height, args.width):
            continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        charuco_corners, charuco_ids, _, _ = detector.detectBoard(gray)
        if charuco_ids is None or len(charuco_ids) < args.min_corners:
            continue
        ids = charuco_ids.reshape(-1).astype(np.int32)
        points = charuco_corners.reshape(-1, 1, 2).astype(np.float32)
        object_points.append(board_corners[ids].copy())
        image_points.append(points.copy())
        corner_counts.append(len(ids))
        filenames.append(path.name)

    if len(image_points) < 10:
        raise RuntimeError(f"Only {len(image_points)} usable views; need at least 10")

    def calculate():
        rms, matrix, distortion, rotations, translations = cv2.calibrateCamera(
            object_points,
            image_points,
            (args.width, args.height),
            None,
            None,
        )
        per_view = []
        for objects, images, rotation, translation in zip(
            object_points, image_points, rotations, translations
        ):
            projected, _ = cv2.projectPoints(objects, rotation, translation, matrix, distortion)
            difference = images.reshape(-1, 2) - projected.reshape(-1, 2)
            per_view.append(float(math.sqrt(np.mean(np.sum(difference * difference, axis=1)))))
        return rms, matrix, distortion, per_view

    rejected = []
    while True:
        rms, camera_matrix, distortion, per_view_rms = calculate()
        worst = int(np.argmax(per_view_rms))
        if per_view_rms[worst] <= args.max_view_rms or len(image_points) <= 10:
            break
        rejected.append({"filename": filenames[worst], "rms_px": per_view_rms[worst]})
        for values in (object_points, image_points, corner_counts, filenames):
            values.pop(worst)

    calibration = {
        "camera": args.camera,
        "fourcc": args.fourcc,
        "image_size": [args.width, args.height],
        "camera_matrix": camera_matrix.tolist(),
        "dist_coeffs": distortion.reshape(-1).tolist(),
        "reprojection_rms_px": float(rms),
        "per_view_rms_px": per_view_rms,
        "per_view_rms_mean_px": float(np.mean(per_view_rms)),
        "per_view_rms_max_px": float(np.max(per_view_rms)),
        "captured_views": len(image_points) + len(rejected),
        "accepted_views": len(image_points),
        "accepted_filenames": filenames,
        "rejected_views": rejected,
        "corners_per_view": corner_counts,
        "outlier_rule": {"max_view_rms_px": args.max_view_rms},
        "board": {
            "dictionary": "DICT_4X4_50",
            "squares": [6, 8],
            "square_length_mm": 30.0,
            "marker_length_mm": 22.0,
            "marker_ids": [10, 33],
        },
    }
    args.calibration_out.parent.mkdir(parents=True, exist_ok=True)
    args.calibration_out.write_text(
        json.dumps(calibration, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(calibration, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(1)
