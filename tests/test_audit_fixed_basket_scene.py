import unittest
from pathlib import Path

from scripts.audit_fixed_basket_scene import compare_measurements


def scene(id5=(382.0, 346.0), bbox=(347, 258, 73, 102)):
    return {"marker_centers_px": {0: [517.0, 432.0], 1: [224.0, 435.0],
                                  2: [260.0, 249.0], 3: [482.0, 229.0],
                                  4: [316.0, 347.0], 5: list(id5),
                                  6: [458.0, 342.0]},
            "body_bboxes_by_id_candidate": {
                "4": [278, 262, 68, 95],
                "5": list(bbox) if bbox is not None else None,
                "6": [410, 257, 77, 120],
            }}


class FixedBasketSceneTests(unittest.TestCase):
    def test_matching_images_are_diagnostic_only(self):
        result = compare_measurements(scene(), scene(id5=(382.25, 346.0)))
        self.assertEqual(result["status"], "VISUAL_LAYOUT_MATCH_DIAGNOSTIC")
        self.assertTrue(result["visual_layout_match_diagnostic"])
        self.assertEqual(set(result["basket_marker_drift_px"]), {"4", "5", "6"})
        self.assertFalse(result["basket_pose_authorized"])
        self.assertFalse(result["motion_authorized"])

    def test_moved_basket_does_not_match(self):
        result = compare_measurements(scene(), scene(id5=(391.0, 346.0), bbox=(356, 258, 73, 102)))
        self.assertEqual(result["status"], "VISUAL_LAYOUT_CHANGED")
        self.assertFalse(result["visual_layout_match_diagnostic"])

    def test_missing_marker_or_body_is_indeterminate(self):
        current = scene(bbox=None)
        current["marker_centers_px"].pop(5)
        result = compare_measurements(scene(), current)
        self.assertEqual(result["status"], "INDETERMINATE")
        self.assertEqual(result["missing_marker_ids"], [5])
        self.assertFalse(result["motion_authorized"])

    def test_body_missing_keeps_marker_only_diagnostic(self):
        result = compare_measurements(scene(), scene(bbox=None))
        self.assertEqual(result["status"], "MARKERS_MATCH_BODY_UNVERIFIED")
        self.assertEqual(result["missing_body_candidate_ids"], [5])
        self.assertTrue(result["marker_layout_match_diagnostic"])
        self.assertFalse(result["visual_layout_match_diagnostic"])
        self.assertFalse(result["motion_authorized"])

    def test_missing_other_basket_marker_is_indeterminate(self):
        current = scene()
        current["marker_centers_px"].pop(6)
        result = compare_measurements(scene(), current)
        self.assertEqual(result["missing_marker_ids"], [6])
        self.assertEqual(result["status"], "INDETERMINATE")

    def test_previous_overlapping_layout_is_rejected(self):
        previous = scene()
        previous["marker_centers_px"][4] = [97.0, 411.0]
        previous["marker_centers_px"][6] = [105.0, 329.0]
        previous["body_bboxes_by_id_candidate"]["4"] = None
        previous["body_bboxes_by_id_candidate"]["6"] = None
        result = compare_measurements(scene(), previous)
        self.assertEqual(result["status"], "MARKER_LAYOUT_CHANGED")
        self.assertFalse(result["basket_pose_authorized"])

    def test_source_has_no_control_route(self):
        source = (Path(__file__).resolve().parents[1] / "scripts" /
                  "audit_fixed_basket_scene.py").read_text()
        for forbidden in ("/move-arm", "/stop-teleoperation", "serial.Serial", "Goal_Position"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
