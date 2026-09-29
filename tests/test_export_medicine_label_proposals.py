import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from export_medicine_label_proposals import bbox_to_label, prefixed_stem


class ProvisionalLabelTests(unittest.TestCase):
    def test_converts_box_to_yolo(self):
        self.assertEqual(
            bbox_to_label([71, 44, 31, 40]),
            "0 0.49712644 0.58181818 0.17816092 0.36363636\n",
        )

    def test_rejects_out_of_bounds_and_non_integer(self):
        with self.assertRaises(ValueError):
            bbox_to_label([160, 80, 20, 20])
        with self.assertRaises(ValueError):
            bbox_to_label([1, 2, 3.0, 4])

    def test_adds_safe_stem_prefix(self):
        self.assertEqual(
            prefixed_stem("newpose_002_", "candidate_001"),
            "newpose_002_candidate_001",
        )
        with self.assertRaises(ValueError):
            prefixed_stem("../escape/", "candidate_001")


if __name__ == "__main__":
    unittest.main()
