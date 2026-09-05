#!/usr/bin/env python3
"""Inspect serial-port identity without opening any device.

The script only reads filesystem, pySerial and udev metadata. It never creates
a Serial object and never calls a robot SDK connect/configure method.
"""

from __future__ import annotations

import argparse
import grp
import json
import os
import stat
import subprocess
from collections import defaultdict
from glob import glob
from pathlib import Path
from typing import Any


def _udev_properties(path: str) -> dict[str, str]:
    if not os.path.exists(path):
        return {}
    try:
        result = subprocess.run(
            ["udevadm", "info", "--query=property", f"--name={path}"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return {}
    properties: dict[str, str] = {}
    for line in result.stdout.splitlines():
        key, separator, value = line.partition("=")
        if separator:
            properties[key] = value
    return properties


def _serial_metadata() -> dict[str, dict[str, Any]]:
    try:
        from serial.tools import list_ports
    except ImportError:
        return {}

    metadata: dict[str, dict[str, Any]] = {}
    for port in list_ports.comports(include_links=True):
        metadata[port.device] = {
            "vid": port.vid,
            "pid": port.pid,
            "serial_number": port.serial_number,
            "location": port.location,
            "hwid": port.hwid,
            "manufacturer": port.manufacturer,
            "product": port.product,
            "interface": port.interface,
        }
    return metadata


def inspect_path(path: str, serial_metadata: dict[str, dict[str, Any]]) -> dict[str, Any]:
    expanded = os.path.expanduser(path)
    canonical = os.path.realpath(expanded)
    result: dict[str, Any] = {
        "input_path": path,
        "expanded_path": expanded,
        "canonical_path": canonical,
        "exists": os.path.exists(expanded),
        "is_character_device": False,
        "major": None,
        "minor": None,
        "mode": None,
        "group": None,
        "pyserial": serial_metadata.get(expanded) or serial_metadata.get(canonical) or {},
        "udev": {},
        "error": None,
    }
    try:
        info = os.stat(expanded)
        result["is_character_device"] = stat.S_ISCHR(info.st_mode)
        result["mode"] = stat.filemode(info.st_mode)
        result["group"] = grp.getgrgid(info.st_gid).gr_name
        if result["is_character_device"]:
            result["major"] = os.major(info.st_rdev)
            result["minor"] = os.minor(info.st_rdev)
        properties = _udev_properties(canonical)
        result["udev"] = {
            key: properties.get(key)
            for key in (
                "ID_VENDOR_ID",
                "ID_MODEL_ID",
                "ID_SERIAL",
                "ID_SERIAL_SHORT",
                "ID_PATH",
                "ID_PATH_TAG",
                "DEVPATH",
            )
            if properties.get(key) is not None
        }
    except (OSError, KeyError) as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def collect_paths(requested: list[str], serial_metadata: dict[str, dict[str, Any]]) -> list[str]:
    discovered = set(requested)
    discovered.update(serial_metadata)
    for pattern in ("/dev/serial/by-id/*", "/dev/serial/by-path/*", "/dev/ttyACM*", "/dev/ttyUSB*"):
        discovered.update(glob(pattern))
    return sorted(discovered)


def identity_groups(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], list[str]] = defaultdict(list)
    for record in records:
        if not record["exists"]:
            continue
        if record["is_character_device"]:
            identity = (record["canonical_path"], record["major"], record["minor"])
        else:
            identity = (record["canonical_path"], "not-character-device")
        groups[identity].append(record["input_path"])
    return [
        {"identity": list(identity), "paths": sorted(paths), "alias_count": len(paths)}
        for identity, paths in sorted(groups.items(), key=lambda item: str(item[0]))
    ]


def build_report(paths: list[str]) -> dict[str, Any]:
    serial_metadata = _serial_metadata()
    records = [inspect_path(path, serial_metadata) for path in collect_paths(paths, serial_metadata)]
    return {
        "safety": "metadata-only; no serial device was opened",
        "records": records,
        "identity_groups": identity_groups(records),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", action="append", default=[], help="Saved/configured port path to include")
    args = parser.parse_args()
    print(json.dumps(build_report(args.path), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
