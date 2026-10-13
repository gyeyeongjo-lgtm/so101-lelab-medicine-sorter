#!/usr/bin/env python3
"""Read three follower pose/telemetry samples without any motor writes."""

from __future__ import annotations

import argparse
import fcntl
import json
import termios
import time
import urllib.request

from serial.tools import list_ports
from lerobot.robots.so_follower import SO101Follower, SO101FollowerConfig


REGISTERS = {
    "goal_raw": "Goal_Position",
    "present_raw": "Present_Position",
    "moving": "Moving",
    "present_load_diagnostic": "Present_Load",
    "temperature_c": "Present_Temperature",
    "torque_enable": "Torque_Enable",
}


def require_controls_idle(url: str) -> None:
    for endpoint, key in (
        ("teleoperation-status", "teleoperation_active"),
        ("recording-status", "recording_active"),
        ("inference-status", "inference_active"),
    ):
        with urllib.request.urlopen(f"{url}/{endpoint}", timeout=3) as response:
            if json.load(response).get(key) is not False:
                raise RuntimeError(f"LeLab {endpoint} is not explicitly inactive")


def forbid_write(*_args, **_kwargs):
    raise RuntimeError("write or torque change forbidden in read-only snapshot")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True)
    parser.add_argument("--serial", required=True)
    parser.add_argument("--lelab-url", default="http://127.0.0.1:8000")
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--interval", type=float, default=0.2)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.samples != 3 or not 0.1 <= args.interval <= 1.0:
        raise ValueError("pose record requires exactly three bounded samples")
    require_controls_idle(args.lelab_url)
    identities = {item.device: item.serial_number for item in list_ports.comports()}
    if identities.get(args.port) != args.serial:
        raise RuntimeError("canonical follower serial identity mismatch")

    robot = SO101Follower(SO101FollowerConfig(
        port=args.port,
        id="so-101",
        disable_torque_on_disconnect=False,
    ))
    bus = robot.bus
    for method in ("write", "sync_write", "enable_torque", "disable_torque"):
        if hasattr(bus, method):
            setattr(bus, method, forbid_write)

    result = []
    try:
        bus.connect(handshake=False)
        fcntl.ioctl(bus.port_handler.ser.fileno(), termios.TIOCEXCL)
        if not bus.is_calibrated:
            raise RuntimeError("follower calibration not loaded")
        names = tuple(bus.motors)
        for index in range(args.samples):
            require_controls_idle(args.lelab_url)
            values = {
                label: {
                    name: int(bus.read(register, name, normalize=False, num_retry=2))
                    for name in names
                }
                for label, register in REGISTERS.items()
            }
            degrees = {}
            goals = {}
            for name in names:
                motor_id = bus.motors[name].id
                degrees[name] = float(bus._normalize({
                    motor_id: values["present_raw"][name]
                })[motor_id])
                goals[name] = float(bus._normalize({
                    motor_id: values["goal_raw"][name]
                })[motor_id])
            result.append({
                "unix_ns": time.time_ns(),
                **values,
                "present_degree_or_percent": degrees,
                "goal_degree_or_percent": goals,
                "goal_minus_present": {
                    name: goals[name] - degrees[name] for name in names
                },
            })
            if index + 1 < args.samples:
                time.sleep(args.interval)
    finally:
        if bus.is_connected:
            bus.disconnect(disable_torque=False)

    print(json.dumps({
        "samples": result,
        "motor_write_calls": 0,
        "torque_change_calls": 0,
        "port_released_on_exit": True,
    }, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
