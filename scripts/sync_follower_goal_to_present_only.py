#!/usr/bin/env python3
"""One-shot Goal=Present raw sync while follower torque remains OFF.

Never enables torque, starts teleop, or commands a named pose. A failed or
ambiguous Goal write is not retried by this program.
"""

from __future__ import annotations

import argparse
import fcntl
import json
from pathlib import Path
import termios
import time

if __package__:
    from scripts.so101_exclusive_bus import ExclusiveFollowerLease, SystemBusProbe
else:
    from so101_exclusive_bus import ExclusiveFollowerLease, SystemBusProbe


AXES = ("shoulder_pan", "shoulder_lift", "elbow_flex",
        "wrist_flex", "wrist_roll", "gripper")


def raw_group(bus, register: str) -> dict[str, int]:
    values = bus.sync_read(register, normalize=False, num_retry=2)
    if set(values) != set(AXES):
        raise RuntimeError(f"{register}_shape_mismatch")
    if any(type(value) is not int for value in values.values()):
        raise RuntimeError(f"{register}_noninteger")
    return {axis: values[axis] for axis in AXES}


def snapshot(bus) -> dict:
    result = {
        "present_raw": raw_group(bus, "Present_Position"),
        "goal_raw": raw_group(bus, "Goal_Position"),
        "torque": raw_group(bus, "Torque_Enable"),
        "moving": raw_group(bus, "Moving"),
        "temperature_c": raw_group(bus, "Present_Temperature"),
    }
    motors = bus.motors
    result["present_degree_or_percent"] = {
        axis: float(bus._normalize({motors[axis].id: result["present_raw"][axis]})[
            motors[axis].id]) for axis in AXES
    }
    result["goal_degree_or_percent"] = {
        axis: float(bus._normalize({motors[axis].id: result["goal_raw"][axis]})[
            motors[axis].id]) for axis in AXES
    }
    return result


def require_off_still(sample: dict) -> None:
    if any(value != 0 for value in sample["torque"].values()):
        raise RuntimeError("torque_not_all_off")
    if any(value != 0 for value in sample["moving"].values()):
        raise RuntimeError("follower_moving")
    if any(value > 55 for value in sample["temperature_c"].values()):
        raise RuntimeError("temperature_over_existing_limit")
    if any(not 0 < value < 4095 for value in sample["present_raw"].values()):
        raise RuntimeError("present_raw_invalid")


def sync_goal_present_only(bus, *, guard=None, sleep_fn=time.sleep) -> dict:
    """Read three still samples, write exact fresh raw once, then read back."""
    before = []
    for index in range(3):
        if guard is not None:
            guard()
        row = snapshot(bus)
        require_off_still(row)
        before.append(row)
        if index < 2:
            sleep_fn(0.2)
    if any(row["present_raw"] != before[-1]["present_raw"] for row in before):
        raise RuntimeError("present_not_stable_before_sync")
    if any(row["goal_raw"] != before[-1]["goal_raw"] for row in before):
        raise RuntimeError("goal_changed_before_sync")

    if guard is not None:
        guard()
    fresh = snapshot(bus)
    require_off_still(fresh)
    if (fresh["present_raw"] != before[-1]["present_raw"] or
            fresh["goal_raw"] != before[-1]["goal_raw"]):
        raise RuntimeError("register_changed_before_write")
    intended = fresh["present_raw"].copy()

    # The only write in this program. No calibration inverse or new pose target.
    bus.sync_write("Goal_Position", intended, normalize=False, num_retry=1)

    if guard is not None:
        guard()
    after = snapshot(bus)
    require_off_still(after)
    if after["goal_raw"] != intended:
        raise RuntimeError("goal_readback_mismatch")
    if after["present_raw"] != intended:
        raise RuntimeError("physical_position_changed_after_sync")
    return {
        "status": "PASS",
        "intended_present_raw": intended,
        "before": fresh,
        "after": after,
        "max_goal_present_raw_diff": max(abs(after["goal_raw"][axis] -
                                             after["present_raw"][axis])
                                         for axis in AXES),
        "goal_write_calls": 1,
        "torque_write_calls": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default="/dev/ttyACM1")
    parser.add_argument("--serial", default="5AE6058306")
    parser.add_argument("--approval", required=True)
    args = parser.parse_args()
    if args.approval != "GOAL_PRESENT_SYNC_ONLY":
        raise RuntimeError("approval_scope_mismatch")

    from lerobot.robots.so_follower import SO101Follower, SO101FollowerConfig

    lease = ExclusiveFollowerLease(SystemBusProbe(), port=Path(args.port),
                                   serial_short=args.serial)
    bus = None
    lease.acquire()
    try:
        robot = SO101Follower(SO101FollowerConfig(
            port=args.port, id="so-101", cameras={},
            disable_torque_on_disconnect=False))
        bus = robot.bus
        bus.connect(handshake=False)
        fcntl.ioctl(bus.port_handler.ser.fileno(), termios.TIOCEXCL)
        if not bus.is_calibrated:
            raise RuntimeError("follower_calibration_not_loaded")
        lease.mark_connected()
        result = sync_goal_present_only(bus, guard=lease.ensure_exclusive)
        print(json.dumps(result, separators=(",", ":")))
        return 0
    except Exception as error:
        print(f"GOAL_PRESENT_SYNC_FAIL:{type(error).__name__}:{error}")
        return 1
    finally:
        if bus is not None and bus.is_connected:
            bus.disconnect(disable_torque=False)
        lease.release()


if __name__ == "__main__":
    raise SystemExit(main())
