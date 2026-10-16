#!/usr/bin/env python3
"""One supervised gripper-only close from the measured C pre-approach pose.

The default is hardware-disconnected dry-run. Live mode never sends arm goals,
never changes torque, never retries, and never starts teleoperation.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

if __package__:
    from scripts.live_gripper_open_only import (
        ARM_NAMES, JOINT_UNITS, _assert_records_safe, _assert_safety_sample,
        _close_fallback, _default_factory, _installed_bus_source_sha256s,
        _installed_robot_source_sha256, validate_live_gripper_quantization,
    )
    from scripts.live_c_safe_escape_only import (
        _validated_escape_telemetry, wait_for_escape_settle,
    )
    from scripts.staged_cycle_execution import StagedCycle
else:
    from live_gripper_open_only import (
        ARM_NAMES, JOINT_UNITS, _assert_records_safe, _assert_safety_sample,
        _close_fallback, _default_factory, _installed_bus_source_sha256s,
        _installed_robot_source_sha256, validate_live_gripper_quantization,
    )
    from live_c_safe_escape_only import (
        _validated_escape_telemetry, wait_for_escape_settle,
    )
    from staged_cycle_execution import StagedCycle


SCOPE = "c_preapproach_gripper_close_to_20_only"
RUN_PHRASE = "RUN GRIPPER CLOSE TO 20 ONLY"
SITE_PHRASE = "FINGERS PHYSICALLY MOVED AND CONTACT FREE"
EXPECTED_COMMAND_PERCENT = 20.012239902080783
EXPECTED_COMMAND_RAW = 740


def load_plan(path: Path) -> dict:
    plan = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "scope", "run_phrase", "motion_authorized", "arm_joint_target_allowed",
        "automatic_retry", "confirmed_start_arm_deg", "arm_start_tolerances_deg",
        "confirmed_start_gripper_percent", "confirmed_start_gripper_raw",
        "gripper_start_tolerance_pp", "requested_gripper_percent",
        "command_gripper_percent", "minimum_final_gripper_percent",
        "maximum_final_gripper_percent", "expected_command_raw",
        "expected_command_normalized_feedback_percent",
        "gripper_calibration_evidence", "so_follower_source_sha256",
        "feetech_source_sha256", "motors_bus_source_sha256",
        "arm_present_drift_limit_deg", "temperature_limit_c",
        "verified_abs_load_limit", "present_load_policy",
        "pre_send_stillness_s", "post_send_settle_window_s",
        "telemetry_poll_s", "post_send_timeout_s", "feedback_max_age_s",
        "arm_goal_raw_must_remain_unchanged", "follower_port",
        "follower_serial_short", "human_confirmed_closing_sweep_clear",
    }
    if not required <= set(plan):
        raise ValueError("gripper_close_plan_fields_missing")
    if (plan["scope"] != SCOPE or plan["run_phrase"] != RUN_PHRASE or
            plan["motion_authorized"] is not False or
            plan["arm_joint_target_allowed"] is not False or
            plan["automatic_retry"] is not False or
            plan["human_confirmed_closing_sweep_clear"] is not True or
            plan["follower_port"] != "/dev/ttyACM1" or
            plan["follower_serial_short"] != "5AE6058306" or
            plan["verified_abs_load_limit"] is not None or
            plan["present_load_policy"] != "SIGNED_DIAGNOSTIC_ONLY" or
            plan["arm_goal_raw_must_remain_unchanged"] is not True):
        raise ValueError("gripper_close_scope_or_safety_invalid")
    if (set(plan["confirmed_start_arm_deg"]) != set(ARM_NAMES) or
            plan["arm_start_tolerances_deg"] != {
                "shoulder_pan": 0.5, "shoulder_lift": 1.5,
                "elbow_flex": 1.5, "wrist_flex": 0.5, "wrist_roll": 0.5,
            } or
            plan["confirmed_start_gripper_raw"] != 918 or
            plan["expected_command_raw"] != EXPECTED_COMMAND_RAW or
            plan["requested_gripper_percent"] != 20.0 or
            not math.isclose(plan["command_gripper_percent"],
                             EXPECTED_COMMAND_PERCENT, abs_tol=1e-12) or
            not math.isclose(plan["expected_command_normalized_feedback_percent"],
                             EXPECTED_COMMAND_PERCENT, abs_tol=1e-12) or
            plan["minimum_final_gripper_percent"] != 19.0 or
            plan["maximum_final_gripper_percent"] != 21.0 or
            plan["gripper_start_tolerance_pp"] != 2.0 or
            plan["arm_present_drift_limit_deg"] != 1.0 or
            plan["temperature_limit_c"] != 55.0 or
            plan["pre_send_stillness_s"] != 0.5 or
            plan["post_send_settle_window_s"] != 0.5 or
            not 0.05 <= plan["telemetry_poll_s"] <= 0.2 or
            not 3.0 <= plan["post_send_timeout_s"] <= 10.0 or
            not 0 < plan["feedback_max_age_s"] <= 0.5):
        raise ValueError("gripper_close_policy_invalid")
    numeric = [*plan["confirmed_start_arm_deg"].values(),
               plan["confirmed_start_gripper_percent"]]
    if any(not isinstance(x, (int, float)) or not math.isfinite(x)
           for x in numeric):
        raise ValueError("gripper_close_start_nonfinite")
    return plan


def evaluate_close(before, after, plan: dict) -> dict:
    drift = {name: float(after.positions[name] - before.positions[name])
             for name in ARM_NAMES}
    result = {
        "before_percent": float(before.positions["gripper"]),
        "after_percent": float(after.positions["gripper"]),
        "gripper_moved_closing_direction": (
            after.positions["gripper"] < before.positions["gripper"]),
        "within_existing_one_pp_final_tolerance": (
            plan["minimum_final_gripper_percent"] <=
            after.positions["gripper"] <=
            plan["maximum_final_gripper_percent"]),
        "arm_present_drift_deg": drift,
        "arm_drift_within_one_degree": all(abs(value) <= 1.0
                                           for value in drift.values()),
        "arm_goal_raw_unchanged": all(
            after.goal_raw[name] == before.goal_raw[name] for name in ARM_NAMES),
        "gripper_goal_raw_expected": (
            after.goal_raw["gripper"] == plan["expected_command_raw"]),
        "moving_all_zero": all(after.moving[name] == 0 for name in JOINT_UNITS),
        "temperature_within_55c": all(
            after.temperature_c[name] <= 55 for name in JOINT_UNITS),
        "present_load_diagnostic": dict(after.present_load),
    }
    result["pass"] = all(value for key, value in result.items()
                         if key in {"gripper_moved_closing_direction",
                                    "within_existing_one_pp_final_tolerance",
                                    "arm_drift_within_one_degree",
                                    "arm_goal_raw_unchanged",
                                    "gripper_goal_raw_expected",
                                    "moving_all_zero", "temperature_within_55c"})
    return result


def run(path: Path, *, live: bool, confirm_scope: str | None,
        input_fn=input, transport_factory=None, settle_fn=wait_for_escape_settle,
        controller_factory=StagedCycle,
        source_hash_fn=_installed_robot_source_sha256,
        bus_source_hash_fn=_installed_bus_source_sha256s) -> int:
    plan = load_plan(path)
    print(json.dumps({"scope": SCOPE, "target_percent": 20.0,
                      "expected_goal_raw": EXPECTED_COMMAND_RAW,
                      "arm_target_send": 0, "automatic_retry": 0,
                      "dry_run": not live}, separators=(",", ":")), flush=True)
    if not live:
        print("DRY_RUN: no port opened; no send_action", flush=True)
        return 0
    if confirm_scope != SCOPE:
        raise ValueError("live_scope_mismatch")
    if input_fn(f"Closing sweep clear and site stop ready. Type {RUN_PHRASE}: ") != RUN_PHRASE:
        print("NOT_RUN", flush=True)
        return 2

    transport = (transport_factory or (lambda: _default_factory(plan)))()
    controller = None
    command_attempted = False
    closed = False
    outcome = 1
    try:
        first = _validated_escape_telemetry(
            transport, max_age_s=plan["feedback_max_age_s"])
        _assert_safety_sample(first, plan, require_initial_gripper=True)
        if first.present_raw["gripper"] != plan["confirmed_start_gripper_raw"]:
            raise RuntimeError("gripper_start_raw_changed")
        transport.verify_start_pose(
            dict(first.positions),
            {name: (0.5 if name == "gripper" else 0.25)
             for name in JOINT_UNITS})
        before, pre_records = settle_fn(
            transport, timeout_s=plan["post_send_timeout_s"],
            settle_window_s=plan["pre_send_stillness_s"],
            poll_s=plan["telemetry_poll_s"])
        _assert_safety_sample(before, plan, require_initial_gripper=True)
        _assert_records_safe(pre_records, plan,
                             baseline_present_raw=first.present_raw,
                             baseline_goal_raw=first.goal_raw)
        if before.present_raw["gripper"] != plan["confirmed_start_gripper_raw"]:
            raise RuntimeError("gripper_start_raw_changed")
        quantization = validate_live_gripper_quantization(
            transport, plan, source_hash_fn=source_hash_fn,
            bus_source_hash_fn=bus_source_hash_fn)
        print(json.dumps({"quantization": quantization}, separators=(",", ":")), flush=True)

        controller = controller_factory(
            transport, {name: (1.0 if name == "gripper" else 0.5)
                        for name in JOINT_UNITS},
            timeout_s=plan["post_send_timeout_s"],
            final_timeout_s=plan["post_send_timeout_s"],
            feedback_max_age_s=plan["feedback_max_age_s"],
            stable_s=0.15, poll_s=0.05)
        command_attempted = True
        sent = transport.send_gripper_goal_only(plan["command_gripper_percent"])
        if sent != {"gripper": plan["command_gripper_percent"]}:
            raise RuntimeError("gripper_only_actual_sent_goal_differs")
        after, post_records = settle_fn(
            transport, timeout_s=plan["post_send_timeout_s"],
            settle_window_s=plan["post_send_settle_window_s"],
            poll_s=plan["telemetry_poll_s"])
        print(json.dumps({"post_send_settle_records": post_records},
                         separators=(",", ":")), flush=True)
        _assert_records_safe(
            post_records, plan, baseline_positions=before.positions,
            baseline_goal_raw=before.goal_raw,
            expected_gripper_goal_raw=plan["expected_command_raw"],
            allow_gripper_moving=True)
        verification = evaluate_close(before, after, plan)
        print(json.dumps({"verification": verification,
                          "arm_target_send": 0, "gripper_target_send": 1,
                          "goal_raw_before": dict(before.goal_raw),
                          "goal_raw_after": dict(after.goal_raw),
                          "present_raw_before": dict(before.present_raw),
                          "present_raw_after": dict(after.present_raw)},
                         separators=(",", ":")), flush=True)
        if not verification["pass"]:
            raise RuntimeError("gripper_close_verification_failed")
        print("GRIPPER_REGISTER_RESPONSE_PASS_PHYSICAL_MOTION_UNVERIFIED",
              flush=True)
        if input_fn(
            f"Did the fingers visibly close without contact? Type {SITE_PHRASE}: "
        ) != SITE_PHRASE:
            raise RuntimeError("gripper_physical_finger_motion_not_confirmed")
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
                    "Gripper and arm stopped; links contact-free. Type STOPPED: ") == "STOPPED"
                stable = stopped and controller.verify_arm_stopped(
                    motion_tolerances={name: (1.0 if name == "gripper" else 0.5)
                                       for name in JOINT_UNITS},
                    window_s=0.5, timeout_s=3.0,
                    human_confirmed=human_stopped)
                if stable:
                    transport.close_after_site_confirmation(
                        controller, object_supported=True)
                    closed = True
                    print("physical_stop=FEEDBACK_AND_HUMAN_CONFIRMED", flush=True)
                else:
                    outcome = 1
                    print("physical_stop=NOT_VERIFIED", file=sys.stderr, flush=True)
            else:
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
    if outcome == 0 and closed:
        print("GRIPPER_CLOSE_TO_20_PASS", flush=True)
        return 0
    return 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-scope", choices=[SCOPE])
    args = parser.parse_args(argv)
    try:
        return run(args.plan, live=args.live, confirm_scope=args.confirm_scope)
    except (OSError, ValueError) as error:
        parser.exit(2, f"GRIPPER_CLOSE_NOT_STARTED: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
