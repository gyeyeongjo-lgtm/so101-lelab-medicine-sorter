#!/usr/bin/env python3
"""Offline brown-basket body proposal from local JPEGs; never a robot target.

The fixed ROI and HSV bounds were explored on one scene and are intentionally
not a calibrated basket-mouth detector. Occlusion and lighting can invalidate it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from pathlib import Path

import cv2
import numpy as np

from scripts.audit_teleop_trace import audit as audit_trace


ROI_XYXY = (300, 240, 440, 380)
HSV_LOWER = (8, 70, 40)
HSV_UPPER = (37, 255, 230)
MIN_COMPONENT_AREA_PX = 1000
DEFAULT_URDF = Path(__file__).resolve().parents[1] / "configs/so101_installed_urdf_limits_20261005.json"


def propose_color_bbox(image: np.ndarray, roi_xyxy: tuple[int, int, int, int],
                       hsv_lower: tuple[int, int, int], hsv_upper: tuple[int, int, int],
                       min_component_area_px: int = MIN_COMPONENT_AREA_PX) -> dict:
    if image is None or image.ndim != 3 or image.shape[2] != 3 or image.shape[:2] != (480, 640):
        raise ValueError("expected a 640x480 BGR image")
    x1, y1, x2, y2 = roi_xyxy
    if not 0 <= x1 < x2 <= 640 or not 0 <= y1 < y2 <= 480:
        raise ValueError("invalid ROI")
    hsv = cv2.cvtColor(image[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array(hsv_lower, np.uint8), np.array(hsv_upper, np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask)
    candidates = [row for row in stats[1:count] if row[cv2.CC_STAT_AREA] >= min_component_area_px]
    if not candidates:
        return {"status": "NO_BODY_CANDIDATE", "bbox_xywh_px": None, "mask_area_px": 0,
                "candidate_only": True, "basket_mouth_detected": False,
                "basket_pose_authorized": False, "robot_enabled": False,
                "motion_authorized": False}
    component = max(candidates, key=lambda row: row[cv2.CC_STAT_AREA])
    x, y, width, height, area = map(int, component)
    return {"status": "BODY_BBOX_CANDIDATE", "bbox_xywh_px": [x + x1, y + y1, width, height],
            "mask_area_px": area, "candidate_only": True,
            "basket_mouth_detected": False, "basket_pose_authorized": False,
            "robot_enabled": False, "motion_authorized": False}


def propose_body_bbox(image: np.ndarray) -> dict:
    """Legacy central brown-body proposal used for the earlier video audit."""
    return propose_color_bbox(image, ROI_XYXY, HSV_LOWER, HSV_UPPER)


def inspect_image(path: Path) -> dict:
    raw = path.read_bytes()
    image = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
    result = propose_body_bbox(image)
    return {"image": path.name, "sha256": hashlib.sha256(raw).hexdigest(), **result}


def summarize_trace(trace_dir: Path, limits_file: Path = DEFAULT_URDF) -> dict:
    integrity = audit_trace(trace_dir, limits_file)
    index = (trace_dir / "ceiling" / "frames.jsonl").read_text(encoding="utf-8").splitlines()
    if not index:
        raise ValueError("no verified ceiling frames")
    results = [inspect_image(trace_dir / "ceiling" / json.loads(line)["filename"]) for line in index]
    found = [row for row in results if row["bbox_xywh_px"] is not None]
    def extent(values: list[float]) -> list[float] | None:
        return [round(min(values), 3), round(statistics.median(values), 3), round(max(values), 3)] if values else None
    boxes = [row["bbox_xywh_px"] for row in found]
    return {
        "status": "OFFLINE_BODY_BBOX_EXPLORATION_ONLY",
        "trace": trace_dir.name,
        "trace_sha256": integrity["trace_sha256"],
        "urdf_audit_status": integrity["status"],
        "verified_ceiling_frames": len(index),
        "candidate_frames": len(found),
        "candidate_fraction": round(len(found) / len(index), 4),
        "center_x_px_min_median_max": extent([x + width / 2 for x, _, width, _ in boxes]),
        "center_y_px_min_median_max": extent([y + height / 2 for _, y, _, height in boxes]),
        "width_px_min_median_max": extent([float(width) for _, _, width, _ in boxes]),
        "height_px_min_median_max": extent([float(height) for _, _, _, height in boxes]),
        "basket_mouth_detected": False,
        "basket_pose_authorized": False,
        "robot_enabled": False,
        "motion_authorized": False,
        "caution": "Color-component bbox is not the inside opening, height-corrected center, orientation, or collision clearance.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace-dir", type=Path, action="append")
    parser.add_argument("--image", type=Path, action="append")
    parser.add_argument("--limits", type=Path, default=DEFAULT_URDF)
    args = parser.parse_args()
    if not args.trace_dir and not args.image:
        parser.error("provide --trace-dir or --image")
    try:
        results = [summarize_trace(path, args.limits) for path in args.trace_dir or []]
        results += [inspect_image(path) for path in args.image or []]
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        parser.exit(2, f"offline basket candidate audit failed: {error}\n")
    print(json.dumps(results, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
