"""Fail-closed follower-port ownership preflight; never starts/stops a service.

LeLab's camera server may remain alive, but all of its motor-control tasks and
the old follower port owner must be gone. A kernel tty exclusive seal is set
by the live transport after connection to prevent a later competing open.
"""

from __future__ import annotations

import fcntl
import os
from pathlib import Path
import re
import subprocess
import json
from typing import Protocol
from urllib.request import urlopen
from urllib.error import URLError


FOLLOWER_SERIAL = "5AE6058306"
FOLLOWER_PORT = Path("/dev/ttyACM0")


class PreflightError(RuntimeError):
    pass


class BusProbe(Protocol):
    def lelab_controls_idle(self) -> bool: ...
    def serial_short(self, port: Path) -> str: ...
    def owner_pids(self, port: Path) -> set[int]: ...


class SystemBusProbe:
    LELAB_URL = "http://127.0.0.1:8000"
    CONTROL_STATES = (("teleoperation-status", "teleoperation_active"),
                      ("recording-status", "recording_active"),
                      ("inference-status", "inference_active"))

    @staticmethod
    def _run(argv: list[str]) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(argv, text=True, capture_output=True,
                                  timeout=3, check=False)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise PreflightError(f"probe_failed:{argv[0]}") from error

    def lelab_controls_idle(self) -> bool:
        for endpoint, field in self.CONTROL_STATES:
            try:
                with urlopen(f"{self.LELAB_URL}/{endpoint}", timeout=2) as response:
                    state = json.load(response)
            except (OSError, URLError, ValueError) as error:
                raise PreflightError(f"lelab_control_state_unknown:{endpoint}") from error
            if field not in state or type(state[field]) is not bool:
                raise PreflightError(f"lelab_control_state_unknown:{endpoint}")
            if state[field]:
                return False
        return True

    def serial_short(self, port: Path) -> str:
        if not port.exists():
            raise PreflightError("follower_port_missing")
        result = self._run(["udevadm", "info", "-q", "property", "-n", str(port)])
        if result.returncode != 0:
            raise PreflightError("canonical_usb_identity_unknown")
        values = [line.split("=", 1)[1] for line in result.stdout.splitlines()
                  if line.startswith("ID_SERIAL_SHORT=")]
        if len(values) != 1:
            raise PreflightError("canonical_usb_identity_unknown")
        return values[0]

    def owner_pids(self, port: Path) -> set[int]:
        if not port.exists():
            raise PreflightError("follower_port_missing")
        result = self._run(["fuser", str(port)])
        # On this Jetson, an unprivileged fuser reports /proc permission errors
        # even when the tty is free. Do not infer "unowned" from that partial
        # scan: require a privileged, noninteractive read-only scan instead.
        if result.returncode == 1 and not result.stdout.strip() and "Permission denied" in result.stderr:
            result = self._run(["sudo", "-n", "fuser", str(port)])
        if result.returncode == 1 and not result.stdout.strip() and not result.stderr.strip():
            return set()
        if result.returncode != 0:
            raise PreflightError("port_ownership_unknown")
        pids = {int(value) for value in re.findall(r"\b\d+\b", result.stdout)}
        if not pids:
            raise PreflightError("port_ownership_unknown")
        return pids


class ExclusiveFollowerLease:
    """Hold a local lock and recheck service, canonical USB, and port owners."""

    def __init__(self, probe: BusProbe, *, port: Path = FOLLOWER_PORT,
                 serial_short: str = FOLLOWER_SERIAL,
                 lock_path: Path | None = None, own_pid: int | None = None):
        self.probe = probe
        self.port = port
        self.serial_short = serial_short
        self.lock_path = lock_path or Path(f"/run/user/{os.getuid()}/so101-follower-program.lock")
        self.own_pid = own_pid or os.getpid()
        self._lock_file = None
        self.connected = False

    def acquire(self) -> None:
        if self._lock_file is not None:
            raise PreflightError("lease_already_acquired")
        try:
            self._lock_file = self.lock_path.open("a+")
            fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.check_before_connect()
        except (OSError, PreflightError) as error:
            self.release()
            raise PreflightError(str(error)) from error

    def check_before_connect(self) -> None:
        if self._lock_file is None:
            raise PreflightError("lease_not_held")
        if not self.probe.lelab_controls_idle():
            raise PreflightError("lelab_motor_control_not_idle")
        if self.probe.serial_short(self.port) != self.serial_short:
            raise PreflightError("wrong_follower_usb_identity")
        if self.probe.owner_pids(self.port):
            raise PreflightError("follower_port_busy")

    def mark_connected(self) -> None:
        if self._lock_file is None:
            raise PreflightError("lease_not_held")
        self.connected = True
        self.ensure_exclusive()

    def ensure_exclusive(self) -> None:
        if self._lock_file is None or not self.connected:
            raise PreflightError("controller_not_connected")
        if not self.probe.lelab_controls_idle():
            raise PreflightError("lelab_motor_control_started_during_program")
        if self.probe.serial_short(self.port) != self.serial_short:
            raise PreflightError("follower_usb_changed")
        if self.probe.owner_pids(self.port) != {self.own_pid}:
            raise PreflightError("follower_bus_not_exclusive")

    def release(self) -> None:
        self.connected = False
        if self._lock_file is not None:
            fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_UN)
            self._lock_file.close()
            self._lock_file = None
