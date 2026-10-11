"""Recover the established table frame when one reference card has shifted.

ID0, ID1 and ID3 must retain a single planar relationship to the saved
reference frame. Their twelve matching corners fit a current→reference image
homography; ID2 is measured as a hold-out and is never silently used after it
moves. This is camera geometry only, not a robot transform.
"""

from __future__ import annotations

import math

import numpy as np

from medicine_yolo_web import detect_table_markers, project_table_xy


STABLE_IDS = (0, 1, 3)
REFERENCE_IDS = (0, 1, 2, 3)


def reference_homography(cv2, reference_corners: dict, current_corners: dict,
                         table_centers: dict, *, require_id4: bool = True) -> tuple[np.ndarray, dict]:
    if not set(REFERENCE_IDS).issubset(reference_corners):
        raise ValueError("saved reference frame lacks ID0–3")
    # Five-point capture only uses ID0/1/3 for the live homography.  ID2 is a
    # diagnostic hold-out and may be hidden by the arm at a calibration mark.
    required = set(STABLE_IDS) | ({2, 4} if require_id4 else set())
    if not required.issubset(current_corners):
        raise ValueError("live frame lacks required stable/table/basket ArUco IDs")
    old_centers = np.asarray([reference_corners[i].reshape(4, 2).mean(axis=0)
                              for i in REFERENCE_IDS], dtype=np.float64)
    table = np.asarray([table_centers[i] for i in REFERENCE_IDS], dtype=np.float64)
    old_to_table, _ = cv2.findHomography(old_centers, table, method=0)
    current_points = np.concatenate([current_corners[i].reshape(4, 2) for i in STABLE_IDS]).astype(np.float64)
    old_points = np.concatenate([reference_corners[i].reshape(4, 2) for i in STABLE_IDS]).astype(np.float64)
    current_to_old, _ = cv2.findHomography(current_points, old_points, method=0)
    if old_to_table is None or current_to_old is None:
        raise ValueError("stable-marker homography unavailable")
    mapped = cv2.perspectiveTransform(current_points.reshape(-1, 1, 2), current_to_old).reshape(-1, 2)
    errors = np.linalg.norm(mapped - old_points, axis=1)
    rms = float(np.sqrt(np.mean(errors ** 2)))
    maximum = float(errors.max())
    center_drift = max(float(np.linalg.norm(
        current_corners[i].reshape(4, 2).mean(axis=0) -
        reference_corners[i].reshape(4, 2).mean(axis=0))) for i in STABLE_IDS)
    if (not all(math.isfinite(value) for value in (rms, maximum, center_drift)) or
            rms > 2.0 or maximum > 4.0 or center_drift > 5.0):
        raise ValueError(f"stable ArUco geometry changed: rms={rms:.3f}px "
                         f"max={maximum:.3f}px center_drift={center_drift:.3f}px")
    id2_drift = None
    if 2 in current_corners:
        id2_old = reference_corners[2].reshape(4, 2).mean(axis=0)
        id2_current = current_corners[2].reshape(4, 2).mean(axis=0)
        id2_projected = cv2.perspectiveTransform(
            id2_current.reshape(1, 1, 2), current_to_old)[0, 0]
        id2_drift = float(np.linalg.norm(id2_projected - id2_old))
    homography = old_to_table @ current_to_old
    homography /= homography[2, 2]
    if not np.isfinite(homography).all():
        raise ValueError("invalid table homography")
    quality = {
        "model": "saved_ID0-3_table_frame_via_stable_ID0_1_3_corners",
        "stable_ids": list(STABLE_IDS),
        "stable_corner_rms_px": round(rms, 3),
        "stable_corner_max_px": round(maximum, 3),
        "stable_center_max_drift_px": round(center_drift, 3),
        "id2_holdout_drift_px": round(id2_drift, 3) if id2_drift is not None else None,
        "id2_used_in_live_fit": False,
    }
    return homography, quality


class StableTableReference:
    def __init__(self, cv2, np_module, mapper, reference_image):
        self.cv2, self.np, self.mapper = cv2, np_module, mapper
        image = cv2.imread(str(reference_image))
        if image is None or image.shape[:2] != (480, 640):
            raise ValueError("saved 640x480 reference image unavailable")
        self.reference_corners, _ = detect_table_markers(
            cv2, mapper.detector, image, set(mapper.reference_ids))
        if not set(REFERENCE_IDS).issubset(self.reference_corners):
            raise ValueError("saved reference image lacks ID0–3")

    def analyze(self, image, *, require_id4: bool = True) -> dict:
        corners, fallback = detect_table_markers(
            self.cv2, self.mapper.detector, image,
            set(self.mapper.reference_ids) | set(self.mapper.basket_ids))
        homography, quality = reference_homography(
            self.cv2, self.reference_corners, corners, self.mapper.reference_centers,
            require_id4=require_id4)
        centers = {marker_id: marker_corners.reshape(4, 2).mean(axis=0)
                   for marker_id, marker_corners in corners.items()}
        return {"homography": homography, "quality": quality,
                "centers_px": centers, "aruco_ids": sorted(corners),
                "equalized_fallback_ids": fallback,
                "id4_marker_table_xy_mm": (
                    list(project_table_xy(self.np, homography, *centers[4]))
                    if 4 in centers else None)}
