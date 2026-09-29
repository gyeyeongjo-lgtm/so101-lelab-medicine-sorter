import sys
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from review_bootstrap_labels import prepare_review


class ReviewBootstrapLabelsTests(unittest.TestCase):
    def test_prepares_full_bottle_label_and_preserves_history(self):
        original = {
            "selected_candidate": {"bbox_xywh": [191, 105, 16, 13]},
            "yolo_pseudo_label": {
                "class_id": 0,
                "bbox_margin_px": 2,
                "normalized_xywh": [0.621875, 0.46458333, 0.0625, 0.07083333],
                "review_required": True,
            },
        }
        label, updated = prepare_review(
            original, [191, 105, 16, 25], "RGB shows lower body", 320, 240
        )
        self.assertEqual(label, "0 0.62187500 0.48958333 0.06250000 0.12083333\n")
        self.assertEqual(updated["yolo_pseudo_label"]["reviewed_bbox_xywh"], [191, 105, 16, 25])
        self.assertEqual(len(updated["label_review_history"]), 1)
        self.assertNotIn("label_review_history", original)

    def test_rejects_bbox_that_cuts_selected_component(self):
        original = {
            "selected_candidate": {"bbox_xywh": [191, 105, 16, 13]},
            "yolo_pseudo_label": {"class_id": 0, "bbox_margin_px": 2},
        }
        with self.assertRaises(ValueError):
            prepare_review(original, [191, 105, 16, 12], "too short", 320, 240)


if __name__ == "__main__":
    unittest.main()
