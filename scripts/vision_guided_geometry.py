"""Read-only geometry gates for fixed-layout bottle identity and 2D teach calibration.

No robot connection or motion API is imported here. A table-to-robot fit is usable
only with independently measured, verified TCP pairs and a separate hold-out.
"""

from __future__ import annotations

import math

import numpy as np


def nearest_table_slot(table_xy_mm: list[float], config: dict) -> dict:
    if config.get("schema_version") != 1 or config.get("unit") != "mm":
        raise ValueError("invalid table slot configuration")
    anchors = config.get("slots")
    if not isinstance(anchors, dict) or set(anchors) != {"A", "B", "C"}:
        raise ValueError("table slot anchors must contain A/B/C")
    point = np.asarray(table_xy_mm, dtype=float)
    if point.shape != (2,) or not np.isfinite(point).all():
        raise ValueError("invalid table XY")
    distances = []
    for label, anchor in anchors.items():
        anchor_xy = np.asarray(anchor, dtype=float)
        if anchor_xy.shape != (2,) or not np.isfinite(anchor_xy).all():
            raise ValueError(f"invalid {label} table anchor")
        distances.append((float(np.linalg.norm(point - anchor_xy)), label))
    distances.sort()
    nearest, label = distances[0]
    gap = distances[1][0] - nearest
    maximum = float(config.get("max_distance_mm", float("nan")))
    minimum_gap = float(config.get("minimum_runner_up_gap_mm", float("nan")))
    if not all(math.isfinite(value) and value > 0 for value in (maximum, minimum_gap)):
        raise ValueError("invalid table slot gates")
    return {
        "identity": label if nearest <= maximum and gap >= minimum_gap else None,
        "nearest_slot": label,
        "distance_to_slot_mm": round(nearest, 3),
        "runner_up_gap_mm": round(gap, 3),
        "status": "PROVISIONAL_SLOT_MATCH" if nearest <= maximum and gap >= minimum_gap else "BLOCKED_AMBIGUOUS_OR_OUTSIDE_SLOT",
    }


def _xy(record: dict, key: str) -> np.ndarray:
    value = np.asarray(record.get(key), dtype=float)
    if value.shape != (2,) or not np.isfinite(value).all():
        raise ValueError(f"invalid {key}")
    return value


def fit_table_to_robot_xy(document: dict) -> dict:
    """Fit 4+ verified train points; score a physically independent hold-out."""
    if document.get("schema_version") != 1 or document.get("unit") != "mm":
        raise ValueError("invalid table-to-robot calibration schema")
    tcp_offset = np.asarray(document.get("tcp_offset_gripper_link_mm"), dtype=float)
    if (document.get("tcp_offset_verified") is not True or
            tcp_offset.shape != (3,) or not np.isfinite(tcp_offset).all()):
        raise ValueError("verified 3D grasp TCP offset missing")
    records = document.get("points")
    if not isinstance(records, list):
        raise ValueError("calibration points missing")
    train = [r for r in records if isinstance(r, dict) and r.get("role") == "fit"]
    holdout = [r for r in records if isinstance(r, dict) and r.get("role") == "holdout"]
    if len(train) < 4 or len(holdout) < 1 or len(train) + len(holdout) != len(records):
        raise ValueError("at least four fit points and one independent hold-out required")
    names = [r.get("name") for r in records]
    if any(not isinstance(name, str) or not name for name in names) or len(names) != len(set(names)):
        raise ValueError("calibration point names must be unique")
    if any((r.get("contact_verified") is not True and not
            (r.get("alignment_verified") is True and r.get("hover_height_verified") is True)) or
           r.get("tcp_verified") is not True or r.get("image_joint_synchronized") is not True
           for r in records):
        raise ValueError("unverified point alignment, TCP or image-joint synchronization")
    table = np.stack([_xy(r, "table_xy_mm") for r in train])
    robot = np.stack([_xy(r, "robot_tcp_xy_mm") for r in train])
    if np.linalg.matrix_rank(table - table.mean(axis=0)) != 2 or np.ptp(table, axis=0).min() < 80.0:
        raise ValueError("fit points not spread across both table axes")
    pairwise = np.linalg.norm(table[:, None, :] - table[None, :, :], axis=2)
    pairwise[np.diag_indices_from(pairwise)] = np.inf
    if float(pairwise.min()) < 50.0:
        raise ValueError("fit points must be spatially separated")
    centered_table = table - table.mean(axis=0)
    centered_robot = robot - robot.mean(axis=0)
    u, _, vt = np.linalg.svd(centered_table.T @ centered_robot)
    correction = np.eye(2)
    correction[1, 1] = np.linalg.det(u @ vt)
    rotation = u @ correction @ vt  # row-vector SE(2), never a reflection
    translation = robot.mean(axis=0) - table.mean(axis=0) @ rotation
    train_error = np.linalg.norm(table @ rotation + translation - robot, axis=1)
    hold_table = np.stack([_xy(r, "table_xy_mm") for r in holdout])
    hold_robot = np.stack([_xy(r, "robot_tcp_xy_mm") for r in holdout])
    if float(np.min(np.linalg.norm(hold_table[:, None, :] - table[None, :, :], axis=2))) < 30.0:
        raise ValueError("hold-out must be a different table point")
    hold_error = np.linalg.norm(hold_table @ rotation + translation - hold_robot, axis=1)
    max_train = float(train_error.max())
    max_hold = float(hold_error.max())
    rms_train = float(np.sqrt(np.mean(train_error ** 2)))
    passed = rms_train <= 5.0 and max_train <= 8.0 and max_hold <= 8.0
    return {
        "status": "ACCEPTED_HOLDOUT_PASS" if passed else "REJECTED_FIT_OR_HOLDOUT",
        "model": "SE2_ROTATION_TRANSLATION_NO_SCALE",
        "determinant": round(float(np.linalg.det(rotation)), 6),
        "rotation_row_xy": rotation.tolist(),
        "translation_xy_mm": translation.tolist(),
        "train_rms_mm": round(rms_train, 3),
        "train_max_mm": round(max_train, 3),
        "holdout_max_mm": round(max_hold, 3),
        "holdout_errors_mm": {r["name"]: round(float(e), 3) for r, e in zip(holdout, hold_error)},
        "fit_count": len(train),
        "holdout_count": len(holdout),
        "tcp_offset_gripper_link_mm": tcp_offset.tolist(),
        "motion_geometry_eligible": passed,
    }


def table_to_robot_xy(table_xy_mm: list[float], fit: dict) -> list[float]:
    if fit.get("status") != "ACCEPTED_HOLDOUT_PASS":
        raise ValueError("table-to-robot hold-out fit not accepted")
    point = np.asarray(table_xy_mm, dtype=float)
    rotation = np.asarray(fit["rotation_row_xy"], dtype=float)
    translation = np.asarray(fit["translation_xy_mm"], dtype=float)
    if point.shape != (2,) or rotation.shape != (2, 2) or translation.shape != (2,) or not np.isfinite(point).all():
        raise ValueError("invalid table-to-robot projection")
    return [round(float(value), 3) for value in point @ rotation + translation]


def basket_opening_table_xy(marker_table_xy_mm: list[float], basket: dict) -> dict:
    if basket.get("marker_id") != 4 or basket.get("color") != "red":
        raise ValueError("red basket marker binding invalid")
    marker = np.asarray(marker_table_xy_mm, dtype=float)
    offset = np.asarray(basket.get("opening_offset_from_marker_table_mm"), dtype=float)
    if marker.shape != (2,) or offset.shape != (2,) or not np.isfinite(marker).all() or not np.isfinite(offset).all():
        raise ValueError("basket opening offset not measured")
    return {
        "opening_table_xy_mm": [round(float(v), 3) for v in marker + offset],
        "offset_verified": basket.get("opening_offset_verified") is True,
        "status": "VERIFIED_OFFSET" if basket.get("opening_offset_verified") is True else "DIAGNOSTIC_OFFSET_ONLY",
    }
