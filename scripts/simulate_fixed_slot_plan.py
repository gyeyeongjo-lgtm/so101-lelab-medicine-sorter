#!/usr/bin/env python3
"""Pure fixed-slot command planner and event simulator; no robot-control imports.

The route catalog is evidence metadata, not executable joint positions. Even a
successful simulation never grants motion authority or claims a physical pick.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

try:
    from scripts.medicine_fixed_slot_command import (
        COLORS, DEFAULT_SLOTS, decide_fixed_slot_command, parse_command, validate_slots,
    )
except ModuleNotFoundError:  # Direct script execution from the repository root.
    from medicine_fixed_slot_command import (
        COLORS, DEFAULT_SLOTS, decide_fixed_slot_command, parse_command, validate_slots,
    )


PROOF_KEYS = ("grasp_verified", "placement_verified", "retreat_verified")


def _blocked(reason: str, tasks: list[dict] | None = None) -> dict:
    return {"status": "BLOCKED", "reason": reason, "tasks": tasks or [],
            "simulation_only": True, "robot_enabled": False, "motion_authorized": False}


def _catalog_routes(catalog: object, layout_id: str) -> dict[tuple[str, str, int], dict]:
    if (not isinstance(catalog, dict) or catalog.get("schema_version") != 1
            or catalog.get("layout_id") != layout_id or not isinstance(catalog.get("routes"), list)):
        raise ValueError("invalid_or_mismatched_route_catalog")
    routes = {}
    for route in catalog["routes"]:
        if not isinstance(route, dict):
            raise ValueError("invalid_route_record")
        label, color = route.get("bottle_label"), route.get("target_color")
        conditions = route.get("occupancy_conditions")
        if (label not in {"A", "B", "C"} or color not in COLORS
                or not isinstance(conditions, list) or not conditions):
            raise ValueError("invalid_route_key")
        for condition in conditions:
            if not isinstance(condition, dict):
                raise ValueError("invalid_occupancy_condition")
            occupancy = condition.get("occupancy_before")
            if type(occupancy) is not int or occupancy < 0:
                raise ValueError("invalid_occupancy_condition")
            key = (label, color, occupancy)
            if key in routes:
                raise ValueError("duplicate_route_key")
            routes[key] = (route, condition)
    return routes


def prepare_plan(command: str, snapshot: object, slots: dict[str, dict],
                 catalog: object, initial_occupancy: object) -> dict:
    """Build an ordered simulation plan; all routes must have full-cycle evidence."""
    assignments = parse_command(command)
    decision = decide_fixed_slot_command(snapshot, assignments, slots)
    if decision["status"] != "DRY_RUN_ROUTE_ONLY":
        return _blocked(decision["reason"])
    if (not isinstance(snapshot, dict) or not isinstance(snapshot.get("layout_id"), str)
            or not snapshot["layout_id"]):
        return _blocked("layout_id_unverified")
    try:
        routes = _catalog_routes(catalog, snapshot["layout_id"])
    except ValueError as error:
        return _blocked(str(error))
    if (not isinstance(initial_occupancy, dict) or set(initial_occupancy) != set(COLORS)
            or any(type(value) is not int or value < 0
                   for value in initial_occupancy.values())):
        return _blocked("basket_occupancy_unverified")

    occupancy = initial_occupancy.copy()
    tasks = []
    missing = False
    for proposed in decision["routes"]:
        label, color = proposed["bottle_label"], proposed["target_color"]
        before = occupancy[color]
        match = routes.get((label, color, before))
        route, condition = match if match is not None else (None, None)
        verified = (route is not None and route.get("validated_full_cycle") is True
                    and isinstance(route.get("route_id"), str) and bool(route["route_id"])
                    and isinstance(route.get("evidence_ref"), str) and bool(route["evidence_ref"])
                    and condition.get("clearance_verified") is True
                    and condition.get("capacity_verified") is True
                    and isinstance(condition.get("evidence_ref"), str)
                    and bool(condition["evidence_ref"]))
        tasks.append({"bottle_label": label, "source_slot": label,
                      "target_color": color, "target_marker_id": COLORS[color],
                      "basket_occupancy_before": before,
                      "route_id": route["route_id"] if verified else None,
                      "status": "READY" if verified else "BLOCKED_UNVERIFIED_ROUTE"})
        missing |= not verified
        occupancy[color] += 1
    if missing:
        return _blocked("unverified_route_or_basket_occupancy", tasks)
    return {"status": "READY", "reason": None, "tasks": tasks,
            "frame_sequence": decision["frame_sequence"],
            "layout_id": snapshot["layout_id"],
            "initial_occupancy": initial_occupancy.copy(),
            "simulation_only": True, "robot_enabled": False,
            "motion_authorized": False}


def simulate_events(plan: dict, events: list[dict]) -> dict:
    """Apply synthetic outcomes sequentially, stopping on any unverified result."""
    result = copy.deepcopy(plan)
    if not isinstance(events, list) or any(not isinstance(event, dict) for event in events):
        raise ValueError("invalid_simulation_events")
    result.setdefault("history", [])
    result["events_consumed"] = 0
    if result["status"] not in {"READY", "RUNNING"}:
        return result
    for event in events:
        task = next((item for item in result["tasks"] if item["status"] == "RUNNING"), None)
        if task is None:
            task = next((item for item in result["tasks"] if item["status"] == "READY"), None)
            if task is None:
                raise ValueError("extra_simulation_events")
            task["status"] = "RUNNING"
            result["status"] = "RUNNING"
            result["history"].append({"bottle_label": task["bottle_label"],
                                      "status": "RUNNING"})
        elif event.get("outcome") == "start":
            raise ValueError("task_already_running")
        result["events_consumed"] += 1
        outcome = event.get("outcome")
        if outcome == "start":
            continue
        if outcome == "completed":
            if all(event.get(key) is True for key in PROOF_KEYS):
                task["status"] = "SUCCEEDED"
            else:
                task["status"] = "UNVERIFIED"
                result["status"] = "USER_CONFIRMATION_REQUIRED"
                result["reason"] = "pick_place_or_retreat_not_verified"
        elif outcome in {"failure", "timeout"}:
            task["status"] = "FAILED"
            result["status"] = "FAILED"
            result["reason"] = outcome
        elif outcome == "stop":
            task["status"] = "STOPPED"
            result["status"] = "STOPPED"
            result["reason"] = "stop_requested"
        else:
            raise ValueError("invalid_simulation_outcome")
        result["history"].append({"bottle_label": task["bottle_label"],
                                  "status": task["status"]})
        if task["status"] != "SUCCEEDED":
            break
    if result["tasks"] and all(task["status"] == "SUCCEEDED" for task in result["tasks"]):
        result["status"] = "SUCCEEDED"
    result["simulation_only"] = True
    result["robot_enabled"] = False
    result["motion_authorized"] = False
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--command", required=True)
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--occupancy", required=True, type=Path)
    parser.add_argument("--slots", default=DEFAULT_SLOTS, type=Path)
    parser.add_argument("--events", type=Path, help="Synthetic outcomes only; never robot observations")
    args = parser.parse_args()
    try:
        slots = validate_slots(json.loads(args.slots.read_text(encoding="utf-8")))
        snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
        catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
        occupancy = json.loads(args.occupancy.read_text(encoding="utf-8"))
        plan = prepare_plan(args.command, snapshot, slots, catalog, occupancy)
        result = (simulate_events(plan, json.loads(args.events.read_text(encoding="utf-8")))
                  if args.events else plan)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
        parser.exit(2, f"simulation not started: {error}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] in {"READY", "RUNNING", "SUCCEEDED"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
