import json
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from medicine_sort_dry_run import DEFAULT_RULES, decide, decide_manual_pixel, validate_rules


class MedicineSortDryRunTests(unittest.TestCase):
    def setUp(self):
        self.rules = validate_rules(json.loads(DEFAULT_RULES.read_text(encoding="utf-8")))
        self.snapshot = {
            "ok": True,
            "frame_age_s": 0.12,
            "robot_enabled": False,
            "table": {
                "ready": True,
                "detections_inside_pickup_roi": 1,
                "basket_mapping": {"4": "red", "5": "green", "6": "blue"},
                "basket_markers": {
                    "4": {"color": "red"}, "5": {"color": "green"}, "6": {"color": "blue"},
                },
            },
        }

    def test_a_b_c_map_to_marker_ids_not_screen_positions(self):
        for label, marker_id, color in (("A", 6, "blue"), ("B", 5, "green"), ("C", 4, "red")):
            result = decide(self.snapshot, label, self.rules)
            self.assertEqual(result["status"], "DRY_RUN_ROUTE_ONLY")
            self.assertEqual((result["target_marker_id"], result["target_color"]), (marker_id, color))
            self.assertFalse(result["robot_enabled"])
            self.assertFalse(result["motion_authorized"])
            self.assertFalse(result["robot_coordinates_included"])

    def test_unknown_label_has_no_target(self):
        result = decide(self.snapshot, "unknown", self.rules)
        self.assertEqual(result["reason"], "unknown_or_unverified_label")
        self.assertIsNone(result["target_marker_id"])

    def test_missing_reference_or_target_marker_has_no_target(self):
        self.snapshot["table"]["ready"] = False
        self.assertEqual(decide(self.snapshot, "A", self.rules)["reason"], "reference_markers_incomplete")
        self.snapshot["table"]["ready"] = True
        del self.snapshot["table"]["basket_markers"]["6"]
        self.assertEqual(decide(self.snapshot, "A", self.rules)["reason"], "target_marker_missing_or_mismatched")

    def test_stale_or_ambiguous_snapshot_has_no_target(self):
        self.snapshot["robot_enabled"] = True
        self.assertEqual(decide(self.snapshot, "B", self.rules)["reason"], "vision_source_not_read_only")
        self.snapshot["robot_enabled"] = False
        self.snapshot["frame_age_s"] = 1.0
        self.assertEqual(decide(self.snapshot, "B", self.rules)["reason"], "vision_snapshot_stale")
        self.snapshot["frame_age_s"] = 0.1
        self.snapshot["table"]["detections_inside_pickup_roi"] = 2
        self.assertEqual(decide(self.snapshot, "B", self.rules)["reason"], "pickup_candidate_not_unique")

    def test_bad_rules_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "color/ID mismatch"):
            validate_rules({"schema_version": 1, "label_source": "human_verified_only", "rules": {
                **self.rules, "A": {"basket_id": 6, "color": "red"},
            }})

    def test_manual_pixel_selects_overlapping_duplicate_boxes(self):
        self.snapshot.update(sequence=42, detections=[
            {"xyxy": [308, 222, 333, 258], "confidence": 0.89},
            {"xyxy": [308, 222, 345, 256], "confidence": 0.26},
        ])
        self.snapshot["table"].update(required_ids=[0, 1, 2, 3],
                                      detected_ids=[0, 1, 2, 3, 4, 5, 6])
        result = decide_manual_pixel(self.snapshot, "B", (320, 240), 42, self.rules)
        self.assertEqual(result["status"], "DRY_RUN_ROUTE_ONLY")
        self.assertEqual(result["selected_detection_count"], 2)
        self.assertEqual((result["target_marker_id"], result["target_color"]), (5, "green"))
        self.assertFalse(result["motion_authorized"])
        self.assertFalse(result["robot_coordinates_included"])

    def test_manual_pixel_rejects_wrong_frame_or_point(self):
        self.snapshot.update(sequence=42, detections=[{"xyxy": [10, 10, 30, 30], "confidence": 0.8}])
        self.snapshot["table"].update(required_ids=[0, 1, 2, 3],
                                      detected_ids=[0, 1, 2, 3, 4, 5, 6])
        self.assertEqual(decide_manual_pixel(self.snapshot, "A", (20, 20), 41, self.rules)["reason"],
                         "frame_sequence_mismatch")
        self.assertEqual(decide_manual_pixel(self.snapshot, "A", (50, 50), 42, self.rules)["reason"],
                         "clicked_point_not_in_bottle_detection")
        del self.snapshot["table"]["basket_markers"]["6"]
        self.assertEqual(decide_manual_pixel(self.snapshot, "A", (20, 20), 42, self.rules)["reason"],
                         "target_marker_missing_or_mismatched")


if __name__ == "__main__":
    unittest.main()
