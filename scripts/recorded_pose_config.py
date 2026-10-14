"""Pure helpers for three-sample canonical follower pose records.

This module never opens a robot port.  A separately approved recording runner
must supply three fresh follower samples and FK results after leader teleop has
ended.  Missing measurements are not represented by guessed pose values.
"""

from __future__ import annotations

from datetime import datetime
import math
from pathlib import Path
from statistics import fmean, pstdev
from typing import Mapping, Sequence

import yaml

if __package__:
    from scripts.staged_cycle_execution import JOINT_UNITS
else:
    from staged_cycle_execution import JOINT_UNITS


POSE_NAMES = ("HOME", "SAFE_HIGH", "PICK_READY", "C_PREAPPROACH_EMPIRICAL")
RETURN_POSE_NAMES = frozenset(("HOME", "SAFE_HIGH"))
RUNTIME_START_POSE = "PICK_READY"
POSE_ROLES = {
    "HOME": "STORAGE_PARKING_ONLY",
    "SAFE_HIGH": "RECOVERY_FALLBACK_OPTIONAL_TRANSPORT",
    "PICK_READY": "CANONICAL_RUNTIME_START_VISION_READY",
    "C_PREAPPROACH_EMPIRICAL": "HUMAN_TAUGHT_C_PRE_APPROACH_NOT_AUTOMATICALLY_REPLAYABLE",
}


def _validate_samples(samples: Sequence[Mapping[str, float]], label: str
                      ) -> list[dict[str, float]]:
    if len(samples) != 3:
        raise ValueError(f"{label}_requires_exactly_three_samples")
    result = []
    for sample in samples:
        if set(sample) != set(JOINT_UNITS):
            raise ValueError(f"{label}_joint_shape_invalid")
        converted = {name: float(sample[name]) for name in JOINT_UNITS}
        if any(not math.isfinite(value) for value in converted.values()):
            raise ValueError(f"{label}_nonfinite")
        result.append(converted)
    return result


def build_pose_record(
    *,
    name: str,
    raw_samples: Sequence[Mapping[str, float]],
    degree_samples: Sequence[Mapping[str, float]],
    fk_grasp_tcp_samples_mm: Sequence[Sequence[float]],
    recorded_at: str,
    note: str,
    temperature_samples_c: Sequence[Mapping[str, float]] | None = None,
    ideal_ik_joints_deg: Mapping[str, float] | None = None,
    ideal_ik_fk_grasp_tcp_mm: Sequence[float] | None = None,
) -> dict:
    """Summarize exactly three read-only samples without inventing precision."""
    if name not in POSE_NAMES:
        raise ValueError("pose_name_invalid")
    raw = _validate_samples(raw_samples, "raw")
    degrees = _validate_samples(degree_samples, "degree")
    if len(fk_grasp_tcp_samples_mm) != 3:
        raise ValueError("fk_requires_exactly_three_samples")
    fk = []
    for xyz in fk_grasp_tcp_samples_mm:
        if len(xyz) != 3:
            raise ValueError("fk_shape_invalid")
        row = [float(value) for value in xyz]
        if any(not math.isfinite(value) for value in row):
            raise ValueError("fk_nonfinite")
        fk.append(row)
    try:
        datetime.fromisoformat(recorded_at)
    except ValueError as error:
        raise ValueError("recorded_at_invalid") from error
    if not isinstance(note, str) or not note.strip():
        raise ValueError("pose_note_required")

    joints = {}
    for joint in JOINT_UNITS:
        raw_values = [sample[joint] for sample in raw]
        degree_values = [sample[joint] for sample in degrees]
        joints[joint] = {
            "raw_mean": fmean(raw_values),
            "degree_mean": fmean(degree_values),
            "raw_std": pstdev(raw_values),
            "degree_std": pstdev(degree_values),
        }
    result = {
        "name": name,
        "joints": joints,
        "fk_grasp_tcp_mm": {
            "x": fmean(row[0] for row in fk),
            "y": fmean(row[1] for row in fk),
            "z": fmean(row[2] for row in fk),
        },
        "recorded_at": recorded_at,
        "note": note.strip(),
        "sample_count": 3,
    }
    if temperature_samples_c is not None:
        temperatures = _validate_samples(temperature_samples_c, "temperature")
        result["temperature_c"] = {
            joint: {
                "mean": fmean(sample[joint] for sample in temperatures),
                "maximum": max(sample[joint] for sample in temperatures),
                "std": pstdev(sample[joint] for sample in temperatures),
            }
            for joint in JOINT_UNITS
        }
    if name == "C_PREAPPROACH_EMPIRICAL":
        if ideal_ik_joints_deg is None or ideal_ik_fk_grasp_tcp_mm is None:
            raise ValueError("empirical_pose_requires_ideal_ik_reference")
        if set(ideal_ik_joints_deg) != set(JOINT_UNITS) - {"gripper"}:
            raise ValueError("ideal_ik_joint_shape_invalid")
        ideal = {name: float(value) for name, value in ideal_ik_joints_deg.items()}
        if any(not math.isfinite(value) for value in ideal.values()):
            raise ValueError("ideal_ik_joint_nonfinite")
        if len(ideal_ik_fk_grasp_tcp_mm) != 3:
            raise ValueError("ideal_ik_fk_shape_invalid")
        ideal_xyz = [float(value) for value in ideal_ik_fk_grasp_tcp_mm]
        if any(not math.isfinite(value) for value in ideal_xyz):
            raise ValueError("ideal_ik_fk_nonfinite")
        actual_xyz = [result["fk_grasp_tcp_mm"][axis] for axis in "xyz"]
        xyz_delta = [actual - target for actual, target in zip(actual_xyz, ideal_xyz)]
        result["ideal_ik_reference"] = {
            "joints_deg": ideal,
            "joint_difference_empirical_minus_ideal_deg": {
                joint: result["joints"][joint]["degree_mean"] - ideal[joint]
                for joint in ideal
            },
            "fk_grasp_tcp_mm": dict(zip("xyz", ideal_xyz)),
            "task_space_difference_empirical_minus_ideal_mm": dict(zip("xyz", xyz_delta)),
            "task_space_position_error_norm_mm": math.sqrt(sum(value * value for value in xyz_delta)),
        }
    return result


def save_pose_records(
    path: Path,
    records: Mapping[str, Mapping],
    *,
    require_complete: bool = False,
) -> None:
    """Persist measured poses without fabricating an unmeasured peer pose.

    SAFE_HIGH may be recorded before HOME and PICK_READY may be added later.
    Callers that require the automatic return pair set ``require_complete=True``;
    this continues to require HOME and SAFE_HIGH, not every optional pose.
    """
    if not records or not set(records) <= set(POSE_NAMES):
        raise ValueError("pose_record_set_invalid")
    for name, record in records.items():
        if record.get("name") != name or record.get("sample_count") != 3:
            raise ValueError("pose_record_invalid")
    existing_records = {}
    if path.exists():
        existing = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if existing.get("schema_version") != 1:
            raise ValueError("existing_pose_schema_invalid")
        existing_records = dict(existing.get("poses") or {})
        if not set(existing_records) <= set(POSE_NAMES):
            raise ValueError("existing_pose_record_set_invalid")
    combined = {**existing_records, **dict(records)}
    if require_complete and not RETURN_POSE_NAMES <= set(combined):
        raise ValueError("home_and_safe_high_both_required")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(
        {
            "schema_version": 1,
            "runtime_start_pose": RUNTIME_START_POSE,
            "pose_roles": POSE_ROLES,
            "pose_status": {
                name: "RECORDED" if name in combined else "NOT_RECORDED"
                for name in POSE_NAMES
            },
            "poses": combined,
        },
        sort_keys=False, allow_unicode=True), encoding="utf-8")
