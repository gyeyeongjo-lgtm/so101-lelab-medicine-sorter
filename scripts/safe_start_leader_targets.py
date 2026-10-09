#!/usr/bin/env python3
"""Offline arithmetic for one fresh LeLab Elbow/Wrist alignment measurement.

No USB or HTTP calls. The user must supply simultaneous fresh start values;
historical +2.945 degrees must not be silently reused as tomorrow's offset.
"""

from __future__ import annotations

import argparse
import json
import math


FOLLOWER_SAFE_START = {
    "shoulder_pan": 11.736263736263735,
    "shoulder_lift": -22.32967032967033,
    "elbow_flex": 32.43956043956044,
    "wrist_flex": 5.538461538461538,
    "wrist_roll": -20.395604395604394,
    "gripper": 3.4456355283307807,
}


def leader_targets(*, leader_elbow: float, follower_elbow: float,
                   leader_flex: float, follower_flex: float) -> dict:
    values = (leader_elbow, follower_elbow, leader_flex, follower_flex)
    if any(not math.isfinite(value) for value in values):
        raise ValueError("nonfinite_alignment")
    elbow_offset = follower_elbow - leader_elbow
    wrist_offset = follower_flex - leader_flex
    if abs(elbow_offset) > 3.5 or abs(wrist_offset) > 15.0:
        raise ValueError("temporary_alignment_cap_exceeded")
    leader = dict(FOLLOWER_SAFE_START)
    leader["elbow_flex"] -= elbow_offset
    leader["wrist_flex"] -= wrist_offset
    return {"leader_target": leader,
            "follower_target": dict(FOLLOWER_SAFE_START),
            "teleop_compensation": {"elbow_flex": elbow_offset,
                                    "wrist_flex": wrist_offset},
            "source": "one_fresh_start_alignment_only",
            "motion_authorized": False}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("leader-elbow", "follower-elbow", "leader-flex", "follower-flex"):
        parser.add_argument(f"--{name}", type=float, required=True)
    args = parser.parse_args(argv)
    try:
        result = leader_targets(leader_elbow=args.leader_elbow,
                                follower_elbow=args.follower_elbow,
                                leader_flex=args.leader_flex,
                                follower_flex=args.follower_flex)
    except ValueError as error:
        parser.exit(2, f"TARGETS_BLOCKED: {error}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
