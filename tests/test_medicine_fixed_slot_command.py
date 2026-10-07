import json
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from medicine_fixed_slot_command import (DEFAULT_SLOTS, decide_fixed_slot_command,
                                         parse_command, validate_slots)


class FixedSlotCommandTests(unittest.TestCase):
    def setUp(self):
        self.slots = validate_slots(json.loads(DEFAULT_SLOTS.read_text(encoding="utf-8")))
        self.snapshot = {
            "ok": True, "robot_enabled": False, "frame_age_s": 0.1, "sequence": 42,
            "table": {
                "ready": True, "detected_ids": [0, 1, 2, 3, 4, 5, 6],
                "basket_mapping": {"4": "red", "5": "green", "6": "blue"},
                "basket_markers": {"4": {"color": "red"}, "5": {"color": "green"},
                                   "6": {"color": "blue"}},
            },
            "detections": [
                {"confidence": 0.9, "xyxy": [300, 221, 340, 258]},
                {"confidence": 0.9, "xyxy": [361, 216, 391, 255]},
                {"confidence": 0.9, "xyxy": [422, 203, 458, 255]},
            ],
        }

    def test_example_allows_two_types_to_one_basket(self):
        assignments = parse_command("A를 빨간색, B도 빨간색 박스")
        self.assertEqual(assignments, {"A": "red", "B": "red"})
        result = decide_fixed_slot_command(self.snapshot, assignments, self.slots)
        self.assertEqual(result["status"], "DRY_RUN_ROUTE_ONLY")
        self.assertEqual([r["target_marker_id"] for r in result["routes"]], [4, 4])
        self.assertFalse(result["robot_enabled"])
        self.assertFalse(result["motion_authorized"])
        self.assertFalse(result["robot_coordinates_included"])

    def test_other_colors_and_subset(self):
        result = decide_fixed_slot_command(self.snapshot,
                                           parse_command("C를 초록색; A를 파란색"), self.slots)
        self.assertEqual([(r["bottle_label"], r["target_marker_id"])
                          for r in result["routes"]], [("C", 5), ("A", 6)])

    def test_rejects_ambiguous_or_unsupported_text(self):
        for command in ("", "A를 빨강, A를 파랑", "A를 보라색", "A를 빨강 B는 아무데나"):
            with self.assertRaises(ValueError):
                parse_command(command)

    def test_missing_bottle_or_marker_blocks(self):
        self.snapshot["detections"] = self.snapshot["detections"][:1]
        self.assertEqual(decide_fixed_slot_command(self.snapshot, {"A": "red"}, self.slots)["reason"],
                         "requested_bottle_missing")
        self.snapshot["detections"] = self.snapshot["detections"][:1]
        self.snapshot["table"]["detected_ids"].remove(4)
        self.assertEqual(decide_fixed_slot_command(self.snapshot, {"C": "red"}, self.slots)["reason"],
                         "reference_or_target_marker_missing")

    def test_stale_duplicate_or_wrong_size_blocks(self):
        self.snapshot["frame_age_s"] = 1.0
        self.assertEqual(decide_fixed_slot_command(self.snapshot, {"A": "blue"}, self.slots)["reason"],
                         "vision_snapshot_stale")
        self.snapshot["frame_age_s"] = 0.1
        self.snapshot["detections"].append({"confidence": 0.8, "xyxy": [423, 204, 459, 255]})
        self.assertEqual(decide_fixed_slot_command(self.snapshot, {"A": "blue"}, self.slots)["reason"],
                         "multiple_bottle_boxes_in_slot")
        self.snapshot["detections"].pop()
        self.snapshot["detections"][2]["xyxy"] = [423, 215, 459, 255]
        self.assertEqual(decide_fixed_slot_command(self.snapshot, {"A": "blue"}, self.slots)["reason"],
                         "bottle_size_outside_slot_guard")

    def test_overlapping_slot_config_rejected(self):
        raw = json.loads(DEFAULT_SLOTS.read_text(encoding="utf-8"))
        raw["slots"]["B"]["center_x_px"] = [330, 405]
        with self.assertRaisesRegex(ValueError, "overlapping"):
            validate_slots(raw)

    def test_malformed_status_blocks_without_crashing(self):
        self.snapshot["table"]["detected_ids"] = [0, 1, 2, 3, [4]]
        self.assertEqual(decide_fixed_slot_command(self.snapshot, {"A": "red"}, self.slots)["reason"],
                         "reference_or_target_marker_missing")
        self.snapshot["table"]["detected_ids"] = [0, 1, 2, 3, 4, 5, 6]
        self.snapshot["detections"][0]["confidence"] = "high"
        self.assertEqual(decide_fixed_slot_command(self.snapshot, {"A": "red"}, self.slots)["reason"],
                         "invalid_detection_confidence")


if __name__ == "__main__":
    unittest.main()
