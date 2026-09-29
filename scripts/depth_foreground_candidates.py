#!/usr/bin/env python3
"""Find above-table foreground candidates in a saved Astra RGB-D snapshot.

This is a camera-only dataset-bootstrap tool. It does not import robot code or
send motion commands. Candidate boxes are proposals for review, not medicine
identity decisions and not robot targets.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rgb", required=True, type=Path)
    parser.add_argument("--depth", required=True, type=Path)
    parser.add_argument("--calibration", required=True, type=Path)
    parser.add_argument("--workspace-config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--min-height-mm", type=float, default=15.0)
    parser.add_argument("--max-height-mm", type=float, default=180.0)
    parser.add_argument("--min-area-px", type=int, default=12)
    parser.add_argument("--max-area-px", type=int, default=2500)
    parser.add_argument("--max-candidates", type=int, default=30)
    parser.add_argument("--yolo-label-output", type=Path)
    parser.add_argument("--yolo-class-id", type=int, default=0)
    parser.add_argument("--bbox-margin-px", type=int, default=2)
    parser.add_argument(
        "--reviewed-bbox-xywh",
        type=int,
        nargs=4,
        metavar=("X", "Y", "W", "H"),
        help="Explicit whole-object box after RGB visual review; must contain the selected depth box",
    )
    parser.add_argument("--review-note", help="Required reason for a reviewed box override")
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if not 0 <= args.min_height_mm < args.max_height_mm:
        raise ValueError("height range must satisfy 0 <= min < max")
    if not 0 < args.min_area_px <= args.max_area_px:
        raise ValueError("area range must satisfy 0 < min <= max")
    if args.max_candidates < 1:
        raise ValueError("max-candidates must be positive")
    if args.yolo_class_id < 0:
        raise ValueError("yolo-class-id must be non-negative")
    if args.bbox_margin_px < 0:
        raise ValueError("bbox-margin-px must be non-negative")
    if args.reviewed_bbox_xywh is not None and (
        args.yolo_label_output is None or not args.review_note
    ):
        raise ValueError("reviewed box requires --yolo-label-output and --review-note")


def load_pickup_roi(config_path: Path) -> dict[str, list[float]]:
    """Load the table-coordinate ROI used only to rank camera proposals."""
    config = json.loads(config_path.read_text(encoding="utf-8"))
    roi = config.get("pickup_roi_table_mm")
    if not isinstance(roi, dict):
        raise ValueError("workspace config requires pickup_roi_table_mm")
    result: dict[str, list[float]] = {}
    for axis in ("x", "y"):
        bounds = roi.get(axis)
        if (
            not isinstance(bounds, list)
            or len(bounds) != 2
            or not all(isinstance(value, (int, float)) for value in bounds)
            or float(bounds[0]) >= float(bounds[1])
        ):
            raise ValueError(f"pickup ROI {axis} must be [min, max]")
        result[axis] = [float(bounds[0]), float(bounds[1])]
    return result


def load_pickup_candidate_filter(config_path: Path) -> dict[str, float]:
    """Load conservative whole-object gates for bootstrap label selection."""
    config = json.loads(config_path.read_text(encoding="utf-8"))
    values = config.get("pickup_candidate_filter")
    if not isinstance(values, dict):
        raise ValueError("workspace config requires pickup_candidate_filter")
    result = {}
    for key in (
        "min_area_px",
        "max_area_px",
        "min_height_median_mm",
        "max_height_median_mm",
    ):
        value = values.get(key)
        if not isinstance(value, (int, float)):
            raise ValueError(f"pickup candidate filter requires numeric {key}")
        result[key] = float(value)
    if not 0 < result["min_area_px"] <= result["max_area_px"]:
        raise ValueError("pickup candidate area filter must satisfy 0 < min <= max")
    if not 0 <= result["min_height_median_mm"] <= result["max_height_median_mm"]:
        raise ValueError("pickup candidate height filter must satisfy 0 <= min <= max")
    return result


def select_pickup_candidate(
    candidates: list[dict[str, Any]],
    roi: dict[str, list[float]],
    candidate_filter: dict[str, float] | None = None,
) -> dict[str, Any] | None:
    """Choose the largest foreground proposal whose centroid is inside the ROI."""
    eligible = []
    for candidate in candidates:
        x_mm, y_mm = candidate["table_xy_mm"]
        if not (
            roi["x"][0] <= x_mm <= roi["x"][1]
            and roi["y"][0] <= y_mm <= roi["y"][1]
        ):
            continue
        if candidate_filter and not (
            candidate_filter["min_area_px"]
            <= candidate["area_px"]
            <= candidate_filter["max_area_px"]
            and candidate_filter["min_height_median_mm"]
            <= candidate["height_median_mm"]
            <= candidate_filter["max_height_median_mm"]
        ):
            continue
        eligible.append(candidate)
    if not eligible:
        return None
    return max(eligible, key=lambda item: (item["area_px"], item["height_median_mm"]))


def bbox_to_yolo(
    bbox_xywh: list[int], image_width: int, image_height: int, margin_px: int = 0
) -> tuple[float, float, float, float]:
    """Convert a clipped pixel bbox to normalized YOLO center/size values."""
    x, y, width, height = bbox_xywh
    x1 = max(0, x - margin_px)
    y1 = max(0, y - margin_px)
    x2 = min(image_width, x + width + margin_px)
    y2 = min(image_height, y + height + margin_px)
    return (
        ((x1 + x2) / 2.0) / image_width,
        ((y1 + y2) / 2.0) / image_height,
        (x2 - x1) / image_width,
        (y2 - y1) / image_height,
    )


def validate_reviewed_bbox(
    reviewed_bbox: list[int], selected_bbox: list[int], image_width: int, image_height: int
) -> None:
    x, y, width, height = reviewed_bbox
    sx, sy, sw, sh = selected_bbox
    if width <= 0 or height <= 0 or x < 0 or y < 0:
        raise ValueError("reviewed bbox must have positive size and non-negative origin")
    if x + width > image_width or y + height > image_height:
        raise ValueError("reviewed bbox must lie inside the image")
    if not (x <= sx and y <= sy and x + width >= sx + sw and y + height >= sy + sh):
        raise ValueError("reviewed bbox must contain the selected depth candidate")


def deproject_dense_depth(np_module: Any, normalized_pixels: Any, depth_mm: Any) -> Any:
    """Build XYZ without allowing a temporary expression to overwrite depth Z."""
    rays = np_module.asarray(normalized_pixels, dtype=np_module.float64)
    z_mm = np_module.asarray(depth_mm, dtype=np_module.float64)
    if rays.ndim != 2 or rays.shape[1] != 2 or z_mm.shape != (len(rays),):
        raise ValueError("normalized pixels and depth values must have matching lengths")
    camera_points = np_module.empty((len(z_mm), 3), dtype=np_module.float64)
    np_module.multiply(rays[:, 0], z_mm, out=camera_points[:, 0])
    np_module.multiply(rays[:, 1], z_mm, out=camera_points[:, 1])
    camera_points[:, 2] = z_mm
    return camera_points


def main() -> int:
    args = parse_args()
    validate_args(args)

    import cv2
    import numpy as np

    import astra_depth_diagnostic as diagnostic

    rgb = cv2.imread(str(args.rgb), cv2.IMREAD_COLOR)
    depth = cv2.imread(str(args.depth), cv2.IMREAD_UNCHANGED)
    if rgb is None:
        raise RuntimeError(f"could not read RGB image: {args.rgb}")
    if depth is None or depth.dtype != np.uint16:
        raise RuntimeError("depth image must be a readable uint16 PNG")
    if rgb.shape[:2] != depth.shape:
        raise RuntimeError("RGB and depth dimensions must match")

    height, width = depth.shape
    camera_matrix, distortion, calibration_size = diagnostic.load_calibration(
        args.calibration, np
    )
    camera_matrix = diagnostic.scale_camera_matrix(
        np, camera_matrix, calibration_size, (width, height)
    )
    reference_centers = diagnostic.load_reference_centers(args.workspace_config)
    pickup_roi = load_pickup_roi(args.workspace_config)
    pickup_candidate_filter = load_pickup_candidate_filter(args.workspace_config)
    detector = cv2.aruco.ArucoDetector(
        cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50),
        cv2.aruco.DetectorParameters(),
    )
    corners, ids, _ = diagnostic.detect_markers_multiscale(cv2, np, detector, rgb)
    table_homography = diagnostic.estimate_table_homography(
        cv2, np, corners, ids, reference_centers
    )
    if table_homography is None:
        raise RuntimeError("all four reference markers are required")

    reference_camera_points: dict[int, Any] = {}
    if ids is not None:
        for marker_corners, marker_id_value in zip(corners, ids.flatten()):
            marker_id = int(marker_id_value)
            if marker_id not in reference_centers:
                continue
            center = marker_corners.reshape(4, 2).mean(axis=0)
            marker_depth, _, _ = diagnostic.median_depth_roi(
                depth, float(center[0]), float(center[1]), 5, 200, 4000
            )
            if marker_depth is None:
                continue
            reference_camera_points[marker_id] = diagnostic.deproject_registered_pixel(
                np,
                float(center[0]),
                float(center[1]),
                marker_depth,
                camera_matrix,
                distortion,
                cv2,
            )
    depth_pose = diagnostic.estimate_depth_world_transform(
        np, reference_camera_points, reference_centers
    )
    if depth_pose is None:
        raise RuntimeError("valid depth is required at all four reference markers")

    valid = (depth >= 200) & (depth <= 4000)
    ys, xs = np.nonzero(valid)
    pixels = np.column_stack((xs, ys)).astype(np.float64).reshape(-1, 1, 2)
    normalized = cv2.undistortPoints(pixels, camera_matrix, distortion).reshape(-1, 2)
    z = depth[ys, xs].astype(np.float64)
    camera_points = deproject_dense_depth(np, normalized, z)
    origin = np.asarray(depth_pose["plane_origin_camera_mm"], dtype=np.float64)
    normal = np.asarray(depth_pose["plane_normal_toward_camera"], dtype=np.float64)
    heights = (camera_points - origin) @ normal

    height_map = np.full(depth.shape, np.nan, dtype=np.float32)
    height_map[ys, xs] = heights.astype(np.float32)
    foreground = (
        valid
        & (height_map >= args.min_height_mm)
        & (height_map <= args.max_height_mm)
    ).astype(np.uint8)

    for marker_corners in corners:
        polygon = np.rint(marker_corners.reshape(4, 2)).astype(np.int32)
        cv2.fillConvexPoly(foreground, polygon, 0)
    kernel = np.ones((3, 3), dtype=np.uint8)
    foreground = cv2.morphologyEx(foreground, cv2.MORPH_OPEN, kernel)
    foreground = cv2.morphologyEx(foreground, cv2.MORPH_CLOSE, kernel)

    count, labels, stats, centroids = cv2.connectedComponentsWithStats(
        foreground, connectivity=8
    )
    candidates = []
    for label in range(1, count):
        x, y, box_width, box_height, area = [int(value) for value in stats[label]]
        if area < args.min_area_px or area > args.max_area_px:
            continue
        if x == 0 or y == 0 or x + box_width >= width or y + box_height >= height:
            continue
        component = labels == label
        component_heights = height_map[component]
        center_u, center_v = [float(value) for value in centroids[label]]
        table_xy = diagnostic.project_table_xy(
            np,
            table_homography["H_table_image"],
            center_u,
            center_v,
        )
        candidates.append(
            {
                "bbox_xywh": [x, y, box_width, box_height],
                "area_px": area,
                "centroid_px": [round(center_u, 3), round(center_v, 3)],
                "table_xy_mm": [round(float(value), 3) for value in table_xy],
                "height_median_mm": round(float(np.nanmedian(component_heights)), 3),
                "height_max_mm": round(float(np.nanmax(component_heights)), 3),
            }
        )
    candidates.sort(key=lambda item: item["area_px"], reverse=True)
    candidates = candidates[: args.max_candidates]
    for index, candidate in enumerate(candidates):
        candidate["candidate_id"] = f"C{index}"
    selected = select_pickup_candidate(
        candidates, pickup_roi, pickup_candidate_filter
    )
    reviewed_bbox = args.reviewed_bbox_xywh
    if reviewed_bbox is not None:
        if selected is None:
            raise RuntimeError("cannot review a bbox without a selected depth candidate")
        validate_reviewed_bbox(reviewed_bbox, selected["bbox_xywh"], width, height)

    annotated = rgb.copy()
    for candidate in candidates:
        x, y, box_width, box_height = candidate["bbox_xywh"]
        is_selected = selected is candidate
        color = (0, 255, 255) if is_selected else (0, 255, 0)
        thickness = 2 if is_selected else 1
        cv2.rectangle(
            annotated, (x, y), (x + box_width, y + box_height), color, thickness
        )
        cv2.putText(
            annotated,
            f"{candidate['candidate_id']} H{candidate['height_median_mm']:.0f}",
            (x, max(12, y - 3)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.35,
            color,
            1,
            cv2.LINE_AA,
        )
    if reviewed_bbox is not None:
        x, y, box_width, box_height = reviewed_bbox
        cv2.rectangle(
            annotated, (x, y), (x + box_width, y + box_height), (255, 0, 255), 2
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(args.output), annotated):
        raise RuntimeError(f"could not write {args.output}")
    result = {
        "type": "depth_foreground_candidates",
        "safety": "camera-only offline snapshot analysis; not robot targets",
        "height_range_mm": [args.min_height_mm, args.max_height_mm],
        "reference_plane_rms_mm": depth_pose["plane_rms_mm"],
        "pickup_roi_table_mm": pickup_roi,
        "pickup_candidate_filter": pickup_candidate_filter,
        "selected_candidate": selected,
        "selection_note": "foreground proposal only; identity and grasp pose are unverified",
        "candidates": candidates,
    }
    if args.yolo_label_output:
        if selected is None:
            raise RuntimeError("cannot export a YOLO label without a selected candidate")
        source_bbox = selected["bbox_xywh"]
        yolo_bbox = bbox_to_yolo(
            reviewed_bbox if reviewed_bbox is not None else source_bbox,
            width,
            height,
            args.bbox_margin_px,
        )
        label = f"{args.yolo_class_id} " + " ".join(
            f"{value:.8f}" for value in yolo_bbox
        )
        args.yolo_label_output.parent.mkdir(parents=True, exist_ok=True)
        args.yolo_label_output.write_text(label + "\n", encoding="utf-8")
        result["yolo_pseudo_label"] = {
            "class_id": args.yolo_class_id,
            "bbox_margin_px": args.bbox_margin_px,
            "normalized_xywh": [round(value, 8) for value in yolo_bbox],
            "review_required": True,
            "source_candidate_bbox_xywh": source_bbox,
            "reviewed_bbox_xywh": reviewed_bbox,
            "review_note": args.review_note if reviewed_bbox is not None else None,
        }
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(
            json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}")
        raise SystemExit(1)
