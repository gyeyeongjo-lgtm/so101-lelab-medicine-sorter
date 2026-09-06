#!/usr/bin/env python3
"""Read both SO-101 Feetech buses without register writes or torque changes.

This isolates whether merely opening and reading the leader and follower USB
serial adapters together causes packet loss.  LeLab teleoperation and recording
must both be inactive.  Both buses are disconnected with disable_torque=False.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.request
from datetime import datetime, timezone
from typing import Any


MOTOR_LAYOUT = {
    "shoulder_pan": (1, "sts3215"),
    "shoulder_lift": (2, "sts3215"),
    "elbow_flex": (3, "sts3215"),
    "wrist_flex": (4, "sts3215"),
    "wrist_roll": (5, "sts3215"),
    "gripper": (6, "sts3215"),
}


def now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def serial_number(port: str) -> str | None:
    from serial.tools import list_ports

    resolved = os.path.realpath(port)
    for candidate in list_ports.comports(include_links=True):
        if candidate.device in (port, resolved):
            return candidate.serial_number
    return None


def status_is_inactive(base_url: str, endpoint: str) -> dict[str, Any]:
    with urllib.request.urlopen(base_url.rstrip("/") + endpoint, timeout=2) as response:
        payload = json.loads(response.read().decode("utf-8"))

    def find_active(value: Any) -> bool | None:
        if isinstance(value, dict):
            for key in ("teleoperation_active", "recording_active", "active"):
                if isinstance(value.get(key), bool):
                    return value[key]
            for child in value.values():
                found = find_active(child)
                if found is not None:
                    return found
        return None

    active = find_active(payload)
    if active is not False:
        raise RuntimeError(f"{endpoint} was not explicitly inactive: {active!r}")
    return {"endpoint": endpoint, "active": active}


def error_record(exc: BaseException) -> dict[str, str]:
    return {"type": type(exc).__name__, "message": str(exc)}


def build_bus(port: str):
    from lerobot.motors import Motor, MotorNormMode
    from lerobot.motors.feetech import FeetechMotorsBus

    motors = {
        name: Motor(
            motor_id,
            model,
            MotorNormMode.RANGE_0_100 if name == "gripper" else MotorNormMode.DEGREES,
        )
        for name, (motor_id, model) in MOTOR_LAYOUT.items()
    }
    return FeetechMotorsBus(port=port, motors=motors), motors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--follower-port", default="/dev/ttyACM0")
    parser.add_argument("--leader-port", default="/dev/ttyACM1")
    parser.add_argument("--follower-serial", required=True)
    parser.add_argument("--leader-serial", required=True)
    parser.add_argument("--rounds", type=int, default=60)
    parser.add_argument("--rate-hz", type=float, default=30.0)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    if not 1 <= args.rounds <= 600:
        parser.error("--rounds must be between 1 and 600")
    if not 0 < args.rate_hz <= 100:
        parser.error("--rate-hz must be above 0 and at most 100")

    report: dict[str, Any] = {
        "tool": "diagnose_dual_bus_readonly",
        "started_at": now(),
        "safety": {
            "read_only_packets": True,
            "register_writes": False,
            "torque_changes": False,
            "usb_reconnect": False,
            "disconnect_disable_torque": False,
        },
        "ports": {},
        "service_status": [],
        "rounds": args.rounds,
        "rate_hz": args.rate_hz,
        "samples": [],
    }

    follower = leader = None
    follower_connected = leader_connected = False
    try:
        report["service_status"] = [
            status_is_inactive(args.base_url, "/teleoperation-status"),
            status_is_inactive(args.base_url, "/recording-status"),
        ]
        observed = {
            "follower": serial_number(args.follower_port),
            "leader": serial_number(args.leader_port),
        }
        report["ports"] = {
            "follower": {"path": args.follower_port, "serial": observed["follower"]},
            "leader": {"path": args.leader_port, "serial": observed["leader"]},
        }
        if observed["follower"] != args.follower_serial:
            raise RuntimeError("follower serial identity mismatch; no port opened")
        if observed["leader"] != args.leader_serial:
            raise RuntimeError("leader serial identity mismatch; no port opened")

        follower, follower_motors = build_bus(args.follower_port)
        leader, leader_motors = build_bus(args.leader_port)
        follower.connect(handshake=False)
        follower_connected = True
        leader.connect(handshake=False)
        leader_connected = True

        period = 1.0 / args.rate_hz
        for round_number in range(1, args.rounds + 1):
            round_started = time.monotonic()
            item: dict[str, Any] = {"round": round_number}
            for role, bus, motors in (
                ("leader", leader, leader_motors),
                ("follower", follower, follower_motors),
            ):
                read_started = time.monotonic()
                try:
                    values = bus.sync_read(
                        "Present_Position", list(motors), normalize=False, num_retry=0
                    )
                    item[role] = {"ok": True, "values": values}
                except Exception as exc:
                    item[role] = {"ok": False, "error": error_record(exc)}
                item[role]["elapsed_ms"] = round(
                    (time.monotonic() - read_started) * 1000, 3
                )
            report["samples"].append(item)
            remaining = period - (time.monotonic() - round_started)
            if remaining > 0:
                time.sleep(remaining)
        report["ok"] = all(
            sample[role]["ok"]
            for sample in report["samples"]
            for role in ("leader", "follower")
        )
    except Exception as exc:
        report["ok"] = False
        report["fatal_error"] = error_record(exc)
    finally:
        if leader_connected:
            leader.disconnect(disable_torque=False)
        if follower_connected:
            follower.disconnect(disable_torque=False)
        report["finished_at"] = now()

    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
