#!/usr/bin/env python3
"""Connect-only Torque writer diagnostic with a fail-closed write firewall.

Default execution is hardware-free. A separately approved live invocation may
open only the follower bus, block every discovered write layer, read registers,
and disconnect with torque preservation. It never configures or teleoperates.
"""

from __future__ import annotations

import argparse
import fcntl
import json
from pathlib import Path
import signal
import termios
import time
import traceback
from typing import Any, Callable

if __package__:
    from .atomic_hold_restore import AXES, snapshot
    from .so101_exclusive_bus import ExclusiveFollowerLease, SystemBusProbe
else:
    from atomic_hold_restore import AXES, snapshot
    from so101_exclusive_bus import ExclusiveFollowerLease, SystemBusProbe


APPROVAL = "RUN TORQUE WRITER DIAGNOSTIC"
SITE_CONFIRMATION = "SUPPORTED NON_CONTACT PORTS_FREE STOP_READY"
FOLLOWER_PORT = Path("/dev/ttyACM1")
LEADER_PORT = Path("/dev/ttyACM0")
FOLLOWER_SERIAL = "5AE6058306"


class WriteAttemptBlocked(RuntimeError):
    pass


class WriteAttemptFirewall:
    """Log a Python stack and block high-, low-, and raw-serial writes."""

    def __init__(self, bus, *, wall_time_ns: Callable[[], int] = time.time_ns):
        self.bus = bus
        self.wall_time_ns = wall_time_ns
        self.attempts: list[dict[str, Any]] = []
        self.originals: dict[str, Any] = {}
        self._install()

    def _motor_ids(self, motors) -> list[int] | str:
        if motors is None:
            return sorted(motor.id for motor in self.bus.motors.values())
        names = [motors] if isinstance(motors, str) else motors
        try:
            return [self.bus.motors[name].id for name in names]
        except (KeyError, TypeError):
            return "UNKNOWN"

    def _block(self, *, layer: str, register: str, motor_ids, value) -> None:
        self.attempts.append({
            "event": "WRITE_ATTEMPTED_BLOCKED",
            "timestamp_unix_ns": self.wall_time_ns(),
            "layer": layer,
            "register_name": register,
            "motor_ids": motor_ids,
            "value": value,
            "python_call_stack": traceback.format_stack()[:-1],
        })
        raise WriteAttemptBlocked(f"write_blocked:{layer}:{register}")

    def _replace(self, owner, name: str, replacement) -> None:
        if hasattr(owner, name):
            key = f"{id(owner)}:{name}"
            self.originals[key] = (owner, name, getattr(owner, name))
            setattr(owner, name, replacement)

    def _install(self) -> None:
        bus = self.bus

        def write(register, motor, value, *_args, **_kwargs):
            motor_id = self._motor_ids(motor)
            self._block(layer="bus.write", register=str(register),
                        motor_ids=motor_id, value=value)

        def sync_write(register, values, *_args, **_kwargs):
            if isinstance(values, dict):
                motor_ids = {str(bus.motors[name].id): values[name]
                             for name in values if name in bus.motors}
                value = dict(values)
            else:
                motor_ids = self._motor_ids(None)
                value = values
            self._block(layer="bus.sync_write", register=str(register),
                        motor_ids=motor_ids, value=value)

        def enable_torque(motors=None, *_args, **_kwargs):
            self._block(layer="bus.enable_torque", register="Torque_Enable",
                        motor_ids=self._motor_ids(motors), value=1)

        def disable_torque(motors=None, *_args, **_kwargs):
            self._block(layer="bus.disable_torque", register="Torque_Enable",
                        motor_ids=self._motor_ids(motors), value=0)

        def configure(*_args, **_kwargs):
            self._block(layer="bus.configure_motors", register="MULTIPLE_CONFIG_REGISTERS",
                        motor_ids=self._motor_ids(None), value="CONFIGURE")

        def calibration(*_args, **_kwargs):
            self._block(layer="bus.write_calibration", register="CALIBRATION",
                        motor_ids=self._motor_ids(None), value="CALIBRATION")

        def low_write(addr, length, motor_id, value, *_args, **_kwargs):
            self._block(layer="bus._write", register=f"ADDRESS_{addr}_LENGTH_{length}",
                        motor_ids=[motor_id], value=value)

        def low_sync(addr, length, ids_values, *_args, **_kwargs):
            self._block(layer="bus._sync_write", register=f"ADDRESS_{addr}_LENGTH_{length}",
                        motor_ids=sorted(ids_values), value=dict(ids_values))

        def raw_serial(data, *_args, **_kwargs):
            payload = bytes(data) if not isinstance(data, bytes) else data
            self._block(layer="port_handler.writePort", register="RAW_SERIAL_UNKNOWN",
                        motor_ids="UNKNOWN", value=payload.hex())

        for name, replacement in (
            ("write", write), ("sync_write", sync_write),
            ("enable_torque", enable_torque), ("disable_torque", disable_torque),
            ("configure_motors", configure), ("write_calibration", calibration),
            ("_write", low_write), ("_sync_write", low_sync),
        ):
            self._replace(bus, name, replacement)
        if hasattr(bus, "port_handler"):
            self._replace(bus.port_handler, "writePort", raw_serial)

    def restore(self) -> None:
        for owner, name, original in reversed(list(self.originals.values())):
            setattr(owner, name, original)
        self.originals.clear()

    def write_json(self, path: Path) -> None:
        path.write_text(json.dumps(self.attempts, indent=2) + "\n", encoding="utf-8")


def _live(args) -> int:
    from lerobot.robots.so_follower import SO101Follower, SO101FollowerConfig

    if args.approval != APPROVAL:
        raise RuntimeError("live_approval_phrase_missing")
    if args.audit.exists():
        raise RuntimeError("fresh_audit_path_required")
    if input(f"Type {SITE_CONFIRMATION}: ") != SITE_CONFIRMATION:
        print("NOT_RUN:onsite_confirmation_missing")
        return 2

    probe = SystemBusProbe()
    if probe.owner_pids(LEADER_PORT):
        raise RuntimeError("leader_port_busy")
    lease = ExclusiveFollowerLease(
        probe, port=FOLLOWER_PORT, serial_short=FOLLOWER_SERIAL)
    robot = bus = firewall = None
    stopping = False

    def on_stop(_signal, _frame):
        nonlocal stopping
        stopping = True

    previous_sigint = signal.signal(signal.SIGINT, on_stop)
    previous_sigterm = signal.signal(signal.SIGTERM, on_stop)
    result: dict[str, Any] = {}
    try:
        lease.acquire()
        robot = SO101Follower(SO101FollowerConfig(
            port=str(FOLLOWER_PORT), id="so-101", cameras={},
            disable_torque_on_disconnect=False))
        bus = robot.bus
        firewall = WriteAttemptFirewall(bus)
        bus.connect(handshake=False)
        fcntl.ioctl(bus.port_handler.ser.fileno(), termios.TIOCEXCL)
        lease.mark_connected()
        if stopping:
            raise RuntimeError("stop_requested")
        first = snapshot(bus)
        time.sleep(1.0)
        lease.ensure_exclusive()
        second = snapshot(bus)
        result = {
            "status": "CONNECT_DIAGNOSTIC_COMPLETE",
            "first": first,
            "second": second,
            "write_attempt_count": len(firewall.attempts),
            "torque_changed": first["torque"] != second["torque"],
            "external_or_firmware_change_suspected": (
                not firewall.attempts and first["torque"] != second["torque"]),
        }
        print(json.dumps(result, separators=(",", ":")))
        return 0
    except WriteAttemptBlocked as error:
        result = {"status": "WRITE_ATTEMPT_BLOCKED", "error": str(error),
                  "write_attempt_count": len(firewall.attempts) if firewall else 0}
        print(json.dumps(result, separators=(",", ":")))
        return 1
    finally:
        if firewall is not None:
            firewall.write_json(args.audit)
        signal.signal(signal.SIGINT, previous_sigint)
        signal.signal(signal.SIGTERM, previous_sigterm)
        if bus is not None and bus.is_connected:
            bus.disconnect(disable_torque=False)
        lease.release()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--approval", default="")
    parser.add_argument("--audit", type=Path)
    args = parser.parse_args(argv)
    if not args.live:
        print(json.dumps({
            "entrypoint": "TORQUE_WRITER_DIAGNOSTIC_DRY_RUN_ONLY",
            "write_firewall": "READY_OFFLINE",
            "serial_open": 0, "motor_command": 0,
            "goal_write": 0, "torque_write": 0, "config_write": 0,
        }))
        return 0
    if args.audit is None:
        raise RuntimeError("live_audit_path_required")
    return _live(args)


if __name__ == "__main__":
    raise SystemExit(main())
