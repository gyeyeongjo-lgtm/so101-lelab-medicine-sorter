#!/usr/bin/env python3
"""Open only the follower gripper from the stopped CURRENT pose.

Dry-run is the default and opens no port.  Live mode sends exactly one
singleton gripper action, never an arm target.  After the user confirms the
stopped result, the command-owning session is released before a separate
read-only session rechecks the prepared CURRENT->C route start gate.
"""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import math
from pathlib import Path
import sys
from typing import Callable, Mapping

if __package__:
    from scripts.continuous_following_execution import ARM_NAMES, FollowingTelemetry
    from scripts.live_c_approach import (
        load_plan as load_c_route_plan,
        validate_staged_reference_start,
    )
    from scripts.live_c_safe_escape_only import (
        _validated_escape_telemetry,
        wait_for_escape_settle,
    )
    from scripts.so101_exclusive_bus import ExclusiveFollowerLease, SystemBusProbe
    from scripts.so101_follower_transport import SO101FollowerTransport
    from scripts.staged_cycle_execution import JOINT_UNITS, StagedCycle
else:
    from continuous_following_execution import ARM_NAMES, FollowingTelemetry
    from live_c_approach import load_plan as load_c_route_plan
    from live_c_approach import validate_staged_reference_start
    from live_c_safe_escape_only import (
        _validated_escape_telemetry,
        wait_for_escape_settle,
    )
    from so101_exclusive_bus import ExclusiveFollowerLease, SystemBusProbe
    from so101_follower_transport import SO101FollowerTransport
    from staged_cycle_execution import JOINT_UNITS, StagedCycle


SCOPE = "c_pick_gripper_open_only"
RUN_PHRASE = "RUN GRIPPER OPEN ONLY"
SITE_CONFIRM_PHRASE = "GRIPPER OPEN CONFIRMED"
NEXT_RUN_PHRASE = "RUN CURRENT TO C PRE APPROACH"
EXPECTED_GRIPPER_CALIBRATION = {
    "motor_id": 6,
    "drive_mode": 0,
    "range_min": 413,
    "range_max": 2047,
    "source_sha256": (
        "2f74c1303b2fce03576eff539329e1185a652e2d551caa1ec82b026dafe29c2e"
    ),
}
EXPECTED_COMMAND_GRIPPER_PERCENT = 35.0061199510404
EXPECTED_COMMAND_RAW = 985
EXPECTED_COMMAND_FEEDBACK_PERCENT = 35.00611995104039
EXPECTED_SO_FOLLOWER_SOURCE_SHA256 = (
    "b7d9fcfcf67818c267d71744c993470dfb5077887f9ecedfe8cdf69f450be8fd"
)
EXPECTED_FEETECH_SOURCE_SHA256 = (
    "0460413cd6a641cede015ac19ac53d2cfe9c343af1bd18ed74e1951229f64ff2"
)
EXPECTED_MOTORS_BUS_SOURCE_SHA256 = (
    "ade55d42046f1f0fa737eb61c360d76ed98211f200e10918dc2e6fcfd640a688"
)


def _finite_number(value) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def _route_plan_path(plan_path: Path, configured: str) -> Path:
    candidate = Path(configured)
    if candidate.is_absolute():
        return candidate
    return plan_path.parent / candidate


def load_plan(path: Path) -> dict:
    plan = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "scope", "run_phrase", "site_confirmation_phrase",
        "motion_authorized", "arm_joint_target_allowed", "automatic_retry",
        "confirmed_start_arm_deg", "arm_start_tolerances_deg",
        "confirmed_start_gripper_percent", "gripper_start_tolerance_pp",
        "requested_gripper_percent", "command_gripper_percent",
        "minimum_final_gripper_percent", "expected_command_raw",
        "expected_command_normalized_feedback_percent",
        "gripper_calibration_evidence",
        "so_follower_source_sha256", "feetech_source_sha256",
        "motors_bus_source_sha256",
        "arm_present_drift_limit_deg", "temperature_limit_c",
        "verified_abs_load_limit", "present_load_policy",
        "pre_send_stillness_s", "post_send_settle_window_s",
        "telemetry_poll_s", "post_send_timeout_s", "feedback_max_age_s",
        "arm_goal_raw_must_remain_unchanged", "full_mesh_environment",
        "follower_port", "follower_serial_short", "post_stop_route_plan",
        "post_stop_route_plan_sha256", "next_run_phrase",
    }
    if not required <= set(plan) or plan["scope"] != SCOPE:
        raise ValueError("gripper_open_scope_or_schema_invalid")
    if (plan["run_phrase"] != RUN_PHRASE or
            plan["site_confirmation_phrase"] != SITE_CONFIRM_PHRASE or
            plan["next_run_phrase"] != NEXT_RUN_PHRASE):
        raise ValueError("gripper_open_phrase_contract_invalid")
    if (plan["motion_authorized"] is not False or
            plan["arm_joint_target_allowed"] is not False or
            plan["automatic_retry"] is not False):
        raise ValueError("plan_must_not_self_authorize_or_expand_scope")
    if (plan["verified_abs_load_limit"] is not None or
            plan["present_load_policy"] != "SIGNED_DIAGNOSTIC_ONLY"):
        raise ValueError("unverified_load_must_remain_diagnostic_only")
    if (plan["arm_goal_raw_must_remain_unchanged"] is not True or
            plan["full_mesh_environment"] != "NOT_VERIFIED"):
        raise ValueError("gripper_open_safety_contract_invalid")
    if (set(plan["confirmed_start_arm_deg"]) != set(ARM_NAMES) or
            set(plan["arm_start_tolerances_deg"]) != set(ARM_NAMES)):
        raise ValueError("gripper_open_arm_shape_invalid")

    numeric = (
        list(plan["confirmed_start_arm_deg"].values()) +
        list(plan["arm_start_tolerances_deg"].values()) + [
            plan["confirmed_start_gripper_percent"],
            plan["gripper_start_tolerance_pp"],
            plan["requested_gripper_percent"],
            plan["command_gripper_percent"],
            plan["minimum_final_gripper_percent"],
            plan["expected_command_normalized_feedback_percent"],
            plan["arm_present_drift_limit_deg"], plan["temperature_limit_c"],
            plan["pre_send_stillness_s"], plan["post_send_settle_window_s"],
            plan["telemetry_poll_s"], plan["post_send_timeout_s"],
            plan["feedback_max_age_s"],
        ]
    )
    if any(not _finite_number(value) for value in numeric):
        raise ValueError("gripper_open_nonfinite_value")
    if (dict(plan["arm_start_tolerances_deg"]) != {
            "shoulder_pan": 0.5, "shoulder_lift": 1.5,
            "elbow_flex": 1.5, "wrist_flex": 0.5, "wrist_roll": 0.5,
            } or
            float(plan["gripper_start_tolerance_pp"]) != 2.0 or
            float(plan["requested_gripper_percent"]) != 35.0 or
            float(plan["command_gripper_percent"]) !=
            EXPECTED_COMMAND_GRIPPER_PERCENT or
            float(plan["minimum_final_gripper_percent"]) != 35.0 or
            plan["expected_command_raw"] != EXPECTED_COMMAND_RAW or
            float(plan["expected_command_normalized_feedback_percent"]) !=
            EXPECTED_COMMAND_FEEDBACK_PERCENT or
            plan["gripper_calibration_evidence"] !=
            EXPECTED_GRIPPER_CALIBRATION or
            plan["so_follower_source_sha256"] !=
            EXPECTED_SO_FOLLOWER_SOURCE_SHA256 or
            plan["feetech_source_sha256"] !=
            EXPECTED_FEETECH_SOURCE_SHA256 or
            plan["motors_bus_source_sha256"] !=
            EXPECTED_MOTORS_BUS_SOURCE_SHA256 or
            float(plan["arm_present_drift_limit_deg"]) != 1.0 or
            float(plan["temperature_limit_c"]) != 55.0 or
            float(plan["pre_send_stillness_s"]) != 0.5 or
            float(plan["post_send_settle_window_s"]) != 0.5 or
            not 0.05 <= float(plan["telemetry_poll_s"]) <= 0.2 or
            not 3.0 <= float(plan["post_send_timeout_s"]) <= 10.0 or
            not 0 < float(plan["feedback_max_age_s"]) <= 0.5):
        raise ValueError("gripper_open_policy_invalid")

    route_path = _route_plan_path(path, plan["post_stop_route_plan"])
    try:
        route_digest = hashlib.sha256(route_path.read_bytes()).hexdigest()
    except OSError as error:
        raise ValueError("post_stop_route_plan_unavailable") from error
    if route_digest != plan["post_stop_route_plan_sha256"]:
        raise ValueError("post_stop_route_plan_changed")
    route = load_c_route_plan(route_path)
    if (route.get("run_phrase") != NEXT_RUN_PHRASE or
            route.get("minimum_fresh_gripper_open_percent") != 35.0 or
            route.get("staged_reference_start_arm_deg") !=
            plan["confirmed_start_arm_deg"] or
            route.get("start_pose_tolerance_deg") !=
            plan["arm_start_tolerances_deg"]):
        raise ValueError("post_stop_route_gate_contract_changed")
    plan["_route_plan"] = route
    return plan


def _source_sha256(subject, *, unavailable_reason: str) -> str:
    source = inspect.getsourcefile(subject)
    if source is None:
        raise RuntimeError(unavailable_reason)
    try:
        return hashlib.sha256(Path(source).read_bytes()).hexdigest()
    except OSError as error:
        raise RuntimeError(unavailable_reason) from error


def _installed_robot_source_sha256(robot) -> str:
    return _source_sha256(
        type(robot), unavailable_reason="so_follower_runtime_source_unavailable")


def _installed_bus_source_sha256s(robot) -> dict[str, str]:
    bus_type = type(robot.bus)
    sync_write = getattr(bus_type, "sync_write", None)
    if sync_write is None:
        raise RuntimeError("partial_action_bus_source_unavailable")
    return {
        "feetech": _source_sha256(
            bus_type, unavailable_reason="partial_action_bus_source_unavailable"),
        "motors_bus": _source_sha256(
            inspect.unwrap(sync_write),
            unavailable_reason="partial_action_bus_source_unavailable"),
    }


def validate_live_gripper_quantization(transport, plan: dict, *,
                                       source_hash_fn=_installed_robot_source_sha256,
                                       bus_source_hash_fn=
                                       _installed_bus_source_sha256s
                                       ) -> dict:
    """Reproduce the installed percent->raw->percent conversion before send."""
    bus = getattr(getattr(transport, "robot", None), "bus", None)
    calibration = getattr(bus, "calibration", None)
    motors = getattr(bus, "motors", None)
    unnormalize = getattr(bus, "_unnormalize", None)
    normalize = getattr(bus, "_normalize", None)
    get_ids_values = getattr(bus, "_get_ids_values_dict", None)
    if (calibration is None or motors is None or
            not callable(unnormalize) or not callable(normalize) or
            not callable(get_ids_values)):
        raise RuntimeError("gripper_calibration_runtime_unavailable")
    try:
        item = calibration["gripper"]
        motor = motors["gripper"]
        motor_id = int(motor.id)
        range_min = int(item.range_min if hasattr(item, "range_min")
                        else item["range_min"])
        range_max = int(item.range_max if hasattr(item, "range_max")
                        else item["range_max"])
        drive_mode = int(item.drive_mode if hasattr(item, "drive_mode")
                         else item["drive_mode"])
        partial_ids_values = get_ids_values({
            "gripper": float(plan["command_gripper_percent"]),
        })
        partial_raw_values = unnormalize(partial_ids_values)
        command_raw = int(partial_raw_values[motor_id])
        normalized_feedback = float(normalize({
            motor_id: int(plan["expected_command_raw"]),
        })[motor_id])
    except Exception as error:
        raise RuntimeError("gripper_calibration_runtime_invalid") from error

    evidence = plan["gripper_calibration_evidence"]
    runtime_source_sha256 = source_hash_fn(transport.robot)
    runtime_bus_source_sha256s = bus_source_hash_fn(transport.robot)
    expected_bus_source_sha256s = {
        "feetech": plan["feetech_source_sha256"],
        "motors_bus": plan["motors_bus_source_sha256"],
    }
    if (runtime_source_sha256 != plan["so_follower_source_sha256"] or
            runtime_bus_source_sha256s != expected_bus_source_sha256s or {
            "motor_id": motor_id,
            "drive_mode": drive_mode,
            "range_min": range_min,
            "range_max": range_max,
            "source_sha256": evidence["source_sha256"],
            } != evidence or
            set(partial_ids_values) != {motor_id} or
            set(partial_raw_values) != {motor_id} or
            command_raw != int(plan["expected_command_raw"]) or
            not math.isclose(
                normalized_feedback,
                float(plan["expected_command_normalized_feedback_percent"]),
                rel_tol=0.0, abs_tol=1e-12) or
            normalized_feedback < float(plan["minimum_final_gripper_percent"])):
        raise RuntimeError("gripper_calibration_or_quantization_changed")
    return {
        "recorded_evidence_source_sha256": evidence["source_sha256"],
        "so_follower_runtime_source_sha256": runtime_source_sha256,
        "partial_action_bus_runtime_source_sha256":
            runtime_bus_source_sha256s,
        "runtime_source_hash_verified": True,
        "motor_id": motor_id,
        "drive_mode": drive_mode,
        "range_min": range_min,
        "range_max": range_max,
        "requested_percent": float(plan["requested_gripper_percent"]),
        "command_percent": float(plan["command_gripper_percent"]),
        "expected_goal_raw": command_raw,
        "expected_feedback_percent": normalized_feedback,
        "partial_action_motor_ids": sorted(partial_ids_values),
        "raw_write_used": False,
    }


def _assert_start_gate(positions: Mapping[str, float], plan: dict, *,
                       require_initial_gripper: bool) -> None:
    validate_staged_reference_start(
        dict(positions), plan["confirmed_start_arm_deg"],
        tolerance_deg=plan["arm_start_tolerances_deg"],
    )
    gripper = float(positions["gripper"])
    if require_initial_gripper:
        error = gripper - float(plan["confirmed_start_gripper_percent"])
        if abs(error) > float(plan["gripper_start_tolerance_pp"]):
            raise RuntimeError(f"gripper_initial_reference_mismatch:{error:+.3f}")
    elif gripper < float(plan["minimum_final_gripper_percent"]):
        raise RuntimeError(f"gripper_below_route_minimum:{gripper:.6f}")


def _assert_safety_sample(sample: FollowingTelemetry, plan: dict, *,
                          require_initial_gripper: bool) -> None:
    if any(int(sample.moving[name]) != 0 for name in JOINT_UNITS):
        raise RuntimeError("follower_not_stopped")
    if any(float(sample.temperature_c[name]) > float(plan["temperature_limit_c"])
           for name in JOINT_UNITS):
        raise RuntimeError("temperature_limit_exceeded")
    _assert_start_gate(
        sample.positions, plan,
        require_initial_gripper=require_initial_gripper,
    )


def _assert_records_safe(records: list[dict], plan: dict, *,
                         baseline_present_raw: Mapping[str, int] | None = None,
                         baseline_positions: Mapping[str, float] | None = None,
                         baseline_goal_raw: Mapping[str, int] | None = None,
                         expected_gripper_goal_raw: int | None = None,
                         allow_gripper_moving: bool = False) -> None:
    for record in records:
        if (set(record.get("moving", {})) != set(JOINT_UNITS) or
                set(record.get("temperature_c", {})) != set(JOINT_UNITS) or
                set(record.get("present_raw", {})) != set(JOINT_UNITS) or
                set(record.get("goal_raw", {})) != set(JOINT_UNITS)):
            raise RuntimeError("settle_record_shape_invalid")
        moving_must_be_zero = ARM_NAMES if allow_gripper_moving else JOINT_UNITS
        if any(int(record["moving"][name]) != 0
               for name in moving_must_be_zero):
            raise RuntimeError("movement_observed_during_required_stillness")
        if any(float(record["temperature_c"][name]) >
               float(plan["temperature_limit_c"]) for name in JOINT_UNITS):
            raise RuntimeError("temperature_limit_exceeded")
        if (baseline_present_raw is not None and
                dict(record["present_raw"]) != dict(baseline_present_raw)):
            raise RuntimeError("startup_stillness_changed")
        if (baseline_goal_raw is not None and
                expected_gripper_goal_raw is None and
                dict(record["goal_raw"]) != dict(baseline_goal_raw)):
            raise RuntimeError("startup_goal_changed")
        if expected_gripper_goal_raw is not None:
            if any(int(record["goal_raw"][name]) != int(baseline_goal_raw[name])
                   for name in ARM_NAMES):
                raise RuntimeError("arm_goal_changed_during_gripper_open")
            if int(record["goal_raw"]["gripper"]) != int(
                    expected_gripper_goal_raw):
                raise RuntimeError("gripper_goal_raw_mismatch_during_settle")
        if baseline_positions is not None:
            positions = record.get("present_deg_or_pp", {})
            if set(positions) != set(JOINT_UNITS):
                raise RuntimeError("settle_record_position_shape_invalid")
            if any(abs(float(positions[name]) - float(baseline_positions[name])) >
                   float(plan["arm_present_drift_limit_deg"])
                   for name in ARM_NAMES):
                raise RuntimeError("arm_drift_during_gripper_open")


def evaluate_gripper_open(before: FollowingTelemetry,
                          after: FollowingTelemetry,
                          plan: dict) -> dict:
    arm_present_drift = {
        name: float(after.positions[name]) - float(before.positions[name])
        for name in ARM_NAMES
    }
    arm_goal_raw_unchanged = all(
        int(after.goal_raw[name]) == int(before.goal_raw[name])
        for name in ARM_NAMES
    )
    gripper_delta = float(after.positions["gripper"] -
                          before.positions["gripper"])
    result = {
        "gripper_before_percent": float(before.positions["gripper"]),
        "gripper_after_percent": float(after.positions["gripper"]),
        "gripper_delta_pp": gripper_delta,
        "gripper_reached_minimum": (
            float(after.positions["gripper"]) >=
            float(plan["minimum_final_gripper_percent"])),
        "gripper_moved_positive": gripper_delta > 0.0,
        "arm_present_drift_deg": arm_present_drift,
        "arm_present_drift_within_limit": all(
            abs(value) <= float(plan["arm_present_drift_limit_deg"])
            for value in arm_present_drift.values()),
        "arm_goal_raw_unchanged": arm_goal_raw_unchanged,
        "gripper_goal_raw_matches_expected": (
            int(after.goal_raw["gripper"]) ==
            int(plan["expected_command_raw"])),
        "moving_all_zero": all(int(after.moving[name]) == 0
                               for name in JOINT_UNITS),
        "temperature_within_limit": all(
            float(after.temperature_c[name]) <= float(plan["temperature_limit_c"])
            for name in JOINT_UNITS),
        "present_load_policy": "SIGNED_DIAGNOSTIC_ONLY",
    }
    result["pass"] = all((
        result["gripper_reached_minimum"],
        result["gripper_moved_positive"],
        result["arm_present_drift_within_limit"],
        result["arm_goal_raw_unchanged"],
        result["gripper_goal_raw_matches_expected"],
        result["moving_all_zero"],
        result["temperature_within_limit"],
    ))
    return result


def _default_factory(plan: dict):
    return SO101FollowerTransport.open_live(
        ExclusiveFollowerLease(
            SystemBusProbe(), port=Path(plan["follower_port"]),
            serial_short=plan["follower_serial_short"],
        ),
        approval_confirmed=True,
    )


def _close_fallback(transport) -> None:
    try:
        transport.robot.bus.disconnect(disable_torque=False)
    finally:
        transport.lease.release()


def _run_post_stop_route_gate(plan: dict, factory: Callable[[], object], *,
                              expected_arm_goal_raw: Mapping[str, int]) -> bool:
    transport = factory()
    closed = False
    try:
        sample = _validated_escape_telemetry(
            transport, max_age_s=float(plan["feedback_max_age_s"]))
        _assert_safety_sample(sample, plan, require_initial_gripper=False)
        route = plan["_route_plan"]
        validate_staged_reference_start(
            dict(sample.positions), route["staged_reference_start_arm_deg"],
            tolerance_deg=route["start_pose_tolerance_deg"],
        )
        if float(sample.positions["gripper"]) < float(
                route["minimum_fresh_gripper_open_percent"]):
            raise RuntimeError("route_gate_gripper_not_open")
        if int(sample.goal_raw["gripper"]) != int(plan["expected_command_raw"]):
            raise RuntimeError("route_gate_gripper_goal_raw_mismatch")
        if (set(expected_arm_goal_raw) != set(ARM_NAMES) or
                any(int(sample.goal_raw[name]) !=
                    int(expected_arm_goal_raw[name]) for name in ARM_NAMES)):
            raise RuntimeError("route_gate_arm_goal_raw_changed")
        print(json.dumps({
            "post_stop_fresh_positions": dict(sample.positions),
            "post_stop_goal_raw": dict(sample.goal_raw),
            "post_stop_moving": dict(sample.moving),
            "post_stop_present_load_diagnostic": dict(sample.present_load),
            "post_stop_temperature_c": dict(sample.temperature_c),
            "current_to_c_start_gate": "PASS",
            "arm_target_sent": False,
        }, separators=(",", ":")), flush=True)
        transport.close_without_motion(arm_stable=True, object_supported=True)
        closed = True
        return True
    except (KeyboardInterrupt, Exception) as error:
        print(f"ROUTE_GATE_BLOCKED: {type(error).__name__}: {error}",
              file=sys.stderr, flush=True)
        return False
    finally:
        if not closed:
            try:
                transport.stop_commands()
            finally:
                _close_fallback(transport)


def run(plan_path: Path, *, live: bool, confirm_scope: str | None,
        input_fn=input, transport_factory=None, post_stop_transport_factory=None,
        settle_fn=wait_for_escape_settle, controller_factory=StagedCycle,
        source_hash_fn=_installed_robot_source_sha256,
        bus_source_hash_fn=_installed_bus_source_sha256s) -> int:
    plan = load_plan(plan_path)
    print(json.dumps({
        "scope": SCOPE,
        "requested_gripper_percent": plan["requested_gripper_percent"],
        "command_gripper_percent": plan["command_gripper_percent"],
        "arm_joint_target_allowed": False,
        "automatic_retry": False,
        "present_load_policy": "SIGNED_DIAGNOSTIC_ONLY",
        "full_mesh_environment": "NOT_VERIFIED",
        "dry_run": not live,
    }, separators=(",", ":")), flush=True)
    if not live:
        print("DRY_RUN: no port opened; no send_action; arm/gripper motion unavailable",
              flush=True)
        return 0
    if confirm_scope != SCOPE:
        raise ValueError("live_scope_mismatch")
    if input_fn(
        f"Finger opening sweep is contact-free; open gripper only. Type {RUN_PHRASE}: "
    ) != RUN_PHRASE:
        print("NOT_RUN", flush=True)
        return 2

    factory = transport_factory or (lambda: _default_factory(plan))
    transport = factory()
    controller = None
    command_attempted = False
    closed = False
    outcome = 1
    site_confirmed = False
    expected_arm_goal_raw = None
    try:
        first = _validated_escape_telemetry(
            transport, max_age_s=float(plan["feedback_max_age_s"]))
        _assert_safety_sample(first, plan, require_initial_gripper=True)
        verified = transport.verify_start_pose(
            dict(first.positions),
            {name: (0.5 if name == "gripper" else 0.25)
             for name in JOINT_UNITS},
        )
        _assert_start_gate(
            verified.positions, plan, require_initial_gripper=True)

        stillness_start = _validated_escape_telemetry(
            transport, max_age_s=float(plan["feedback_max_age_s"]))
        _assert_safety_sample(
            stillness_start, plan, require_initial_gripper=True)
        before, stillness_records = settle_fn(
            transport,
            timeout_s=float(plan["post_send_timeout_s"]),
            settle_window_s=float(plan["pre_send_stillness_s"]),
            poll_s=float(plan["telemetry_poll_s"]),
            record_sink=lambda record: print(json.dumps({
                "settle_phase": "PRE_SEND_STILLNESS",
                "settle_record": record,
            }, separators=(",", ":")), flush=True),
        )
        _assert_safety_sample(before, plan, require_initial_gripper=True)
        _assert_records_safe(
            stillness_records, plan,
            baseline_present_raw=stillness_start.present_raw,
            baseline_goal_raw=stillness_start.goal_raw,
        )
        if dict(before.present_raw) != dict(stillness_start.present_raw):
            raise RuntimeError("startup_stillness_changed")

        quantization = validate_live_gripper_quantization(
            transport, plan, source_hash_fn=source_hash_fn,
            bus_source_hash_fn=bus_source_hash_fn)
        print(json.dumps({
            "gripper_command_quantization": quantization,
        }, separators=(",", ":")), flush=True)

        controller = controller_factory(
            transport,
            {name: (1.0 if name == "gripper" else 0.5)
             for name in JOINT_UNITS},
            timeout_s=float(plan["post_send_timeout_s"]),
            final_timeout_s=float(plan["post_send_timeout_s"]),
            feedback_max_age_s=float(plan["feedback_max_age_s"]),
            stable_s=0.15,
            poll_s=0.05,
        )
        command_attempted = True
        sent = transport.send_gripper_goal_only(
            float(plan["command_gripper_percent"]))
        if sent != {"gripper": float(plan["command_gripper_percent"])}:
            raise RuntimeError("gripper_only_actual_sent_goal_differs")

        after, settle_records = settle_fn(
            transport,
            timeout_s=float(plan["post_send_timeout_s"]),
            settle_window_s=float(plan["post_send_settle_window_s"]),
            poll_s=float(plan["telemetry_poll_s"]),
            record_sink=lambda record: print(json.dumps({
                "settle_phase": "POST_SEND_SETTLE",
                "settle_record": record,
            }, separators=(",", ":")), flush=True),
        )
        # Emit the raw settling evidence before any assertion can abort.  This
        # preserves the first transient arm drift/Moving/temperature failure.
        print(json.dumps({
            "post_send_settle_records": settle_records,
        }, separators=(",", ":")), flush=True)
        # The gripper is expected to report Moving=1 while opening.  Arm-axis
        # movement is never allowed; the final sample below must have all six
        # Moving values at zero and must satisfy the <=1 degree arm drift gate.
        _assert_records_safe(
            settle_records, plan,
            baseline_positions=before.positions,
            baseline_goal_raw=before.goal_raw,
            expected_gripper_goal_raw=int(plan["expected_command_raw"]),
            allow_gripper_moving=True)
        verification = evaluate_gripper_open(before, after, plan)
        print(json.dumps({
            "requested_gripper_percent": plan["requested_gripper_percent"],
            "command_gripper_percent": plan["command_gripper_percent"],
            "goal_raw_before": dict(before.goal_raw),
            "goal_raw_after": dict(after.goal_raw),
            "present_raw_before": dict(before.present_raw),
            "present_raw_after": dict(after.present_raw),
            "present_load_before_diagnostic": dict(before.present_load),
            "present_load_after_diagnostic": dict(after.present_load),
            "temperature_c": dict(after.temperature_c),
            "moving": dict(after.moving),
            "verification": verification,
            "arm_target_sent": False,
            "gripper_send_count": 1,
        }, separators=(",", ":")), flush=True)
        if not verification["pass"]:
            raise RuntimeError("gripper_open_verification_failed")
        expected_arm_goal_raw = {
            name: int(before.goal_raw[name]) for name in ARM_NAMES
        }
        if input_fn(
            f"Opening is contact-free and visually confirmed. Type {SITE_CONFIRM_PHRASE}: "
        ) != SITE_CONFIRM_PHRASE:
            raise RuntimeError("gripper_open_site_result_not_confirmed")
        site_confirmed = True
        print("GRIPPER_OPEN_TARGET_VERIFIED", flush=True)
        outcome = 0
    except (KeyboardInterrupt, Exception) as error:
        print(f"ABORT: {type(error).__name__}: {error}", file=sys.stderr, flush=True)
    finally:
        transport.stop_commands()
        try:
            if command_attempted and controller is not None:
                controller.request_stop()
                stopped = controller.verify_stop_completed(timeout_s=3.0)
                human_stopped = input_fn(
                    "Gripper and arm stopped; links remain contact-free. Type STOPPED: "
                ) == "STOPPED"
                stable = stopped and controller.verify_arm_stopped(
                    motion_tolerances={
                        name: (1.0 if name == "gripper" else 0.5)
                        for name in JOINT_UNITS
                    },
                    window_s=0.5, timeout_s=3.0,
                    human_confirmed=human_stopped,
                )
                if stable:
                    transport.close_after_site_confirmation(
                        controller, object_supported=True)
                    closed = True
                    print("physical_stop=FEEDBACK_AND_HUMAN_CONFIRMED", flush=True)
                else:
                    outcome = 1
                    print("physical_stop=NOT_VERIFIED", file=sys.stderr, flush=True)
            elif not command_attempted:
                transport.close_without_motion(
                    arm_stable=True, object_supported=True)
                closed = True
        except (KeyboardInterrupt, Exception) as error:
            outcome = 1
            print(f"shutdown_check_failed:{type(error).__name__}:{error}",
                  file=sys.stderr, flush=True)
        finally:
            if not closed:
                _close_fallback(transport)

    if (outcome != 0 or not site_confirmed or not closed or
            expected_arm_goal_raw is None):
        return 1

    print("GRIPPER_OPEN_PASS", flush=True)
    post_factory = post_stop_transport_factory or factory
    if not _run_post_stop_route_gate(
            plan, post_factory,
            expected_arm_goal_raw=expected_arm_goal_raw):
        return 1
    print(f"NEXT_LIVE_COMMAND={NEXT_RUN_PHRASE}", flush=True)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-scope", choices=[SCOPE])
    args = parser.parse_args(argv)
    try:
        return run(args.plan, live=args.live, confirm_scope=args.confirm_scope)
    except (OSError, ValueError) as error:
        parser.exit(2, f"GRIPPER_OPEN_NOT_STARTED: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
