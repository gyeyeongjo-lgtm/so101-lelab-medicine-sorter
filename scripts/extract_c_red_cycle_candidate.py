#!/usr/bin/env python3
"""Extract an offline-only C→red teleop trace candidate; never open a robot bus.

The result is a numerical reference, not a command stream approved for replay.
Source rows remain untouched. No clipping, interpolation across an invalid
joint sample, or reinterpretation of follower feedback as a sent command.
"""

from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path


ARM = ("shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll")
AXES = (*ARM, "gripper")
MOTOR_TO_URDF = {
    "shoulder_pan": "Rotation", "shoulder_lift": "Pitch", "elbow_flex": "Elbow",
    "wrist_flex": "Wrist_Pitch", "wrist_roll": "Wrist_Roll",
}
KST = timezone(timedelta(hours=9))


def iso_ns(ns: int) -> str:
    return datetime.fromtimestamp(ns / 1e9, KST).isoformat(timespec="microseconds")


def margins(values: dict, limits: dict) -> dict:
    return {
        name: {
            "lower_deg": values[name] - math.degrees(limits[MOTOR_TO_URDF[name]][0]),
            "upper_deg": math.degrees(limits[MOTOR_TO_URDF[name]][1]) - values[name],
        }
        for name in ARM
    }


def min_margin(row: dict, limits: dict) -> float:
    return min(
        value
        for source in ("follower_command", "follower_feedback")
        for item in margins(row[source], limits).values()
        for value in item.values()
    )


def load_trace(root: Path) -> tuple[list[dict], list[dict], dict]:
    manifest = json.loads((root / "manifest.json").read_text())
    digest = hashlib.sha256()
    with (root / "cycles.jsonl").open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != manifest["cycle_sha256"]:
        raise ValueError("cycle SHA-256 differs from manifest")
    rows = [json.loads(line) for line in (root / "cycles.jsonl").open()]
    events = [json.loads(line) for line in (root / "events.jsonl").open()]
    if len(rows) != manifest["cycle_count"] or any(row["seq"] != i for i, row in enumerate(rows)):
        raise ValueError("cycle count or sequence discontinuity")
    if [event["phase"] for event in events] != ["approach", "grasp", "transport", "place", "retreat"]:
        raise ValueError("expected ordered C→red phase markers")
    if not manifest["data_complete"] or manifest["error_count"]:
        raise ValueError("incomplete source trace")
    return rows, events, manifest


def stable_window(
    rows: list[dict], times: list[int], center: int, *,
    duration_s: float, limits: dict, minimum_margin_deg: float,
    gripper_open_at_least: float | None = None,
) -> dict | None:
    half_ns = int(duration_s * 1e9 / 2)
    left = bisect.bisect_left(times, times[center] - half_ns)
    right = bisect.bisect_right(times, times[center] + half_ns)
    selected = rows[left:right]
    if len(selected) < max(50, int(duration_s * 100)):
        return None
    if min(min_margin(row, limits) for row in selected) < minimum_margin_deg:
        return None
    if gripper_open_at_least is not None and any(
        row["follower_feedback"]["gripper"] < gripper_open_at_least for row in selected
    ):
        return None
    ranges = {}
    for source in ("leader_position", "follower_command", "follower_feedback"):
        ranges[source] = {
            axis: max(row[source][axis] for row in selected) - min(row[source][axis] for row in selected)
            for axis in AXES
        }
        if any(value > 0.5 for value in ranges[source].values()):
            return None
    return {
        "center_seq": rows[center]["seq"], "first_seq": selected[0]["seq"],
        "last_seq": selected[-1]["seq"], "duration_s":
        (times[right - 1] - times[left]) / 1e9,
        "sample_count": len(selected), "max_range_by_stream": {
            source: max(value.values()) for source, value in ranges.items()
        },
        "minimum_command_or_feedback_margin_deg": min(min_margin(row, limits) for row in selected),
    }


def latest_stable(
    rows: list[dict], times: list[int], *, earliest_ns: int, latest_ns: int,
    limits: dict, margin_deg: float, gripper_open_at_least: float | None = None,
) -> tuple[int, dict] | None:
    first = bisect.bisect_left(times, earliest_ns)
    last = bisect.bisect_right(times, latest_ns) - 1
    for i in range(last, first - 1, -25):
        window = stable_window(
            rows, times, i, duration_s=1.0, limits=limits,
            minimum_margin_deg=margin_deg, gripper_open_at_least=gripper_open_at_least,
        )
        if window and times[window["first_seq"]] >= earliest_ns and times[window["last_seq"]] <= latest_ns:
            return i, window
    return None


def first_violation(rows: list[dict], limits: dict, source: str, *, after_ns: int,
                    joint: str | None = None) -> int | None:
    for i, row in enumerate(rows):
        if row["started_monotonic_ns"] < after_ns:
            continue
        values = margins(row[source], limits)
        if any(min(item.values()) <= 0 for name, item in values.items()
               if joint is None or name == joint):
            return i
    return None


def sample_detail(rows: list[dict], index: int, limits: dict, first_ns: int, *,
                  bottle_state: str, evidence: str) -> dict:
    row = rows[index]
    change = {}
    for source in ("leader_position", "follower_command", "follower_feedback"):
        prev = rows[max(0, index - 1)][source]
        nxt = rows[min(len(rows) - 1, index + 1)][source]
        change[source] = {
            "arm_max_deg": max(max(abs(row[source][name] - prev[name]),
                                   abs(nxt[name] - row[source][name])) for name in ARM),
            "gripper_max_percentage_points": max(
                abs(row[source]["gripper"] - prev["gripper"]),
                abs(nxt["gripper"] - row[source]["gripper"]),
            ),
        }
    return {
        "seq": row["seq"], "timestamp_kst": iso_ns(row["feedback_read_unix_ns"]),
        "elapsed_from_trace_start_s": (row["feedback_monotonic_ns"] - first_ns) / 1e9,
        "leader_position": row["leader_position"],
        "follower_command": row["follower_command"],
        "follower_feedback": row["follower_feedback"],
        "joint_margins_deg": {
            source: margins(row[source], limits)
            for source in ("follower_command", "follower_feedback")
        },
        "adjacent_sample_max_change": change,
        "bottle_state": bottle_state, "bottle_state_evidence": evidence,
    }


def turns(rows: list[dict], first: int, last: int, tolerances: tuple[float, ...]) -> set[int]:
    result = set()
    for axis, prominence in zip(AXES, (1.0, 1.0, 1.0, 1.0, 1.0, 2.0)):
        direction = 0
        low = high = rows[first]["follower_command"][axis]
        low_i = high_i = first
        for i in range(first + 1, last + 1):
            v = rows[i]["follower_command"][axis]
            if direction == 0:
                if v < low:
                    low, low_i = v, i
                if v > high:
                    high, high_i = v, i
                if v - low >= prominence:
                    result.add(low_i)
                    direction, high, high_i = 1, v, i
                elif high - v >= prominence:
                    result.add(high_i)
                    direction, low, low_i = -1, v, i
            elif direction == 1:
                if v > high:
                    high, high_i = v, i
                elif high - v >= prominence:
                    result.add(high_i)
                    direction, low, low_i = -1, v, i
            else:
                if v < low:
                    low, low_i = v, i
                elif v - low >= prominence:
                    result.add(low_i)
                    direction, high, high_i = 1, v, i
    return {i for i in result if first < i < last}


def rdp_indices(rows: list[dict], times: list[int], forced: set[int],
                tolerance: tuple[float, ...], motion_gap_s: float,
                hold_gap_s: float, max_arm_step_deg: float,
                max_gripper_step_points: float) -> list[int]:
    selected = set(forced)
    anchors = sorted(forced)
    stack = [(a, b) for a, b in zip(anchors, anchors[1:])]
    while stack:
        a, b = stack.pop()
        if b - a <= 1:
            continue
        start = rows[a]["follower_command"]
        end = rows[b]["follower_command"]
        span = times[b] - times[a]
        worst, worst_i = 0.0, None
        for i in range(a + 1, b):
            fraction = (times[i] - times[a]) / span
            values = rows[i]["follower_command"]
            error = max(
                abs(values[axis] - (start[axis] + fraction * (end[axis] - start[axis]))) / tolerance[j]
                for j, axis in enumerate(AXES)
            )
            if error > worst:
                worst, worst_i = error, i
        split = worst_i if worst > 1.0 else None
        if split is None:
            moving = any(abs(end[axis] - start[axis]) > tolerance[j]
                         for j, axis in enumerate(AXES))
            cap_ns = int((motion_gap_s if moving else hold_gap_s) * 1e9)
            if span > cap_ns:
                split = min(b - 1, max(a + 1, bisect.bisect_left(
                    times, times[a] + cap_ns, a + 1, b
                )))
        if split is None and (
            max(abs(end[axis] - start[axis]) for axis in ARM) > max_arm_step_deg
            or abs(end["gripper"] - start["gripper"]) > max_gripper_step_points
        ):
            split = (a + b) // 2
        if split is not None:
            selected.add(split)
            stack.extend(((a, split), (split, b)))
    return sorted(selected)


def interpolation_errors(rows: list[dict], times: list[int], indices: list[int]) -> dict:
    errors = {axis: 0.0 for axis in AXES}
    for a, b in zip(indices, indices[1:]):
        start, end = rows[a]["follower_command"], rows[b]["follower_command"]
        span = times[b] - times[a]
        for i in range(a + 1, b):
            fraction = (times[i] - times[a]) / span
            for axis in AXES:
                reconstructed = start[axis] + fraction * (end[axis] - start[axis])
                errors[axis] = max(errors[axis], abs(rows[i]["follower_command"][axis] - reconstructed))
    return errors


def analyze(root: Path, limit_path: Path, output: Path) -> dict:
    rows, events, manifest = load_trace(root)
    model = json.loads(limit_path.read_text())
    limits = model["joints"]
    times = [row["started_monotonic_ns"] for row in rows]
    if any(a >= b for a, b in zip(times, times[1:])):
        raise ValueError("non-monotonic trace samples")
    event_ns = {event["phase"]: event["monotonic_ns"] for event in events}
    command_cross = first_violation(rows, limits, "follower_command", after_ns=event_ns["place"],
                                    joint="elbow_flex")
    feedback_cross = first_violation(rows, limits, "follower_feedback", after_ns=event_ns["place"],
                                     joint="elbow_flex")
    if command_cross is None or feedback_cross is None:
        raise ValueError("expected observed retreat limit crossing not found")

    start = latest_stable(
        rows, times, earliest_ns=event_ns["approach"] - int(10e9),
        latest_ns=event_ns["approach"] - int(0.5e9),
        limits=limits, margin_deg=20,
    )
    grasp_before = bisect.bisect_left(times, event_ns["transport"]) - 125
    grasp_open = rows[grasp_before]["follower_feedback"]["gripper"]
    end = latest_stable(
        rows, times, earliest_ns=event_ns["retreat"] + int(3e9),
        latest_ns=times[command_cross] - int(0.5e9),
        limits=limits, margin_deg=20, gripper_open_at_least=grasp_open + 10,
    )
    if not start or not end:
        raise ValueError("no qualifying stable start or retreat interval")
    start_i, start_window = start
    end_i, end_window = end
    if not start_i < end_i < command_cross <= feedback_cross:
        raise ValueError("start/end/crossing order invalid")

    preceding = {
        "approach": ("grasp", "C on pickup table; gripper open and noncontact", "human stage confirmation"),
        "grasp": ("transport", "C held and slightly lifted", "human stage confirmation"),
        "transport": ("place", "C held above red basket rim", "human stage confirmation"),
        "place": ("retreat", "C in red basket; gripper opened", "human stage confirmation"),
    }
    key_indices = {"safe_start": start_i, "safe_retreat_end": end_i}
    for name, (next_event, _, _) in preceding.items():
        marker_i = bisect.bisect_left(times, event_ns[next_event])
        # A stable representative in the final second before the next marker.
        key_indices[name] = bisect.bisect_left(times, times[marker_i] - int(0.5e9))
    keypoints = {
        "safe_start": sample_detail(
            rows, start_i, limits, times[0], bottle_state="C at pickup; arm in clear air",
            evidence="human pre-approach confirmation; no synchronized video archive",
        ),
        "safe_retreat_end": sample_detail(
            rows, end_i, limits, times[0], bottle_state="C previously confirmed in red basket; gripper open",
            evidence="human place confirmation; rim clearance at this exact timestamp not video-verified",
        ),
    }
    for name, (_, state, evidence) in preceding.items():
        keypoints[name] = sample_detail(rows, key_indices[name], limits, times[0],
                                        bottle_state=state, evidence=evidence)

    first_i, last_i = start_i, end_i
    source_min_margin = (math.inf, None)
    for row in rows[first_i:last_i + 1]:
        margin = min_margin(row, limits)
        if margin < source_min_margin[0]:
            source_min_margin = (margin, row["seq"])
        if margin <= 0:
            raise ValueError(f"candidate contains URDF violation at seq {row['seq']}")

    reasons: dict[int, set[str]] = defaultdict(set)
    for name, i in key_indices.items():
        reasons[i].add(f"keypoint:{name}")
    for event in events:
        i = bisect.bisect_left(times, event["monotonic_ns"])
        for j, side in ((i - 1, "before"), (i, "after")):
            if first_i <= j <= last_i:
                reasons[j].add(f"event:{event['phase']}:{side}")
    turn_indices = turns(rows, first_i, last_i, (0.5, 0.5, 0.5, 0.5, 0.5, 1.0))
    for i in turn_indices:
        reasons[i].add("prominent_direction_turn")
    gripper_crossings = 0
    for i in range(first_i + 1, last_i + 1):
        before = rows[i - 1]["follower_command"]["gripper"]
        after = rows[i]["follower_command"]["gripper"]
        if any((before < level <= after) or (after < level <= before)
               for level in (10, 20, 30, 40, 50, 60)):
            reasons[i - 1].add("gripper_threshold_before")
            reasons[i].add("gripper_threshold_after")
            gripper_crossings += 1
    reasons[first_i].add("candidate_start")
    reasons[last_i].add("candidate_end")
    forced = set(reasons)

    profiles = {}
    chosen = None
    for label, arm_tol, grip_tol, motion_gap, hold_gap, arm_step, grip_step in (
        ("fine", 0.25, 0.5, 0.2, 1.0, 1.0, 1.0),
        ("balanced", 0.5, 1.0, 0.25, 1.5, 2.0, 2.0),
        ("coarse", 1.0, 2.0, 0.5, 2.0, 4.0, 4.0),
    ):
        tolerances = (arm_tol,) * 5 + (grip_tol,)
        indices = rdp_indices(rows, times, forced, tolerances, motion_gap, hold_gap,
                              arm_step, grip_step)
        errors = interpolation_errors(rows, times, indices)
        if any(errors[axis] > tolerances[i] + 1e-8 for i, axis in enumerate(AXES)):
            raise ValueError(f"{label} interpolation error exceeds tolerance")
        actual_arm_step = max(max(abs(rows[b]["follower_command"][axis] -
                                      rows[a]["follower_command"][axis]) for axis in ARM)
                              for a, b in zip(indices, indices[1:]))
        actual_grip_step = max(abs(rows[b]["follower_command"]["gripper"] -
                                   rows[a]["follower_command"]["gripper"])
                               for a, b in zip(indices, indices[1:]))
        if actual_arm_step > arm_step + 1e-8 or actual_grip_step > grip_step + 1e-8:
            raise ValueError(f"{label} contains excessive adjacent goal step")
        profiles[label] = {
            "waypoint_count": len(indices), "compression_vs_candidate":
            (last_i - first_i + 1) / len(indices),
            "max_command_interpolation_error": errors,
            "arm_tolerance_deg": arm_tol, "gripper_tolerance_percentage_points": grip_tol,
            "max_motion_gap_s": motion_gap, "max_hold_gap_s": hold_gap,
            "max_adjacent_arm_goal_step_deg": actual_arm_step,
            "max_adjacent_gripper_goal_step_points": actual_grip_step,
        }
        if label == "balanced":
            chosen = indices

    tracking = {}
    for axis in AXES:
        errors = sorted(abs(row["follower_command"][axis] - row["follower_feedback"][axis])
                        for row in rows[first_i:last_i + 1])
        tracking[axis] = {"p95": errors[int(0.95 * (len(errors) - 1))], "max": errors[-1]}

    crossing = {}
    for source, i in (("follower_command", command_cross), ("follower_feedback", feedback_cross)):
        timestamp_field = "send_action_return_unix_ns" if source == "follower_command" else "feedback_read_unix_ns"
        crossing[source] = {
            "seq": i, "timestamp_kst": iso_ns(rows[i][timestamp_field]),
            "previous_elbow_deg": rows[i - 1][source]["elbow_flex"],
            "first_over_elbow_deg": rows[i][source]["elbow_flex"],
            "next_elbow_deg": rows[i + 1][source]["elbow_flex"],
            "urdf_upper_deg": math.degrees(limits["Elbow"][1]),
        }

    output.mkdir(parents=True, exist_ok=True)
    trajectory = {
        "status": "OFFLINE_NUMERIC_CANDIDATE_ONLY",
        "motion_authorized": False, "automatic_replay_verified": False,
        "collision_verified": False, "video_clearance_verified": False,
        "source_cycle_sha256": manifest["cycle_sha256"],
        "source_urdf_sha256": model["source_sha256"],
        "goal_source": "follower_command_not_follower_feedback",
        "all_source_command_and_feedback_samples_within_urdf": True,
        "linear_joint_interpolation_within_urdf": True,
        "gripper_percent_not_compared_to_urdf_jaw_radians": True,
        "arm_unit": "degree", "gripper_unit": "percent_0_100",
        "waypoints": [
            {
                "seq": i, "timestamp_kst": iso_ns(rows[i]["send_action_return_unix_ns"]),
                "elapsed_from_safe_start_s": (times[i] - times[first_i]) / 1e9,
                "goal": rows[i]["follower_command"],
                "observed_feedback": rows[i]["follower_feedback"],
                "preserved_anchor_reasons": sorted(reasons.get(i, ())),
            }
            for i in chosen
        ],
    }
    (output / "trajectory_candidate.json").write_text(
        json.dumps(trajectory, ensure_ascii=False, indent=2) + "\n"
    )
    summary = {
        "status": "OFFLINE_NUMERIC_CANDIDATE_ONLY",
        "motion_authorized": False, "automatic_replay_verified": False,
        "collision_verified": False, "video_clearance_verified": False,
        "source_cycle_sha256": manifest["cycle_sha256"],
        "source_urdf_sha256": model["source_sha256"],
        "whole_trace_count": len(rows), "candidate_first_seq": first_i,
        "candidate_last_seq": last_i, "candidate_original_count": last_i - first_i + 1,
        "discarded_after_end_count": len(rows) - last_i - 1,
        "candidate_source_minimum_arm_margin_deg": source_min_margin[0],
        "candidate_source_minimum_arm_margin_seq": source_min_margin[1],
        "all_source_command_and_feedback_samples_within_urdf": True,
        "linear_joint_interpolation_within_urdf": True,
        "gripper_percent_not_compared_to_urdf_jaw_radians": True,
        "crossing": crossing,
        "stable_windows": {"safe_start": start_window, "safe_retreat_end": end_window},
        "keypoints": keypoints, "forced_event_or_turn_count": len(forced),
        "prominent_turn_count": len(turn_indices),
        "gripper_threshold_crossing_count": gripper_crossings,
        "downsampling": profiles,
        "command_feedback_absolute_error": tracking,
        "note": "Human task completion does not prove video clearance at the selected end or safe automated replay.",
    }
    (output / "analysis.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace", required=True, type=Path)
    parser.add_argument("--limits", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = analyze(args.trace, args.limits, args.output)
    print(json.dumps({key: result[key] for key in (
        "status", "candidate_first_seq", "candidate_last_seq", "candidate_original_count",
        "discarded_after_end_count", "crossing", "stable_windows", "downsampling",
    )}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
