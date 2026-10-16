#!/usr/bin/python3
"""Root-owned, fixed-scope process lookup for the two SO-101 serial ports.

This helper accepts no arguments, never opens either serial device, and only
reads /proc to report processes that already have one of the fixed paths open.
It does not import subprocess and has no signal or process-control operation.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys


PORTS = (Path("/dev/ttyACM0"), Path("/dev/ttyACM1"))


def _process_name(pid: int) -> str:
    try:
        name = Path(f"/proc/{pid}/comm").read_text(encoding="utf-8").strip()
    except (FileNotFoundError, PermissionError, ProcessLookupError, OSError):
        return "unknown"
    # One record per line with no terminal/control injection.
    cleaned = "".join(character if character.isprintable() and not character.isspace()
                      else "_" for character in name)
    return cleaned[:64] or "unknown"


def _owners(port: Path) -> list[tuple[int, str]]:
    try:
        target = port.resolve(strict=True)
    except (FileNotFoundError, OSError):
        return []
    owners: list[tuple[int, str]] = []
    for entry in os.scandir("/proc"):
        if not entry.name.isdecimal():
            continue
        pid = int(entry.name)
        try:
            descriptors = os.scandir(f"/proc/{pid}/fd")
        except (FileNotFoundError, PermissionError, ProcessLookupError, OSError):
            continue
        with descriptors:
            found = False
            for descriptor in descriptors:
                try:
                    if Path(descriptor.path).resolve(strict=True) == target:
                        found = True
                        break
                except (FileNotFoundError, PermissionError, ProcessLookupError, OSError):
                    continue
        if found:
            owners.append((pid, _process_name(pid)))
    return sorted(set(owners))


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv if argv is None else argv
    if len(arguments) != 1:
        print("fixed_port_occupancy accepts no arguments", file=sys.stderr)
        return 64
    for port in PORTS:
        owners = _owners(port)
        if not owners:
            print(f"{port}\tFREE\t-\t-")
            continue
        for pid, name in owners:
            print(f"{port}\tOCCUPIED\t{pid}\t{name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
