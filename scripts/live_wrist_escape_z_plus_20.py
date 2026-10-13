#!/usr/bin/env python3
"""Run only the staged Wrist-Flex escape to a measured +20 mm GRASP-TCP Z.

Dry-run is the default.  Live mode requires an explicit scope phrase, starts
from fresh telemetry, commands Wrist Flex only, replans each <=2 degree step
from the latest actual feedback, and latches off after the first failed step.
It contains no +30/+40 continuation, Lift/Elbow probe, HOME, or SAFE_HIGH path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Mapping

import numpy as np

if __package__:
    from scripts.live_c_safe_escape_only import (
        SafeEscapeCycle, _validated_escape_telemetry, wait_for_escape_settle,
    )
    from scripts.plan_pick_grasp_tcp_ik import JOINTS, tcp_position_mm
    from scripts.plan_responsive_joint_escape import (
        WRIST_FLEX_INDEX, find_wrist_endpoint, fk_z_sensitivity_mm_per_deg,
        minimum_centerline_distance_mm,
    )
    from scripts.safe_escape_verification import evaluate_escape_motion
    from scripts.so101_exclusive_bus import ExclusiveFollowerLease, SystemBusProbe
    from scripts.so101_follower_transport import (
        SO101FollowerTransport, verify_installed_urdf,
    )
    from scripts.staged_cycle_execution import JOINT_UNITS
    from scripts.urdf_forward_kinematics import UrdfKinematics
else:
    from live_c_safe_escape_only import (
        SafeEscapeCycle, _validated_escape_telemetry, wait_for_escape_settle,
    )
    from plan_pick_grasp_tcp_ik import JOINTS, tcp_position_mm
    from plan_responsive_joint_escape import (
        WRIST_FLEX_INDEX, find_wrist_endpoint, fk_z_sensitivity_mm_per_deg,
        minimum_centerline_distance_mm,
    )
    from safe_escape_verification import evaluate_escape_motion
    from so101_exclusive_bus import ExclusiveFollowerLease, SystemBusProbe
    from so101_follower_transport import SO101FollowerTransport, verify_installed_urdf
    from staged_cycle_execution import JOINT_UNITS
    from urdf_forward_kinematics import UrdfKinematics


SCOPE = "c_pick_wrist_escape_z_plus_20_only"
RUN_PHRASE = "RUN WRIST ESCAPE Z PLUS 20 ONLY"
CONFIRM_PHRASE = "WRIST ESCAPE CLEARANCE CONFIRMED"


def load_plan(path: Path) -> dict:
    plan = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "scope", "current_arm_joints_deg", "pick_grasp_tcp_offset_gripper_mm",
        "servo_bounds_deg", "target_z_gain_mm", "target_z_completion_tolerance_mm",
        "maximum_joint_step_deg", "maximum_live_steps", "confirmed_start_tolerance_deg",
        "terminal_tolerances_deg_or_pp", "minimum_motion_fraction",
        "noncommanded_joint_drift_limit_deg_or_pp", "temperature_limit_c",
        "verified_abs_load_limit", "settle_window_s", "telemetry_poll_s",
        "step_timeout_s", "table_contact_reference_z_mm", "urdf_sha256",
        "minimum_self_collision_centerline_mm",
        "full_mesh_collision_status", "follower_port", "follower_serial_short",
        "motion_authorized",
    }
    if not required <= set(plan) or plan["scope"] != SCOPE:
        raise ValueError("wrist_escape_scope_or_schema_invalid")
    if plan["motion_authorized"] is not False:
        raise ValueError("plan_must_not_self_authorize")
    if plan["full_mesh_collision_status"] != "NOT_VERIFIED":
        raise ValueError("full_mesh_status_must_remain_not_verified")
    if plan["verified_abs_load_limit"] is not None:
        raise ValueError("unverified_load_limit_must_remain_not_defined")
    if (float(plan["target_z_gain_mm"]) != 20.0 or
            not 0 < float(plan["maximum_joint_step_deg"]) <= 2.0 or
            int(plan["maximum_live_steps"]) < 1 or
            not 0 < float(plan["confirmed_start_tolerance_deg"]) <= 0.5 or
            float(plan["minimum_motion_fraction"]) != 0.5 or
            float(plan["noncommanded_joint_drift_limit_deg_or_pp"]) != 1.0 or
            float(plan["temperature_limit_c"]) != 55.0):
        raise ValueError("wrist_escape_policy_invalid")
    if (len(plan["current_arm_joints_deg"]) != len(JOINTS) or
            len(plan["pick_grasp_tcp_offset_gripper_mm"]) != 3 or
            np.asarray(plan["servo_bounds_deg"], dtype=float).shape != (5, 2) or
            set(plan["terminal_tolerances_deg_or_pp"]) != set(JOINT_UNITS)):
        raise ValueError("wrist_escape_shape_invalid")
    return plan


def assert_confirmed_start(start: Mapping[str, float], plan: dict) -> None:
    if set(start) != set(JOINT_UNITS):
        raise ValueError("fresh_start_feedback_invalid")
    reference = dict(zip(JOINTS, map(float, plan["current_arm_joints_deg"])))
    tolerance = float(plan["confirmed_start_tolerance_deg"])
    error = {joint: float(start[joint]) - reference[joint] for joint in JOINTS}
    if any(abs(value) > tolerance for value in error.values()):
        detail = ",".join(f"{name}={value:+.3f}" for name, value in error.items())
        raise RuntimeError(f"site_confirmed_start_changed:{detail}")


def build_next_wrist_goal(
    current: Mapping[str, float],
    *,
    target_z_mm: float,
    kinematics: UrdfKinematics,
    grasp_offset_mm: np.ndarray,
    bounds_deg: np.ndarray,
    maximum_step_deg: float,
    completion_tolerance_mm: float,
    table_reference_z_mm: float,
    minimum_centerline_mm: float,
) -> tuple[dict[str, float] | None, dict]:
    if set(current) != set(JOINT_UNITS):
        raise ValueError("current_feedback_shape_invalid")
    q = np.asarray([float(current[name]) for name in JOINTS], dtype=float)
    xyz = tcp_position_mm(kinematics, q, grasp_offset_mm)
    remaining = float(target_z_mm - xyz[2])
    if remaining <= completion_tolerance_mm:
        return None, {
            "current_grasp_tcp_xyz_mm": xyz.tolist(),
            "remaining_z_mm": remaining,
        }
    sensitivity = fk_z_sensitivity_mm_per_deg(
        kinematics, q, grasp_offset_mm, 0.01,
    )
    wrist_sensitivity = sensitivity["wrist_flex"]
    if abs(wrist_sensitivity) < 1e-9:
        raise RuntimeError("wrist_flex_z_sensitivity_zero")
    direction = math.copysign(1.0, wrist_sensitivity)
    endpoint = find_wrist_endpoint(
        kinematics, q, grasp_offset_mm, bounds_deg, remaining, direction,
    )
    if endpoint is None:
        raise RuntimeError("fresh_wrist_endpoint_not_found")
    wrist_delta = float(np.clip(
        endpoint[WRIST_FLEX_INDEX] - q[WRIST_FLEX_INDEX],
        -maximum_step_deg, maximum_step_deg,
    ))
    if wrist_delta * direction <= 0.0:
        raise RuntimeError("wrist_escape_direction_invalid")
    goal = {name: float(current[name]) for name in JOINT_UNITS}
    goal["wrist_flex"] += wrist_delta
    target_q = np.asarray([goal[name] for name in JOINTS], dtype=float)
    target_xyz = tcp_position_mm(kinematics, target_q, grasp_offset_mm)
    if target_xyz[2] <= xyz[2]:
        raise RuntimeError("wrist_step_does_not_increase_tcp_z")
    if any(not bounds_deg[index, 0] <= target_q[index] <= bounds_deg[index, 1]
           for index in range(len(JOINTS))):
        raise RuntimeError("wrist_step_outside_servo_bounds")
    target_centerline = minimum_centerline_distance_mm(kinematics, target_q)
    if target_centerline <= minimum_centerline_mm:
        raise RuntimeError("wrist_step_self_collision_proxy_failed")
    return goal, {
        "current_grasp_tcp_xyz_mm": xyz.tolist(),
        "predicted_target_grasp_tcp_xyz_mm": target_xyz.tolist(),
        "predicted_step_z_gain_mm": float(target_xyz[2] - xyz[2]),
        "remaining_z_mm": remaining,
        "wrist_flex_z_sensitivity_mm_per_deg": wrist_sensitivity,
        "current_table_proxy_margin_mm": float(xyz[2] - table_reference_z_mm),
        "predicted_target_table_proxy_margin_mm": float(
            target_xyz[2] - table_reference_z_mm),
        "predicted_target_self_collision_centerline_margin_mm": target_centerline,
        "full_mesh_collision_status": "NOT_VERIFIED",
    }


def run(plan_path: Path, *, live: bool, confirm_scope: str | None,
        input_fn=input, transport_factory=None, urdf_path_factory=None,
        controller_factory=SafeEscapeCycle) -> int:
    plan = load_plan(plan_path)
    print(json.dumps({
        "scope": SCOPE,
        "target_z_gain_mm": 20.0,
        "maximum_joint_step_deg": plan["maximum_joint_step_deg"],
        "load_policy": "DIAGNOSTIC_ONLY_NOT_DEFINED",
        "automatic_plus_30_or_40": False,
        "full_mesh_collision_status": "NOT_VERIFIED",
        "dry_run": not live,
    }, separators=(",", ":")), flush=True)
    if not live:
        print("DRY_RUN: no port opened; no send_action; wrist escape not run", flush=True)
        return 0
    if confirm_scope != SCOPE:
        raise ValueError("live_scope_mismatch")
    if input_fn(
        f"All links stopped/clear; run Wrist escape to +20 mm only. Type {RUN_PHRASE}: "
    ) != RUN_PHRASE:
        print("NOT_RUN", flush=True)
        return 2

    factory = transport_factory or (lambda: SO101FollowerTransport.open_live(
        ExclusiveFollowerLease(
            SystemBusProbe(), port=Path(plan["follower_port"]),
            serial_short=plan["follower_serial_short"]),
        approval_confirmed=True))
    transport = factory()
    controller = None
    closed = False
    command_attempted = False
    outcome = 1
    try:
        installed_urdf = (urdf_path_factory or verify_installed_urdf)()
        installed_urdf = Path(installed_urdf)
        if hashlib.sha256(installed_urdf.read_bytes()).hexdigest() != plan["urdf_sha256"]:
            raise RuntimeError("installed_urdf_changed")
        kinematics = UrdfKinematics.from_file(installed_urdf)
        grasp_offset = np.asarray(
            plan["pick_grasp_tcp_offset_gripper_mm"], dtype=float)
        bounds = np.asarray(plan["servo_bounds_deg"], dtype=float)

        first = _validated_escape_telemetry(transport)
        start = dict(first.positions)
        assert_confirmed_start(start, plan)
        verified = transport.verify_start_pose(
            start,
            {name: (1.0 if name == "gripper" else 0.25)
             for name in JOINT_UNITS},
        )
        assert_confirmed_start(dict(verified.positions), plan)
        # Refresh Goal/Present/Load/Temperature after arming the transport's
        # existing start-pose latch.  This remains read-only and becomes the
        # exact before-sample for step 1.
        first = _validated_escape_telemetry(transport)
        start = dict(first.positions)
        assert_confirmed_start(start, plan)
        start_q = np.asarray([start[name] for name in JOINTS], dtype=float)
        start_tcp = tcp_position_mm(kinematics, start_q, grasp_offset)
        target_z = float(start_tcp[2] + float(plan["target_z_gain_mm"]))
        tolerances = {
            name: float(plan["terminal_tolerances_deg_or_pp"][name])
            for name in JOINT_UNITS
        }
        controller = controller_factory(
            transport, tolerances, timeout_s=float(plan["step_timeout_s"]),
            final_timeout_s=float(plan["step_timeout_s"]),
            feedback_max_age_s=0.5, stable_s=0.15, poll_s=0.05)
        pre = first
        records = []
        for step_number in range(1, int(plan["maximum_live_steps"]) + 1):
            current = dict(pre.positions)
            goal, prediction = build_next_wrist_goal(
                current,
                target_z_mm=target_z,
                kinematics=kinematics,
                grasp_offset_mm=grasp_offset,
                bounds_deg=bounds,
                maximum_step_deg=float(plan["maximum_joint_step_deg"]),
                completion_tolerance_mm=float(
                    plan["target_z_completion_tolerance_mm"]),
                table_reference_z_mm=float(plan["table_contact_reference_z_mm"]),
                minimum_centerline_mm=float(
                    plan["minimum_self_collision_centerline_mm"]),
            )
            if goal is None:
                break
            current_tcp = np.asarray(prediction["current_grasp_tcp_xyz_mm"])
            target_tcp = np.asarray(prediction["predicted_target_grasp_tcp_xyz_mm"])
            if target_tcp[2] < current_tcp[2] or target_tcp[2] < start_tcp[2]:
                raise RuntimeError("table_proxy_not_monotonic")
            command_attempted = True
            sent = transport.send_goal(goal)
            if set(sent) != set(goal) or any(
                    abs(float(sent[name]) - goal[name]) > 1e-9 for name in JOINT_UNITS):
                raise RuntimeError("actual_sent_goal_differs")
            final, samples = wait_for_escape_settle(
                transport,
                timeout_s=float(plan["step_timeout_s"]),
                settle_window_s=float(plan["settle_window_s"]),
                poll_s=float(plan["telemetry_poll_s"]),
            )
            after = dict(final.positions)
            after_q = np.asarray([after[name] for name in JOINTS], dtype=float)
            after_tcp = tcp_position_mm(kinematics, after_q, grasp_offset)
            after_centerline = minimum_centerline_distance_mm(
                kinematics, after_q)
            actual_centerline_ok = after_centerline > float(
                plan["minimum_self_collision_centerline_mm"])
            verification = evaluate_escape_motion(
                present_before=current,
                requested_target=goal,
                present_after=after,
                grasp_tcp_before_mm=current_tcp,
                grasp_tcp_after_mm=after_tcp,
                present_load_before=pre.present_load,
                present_load=final.present_load,
                temperature_c=final.temperature_c,
                terminal_tolerances=tolerances,
                verified_abs_load_limit=None,
                feedback_fresh=True,
                communication_ok=True,
                settled=True,
            )
            record = {
                "step": step_number,
                "requested_target": goal,
                "goal_raw": dict(final.goal_raw),
                "present_raw": dict(final.present_raw),
                "present_deg_or_pp": after,
                "joint_motion": verification["joint_motion"],
                "moving": dict(final.moving),
                "present_load": dict(final.present_load),
                "present_load_delta": verification["present_load_delta"],
                "temperature_c": dict(final.temperature_c),
                "grasp_tcp_xyz_mm": [float(value) for value in after_tcp],
                "cumulative_delta_z_mm": float(after_tcp[2] - start_tcp[2]),
                "actual_self_collision_centerline_margin_mm": after_centerline,
                "actual_self_collision_centerline_proxy": (
                    "PASS" if actual_centerline_ok else "FAIL"),
                "full_mesh_collision_status": "NOT_VERIFIED",
                "sdk_communication_fault": False,
                "verification": verification,
                "settle_samples": samples,
            }
            records.append(record)
            print(json.dumps(record, separators=(",", ":")), flush=True)
            if not verification["pass"] or not actual_centerline_ok:
                raise RuntimeError(f"wrist_escape_step_{step_number}_failed")
            pre = final
        else:
            raise RuntimeError("wrist_escape_maximum_steps_exceeded")

        final_q = np.asarray([pre.positions[name] for name in JOINTS], dtype=float)
        final_tcp = tcp_position_mm(kinematics, final_q, grasp_offset)
        achieved_z = float(final_tcp[2] - start_tcp[2])
        if achieved_z + float(plan["target_z_completion_tolerance_mm"]) < 20.0:
            raise RuntimeError("wrist_escape_target_z_not_reached")
        if input_fn(
            f"No contact and clearance improved? Type {CONFIRM_PHRASE}: "
        ) != CONFIRM_PHRASE:
            raise RuntimeError("wrist_escape_site_result_not_confirmed")
        print(json.dumps({
            "result": "WRIST_ESCAPE_Z_PLUS_20_PASS",
            "achieved_z_gain_mm": achieved_z,
            "final_grasp_tcp_xyz_mm": final_tcp.tolist(),
            "step_count": len(records),
            "automatic_plus_30_or_40": False,
        }, separators=(",", ":")), flush=True)
        outcome = 0
    except (KeyboardInterrupt, Exception) as error:
        print(f"ABORT: {type(error).__name__}: {error}", file=sys.stderr, flush=True)
    finally:
        transport.stop_commands()
        try:
            if controller is not None:
                controller.request_stop()
                controller.verify_stop_completed(timeout_s=3.0)
                human_stopped = input_fn("Arm stopped and scene safe? Type STOPPED: ") == "STOPPED"
                stable = controller.verify_arm_stopped(
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
                transport.close_without_motion(arm_stable=True, object_supported=True)
                closed = True
        except (KeyboardInterrupt, Exception) as error:
            outcome = 1
            print(f"shutdown_check_failed:{type(error).__name__}:{error}",
                  file=sys.stderr, flush=True)
        finally:
            if not closed:
                try:
                    transport.robot.bus.disconnect(disable_torque=False)
                finally:
                    transport.lease.release()
    return outcome


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-scope", choices=[SCOPE])
    args = parser.parse_args(argv)
    try:
        return run(args.plan, live=args.live, confirm_scope=args.confirm_scope)
    except (OSError, ValueError) as error:
        parser.exit(2, f"WRIST_ESCAPE_NOT_STARTED: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
