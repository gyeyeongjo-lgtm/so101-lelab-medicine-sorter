#!/usr/bin/env python3
"""Validate a LeLab robot record without opening cameras or serial ports."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _device_record(path: str) -> dict[str, Any]:
    expanded = os.path.expanduser(path)
    canonical = os.path.realpath(expanded)
    exists = os.path.exists(expanded)
    is_character_device = False
    if exists:
        try:
            is_character_device = stat.S_ISCHR(os.stat(expanded).st_mode)
        except OSError:
            exists = False
    return {
        "configured": path,
        "canonical": canonical,
        "exists": exists,
        "is_character_device": is_character_device,
    }


def validate(record: dict[str, Any], home: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    leader = _device_record(str(record.get("leader_port", "")))
    follower = _device_record(str(record.get("follower_port", "")))

    for role, device in (("leader", leader), ("follower", follower)):
        checks.append(
            {
                "name": f"{role}_serial_exists",
                "status": "PASS" if device["exists"] and device["is_character_device"] else "FAIL",
                "details": device,
            }
        )

    if leader["exists"] and follower["exists"]:
        try:
            same_device = os.path.samefile(leader["configured"], follower["configured"])
        except OSError:
            same_device = True
        checks.append(
            {
                "name": "leader_follower_are_distinct",
                "status": "FAIL" if same_device else "PASS",
                "details": {"same_device": same_device},
            }
        )
    else:
        checks.append(
            {
                "name": "leader_follower_are_distinct",
                "status": "BLOCKED",
                "details": {"reason": "one or both configured serial devices are missing"},
            }
        )

    calibration_base = home / ".cache/huggingface/lerobot/calibration"
    calibration_paths = {
        "leader": calibration_base
        / "teleoperators/so_leader"
        / str(record.get("leader_config", "")),
        "follower": calibration_base
        / "robots/so_follower"
        / str(record.get("follower_config", "")),
    }
    for role, path in calibration_paths.items():
        checks.append(
            {
                "name": f"{role}_calibration_exists",
                "status": "PASS" if path.is_file() else "FAIL",
                "details": {"path": str(path), "sha256": _sha256(path)},
            }
        )

    for camera in record.get("cameras", []):
        index = camera.get("camera_index")
        path = Path(f"/dev/video{index}")
        is_character_device = path.exists() and stat.S_ISCHR(path.stat().st_mode)
        checks.append(
            {
                "name": f"camera_{index}_exists",
                "status": "PASS" if is_character_device else "FAIL",
                "details": {"path": str(path), "configured": camera},
            }
        )

    failed = [check for check in checks if check["status"] == "FAIL"]
    blocked = [check for check in checks if check["status"] == "BLOCKED"]
    return {
        "safety": "metadata-only; no serial or camera device was opened",
        "ready": not failed and not blocked,
        "summary": {"pass": len(checks) - len(failed) - len(blocked), "fail": len(failed), "blocked": len(blocked)},
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--robot-record", required=True, type=Path)
    parser.add_argument("--home", type=Path, default=Path.home())
    args = parser.parse_args()
    record = json.loads(args.robot_record.read_text(encoding="utf-8"))
    report = validate(record, args.home)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
