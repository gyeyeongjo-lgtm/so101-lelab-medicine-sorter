#!/usr/bin/env python3
"""Dry-run fixed-slot bottle recognition plus per-command basket assignment.

This consumes a saved one-class YOLO status frame. It does not train a model,
open a camera, or connect to any robot-control endpoint. Slot and size ranges
are provisional for the unchanged 640x480 camera/layout only.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path


DEFAULT_SLOTS = Path(__file__).resolve().parents[1] / "configs/medicine_fixed_slots.example.json"
COLORS = {"red": 4, "green": 5, "blue": 6}
COLOR_WORDS = {
    "빨간색": "red", "빨강": "red", "초록색": "green", "초록": "green",
    "파란색": "blue", "파랑": "blue",
}
COMMAND = re.compile(
    r"(?P<label>[ABC])\s*(?:를|을|도)?\s*"
    r"(?P<color>빨간색|빨강|초록색|초록|파란색|파랑)"
    r"\s*(?:바구니|박스)?",
    re.IGNORECASE,
)


def parse_command(command: str) -> dict[str, str]:
    """Accept explicit clauses such as 'A를 빨간색, B도 빨간색 박스'."""
    if not isinstance(command, str) or not command.strip():
        raise ValueError("empty_command")
    matches = list(COMMAND.finditer(command))
    if not matches or COMMAND.sub("", command).strip(" \t\r\n,;，；"):
        raise ValueError("unsupported_command_words")
    assignments = {}
    for match in matches:
        label = match.group("label").upper()
        if label in assignments:
            raise ValueError("duplicate_bottle_assignment")
        assignments[label] = COLOR_WORDS[match.group("color")]
    return assignments


def validate_slots(raw: object) -> dict[str, dict]:
    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise ValueError("unsupported_slot_config")
    if raw.get("image_size_px") != [640, 480] or raw.get("provisional") is not True:
        raise ValueError("slot_config_must_be_provisional_640x480")
    slots = raw.get("slots")
    if not isinstance(slots, dict) or set(slots) != {"A", "B", "C"}:
        raise ValueError("slot_config_requires_A_B_C")
    ranges = []
    for label, slot in slots.items():
        if not isinstance(slot, dict):
            raise ValueError(f"invalid_slot_{label}")
        for key in ("center_x_px", "box_height_px"):
            bounds = slot.get(key)
            if (not isinstance(bounds, list) or len(bounds) != 2
                    or any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in bounds)
                    or bounds[0] < 0 or bounds[1] <= bounds[0]):
                raise ValueError(f"invalid_{key}_{label}")
        ranges.append((slot["center_x_px"][0], slot["center_x_px"][1], label))
    ranges.sort()
    if any(left[1] >= right[0] for left, right in zip(ranges, ranges[1:])):
        raise ValueError("overlapping_slot_centers")
    return slots


def _blocked(reason: str) -> dict:
    return {"status": "BLOCKED", "reason": reason, "routes": [],
            "robot_enabled": False, "motion_authorized": False,
            "robot_coordinates_included": False}


def decide_fixed_slot_command(snapshot: object, assignments: dict[str, str],
                              slots: dict[str, dict]) -> dict:
    """Identify occupied fixed slots and propose destinations, never motion."""
    if not isinstance(snapshot, dict) or snapshot.get("ok") is not True:
        return _blocked("vision_snapshot_unhealthy")
    if snapshot.get("robot_enabled") is not False:
        return _blocked("vision_source_not_read_only")
    age = snapshot.get("frame_age_s")
    if not isinstance(age, (int, float)) or not math.isfinite(age) or not 0 <= age <= 0.75:
        return _blocked("vision_snapshot_stale")
    if not isinstance(assignments, dict) or not assignments or any(
        label not in slots or color not in COLORS for label, color in assignments.items()
    ):
        return _blocked("invalid_command_assignments")
    table = snapshot.get("table")
    if not isinstance(table, dict) or table.get("ready") is not True:
        return _blocked("reference_markers_incomplete")
    detected_ids = table.get("detected_ids")
    required = {0, 1, 2, 3, *(COLORS[color] for color in assignments.values())}
    if (not isinstance(detected_ids, list)
            or any(type(marker_id) is not int for marker_id in detected_ids)
            or not required.issubset(set(detected_ids))):
        return _blocked("reference_or_target_marker_missing")
    mapping, markers = table.get("basket_mapping"), table.get("basket_markers")
    if not isinstance(mapping, dict) or not isinstance(markers, dict):
        return _blocked("basket_mapping_missing")
    for color in assignments.values():
        marker_id = str(COLORS[color])
        if mapping.get(marker_id) != color or not isinstance(markers.get(marker_id), dict) or markers[marker_id].get("color") != color:
            return _blocked("target_marker_mismatch")
    detections = snapshot.get("detections")
    if not isinstance(detections, list):
        return _blocked("detections_missing")
    occupied = {}
    for detection in detections:
        if not isinstance(detection, dict):
            return _blocked("invalid_detection")
        confidence = detection.get("confidence")
        if not isinstance(confidence, (int, float)) or not math.isfinite(confidence):
            return _blocked("invalid_detection_confidence")
        if confidence < 0.5:
            continue
        box = detection.get("xyxy")
        if (not isinstance(box, list) or len(box) != 4
                or any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in box)
                or box[2] <= box[0] or box[3] <= box[1]):
            return _blocked("invalid_detection_box")
        center_x, height = (box[0] + box[2]) / 2, box[3] - box[1]
        matches = [label for label, slot in slots.items()
                   if slot["center_x_px"][0] <= center_x <= slot["center_x_px"][1]]
        if len(matches) != 1:
            return _blocked("bottle_outside_fixed_slots")
        label = matches[0]
        height_range = slots[label]["box_height_px"]
        if not height_range[0] <= height <= height_range[1]:
            return _blocked("bottle_size_outside_slot_guard")
        if label in occupied:
            return _blocked("multiple_bottle_boxes_in_slot")
        occupied[label] = detection
    if any(label not in occupied for label in assignments):
        return _blocked("requested_bottle_missing")
    routes = [{"bottle_label": label, "source_slot": label,
               "target_color": color, "target_marker_id": COLORS[color],
               "detection_confidence": occupied[label]["confidence"]}
              for label, color in assignments.items()]
    return {"status": "DRY_RUN_ROUTE_ONLY", "reason": None,
            "frame_sequence": snapshot.get("sequence"), "routes": routes,
            "fixed_layout_provisional": True,
            "warning": "No grasp coordinates, path, collision clearance, or basket capacity is verified",
            "robot_enabled": False, "motion_authorized": False,
            "robot_coordinates_included": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--command", required=True)
    parser.add_argument("--slots", type=Path, default=DEFAULT_SLOTS)
    args = parser.parse_args()
    try:
        assignments = parse_command(args.command)
        slots = validate_slots(json.loads(args.slots.read_text(encoding="utf-8")))
        snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
        result = decide_fixed_slot_command(snapshot, assignments, slots)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.exit(2, f"dry run not started: {error}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "DRY_RUN_ROUTE_ONLY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
