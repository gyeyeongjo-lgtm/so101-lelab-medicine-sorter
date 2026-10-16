#!/usr/bin/env python3
"""Single-purpose, arm-only relative-start contact release.

This is a separate entrypoint from LeLab /move-arm. No recorder, teaching,
inference, replay, calibration/configuration write, or torque toggle is used.
The default invocation is a fake dry-run; live requires a separate approval.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import logging
import math
import signal
import termios
import time
from pathlib import Path

import numpy as np

if __package__:
    from scripts.relative_start_teleop import (
        ACTION_KEYS, ARM_ACTION_KEYS, JOINTS, arm_only_relative_target,
        calibrated_action_bounds, capture_origins, dispatch_guarded_relative_action,
        out_of_range_targets, oversized_arm_steps,
    )
    from scripts.so101_exclusive_bus import ExclusiveFollowerLease, SystemBusProbe
    from scripts.temporary_elbow_direction_guard import guarded_elbow_send
    from scripts.urdf_forward_kinematics import UrdfKinematics
else:
    from relative_start_teleop import (
        ACTION_KEYS, ARM_ACTION_KEYS, JOINTS, arm_only_relative_target,
        calibrated_action_bounds, capture_origins, dispatch_guarded_relative_action,
        out_of_range_targets, oversized_arm_steps,
    )
    from so101_exclusive_bus import ExclusiveFollowerLease, SystemBusProbe
    from temporary_elbow_direction_guard import guarded_elbow_send
    from urdf_forward_kinematics import UrdfKinematics


LOGGER = logging.getLogger("contact_release_only")
ARM_JOINTS = JOINTS[:-1]
FOLLOWER_SERIAL = "5AE6058306"
LEADER_SERIAL = "5AE6085272"
MAX_INITIAL_GOAL_ERROR_RAW = 4  # Last human-confirmed fresh baseline, not a global tolerance.
MAX_TEMPERATURE_C = 55  # Existing servo safety gate.
STILLNESS_S = 3.0
BASELINE_PRESENT_RAW = dict(zip(JOINTS, (2028, 1643, 2754, 2394, 1612, 489)))
BASELINE_GOAL_RAW = dict(zip(JOINTS, (2032, 1642, 2752, 2396, 1612, 490)))


def load_contact_fk(urdf_path: Path, tcp_config_path: Path):
    """Read existing pinned GRASP TCP inputs; no recorder or hardware import."""
    config = json.loads(tcp_config_path.read_text(encoding="utf-8"))
    if hashlib.sha256(urdf_path.read_bytes()).hexdigest() != config["urdf_sha256"]:
        raise RuntimeError("contact_release_URDF_SHA_mismatch")
    offset = np.asarray(config["pick_grasp_tcp_offset_gripper_mm"], dtype=float)
    if offset.shape != (3,) or not np.isfinite(offset).all():
        raise RuntimeError("contact_release_GRASP_TCP_invalid")
    kinematics = UrdfKinematics.from_file(urdf_path)
    urdf_names = ("Rotation", "Pitch", "Elbow", "Wrist_Pitch", "Wrist_Roll")

    def fk(degrees: dict[str, float]) -> list[float]:
        if set(degrees) != set(ARM_JOINTS):
            raise RuntimeError("contact_release_FK_joint_shape_invalid")
        q = {urdf_name: math.radians(float(degrees[name]))
             for name, urdf_name in zip(ARM_JOINTS, urdf_names)}
        transform = kinematics.forward(q, "base", "gripper")
        xyz = transform[:3, 3] * 1000.0 + transform[:3, :3] @ offset
        if not np.isfinite(xyz).all():
            raise RuntimeError("contact_release_FK_nonfinite")
        return [float(value) for value in xyz]

    return fk


def _raw(bus, register: str) -> dict[str, int]:
    values = bus.sync_read(register, normalize=False, num_retry=2)
    if set(values) != set(JOINTS) or any(type(v) is not int for v in values.values()):
        raise RuntimeError(f"{register}_invalid")
    return {name: values[name] for name in JOINTS}


def follower_snapshot(bus) -> dict:
    return {
        "present": _raw(bus, "Present_Position"),
        "goal": _raw(bus, "Goal_Position"),
        "torque": _raw(bus, "Torque_Enable"),
        "moving": _raw(bus, "Moving"),
        # The installed grouped temperature path has returned mismatched
        # packets; use the proven individual register reads instead.
        "temperature": {
            name: int(bus.read("Present_Temperature", name,
                               normalize=False, num_retry=2)) for name in JOINTS
        },
    }


def _check_start(sample: dict) -> None:
    if sample["goal"] != BASELINE_GOAL_RAW:
        raise RuntimeError("goal_changed_from_approved_baseline")
    if any(abs(sample["present"][name] - BASELINE_PRESENT_RAW[name]) > 1
           for name in JOINTS):
        raise RuntimeError("present_changed_from_approved_baseline")
    if any(value != 1 for value in sample["torque"].values()):
        raise RuntimeError("contact_release_requires_unchanged_torque_on")
    if any(value != 0 for value in sample["moving"].values()):
        raise RuntimeError("follower_moving_before_arm")
    if any(value > MAX_TEMPERATURE_C for value in sample["temperature"].values()):
        raise RuntimeError("temperature_gate")
    if any(abs(sample["goal"][name] - sample["present"][name]) >
           MAX_INITIAL_GOAL_ERROR_RAW for name in JOINTS):
        raise RuntimeError("goal_present_baseline_changed")


def _check_live(sample: dict, gripper_goal: int, gripper_present: int) -> None:
    if any(value != 1 for value in sample["torque"].values()):
        raise RuntimeError("torque_changed_during_contact_release")
    if any(value > MAX_TEMPERATURE_C for value in sample["temperature"].values()):
        raise RuntimeError("temperature_gate")
    if sample["goal"]["gripper"] != gripper_goal:
        raise RuntimeError("gripper_goal_changed")
    if sample["present"]["gripper"] != gripper_present:
        raise RuntimeError("gripper_present_changed")


def make_write_firewall(bus, *, allow_arm_goal) -> list[dict]:
    """Forbid all bus writes except a five-axis Goal when explicitly armed."""
    original_sync_write = bus.sync_write
    writes = []

    def denied(*_args, **_kwargs):
        raise RuntimeError("contact_release_forbids_config_or_torque_write")

    def guarded_sync_write(register, values, *args, **kwargs):
        if (not allow_arm_goal() or register != "Goal_Position" or
                set(values) != set(ARM_JOINTS)):
            raise RuntimeError("contact_release_forbids_non_arm_goal_write")
        writes.append(dict(values))
        return original_sync_write(register, values, *args, **kwargs)

    for method in ("write", "write_calibration", "configure_motors",
                   "enable_torque", "disable_torque"):
        if hasattr(bus, method):
            setattr(bus, method, denied)
    bus.sync_write = guarded_sync_write
    return writes


def _action_fk_z(fk, action: dict[str, float]) -> float:
    degrees = {name: action[f"{name}.pos"] for name in ARM_JOINTS}
    return float(fk(degrees)[2])


def run_contact_release(
    *, leader, follower, fk, send_arm, stop_requested, arm_confirm,
    enable_arm_goals,
    monotonic=time.monotonic, sleep=time.sleep, stillness_s=STILLNESS_S,
    max_run_s=60.0,
) -> dict:
    """No connect/configure here: caller supplies already write-guarded buses."""
    if stillness_s < STILLNESS_S or not 0 < max_run_s <= 60.0:
        raise ValueError("contact_release_time_contract_invalid")
    leader_torque = _raw(leader.bus, "Torque_Enable")
    if any(value != 0 for value in leader_torque.values()):
        raise RuntimeError("leader_not_passive_without_torque_write")
    leader_origin_before = dict(leader.get_action())
    baseline = follower_snapshot(follower.bus)
    _check_start(baseline)
    deadline = monotonic() + stillness_s
    stillness_samples = 0
    while True:
        if stop_requested():
            return {"status": "STOPPED_BEFORE_ARM", "arm_goal_sends": 0}
        current_leader = dict(leader.get_action())
        if current_leader != leader_origin_before:
            raise RuntimeError("leader_moved_during_startup_stillness")
        sample = follower_snapshot(follower.bus)
        _check_start(sample)
        if sample["goal"] != baseline["goal"]:
            raise RuntimeError("goal_changed_during_startup_stillness")
        if any(abs(sample["present"][name] - baseline["present"][name]) > 1
               for name in JOINTS):
            raise RuntimeError("present_drift_during_startup_stillness")
        stillness_samples += 1
        if monotonic() >= deadline:
            break
        sleep(0.1)

    origins = capture_origins(leader.get_action,
                              lambda: follower.bus.sync_read("Present_Position"))
    fresh = follower_snapshot(follower.bus)
    _check_start(fresh)
    if fresh["goal"] != baseline["goal"] or any(
        abs(fresh["present"][name] - baseline["present"][name]) > 1
        for name in JOINTS
    ):
        raise RuntimeError("origin_changed_after_stillness")
    frozen_gripper_goal = fresh["goal"]["gripper"]
    frozen_gripper_present = fresh["present"]["gripper"]
    bounds = calibrated_action_bounds(follower)
    previous = dict(origins.follower)
    previous_elbow = previous["elbow_flex.pos"]
    first_goal_skipped = True  # No call to send_arm for the follower origin.
    if not arm_confirm():
        return {"status": "STOPPED_BEFORE_ARM", "arm_goal_sends": 0,
                "first_goal_skipped": first_goal_skipped,
                "stillness_samples": stillness_samples}
    if stop_requested():
        return {"status": "STOPPED_BEFORE_ARM", "arm_goal_sends": 0,
                "first_goal_skipped": first_goal_skipped,
                "stillness_samples": stillness_samples}
    if dict(leader.get_action()) != origins.leader:
        raise RuntimeError("leader_moved_between_origin_and_arm")
    armed_sample = follower_snapshot(follower.bus)
    _check_start(armed_sample)
    if (armed_sample["goal"] != fresh["goal"] or
            any(abs(armed_sample["present"][name] - fresh["present"][name]) > 1
                for name in JOINTS)):
        raise RuntimeError("follower_changed_between_origin_and_arm")
    enable_arm_goals()

    start = monotonic()
    sends = 0
    initial_z = _action_fk_z(fk, origins.follower)
    while not stop_requested() and monotonic() - start < max_run_s:
        sample = follower_snapshot(follower.bus)
        _check_live(sample, frozen_gripper_goal, frozen_gripper_present)
        leader_now = leader.get_action()
        target = arm_only_relative_target(leader_now, origins)
        if out_of_range_targets(target, bounds):
            raise RuntimeError("target_outside_calibrated_range")
        if oversized_arm_steps(target, previous):
            raise RuntimeError("arm_step_exceeds_existing_guard")
        if all(target[key] == previous[key] for key in ARM_ACTION_KEYS):
            sleep(0.1)
            continue
        target_z = _action_fk_z(fk, target)
        if target_z <= initial_z:
            raise RuntimeError("target_not_upward_from_contact")
        actual_action = {f"{name}.pos": value for name, value in
                         follower.bus.sync_read("Present_Position").items()}
        actual_z = _action_fk_z(fk, actual_action)
        if target_z <= actual_z:
            raise RuntimeError("target_not_above_fresh_actual_tcp")
        dispatch = dispatch_guarded_relative_action(
            target, previous_elbow, previous, send_arm, arm_only=True)
        previous_elbow = dispatch.previous_elbow_target_deg
        previous = dispatch.previous_relative_target
        if dispatch.sent:
            sends += 1
            after = follower_snapshot(follower.bus)
            _check_live(after, frozen_gripper_goal, frozen_gripper_present)
            actual_after = {f"{name}.pos": value for name, value in
                            follower.bus.sync_read("Present_Position").items()}
            if _action_fk_z(fk, actual_after) < initial_z:
                raise RuntimeError("actual_tcp_descended_during_contact_release")
        sleep(0.1)

    # STOP only; no extra goal or torque command. The caller then disconnects.
    final = []
    for index in range(3):
        final.append(follower_snapshot(follower.bus))
        if index < 2:
            sleep(0.2)
    for row in final:
        _check_live(row, frozen_gripper_goal, frozen_gripper_present)
    return {"status": "STOPPED", "arm_goal_sends": sends,
            "first_goal_skipped": first_goal_skipped,
            "stillness_samples": stillness_samples, "final_read_only": final}


def _live(args) -> int:
    from lerobot.robots.so_follower import SO101Follower, SO101FollowerConfig
    from lerobot.teleoperators.so_leader import SO101Leader, SO101LeaderConfig

    if args.approval != "RUN CONTACT RELEASE ONLY":
        raise RuntimeError("live_approval_phrase_missing")
    if input("Confirm arm supported, gripper-table contact observed, stop ready: ") != \
            "CONTACT RELEASE SITE CONFIRMED":
        raise RuntimeError("site_confirmation_missing")
    probe = SystemBusProbe()
    follower_lease = ExclusiveFollowerLease(
        probe, port=Path(args.follower_port), serial_short=FOLLOWER_SERIAL)
    leader_lease = ExclusiveFollowerLease(
        probe, port=Path(args.leader_port), serial_short=LEADER_SERIAL,
        lock_path=Path(follower_lease.lock_path).with_name("so101-leader-program.lock"))
    follower = leader = None
    armed = False
    stopping = False

    def stop_requested():
        return stopping

    def on_sigint(_signal, _frame):
        nonlocal stopping
        stopping = True
        # Interrupt a blocked operator prompt as well as the motion loop.
        # The finally block releases both buses without a torque write.
        raise KeyboardInterrupt

    previous_sigint = signal.signal(signal.SIGINT, on_sigint)
    previous_sigterm = signal.signal(signal.SIGTERM, on_sigint)
    try:
        follower_lease.acquire()
        leader_lease.acquire()
        follower = SO101Follower(SO101FollowerConfig(
            port=args.follower_port, id="so-101", cameras={},
            use_degrees=True, max_relative_target=None,
            disable_torque_on_disconnect=False))
        leader = SO101Leader(SO101LeaderConfig(port=args.leader_port, id="so-101"))
        follower_writes = make_write_firewall(follower.bus, allow_arm_goal=lambda: armed)
        make_write_firewall(leader.bus, allow_arm_goal=lambda: False)
        follower.bus.connect(handshake=False)
        fcntl.ioctl(follower.bus.port_handler.ser.fileno(), termios.TIOCEXCL)
        follower_lease.mark_connected()
        leader.bus.connect(handshake=False)
        fcntl.ioctl(leader.bus.port_handler.ser.fileno(), termios.TIOCEXCL)
        leader_lease.mark_connected()
        if not follower.bus.is_calibrated or not leader.bus.is_calibrated:
            raise RuntimeError("stored_calibration_not_loaded")
        # No robot/leader configure or calibration write is called.
        fk = load_contact_fk(args.urdf, args.tcp_config)

        def send_arm(action, previous_elbow):
            if stop_requested():
                return None
            follower_lease.ensure_exclusive()
            leader_lease.ensure_exclusive()
            return guarded_elbow_send(follower, action, previous_elbow, LOGGER)

        def arm_confirm():
            print("STARTUP_STILLNESS_PASS: leader still; no Goal has been sent")
            if input("Type START SMALL UPWARD LEADER MOTION: ") != \
                    "START SMALL UPWARD LEADER MOTION":
                return False
            return True

        def enable_arm_goals():
            nonlocal armed
            armed = True
            print("CONTACT_RELEASE_ARMED")

        result = run_contact_release(
            leader=leader, follower=follower, fk=fk, send_arm=send_arm,
            stop_requested=stop_requested, arm_confirm=arm_confirm,
            enable_arm_goals=enable_arm_goals)
        if len(follower_writes) != result["arm_goal_sends"]:
            raise RuntimeError("arm_goal_write_count_mismatch")
        print(json.dumps(result, separators=(",", ":")))
        return 0
    except Exception as error:
        print(f"CONTACT_RELEASE_ABORT:{type(error).__name__}:{error}")
        return 1
    except KeyboardInterrupt:
        print("CONTACT_RELEASE_STOPPED_BY_OPERATOR: no further Goal sent")
        return 130
    finally:
        signal.signal(signal.SIGINT, previous_sigint)
        signal.signal(signal.SIGTERM, previous_sigterm)
        # Neither disconnect may toggle torque. The contact-release entrypoint
        # never calls the LeLab default connect/configure/disconnect sequence.
        if leader is not None and leader.bus.is_connected:
            leader.bus.disconnect(disable_torque=False)
        if follower is not None and follower.bus.is_connected:
            follower.bus.disconnect(disable_torque=False)
        leader_lease.release()
        follower_lease.release()


def _dry_run() -> int:
    # Tests exercise the injected session and firewall more thoroughly; this
    # CLI proves the default entrypoint never imports LeRobot or opens serial.
    print(json.dumps({"contact_release_entrypoint": "DRY_RUN_ONLY",
                      "serial_open": 0, "motor_command": 0,
                      "torque_write": 0, "gripper_write": 0,
                      "recorder": False, "teaching": False,
                      "inference": False, "replay": False}))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--approval", default="")
    parser.add_argument("--leader-port", default="/dev/ttyACM0")
    parser.add_argument("--follower-port", default="/dev/ttyACM1")
    parser.add_argument("--urdf", type=Path)
    parser.add_argument("--tcp-config", type=Path)
    args = parser.parse_args(argv)
    if not args.live:
        return _dry_run()
    if args.urdf is None or args.tcp_config is None:
        raise RuntimeError("verified_FK_inputs_required")
    return _live(args)


if __name__ == "__main__":
    raise SystemExit(main())
