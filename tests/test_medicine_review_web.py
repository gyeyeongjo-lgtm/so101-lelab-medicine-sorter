import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from medicine_review_web import MedicineReviewStore, eligible_bodies, proposed_bbox, yolo_label


class MedicineReviewWebTests(unittest.TestCase):
    def test_filters_component_stats(self):
        stats = [
            [100, 220, 20, 20, 400],
            [370, 240, 20, 20, 400],
            [10, 10, 3, 3, 9],
        ]
        self.assertEqual(eligible_bodies(stats), [[100, 220, 20, 20], [370, 240, 20, 20]])

    def test_bbox_and_label(self):
        box = proposed_bbox([370, 240, 20, 20])
        self.assertEqual(box, [365, 222, 30, 41])
        self.assertEqual(yolo_label(box), "0 0.59375000 0.50520833 0.04687500 0.08541667\n")

    def test_blocked_item_cannot_be_approved(self):
        with tempfile.TemporaryDirectory() as directory:
            store = MedicineReviewStore(Path(directory))
            stem = "blocked_001"
            (store.root / "images" / f"{stem}.png").write_bytes(b"image")
            (store.root / "metadata" / f"{stem}.json").write_text(json.dumps({
                "stem": stem, "status": "blocked", "expected": "positive",
                "bbox_xywh_640x480": None, "training_ready": False,
            }), encoding="utf-8")
            with self.assertRaises(ValueError):
                store.decide(stem, "approve", "")
            result = store.decide(stem, "exclude", "invalid capture")
            self.assertEqual(result["status"], "excluded")


if __name__ == "__main__":
    unittest.main()
