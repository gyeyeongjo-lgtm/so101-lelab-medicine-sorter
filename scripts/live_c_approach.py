#!/usr/bin/env python3
"""Execute one approved live-C move to the pre-approach joint target only.

Dry-run is the default. Live mode owns only the canonical follower bus, reads
the actual start pose, holds the fresh gripper position, and sends bounded
joint interpolation. It never starts/stops LeLab or advances to grasp/lift.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
import time

if __package__:
    from scripts.continuous_following_execution import ContinuousFollowingCycle
    from scripts.so101_exclusive_bus import ExclusiveFollowerLease, SystemBusProbe
    from scripts.so101_follower_transport import ARM_LIMITS_DEG, SO101FollowerTransport
    from scripts.staged_cycle_execution import JOINT_UNITS, StagedCycle
else:
    from continuous_following_execution import ContinuousFollowingCycle
    from so101_exclusive_bus import ExclusiveFollowerLease, SystemBusProbe
    from so101_follower_transport import ARM_LIMITS_DEG, SO101FollowerTransport
    from staged_cycle_execution import JOINT_UNITS, StagedCycle


ARM_NAMES = tuple(name for name in JOINT_UNITS if name != "gripper")
EXPECTED_URDF_SHA256 = "443d38d756e01bac7d3455b24430047ddc6427105e0d3454b2003116f5f67236"
EXPECTED_SERIAL = "5AE6058306"


def load_plan(path: Path, *, expected_scope: str = "live_c_pre_approach_only") -> dict:
    plan = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "schema_version", "scope", "source_frame_sha256", "c_robot_xy_mm",
        "target_robot_xyz_mm", "target_arm_deg", "ik_position_residual_mm",
        "urdf_sha256", "follower_port", "follower_serial_short",
        "maximum_joint_step_deg", "holds_fresh_gripper_position",
        "orientation_solved", "collision_checked", "motion_authorized",
    }
    if not required.issubset(plan):
        raise ValueError("approach_plan_fields_missing")
    if (plan["schema_version"] != 1 or plan["scope"] != expected_scope or
            plan["urdf_sha256"] != EXPECTED_URDF_SHA256 or
            plan["follower_port"] != "/dev/ttyACM1" or
            plan["follower_serial_short"] != EXPECTED_SERIAL or
            plan["holds_fresh_gripper_position"] is not True or
            plan["motion_authorized"] is not False or
            set(plan["target_arm_deg"]) != set(ARM_NAMES)):
        raise ValueError("approach_plan_contract_mismatch")
    numeric = [*plan["c_robot_xy_mm"], *plan["target_robot_xyz_mm"],
               *plan["target_arm_deg"].values(), plan["ik_position_residual_mm"],
               plan["maximum_joint_step_deg"]]
    if any(not isinstance(value, (int, float)) or not math.isfinite(value)
           for value in numeric):
        raise ValueError("approach_plan_nonfinite")
    if (len(plan["c_robot_xy_mm"]) != 2 or len(plan["target_robot_xyz_mm"]) != 3 or
            not 0 < plan["maximum_joint_step_deg"] <= 2.0 or
            plan["ik_position_residual_mm"] > 1.0):
        raise ValueError("approach_plan_geometry_invalid")
    refine_last = plan.get("refine_last_waypoints", 0)
    refinement_factor = plan.get("final_refinement_factor", 1)
    final_timeout_s = plan.get("final_waypoint_timeout_s", 3.0)
    if (type(refine_last) is not int or not 0 <= refine_last <= 5 or
            type(refinement_factor) is not int or not 1 <= refinement_factor <= 4 or
            not isinstance(final_timeout_s, (int, float)) or
            not math.isfinite(final_timeout_s) or not 3.0 <= final_timeout_s <= 10.0):
        raise ValueError("approach_convergence_policy_invalid")
    plan["refine_last_waypoints"] = refine_last
    plan["final_refinement_factor"] = refinement_factor
    plan["final_waypoint_timeout_s"] = float(final_timeout_s)
    execution_mode = plan.get("execution_mode", "stop_and_wait")
    if execution_mode not in {"stop_and_wait", "bounded_continuous_following"}:
        raise ValueError("approach_execution_mode_invalid")
    plan["execution_mode"] = execution_mode
    if execution_mode == "bounded_continuous_following":
        limits = plan.get("following_error_limits_deg")
        expected_limits = {name: (4.0 if name == "elbow_flex" else 2.5)
                           for name in ARM_NAMES}
        cadence_s = plan.get("following_cadence_s")
        no_progress_s = plan.get("following_no_progress_timeout_s")
        progress_epsilon = plan.get("following_progress_epsilon_deg")
        if (plan["maximum_joint_step_deg"] > 1.0 or
                limits != expected_limits or
                not isinstance(cadence_s, (int, float)) or
                not math.isfinite(cadence_s) or not 0.15 <= cadence_s <= 0.3 or
                not isinstance(no_progress_s, (int, float)) or
                not math.isfinite(no_progress_s) or no_progress_s <= cadence_s or
                not isinstance(progress_epsilon, (int, float)) or
                not math.isfinite(progress_epsilon) or not 0 < progress_epsilon <= 0.25):
            raise ValueError("continuous_following_plan_invalid")
        plan["following_cadence_s"] = float(cadence_s)
        plan["following_no_progress_timeout_s"] = float(no_progress_s)
        plan["following_progress_epsilon_deg"] = float(progress_epsilon)
    for name, value in plan["target_arm_deg"].items():
        lower, upper = ARM_LIMITS_DEG[name]
        if not lower <= value <= upper:
            raise ValueError("approach_target_outside_installed_urdf")
    intermediates = plan.get("staged_intermediate_arm_deg", [])
    reference_start = plan.get("staged_reference_start_arm_deg")
    if intermediates or reference_start is not None:
        if (not isinstance(intermediates, list) or not 1 <= len(intermediates) <= 6 or
                not isinstance(reference_start, dict) or
                set(reference_start) != set(ARM_NAMES)):
            raise ValueError("staged_approach_contract_invalid")
        for stage in [reference_start, *intermediates]:
            if (not isinstance(stage, dict) or set(stage) != set(ARM_NAMES) or
                    any(not isinstance(value, (int, float)) or not math.isfinite(value)
                        for value in stage.values())):
                raise ValueError("staged_approach_joint_shape_invalid")
            for name, value in stage.items():
                lower, upper = ARM_LIMITS_DEG[name]
                if not lower <= value <= upper:
                    raise ValueError("staged_approach_joint_outside_installed_urdf")
    plan["staged_intermediate_arm_deg"] = intermediates
    plan["staged_reference_start_arm_deg"] = reference_start
    return plan


def interpolate_goals(start: dict[str, float], target_arm: dict[str, float],
                      max_step_deg: float, *, refine_last_waypoints: int = 0,
                      final_refinement_factor: int = 1) -> list[dict[str, float]]:
    if set(start) != set(JOINT_UNITS) or set(target_arm) != set(ARM_NAMES):
        raise ValueError("interpolation_joint_shape_mismatch")
    if (not math.isfinite(max_step_deg) or not 0 < max_step_deg <= 2.0 or
            type(refine_last_waypoints) is not int or refine_last_waypoints < 0 or
            type(final_refinement_factor) is not int or final_refinement_factor < 1 or
            any(not isinstance(value, (int, float)) or not math.isfinite(value)
                for value in [*start.values(), *target_arm.values()])):
        raise ValueError("interpolation_input_invalid")
    largest = max(abs(target_arm[name] - start[name]) for name in ARM_NAMES)
    steps = max(1, math.ceil(largest / max_step_deg))
    base_goals = []
    for index in range(1, steps + 1):
        fraction = index / steps
        goal = {
            name: start[name] + (target_arm[name] - start[name]) * fraction
            for name in ARM_NAMES
        }
        goal["gripper"] = start["gripper"]
        base_goals.append(goal)
    if refine_last_waypoints == 0 or final_refinement_factor == 1:
        return base_goals

    # Subdivide only the tail of the already validated linear route. This adds
    # smaller final elbow steps without changing the joint-space line or target.
    refined = []
    segment_start = dict(start)
    first_refined = max(0, len(base_goals) - refine_last_waypoints)
    for index, segment_end in enumerate(base_goals):
        factor = final_refinement_factor if index >= first_refined else 1
        for part in range(1, factor + 1):
            fraction = part / factor
            goal = {
                name: segment_start[name] +
                      (segment_end[name] - segment_start[name]) * fraction
                for name in ARM_NAMES
            }
            goal["gripper"] = start["gripper"]
            refined.append(goal)
        segment_start = segment_end
    return refined


def interpolate_staged_goals(
    start: dict[str, float],
    intermediate_arm: list[dict[str, float]],
    target_arm: dict[str, float],
    max_step_deg: float,
    *,
    refine_last_waypoints: int = 0,
    final_refinement_factor: int = 1,
) -> list[dict[str, float]]:
    """Concatenate bounded linear stages while preserving one final endpoint."""
    previous = dict(start)
    goals = []
    targets = [*intermediate_arm, target_arm]
    for index, target in enumerate(targets):
        final_segment = index == len(targets) - 1
        segment = interpolate_goals(
            previous, target, max_step_deg,
            refine_last_waypoints=(refine_last_waypoints if final_segment else 0),
            final_refinement_factor=(final_refinement_factor if final_segment else 1),
        )
        goals.extend(segment)
        previous = dict(segment[-1])
    return goals


def validate_staged_reference_start(
    fresh: dict[str, float], reference_arm: dict[str, float] | None,
    *, tolerance_deg: float = 1.0,
) -> None:
    if reference_arm is None:
        return
    if set(fresh) != set(JOINT_UNITS) or set(reference_arm) != set(ARM_NAMES):
        raise ValueError("staged_reference_start_shape_invalid")
    errors = {name: fresh[name] - reference_arm[name] for name in ARM_NAMES}
    if any(abs(value) > tolerance_deg for value in errors.values()):
        detail = ",".join(f"{name}={value:+.3f}" for name, value in errors.items())
        raise RuntimeError(f"staged_reference_start_mismatch:{detail}")


def verify_final_feedback(transport, goal: dict[str, float],
                          tolerances: dict[str, float], *,
                          max_age_s: float) -> tuple[dict[str, float], dict[str, float]]:
    feedback = transport.read_feedback()
    now = time.monotonic()
    if (feedback is None or set(feedback.positions) != set(goal) or
            not feedback.received_monotonic <= now or
            now - feedback.received_monotonic > max_age_s or
            any(not math.isfinite(feedback.positions[name]) for name in goal)):
        raise RuntimeError("final_fresh_feedback_invalid")
    positions = dict(feedback.positions)
    errors = {name: positions[name] - goal[name] for name in goal}
    if any(abs(errors[name]) > tolerances[name] for name in goal):
        detail = ",".join(f"{name}={error:+.3f}" for name, error in errors.items())
        raise RuntimeError(f"final_fresh_feedback_outside_tolerance:{detail}")
    return positions, errors


def persist_elbow_diagnostic(transport, output_path: Path | None) -> dict | None:
    if output_path is None:
        return None
    report = transport.elbow_diagnostic_report()
    if report is None:
        return None
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def run(plan_path: Path, *, live: bool, confirm_scope: str | None,
        elbow_diagnostic_output: Path | None = None,
        following_log_output: Path | None = None,
        input_fn=input, transport_factory=None) -> int:
    plan = load_plan(plan_path)
    print(json.dumps({
        "scope": plan["scope"],
        "source_frame_sha256": plan["source_frame_sha256"],
        "target_robot_xyz_mm": plan["target_robot_xyz_mm"],
        "target_arm_deg": plan["target_arm_deg"],
        "orientation_solved": False,
        "collision_checked": False,
        "refine_last_waypoints": plan["refine_last_waypoints"],
        "final_refinement_factor": plan["final_refinement_factor"],
        "final_waypoint_timeout_s": plan["final_waypoint_timeout_s"],
        "execution_mode": plan["execution_mode"],
        "following_cadence_s": plan.get("following_cadence_s"),
        "following_error_limits_deg": plan.get("following_error_limits_deg"),
        "staged_reference_start_arm_deg": plan["staged_reference_start_arm_deg"],
        "staged_intermediate_arm_deg": plan["staged_intermediate_arm_deg"],
        "following_log_output": (str(following_log_output)
                                 if following_log_output is not None else None),
        "elbow_diagnostic_output": (str(elbow_diagnostic_output)
                                    if elbow_diagnostic_output is not None else None),
        "dry_run": not live,
    }, separators=(",", ":")), flush=True)
    if not live:
        print("DRY_RUN: no port opened; no send_action", flush=True)
        return 0
    if confirm_scope != plan["scope"]:
        raise ValueError("live_scope_mismatch")
    if (plan["execution_mode"] == "bounded_continuous_following" and
            following_log_output is None):
        raise ValueError("continuous_following_log_required")
    if (following_log_output is not None and following_log_output.exists()):
        raise ValueError("continuous_following_log_already_exists")
    phrase = "RUN LIVE C APPROACH"
    if input_fn("C unchanged, path clear, site stop ready. Type RUN LIVE C APPROACH: ") != phrase:
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
    try:
        first = transport.read_feedback()
        if (set(first.positions) != set(JOINT_UNITS) or
                any(not math.isfinite(first.positions[name]) for name in JOINT_UNITS)):
            raise ValueError("fresh_start_feedback_invalid")
        start = dict(first.positions)
        transport.verify_start_pose(
            start, {name: (2.0 if name == "gripper" else 1.0) for name in JOINT_UNITS})
        validate_staged_reference_start(start, plan["staged_reference_start_arm_deg"])
        goals = interpolate_staged_goals(
            start, plan["staged_intermediate_arm_deg"], plan["target_arm_deg"],
            plan["maximum_joint_step_deg"],
            refine_last_waypoints=plan["refine_last_waypoints"],
            final_refinement_factor=plan["final_refinement_factor"])
        if (elbow_diagnostic_output is not None and
                plan["execution_mode"] == "stop_and_wait"):
            transport.configure_elbow_diagnostic(
                total_waypoints=len(goals), tail_waypoints=min(10, len(goals)))
        print(json.dumps({"fresh_start": start, "waypoints": len(goals),
                          "gripper_hold": start["gripper"]},
                         separators=(",", ":")), flush=True)
        tolerances = {name: (2.0 if name == "gripper" else 1.6)
                      for name in JOINT_UNITS}
        if plan["execution_mode"] == "bounded_continuous_following":
            assert following_log_output is not None
            following_log_output.parent.mkdir(parents=True, exist_ok=True)

            def write_following_row(row: dict) -> None:
                with following_log_output.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(row, separators=(",", ":")) + "\n")
                    stream.flush()

            controller = ContinuousFollowingCycle(
                transport, tolerances,
                planned_start=start,
                following_limits=plan["following_error_limits_deg"],
                max_joint_step_deg=plan["maximum_joint_step_deg"],
                cadence_s=plan["following_cadence_s"],
                no_progress_timeout_s=plan["following_no_progress_timeout_s"],
                progress_epsilon_deg=plan["following_progress_epsilon_deg"],
                final_timeout_s=plan["final_waypoint_timeout_s"],
                feedback_max_age_s=0.5, stable_s=0.1, poll_s=0.05,
                log_sink=write_following_row)
        else:
            controller = StagedCycle(
                transport, tolerances, timeout_s=3.0,
                final_timeout_s=plan["final_waypoint_timeout_s"],
                feedback_max_age_s=0.5, stable_s=0.1, poll_s=0.02)
        controller.start_stage("approach", goals, approved=True)
        if plan["execution_mode"] == "bounded_continuous_following":
            wait_timeout_s = (len(goals) *
                              (plan["following_cadence_s"] +
                               plan["following_no_progress_timeout_s"]) +
                              plan["final_waypoint_timeout_s"] + 10.0)
        else:
            wait_timeout_s = (len(goals) * 3.0 +
                              max(0.0, plan["final_waypoint_timeout_s"] - 3.0) + 10.0)
        if not controller.wait_worker(wait_timeout_s):
            raise RuntimeError("approach_worker_timeout")
        if (elbow_diagnostic_output is not None and
                plan["execution_mode"] == "stop_and_wait"):
            transport.collect_final_elbow_settle(duration_s=3.0, interval_s=0.15)
            report = persist_elbow_diagnostic(transport, elbow_diagnostic_output)
            for row in report["samples"] if report is not None else []:
                print(json.dumps({"elbow_diagnostic": row}, separators=(",", ":")),
                      flush=True)
            print(f"ELBOW_DIAGNOSTIC_SAVED={elbow_diagnostic_output}", flush=True)
        if (controller.reach_state != "GOAL_REACHED" or
                controller.task_state != "USER_CONFIRMATION_REQUIRED" or
                controller.waypoints_reached != len(goals)):
            raise RuntimeError(f"approach_failed:{controller.failure}")
        final_positions, final_errors = verify_final_feedback(
            transport, goals[-1], tolerances, max_age_s=0.5)
        print(json.dumps({
            "final_fresh_feedback": final_positions,
            "final_error_deg_or_pp": final_errors,
            "within_tolerance": True,
        }, separators=(",", ":")), flush=True)
        print(f"APPROACH_REACHED waypoints={len(goals)}", flush=True)
        if input_fn("Physical TCP above C and scene safe? Type APPROACH CONFIRMED: ") != "APPROACH CONFIRMED":
            raise RuntimeError("approach_site_result_not_confirmed")
        controller.confirm_task_result(stage="approach", human_observed=True, result=True)
        print("PRE_APPROACH_PASS", flush=True)
        outcome = 0
    except (KeyboardInterrupt, Exception) as error:
        print(f"ABORT: {type(error).__name__}: {error}", file=sys.stderr, flush=True)
    finally:
        try:
            persist_elbow_diagnostic(transport, elbow_diagnostic_output)
        except Exception as error:
            outcome = 1
            print(f"elbow_diagnostic_save_failed:{type(error).__name__}:{error}",
                  file=sys.stderr, flush=True)
        transport.stop_commands()
        try:
            if controller is not None:
                controller.request_stop()
                controller.verify_stop_completed(timeout_s=3.0)
                human_stopped = input_fn("Arm stopped and scene safe? Type STOPPED: ") == "STOPPED"
                stable = controller.verify_arm_stopped(
                    motion_tolerances={name: (2.0 if name == "gripper" else 1.0)
                                       for name in JOINT_UNITS},
                    window_s=0.5, timeout_s=3.0, human_confirmed=human_stopped)
                if stable:
                    transport.close_after_site_confirmation(controller, object_supported=True)
                    closed = True
                    print("physical_stop=FEEDBACK_AND_HUMAN_CONFIRMED", flush=True)
                else:
                    outcome = 1
                    print("physical_stop=NOT_VERIFIED", file=sys.stderr, flush=True)
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
    parser.add_argument("--confirm-scope", choices=["live_c_pre_approach_only"])
    parser.add_argument("--elbow-diagnostic-output", type=Path)
    parser.add_argument("--following-log-output", type=Path)
    args = parser.parse_args(argv)
    try:
        return run(args.plan, live=args.live, confirm_scope=args.confirm_scope,
                   elbow_diagnostic_output=args.elbow_diagnostic_output,
                   following_log_output=args.following_log_output)
    except (OSError, ValueError) as error:
        parser.exit(2, f"APPROACH_NOT_STARTED: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
