#!/usr/bin/env python3
"""Atomic current-pose HOLD followed by teaching without reconnecting.

The default invocation is hardware-free. Live mode is a thin composition of
the existing atomic HOLD restore and no-reconfigure teaching routines: both
serial buses are acquired and connected once, the follower write firewall is
handed from HOLD to teaching, and disconnect happens only after teaching ends.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import logging
import os
from pathlib import Path
import signal
import termios
import time
from typing import Callable, Mapping

if __package__:
    from .atomic_hold_restore import OneShotRawWrites, restore_hold
    from .relative_start_teleop import JOINTS, calibrated_action_bounds
    from .so101_exclusive_bus import ExclusiveFollowerLease, SystemBusProbe
    from .supervised_teaching_from_current_hold import (
        _raw, make_write_firewall, run_teaching_from_hold,
    )
    from .teleop_cycle_trace import CycleTrace, load_grasp_fk, read_same_owner_diagnostics
    from .temporary_elbow_direction_guard import guarded_elbow_send
else:
    from atomic_hold_restore import OneShotRawWrites, restore_hold
    from relative_start_teleop import JOINTS, calibrated_action_bounds
    from so101_exclusive_bus import ExclusiveFollowerLease, SystemBusProbe
    from supervised_teaching_from_current_hold import (
        _raw, make_write_firewall, run_teaching_from_hold,
    )
    from teleop_cycle_trace import CycleTrace, load_grasp_fk, read_same_owner_diagnostics
    from temporary_elbow_direction_guard import guarded_elbow_send


LOGGER = logging.getLogger("single_session_demo")
FOLLOWER_SERIAL = "5AE6058306"
LEADER_SERIAL = "5AE6085272"
APPROVAL = "RUN SINGLE SESSION DEMO"
SITE_CONFIRMATION = "SUPPORTED STOPPED NON_CONTACT CLEAR STOP_READY"


def run_single_session_lifecycle(
    *, follower_bus, atomic_writes: OneShotRawWrites,
    guard: Callable[[], None], stop_requested: Callable[[], bool],
    hold_audit: list[dict], goals_enabled: Callable[[], bool],
    read_transition: Callable[[], Mapping[str, object]],
    read_transition_torque: Callable[[], Mapping[str, int]],
    run_teaching: Callable[[Mapping[str, object]], dict],
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> dict:
    """Run both proven stages while the caller retains the same open buses."""
    hold = restore_hold(
        follower_bus, atomic_writes, guard=guard,
        stop_requested=stop_requested, audit=hold_audit,
        monotonic=monotonic, sleep=sleep)
    if stop_requested():
        raise RuntimeError("stop_requested_after_hold")

    # restore_hold closes its one-shot gate. Release only sync_write, then
    # immediately replace it with the existing armed-Goal-only firewall.
    atomic_writes.handoff_to_teaching()
    teaching_writes = make_write_firewall(
        follower_bus, goals_enabled=goals_enabled)
    transition = dict(read_transition())
    final = hold["final"]
    for field in ("present_raw", "goal_raw", "moving"):
        if transition.get(field) != final[field]:
            raise RuntimeError(f"hold_changed_before_teaching:{field}")
    transition_torque = dict(read_transition_torque())
    if transition_torque != final["torque"]:
        raise RuntimeError("hold_changed_before_teaching:torque")
    if any(transition_torque[name] != 1 for name in JOINTS):
        raise RuntimeError("torque_not_all_on_at_handoff")
    if any(transition["moving"][name] != 0 for name in JOINTS):
        raise RuntimeError("moving_at_handoff")

    teaching = run_teaching(transition)
    if len(teaching_writes) != teaching["goal_sends"]:
        raise RuntimeError("goal_write_count_mismatch")
    return {
        "status": "SINGLE_SESSION_COMPLETE",
        "hold": hold,
        "teaching": teaching,
        "connect_session_retained": True,
        "disconnects_between_stages": 0,
        "goal_write_attempts_before_teaching": hold["goal_write_attempts"],
        "torque_on_write_attempts": hold["torque_on_write_attempts"],
        "torque_off_write_attempts": 0,
        "teaching_goal_writes": len(teaching_writes),
        "config_writes": 0,
    }


def _live(args) -> int:
    from lerobot.robots.so_follower import SO101Follower, SO101FollowerConfig
    from lerobot.teleoperators.so_leader import SO101Leader, SO101LeaderConfig

    if args.approval != APPROVAL:
        raise RuntimeError("live_approval_phrase_missing")
    if not args.ticket.is_file() or args.output.exists():
        raise RuntimeError("fresh_one_shot_ticket_or_output_missing")
    if input(f"Type {SITE_CONFIRMATION}: ") != SITE_CONFIRMATION:
        print("NOT_RUN:onsite_confirmation_missing")
        return 2

    fk = load_grasp_fk(args.urdf, args.tcp_config)
    old_ticket = os.environ.get("LELAB_TELEOP_TRACE_ONCE_TICKET")
    os.environ["LELAB_TELEOP_TRACE_ONCE_TICKET"] = str(args.ticket)
    trace = CycleTrace(args.output, capture_kind="empirical_relative_teaching")
    follower_lease = ExclusiveFollowerLease(
        SystemBusProbe(), port=Path(args.follower_port), serial_short=FOLLOWER_SERIAL)
    leader_lease = ExclusiveFollowerLease(
        SystemBusProbe(), port=Path(args.leader_port), serial_short=LEADER_SERIAL,
        lock_path=Path(follower_lease.lock_path).with_name("so101-leader-program.lock"))
    follower = leader = None
    atomic_writes = None
    armed = False
    stopping = False
    hold_audit: list[dict] = []

    def on_stop(_signal, _frame):
        nonlocal stopping
        stopping = True
        if not armed:
            raise KeyboardInterrupt

    previous_sigint = signal.signal(signal.SIGINT, on_stop)
    previous_sigterm = signal.signal(signal.SIGTERM, on_stop)
    try:
        follower_lease.acquire()
        leader_lease.acquire()
        follower = SO101Follower(SO101FollowerConfig(
            port=args.follower_port, id="so-101", cameras={}, use_degrees=True,
            max_relative_target=None, disable_torque_on_disconnect=False))
        leader = SO101Leader(SO101LeaderConfig(port=args.leader_port, id="so-101"))

        atomic_writes = OneShotRawWrites(follower.bus)
        make_write_firewall(leader.bus, goals_enabled=lambda: False)
        follower.bus.connect(handshake=False)
        fcntl.ioctl(follower.bus.port_handler.ser.fileno(), termios.TIOCEXCL)
        follower_lease.mark_connected()
        leader.bus.connect(handshake=False)
        fcntl.ioctl(leader.bus.port_handler.ser.fileno(), termios.TIOCEXCL)
        leader_lease.mark_connected()
        if not follower.bus.is_calibrated or not leader.bus.is_calibrated:
            raise RuntimeError("stored_calibration_not_loaded")
        follower.configure = leader.configure = lambda: (_ for _ in ()).throw(
            RuntimeError("configure_forbidden"))
        bounds = calibrated_action_bounds(follower)

        def ensure_owned() -> None:
            follower_lease.ensure_exclusive()
            leader_lease.ensure_exclusive()

        def diagnostics() -> dict:
            ensure_owned()
            return read_same_owner_diagnostics(follower, fk)

        def guarded_send(action, previous_elbow):
            if stopping:
                return None
            ensure_owned()
            return guarded_elbow_send(follower, action, previous_elbow, LOGGER)

        def arm_confirm() -> bool:
            print("SINGLE_SESSION_HOLD_PASS: buses retained; first Goal will be skipped")
            return input("Type START SINGLE SESSION TEACHING: ") == \
                "START SINGLE SESSION TEACHING"

        def enable_goals() -> None:
            nonlocal armed
            armed = True

        def teaching(pre_connect: Mapping[str, object]) -> dict:
            return run_teaching_from_hold(
                trace=trace, pre_connect=pre_connect,
                read_leader=leader.get_action,
                read_leader_torque=lambda: _raw(leader.bus, "Torque_Enable"),
                read_follower_action=lambda: {
                    f"{name}.pos": value for name, value in
                    follower.bus.sync_read("Present_Position").items()},
                read_diagnostics=diagnostics,
                read_follower_torque=lambda: _raw(follower.bus, "Torque_Enable"),
                bounds=bounds, send_guarded=guarded_send,
                enable_goals=enable_goals, arm_confirm=arm_confirm,
                stop_requested=lambda: stopping, hold_policy="quantized")

        result = run_single_session_lifecycle(
            follower_bus=follower.bus, atomic_writes=atomic_writes,
            guard=ensure_owned, stop_requested=lambda: stopping,
            hold_audit=hold_audit, goals_enabled=lambda: armed and not stopping,
            read_transition=diagnostics,
            read_transition_torque=lambda: _raw(follower.bus, "Torque_Enable"),
            run_teaching=teaching)
        (trace.session_dir / "hold_restore_audit.json").write_text(
            json.dumps(hold_audit, indent=2) + "\n", encoding="utf-8")
        manifest = trace.finish(stop_reason="teleoperation_inactive")
        print(json.dumps({"result": result, "manifest": manifest}, separators=(",", ":")))
        return 0
    except (Exception, KeyboardInterrupt) as error:
        trace.record_startup_failure(error)
        (trace.session_dir / "hold_restore_audit.json").write_text(
            json.dumps(hold_audit, indent=2) + "\n", encoding="utf-8")
        if not trace.closed:
            trace.finish(stop_reason="worker_error")
        print(f"SINGLE_SESSION_DEMO_ABORT:{type(error).__name__}:{error}")
        return 1
    finally:
        if atomic_writes is not None:
            atomic_writes.stop()
        signal.signal(signal.SIGINT, previous_sigint)
        signal.signal(signal.SIGTERM, previous_sigterm)
        if leader is not None and leader.bus.is_connected:
            leader.bus.disconnect(disable_torque=False)
        if follower is not None and follower.bus.is_connected:
            follower.bus.disconnect(disable_torque=False)
        leader_lease.release()
        follower_lease.release()
        if old_ticket is None:
            os.environ.pop("LELAB_TELEOP_TRACE_ONCE_TICKET", None)
        else:
            os.environ["LELAB_TELEOP_TRACE_ONCE_TICKET"] = old_ticket


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--approval", default="")
    parser.add_argument("--leader-port", default="/dev/ttyACM0")
    parser.add_argument("--follower-port", default="/dev/ttyACM1")
    parser.add_argument("--ticket", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--urdf", type=Path)
    parser.add_argument("--tcp-config", type=Path)
    args = parser.parse_args(argv)
    if not args.live:
        print(json.dumps({
            "entrypoint": "SINGLE_SESSION_DEMO_DRY_RUN_ONLY",
            "serial_open": 0, "motor_command": 0, "goal_write": 0,
            "torque_write": 0, "config_write": 0,
            "hold_to_teaching_without_disconnect": "READY_FAKE_ONLY",
        }))
        return 0
    if any(value is None for value in (args.ticket, args.output, args.urdf, args.tcp_config)):
        raise RuntimeError("live_inputs_required")
    return _live(args)


if __name__ == "__main__":
    raise SystemExit(main())
