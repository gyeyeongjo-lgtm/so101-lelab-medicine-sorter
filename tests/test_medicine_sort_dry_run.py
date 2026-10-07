import json
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from medicine_sort_dry_run import DEFAULT_RULES, decide, validate_rules


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


if __name__ == "__main__":
    unittest.main()
