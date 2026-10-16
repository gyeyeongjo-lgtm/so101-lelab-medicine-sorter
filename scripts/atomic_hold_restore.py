#!/usr/bin/env python3
"""Prepare current-pose HOLD in one exclusive session, never a named pose.

Default invocation is non-live. Explicit approval and onsite confirmation are
required for --live. Atomic means one bus-owning session, not an all-servos
hardware transaction. An ambiguous write is never retried or rolled back.
"""

from __future__ import annotations

import argparse
import fcntl
import json
from pathlib import Path
import signal
import termios
import time

if __package__:
    from scripts.so101_exclusive_bus import ExclusiveFollowerLease, SystemBusProbe
else:
    from so101_exclusive_bus import ExclusiveFollowerLease, SystemBusProbe


AXES = ("shoulder_pan", "shoulder_lift", "elbow_flex",
        "wrist_flex", "wrist_roll", "gripper")
STABILITY_S = 3.0
MAX_TEMPERATURE_C = 55  # Existing servo gate; no tolerance change.
APPROVAL = "RUN ATOMIC HOLD RESTORE"
SITE_CONFIRMATION = "SUPPORTED STOPPED NON_CONTACT CLEAR STOP_READY OTHER_CONTROLLERS_INACTIVE"


def _raw(bus, register):
    values = bus.sync_read(register, normalize=False, num_retry=0)
    if set(values) != set(AXES) or any(type(v) is not int for v in values.values()):
        raise RuntimeError(f"invalid_raw_register:{register}")
    return {axis: values[axis] for axis in AXES}


def snapshot(bus):
    # No normalization or inverse calibration anywhere in this path.
    result = {name: _raw(bus, register) for name, register in (
        ("present_raw", "Present_Position"), ("goal_raw", "Goal_Position"),
        ("torque", "Torque_Enable"), ("moving", "Moving"))}
    # Preserve the individually-read temperature path proven on this bus.
    result["temperature_c"] = {}
    for axis in AXES:
        value = bus.read("Present_Temperature", axis, normalize=False, num_retry=0)
        if type(value) is not int:
            raise RuntimeError(f"invalid_temperature:{axis}")
        result["temperature_c"][axis] = value
    return result


def _check(sample, *, torque, present=None, goal=None):
    if any(v != torque for v in sample["torque"].values()):
        raise RuntimeError(f"unexpected_torque:expected_all_{torque}")
    if any(v != 0 for v in sample["moving"].values()):
        raise RuntimeError("unexpected_moving")
    if any(v < 0 or v > MAX_TEMPERATURE_C for v in sample["temperature_c"].values()):
        raise RuntimeError("temperature_fault")
    if any(not 0 < v < 4095 for v in sample["present_raw"].values()):
        raise RuntimeError("present_raw_outside_hardware_range")
    if any(not 0 <= v <= 4095 for v in sample["goal_raw"].values()):
        raise RuntimeError("goal_raw_outside_hardware_range")
    if present is not None and sample["present_raw"] != present:
        raise RuntimeError("unexpected_present_drift")
    if goal is not None and sample["goal_raw"] != goal:
        raise RuntimeError("unexpected_goal_change_or_readback_mismatch")


class OneShotRawWrites:
    """Deny connect/config/disconnect writes; allow only two scoped packets."""

    def __init__(self, bus):
        self.bus = bus
        self.attempts = {"Goal_Position": 0, "Torque_Enable": 0}
        self._pending = None
        self.closed = False
        original = bus.sync_write
        self._original_sync_write = original

        def denied(*_args, **_kwargs):
            raise RuntimeError("atomic_hold_forbidden_write")

        def checked(register, values, *args, **kwargs):
            pending, self._pending = self._pending, None
            if (self.closed or pending is None or args or
                    kwargs != {"normalize": False, "num_retry": 0} or
                    register != pending[0] or values != pending[1] or
                    set(values) != set(AXES) or
                    any(type(v) is not int for v in values.values()) or
                    self.attempts[register] != 0):
                raise RuntimeError("atomic_hold_forbidden_sync_write")
            self.attempts[register] += 1  # Count even a failed/ambiguous attempt.
            return original(register, dict(values), normalize=False, num_retry=0)

        for name in ("write", "write_calibration", "configure_motors",
                     "enable_torque", "disable_torque"):
            if hasattr(bus, name):
                setattr(bus, name, denied)
        self._installed_sync_write = checked
        bus.sync_write = checked

    def send(self, register, values):
        if self.closed or register not in self.attempts or self.attempts[register]:
            raise RuntimeError("atomic_hold_write_already_attempted_or_stopped")
        if register == "Torque_Enable" and (
                self.attempts["Goal_Position"] != 1 or set(values.values()) != {1}):
            raise RuntimeError("atomic_hold_invalid_torque_enable")
        self._pending = (register, dict(values))
        try:
            self.bus.sync_write(register, values, normalize=False, num_retry=0)
        finally:
            self._pending = None

    def stop(self):
        self.closed = True
        self._pending = None

    def handoff_to_teaching(self):
        """Release only sync_write after a complete HOLD restore.

        The caller must immediately install the already-tested teaching Goal
        firewall. Config and torque helpers remain denied throughout the same
        connected session.
        """
        if (not self.closed or self._pending is not None or
                self.attempts != {"Goal_Position": 1, "Torque_Enable": 1}):
            raise RuntimeError("atomic_hold_handoff_before_complete_restore")
        if self.bus.sync_write is not self._installed_sync_write:
            raise RuntimeError("atomic_hold_sync_write_changed_before_handoff")
        self.bus.sync_write = self._original_sync_write


def restore_hold(bus, writes, *, guard, stop_requested, audit,
                 monotonic=time.monotonic, sleep=time.sleep):
    """Caller owns/seals this connected bus for the entire operation."""
    def check_control():
        if stop_requested():
            raise RuntimeError("stop_requested")
        guard()
        if stop_requested():
            raise RuntimeError("stop_requested")

    def read(phase, *, immediate=False):
        # The ON packet was already ownership-guarded. Read it back before
        # slow HTTP/process probes, then recheck ownership below.
        if immediate:
            if stop_requested():
                raise RuntimeError("stop_requested")
        else:
            check_control()
        sample = snapshot(bus)
        audit.append({"phase": phase, "monotonic": monotonic(), **sample})
        if not immediate:
            check_control()
        return sample

    try:
        fresh = read("FRESH_OFF_PRESENT")
        _check(fresh, torque=0)
        # Recheck immediately before writing; no gap/session between sync/ON.
        before = read("PRE_SYNC_RECHECK")
        _check(before, torque=0, present=fresh["present_raw"], goal=fresh["goal_raw"])
        intended = dict(before["present_raw"])
        check_control()
        writes.send("Goal_Position", intended)
        synced = read("GOAL_READBACK_TORQUE_OFF")
        _check(synced, torque=0, present=intended, goal=intended)
        # Last fresh state in this same exclusive session, before ON packet.
        ready = read("PRE_ENABLE_RECHECK")
        _check(ready, torque=0, present=intended, goal=intended)
        check_control()
        writes.send("Torque_Enable", {axis: 1 for axis in AXES})
        immediate = read("IMMEDIATE_AFTER_ENABLE", immediate=True)
        _check(immediate, torque=1, present=intended, goal=intended)
        started = observed_at = audit[-1]["monotonic"]
        check_control()
        samples = [immediate]
        # Measure actual observation span, not time spent in slow owner probes
        # after the last sample. A final sample must itself reach >= 3 seconds.
        while observed_at - started < STABILITY_S:
            sleep(max(0.0, min(0.1, STABILITY_S - (monotonic() - started))))
            sample = read("POST_ENABLE_STABILITY")
            _check(sample, torque=1, present=intended, goal=intended)
            samples.append(sample)
            observed_at = audit[-1]["monotonic"]
        elapsed = observed_at - started
        return {"status": "HOLD_RESTORED", "intended_present_raw": intended,
                "final": samples[-1], "stability_seconds": elapsed,
                "stability_samples": len(samples), "max_goal_present_raw_diff": 0,
                "goal_write_attempts": writes.attempts["Goal_Position"],
                "torque_on_write_attempts": writes.attempts["Torque_Enable"],
                "torque_off_write_attempts": 0, "config_writes": 0}
    except BaseException as error:
        audit.append({"phase": "ABORT_NO_FURTHER_WRITES", "monotonic": monotonic(),
                      "error": f"{type(error).__name__}:{error}",
                      "write_attempts": dict(writes.attempts)})
        raise
    finally:
        writes.stop()  # Never roll back torque, rewrite Goal, or retry.


def run_exclusive_session(*, lease, bus_factory, seal, stop_requested, audit,
                          monotonic=time.monotonic, sleep=time.sleep):
    bus = writes = None
    lease.acquire()
    try:
        bus = bus_factory()
        writes = OneShotRawWrites(bus)  # Installed BEFORE opening the port.
        bus.connect(handshake=False)
        seal(bus)
        lease.mark_connected()
        return restore_hold(bus, writes, guard=lease.ensure_exclusive,
                            stop_requested=stop_requested, audit=audit,
                            monotonic=monotonic, sleep=sleep)
    finally:
        if writes is not None:
            writes.stop()
        try:
            if bus is not None and bus.is_connected:
                bus.disconnect(disable_torque=False)
        finally:
            lease.release()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--approval")
    parser.add_argument("--port", default="/dev/ttyACM1")
    parser.add_argument("--serial", default="5AE6058306")
    parser.add_argument("--audit", type=Path)
    args = parser.parse_args(argv)
    if not args.live:
        print(json.dumps({"mode": "OFFLINE_PLAN_ONLY", "serial_open": 0,
                          "motor_command": 0, "live_restore": "NOT_RUN"}))
        return 0
    if args.approval != APPROVAL or args.audit is None:
        parser.error("--live requires scoped approval and a new --audit file")
    if input(f"Type {SITE_CONFIRMATION}: ") != SITE_CONFIRMATION:
        print("NOT_RUN:onsite_confirmation_missing")
        return 2
    # Runtime import only after live authorization; default/fake need no SDK.
    from lerobot.robots.so_follower import SO101Follower, SO101FollowerConfig

    stopping = False

    def stop(_signum, _frame):
        nonlocal stopping
        stopping = True

    def bus_factory():
        robot = SO101Follower(SO101FollowerConfig(
            port=args.port, id="so-101", cameras={},
            disable_torque_on_disconnect=False))
        return robot.bus  # robot.connect/configure/send_action never called.

    lease = ExclusiveFollowerLease(SystemBusProbe(), port=Path(args.port),
                                   serial_short=args.serial)
    audit = []
    # Refuse overwrites and audit-path failure BEFORE any serial connection.
    with args.audit.open("x", encoding="utf-8") as output:
        old = {sig: signal.signal(sig, stop) for sig in (signal.SIGINT, signal.SIGTERM)}
        try:
            result = run_exclusive_session(
                lease=lease, bus_factory=bus_factory,
                seal=lambda bus: fcntl.ioctl(bus.port_handler.ser.fileno(), termios.TIOCEXCL),
                stop_requested=lambda: stopping, audit=audit)
            print(json.dumps(result))
            return 0
        except Exception as error:
            print(f"ATOMIC_HOLD_RESTORE_ABORTED:{type(error).__name__}:{error}")
            return 1
        finally:
            json.dump(audit, output, indent=2)
            output.flush()
            for sig, handler in old.items():
                signal.signal(sig, handler)


if __name__ == "__main__":
    raise SystemExit(main())
