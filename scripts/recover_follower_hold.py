#!/usr/bin/env python3
"""One-shot recovery: latch fresh follower raw positions, then enable hold torque.

This never moves to a named pose, starts LeLab, or disables torque on normal
exit.  It is intentionally unusable when any follower axis already has torque.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import time

if __package__:
    from scripts.so101_exclusive_bus import ExclusiveFollowerLease, SystemBusProbe
    from scripts.so101_follower_transport import SO101FollowerTransport
    from scripts.staged_cycle_execution import JOINT_UNITS
else:
    from so101_exclusive_bus import ExclusiveFollowerLease, SystemBusProbe
    from so101_follower_transport import SO101FollowerTransport
    from staged_cycle_execution import JOINT_UNITS


AXES = tuple(JOINT_UNITS)
MAX_PRE_ENABLE_DRIFT_RAW = 8
MAX_POST_ENABLE_DELTA_RAW = 8
SAMPLE_COUNT = 10
SAMPLE_INTERVAL_S = 0.1


def _raw_group(bus, register: str) -> dict[str, int]:
    values = bus.sync_read(register, normalize=False, num_retry=2)
    if set(values) != set(AXES):
        raise RuntimeError(f"{register}_shape_mismatch")
    result = {}
    for name, value in values.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise RuntimeError(f"{register}_invalid:{name}")
        result[name] = int(value)
    return result


def _calibration_ranges_raw(bus) -> dict[str, tuple[int, int]]:
    calibration = getattr(bus, "calibration", None)
    if calibration is None:
        raise RuntimeError("calibration_unavailable")
    result = {}
    for name in AXES:
        item = calibration[name]
        lower = item.range_min if hasattr(item, "range_min") else item["range_min"]
        upper = item.range_max if hasattr(item, "range_max") else item["range_max"]
        if (not isinstance(lower, int) or not isinstance(upper, int) or
                not 0 <= lower < upper < 4096):
            raise RuntimeError(f"calibration_invalid:{name}")
        result[name] = (lower, upper)
    return result


def recover_current_hold(bus, *, input_fn=input, sleep_fn=time.sleep,
                         sample_count: int = SAMPLE_COUNT) -> dict:
    if sample_count < 2:
        raise ValueError("sample_count_too_small")
    torque_before = _raw_group(bus, "Torque_Enable")
    if any(value != 0 for value in torque_before.values()):
        raise RuntimeError("torque_not_all_off_before_recovery")

    calibration = _calibration_ranges_raw(bus)
    present_before = _raw_group(bus, "Present_Position")
    if any(not 0 < value < 4095 for value in present_before.values()):
        raise RuntimeError("fresh_present_outside_hardware_raw_range")
    outside_calibration = {
        name: {"present": present_before[name], "range": list(calibration[name])}
        for name in AXES
        if not calibration[name][0] <= present_before[name] <= calibration[name][1]
    }

    # Torque is still OFF. Writing the exact fresh raw values cannot request a
    # pose displacement; it only prepares the hold target for torque enable.
    bus.sync_write("Goal_Position", present_before, normalize=False, num_retry=2)
    torque_after_goal = _raw_group(bus, "Torque_Enable")
    if any(value != 0 for value in torque_after_goal.values()):
        raise RuntimeError("torque_changed_before_explicit_enable")
    goal_readback = _raw_group(bus, "Goal_Position")
    if any(value == 0 for value in goal_readback.values()):
        raise RuntimeError("goal_readback_contains_zero")
    if goal_readback != present_before:
        raise RuntimeError("goal_readback_mismatch")
    present_at_enable = _raw_group(bus, "Present_Position")
    if any(abs(present_at_enable[name] - present_before[name]) > MAX_PRE_ENABLE_DRIFT_RAW
           for name in AXES):
        raise RuntimeError("arm_drifted_before_torque_enable")

    enable_attempted = True
    try:
        bus.enable_torque(num_retry=2)
        torque_enabled = _raw_group(bus, "Torque_Enable")
        if any(value != 1 for value in torque_enabled.values()):
            raise RuntimeError("torque_enable_readback_failed")

        samples = []
        for index in range(sample_count):
            sample = {
                "present": _raw_group(bus, "Present_Position"),
                "goal": _raw_group(bus, "Goal_Position"),
                "torque": _raw_group(bus, "Torque_Enable"),
                "moving": _raw_group(bus, "Moving"),
            }
            if sample["goal"] != goal_readback:
                raise RuntimeError("goal_changed_after_torque_enable")
            if any(value != 1 for value in sample["torque"].values()):
                raise RuntimeError("torque_dropped_after_enable")
            samples.append(sample)
            if index + 1 < sample_count:
                sleep_fn(SAMPLE_INTERVAL_S)

        present_after = samples[-1]["present"]
        delta = {name: present_after[name] - present_before[name] for name in AXES}
        if any(abs(value) > MAX_POST_ENABLE_DELTA_RAW for value in delta.values()):
            raise RuntimeError(f"unexpected_motion_after_torque_enable:{delta}")
        if any(max(sample["present"][name] for sample in samples) -
               min(sample["present"][name] for sample in samples) > MAX_POST_ENABLE_DELTA_RAW
               for name in AXES):
            raise RuntimeError("position_not_stationary_after_torque_enable")

        response = input_fn(
            "Arm held current pose with no unexpected movement. "
            "Type HOLD CONFIRMED (or UNEXPECTED MOVEMENT): "
        )
        if response == "UNEXPECTED MOVEMENT":
            raise RuntimeError("unexpected_motion_reported")
        if response != "HOLD CONFIRMED":
            raise RuntimeError("stationary_hold_not_confirmed")
    except Exception as error:
        # The user is physically supporting the arm. Any post-enable failure
        # rolls the attempted recovery back to torque OFF before disconnect.
        if enable_attempted:
            try:
                bus.disable_torque(num_retry=2)
                if any(value != 0 for value in _raw_group(bus, "Torque_Enable").values()):
                    raise RuntimeError("torque_disable_readback_failed")
            except Exception as disable_error:
                raise RuntimeError(
                    f"post_enable_failure_and_torque_disable_failed:{disable_error}"
                ) from error
        raise

    rows = []
    for name in AXES:
        rows.append({
            "axis": name,
            "present_before": present_before[name],
            "goal_written": present_before[name],
            "goal_readback": goal_readback[name],
            "torque": torque_enabled[name],
            "present_after": present_after[name],
            "delta": delta[name],
        })
    return {
        "status": "CURRENT_POSE_HOLD_RECOVERED",
        "rows": rows,
        "outside_calibration_exact_hold_only": outside_calibration,
        "samples": samples,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default="/dev/ttyACM1")
    parser.add_argument("--serial", default="5AE6058306")
    args = parser.parse_args(argv)
    if input(
        "Physically support follower; scene clear; LeLab controls OFF. "
        "Type ARM SUPPORTED AND CLEAR: "
    ) != "ARM SUPPORTED AND CLEAR":
        print("NOT_RUN")
        return 2

    lease = ExclusiveFollowerLease(
        SystemBusProbe(), port=Path(args.port), serial_short=args.serial)
    transport = None
    try:
        transport = SO101FollowerTransport.open_live(lease, approval_confirmed=True)
        result = recover_current_hold(transport.robot.bus)
        for row in result["rows"]:
            print("{axis} | {present_before} | {goal_written} | {goal_readback} | "
                  "{torque} | {present_after} | {delta:+d}".format(**row))
        print(json.dumps(result, separators=(",", ":")))
        return 0
    except (OSError, RuntimeError, ValueError) as error:
        print(f"HOLD_RECOVERY_ABORTED:{type(error).__name__}:{error}")
        return 1
    finally:
        if transport is not None:
            # Preserve the verified hold torque. Never call the default
            # disconnect(), whose default is disable_torque=True.
            transport.robot.bus.disconnect(disable_torque=False)
            transport.lease.release()


if __name__ == "__main__":
    raise SystemExit(main())
