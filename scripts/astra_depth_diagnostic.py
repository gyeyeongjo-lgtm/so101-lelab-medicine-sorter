#!/usr/bin/env python3
"""Camera-only Astra RGB/depth alignment and ArUco depth diagnostic.

This tool never imports LeRobot, opens a robot serial port, changes torque, or
sends a motion command. OpenNI registers depth pixels into the color frame.
All geometric and depth values use millimetres.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import select
import statistics
import struct
import subprocess
import time
from typing import Any


HEADER = struct.Struct("<4sIIQQ")


def read_exact(stream: Any, size: int) -> bytes | None:
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        chunk = stream.read(remaining)
        if not chunk:
            return None
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def read_frame_header(stream: Any) -> bytes | None:
    """Skip any startup text until the first RGBD protocol magic."""
    window = bytearray()
    while True:
        value = stream.read(1)
        if not value:
            return None
        window += value
        if len(window) > 4:
            del window[0]
        if bytes(window) == b"RGBD":
            remainder = read_exact(stream, HEADER.size - 4)
            return None if remainder is None else b"RGBD" + remainder


def openni_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment["OPENNI2_REDIST"] = "/opt/orbbec-openni2"
    old_library_path = environment.get("LD_LIBRARY_PATH")
    environment["LD_LIBRARY_PATH"] = "/opt/orbbec-openni2" + (
        f":{old_library_path}" if old_library_path else ""
    )
    return environment


def median_depth_roi(
    depth: Any,
    u: float,
    v: float,
    radius: int,
    min_depth_mm: int,
    max_depth_mm: int,
) -> tuple[float | None, int, int]:
    import numpy as np

    x = int(round(u))
    y = int(round(v))
    y0 = max(0, y - radius)
    y1 = min(depth.shape[0], y + radius + 1)
    x0 = max(0, x - radius)
    x1 = min(depth.shape[1], x + radius + 1)
    roi = depth[y0:y1, x0:x1]
    valid = roi[(roi >= min_depth_mm) & (roi <= max_depth_mm)]
    if valid.size == 0:
        return None, 0, int(roi.size)
    return float(np.median(valid)), int(valid.size), int(roi.size)


def load_calibration(path: Path, np_module: Any) -> tuple[Any, Any, tuple[int, int]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    matrix = np_module.asarray(raw.get("camera_matrix"), dtype=np_module.float64)
    distortion = np_module.asarray(raw.get("dist_coeffs"), dtype=np_module.float64).reshape(-1, 1)
    if matrix.shape != (3, 3) or distortion.size < 4:
        raise ValueError("calibration requires camera_matrix 3x3 and at least four dist_coeffs")
    if not np_module.isfinite(matrix).all() or not np_module.isfinite(distortion).all():
        raise ValueError("calibration values must be finite")
    image_size_raw = raw.get("image_size", [640, 480])
    if not isinstance(image_size_raw, list) or len(image_size_raw) != 2:
        raise ValueError("calibration image_size must be [width,height]")
    image_size = (int(image_size_raw[0]), int(image_size_raw[1]))
    if image_size[0] <= 0 or image_size[1] <= 0:
        raise ValueError("calibration image_size must be positive")
    return matrix, distortion, image_size


def scale_camera_matrix(
    np_module: Any,
    camera_matrix: Any,
    source_size: tuple[int, int],
    target_size: tuple[int, int],
) -> Any:
    if source_size == target_size:
        return np_module.asarray(camera_matrix, dtype=np_module.float64).copy()
    scale_x = target_size[0] / source_size[0]
    scale_y = target_size[1] / source_size[1]
    scaled = np_module.asarray(camera_matrix, dtype=np_module.float64).copy()
    scaled[0, 0] *= scale_x
    scaled[0, 2] *= scale_x
    scaled[1, 1] *= scale_y
    scaled[1, 2] *= scale_y
    return scaled


def detect_markers_multiscale(cv2_module: Any, np_module: Any, detector: Any, bgr: Any):
    gray = cv2_module.cvtColor(bgr, cv2_module.COLOR_BGR2GRAY)
    corners, ids, rejected = detector.detectMarkers(gray)
    if bgr.shape[1] > 320:
        return corners, ids, rejected
    enlarged = cv2_module.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2_module.INTER_CUBIC)
    large_corners, large_ids, large_rejected = detector.detectMarkers(enlarged)
    merged: dict[int, Any] = {}
    if ids is not None:
        for marker_corners, marker_id in zip(corners, ids.flatten()):
            merged[int(marker_id)] = marker_corners
    if large_ids is not None:
        for marker_corners, marker_id in zip(large_corners, large_ids.flatten()):
            merged.setdefault(int(marker_id), marker_corners / 2.0)
    if not merged:
        return [], None, [*rejected, *large_rejected]
    ordered_ids = sorted(merged)
    merged_corners = [merged[marker_id] for marker_id in ordered_ids]
    merged_ids = np_module.asarray(ordered_ids, dtype=np_module.int32).reshape(-1, 1)
    return merged_corners, merged_ids, [*rejected, *large_rejected]


def load_reference_centers(path: Path) -> dict[int, tuple[float, float, float]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    marker_config = raw.get("markers", {})
    centers_raw = marker_config.get("reference_centers_mm")
    if not isinstance(centers_raw, dict) or len(centers_raw) < 4:
        raise ValueError("markers.reference_centers_mm must contain at least four IDs")
    centers: dict[int, tuple[float, float, float]] = {}
    for raw_id, raw_point in centers_raw.items():
        marker_id = int(raw_id)
        if not isinstance(raw_point, list) or len(raw_point) not in (2, 3):
            raise ValueError(f"reference marker {marker_id} must be [x,y] or [x,y,z]")
        values = [float(value) for value in raw_point]
        if len(values) == 2:
            values.append(0.0)
        if not all(math.isfinite(value) for value in values):
            raise ValueError(f"reference marker {marker_id} coordinates must be finite")
        centers[marker_id] = (values[0], values[1], values[2])
    return centers


def load_marker_sizes(path: Path) -> tuple[float, dict[int, float]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    marker_config = raw.get("markers", {})
    default_size = marker_config.get("marker_size_mm")
    if not isinstance(default_size, (int, float)) or not math.isfinite(default_size):
        raise ValueError("markers.marker_size_mm must be a finite positive number")
    default_size = float(default_size)
    if default_size <= 0:
        raise ValueError("markers.marker_size_mm must be a finite positive number")
    overrides_raw = marker_config.get("marker_size_by_id_mm", {})
    if not isinstance(overrides_raw, dict):
        raise ValueError("markers.marker_size_by_id_mm must be an object")
    overrides: dict[int, float] = {}
    for raw_id, raw_size in overrides_raw.items():
        if not isinstance(raw_size, (int, float)) or not math.isfinite(raw_size):
            raise ValueError(f"marker size override {raw_id} must be finite and positive")
        size = float(raw_size)
        if size <= 0:
            raise ValueError(f"marker size override {raw_id} must be finite and positive")
        overrides[int(raw_id)] = size
    return default_size, overrides


def estimate_single_marker_pnp_z(
    cv2_module: Any,
    np_module: Any,
    marker_corners: Any,
    marker_size_mm: float,
    camera_matrix: Any,
    distortion: Any,
) -> float | None:
    half = marker_size_mm / 2.0
    object_points = np_module.asarray(
        [
            [-half, half, 0.0],
            [half, half, 0.0],
            [half, -half, 0.0],
            [-half, -half, 0.0],
        ],
        dtype=np_module.float64,
    )
    image_points = np_module.asarray(marker_corners, dtype=np_module.float64).reshape(4, 2)
    flag = getattr(
        cv2_module,
        "SOLVEPNP_IPPE_SQUARE",
        cv2_module.SOLVEPNP_ITERATIVE,
    )
    ok, _, translation = cv2_module.solvePnP(
        object_points,
        image_points,
        camera_matrix,
        distortion,
        flags=flag,
    )
    if not ok:
        return None
    return float(np_module.asarray(translation).reshape(3)[2])


def deproject_registered_pixel(
    np_module: Any,
    u: float,
    v: float,
    depth_mm: float,
    camera_matrix: Any,
    distortion: Any | None = None,
    cv2_module: Any | None = None,
) -> Any:
    """Deproject a depth-to-color registered pixel using the calibrated RGB ray.

    OpenNI registration places the depth sample on the RGB pixel grid. The depth
    value is treated as optical-axis Z in millimetres and is cross-checked against
    the multi-marker PnP prediction before it may be used beyond diagnostics.
    """
    if depth_mm <= 0:
        raise ValueError("depth_mm must be positive")
    if distortion is not None and cv2_module is not None:
        pixel = np_module.asarray([[[u, v]]], dtype=np_module.float64)
        normalized = cv2_module.undistortPoints(pixel, camera_matrix, distortion)[0, 0]
        x_normalized, y_normalized = float(normalized[0]), float(normalized[1])
    else:
        fx = float(camera_matrix[0, 0])
        fy = float(camera_matrix[1, 1])
        cx = float(camera_matrix[0, 2])
        cy = float(camera_matrix[1, 2])
        if fx <= 0 or fy <= 0:
            raise ValueError("camera focal lengths must be positive")
        x_normalized = (u - cx) / fx
        y_normalized = (v - cy) / fy
    return np_module.asarray(
        [x_normalized * depth_mm, y_normalized * depth_mm, depth_mm],
        dtype=np_module.float64,
    )


def invert_transform(np_module: Any, transform: Any) -> Any:
    matrix = np_module.asarray(transform, dtype=np_module.float64)
    if matrix.shape != (4, 4):
        raise ValueError("transform must be 4x4")
    rotation = matrix[:3, :3]
    translation = matrix[:3, 3]
    inverse = np_module.eye(4, dtype=np_module.float64)
    inverse[:3, :3] = rotation.T
    inverse[:3, 3] = -rotation.T @ translation
    return inverse


def transform_point(np_module: Any, transform: Any, point_xyz: Any) -> Any:
    point = np_module.asarray(point_xyz, dtype=np_module.float64).reshape(3)
    homogeneous = np_module.concatenate((point, np_module.asarray([1.0])))
    return (np_module.asarray(transform, dtype=np_module.float64) @ homogeneous)[:3]


def estimate_rigid_transform(
    np_module: Any,
    source_points: Any,
    target_points: Any,
) -> dict[str, Any]:
    """Fit a no-scale rigid transform that maps source points into target points."""
    source = np_module.asarray(source_points, dtype=np_module.float64)
    target = np_module.asarray(target_points, dtype=np_module.float64)
    if source.shape != target.shape or source.ndim != 2 or source.shape[1] != 3:
        raise ValueError("source_points and target_points must have matching Nx3 shape")
    if source.shape[0] < 3:
        raise ValueError("at least three point correspondences are required")
    source_centered = source - source.mean(axis=0)
    target_centered = target - target.mean(axis=0)
    if np_module.linalg.matrix_rank(source_centered) < 2:
        raise ValueError("source point correspondences are degenerate")
    covariance = source_centered.T @ target_centered
    left, _, right_transposed = np_module.linalg.svd(covariance)
    rotation = right_transposed.T @ left.T
    if np_module.linalg.det(rotation) < 0:
        right_transposed[-1, :] *= -1
        rotation = right_transposed.T @ left.T
    translation = target.mean(axis=0) - rotation @ source.mean(axis=0)
    transform = np_module.eye(4, dtype=np_module.float64)
    transform[:3, :3] = rotation
    transform[:3, 3] = translation
    predicted = (rotation @ source.T).T + translation
    residual_vectors = predicted - target
    residuals = np_module.linalg.norm(residual_vectors, axis=1)
    rms = float(np_module.sqrt(np_module.mean(np_module.sum(residual_vectors ** 2, axis=1))))
    return {
        "transform": transform,
        "residuals_mm": residuals,
        "rms_mm": rms,
    }


def estimate_depth_world_transform(
    np_module: Any,
    reference_camera_points_mm: dict[int, Any],
    reference_centers_mm: dict[int, tuple[float, float, float]],
) -> dict[str, Any] | None:
    common_ids = sorted(set(reference_camera_points_mm).intersection(reference_centers_mm))
    if len(common_ids) < 4:
        return None
    world_points = np_module.asarray(
        [reference_centers_mm[marker_id] for marker_id in common_ids],
        dtype=np_module.float64,
    )
    camera_points = np_module.asarray(
        [reference_camera_points_mm[marker_id] for marker_id in common_ids],
        dtype=np_module.float64,
    )
    fit = estimate_rigid_transform(np_module, world_points, camera_points)
    plane_origin = camera_points.mean(axis=0)
    centered_camera = camera_points - plane_origin
    _, _, camera_axes = np_module.linalg.svd(centered_camera, full_matrices=False)
    plane_normal = camera_axes[-1]
    if float(plane_normal @ plane_origin) > 0:
        plane_normal = -plane_normal
    plane_distances = centered_camera @ plane_normal
    plane_rms = float(np_module.sqrt(np_module.mean(plane_distances ** 2)))
    pair_distances: dict[str, dict[str, float]] = {}
    for index, first_id in enumerate(common_ids):
        for second_id in common_ids[index + 1:]:
            expected = float(
                np_module.linalg.norm(
                    np_module.asarray(reference_centers_mm[first_id])
                    - np_module.asarray(reference_centers_mm[second_id])
                )
            )
            measured = float(
                np_module.linalg.norm(
                    np_module.asarray(reference_camera_points_mm[first_id])
                    - np_module.asarray(reference_camera_points_mm[second_id])
                )
            )
            pair_distances[f"{first_id}-{second_id}"] = {
                "expected_mm": expected,
                "depth_camera_mm": measured,
                "delta_mm": measured - expected,
            }
    transform_camera_world = fit["transform"]
    return {
        "reference_ids": common_ids,
        "T_C_W": transform_camera_world,
        "T_W_C": invert_transform(np_module, transform_camera_world),
        "fit_rms_mm": fit["rms_mm"],
        "residuals_mm": {
            marker_id: float(residual)
            for marker_id, residual in zip(common_ids, fit["residuals_mm"])
        },
        "plane_rms_mm": plane_rms,
        "plane_origin_camera_mm": plane_origin,
        "plane_normal_toward_camera": plane_normal,
        "pair_distances": pair_distances,
    }


def estimate_table_homography(
    cv2_module: Any,
    np_module: Any,
    corners: Any,
    ids: Any,
    reference_centers_mm: dict[int, tuple[float, float, float]],
) -> dict[str, Any] | None:
    if ids is None:
        return None
    detected = {
        int(marker_id): marker_corners.reshape(4, 2).mean(axis=0)
        for marker_corners, marker_id in zip(corners, ids.flatten())
    }
    common_ids = sorted(set(detected).intersection(reference_centers_mm))
    if len(common_ids) < 4:
        return None
    image_points = np_module.asarray(
        [detected[marker_id] for marker_id in common_ids], dtype=np_module.float64
    )
    table_points = np_module.asarray(
        [reference_centers_mm[marker_id][:2] for marker_id in common_ids],
        dtype=np_module.float64,
    )
    homography, _ = cv2_module.findHomography(image_points, table_points, method=0)
    if homography is None:
        return None
    projected = []
    for point in image_points:
        projected.append(project_table_xy(np_module, homography, point[0], point[1]))
    residual = np_module.asarray(projected) - table_points
    rms = float(np_module.sqrt(np_module.mean(np_module.sum(residual ** 2, axis=1))))
    return {
        "reference_ids": common_ids,
        "H_table_image": homography,
        "reference_rms_mm": rms,
    }


def project_table_xy(
    np_module: Any,
    homography: Any,
    u: float,
    v: float,
) -> Any:
    projected = np_module.asarray(homography, dtype=np_module.float64) @ np_module.asarray(
        [u, v, 1.0], dtype=np_module.float64
    )
    if abs(float(projected[2])) < 1e-12:
        raise ValueError("homography projected point at infinity")
    return projected[:2] / projected[2]


def height_above_depth_plane(
    np_module: Any,
    camera_point_mm: Any,
    plane_origin_camera_mm: Any,
    plane_normal_toward_camera: Any,
) -> float:
    point = np_module.asarray(camera_point_mm, dtype=np_module.float64).reshape(3)
    origin = np_module.asarray(plane_origin_camera_mm, dtype=np_module.float64).reshape(3)
    normal = np_module.asarray(
        plane_normal_toward_camera, dtype=np_module.float64
    ).reshape(3)
    norm = float(np_module.linalg.norm(normal))
    if norm <= 0:
        raise ValueError("plane normal must be non-zero")
    return float((point - origin) @ (normal / norm))


def estimate_world_transform(
    cv2_module: Any,
    np_module: Any,
    corners: Any,
    ids: Any,
    reference_centers_mm: dict[int, tuple[float, float, float]],
    camera_matrix: Any,
    distortion: Any,
) -> dict[str, Any] | None:
    if ids is None:
        return None
    detected = {
        int(marker_id): marker_corners.reshape(4, 2).mean(axis=0)
        for marker_corners, marker_id in zip(corners, ids.flatten())
    }
    common_ids = sorted(set(detected).intersection(reference_centers_mm))
    if len(common_ids) < 4:
        return None
    object_points = np_module.asarray(
        [reference_centers_mm[marker_id] for marker_id in common_ids],
        dtype=np_module.float64,
    )
    image_points = np_module.asarray(
        [detected[marker_id] for marker_id in common_ids],
        dtype=np_module.float64,
    )
    flag = getattr(cv2_module, "SOLVEPNP_IPPE", cv2_module.SOLVEPNP_ITERATIVE)
    ok, rotation_vector, translation = cv2_module.solvePnP(
        object_points,
        image_points,
        camera_matrix,
        distortion,
        flags=flag,
    )
    if not ok:
        return None
    rotation, _ = cv2_module.Rodrigues(rotation_vector)
    transform_camera_world = np_module.eye(4, dtype=np_module.float64)
    transform_camera_world[:3, :3] = rotation
    transform_camera_world[:3, 3] = translation.reshape(3)
    transform_world_camera = invert_transform(np_module, transform_camera_world)
    projected, _ = cv2_module.projectPoints(
        object_points, rotation_vector, translation, camera_matrix, distortion
    )
    residual = projected.reshape(-1, 2) - image_points
    reprojection_rms_px = float(np_module.sqrt(np_module.mean(np_module.sum(residual ** 2, axis=1))))
    return {
        "reference_ids": common_ids,
        "T_C_W": transform_camera_world,
        "T_W_C": transform_world_camera,
        "reprojection_rms_px": reprojection_rms_px,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pipe", default="/opt/orbbec-openni2/bin/orbbec-rgbd-pipe")
    parser.add_argument("--frames", type=int, default=300)
    parser.add_argument(
        "--frame-timeout-s",
        type=float,
        default=5.0,
        help="Abort and release the camera if the next RGB-D frame does not arrive",
    )
    parser.add_argument("--roi-radius", type=int, default=5, help="5 makes an 11x11 depth ROI")
    parser.add_argument("--min-depth-mm", type=int, default=200)
    parser.add_argument("--max-depth-mm", type=int, default=4000)
    parser.add_argument("--expected", default="0,1,2,3,4,5,6")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--rgb-output", type=Path, help="Save an unannotated RGB snapshot")
    parser.add_argument("--depth-output", type=Path, help="Save the matching raw uint16 depth snapshot as PNG")
    parser.add_argument(
        "--snapshot-require-expected",
        action="store_true",
        help="For raw outputs, prefer the first frame containing every expected marker ID",
    )
    parser.add_argument("--jsonl", type=Path)
    parser.add_argument("--calibration", type=Path)
    parser.add_argument("--workspace-config", type=Path)
    parser.add_argument(
        "--low-bandwidth",
        action="store_true",
        help="Use 320x240 RGB+depth to avoid legacy Astra USB2 bandwidth stalls",
    )
    parser.add_argument("--display", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.frames < 1 or args.roi_radius < 0 or args.frame_timeout_s <= 0:
        raise ValueError(
            "frames and frame-timeout-s must be positive; roi-radius must be non-negative"
        )
    if not 0 < args.min_depth_mm < args.max_depth_mm:
        raise ValueError("depth range must satisfy 0 < min < max")
    expected_ids = sorted({int(value) for value in args.expected.split(",") if value})

    import cv2
    import numpy as np

    calibration = load_calibration(args.calibration, np) if args.calibration else None
    reference_centers = (
        load_reference_centers(args.workspace_config) if args.workspace_config else None
    )
    marker_sizes = load_marker_sizes(args.workspace_config) if args.workspace_config else None
    if reference_centers is not None and calibration is None:
        raise ValueError("--workspace-config requires --calibration")

    pipe_arguments = [args.pipe] + (["--low-bandwidth"] if args.low_bandwidth else [])
    metadata_result = subprocess.run(
        [*pipe_arguments, "--info"],
        env=openni_environment(),
        check=True,
        text=True,
        capture_output=True,
    )
    metadata_lines = [line for line in metadata_result.stdout.splitlines() if line.lstrip().startswith("{")]
    if not metadata_lines:
        raise RuntimeError("RGBD helper did not return device metadata JSON")
    metadata = json.loads(metadata_lines[-1])
    if not metadata.get("registration_enabled"):
        raise RuntimeError("OpenNI depth-to-color registration is not enabled")
    rgb_size = (int(metadata["rgb"]["width"]), int(metadata["rgb"]["height"]))
    depth_size = (int(metadata["depth"]["width"]), int(metadata["depth"]["height"]))
    if rgb_size != depth_size:
        raise RuntimeError("registered RGB and depth resolutions must match")
    if calibration is not None:
        calibration = (
            scale_camera_matrix(np, calibration[0], calibration[2], rgb_size),
            calibration[1],
            rgb_size,
        )
    print(json.dumps({"type": "device", **metadata}, ensure_ascii=False), flush=True)

    detector = cv2.aruco.ArucoDetector(
        cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50),
        cv2.aruco.DetectorParameters(),
    )
    process = subprocess.Popen(
        pipe_arguments,
        stdout=subprocess.PIPE,
        env=openni_environment(),
        bufsize=0,
    )
    if process.stdout is None:
        raise RuntimeError("RGBD helper stdout is unavailable")

    log_handle = None
    if args.jsonl:
        args.jsonl.parent.mkdir(parents=True, exist_ok=True)
        log_handle = args.jsonl.open("w", encoding="utf-8")
    frames = 0
    invalid_percentages: list[float] = []
    center_depths: list[float] = []
    marker_depths: dict[int, list[float]] = {}
    marker_camera_points: dict[int, list[Any]] = {}
    marker_world_points: dict[int, list[Any]] = {}
    marker_world_reference_errors: dict[int, list[float]] = {}
    marker_depth_world_points: dict[int, list[Any]] = {}
    marker_depth_world_reference_errors: dict[int, list[float]] = {}
    marker_table_xy: dict[int, list[Any]] = {}
    marker_heights_above_table: dict[int, list[float]] = {}
    marker_depth_pnp_deltas: dict[int, list[float]] = {}
    marker_single_pnp_z: dict[int, list[float]] = {}
    marker_depth_single_pnp_deltas: dict[int, list[float]] = {}
    marker_seen: dict[int, int] = {marker_id: 0 for marker_id in expected_ids}
    world_pose_frames = 0
    world_reprojection_rms_px: list[float] = []
    world_camera_origins_mm: list[Any] = []
    depth_world_pose_frames = 0
    depth_world_fit_rms_mm: list[float] = []
    depth_reference_plane_rms_mm: list[float] = []
    depth_world_camera_origins_mm: list[Any] = []
    depth_pair_measurements: dict[str, dict[str, Any]] = {}
    table_homography_frames = 0
    table_homography_reference_rms_mm: list[float] = []
    last_composite = None
    last_bgr_raw = None
    last_depth = None
    expected_snapshot_bgr = None
    expected_snapshot_depth = None
    sync_deltas_us: list[int] = []
    valid_min = None
    valid_max = None
    started = time.monotonic()
    try:
        while frames < args.frames:
            readable, _, _ = select.select(
                [process.stdout], [], [], args.frame_timeout_s
            )
            if not readable:
                raise RuntimeError(
                    f"RGBD frame timeout after {args.frame_timeout_s:g}s "
                    f"(captured={frames})"
                )
            header = read_frame_header(process.stdout)
            if header is None:
                raise RuntimeError(f"RGBD pipe ended early (exit={process.poll()})")
            magic, width, height, color_timestamp, depth_timestamp = HEADER.unpack(header)
            if magic != b"RGBD" or (width, height) != rgb_size:
                raise RuntimeError("invalid RGBD frame header")
            rgb_bytes = read_exact(process.stdout, width * height * 3)
            depth_bytes = read_exact(process.stdout, width * height * 2)
            if rgb_bytes is None or depth_bytes is None:
                raise RuntimeError("incomplete RGBD frame payload")
            rgb = np.frombuffer(rgb_bytes, dtype=np.uint8).reshape((height, width, 3))
            bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
            depth = np.frombuffer(depth_bytes, dtype="<u2").reshape((height, width))
            last_bgr_raw = bgr.copy()
            last_depth = depth.copy()
            frames += 1
            sync_delta = abs(int(color_timestamp) - int(depth_timestamp))
            sync_deltas_us.append(sync_delta)

            valid_mask = (depth >= args.min_depth_mm) & (depth <= args.max_depth_mm)
            valid = depth[valid_mask]
            invalid_percentage = 100.0 * (1.0 - float(valid.size) / float(depth.size))
            invalid_percentages.append(invalid_percentage)
            if valid.size:
                frame_min = int(valid.min())
                frame_max = int(valid.max())
                valid_min = frame_min if valid_min is None else min(valid_min, frame_min)
                valid_max = frame_max if valid_max is None else max(valid_max, frame_max)
            center_depth, center_valid, center_total = median_depth_roi(
                depth, width / 2.0, height / 2.0, args.roi_radius,
                args.min_depth_mm, args.max_depth_mm,
            )
            if center_depth is not None:
                center_depths.append(center_depth)

            corners, ids, _ = detect_markers_multiscale(cv2, np, detector, bgr)
            if (
                args.snapshot_require_expected
                and expected_snapshot_bgr is None
                and ids is not None
                and set(expected_ids).issubset({int(value) for value in ids.flatten()})
            ):
                expected_snapshot_bgr = last_bgr_raw.copy()
                expected_snapshot_depth = last_depth.copy()
            world_pose = None
            if calibration is not None and reference_centers is not None:
                world_pose = estimate_world_transform(
                    cv2,
                    np,
                    corners,
                    ids,
                    reference_centers,
                    calibration[0],
                    calibration[1],
                )
                if world_pose is not None:
                    world_pose_frames += 1
                    world_reprojection_rms_px.append(world_pose["reprojection_rms_px"])
                    world_camera_origins_mm.append(world_pose["T_W_C"][:3, 3].copy())
            table_homography = None
            if reference_centers is not None:
                table_homography = estimate_table_homography(
                    cv2,
                    np,
                    corners,
                    ids,
                    reference_centers,
                )
                if table_homography is not None:
                    table_homography_frames += 1
                    table_homography_reference_rms_mm.append(
                        table_homography["reference_rms_mm"]
                    )
            depth_world_pose = None
            if ids is not None and calibration is not None and reference_centers is not None:
                reference_camera_points: dict[int, Any] = {}
                for marker_corners, marker_id_value in zip(corners, ids.flatten()):
                    marker_id = int(marker_id_value)
                    if marker_id not in reference_centers:
                        continue
                    center = marker_corners.reshape(4, 2).mean(axis=0)
                    marker_depth, _, _ = median_depth_roi(
                        depth,
                        float(center[0]),
                        float(center[1]),
                        args.roi_radius,
                        args.min_depth_mm,
                        args.max_depth_mm,
                    )
                    if marker_depth is None:
                        continue
                    reference_camera_points[marker_id] = deproject_registered_pixel(
                        np,
                        float(center[0]),
                        float(center[1]),
                        marker_depth,
                        calibration[0],
                        calibration[1],
                        cv2,
                    )
                depth_world_pose = estimate_depth_world_transform(
                    np,
                    reference_camera_points,
                    reference_centers,
                )
                if depth_world_pose is not None:
                    depth_world_pose_frames += 1
                    depth_world_fit_rms_mm.append(depth_world_pose["fit_rms_mm"])
                    depth_reference_plane_rms_mm.append(depth_world_pose["plane_rms_mm"])
                    depth_world_camera_origins_mm.append(
                        depth_world_pose["T_W_C"][:3, 3].copy()
                    )
                    for pair_name, pair_values in depth_world_pose["pair_distances"].items():
                        aggregate = depth_pair_measurements.setdefault(
                            pair_name,
                            {
                                "expected_mm": pair_values["expected_mm"],
                                "depth_camera_mm": [],
                                "delta_mm": [],
                            },
                        )
                        aggregate["depth_camera_mm"].append(
                            pair_values["depth_camera_mm"]
                        )
                        aggregate["delta_mm"].append(pair_values["delta_mm"])
            frame_markers = []
            if ids is not None:
                cv2.aruco.drawDetectedMarkers(bgr, corners, ids)
                for marker_corners, marker_id_value in zip(corners, ids.flatten()):
                    marker_id = int(marker_id_value)
                    center = marker_corners.reshape(4, 2).mean(axis=0)
                    marker_depth, roi_valid, roi_total = median_depth_roi(
                        depth, float(center[0]), float(center[1]), args.roi_radius,
                        args.min_depth_mm, args.max_depth_mm,
                    )
                    marker_seen[marker_id] = marker_seen.get(marker_id, 0) + 1
                    if marker_depth is not None:
                        marker_depths.setdefault(marker_id, []).append(marker_depth)
                    table_xy = None
                    if table_homography is not None:
                        table_xy = project_table_xy(
                            np,
                            table_homography["H_table_image"],
                            float(center[0]),
                            float(center[1]),
                        )
                        marker_table_xy.setdefault(marker_id, []).append(table_xy)
                    camera_xyz = None
                    world_xyz = None
                    world_reference_error = None
                    depth_world_xyz = None
                    depth_world_reference_error = None
                    height_above_table = None
                    depth_minus_pnp_z = None
                    marker_size_mm = None
                    single_marker_pnp_z = None
                    depth_minus_single_marker_pnp_z = None
                    if calibration is not None and marker_sizes is not None:
                        marker_size_mm = marker_sizes[1].get(marker_id, marker_sizes[0])
                        single_marker_pnp_z = estimate_single_marker_pnp_z(
                            cv2,
                            np,
                            marker_corners,
                            marker_size_mm,
                            calibration[0],
                            calibration[1],
                        )
                        if single_marker_pnp_z is not None:
                            marker_single_pnp_z.setdefault(marker_id, []).append(
                                single_marker_pnp_z
                            )
                            if marker_depth is not None:
                                depth_minus_single_marker_pnp_z = (
                                    marker_depth - single_marker_pnp_z
                                )
                                marker_depth_single_pnp_deltas.setdefault(
                                    marker_id, []
                                ).append(depth_minus_single_marker_pnp_z)
                    if marker_depth is not None and calibration is not None:
                        camera_xyz = deproject_registered_pixel(
                            np,
                            float(center[0]),
                            float(center[1]),
                            marker_depth,
                            calibration[0],
                            calibration[1],
                            cv2,
                        )
                        marker_camera_points.setdefault(marker_id, []).append(camera_xyz)
                        if world_pose is not None:
                            world_xyz = transform_point(np, world_pose["T_W_C"], camera_xyz)
                            marker_world_points.setdefault(marker_id, []).append(world_xyz)
                            if marker_id in reference_centers:
                                expected_world = np.asarray(
                                    reference_centers[marker_id], dtype=np.float64
                                )
                                world_reference_error = float(
                                    np.linalg.norm(world_xyz - expected_world)
                                )
                                marker_world_reference_errors.setdefault(
                                    marker_id, []
                                ).append(world_reference_error)
                                predicted_camera = transform_point(
                                    np, world_pose["T_C_W"], expected_world
                                )
                                depth_minus_pnp_z = marker_depth - float(predicted_camera[2])
                                marker_depth_pnp_deltas.setdefault(marker_id, []).append(
                                    depth_minus_pnp_z
                                )
                        if depth_world_pose is not None:
                            height_above_table = height_above_depth_plane(
                                np,
                                camera_xyz,
                                depth_world_pose["plane_origin_camera_mm"],
                                depth_world_pose["plane_normal_toward_camera"],
                            )
                            marker_heights_above_table.setdefault(marker_id, []).append(
                                height_above_table
                            )
                            depth_world_xyz = transform_point(
                                np,
                                depth_world_pose["T_W_C"],
                                camera_xyz,
                            )
                            marker_depth_world_points.setdefault(marker_id, []).append(
                                depth_world_xyz
                            )
                            if marker_id in reference_centers:
                                expected_depth_world = np.asarray(
                                    reference_centers[marker_id], dtype=np.float64
                                )
                                depth_world_reference_error = float(
                                    np.linalg.norm(
                                        depth_world_xyz - expected_depth_world
                                    )
                                )
                                marker_depth_world_reference_errors.setdefault(
                                    marker_id, []
                                ).append(depth_world_reference_error)
                    marker_record = {
                        "marker_id": marker_id,
                        "u": round(float(center[0]), 3),
                        "v": round(float(center[1]), 3),
                        "depth_mm": marker_depth,
                        "depth_valid_samples": roi_valid,
                        "depth_roi_samples": roi_total,
                        "camera_xyz_mm": (
                            None if camera_xyz is None else [round(float(value), 3) for value in camera_xyz]
                        ),
                        "world_xyz_mm": (
                            None if world_xyz is None else [round(float(value), 3) for value in world_xyz]
                        ),
                        "world_reference_error_mm": (
                            None
                            if world_reference_error is None
                            else round(world_reference_error, 3)
                        ),
                        "depth_world_xyz_mm": (
                            None
                            if depth_world_xyz is None
                            else [round(float(value), 3) for value in depth_world_xyz]
                        ),
                        "depth_world_reference_error_mm": (
                            None
                            if depth_world_reference_error is None
                            else round(depth_world_reference_error, 3)
                        ),
                        "table_xy_mm": (
                            None
                            if table_xy is None
                            else [round(float(value), 3) for value in table_xy]
                        ),
                        "height_above_table_mm": (
                            None
                            if height_above_table is None
                            else round(height_above_table, 3)
                        ),
                        "depth_minus_pnp_z_mm": (
                            None if depth_minus_pnp_z is None else round(depth_minus_pnp_z, 3)
                        ),
                        "marker_size_mm": marker_size_mm,
                        "single_marker_pnp_z_mm": (
                            None
                            if single_marker_pnp_z is None
                            else round(single_marker_pnp_z, 3)
                        ),
                        "depth_minus_single_marker_pnp_z_mm": (
                            None
                            if depth_minus_single_marker_pnp_z is None
                            else round(depth_minus_single_marker_pnp_z, 3)
                        ),
                    }
                    frame_markers.append(marker_record)

            clipped = np.clip(depth.astype(np.float32), args.min_depth_mm, args.max_depth_mm)
            normalized = ((clipped - args.min_depth_mm) * 255.0 /
                          (args.max_depth_mm - args.min_depth_mm)).astype(np.uint8)
            colorized = cv2.applyColorMap(255 - normalized, cv2.COLORMAP_TURBO)
            colorized[~valid_mask] = 0
            cv2.rectangle(colorized, (0, 0), (width - 1, min(height - 1, 16 * len(frame_markers) + 8)), (0, 0, 0), -1)
            for row, marker_record in enumerate(frame_markers):
                table_xy = marker_record["table_xy_mm"]
                height_mm = marker_record["height_above_table_mm"]
                if table_xy is not None and height_mm is not None:
                    label = (
                        f"ID{marker_record['marker_id']} "
                        f"T({table_xy[0]:.0f},{table_xy[1]:.0f}) "
                        f"H{height_mm:.0f}mm"
                    )
                    color = (0, 255, 0)
                else:
                    label = f"ID{marker_record['marker_id']} 2.5D unavailable"
                    color = (0, 200, 255)
                cv2.putText(
                    colorized,
                    label,
                    (6, 16 * row + 15),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.42,
                    color,
                    1,
                    cv2.LINE_AA,
                )
            last_composite = np.hstack((bgr, colorized))
            record = {
                "timestamp": time.time(),
                "frame": frames,
                "unit": "mm",
                "registered_depth_to_color": True,
                "sync_delta_us": sync_delta,
                "center_depth_mm": center_depth,
                "center_depth_valid_samples": center_valid,
                "center_depth_roi_samples": center_total,
                "invalid_depth_percent": round(invalid_percentage, 4),
                "deprojection_model": (
                    "registered_color_pinhole" if calibration is not None else None
                ),
                "world_pose": (
                    None
                    if world_pose is None
                    else {
                        "reference_ids": world_pose["reference_ids"],
                        "reprojection_rms_px": round(world_pose["reprojection_rms_px"], 6),
                        "T_W_C": np.round(world_pose["T_W_C"], 6).tolist(),
                    }
                ),
                "table_homography": (
                    None
                    if table_homography is None
                    else {
                        "reference_ids": table_homography["reference_ids"],
                        "reference_rms_mm": round(
                            table_homography["reference_rms_mm"], 6
                        ),
                        "H_table_image": np.round(
                            table_homography["H_table_image"], 9
                        ).tolist(),
                    }
                ),
                "depth_world_pose": (
                    None
                    if depth_world_pose is None
                    else {
                        "reference_ids": depth_world_pose["reference_ids"],
                        "fit_rms_mm": round(depth_world_pose["fit_rms_mm"], 6),
                        "plane_rms_mm": round(depth_world_pose["plane_rms_mm"], 6),
                        "plane_origin_camera_mm": np.round(
                            depth_world_pose["plane_origin_camera_mm"], 6
                        ).tolist(),
                        "plane_normal_toward_camera": np.round(
                            depth_world_pose["plane_normal_toward_camera"], 9
                        ).tolist(),
                        "pair_distances": {
                            pair_name: {
                                key: round(value, 6)
                                for key, value in pair_values.items()
                            }
                            for pair_name, pair_values in depth_world_pose[
                                "pair_distances"
                            ].items()
                        },
                        "T_W_C": np.round(
                            depth_world_pose["T_W_C"], 6
                        ).tolist(),
                    }
                ),
                "markers": frame_markers,
            }
            if log_handle:
                log_handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            if frames == 1 or frames % 30 == 0:
                print(json.dumps(record, ensure_ascii=False), flush=True)
            if args.display:
                cv2.imshow("Astra RGB | aligned depth", last_composite)
                if cv2.waitKey(1) & 0xFF in (27, ord("q")):
                    break
    finally:
        if log_handle:
            log_handle.close()
        if process.stdout is not None:
            process.stdout.close()
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
        if args.display:
            cv2.destroyAllWindows()

    if args.output and last_composite is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite(str(args.output), last_composite):
            raise RuntimeError(f"Could not write {args.output}")
    snapshot_bgr = (
        expected_snapshot_bgr if expected_snapshot_bgr is not None else last_bgr_raw
    )
    snapshot_depth = (
        expected_snapshot_depth if expected_snapshot_depth is not None else last_depth
    )
    if args.rgb_output and snapshot_bgr is not None:
        args.rgb_output.parent.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite(str(args.rgb_output), snapshot_bgr):
            raise RuntimeError(f"Could not write {args.rgb_output}")
    if args.depth_output and snapshot_depth is not None:
        args.depth_output.parent.mkdir(parents=True, exist_ok=True)
        if args.depth_output.suffix.lower() != ".png":
            raise ValueError("--depth-output must use .png to preserve uint16 millimetres")
        if not cv2.imwrite(str(args.depth_output), snapshot_depth):
            raise RuntimeError(f"Could not write {args.depth_output}")

    marker_summary = {}
    for marker_id in sorted(
        set(expected_ids)
        .union(marker_depths)
        .union(marker_camera_points)
        .union(marker_world_points)
        .union(marker_depth_world_points)
    ):
        values = marker_depths.get(marker_id, [])
        camera_values = marker_camera_points.get(marker_id, [])
        world_values = marker_world_points.get(marker_id, [])
        world_reference_errors = marker_world_reference_errors.get(marker_id, [])
        depth_world_values = marker_depth_world_points.get(marker_id, [])
        depth_world_reference_errors = marker_depth_world_reference_errors.get(
            marker_id, []
        )
        table_xy_values = marker_table_xy.get(marker_id, [])
        height_values = marker_heights_above_table.get(marker_id, [])
        pnp_deltas = marker_depth_pnp_deltas.get(marker_id, [])
        single_pnp_z_values = marker_single_pnp_z.get(marker_id, [])
        single_pnp_deltas = marker_depth_single_pnp_deltas.get(marker_id, [])
        marker_size_mm = (
            None
            if marker_sizes is None
            else marker_sizes[1].get(marker_id, marker_sizes[0])
        )
        marker_summary[str(marker_id)] = {
            "seen_frames": marker_seen.get(marker_id, 0),
            "valid_depth_frames": len(values),
            "depth_median_mm": statistics.median(values) if values else None,
            "depth_std_mm": statistics.pstdev(values) if len(values) > 1 else None,
            "camera_xyz_median_mm": (
                None if not camera_values else np.median(np.asarray(camera_values), axis=0).tolist()
            ),
            "world_xyz_median_mm": (
                None if not world_values else np.median(np.asarray(world_values), axis=0).tolist()
            ),
            "world_reference_error_median_mm": (
                statistics.median(world_reference_errors)
                if world_reference_errors
                else None
            ),
            "depth_world_xyz_median_mm": (
                None
                if not depth_world_values
                else np.median(np.asarray(depth_world_values), axis=0).tolist()
            ),
            "depth_world_reference_error_median_mm": (
                statistics.median(depth_world_reference_errors)
                if depth_world_reference_errors
                else None
            ),
            "table_xy_median_mm": (
                None
                if not table_xy_values
                else np.median(np.asarray(table_xy_values), axis=0).tolist()
            ),
            "table_xy_std_mm": (
                None
                if len(table_xy_values) < 2
                else np.std(np.asarray(table_xy_values), axis=0).tolist()
            ),
            "height_above_table_median_mm": (
                statistics.median(height_values) if height_values else None
            ),
            "height_above_table_std_mm": (
                statistics.pstdev(height_values) if len(height_values) > 1 else None
            ),
            "depth_minus_pnp_z_median_mm": (
                statistics.median(pnp_deltas) if pnp_deltas else None
            ),
            "marker_size_mm": marker_size_mm,
            "single_marker_pnp_z_median_mm": (
                statistics.median(single_pnp_z_values) if single_pnp_z_values else None
            ),
            "depth_minus_single_marker_pnp_z_median_mm": (
                statistics.median(single_pnp_deltas) if single_pnp_deltas else None
            ),
        }
    depth_pair_summary = {
        pair_name: {
            "expected_mm": values["expected_mm"],
            "depth_camera_median_mm": statistics.median(values["depth_camera_mm"]),
            "delta_median_mm": statistics.median(values["delta_mm"]),
        }
        for pair_name, values in sorted(depth_pair_measurements.items())
    }
    elapsed = time.monotonic() - started
    summary = {
        "type": "summary",
        "safety": "camera-only; no robot serial port opened; no motion command",
        "unit": "mm",
        "frames": frames,
        "elapsed_s": round(elapsed, 3),
        "effective_fps": round(frames / elapsed, 3) if elapsed else None,
        "depth_resolution": list(depth_size),
        "depth_format": "DEPTH_1_MM",
        "registered_depth_to_color": True,
        "deprojection_model": (
            "registered_color_pinhole" if calibration is not None else None
        ),
        "center_depth_median_mm": statistics.median(center_depths) if center_depths else None,
        "valid_depth_min_mm": valid_min,
        "valid_depth_max_mm": valid_max,
        "invalid_depth_mean_percent": (
            statistics.mean(invalid_percentages) if invalid_percentages else None
        ),
        "sync_delta_median_us": statistics.median(sync_deltas_us) if sync_deltas_us else None,
        "expected_ids": expected_ids,
        "world_pose_frames": world_pose_frames,
        "table_homography_frames": table_homography_frames,
        "table_homography_reference_rms_median_mm": (
            statistics.median(table_homography_reference_rms_mm)
            if table_homography_reference_rms_mm
            else None
        ),
        "world_reprojection_rms_median_px": (
            statistics.median(world_reprojection_rms_px)
            if world_reprojection_rms_px
            else None
        ),
        "camera_origin_world_median_mm": (
            None
            if not world_camera_origins_mm
            else np.median(np.asarray(world_camera_origins_mm), axis=0).tolist()
        ),
        "depth_world_pose_frames": depth_world_pose_frames,
        "depth_world_fit_rms_median_mm": (
            statistics.median(depth_world_fit_rms_mm)
            if depth_world_fit_rms_mm
            else None
        ),
        "depth_reference_plane_rms_median_mm": (
            statistics.median(depth_reference_plane_rms_mm)
            if depth_reference_plane_rms_mm
            else None
        ),
        "depth_camera_origin_world_median_mm": (
            None
            if not depth_world_camera_origins_mm
            else np.median(np.asarray(depth_world_camera_origins_mm), axis=0).tolist()
        ),
        "depth_reference_pair_distances": depth_pair_summary,
        "markers": marker_summary,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True), flush=True)
    return 0 if frames > 0 else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", flush=True)
        raise SystemExit(1)
