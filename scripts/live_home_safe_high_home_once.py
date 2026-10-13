#!/usr/bin/env python3
"""Dry-run or execute one HOME→SAFE_HIGH→HOME bounded round trip.

Dry-run is the default.  Live execution requires the exact scope and human
phrase, reuses the recorded poses and existing follower transport, verifies
every waypoint from fresh settled telemetry, and permanently stops command
production on the first failed gate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np
import yaml

if __package__:
    from scripts.live_c_safe_escape_only import (
        SafeEscapeCycle, _validated_escape_telemetry, wait_for_escape_settle,
    )
    from scripts.plan_pick_grasp_tcp_ik import JOINTS, tcp_position_mm
    from scripts.plan_responsive_joint_escape import minimum_centerline_distance_mm
    from scripts.safe_home_return import (
        build_go_home_safe_plan, evaluate_return_waypoint, flatten_return_plan,
    )
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
    from plan_responsive_joint_escape import minimum_centerline_distance_mm
    from safe_home_return import (
        build_go_home_safe_plan, evaluate_return_waypoint, flatten_return_plan,
    )
    from so101_exclusive_bus import ExclusiveFollowerLease, SystemBusProbe
    from so101_follower_transport import SO101FollowerTransport, verify_installed_urdf
    from staged_cycle_execution import JOINT_UNITS
    from urdf_forward_kinematics import UrdfKinematics


SCOPE = "home_safe_high_home_once"
RUN_PHRASE = "RUN HOME SAFE_HIGH HOME ONCE"
EXPECTED_SEGMENTS = (
    "SAFE_HIGH_EXCEPT_PAN", "PAN_ALIGNMENT",
    "HOME_EXCEPT_PAN", "HOME_PAN_ALIGNMENT",
)
TERMINAL_TOLERANCES = {
    "shoulder_pan": 0.5,
    "shoulder_lift": 1.5,
    "elbow_flex": 1.5,
    "wrist_flex": 0.5,
    "wrist_roll": 0.5,
    "gripper": 1.0,
}


def _recorded_pose(document: dict, name: str) -> dict[str, float]:
    if document.get("pose_status", {}).get(name) != "RECORDED":
        raise ValueError(f"{name.lower()}_not_recorded")
    record = document.get("poses", {}).get(name, {})
    joints = record.get("joints", {})
    if set(joints) != set(JOINT_UNITS):
        raise ValueError(f"{name.lower()}_joint_shape_invalid")
    result = {
        joint: float(joints[joint]["degree_mean"]) for joint in JOINT_UNITS
    }
    if any(not math.isfinite(value) for value in result.values()):
        raise ValueError(f"{name.lower()}_joint_nonfinite")
    return result


def _calibration_bounds(document: dict) -> dict[str, tuple[float, float]]:
    names = ("Rotation", "Pitch", "Elbow", "Wrist_Pitch", "Wrist_Roll")
    raw = document.get("arm_ranges_raw", {})
    if tuple(raw) != names or document.get("resolution_steps") != 4096:
        raise ValueError("calibration_bounds_schema_invalid")
    result = {}
    for joint, source in zip(JOINTS, names):
        low, high = raw[source]
        midpoint = (low + high) / 2.0
        result[joint] = (
            (low - midpoint) * 360.0 / 4095.0,
            (high - midpoint) * 360.0 / 4095.0,
        )
    return result


def load_context(*, poses_path: Path, tcp_path: Path, escape_path: Path,
                 calibration_path: Path, urdf_path: Path) -> dict:
    poses = yaml.safe_load(poses_path.read_text(encoding="utf-8"))
    tcp = json.loads(tcp_path.read_text(encoding="utf-8"))
    escape = json.loads(escape_path.read_text(encoding="utf-8"))
    calibration = json.loads(calibration_path.read_text(encoding="utf-8"))
    urdf_sha = hashlib.sha256(urdf_path.read_bytes()).hexdigest()
    if tcp.get("urdf_sha256") != urdf_sha or escape.get("urdf_sha256") != urdf_sha:
        raise ValueError("urdf_sha_mismatch")
    if (tcp.get("motion_authorized") is not False or
            escape.get("motion_authorized") is not False or
            escape.get("full_mesh_collision_status") != "NOT_VERIFIED"):
        raise ValueError("offline_source_policy_invalid")
    home = _recorded_pose(poses, "HOME")
    safe_high = _recorded_pose(poses, "SAFE_HIGH")
    offset = np.asarray(tcp["pick_grasp_tcp_offset_gripper_mm"], dtype=float)
    if offset.shape != (3,) or not np.isfinite(offset).all():
        raise ValueError("grasp_tcp_offset_invalid")
    arm_bounds = _calibration_bounds(calibration)
    return {
        "home": home,
        "safe_high": safe_high,
        "grasp_offset_mm": offset,
        "table_reference_z_mm": float(tcp["table_contact_reference_z_mm"]),
        "arm_calibration_bounds": arm_bounds,
        "urdf_sha256": urdf_sha,
        "urdf_path": urdf_path,
        "follower_port": escape["follower_port"],
        "follower_serial_short": escape["follower_serial_short"],
        "full_mesh_collision_status": "NOT_VERIFIED",
    }


def build_offline_report(context: dict) -> tuple[object, dict]:
    home = context["home"]
    safe_high = context["safe_high"]
    kinematics = UrdfKinematics.from_file(context["urdf_path"])
    home_q = np.asarray([home[name] for name in JOINTS], dtype=float)
    home_tcp = tcp_position_mm(kinematics, home_q, context["grasp_offset_mm"])
    plan = build_go_home_safe_plan(
        current=home,
        safe_high=safe_high,
        home=home,
        current_grasp_tcp_z_mm=float(home_tcp[2]),
        table_reference_z_mm=context["table_reference_z_mm"],
        max_joint_step_deg=2.0,
    )
    if tuple(segment.name for segment in plan.segments) != EXPECTED_SEGMENTS:
        raise RuntimeError("round_trip_segment_order_invalid")
    flattened = flatten_return_plan(plan)
    outbound_count = sum(
        len(segment.goals) for segment in plan.segments[:2])
    return_count = sum(
        len(segment.goals) for segment in plan.segments[2:])

    q_path = [home_q]
    previous = np.asarray([home[name] for name in JOINTS], dtype=float)
    maximum_step = 0.0
    for _segment, goal in flattened:
        current = np.asarray([goal[name] for name in JOINTS], dtype=float)
        maximum_step = max(maximum_step, float(np.max(np.abs(current - previous))))
        q_path.append(current)
        previous = current
    tcp = np.asarray([
        tcp_position_mm(kinematics, q, context["grasp_offset_mm"])
        for q in q_path
    ])
    centerline = np.asarray([
        minimum_centerline_distance_mm(kinematics, q) for q in q_path
    ])
    bounds = np.asarray([
        context["arm_calibration_bounds"][name] for name in JOINTS
    ], dtype=float)
    q_array = np.asarray(q_path)
    margins = np.minimum(q_array - bounds[:, 0], bounds[:, 1] - q_array)
    table_margins = tcp[:, 2] - context["table_reference_z_mm"]
    outbound_z = tcp[:outbound_count + 1, 2]
    return_z = tcp[outbound_count:, 2]
    exact_home = all(
        abs(flattened[-1][1][name] - home[name]) <= 1e-12
        for name in JOINT_UNITS
    )
    report = {
        "scope": SCOPE,
        "home_to_safe_high_waypoint_count": outbound_count,
        "safe_high_to_home_waypoint_count": return_count,
        "total_waypoint_count": len(flattened),
        "maximum_per_joint_step_deg": maximum_step,
        "predicted_grasp_tcp_z_range_mm": [
            float(np.min(tcp[:, 2])), float(np.max(tcp[:, 2]))
        ],
        "home_to_safe_high_z_monotonic_non_decreasing": bool(
            np.all(np.diff(outbound_z) >= -1e-9)),
        "safe_high_to_home_z_monotonic_non_increasing": bool(
            np.all(np.diff(return_z) <= 1e-9)),
        "minimum_table_proxy_margin_mm": float(np.min(table_margins)),
        "minimum_self_collision_centerline_proxy_mm": float(np.min(centerline)),
        "minimum_servo_calibration_margin_deg": float(np.min(margins)),
        "final_home_exact_in_plan": exact_home,
        "final_home_verification_rule": {
            "terminal_tolerances_deg_or_pp": dict(TERMINAL_TOLERANCES),
            "fresh_feedback": True,
            "moving_all_zero": True,
            "temperature_max_c": 55.0,
            "elbow_goal_present_logged": True,
            "present_load_policy": "DIAGNOSTIC_ONLY_NOT_NUMERIC_GATE",
        },
        "segment_order": [segment.name for segment in plan.segments],
        "full_mesh_collision_status": "NOT_VERIFIED",
        "offline_constraints_pass": all((
            outbound_count > 0,
            return_count > 0,
            maximum_step <= 2.0 + 1e-9,
            bool(np.all(margins >= -1e-9)),
            exact_home,
            bool(np.all(np.diff(outbound_z) >= -1e-9)),
            bool(np.all(np.diff(return_z) <= 1e-9)),
        )),
        "hardware_command": 0,
    }
    return plan, report


def _terminal_check(actual: dict[str, float], target: dict[str, float]) -> dict:
    errors = {name: actual[name] - target[name] for name in JOINT_UNITS}
    within = {
        name: abs(errors[name]) <= TERMINAL_TOLERANCES[name]
        for name in JOINT_UNITS
    }
    return {"errors": errors, "within": within, "pass": all(within.values())}


def run(*, context: dict, live: bool, confirm_scope: str | None,
        input_fn=input, transport_factory=None,
        urdf_path_factory=None, controller_factory=SafeEscapeCycle) -> int:
    plan, report = build_offline_report(context)
    print(json.dumps(report, separators=(",", ":")), flush=True)
    if not report["offline_constraints_pass"]:
        raise RuntimeError("round_trip_offline_constraints_failed")
    if not live:
        print("DRY_RUN: no port opened; no send_action; round trip not run", flush=True)
        return 0
    if confirm_scope != SCOPE:
        raise ValueError("live_scope_mismatch")
    if input_fn(f"Run one HOME-SAFE_HIGH-HOME round trip. Type {RUN_PHRASE}: ") != RUN_PHRASE:
        print("NOT_RUN", flush=True)
        return 2

    factory = transport_factory or (lambda: SO101FollowerTransport.open_live(
        ExclusiveFollowerLease(
            SystemBusProbe(), port=Path(context["follower_port"]),
            serial_short=context["follower_serial_short"]),
        approval_confirmed=True))
    transport = factory()
    controller = None
    closed = False
    command_attempted = False
    outcome = 1
    try:
        installed = Path((urdf_path_factory or verify_installed_urdf)())
        if hashlib.sha256(installed.read_bytes()).hexdigest() != context["urdf_sha256"]:
            raise RuntimeError("installed_urdf_changed")
        kinematics = UrdfKinematics.from_file(installed)
        first = _validated_escape_telemetry(transport)
        fresh = dict(first.positions)
        start_check = _terminal_check(fresh, context["home"])
        if not start_check["pass"]:
            raise RuntimeError(f"fresh_home_start_mismatch:{start_check['errors']}")
        transport.verify_start_pose(fresh, {
            name: (1.0 if name == "gripper" else 0.25)
            for name in JOINT_UNITS
        })
        pre = _validated_escape_telemetry(transport)
        calibrated_bounds = dict(transport.calibrated_bounds)
        controller = controller_factory(
            transport, TERMINAL_TOLERANCES,
            timeout_s=5.0, final_timeout_s=5.0,
            feedback_max_age_s=0.5, stable_s=0.15, poll_s=0.05,
        )
        flat = flatten_return_plan(plan)
        minimum_table = float(report["minimum_table_proxy_margin_mm"])
        minimum_centerline = float(
            report["minimum_self_collision_centerline_proxy_mm"])
        outbound_count = int(report["home_to_safe_high_waypoint_count"])
        records = []
        for index, (segment, goal) in enumerate(flat, start=1):
            before = dict(pre.positions)
            if any(abs(goal[name] - before[name]) > 2.0 + 1e-9 for name in JOINTS):
                raise RuntimeError(f"fresh_step_exceeds_two_degrees:{index}")
            command_attempted = True
            sent = transport.send_goal(goal)
            if set(sent) != set(goal) or any(
                    abs(float(sent[name]) - goal[name]) > 1e-9
                    for name in JOINT_UNITS):
                raise RuntimeError(f"actual_sent_goal_differs:{index}")
            final, settle_samples = wait_for_escape_settle(
                transport, timeout_s=5.0, settle_window_s=0.5, poll_s=0.1)
            after = dict(final.positions)
            q_after = np.asarray([after[name] for name in JOINTS], dtype=float)
            xyz = tcp_position_mm(kinematics, q_after, context["grasp_offset_mm"])
            table_margin = float(xyz[2] - context["table_reference_z_mm"])
            centerline = minimum_centerline_distance_mm(kinematics, q_after)
            verification = evaluate_return_waypoint(
                present_before=before,
                requested_target=goal,
                present_after=after,
                moving=final.moving,
                present_load=final.present_load,
                temperature_c=final.temperature_c,
                calibrated_bounds=calibrated_bounds,
                table_proxy_margin_mm=table_margin,
                minimum_table_proxy_margin_mm=minimum_table,
                self_collision_proxy_mm=centerline,
                minimum_self_collision_proxy_mm=minimum_centerline,
                feedback_fresh=True,
                communication_ok=True,
            )
            record = {
                "waypoint": index,
                "segment": segment,
                "requested_target": goal,
                "goal_raw": dict(final.goal_raw),
                "present_raw": dict(final.present_raw),
                "present_deg_or_pp": after,
                "moving": dict(final.moving),
                "present_load_diagnostic": dict(final.present_load),
                "temperature_c": dict(final.temperature_c),
                "grasp_tcp_xyz_mm": [float(value) for value in xyz],
                "table_proxy_margin_mm": table_margin,
                "self_collision_centerline_proxy_mm": centerline,
                "elbow": {
                    "goal_deg": float(goal["elbow_flex"]),
                    "present_deg": float(after["elbow_flex"]),
                    "error_deg": float(after["elbow_flex"] - goal["elbow_flex"]),
                    "moving": int(final.moving["elbow_flex"]),
                    "load_diagnostic": int(final.present_load["elbow_flex"]),
                },
                "verification": verification,
                "settle_samples": settle_samples,
            }
            print(json.dumps(record, separators=(",", ":")), flush=True)
            records.append(record)
            if not verification["pass"]:
                raise RuntimeError(f"waypoint_verification_failed:{index}")
            pre = final
            if index == outbound_count:
                safe_check = _terminal_check(after, context["safe_high"])
                if not safe_check["pass"]:
                    raise RuntimeError(f"safe_high_terminal_failed:{safe_check['errors']}")

        final_check = _terminal_check(dict(pre.positions), context["home"])
        print(json.dumps({
            "final_home_verification": final_check,
            "final_elbow": records[-1]["elbow"],
            "present_load_policy": "DIAGNOSTIC_ONLY_NOT_NUMERIC_GATE",
        }, separators=(",", ":")), flush=True)
        if not final_check["pass"]:
            raise RuntimeError("final_home_verification_failed")
        print("HOME_SAFE_HIGH_HOME_ONCE_PASS", flush=True)
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
    parser.add_argument("--poses", type=Path, default=Path("configs/poses.yaml"))
    parser.add_argument("--tcp-config", type=Path,
                        default=Path("configs/c_pick_grasp_tcp_candidate_20261012.json"))
    parser.add_argument("--escape-config", type=Path,
                        default=Path("configs/c_pick_safe_escape_only_20261012.json"))
    parser.add_argument("--calibration", type=Path,
                        default=Path("configs/so101_follower_calibration_bounds_20261008.json"))
    parser.add_argument("--urdf", type=Path, default=Path(
        ".local/c-red-pivot-tcp-table-20261011-s01/so101_new_calib.urdf"))
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-scope", choices=[SCOPE])
    args = parser.parse_args(argv)
    try:
        context = load_context(
            poses_path=args.poses, tcp_path=args.tcp_config,
            escape_path=args.escape_config, calibration_path=args.calibration,
            urdf_path=args.urdf,
        )
        return run(context=context, live=args.live,
                   confirm_scope=args.confirm_scope)
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(2, f"HOME_ROUND_TRIP_NOT_STARTED: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
