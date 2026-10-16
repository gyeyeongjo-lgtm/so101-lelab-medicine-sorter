#!/usr/bin/env python3
"""No-reconfigure, relative-start empirical teaching from the current HOLD.

Default CLI is offline only. A later, separately approved live invocation must
use a fresh write-blocked pre-connect snapshot and a new one-shot ticket.
Nothing here calls LeLab /move-arm, configure, calibration writes, or torque.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import logging
import math
import os
from pathlib import Path
import signal
import termios
import time
from typing import Callable, Mapping, Sequence

if __package__:
    from .relative_start_teleop import (
        ACTION_KEYS, JOINTS, MAX_ARM_COMMAND_STEP_DEG, calibrated_action_bounds, capture_origins,
        dispatch_guarded_relative_action, out_of_range_targets,
        oversized_arm_steps, relative_target,
    )
    from .so101_exclusive_bus import ExclusiveFollowerLease, SystemBusProbe
    from .teleop_cycle_trace import (
        CycleTrace, load_grasp_fk, load_pre_connect_snapshot,
        read_same_owner_diagnostics,
    )
    from .temporary_elbow_direction_guard import guarded_elbow_send
else:
    from relative_start_teleop import (
        ACTION_KEYS, JOINTS, MAX_ARM_COMMAND_STEP_DEG, calibrated_action_bounds, capture_origins,
        dispatch_guarded_relative_action, out_of_range_targets,
        oversized_arm_steps, relative_target,
    )
    from so101_exclusive_bus import ExclusiveFollowerLease, SystemBusProbe
    from teleop_cycle_trace import (
        CycleTrace, load_grasp_fk, load_pre_connect_snapshot,
        read_same_owner_diagnostics,
    )
    from temporary_elbow_direction_guard import guarded_elbow_send


LOGGER = logging.getLogger("supervised_teaching_from_current_hold")
FOLLOWER_SERIAL = "5AE6058306"
LEADER_SERIAL = "5AE6085272"
REFERENCE_PRESENT_RAW = dict(zip(JOINTS, (2065, 1466, 2649, 2497, 1611, 490)))
REFERENCE_GOAL_RAW = dict(zip(JOINTS, (2065, 1466, 2649, 2497, 1611, 490)))
MAX_REFERENCE_DRIFT_RAW = 0
MAX_GOAL_PRESENT_RAW_DIFF = 0
QUANTIZED_REFERENCE_PRESENT_RAW = dict(zip(JOINTS, (2065, 1467, 2649, 2497, 1612, 490)))
QUANTIZED_REFERENCE_GOAL_RAW = dict(zip(JOINTS, (2065, 1466, 2649, 2497, 1611, 490)))
MAX_QUANTIZED_GOAL_PRESENT_RAW_DIFF = 1
# 2026-10-11 stationary HOLD: 10 consecutive ~1 s samples, max gap 10 raw.
# This bounds startup only; trajectory convergence tolerances are untouched.
MAX_PRE_ARM_HOLD_GAP_RAW = 10
MAX_TEMPERATURE_C = 55
STILLNESS_S = 3.0
MAX_GRIPPER_STEP_PP = 2.0  # Conservative fail-closed cap for manually opened fingers.
MAX_GRIPPER_OPEN_PP = 34.577723378  # Prior human-confirmed opening; do not exceed it here.


def slew_relative_target(
    requested: Mapping[str, float], previous: Mapping[str, float],
) -> tuple[dict[str, float], float]:
    """One coordinated step toward the newest request; never queue old targets.

    Every axis, including the gripper, uses the same interpolation fraction.
    The caller still validates the *full* requested target and gripper rules,
    then applies the unchanged arm/Elbow guards to this candidate before send.
    """
    if set(requested) != set(ACTION_KEYS) or set(previous) != set(ACTION_KEYS):
        raise ValueError("slew_target_keys_invalid")
    target = {key: float(requested[key]) for key in ACTION_KEYS}
    before = {key: float(previous[key]) for key in ACTION_KEYS}
    if not all(math.isfinite(value) for values in (target, before)
               for value in values.values()):
        raise ValueError("slew_target_nonfinite")
    delta = {key: target[key] - before[key] for key in ACTION_KEYS}
    if not all(math.isfinite(value) for value in delta.values()):
        raise ValueError("slew_delta_nonfinite")
    fraction = 1.0
    for key in ACTION_KEYS:
        limit = (MAX_GRIPPER_STEP_PP if key == "gripper.pos"
                 else MAX_ARM_COMMAND_STEP_DEG)
        if abs(delta[key]) > limit:
            fraction = min(fraction, limit / abs(delta[key]))
    if fraction == 1.0:
        return target, fraction

    while True:
        candidate = {key: before[key] + fraction * delta[key] for key in ACTION_KEYS}
        if (not oversized_arm_steps(candidate, before) and
                abs(candidate["gripper.pos"] - before["gripper.pos"]) <= MAX_GRIPPER_STEP_PP):
            return candidate, fraction
        # Floating-point addition can round a nominal 2-degree step upwards.
        # Reduce the common fraction, never widen the existing strict guard.
        fraction = math.nextafter(fraction, 0.0)


def hold_stable_quantized(samples: Sequence[Mapping[str, object]]) -> bool:
    """Separate read-only verdict; never changes the exact-zero HOLD contract."""
    if len(samples) < 2:
        return False
    first_present = samples[0].get("present_raw")
    first_goal = samples[0].get("goal_raw")
    if not isinstance(first_present, Mapping) or not isinstance(first_goal, Mapping):
        return False
    for sample in samples:
        present, goal = sample.get("present_raw"), sample.get("goal_raw")
        moving, temperature = sample.get("moving"), sample.get("temperature_c")
        if any(not isinstance(values, Mapping) or set(values) != set(JOINTS)
               for values in (present, goal, moving, temperature)):
            return False
        if present != first_present or goal != first_goal:
            return False
        if any(type(present[name]) is not int or type(goal[name]) is not int or
               abs(goal[name] - present[name]) > MAX_QUANTIZED_GOAL_PRESENT_RAW_DIFF or
               type(moving[name]) is not int or moving[name] != 0 or
               not isinstance(temperature[name], (int, float)) or
               not 0 <= temperature[name] <= MAX_TEMPERATURE_C
               for name in JOINTS):
            return False
    return True


def pre_arm_hold_stability(samples: Sequence[Mapping[str, object]]) -> bool:
    """Quantized teaching startup only: bounded, non-growing gap and no drift."""
    if len(samples) < 2:
        return False
    first_present = samples[0].get("present_raw")
    first_goal = samples[0].get("goal_raw")
    if any(not isinstance(values, Mapping) or set(values) != set(JOINTS)
           for values in (first_present, first_goal)):
        return False
    if any(type(first_present[name]) is not int or type(first_goal[name]) is not int
           for name in JOINTS):
        return False
    first_gap = {name: abs(first_goal[name] - first_present[name]) for name in JOINTS}
    for sample in samples:
        present, goal = sample.get("present_raw"), sample.get("goal_raw")
        moving, temperature = sample.get("moving"), sample.get("temperature_c")
        if any(not isinstance(values, Mapping) or set(values) != set(JOINTS)
               for values in (present, goal, moving, temperature)):
            return False
        if present != first_present or goal != first_goal:
            return False
        if any(type(present[name]) is not int or type(goal[name]) is not int or
               abs(goal[name] - present[name]) > MAX_PRE_ARM_HOLD_GAP_RAW or
               abs(goal[name] - present[name]) > first_gap[name] or
               type(moving[name]) is not int or moving[name] != 0 or
               not isinstance(temperature[name], (int, float)) or
               not 0 <= temperature[name] <= MAX_TEMPERATURE_C
               for name in JOINTS):
            return False
    return True


def _raw(bus, register: str) -> dict[str, int]:
    values = bus.sync_read(register, normalize=False, num_retry=2)
    if set(values) != set(JOINTS) or any(type(value) is not int for value in values.values()):
        raise RuntimeError(f"{register}_invalid")
    return {name: values[name] for name in JOINTS}


def make_write_firewall(bus, *, goals_enabled: Callable[[], bool]) -> list[dict]:
    """No bus writes except six-axis Goal after explicit teaching arm."""
    original_sync_write = bus.sync_write
    writes: list[dict] = []

    def denied(*_args, **_kwargs):
        raise RuntimeError("current_hold_forbids_config_or_torque_write")

    def guarded_sync_write(register, values, *args, **kwargs):
        if (not goals_enabled() or register != "Goal_Position" or
                set(values) != set(JOINTS)):
            raise RuntimeError("current_hold_forbids_unarmed_or_partial_goal_write")
        writes.append(dict(values))
        return original_sync_write(register, values, *args, **kwargs)

    for method in ("write", "write_calibration", "configure_motors",
                   "enable_torque", "disable_torque"):
        if hasattr(bus, method):
            setattr(bus, method, denied)
    bus.sync_write = guarded_sync_write
    return writes


def _check_hold(diagnostics: Mapping[str, object], torque: Mapping[str, int],
                *, startup: bool, expected_goal: Mapping[str, int] | None = None,
                max_goal_present_raw_diff: int = MAX_GOAL_PRESENT_RAW_DIFF) -> None:
    present = diagnostics["present_raw"]
    goal = diagnostics["goal_raw"]
    moving = diagnostics["moving"]
    temperatures = diagnostics["temperature_c"]
    if set(torque) != set(JOINTS) or any(torque[name] != 1 for name in JOINTS):
        raise RuntimeError("current_hold_torque_not_all_on")
    if any(temperatures[name] > MAX_TEMPERATURE_C for name in JOINTS):
        raise RuntimeError("current_hold_temperature_gate")
    if startup and any(moving[name] != 0 for name in JOINTS):
        raise RuntimeError("current_hold_moving_before_arm")
    if expected_goal is not None and goal != expected_goal:
        raise RuntimeError("current_hold_goal_changed_before_arm")
    if startup and any(abs(goal[name] - present[name]) > max_goal_present_raw_diff
                       for name in JOINTS):
        raise RuntimeError("current_hold_goal_present_diff_exceeded")


def run_teaching_from_hold(
    *, trace: CycleTrace | None, pre_connect: Mapping[str, object],
    read_leader: Callable[[], Mapping[str, float]],
    read_leader_torque: Callable[[], Mapping[str, int]],
    read_follower_action: Callable[[], Mapping[str, float]],
    read_diagnostics: Callable[[], Mapping[str, object]],
    read_follower_torque: Callable[[], Mapping[str, int]],
    bounds: Mapping[str, tuple[float, float]],
    send_guarded: Callable[[dict[str, float], float | None], Mapping[str, float] | None],
    enable_goals: Callable[[], None],
    arm_confirm: Callable[[], bool], stop_requested: Callable[[], bool],
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    stillness_s: float = STILLNESS_S, max_run_s: float = 180.0,
    hold_policy: str = "exact_zero",
    recorder_off: bool = False,
) -> dict:
    """Pure session sequencing; caller owns already-connected, write-guarded buses.

    Teaching requires its empirical trace by default. UI teleop may explicitly
    opt out with ``trace=None, recorder_off=True``; this does not bypass any
    startup, movement, or stop guard, and creates/consumes no recording ticket.
    ``enable_goals`` is called only after the fresh-origin startup gates pass.
    """
    if stillness_s < STILLNESS_S or not 0 < max_run_s <= 180:
        raise ValueError("teaching_time_contract_invalid")
    if recorder_off and trace is not None:
        raise ValueError("recorder_off_trace_conflict")
    if not recorder_off and (trace is None or
                             trace.capture_kind != "empirical_relative_teaching"):
        raise RuntimeError("empirical_recorder_required")
    if hold_policy not in ("exact_zero", "quantized"):
        raise ValueError("unknown_hold_policy")
    reference_present = (QUANTIZED_REFERENCE_PRESENT_RAW if hold_policy == "quantized"
                         else REFERENCE_PRESENT_RAW)
    reference_goal = (QUANTIZED_REFERENCE_GOAL_RAW if hold_policy == "quantized"
                      else REFERENCE_GOAL_RAW)
    max_diff = (MAX_PRE_ARM_HOLD_GAP_RAW if hold_policy == "quantized"
                else MAX_GOAL_PRESENT_RAW_DIFF)
    if any(read_leader_torque()[name] != 0 for name in JOINTS):
        raise RuntimeError("leader_not_passive_without_torque_write")
    leader_start = dict(read_leader())
    first = dict(read_diagnostics())
    goal_start = dict(first["goal_raw"])
    _check_hold(first, read_follower_torque(), startup=True,
                max_goal_present_raw_diff=max_diff)
    reference_present_exact = all(
        abs(first["present_raw"][name] - reference_present[name]) <=
        MAX_REFERENCE_DRIFT_RAW for name in JOINTS)
    reference_goal_exact = goal_start == reference_goal
    reference_exact_match = reference_present_exact and reference_goal_exact
    if hold_policy == "exact_zero" and not reference_present_exact:
        raise RuntimeError("current_hold_reference_present_changed")
    if hold_policy == "exact_zero" and not reference_goal_exact:
        raise RuntimeError("current_hold_reference_goal_changed")
    if any(abs(first["present_raw"][name] - pre_connect["present_raw"][name]) > 0
           for name in JOINTS) or goal_start != pre_connect["goal_raw"]:
        raise RuntimeError("pre_connect_follower_changed")
    if trace is not None:
        trace.record_startup("PRE_CONNECT_PRESENT", pre_connect)
        trace.record_startup("FIRST_POST_CONNECT", first)

    start = monotonic()
    settled = first
    samples = 0
    hold_samples = [first]
    while True:
        if stop_requested():
            return {"status": "STOPPED_BEFORE_ARM", "goal_sends": 0,
                    "first_goal_skipped": True}
        if dict(read_leader()) != leader_start:
            raise RuntimeError("leader_moved_during_startup_stillness")
        settled = dict(read_diagnostics())
        _check_hold(settled, read_follower_torque(), startup=True,
                    expected_goal=goal_start, max_goal_present_raw_diff=max_diff)
        if any(abs(settled["present_raw"][name] - first["present_raw"][name]) > 0
               for name in JOINTS):
            raise RuntimeError("present_drift_during_startup_stillness")
        if trace is not None:
            trace.record_startup("PRE_ARM_SETTLE", settled)
        hold_samples.append(settled)
        samples += 1
        if monotonic() - start >= stillness_s:
            break
        sleep(0.1)
    current_fresh_stability = (pre_arm_hold_stability(hold_samples)
                               if hold_policy == "quantized"
                               else hold_stable_quantized(hold_samples))
    if hold_policy == "quantized" and not current_fresh_stability:
        raise RuntimeError("pre_arm_hold_stability_failed_before_arm")
    if trace is not None:
        trace.record_startup("SETTLED", settled)
        trace.record_settle_result({"first": first, "settled": settled,
                                   "reference_exact_match": reference_exact_match,
                                   "current_fresh_stability": current_fresh_stability,
                                   "reference_present_delta_raw": {
                                       name: first["present_raw"][name] - reference_present[name]
                                       for name in JOINTS},
                                   "reference_goal_delta_raw": {
                                       name: goal_start[name] - reference_goal[name]
                                       for name in JOINTS},
                                   "drift_degree": {
                                       name: settled["present_degree_or_percent"][name]
                                       - pre_connect["present_degree_or_percent"][name]
                                       for name in JOINTS[:-1]}})

    origins = capture_origins(read_leader, read_follower_action)
    if out_of_range_targets(origins.follower, bounds):
        raise RuntimeError("fresh_follower_origin_outside_calibrated_range")
    if origins.leader != leader_start:
        raise RuntimeError("leader_moved_before_origin_capture")
    fresh = dict(read_diagnostics())
    _check_hold(fresh, read_follower_torque(), startup=True,
                expected_goal=goal_start, max_goal_present_raw_diff=max_diff)
    if any(abs(fresh["present_raw"][name] - settled["present_raw"][name]) > 0
           for name in JOINTS):
        raise RuntimeError("follower_changed_after_origin_capture")
    if not arm_confirm() or stop_requested():
        return {"status": "STOPPED_BEFORE_ARM", "goal_sends": 0,
                "first_goal_skipped": True, "stillness_samples": samples,
                "reference_exact_match": reference_exact_match,
                "current_fresh_stability": current_fresh_stability}
    if dict(read_leader()) != origins.leader:
        raise RuntimeError("leader_moved_before_teaching_arm")
    ready = dict(read_diagnostics())
    _check_hold(ready, read_follower_torque(), startup=True,
                expected_goal=goal_start, max_goal_present_raw_diff=max_diff)
    if any(abs(ready["present_raw"][name] - fresh["present_raw"][name]) > 0
           for name in JOINTS):
        raise RuntimeError("follower_changed_before_teaching_arm")
    if trace is not None:
        trace.arm_teaching()
        trace.start_teaching()
    enable_goals()

    def feedback() -> dict[str, float]:
        current = read_follower_action()
        return {name: current[f"{name}.pos"] for name in JOINTS}

    previous = dict(origins.follower)
    previous_elbow = previous["elbow_flex.pos"]
    expected_goal_raw = dict(ready["goal_raw"])
    if trace is not None:
        trace.observe_relative_cycle(
            leader_action=origins.leader, relative_target=previous,
            command_sent=False, gripper_goal_sent=False,
            read_feedback=feedback,
            read_diagnostics=lambda _feedback: read_diagnostics())
    first_goal_skipped = True
    sends = 0
    max_emitted_step = 0.0
    started = monotonic()
    while not stop_requested() and monotonic() - started < max_run_s:
        actual = dict(read_diagnostics())
        _check_hold(actual, read_follower_torque(), startup=False)
        if actual["goal_raw"] != expected_goal_raw:
            raise RuntimeError("external_goal_change_during_teaching")
        leader_now = dict(read_leader())
        target = relative_target(leader_now, origins)
        violations = oversized_arm_steps(target, previous)
        if trace is not None:
            trace.record_relative_request(
                leader_action=leader_now, relative_target=target,
                previous_target=previous, step_violations=violations,
                actual_diagnostics=actual)
        if out_of_range_targets(target, bounds):
            raise RuntimeError("target_outside_calibrated_range")
        if abs(target["gripper.pos"] - previous["gripper.pos"]) > MAX_GRIPPER_STEP_PP:
            raise RuntimeError("gripper_step_exceeds_teaching_guard")
        if target["gripper.pos"] < previous["gripper.pos"]:
            raise RuntimeError("gripper_close_forbidden_before_grasp")
        if target["gripper.pos"] > MAX_GRIPPER_OPEN_PP:
            raise RuntimeError("gripper_exceeds_last_human_confirmed_opening")
        emitted, _fraction = slew_relative_target(target, previous)
        if oversized_arm_steps(emitted, previous):
            raise RuntimeError("arm_step_exceeds_existing_guard")
        if abs(emitted["gripper.pos"] - previous["gripper.pos"]) > MAX_GRIPPER_STEP_PP:
            raise RuntimeError("gripper_step_exceeds_teaching_guard")
        if stop_requested():
            break
        sent = False
        if any(emitted[key] != previous[key] for key in ACTION_KEYS):
            sent_action = None

            def tracked_send(command, elbow):
                nonlocal sent_action
                if stop_requested():
                    return None
                sent_action = send_guarded(command, elbow)
                return sent_action

            before_dispatch = dict(previous)
            dispatch = dispatch_guarded_relative_action(
                emitted, previous_elbow, previous, tracked_send)
            previous_elbow = dispatch.previous_elbow_target_deg
            sent = dispatch.sent
            if sent:
                # The sender may return a different accepted target; never
                # advance the slew origin to an unsent request or a HOLD.
                previous = {key: float(sent_action[key]) for key in ACTION_KEYS}
                if oversized_arm_steps(previous, before_dispatch):
                    raise RuntimeError("sender_returned_step_over_existing_guard")
                max_emitted_step = max(max_emitted_step, *(
                    abs(previous[key] - before_dispatch[key]) for key in ACTION_KEYS[:-1]))
                sends += 1
                expected_goal_raw = dict(read_diagnostics()["goal_raw"])
                if trace is not None:
                    trace.record_first_sent_goal(
                        requested_target=previous,
                        goal_raw=expected_goal_raw)
        # requests.jsonl retains the full leader request; cycles.jsonl records
        # the dispatched step (or the unsent candidate, marked command_sent=0).
        if trace is not None:
            trace.observe_relative_cycle(
                leader_action=leader_now, relative_target=previous if sent else emitted,
                command_sent=sent, gripper_goal_sent=sent,
                read_feedback=feedback,
                read_diagnostics=lambda _feedback: read_diagnostics())
        sleep(0.1)

    final = []
    for index in range(3):
        sample = dict(read_diagnostics())
        _check_hold(sample, read_follower_torque(), startup=False)
        if any(sample["moving"][name] != 0 for name in JOINTS):
            raise RuntimeError("follower_moving_after_teaching_stop")
        final.append(sample)
        if index < 2:
            sleep(0.2)
    if trace is not None:
        (trace.session_dir / "final_pose_3sample.json").write_text(
            json.dumps({"samples": final}, separators=(",", ":")) + "\n",
            encoding="utf-8")
    return {"status": "STOPPED", "goal_sends": sends,
            "max_emitted_arm_step_deg": max_emitted_step,
            "first_goal_skipped": first_goal_skipped,
            "stillness_samples": samples,
            "reference_exact_match": reference_exact_match,
            "current_fresh_stability": current_fresh_stability,
            "final_read_only_samples": len(final)}


def _live(args) -> int:
    from lerobot.robots.so_follower import SO101Follower, SO101FollowerConfig
    from lerobot.teleoperators.so_leader import SO101Leader, SO101LeaderConfig

    if args.approval != "RUN SUPERVISED C APPROACH TEACHING":
        raise RuntimeError("live_approval_phrase_missing")
    if not args.ticket.is_file() or args.output.exists():
        raise RuntimeError("fresh_one_shot_ticket_or_output_missing")
    pre_connect = load_pre_connect_snapshot(args.pre_connect_json)
    if input("Confirm supported, stopped, fully non-contact, leader still: ") != \
            "CURRENT HOLD SITE CONFIRMED":
        raise RuntimeError("site_confirmation_missing")
    fk = load_grasp_fk(args.urdf, args.tcp_config)
    old_ticket = os.environ.get("LELAB_TELEOP_TRACE_ONCE_TICKET")
    os.environ["LELAB_TELEOP_TRACE_ONCE_TICKET"] = str(args.ticket)
    trace = CycleTrace(args.output, capture_kind="empirical_relative_teaching")
    follower_lease = ExclusiveFollowerLease(SystemBusProbe(), port=Path(args.follower_port),
                                             serial_short=FOLLOWER_SERIAL)
    leader_lease = ExclusiveFollowerLease(
        SystemBusProbe(), port=Path(args.leader_port), serial_short=LEADER_SERIAL,
        lock_path=Path(follower_lease.lock_path).with_name("so101-leader-program.lock"))
    follower = leader = None
    armed = False
    stopping = False
    writes: list[dict] = []

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
        writes = make_write_firewall(
            follower.bus, goals_enabled=lambda: armed and not stopping)
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

        def diagnostics():
            follower_lease.ensure_exclusive()
            leader_lease.ensure_exclusive()
            return read_same_owner_diagnostics(follower, fk)

        def guarded_send(action, previous_elbow):
            if stopping:
                return None
            follower_lease.ensure_exclusive()
            leader_lease.ensure_exclusive()
            return guarded_elbow_send(follower, action, previous_elbow, LOGGER)

        def arm_confirm():
            print("CURRENT_HOLD_STARTUP_PASS: no Goal/config/torque write")
            return input("Type START CURRENT HOLD TEACHING: ") == \
                "START CURRENT HOLD TEACHING"

        def enable_goals():
            nonlocal armed
            armed = True

        result = run_teaching_from_hold(
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
        if len(writes) != result["goal_sends"]:
            raise RuntimeError("goal_write_count_mismatch")
        manifest = trace.finish(stop_reason="teleoperation_inactive")
        print(json.dumps({"result": result, "manifest": manifest}, separators=(",", ":")))
        return 0
    except (Exception, KeyboardInterrupt) as error:
        trace.record_startup_failure(error)
        if not trace.closed:
            trace.finish(stop_reason="worker_error")
        print(f"CURRENT_HOLD_TEACHING_ABORT:{type(error).__name__}:{error}")
        return 1
    finally:
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
    parser.add_argument("--pre-connect-json", type=Path)
    parser.add_argument("--urdf", type=Path)
    parser.add_argument("--tcp-config", type=Path)
    args = parser.parse_args(argv)
    if not args.live:
        print(json.dumps({"entrypoint": "DRY_RUN_ONLY", "recorder": "READY_OFFLINE",
                          "serial_open": 0, "goal_write": 0, "torque_write": 0,
                          "config_write": 0, "inference": False, "replay": False}))
        return 0
    if any(value is None for value in (
            args.ticket, args.output, args.pre_connect_json, args.urdf, args.tcp_config)):
        raise RuntimeError("live_inputs_required")
    return _live(args)


if __name__ == "__main__":
    raise SystemExit(main())
