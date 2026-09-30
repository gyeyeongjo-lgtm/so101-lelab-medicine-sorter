#!/usr/bin/env python3
"""Offline diagnostic for ArUco edge-gap measurements mistaken for center distances.

Assumes the four black marker squares are aligned with the table axes. This is
only a diagnostic: it neither changes the active camera config nor authorizes
robot motion. Confirm center-to-center distances before adopting any result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from scripts.fit_robot_world_from_joint_samples import load_reviewed_pairs
from scripts.fit_robot_world_tcp_transform import build_result


EDGES = ((0, 1), (1, 2), (2, 3), (3, 0), (0, 2), (1, 3))
THRESHOLDS = {
    "max_rmse_mm": 5.0,
    "max_error_mm": 8.0,
    "max_condition_number": 1000.0,
    "max_tcp_offset_mm": 200.0,
}


def marker_centers_from_edge_gaps(markers: dict) -> tuple[dict[int, np.ndarray], dict[str, float]]:
    """Fit center positions to shortest black-square boundary gaps in millimetres."""
    gaps = markers["reference_measurements_mm"]
    size = {
        index: float(markers.get("marker_size_by_id_mm", {}).get(str(index), markers["marker_size_mm"]))
        for index in range(4)
    }
    measured = {(a, b): float(gaps[f"{a}-{b}"]) for a, b in EDGES}
    if any(value <= 0 for value in measured.values()) or any(value <= 0 for value in size.values()):
        raise ValueError("marker size and edge gaps must be positive")
    width = measured[0, 1] + (size[0] + size[1]) / 2

    def centers(parameters: np.ndarray) -> dict[int, np.ndarray]:
        return {
            0: np.array([0.0, 0.0]),
            1: np.array([width, 0.0]),
            2: parameters[:2],
            3: parameters[2:],
        }

    def residual(parameters: np.ndarray) -> np.ndarray:
        points = centers(parameters)
        differences = []
        for (a, b), distance in measured.items():
            half_width_sum = (size[a] + size[b]) / 2
            separation = np.maximum(np.abs(points[a] - points[b]) - half_width_sum, 0.0)
            differences.append(float(np.linalg.norm(separation)) - distance)
        return np.array(differences)

    height = (
        measured[1, 2] + (size[1] + size[2]) / 2
        + measured[3, 0] + (size[3] + size[0]) / 2
    ) / 2
    parameters = np.array([width, height, 0.0, height], dtype=float)
    damping = 1e-3
    for _ in range(100):
        current = residual(parameters)
        epsilon = 1e-4
        jacobian = np.column_stack(
            [(residual(parameters + np.eye(4)[axis] * epsilon) - current) / epsilon for axis in range(4)]
        )
        step = np.linalg.solve(jacobian.T @ jacobian + damping * np.eye(4), -jacobian.T @ current)
        candidate = parameters + step
        if float(residual(candidate) @ residual(candidate)) < float(current @ current):
            parameters = candidate
            damping = max(damping / 3, 1e-9)
        else:
            damping *= 10
        if float(np.linalg.norm(step)) < 1e-8:
            break
    fitted = residual(parameters)
    return centers(parameters), {
        f"{a}-{b}": float(fitted[index]) for index, (a, b) in enumerate(EDGES)
    }


def four_point_homography(old: dict[int, np.ndarray], new: dict[int, np.ndarray]) -> np.ndarray:
    rows = []
    values = []
    for index in range(4):
        x, y = old[index]
        u, v = new[index]
        rows.extend(([x, y, 1, 0, 0, 0, -u * x, -u * y], [0, 0, 0, x, y, 1, -v * x, -v * y]))
        values.extend((u, v))
    return np.r_[np.linalg.solve(np.asarray(rows), np.asarray(values)), 1.0].reshape(3, 3)


def corrected_xy(homography: np.ndarray, xy: list[float]) -> list[float]:
    projected = homography @ np.array([xy[0], xy[1], 1.0])
    return (projected[:2] / projected[2]).tolist()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--pairs", required=True, type=Path)
    parser.add_argument("--urdf", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output already exists; never overwrite a diagnostic")
    if not args.output.parent.is_dir():
        parser.error("output parent does not exist")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    markers = config["markers"]
    old = {index: np.asarray(markers["reference_centers_mm"][str(index)][:2], dtype=float) for index in range(4)}
    new, edge_residuals = marker_centers_from_edge_gaps(markers)
    transform = four_point_homography(old, new)
    pairs, _ = load_reviewed_pairs(args.pairs, args.urdf)
    for pair in pairs["pairs"]:
        pair["world_mm"] = corrected_xy(transform, pair["world_mm"][:2]) + [0.0]
    fit = build_result(pairs, THRESHOLDS)
    output = {
        "status": "PROVISIONAL_EDGE_GAP_DIAGNOSTIC_NOT_FOR_MOTION",
        "assumption": "measured distances are shortest gaps between axis-aligned black marker squares, not center distances",
        "marker_centers_mm": {str(index): point.tolist() for index, point in new.items()},
        "edge_gap_residuals_mm": edge_residuals,
        "corrected_world_points_mm": {pair["name"]: pair["world_mm"] for pair in pairs["pairs"]},
        "fit": fit,
        "source_config_sha256": hashlib.sha256(args.config.read_bytes()).hexdigest(),
        "source_pairs_sha256": hashlib.sha256(args.pairs.read_bytes()).hexdigest(),
        "source_urdf_sha256": hashlib.sha256(args.urdf.read_bytes()).hexdigest(),
        "robot_enabled": False,
        "motion_authorized": False,
        "note": "Do not edit the active reference config from this estimate alone. Independently measure marker center distances and validate camera reprojection/holdout.",
    }
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(f"{fit['status']} provisional_rmse_mm={fit['rmse_mm']:.3f} max_error_mm={fit['max_error_mm']:.3f} robot_enabled=false")
    return 0 if not fit["rejection_reasons"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
