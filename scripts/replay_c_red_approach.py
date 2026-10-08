"""Human-supervised, time-scaled first segment of the recorded C->red trace.

Dry-run is the default and never imports LeRobot. Live mode is deliberately
limited to safe_start through the approach keypoint; it is not a full cycle.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import time

from scripts.so101_exclusive_bus import ExclusiveFollowerLease, SystemBusProbe
from scripts.so101_follower_transport import (
    ARM_LIMITS_DEG, EXPECTED_URDF_SHA256, SO101FollowerTransport,
)
from scripts.staged_cycle_execution import JOINT_UNITS


SOURCE_SHA = "01a8b48183ed90d1acc34d70ce855520e9fa75f75fa6d1ffaae822005bf18978"
CANDIDATE_SHA = "684d90e61f23ac849ccd74152bac71ad0baf2eb00961c425daa6ca5763f265fa"
APPROACH_SEQ = 45133
START_SEQ = 28363
START_TOLERANCE = {name: 3.0 for name in JOINT_UNITS}
START_TOLERANCE["gripper"] = 3.0
# Conservative first-trial tracking thresholds, below the ~8.7 degree
# demonstration peaks. Exceeding one starts bounded settle; far error or
# non-recovery aborts. They are not success criteria.
TRACKING_ABORT = {
    "shoulder_pan": 3.0, "shoulder_lift": 4.0, "elbow_flex": 4.0,
    "wrist_flex": 3.0, "wrist_roll": 3.0, "gripper": 8.0,
}
MIN_ARM_MARGIN_DEG = 5.0
SETTLE_TIMEOUT_S = 2.0
SETTLE_POLL_S = 0.05
SETTLE_GROWTH_MIN_ARM_ERROR_DEG = 1.5
SETTLE_GROWTH_MIN_GRIPPER_ERROR_PERCENT = 4.0
SETTLE_GROWTH_CONSECUTIVE_SAMPLES = 2


class TrialAbort(RuntimeError):
    pass


def load_segment(path: Path) -> list[dict]:
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != CANDIDATE_SHA:
        raise ValueError("candidate_file_changed")
    data = json.loads(raw)
    if data.get("source_cycle_sha256") != SOURCE_SHA:
        raise ValueError("unexpected_source_trace")
    if data.get("source_urdf_sha256") != EXPECTED_URDF_SHA256:
        raise ValueError("unexpected_urdf_snapshot")
    points = data["waypoints"]
    if not points or points[0]["seq"] != START_SEQ:
        raise ValueError("safe_start_missing")
    selected = []
    for point in points:
        selected.append(point)
        if point["seq"] == APPROACH_SEQ:
            break
    if selected[-1]["seq"] != APPROACH_SEQ:
        raise ValueError("approach_missing")
    previous_time = -1.0
    previous_seq = START_SEQ - 1
    for point in selected:
        elapsed = point["elapsed_from_safe_start_s"]
        goal = point["goal"]
        reference = point["observed_feedback"]
        if (point["seq"] <= previous_seq or not math.isfinite(elapsed) or
                elapsed <= previous_time or set(goal) != set(JOINT_UNITS) or
                set(reference) != set(JOINT_UNITS) or
                any(not math.isfinite(float(v)) for v in (*goal.values(), *reference.values()))):
            raise ValueError("invalid_segment_point")
        for positions in (goal, reference):
            if any(not low <= positions[name] <= high
                   for name, (low, high) in ARM_LIMITS_DEG.items()):
                raise ValueError("point_outside_urdf")
        previous_time, previous_seq = elapsed, point["seq"]
    return selected


def check_feedback_safety(actual) -> None:
    if set(actual) != set(JOINT_UNITS):
        raise TrialAbort("feedback_shape_mismatch")
    if any(not math.isfinite(actual[name]) for name in JOINT_UNITS):
        raise TrialAbort("feedback_nonfinite")
    for name, (low, high) in ARM_LIMITS_DEG.items():
        if min(actual[name] - low, high - actual[name]) < MIN_ARM_MARGIN_DEG:
            raise TrialAbort(f"urdf_margin_below_5deg:{name}")


def check_feedback(actual, reference, goal) -> None:
    check_feedback_safety(actual)
    for name in JOINT_UNITS:
        # The demonstrated feedback is an observation, not a second goal. In
        # this approach segment the gripper command/reference gap reaches
        # 30.7 percentage points; requiring both to match is impossible.
        if abs(actual[name] - goal[name]) > TRACKING_ABORT[name]:
            raise TrialAbort(f"tracking_guard_exceeded:{name}")


def run_timed_segment(points, transport, *, time_scale: float, clock=time.monotonic,
                      sleep=time.sleep, progress=None, on_feedback=None,
                      on_timing=None, on_sample_timing=None) -> int:
    """One fresh feedback read per sent goal; never substitute sent values."""
    if not math.isfinite(time_scale) or time_scale < 2.0:
        raise ValueError("time_scale_must_be_at_least_2")
    initial = transport.verify_start_pose(points[0]["goal"], START_TOLERANCE)
    last_actual = dict(initial.positions)
    last_goal = points[0]["goal"]
    start = clock()
    sent_count = 0
    previous_errors = {name: abs(last_actual[name] - last_goal[name]) for name in JOINT_UNITS}
    increasing_counts = {name: 0 for name in JOINT_UNITS}
    lag_started = {name: None for name in ARM_LIMITS_DEG}
    schedule_rebase_s = 0.0
    for target_index, point in enumerate(points[1:], 1):  # first point is a pose gate
        previous_point = points[target_index - 1]
        nominal_interval_s = (point["elapsed_from_safe_start_s"] -
                              previous_point["elapsed_from_safe_start_s"]) * time_scale
        nominal_deadline = start + point["elapsed_from_safe_start_s"] * time_scale
        deadline = nominal_deadline + schedule_rebase_s
        while clock() < deadline:
            sleep(min(0.02, deadline - clock()))
        lateness = clock() - deadline
        if lateness > 0.5:
            raise TrialAbort(f"scheduler_overrun:seq={point['seq']}:lateness_s={lateness:.3f}")
        sent_at = clock()
        sent = transport.send_goal(point["goal"])
        send_returned_at = clock()
        sent_count += 1
        if progress is not None:
            progress(sent_count, point["seq"])
        if any(abs(sent[name] - point["goal"][name]) > 1e-9 for name in JOINT_UNITS):
            raise TrialAbort("sent_goal_changed")
        feedback_read_started_at = clock()
        observed = transport.read_feedback()  # new Present_Position after send
        first_feedback_read_ended_at = clock()
        first_feedback_at = observed.received_monotonic
        if on_feedback is not None:
            on_feedback(point, sent, observed)  # log before every abort check
        if on_sample_timing is not None:
            on_sample_timing({
                "target_index": target_index, "seq": point["seq"],
                "nominal_interval_s": nominal_interval_s,
                "nominal_deadline_monotonic": nominal_deadline,
                "scheduled_send_monotonic": deadline,
                "send_call_monotonic": sent_at,
                "send_return_monotonic": send_returned_at,
                "feedback_read_started_monotonic": feedback_read_started_at,
                "feedback_read_ended_monotonic": first_feedback_read_ended_at,
                "feedback_monotonic": observed.received_monotonic,
                "settle_start_monotonic": None,
                "settle_end_monotonic": None,
                "settle_elapsed_s": 0.0,
                "command_feedback_abs_error": {
                    name: abs(sent[name] - observed.positions[name]) for name in JOINT_UNITS
                },
                "minimum_arm_urdf_margin_deg": min(
                    min(observed.positions[name] - low, high - observed.positions[name])
                    for name, (low, high) in ARM_LIMITS_DEG.items()
                ),
                "guard_state": "PENDING_CHECK",
            })
        if observed.received_monotonic <= sent_at:
            raise TrialAbort("feedback_not_fresh_after_send")
        settle_start = clock()
        first_errors = {name: abs(observed.positions[name] - point["goal"][name])
                        for name in JOINT_UNITS}
        far_limits = {
            name: TRACKING_ABORT[name] + abs(point["goal"][name] - last_goal[name]) +
            (1.0 if name == "gripper" else 0.5)
            for name in JOINT_UNITS
        }
        for name, error in first_errors.items():
            if error > far_limits[name]:
                raise TrialAbort(f"tracking_guard_far_exceeded:{name}")
        settle_growth_counts = {name: 0 for name in JOINT_UNITS}
        settle_reads = 0
        final_feedback_read_started_at = feedback_read_started_at
        final_feedback_read_ended_at = first_feedback_read_ended_at
        while True:
            try:
                check_feedback(observed.positions, point["observed_feedback"], point["goal"])
                break
            except TrialAbort as error:
                if not str(error).startswith("tracking_guard_exceeded:"):
                    raise
                if clock() - settle_start >= SETTLE_TIMEOUT_S:
                    raise TrialAbort(f"tracking_settle_timeout:{error}") from error
                sleep(SETTLE_POLL_S)
                final_feedback_read_started_at = clock()
                next_observed = transport.read_feedback()
                final_feedback_read_ended_at = clock()
                settle_reads += 1
                if on_feedback is not None:
                    on_feedback(point, sent, next_observed)
                if on_sample_timing is not None:
                    on_sample_timing({
                        "target_index": target_index, "seq": point["seq"],
                        "nominal_interval_s": nominal_interval_s,
                        "nominal_deadline_monotonic": nominal_deadline,
                        "scheduled_send_monotonic": deadline,
                        "send_call_monotonic": sent_at,
                        "send_return_monotonic": send_returned_at,
                        "feedback_read_started_monotonic": final_feedback_read_started_at,
                        "feedback_read_ended_monotonic": final_feedback_read_ended_at,
                        "feedback_monotonic": next_observed.received_monotonic,
                        "settle_start_monotonic": settle_start,
                        "settle_end_monotonic": clock(),
                        "settle_elapsed_s": clock() - settle_start,
                        "command_feedback_abs_error": {
                            name: abs(sent[name] - next_observed.positions[name])
                            for name in JOINT_UNITS
                        },
                        "minimum_arm_urdf_margin_deg": min(
                            min(next_observed.positions[name] - low,
                                high - next_observed.positions[name])
                            for name, (low, high) in ARM_LIMITS_DEG.items()
                        ),
                        "guard_state": "PENDING_CHECK",
                    })
                if next_observed.received_monotonic <= observed.received_monotonic:
                    raise TrialAbort("feedback_not_fresh_during_settle")
                # Safety checks apply to every new sample, including one that
                # is about to be rejected by the per-joint growth debounce.
                check_feedback_safety(next_observed.positions)
                for name in JOINT_UNITS:
                    old_error = abs(observed.positions[name] - point["goal"][name])
                    new_error = abs(next_observed.positions[name] - point["goal"][name])
                    if new_error > far_limits[name]:
                        raise TrialAbort(f"tracking_guard_far_exceeded:{name}")
                    growth_limit = 1.0 if name == "gripper" else 0.5
                    meaningful_error = (SETTLE_GROWTH_MIN_GRIPPER_ERROR_PERCENT
                                        if name == "gripper" else SETTLE_GROWTH_MIN_ARM_ERROR_DEG)
                    if new_error >= meaningful_error and new_error - old_error > growth_limit:
                        settle_growth_counts[name] += 1
                    else:
                        settle_growth_counts[name] = 0
                    if settle_growth_counts[name] >= SETTLE_GROWTH_CONSECUTIVE_SAMPLES:
                        raise TrialAbort(f"tracking_error_growing_during_settle:{name}")
                observed = next_observed
        settle_finished_at = clock()
        settle_elapsed_s = settle_finished_at - settle_start if settle_reads else 0.0
        now = clock()
        for name in JOINT_UNITS:
            error = abs(observed.positions[name] - point["goal"][name])
            step_increase = 1.0 if name == "gripper" else 0.25
            if error >= 2.0 and error - previous_errors[name] >= step_increase:
                increasing_counts[name] += 1
            else:
                increasing_counts[name] = 0
            if increasing_counts[name] >= 3:
                raise TrialAbort(f"tracking_error_growing:{name}")
            previous_errors[name] = error
        for name in ARM_LIMITS_DEG:
            requested_change = point["goal"][name] - last_goal[name]
            measured_change = observed.positions[name] - last_actual[name]
            if abs(requested_change) >= 1.0 and requested_change * measured_change < -1.0:
                raise TrialAbort(f"encoder_direction_opposite:{name}")
            error = abs(observed.positions[name] - point["goal"][name])
            if error >= 2.5 and abs(measured_change) < 0.1:
                lag_started[name] = now if lag_started[name] is None else lag_started[name]
                if now - lag_started[name] >= 0.75:
                    raise TrialAbort(f"tracking_lag:{name}")
            else:
                lag_started[name] = None
        last_actual = dict(observed.positions)
        last_goal = point["goal"]
        completed_at = clock()
        if on_timing is not None:
            on_timing({
                "target_index": target_index,
                "seq": point["seq"],
                "nominal_interval_s": nominal_interval_s,
                "nominal_deadline_monotonic": nominal_deadline,
                "scheduled_send_monotonic": deadline,
                "send_call_monotonic": sent_at,
                "send_return_monotonic": send_returned_at,
                "feedback_read_started_monotonic": feedback_read_started_at,
                "first_feedback_read_ended_monotonic": first_feedback_read_ended_at,
                "first_feedback_monotonic": first_feedback_at,
                "final_feedback_read_started_monotonic": final_feedback_read_started_at,
                "final_feedback_read_ended_monotonic": final_feedback_read_ended_at,
                "final_feedback_monotonic": observed.received_monotonic,
                "settle_reads": settle_reads,
                "settle_start_monotonic": settle_start if settle_reads else None,
                "settle_end_monotonic": settle_finished_at if settle_reads else None,
                "settle_elapsed_s": settle_elapsed_s,
                "command_feedback_abs_error": {
                    name: abs(sent[name] - observed.positions[name]) for name in JOINT_UNITS
                },
                "minimum_arm_urdf_margin_deg": min(
                    min(observed.positions[name] - low, high - observed.positions[name])
                    for name, (low, high) in ARM_LIMITS_DEG.items()
                ),
                "guard_state": "PASS",
                "cumulative_delay_s": completed_at - nominal_deadline,
            })
        # Rebase only after this target's fresh feedback and all safety checks.
        # The next target retains its original scaled interval from this point;
        # no missed deadline is skipped or sent in a catch-up burst.
        schedule_rebase_s = clock() - nominal_deadline
    return sent_count


def read_stillness(transport, *, window_s: float = 1.0,
                   clock=time.monotonic, sleep=time.sleep) -> bool:
    """Encoder stillness only; physical scene must also be checked by a person."""
    first = transport.read_feedback().positions
    start = clock()
    while clock() - start < window_s:
        sleep(0.1)
        later = transport.read_feedback().positions
        if any(abs(later[name] - first[name]) > (2.0 if name == "gripper" else 1.0)
               for name in JOINT_UNITS):
            return False
    return True


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--time-scale", type=float, default=2.0)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-scope", choices=["safe_start_to_approach"])
    args = parser.parse_args(argv)
    points = load_segment(args.candidate)
    if not math.isfinite(args.time_scale) or args.time_scale < 2.0:
        parser.error("time scale must be at least 2")
    print(f"segment=seq {START_SEQ}..{APPROACH_SEQ}, goals={len(points)-1}, "
          f"duration_s={points[-1]['elapsed_from_safe_start_s']*args.time_scale:.1f}")
    margin = min(min(positions[name] - low, high - positions[name])
                 for point in points for positions in (point["goal"], point["observed_feedback"])
                 for name, (low, high) in ARM_LIMITS_DEG.items())
    print(f"ORDER_AND_TIMESTAMP=PASS first_t=0.000 last_t="
          f"{points[-1]['elapsed_from_safe_start_s']:.6f} "
          f"URDF=PASS min_arm_margin_deg={margin:.3f}")
    if not args.live:
        print("DRY_RUN: no port opened; no send_action")
        return 0
    if args.confirm_scope != "safe_start_to_approach":
        parser.error("live trial requires explicit approved scope")
    print("LIVE: C must be removed; LeLab motor tasks must be idle; site stop ready.")
    if input("Type RUN APPROACH to begin the separately approved trial: ") != "RUN APPROACH":
        print("NOT_RUN")
        return 2
    transport = SO101FollowerTransport.open_live(
        ExclusiveFollowerLease(SystemBusProbe()), approval_confirmed=True)
    sent = 0
    outcome = 1
    try:
        sent = run_timed_segment(points, transport, time_scale=args.time_scale,
                                 progress=lambda count, seq: print(
                                     f"sent={count} last_seq={seq}", flush=True),
                                 on_feedback=lambda point, command, feedback: print(
                                     json.dumps({"seq": point["seq"],
                                                 "command": command,
                                                 "feedback": feedback.positions,
                                                 "feedback_monotonic": feedback.received_monotonic,
                                                 "command_feedback_abs_error": {
                                                     name: abs(command[name] - feedback.positions[name])
                                                     for name in JOINT_UNITS
                                                 },
                                                 "guard_state": "PENDING_CHECK"},
                                                separators=(",", ":")), flush=True),
                                 on_timing=lambda timing: print(
                                     json.dumps({"timing": timing}, separators=(",", ":")),
                                     flush=True),
                                 on_sample_timing=lambda sample_timing: print(
                                     json.dumps({"sample_timing": sample_timing},
                                                separators=(",", ":")), flush=True))
        print(f"TRANSMISSION_ENDED goals={sent}; arm stopped=NOT_VERIFIED")
        outcome = 0
    except (KeyboardInterrupt, Exception) as error:
        print(f"ABORT: {type(error).__name__}: {error}",
              file=sys.stderr)
        print("Command production stopped; physical arm stop=NOT_VERIFIED. "
              "Keep clear, inspect the arm and use the site stop procedure.", file=sys.stderr)
    finally:
        transport.stop_commands()
        try:
            still = read_stillness(transport)
            print(f"encoder_stillness={'PASS' if still else 'NOT_VERIFIED'}")
            answer = input("Site check: arm stopped and scene safe? Type STOPPED: ")
            if not still or answer != "STOPPED":
                print("physical_stop=NOT_VERIFIED")
                outcome = 1
            else:
                print("physical_stop=FEEDBACK_AND_HUMAN_CONFIRMED")
        except (Exception, KeyboardInterrupt) as error:
            print(f"physical_stop=NOT_VERIFIED ({type(error).__name__})", file=sys.stderr)
            outcome = 1
        finally:
            # No torque change. A failed check never becomes a success report.
            transport.robot.bus.disconnect(disable_torque=False)
            transport.lease.release()
    return outcome


if __name__ == "__main__":
    raise SystemExit(main())
