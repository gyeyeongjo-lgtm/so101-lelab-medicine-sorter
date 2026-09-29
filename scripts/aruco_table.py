#!/usr/bin/env python3
"""Detect four ArUco markers and map image pixels onto a flat table plane.

Safety boundary: this process only reads an image file or one camera. It never
imports LeRobot, opens a serial port, changes torque, or controls a robot.
"""

from __future__ import annotations

import argparse
from collections import deque
import json
import math
from pathlib import Path
import sys
import time
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--image", type=Path, help="Process one image instead of opening a camera")
    source.add_argument("--camera", help="Override camera device/index from the config")
    parser.add_argument("--output", type=Path, help="Write the last annotated frame")
    parser.add_argument("--display", action="store_true", help="Show a local OpenCV window; q/Esc exits")
    parser.add_argument("--max-frames", type=int, default=0, help="0 runs until interrupted")
    parser.add_argument("--json-every", type=int, default=30)
    parser.add_argument("--stability-window", type=int, default=30)
    return parser.parse_args()


def _is_non_collinear(points: list[tuple[float, float]]) -> bool:
    for first in range(len(points) - 2):
        ax, ay = points[first]
        for second in range(first + 1, len(points) - 1):
            bx, by = points[second]
            for third in range(second + 1, len(points)):
                cx, cy = points[third]
                area2 = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
                if abs(area2) > 1e-9:
                    return True
    return False


def load_config(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Config root must be an object")
    dictionary = data.get("dictionary")
    if not isinstance(dictionary, str) or not dictionary.startswith("DICT_"):
        raise ValueError("dictionary must be an OpenCV ArUco dictionary name")
    marker_size = data.get("marker_size_mm")
    if not isinstance(marker_size, (int, float)) or marker_size <= 0:
        raise ValueError("marker_size_mm must be positive")

    raw_centers = data.get("marker_centers_mm")
    if not isinstance(raw_centers, dict) or len(raw_centers) < 4:
        raise ValueError("marker_centers_mm must contain at least four marker IDs")
    centers: dict[int, tuple[float, float]] = {}
    for raw_id, raw_point in raw_centers.items():
        try:
            marker_id = int(raw_id)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid marker ID: {raw_id!r}") from exc
        if marker_id < 0 or marker_id in centers:
            raise ValueError(f"Invalid or duplicate marker ID: {raw_id!r}")
        if not isinstance(raw_point, list) or len(raw_point) != 2:
            raise ValueError(f"Marker {marker_id} coordinate must be [x_mm, y_mm]")
        try:
            point = (float(raw_point[0]), float(raw_point[1]))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Marker {marker_id} coordinate is not numeric") from exc
        if not all(math.isfinite(value) for value in point):
            raise ValueError(f"Marker {marker_id} coordinate must be finite")
        centers[marker_id] = point
    if len(set(centers.values())) != len(centers):
        raise ValueError("Marker center coordinates must be unique")
    if not _is_non_collinear(list(centers.values())):
        raise ValueError("Marker center coordinates must not be collinear")

    camera = data.get("camera")
    if not isinstance(camera, dict):
        raise ValueError("camera must be an object")
    for field in ("width", "height", "fps"):
        if not isinstance(camera.get(field), (int, float)) or camera[field] <= 0:
            raise ValueError(f"camera.{field} must be positive")
    if not isinstance(camera.get("device"), (str, int)):
        raise ValueError("camera.device must be a path or integer index")
    fourcc = camera.get("fourcc", "MJPG")
    if not isinstance(fourcc, str) or len(fourcc) != 4:
        raise ValueError("camera.fourcc must contain exactly four characters")
    camera["fourcc"] = fourcc

    data["marker_size_mm"] = float(marker_size)
    data["marker_centers_mm"] = centers
    return data


def load_calibration(path: Path | None, np_module) -> tuple[Any, Any] | None:
    if path is None:
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    matrix = np_module.asarray(raw.get("camera_matrix"), dtype=np_module.float64)
    distortion = np_module.asarray(raw.get("dist_coeffs"), dtype=np_module.float64)
    if matrix.shape != (3, 3) or distortion.size < 4:
        raise ValueError("Calibration requires camera_matrix 3x3 and at least four dist_coeffs")
    return matrix, distortion.reshape(-1, 1)


def normalize_camera_source(value: Any) -> Any:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        if value.isdecimal():
            return int(value)
        # Some Linux OpenCV/V4L2 builds reject a device path string while
        # accepting the equivalent numeric camera index.
        prefix = "/dev/video"
        if value.startswith(prefix) and value[len(prefix) :].isdecimal():
            return int(value[len(prefix) :])
    return str(value)


def create_detector(cv2_module, dictionary_name: str):
    dictionary_id = getattr(cv2_module.aruco, dictionary_name, None)
    if dictionary_id is None:
        raise ValueError(f"Unknown ArUco dictionary: {dictionary_name}")
    dictionary = cv2_module.aruco.getPredefinedDictionary(dictionary_id)
    parameters = cv2_module.aruco.DetectorParameters()
    parameters.cornerRefinementMethod = cv2_module.aruco.CORNER_REFINE_SUBPIX
    return cv2_module.aruco.ArucoDetector(dictionary, parameters)


def calculate_homography(cv2_module, np_module, corners, ids, table_points):
    if ids is None:
        return None, None
    detected = {int(marker_id): marker_corners for marker_id, marker_corners in zip(ids.flatten(), corners)}
    common_ids = sorted(set(detected).intersection(table_points))
    if len(common_ids) < 4:
        return None, None
    image_points = np_module.asarray(
        [detected[marker_id].reshape(4, 2).mean(axis=0) for marker_id in common_ids],
        dtype=np_module.float64,
    )
    destination = np_module.asarray([table_points[marker_id] for marker_id in common_ids], dtype=np_module.float64)
    homography, _ = cv2_module.findHomography(image_points, destination, method=0)
    if homography is None:
        return None, None
    projected = cv2_module.perspectiveTransform(image_points.reshape(-1, 1, 2), homography).reshape(-1, 2)
    rms = float(np_module.sqrt(np_module.mean(np_module.sum((projected - destination) ** 2, axis=1))))
    return homography, rms


def transform_point(cv2_module, np_module, homography, point: tuple[float, float]) -> tuple[float, float]:
    source = np_module.asarray([[point]], dtype=np_module.float64)
    transformed = cv2_module.perspectiveTransform(source, homography)[0, 0]
    return float(transformed[0]), float(transformed[1])


def draw_table_grid(cv2_module, np_module, image, homography, table_points) -> None:
    inverse = np_module.linalg.inv(homography)
    xs = [point[0] for point in table_points.values()]
    ys = [point[1] for point in table_points.values()]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    for index in range(6):
        ratio = index / 5
        x = min_x + ratio * (max_x - min_x)
        y = min_y + ratio * (max_y - min_y)
        segments = [((x, min_y), (x, max_y)), ((min_x, y), (max_x, y))]
        for first, second in segments:
            table_line = np_module.asarray([[first, second]], dtype=np_module.float64)
            image_line = cv2_module.perspectiveTransform(table_line, inverse)[0]
            p1 = tuple(int(round(value)) for value in image_line[0])
            p2 = tuple(int(round(value)) for value in image_line[1])
            cv2_module.line(image, p1, p2, (80, 180, 80), 1, cv2_module.LINE_AA)


def estimate_poses(cv2_module, np_module, corners, ids, marker_size_mm, calibration):
    if calibration is None or ids is None:
        return []
    half = marker_size_mm / 2.0
    object_points = np_module.asarray(
        [[-half, half, 0.0], [half, half, 0.0], [half, -half, 0.0], [-half, -half, 0.0]],
        dtype=np_module.float32,
    )
    matrix, distortion = calibration
    poses = []
    for marker_id, marker_corners in zip(ids.flatten(), corners):
        ok, rotation, translation = cv2_module.solvePnP(
            object_points,
            marker_corners.reshape(4, 2).astype(np_module.float32),
            matrix,
            distortion,
            flags=cv2_module.SOLVEPNP_IPPE_SQUARE,
        )
        if ok:
            poses.append((int(marker_id), rotation, translation))
    return poses


def analyze_frame(cv2_module, np_module, detector, frame, config, calibration, stability_history):
    analysis_frame = frame
    pose_calibration = calibration
    if calibration is not None:
        matrix, distortion = calibration
        analysis_frame = cv2_module.undistort(frame, matrix, distortion, None, matrix)
        pose_calibration = (matrix, np_module.zeros_like(distortion))

    grayscale = cv2_module.cvtColor(analysis_frame, cv2_module.COLOR_BGR2GRAY)
    corners, ids, rejected = detector.detectMarkers(grayscale)
    annotated = analysis_frame.copy()
    if ids is not None:
        cv2_module.aruco.drawDetectedMarkers(annotated, corners, ids)
    homography, rms = calculate_homography(
        cv2_module, np_module, corners, ids, config["marker_centers_mm"]
    )
    height, width = analysis_frame.shape[:2]
    camera_center_mm = None
    jitter_mm = None
    marker_centers_projected_table_mm = {}
    if homography is not None:
        draw_table_grid(cv2_module, np_module, annotated, homography, config["marker_centers_mm"])
        camera_center_mm = transform_point(cv2_module, np_module, homography, (width / 2.0, height / 2.0))
        stability_history.append(camera_center_mm)
        if len(stability_history) >= 2:
            history = np_module.asarray(stability_history, dtype=np_module.float64)
            jitter_mm = float(np_module.sqrt(np_module.mean(np_module.sum((history - history.mean(axis=0)) ** 2, axis=1))))
        cv2_module.drawMarker(
            annotated, (width // 2, height // 2), (0, 255, 255), cv2_module.MARKER_CROSS, 16, 2
        )
        if ids is not None:
            for marker_id, marker_corners in zip(ids.flatten(), corners):
                marker_center = marker_corners.reshape(4, 2).mean(axis=0)
                marker_centers_projected_table_mm[str(int(marker_id))] = transform_point(
                    cv2_module,
                    np_module,
                    homography,
                    (float(marker_center[0]), float(marker_center[1])),
                )

    poses = estimate_poses(
        cv2_module,
        np_module,
        corners,
        ids,
        config["marker_size_mm"],
        pose_calibration,
    )
    if calibration is not None:
        matrix, distortion = pose_calibration
        for _, rotation, translation in poses:
            cv2_module.drawFrameAxes(
                annotated, matrix, distortion, rotation, translation, config["marker_size_mm"] * 0.5
            )

    detected_ids = [] if ids is None else [int(value) for value in ids.flatten()]
    status = {
        "timestamp": time.time(),
        "detected_ids": detected_ids,
        "rejected_candidates": len(rejected),
        "required_ids": sorted(config["marker_centers_mm"]),
        "homography_ready": homography is not None,
        "homography_rms_mm": rms,
        "frame_center_table_mm": camera_center_mm,
        "frame_center_jitter_mm": jitter_mm,
        "marker_centers_projected_table_mm": marker_centers_projected_table_mm,
        "stability_samples": len(stability_history),
        "pose_ready": calibration is not None and len(poses) > 0,
        "pose_ids": [marker_id for marker_id, _, _ in poses],
    }
    lines = [f"IDs: {detected_ids}"]
    if camera_center_mm is not None:
        lines.append(f"center: x={camera_center_mm[0]:.1f} y={camera_center_mm[1]:.1f} mm")
    if jitter_mm is not None:
        lines.append(f"stability RMS: {jitter_mm:.2f} mm / {len(stability_history)} frames")
    if calibration is None:
        lines.append("pose: unavailable (no camera calibration)")
    for row, line in enumerate(lines):
        cv2_module.putText(
            annotated,
            line,
            (12, 26 + row * 24),
            cv2_module.FONT_HERSHEY_SIMPLEX,
            0.55,
            (20, 20, 20),
            3,
            cv2_module.LINE_AA,
        )
        cv2_module.putText(
            annotated,
            line,
            (12, 26 + row * 24),
            cv2_module.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            1,
            cv2_module.LINE_AA,
        )
    return annotated, status


def process_image(cv2_module, np_module, args, config, detector, calibration) -> int:
    frame = cv2_module.imread(str(args.image), cv2_module.IMREAD_COLOR)
    if frame is None:
        raise RuntimeError(f"Could not read image: {args.image}")
    annotated, status = analyze_frame(
        cv2_module, np_module, detector, frame, config, calibration, deque(maxlen=args.stability_window)
    )
    print(json.dumps(status, ensure_ascii=False, sort_keys=True))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        if not cv2_module.imwrite(str(args.output), annotated):
            raise RuntimeError(f"Could not write output image: {args.output}")
    if args.display:
        cv2_module.imshow("ArUco table", annotated)
        cv2_module.waitKey(0)
        cv2_module.destroyAllWindows()
    return 0 if status["homography_ready"] else 2


def process_camera(cv2_module, np_module, args, config, detector, calibration) -> int:
    source = normalize_camera_source(args.camera if args.camera is not None else config["camera"]["device"])
    backend = cv2_module.CAP_V4L2 if sys.platform.startswith("linux") else cv2_module.CAP_ANY
    capture = cv2_module.VideoCapture(source, backend)
    capture.set(cv2_module.CAP_PROP_FRAME_WIDTH, config["camera"]["width"])
    capture.set(cv2_module.CAP_PROP_FRAME_HEIGHT, config["camera"]["height"])
    capture.set(cv2_module.CAP_PROP_FPS, config["camera"]["fps"])
    capture.set(
        cv2_module.CAP_PROP_FOURCC,
        cv2_module.VideoWriter_fourcc(*config["camera"]["fourcc"]),
    )
    if not capture.isOpened():
        raise RuntimeError(f"Could not open camera: {source}")

    history = deque(maxlen=args.stability_window)
    marker_histories: dict[str, list[tuple[float, float]]] = {}
    frame_count = 0
    read_failures = 0
    ever_ready = False
    last_annotated = None
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                read_failures += 1
                if read_failures >= 10:
                    raise RuntimeError("Camera returned 10 consecutive read failures")
                continue
            read_failures = 0
            frame_count += 1
            last_annotated, status = analyze_frame(
                cv2_module, np_module, detector, frame, config, calibration, history
            )
            ever_ready = ever_ready or status["homography_ready"]
            for marker_id, point in status["marker_centers_projected_table_mm"].items():
                marker_histories.setdefault(marker_id, []).append(point)
            if frame_count == 1 or frame_count % args.json_every == 0:
                print(json.dumps(status, ensure_ascii=False, sort_keys=True), flush=True)
            if args.display:
                cv2_module.imshow("ArUco table", last_annotated)
                key = cv2_module.waitKey(1) & 0xFF
                if key in (27, ord("q")):
                    break
            if args.max_frames > 0 and frame_count >= args.max_frames:
                break
    except KeyboardInterrupt:
        pass
    finally:
        capture.release()
        if args.display:
            cv2_module.destroyAllWindows()
    if args.output and last_annotated is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        if not cv2_module.imwrite(str(args.output), last_annotated):
            raise RuntimeError(f"Could not write output image: {args.output}")
    marker_summary = {}
    for marker_id, points in sorted(marker_histories.items(), key=lambda item: int(item[0])):
        values = np_module.asarray(points, dtype=np_module.float64)
        mean = values.mean(axis=0)
        jitter = float(
            np_module.sqrt(np_module.mean(np_module.sum((values - mean) ** 2, axis=1)))
        )
        marker_summary[marker_id] = {
            "samples": len(points),
            "mean_projected_table_mm": [float(mean[0]), float(mean[1])],
            "jitter_mm": jitter,
        }
    print(
        json.dumps(
            {"type": "final_marker_summary", "markers": marker_summary},
            ensure_ascii=False,
            sort_keys=True,
        ),
        flush=True,
    )
    return 0 if ever_ready else 2


def main() -> int:
    args = parse_args()
    if args.max_frames < 0 or args.json_every < 1 or args.stability_window < 2:
        raise SystemExit("max-frames >= 0, json-every >= 1, and stability-window >= 2 are required")
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise SystemExit("OpenCV with cv2.aruco and NumPy are required") from exc
    if not hasattr(cv2, "aruco"):
        raise SystemExit("This OpenCV build does not include cv2.aruco")

    config = load_config(args.config)
    detector = create_detector(cv2, config["dictionary"])
    calibration_path = config.get("calibration_file")
    calibration = load_calibration(
        None if calibration_path is None else (args.config.parent / calibration_path).resolve(), np
    )
    if args.image:
        return process_image(cv2, np, args, config, detector, calibration)
    return process_camera(cv2, np, args, config, detector, calibration)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
