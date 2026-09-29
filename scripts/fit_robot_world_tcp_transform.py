#!/usr/bin/env python3
"""Jointly fit a gripper-link TCP offset and dry-run World-to-Base transform.

For each reviewed touch sample the following relation is used in millimetres:

    R_B_W @ p_W + t_B_W = p_B_link + R_B_link @ p_link_tcp

The result is diagnostic only. It never authorizes robot motion.
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pairs", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--max-rmse-mm", type=float, default=5.0)
    parser.add_argument("--max-error-mm", type=float, default=8.0)
    parser.add_argument("--max-condition-number", type=float, default=1000.0)
    parser.add_argument("--max-tcp-offset-mm", type=float, default=200.0)
    return parser.parse_args()


def _finite_vector(value: object, length: int, label: str) -> np.ndarray:
    if not isinstance(value, list) or len(value) != length:
        raise ValueError(f"{label} must contain {length} numbers")
    array = np.asarray(value, dtype=np.float64)
    if array.shape != (length,) or not np.isfinite(array).all():
        raise ValueError(f"{label} must contain {length} finite numbers")
    return array


def _rotation(value: object, label: str) -> np.ndarray:
    array = np.asarray(value, dtype=np.float64)
    if array.shape != (3, 3) or not np.isfinite(array).all():
        raise ValueError(f"{label} must be a finite 3x3 matrix")
    if not np.allclose(array.T @ array, np.eye(3), atol=1e-5):
        raise ValueError(f"{label} is not orthonormal")
    if not math.isclose(float(np.linalg.det(array)), 1.0, abs_tol=1e-5):
        raise ValueError(f"{label} determinant must be +1")
    return array


def validate_pairs(document: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str]]:
    if document.get("unit") != "mm":
        raise ValueError("teach point unit must be mm")
    if document.get("convention") != "T_B_W transforms a point from World into Robot Base":
        raise ValueError("unexpected transform convention")
    records = document.get("pairs")
    if not isinstance(records, list):
        raise ValueError("pairs must be a list")
    requested_names = document.get("fit_pair_names")
    if requested_names is not None:
        if (
            not isinstance(requested_names, list)
            or not requested_names
            or any(not isinstance(name, str) or not name.strip() for name in requested_names)
            or len(set(requested_names)) != len(requested_names)
        ):
            raise ValueError("fit_pair_names must be a non-empty list of unique names")
        by_name = {
            record.get("name"): record
            for record in records
            if isinstance(record, dict) and isinstance(record.get("name"), str)
        }
        missing = [name for name in requested_names if name not in by_name]
        if missing:
            raise ValueError(f"fit_pair_names not found: {missing}")
        records = [by_name[name] for name in requested_names]
    if not 4 <= len(records) <= 16:
        raise ValueError("4 to 16 reviewed teach samples are required")
    names: list[str] = []
    world: list[np.ndarray] = []
    origins: list[np.ndarray] = []
    rotations: list[np.ndarray] = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"pair {index} must be an object")
        name = record.get("name")
        if not isinstance(name, str) or not name.strip() or name in names:
            raise ValueError("teach point names must be non-empty and unique")
        names.append(name)
        world.append(_finite_vector(record.get("world_mm"), 3, f"{name}.world_mm"))
        origins.append(
            _finite_vector(record.get("gripper_link_origin_mm"), 3, f"{name}.gripper_link_origin_mm")
        )
        rotations.append(_rotation(record.get("gripper_link_rotation"), f"{name}.gripper_link_rotation"))
    world_array = np.asarray(world)
    if np.linalg.matrix_rank(world_array - world_array.mean(axis=0)) < 2:
        raise ValueError("World teach samples must span at least two dimensions")
    return world_array, np.asarray(origins), np.asarray(rotations), names


def rotation_exp(vector: np.ndarray) -> np.ndarray:
    angle = float(np.linalg.norm(vector))
    if angle < 1e-12:
        return np.eye(3)
    x, y, z = vector / angle
    skew = np.array([[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]])
    return np.eye(3) + math.sin(angle) * skew + (1.0 - math.cos(angle)) * (skew @ skew)


def kabsch_rotation(source: np.ndarray, target: np.ndarray) -> np.ndarray:
    covariance = (source - source.mean(axis=0)).T @ (target - target.mean(axis=0))
    u, _, vt = np.linalg.svd(covariance)
    rotation = vt.T @ u.T
    if np.linalg.det(rotation) < 0:
        vt[-1, :] *= -1
        rotation = vt.T @ u.T
    return rotation


def solve_linear(
    world: np.ndarray,
    origins: np.ndarray,
    link_rotations: np.ndarray,
    world_rotation: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    design = np.vstack(
        [np.hstack((np.eye(3), -link_rotation)) for link_rotation in link_rotations]
    )
    right_hand = np.concatenate(
        [origins[index] - world_rotation @ world[index] for index in range(len(world))]
    )
    solution = np.linalg.lstsq(design, right_hand, rcond=None)[0]
    return design @ solution - right_hand, solution[:3], solution[3:]


def fit_joint_tcp(
    world: np.ndarray,
    origins: np.ndarray,
    link_rotations: np.ndarray,
    *,
    max_iterations: int = 100,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, int]:
    rotation = kabsch_rotation(world, origins)
    damping = 1e-4
    iterations = 0
    for iterations in range(1, max_iterations + 1):
        residual, translation, tcp_offset = solve_linear(world, origins, link_rotations, rotation)
        epsilon = 1e-6
        jacobian = np.column_stack(
            [
                (
                    solve_linear(
                        world,
                        origins,
                        link_rotations,
                        rotation_exp(np.eye(3)[axis] * epsilon) @ rotation,
                    )[0]
                    - residual
                )
                / epsilon
                for axis in range(3)
            ]
        )
        step = np.linalg.solve(
            jacobian.T @ jacobian + damping * np.eye(3),
            -jacobian.T @ residual,
        )
        candidate = rotation_exp(step) @ rotation
        candidate_residual = solve_linear(world, origins, link_rotations, candidate)[0]
        if float(candidate_residual @ candidate_residual) < float(residual @ residual):
            rotation = candidate
            damping = max(damping / 3.0, 1e-12)
        else:
            damping *= 10.0
        if np.linalg.norm(step) < 1e-10:
            break
    _, translation, tcp_offset = solve_linear(world, origins, link_rotations, rotation)
    return rotation, translation, tcp_offset, iterations


def observability(
    world: np.ndarray,
    link_rotations: np.ndarray,
    world_rotation: np.ndarray,
) -> tuple[int, float, list[float]]:
    columns = []
    epsilon = 1e-5
    baseline = np.concatenate([world_rotation @ point for point in world])
    for axis in range(3):
        candidate = rotation_exp(np.eye(3)[axis] * epsilon) @ world_rotation
        columns.append((np.concatenate([candidate @ point for point in world]) - baseline) / epsilon)
    columns.extend(
        [
            np.tile(np.eye(3)[:, axis], len(world))
            for axis in range(3)
        ]
    )
    columns.extend(
        [
            np.concatenate([-rotation[:, axis] for rotation in link_rotations])
            for axis in range(3)
        ]
    )
    jacobian = np.column_stack(columns)
    singular_values = np.linalg.svd(jacobian, compute_uv=False)
    rank = int(np.linalg.matrix_rank(jacobian))
    condition = float("inf") if singular_values[-1] <= 0 else float(singular_values[0] / singular_values[-1])
    return rank, condition, singular_values.tolist()


def build_result(document: dict, thresholds: dict[str, float]) -> dict:
    world, origins, link_rotations, names = validate_pairs(document)
    rotation, translation, tcp_offset, iterations = fit_joint_tcp(world, origins, link_rotations)
    world_tcp = (rotation @ world.T).T + translation
    link_tcp = np.asarray(
        [origins[index] + link_rotations[index] @ tcp_offset for index in range(len(world))]
    )
    errors = np.linalg.norm(world_tcp - link_tcp, axis=1)
    rmse = float(np.sqrt(np.mean(np.square(errors))))
    max_error = float(errors.max())
    rank, condition, singular_values = observability(world, link_rotations, rotation)
    tcp_norm = float(np.linalg.norm(tcp_offset))
    rejection_reasons = []
    if rmse > thresholds["max_rmse_mm"]:
        rejection_reasons.append("rmse_above_limit")
    if max_error > thresholds["max_error_mm"]:
        rejection_reasons.append("max_error_above_limit")
    if rank < 9:
        rejection_reasons.append("jacobian_rank_below_9")
    if condition > thresholds["max_condition_number"]:
        rejection_reasons.append("condition_number_above_limit")
    if tcp_norm > thresholds["max_tcp_offset_mm"]:
        rejection_reasons.append("tcp_offset_above_limit")
    transform = np.eye(4)
    transform[:3, :3] = rotation
    transform[:3, 3] = translation
    accepted = not rejection_reasons
    return {
        "schema_version": 1,
        "status": (
            "PROVISIONAL_FIT_REQUIRES_INDEPENDENT_DRY_RUN"
            if accepted
            else "REJECTED_NEEDS_MORE_OR_BETTER_TEACH_SAMPLES"
        ),
        "unit": "mm",
        "convention": "T_B_W transforms a point from World into Robot Base",
        "method": "joint nonlinear least squares for T_B_W and fixed gripper-link TCP offset",
        "T_B_W": transform.tolist(),
        "tcp_offset_gripper_link_mm": tcp_offset.tolist(),
        "tcp_offset_norm_mm": tcp_norm,
        "rotation_determinant": float(np.linalg.det(rotation)),
        "rmse_mm": rmse,
        "max_error_mm": max_error,
        "jacobian_rank": rank,
        "condition_number": condition,
        "jacobian_singular_values": singular_values,
        "iterations": iterations,
        "thresholds": thresholds,
        "rejection_reasons": rejection_reasons,
        "points": [
            {
                "name": name,
                "residual_mm": float(error),
                "tcp_base_from_world_mm": world_point.tolist(),
                "tcp_base_from_link_mm": link_point.tolist(),
            }
            for name, error, world_point, link_point in zip(names, errors, world_tcp, link_tcp)
        ],
        "source_pairs": len(names),
        "source_pair_names": names,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "robot_enabled": False,
        "motion_authorized": False,
        "note": "Never use a rejected fit for motion. Even an accepted fit requires independent dry-run validation.",
    }


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise ValueError("output already exists; calibration results are never overwritten")
    if not args.output.parent.is_dir():
        raise ValueError("output parent does not exist")
    thresholds = {
        "max_rmse_mm": args.max_rmse_mm,
        "max_error_mm": args.max_error_mm,
        "max_condition_number": args.max_condition_number,
        "max_tcp_offset_mm": args.max_tcp_offset_mm,
    }
    document = json.loads(args.pairs.read_text(encoding="utf-8"))
    result = build_result(document, thresholds)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        f"{result['status']} pairs={result['source_pairs']} "
        f"rmse_mm={result['rmse_mm']:.3f} max_error_mm={result['max_error_mm']:.3f} "
        f"condition={result['condition_number']:.1f} robot_enabled=false"
    )
    return 0 if not result["rejection_reasons"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
