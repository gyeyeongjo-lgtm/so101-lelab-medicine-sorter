import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from audit_medicine_roi_capture import screen_body_bbox


class RoiScreenTests(unittest.TestCase):
    def test_holds_missing_body(self):
        self.assertEqual(screen_body_bbox(None, (174, 110), 8), "hold_no_purple_body")

    def test_rejects_bottom_or_right_edge(self):
        self.assertEqual(screen_body_bbox((90, 91, 20, 19), (174, 110), 8), "reject_body_at_roi_edge")
        self.assertEqual(screen_body_bbox((155, 50, 19, 20), (174, 110), 8), "reject_body_at_roi_edge")

    def test_never_accepts_automatically(self):
        self.assertEqual(screen_body_bbox((80, 55, 20, 20), (174, 110), 8), "needs_human_review")


if __name__ == "__main__":
    unittest.main()
