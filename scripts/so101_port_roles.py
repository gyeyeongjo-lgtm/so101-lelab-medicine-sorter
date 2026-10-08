"""Offline-testable USB role contracts; inspection only, never opens a tty.

The two-port alignment viewer and LeLab teleop need both roles. A follower
reader or replay never requires the leader role; a leader reader never requires
the follower role. The caller owns any live preflight/port locking policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class PortRole:
    path: Path
    serial: str


PORT_ROLES = {
    "follower": PortRole(Path("/dev/ttyACM0"), "5AE6058306"),
    "leader": PortRole(Path("/dev/ttyACM1"), "5AE6085272"),
}
TASK_ROLES = {
    "follower_read": ("follower",),
    "follower_replay": ("follower",),
    "leader_read": ("leader",),
    "alignment_view": ("follower", "leader"),
    "lelab_teleop": ("follower", "leader"),
}


class Inspector(Protocol):
    def serial_short(self, path: Path) -> str: ...
    def readable_writable(self, path: Path) -> bool: ...
    def owner_pids(self, path: Path) -> set[int]: ...


def inspect_task_ports(task: str, inspector: Inspector) -> dict[str, str]:
    """Check identity, permission, busy separately without opening either port."""
    if task not in TASK_ROLES:
        raise ValueError("unknown_usb_task")
    result = {}
    for role in TASK_ROLES[task]:
        port = PORT_ROLES[role]
        if inspector.serial_short(port.path) != port.serial:
            result[role] = "WRONG_CANONICAL_USB"
        elif not inspector.readable_writable(port.path):
            result[role] = "PERMISSION_DENIED"
        elif inspector.owner_pids(port.path):
            result[role] = "PORT_BUSY"
        else:
            result[role] = "AVAILABLE"
    return result
