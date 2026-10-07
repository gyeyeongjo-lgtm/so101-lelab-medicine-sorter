#!/usr/bin/env python3
"""Compare two local ceiling JPEGs for a fixed ID4/5/6 basket layout.

Pixel tolerances are diagnostic only. Matching photos do not establish a
height-corrected basket mouth, robot coordinates, or a safe movement path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import cv2
import numpy as np

from scripts.audit_basket_body_candidate import propose_color_bbox


REFERENCE_IDS = (0, 1, 2, 3)
BASKET_IDS = (4, 5, 6)
BODY_PROFILES = {
    4: ((275, 245, 350, 385), (88, 65, 45), (125, 255, 240)),
    5: ((340, 245, 425, 385), (8, 70, 40), (37, 255, 230)),
    6: ((410, 245, 495, 385), (38, 75, 45), (75, 255, 240)),
}


def measure_scene(path: Path) -> dict:
    raw = path.read_bytes()
    image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if image is None or image.shape[:2] != (480, 640):
        raise ValueError("expected a 640x480 ceiling JPEG")
    board_median_gray = float(np.median(cv2.cvtColor(image[185:460, 185:530], cv2.COLOR_BGR2GRAY)))
    low_light = board_median_gray < 100  # Diagnostic color-analysis gate, not an exposure setting.
    parameters = cv2.aruco.DetectorParameters()
    parameters.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    detector = cv2.aruco.ArucoDetector(
        cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50), parameters)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    corners, ids, _ = detector.detectMarkers(gray)
    found = {} if ids is None else {int(marker_id): corner
                                    for corner, marker_id in zip(corners, ids.flatten())}
    recovered = []
    missing = (set(REFERENCE_IDS) | set(BASKET_IDS)) - set(found)
    if missing:
        retry_corners, retry_ids, _ = detector.detectMarkers(cv2.equalizeHist(gray))
        if retry_ids is not None:
            for corner, marker_id in zip(retry_corners, retry_ids.flatten()):
                marker_id = int(marker_id)
                if marker_id in missing:
                    found[marker_id] = corner
                    recovered.append(marker_id)
    centers = {marker_id: [float(value) for value in corner.reshape(4, 2).mean(axis=0)]
               for marker_id, corner in found.items()}
    body_boxes = {str(marker_id): None if low_light else propose_color_bbox(image, *profile)["bbox_xywh_px"]
                  for marker_id, profile in BODY_PROFILES.items()}
    return {"sha256": hashlib.sha256(raw).hexdigest(),
            "marker_centers_px": centers,
            "equalized_fallback_ids": sorted(recovered),
            "board_median_gray": board_median_gray,
            "low_light_for_color_candidate": low_light,
            "body_bboxes_by_id_candidate": body_boxes}


def compare_measurements(reference: dict, current: dict) -> dict:
    reference_centers = reference["marker_centers_px"]
    current_centers = current["marker_centers_px"]
    required = set(REFERENCE_IDS) | set(BASKET_IDS)
    missing = sorted(required - set(reference_centers) | required - set(current_centers))
    ref_boxes = reference["body_bboxes_by_id_candidate"]
    current_boxes = current["body_bboxes_by_id_candidate"]
    missing_bodies = [marker_id for marker_id in BASKET_IDS
                      if ref_boxes.get(str(marker_id)) is None or current_boxes.get(str(marker_id)) is None]
    if missing:
        return {"status": "INDETERMINATE", "missing_marker_ids": missing,
                "missing_body_candidate_ids": missing_bodies,
                "visual_layout_match_diagnostic": False,
                "marker_layout_match_diagnostic": False,
                "basket_pose_authorized": False, "robot_enabled": False,
                "motion_authorized": False}
    def distance(first: list[float], second: list[float]) -> float:
        return math.dist(first, second)
    reference_drift = max(distance(reference_centers[marker_id], current_centers[marker_id])
                          for marker_id in REFERENCE_IDS)
    basket_drift = {str(marker_id): round(distance(reference_centers[marker_id],
                                                     current_centers[marker_id]), 3)
                    for marker_id in BASKET_IDS}
    # This pixel tolerance is a change detector, not physical pose accuracy.
    marker_match = reference_drift <= 2 and all(drift <= 3 for drift in basket_drift.values())
    if missing_bodies:
        return {"status": "MARKERS_MATCH_BODY_UNVERIFIED" if marker_match else "MARKER_LAYOUT_CHANGED",
                "max_reference_marker_drift_px": round(reference_drift, 3),
                "basket_marker_drift_px": basket_drift,
                "max_basket_marker_drift_px": max(basket_drift.values()),
                "missing_body_candidate_ids": missing_bodies,
                "marker_layout_match_diagnostic": marker_match,
                "visual_layout_match_diagnostic": False,
                "id4_id6_basket_bodies_verified": False,
                "basket_mouth_corners_verified": False,
                "basket_pose_authorized": False, "robot_enabled": False,
                "motion_authorized": False}
    def bbox_center(box: list[int]) -> list[float]:
        return [box[0] + box[2] / 2, box[1] + box[3] / 2]
    body_center_drift = {str(marker_id): round(distance(
        bbox_center(ref_boxes[str(marker_id)]), bbox_center(current_boxes[str(marker_id)])), 3)
        for marker_id in BASKET_IDS}
    body_size_change = {str(marker_id): max(
        abs(ref_boxes[str(marker_id)][2] - current_boxes[str(marker_id)][2]),
        abs(ref_boxes[str(marker_id)][3] - current_boxes[str(marker_id)][3]))
        for marker_id in BASKET_IDS}
    # These exploratory pixel bounds only detect gross scene changes; they are not safety margins.
    diagnostic_match = (marker_match and all(drift <= 3 for drift in body_center_drift.values())
                        and all(change <= 4 for change in body_size_change.values()))
    return {"status": "VISUAL_LAYOUT_MATCH_DIAGNOSTIC" if diagnostic_match else "VISUAL_LAYOUT_CHANGED",
            "max_reference_marker_drift_px": round(reference_drift, 3),
            "basket_marker_drift_px": basket_drift,
            "max_basket_marker_drift_px": max(basket_drift.values()),
            "body_bbox_center_drift_px_by_id": body_center_drift,
            "max_body_bbox_center_drift_px": max(body_center_drift.values()),
            "body_bbox_size_change_px_by_id": body_size_change,
            "max_body_bbox_size_change_px": max(body_size_change.values()),
            "marker_layout_match_diagnostic": marker_match,
            "visual_layout_match_diagnostic": diagnostic_match,
            "id4_id6_basket_bodies_verified": False,
            "basket_mouth_corners_verified": False,
            "basket_pose_authorized": False, "robot_enabled": False,
            "motion_authorized": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--current", type=Path, required=True)
    args = parser.parse_args()
    try:
        reference = measure_scene(args.reference)
        current = measure_scene(args.current)
        result = {"reference_sha256": reference["sha256"],
                  "current_sha256": current["sha256"],
                  "reference_marker_centers_px": reference["marker_centers_px"],
                  "current_marker_centers_px": current["marker_centers_px"],
                  "reference_equalized_fallback_ids": reference["equalized_fallback_ids"],
                  "current_equalized_fallback_ids": current["equalized_fallback_ids"],
                  "reference_board_median_gray": reference["board_median_gray"],
                  "current_board_median_gray": current["board_median_gray"],
                  "reference_low_light_for_color_candidate": reference["low_light_for_color_candidate"],
                  "current_low_light_for_color_candidate": current["low_light_for_color_candidate"],
                  "reference_body_bboxes_by_id_candidate": reference["body_bboxes_by_id_candidate"],
                  "current_body_bboxes_by_id_candidate": current["body_bboxes_by_id_candidate"],
                  **compare_measurements(reference, current)}
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(2, f"fixed-scene audit failed: {error}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
