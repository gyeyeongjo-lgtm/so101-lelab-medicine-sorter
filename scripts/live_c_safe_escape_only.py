#!/usr/bin/env python3
"""Execute exactly one fresh-pose-relative PICK clearance target.

Dry-run is the default.  Live mode derives one target from fresh follower
feedback, checks every arm step is at most one degree, verifies the GRASP-TCP
point proxy is above the saved table reference, and stops.  It contains no
pre-approach, approach, grasp, lift, or automatic continuation.
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
    from scripts.plan_pick_grasp_tcp_ik import JOINTS, tcp_position_mm
    from scripts.so101_exclusive_bus import ExclusiveFollowerLease, SystemBusProbe
    from scripts.so101_follower_transport import (
        SO101FollowerTransport, verify_installed_urdf,
    )
    from scripts.staged_cycle_execution import JOINT_UNITS, StagedCycle
    from scripts.urdf_forward_kinematics import UrdfKinematics
else:
    from plan_pick_grasp_tcp_ik import JOINTS, tcp_position_mm
    from so101_exclusive_bus import ExclusiveFollowerLease, SystemBusProbe
    from so101_follower_transport import SO101FollowerTransport, verify_installed_urdf
    from staged_cycle_execution import JOINT_UNITS, StagedCycle
    from urdf_forward_kinematics import UrdfKinematics


SCOPE = "c_pick_safe_escape_only"
RUN_PHRASE = "RUN SAFE ESCAPE ONLY"
CONFIRM_PHRASE = "ESCAPE CLEARANCE CONFIRMED"


class SafeEscapeCycle(StagedCycle):
    """One-stage adapter over the generic staged controller.

    The base controller's first slot is named ``approach``.  This adapter
    exposes only ``safe_escape`` so logs and human confirmation cannot imply
    that the PICK approach was attempted.
    """

    def start_stage(self, stage, goals, *, approved):
        if stage != "safe_escape":
            raise ValueError("safe_escape_only_stage")
        super().start_stage("approach", goals, approved=approved)
        self.stage = "safe_escape"


def load_plan(path: Path) -> dict:
    plan = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "scope", "confirmed_fresh_arm_deg", "confirmed_start_tolerance_deg",
        "escape_direction", "maximum_joint_step_deg", "final_tolerance_deg",
        "final_timeout_s", "pick_grasp_tcp_offset_gripper_mm",
        "table_contact_reference_z_mm", "minimum_commanded_table_proxy_margin_mm",
        "urdf_sha256", "follower_port", "follower_serial_short",
        "full_mesh_collision_status", "motion_authorized",
    }
    if not required <= set(plan) or plan["scope"] != SCOPE:
        raise ValueError("safe_escape_scope_or_schema_invalid")
    if plan["motion_authorized"] is not False:
        raise ValueError("plan_must_not_self_authorize")
    if plan["full_mesh_collision_status"] != "NOT_VERIFIED":
        raise ValueError("full_mesh_status_must_remain_not_verified")
    if (set(plan["confirmed_fresh_arm_deg"]) != set(JOINTS) or
            set(plan["escape_direction"]) != set(JOINTS)):
        raise ValueError("safe_escape_joint_shape_invalid")
    numeric = (
        list(plan["confirmed_fresh_arm_deg"].values()) +
        [plan["confirmed_start_tolerance_deg"], plan["maximum_joint_step_deg"],
         plan["final_tolerance_deg"], plan["final_timeout_s"],
         plan["table_contact_reference_z_mm"],
         plan["minimum_commanded_table_proxy_margin_mm"]] +
        list(plan["pick_grasp_tcp_offset_gripper_mm"])
    )
    if any(not isinstance(value, (int, float)) or not math.isfinite(value)
           for value in numeric):
        raise ValueError("safe_escape_nonfinite_value")
    if (not 0 < plan["confirmed_start_tolerance_deg"] <= 0.5 or
            not 0 < plan["maximum_joint_step_deg"] <= 1.0 or
            not 0 < plan["final_tolerance_deg"] < plan["maximum_joint_step_deg"] or
            not 3.0 <= plan["final_timeout_s"] <= 10.0 or
            len(plan["pick_grasp_tcp_offset_gripper_mm"]) != 3 or
            any(plan["escape_direction"][name] not in (-1, 1) for name in JOINTS)):
        raise ValueError("safe_escape_policy_invalid")
    return plan


def assert_confirmed_start(start: Mapping[str, float], plan: dict) -> None:
    if set(start) != set(JOINT_UNITS):
        raise ValueError("fresh_start_feedback_invalid")
    tolerance = float(plan["confirmed_start_tolerance_deg"])
    errors = {
        name: float(start[name]) - float(plan["confirmed_fresh_arm_deg"][name])
        for name in JOINTS
    }
    if any(abs(value) > tolerance for value in errors.values()):
        detail = ",".join(f"{name}={value:+.3f}" for name, value in errors.items())
        raise RuntimeError(f"site_confirmed_start_changed:{detail}")


def build_fresh_escape_goal(start: Mapping[str, float], plan: dict,
                            calibrated_bounds: Mapping[str, tuple[float, float]]) -> dict[str, float]:
    if set(start) != set(JOINT_UNITS) or set(calibrated_bounds) != set(JOINT_UNITS):
        raise ValueError("fresh_escape_shape_invalid")
    step = float(plan["maximum_joint_step_deg"])
    goal = {name: float(start[name]) for name in JOINT_UNITS}
    for name in JOINTS:
        goal[name] += float(plan["escape_direction"][name]) * step
    if any(not calibrated_bounds[name][0] <= goal[name] <= calibrated_bounds[name][1]
           for name in JOINT_UNITS):
        raise RuntimeError("fresh_escape_outside_servo_bounds")
    if (abs(goal["gripper"] - start["gripper"]) > 1e-12 or
            max(abs(goal[name] - start[name]) for name in JOINTS) > step + 1e-12):
        raise RuntimeError("fresh_escape_step_contract_failed")
    return goal


def table_proxy(kinematics: UrdfKinematics, goal: Mapping[str, float], plan: dict) -> dict:
    q = np.asarray([goal[name] for name in JOINTS], dtype=float)
    offset = np.asarray(plan["pick_grasp_tcp_offset_gripper_mm"], dtype=float)
    xyz = tcp_position_mm(kinematics, q, offset)
    margin = float(xyz[2] - float(plan["table_contact_reference_z_mm"]))
    if margin <= float(plan["minimum_commanded_table_proxy_margin_mm"]):
        raise RuntimeError(f"commanded_table_proxy_not_positive:{margin:.6f}")
    return {
        "grasp_tcp_xyz_mm": [float(value) for value in xyz],
        "table_proxy_margin_mm": margin,
        "full_mesh_collision_status": "NOT_VERIFIED",
    }


def run(plan_path: Path, *, live: bool, confirm_scope: str | None,
        input_fn=input, transport_factory=None, urdf_path_factory=None,
        controller_factory=SafeEscapeCycle) -> int:
    plan = load_plan(plan_path)
    print(json.dumps({
        "scope": SCOPE,
        "fresh_relative_target": True,
        "maximum_joint_step_deg": plan["maximum_joint_step_deg"],
        "final_tolerance_deg": plan["final_tolerance_deg"],
        "full_mesh_collision_status": "NOT_VERIFIED",
        "automatic_continuation": False,
        "dry_run": not live,
    }, separators=(",", ":")), flush=True)
    if not live:
        print("DRY_RUN: no port opened; no send_action; escape/approach/grasp/lift unavailable", flush=True)
        return 0
    if confirm_scope != SCOPE:
        raise ValueError("live_scope_mismatch")
    if input_fn(
        f"Initial link clearance confirmed; run one escape target only. Type {RUN_PHRASE}: "
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
    outcome = 1
    closed = False
    command_attempted = False
    try:
        first = transport.read_feedback()
        start = dict(first.positions)
        assert_confirmed_start(start, plan)
        verified = transport.verify_start_pose(
            start, {name: (1.0 if name == "gripper" else 0.25) for name in JOINT_UNITS})
        start = dict(verified.positions)
        assert_confirmed_start(start, plan)
        goal = build_fresh_escape_goal(start, plan, transport.calibrated_bounds)

        installed_urdf = ((urdf_path_factory or verify_installed_urdf)())
        if hashlib.sha256(Path(installed_urdf).read_bytes()).hexdigest() != plan["urdf_sha256"]:
            raise RuntimeError("installed_urdf_changed")
        proxy = table_proxy(UrdfKinematics.from_file(Path(installed_urdf)), goal, plan)
        print(json.dumps({
            "fresh_start": start,
            "escape_target": goal,
            "per_joint_step_deg_or_pp": {
                name: goal[name] - start[name] for name in JOINT_UNITS
            },
            **proxy,
        }, separators=(",", ":")), flush=True)

        tolerances = {
            name: (1.0 if name == "gripper" else float(plan["final_tolerance_deg"]))
            for name in JOINT_UNITS
        }
        controller = controller_factory(
            transport, tolerances, timeout_s=float(plan["final_timeout_s"]),
            final_timeout_s=float(plan["final_timeout_s"]),
            feedback_max_age_s=0.5, stable_s=0.15, poll_s=0.05)
        command_attempted = True
        controller.start_stage("safe_escape", [goal], approved=True)
        if not controller.wait_worker(float(plan["final_timeout_s"]) + 5.0):
            raise RuntimeError("safe_escape_worker_timeout")
        if (controller.reach_state != "GOAL_REACHED" or
                controller.task_state != "USER_CONFIRMATION_REQUIRED" or
                controller.waypoints_reached != 1 or
                controller.waypoints_transmitted != 1):
            raise RuntimeError(f"safe_escape_failed:{controller.failure}")
        final = transport.read_feedback()
        errors = {name: float(final.positions[name]) - goal[name] for name in JOINT_UNITS}
        if any(abs(errors[name]) > tolerances[name] for name in JOINT_UNITS):
            raise RuntimeError("safe_escape_final_fresh_feedback_outside_tolerance")
        print(json.dumps({
            "final_fresh_feedback": dict(final.positions),
            "final_error_deg_or_pp": errors,
            "within_tolerance": True,
        }, separators=(",", ":")), flush=True)
        if input_fn(
            f"No link contact and real table clearance not worse? Type {CONFIRM_PHRASE}: "
        ) != CONFIRM_PHRASE:
            raise RuntimeError("safe_escape_site_result_not_confirmed")
        controller.confirm_task_result(
            stage="safe_escape", human_observed=True, result=True)
        print("SAFE_ESCAPE_PASS", flush=True)
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
                    window_s=0.5, timeout_s=3.0, human_confirmed=human_stopped)
                if stable:
                    transport.close_after_site_confirmation(controller, object_supported=True)
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
        parser.exit(2, f"SAFE_ESCAPE_NOT_STARTED: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
