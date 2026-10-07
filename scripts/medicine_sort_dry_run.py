#!/usr/bin/env python3
"""Select a basket marker for a human-verified A/B/C label, without robot I/O.

The current one-class bottle detector cannot identify A/B/C. This tool only
checks an externally verified label against a saved vision-status snapshot.
It never emits coordinates, motor commands, or motion authorization.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


DEFAULT_RULES = Path(__file__).resolve().parents[1] / "configs/medicine_sort_rules.example.json"


def validate_rules(raw: object) -> dict[str, dict]:
    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise ValueError("unsupported sorting rules schema")
    if raw.get("label_source") != "human_verified_only":
        raise ValueError("A/B/C labels must be human verified")
    rules = raw.get("rules")
    if not isinstance(rules, dict) or set(rules) != {"A", "B", "C"}:
        raise ValueError("sorting rules must define A, B, and C exactly")
    expected_colors = {4: "red", 5: "green", 6: "blue"}
    destinations = []
    for label, rule in rules.items():
        if not isinstance(rule, dict):
            raise ValueError(f"invalid rule for {label}")
        marker_id = rule.get("basket_id")
        if type(marker_id) is not int or marker_id not in expected_colors:
            raise ValueError(f"invalid basket ID for {label}")
        if rule.get("color") != expected_colors[marker_id]:
            raise ValueError(f"basket color/ID mismatch for {label}")
        destinations.append(marker_id)
    if len(set(destinations)) != 3:
        raise ValueError("A/B/C must have distinct basket IDs")
    return rules


def decide(snapshot: object, verified_label: str, rules: dict[str, dict]) -> dict:
    result = {
        "status": "BLOCKED",
        "reason": None,
        "verified_label": verified_label,
        "target_marker_id": None,
        "target_color": None,
        "robot_enabled": False,
        "motion_authorized": False,
        "robot_coordinates_included": False,
    }
    if verified_label not in rules:
        result["reason"] = "unknown_or_unverified_label"
        return result
    if not isinstance(snapshot, dict) or snapshot.get("ok") is not True:
        result["reason"] = "vision_snapshot_unhealthy"
        return result
    if snapshot.get("robot_enabled") is not False:
        result["reason"] = "vision_source_not_read_only"
        return result
    age = snapshot.get("frame_age_s")
    if not isinstance(age, (int, float)) or not math.isfinite(age) or not 0 <= age <= 0.75:
        result["reason"] = "vision_snapshot_stale"
        return result
    table = snapshot.get("table")
    if not isinstance(table, dict) or table.get("ready") is not True:
        result["reason"] = "reference_markers_incomplete"
        return result
    if type(table.get("detections_inside_pickup_roi")) is not int or table["detections_inside_pickup_roi"] != 1:
        result["reason"] = "pickup_candidate_not_unique"
        return result
    rule = rules[verified_label]
    marker_id = str(rule["basket_id"])
    mapping = table.get("basket_mapping")
    baskets = table.get("basket_markers")
    if (not isinstance(mapping, dict) or not isinstance(baskets, dict)
            or mapping.get(marker_id) != rule["color"]
            or not isinstance(baskets.get(marker_id), dict)
            or baskets[marker_id].get("color") != rule["color"]):
        result["reason"] = "target_marker_missing_or_mismatched"
        return result
    result.update(status="DRY_RUN_ROUTE_ONLY", target_marker_id=rule["basket_id"],
                  target_color=rule["color"])
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True,
                        help="saved JSON from the read-only medicine vision status")
    parser.add_argument("--verified-label", required=True,
                        help="human-verified container label A, B, or C")
    parser.add_argument("--rules", type=Path, default=DEFAULT_RULES)
    args = parser.parse_args()
    try:
        rules = validate_rules(json.loads(args.rules.read_text(encoding="utf-8")))
        snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
        result = decide(snapshot, args.verified_label, rules)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.exit(2, f"dry run not started: {error}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "DRY_RUN_ROUTE_ONLY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
