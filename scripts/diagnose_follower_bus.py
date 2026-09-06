#!/usr/bin/env python3
"""Read-only Feetech follower-bus diagnostic.

This deliberately does not call ``configure``, ``enable_torque``,
``disable_torque``, ``write``, ``sync_write`` or any calibration method.  It
opens the selected serial port, sends only ping/read packets, and closes it
with ``disable_torque=False``.  Stop LeLab teleoperation/recording and close
camera preview before running it so that this process is the only owner of the
port.

The script is intended to run on the Jetson in the LeLab/LeRobot environment:

    lelab-python diagnose_follower_bus.py --port /dev/ttyACM0 \
        --expected-serial 5AE6085272

The HTTP status check is read-only and aborts when LeLab reports an active
teleoperation or recording session.  Use ``--skip-service-check`` only when
the service is intentionally unavailable and the user has independently
confirmed that both sessions are stopped.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import stat
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MOTORS = {
    "shoulder_pan": (1, "sts3215"),
    "shoulder_lift": (2, "sts3215"),
    "elbow_flex": (3, "sts3215"),
    "wrist_flex": (4, "sts3215"),
    "wrist_roll": (5, "sts3215"),
    "gripper": (6, "sts3215"),
}


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _port_metadata(port: str) -> dict[str, Any]:
    """Collect identity metadata without opening the serial device."""

    expanded = os.path.expanduser(port)
    result: dict[str, Any] = {
        "requested": port,
        "resolved": os.path.realpath(expanded),
        "exists": os.path.exists(expanded),
        "is_character_device": False,
        "serial_number": None,
        "vid": None,
        "pid": None,
        "location": None,
    }
    try:
        result["is_character_device"] = stat.S_ISCHR(os.stat(expanded).st_mode)
    except OSError as exc:
        result["metadata_error"] = f"{type(exc).__name__}: {exc}"

    try:
        from serial.tools import list_ports

        for candidate in list_ports.comports(include_links=True):
            if candidate.device in (expanded, result["resolved"]):
                result.update(
                    {
                        "serial_number": candidate.serial_number,
                        "vid": candidate.vid,
                        "pid": candidate.pid,
                        "location": candidate.location,
                        "hwid": candidate.hwid,
                    }
                )
                break
    except (ImportError, OSError):
        # The actual LeRobot import below gives the useful error if the
        # runtime is incomplete; identity metadata is best effort only.
        pass
    return result


def _fetch_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=2) as response:
        payload = response.read()
    value = json.loads(payload.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{url} did not return a JSON object")
    return value


def _status_active(payload: dict[str, Any], keys: tuple[str, ...]) -> bool | None:
    """Find a boolean status field without assuming a single API envelope."""

    for key in keys:
        value = payload.get(key)
        if isinstance(value, bool):
            return value
    for value in payload.values():
        if isinstance(value, dict):
            nested = _status_active(value, keys)
            if nested is not None:
                return nested
    return None


def assert_service_inactive(base_url: str) -> dict[str, Any]:
    """Read LeLab status endpoints and reject an active session."""

    endpoints = {
        "teleoperation": ("/teleoperation-status", ("teleoperation_active", "active")),
        "recording": ("/recording-status", ("recording_active", "active")),
    }
    statuses: dict[str, Any] = {}
    for name, (path, keys) in endpoints.items():
        url = base_url.rstrip("/") + path
        payload = _fetch_json(url)
        active = _status_active(payload, keys)
        # Keep the report focused on the guard result. Do not persist the
        # service's full response (which could grow to include dataset or
        # account metadata unrelated to this hardware test).
        statuses[name] = {"url": url, "active": active}
        if active is not False:
            raise RuntimeError(
                f"LeLab {name} status was not explicitly inactive ({active!r}); "
                "stop the session before opening the follower port"
            )
    return statuses


def _error(exc: BaseException) -> dict[str, str]:
    return {"type": type(exc).__name__, "message": str(exc)}


def run_diagnostic(port: str, rounds: int, expected_serial: str | None) -> dict[str, Any]:
    # Imports are intentionally delayed so the script can still print a clear
    # status/identity error when invoked with the wrong Python environment.
    from lerobot.motors import Motor, MotorNormMode
    from lerobot.motors.feetech import FeetechMotorsBus

    motors = {
        name: Motor(motor_id, model, MotorNormMode.DEGREES if name != "gripper" else MotorNormMode.RANGE_0_100)
        for name, (motor_id, model) in MOTORS.items()
    }
    metadata = _port_metadata(port)
    if expected_serial and metadata.get("serial_number") != expected_serial:
        raise RuntimeError(
            f"serial identity mismatch for {port}: expected {expected_serial!r}, "
            f"observed {metadata.get('serial_number')!r}; no serial port was opened"
        )

    bus = FeetechMotorsBus(port=port, motors=motors)
    report: dict[str, Any] = {
        "started_at": _now(),
        "port": metadata,
        "rounds": rounds,
        "safety": {
            "read_only_packets": True,
            "called_write_or_torque_api": False,
            "disconnect_disable_torque": False,
        },
        "ping": [],
        "individual_present_position": [],
        "sync_present_position": [],
    }
    connected = False
    try:
        # handshake=False avoids an implicit ping/firmware check. All packets
        # below are explicit reads or pings, never register writes.
        bus.connect(handshake=False)
        connected = True

        for name in motors:
            try:
                model_number = bus.ping(name, num_retry=0, raise_on_error=False)
                report["ping"].append({"motor": name, "id": motors[name].id, "model_number": model_number})
            except Exception as exc:  # capture per-ID evidence and continue
                report["ping"].append({"motor": name, "id": motors[name].id, "error": _error(exc)})

        for round_number in range(1, rounds + 1):
            for name in motors:
                started = time.monotonic()
                try:
                    value = bus.read("Present_Position", name, normalize=False, num_retry=0)
                    item: dict[str, Any] = {
                        "round": round_number,
                        "motor": name,
                        "id": motors[name].id,
                        "ok": True,
                        "value": value,
                    }
                except Exception as exc:
                    item = {
                        "round": round_number,
                        "motor": name,
                        "id": motors[name].id,
                        "ok": False,
                        "error": _error(exc),
                    }
                item["elapsed_ms"] = round((time.monotonic() - started) * 1000, 2)
                report["individual_present_position"].append(item)

            started = time.monotonic()
            try:
                values = bus.sync_read("Present_Position", list(motors), normalize=False, num_retry=0)
                item = {"round": round_number, "ok": True, "values": values}
            except Exception as exc:
                item = {"round": round_number, "ok": False, "error": _error(exc)}
            item["elapsed_ms"] = round((time.monotonic() - started) * 1000, 2)
            report["sync_present_position"].append(item)
    finally:
        if connected:
            # The default disconnect() writes Torque_Enable=0. This explicit
            # argument is mandatory for this diagnostic's read-only contract.
            bus.disconnect(disable_torque=False)
    report["finished_at"] = _now()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True, help="Follower serial device; do not guess the role")
    parser.add_argument("--expected-serial", help="Optional USB serial identity guard")
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--skip-service-check",
        action="store_true",
        help="Skip HTTP inactive checks only after independently confirming LeLab is stopped",
    )
    args = parser.parse_args()
    if args.rounds < 1 or args.rounds > 20:
        parser.error("--rounds must be between 1 and 20")

    envelope: dict[str, Any] = {
        "tool": "diagnose_follower_bus",
        "started_at": _now(),
        "host": socket.gethostname(),
        "requested_port": args.port,
        "safety": "No motor register writes, torque changes, calibration, USB reconnect, or camera access.",
    }
    try:
        envelope["service_status"] = (
            {"skipped": True}
            if args.skip_service_check
            else assert_service_inactive(args.base_url)
        )
        envelope["result"] = run_diagnostic(args.port, args.rounds, args.expected_serial)
        envelope["ok"] = True
    except Exception as exc:
        envelope["ok"] = False
        envelope["error"] = _error(exc)
        envelope["hint"] = "No serial write was intentionally attempted; inspect the error and identity fields before retrying."
    print(json.dumps(envelope, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if envelope["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
