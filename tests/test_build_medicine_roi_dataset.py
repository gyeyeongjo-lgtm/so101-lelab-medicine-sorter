import sys
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_medicine_roi_dataset import transform_label


class RoiLabelTests(unittest.TestCase):
    def test_transforms_positive_label(self):
        label = transform_label(
            "0 0.48125000 0.48958333 0.06250000 0.12083333",
            (320, 240),
            (128, 85, 215, 140),
        )
        self.assertEqual(label, "0 0.29885057 0.59090908 0.22988506 0.52727271\n")

    def test_keeps_roi_negative_empty(self):
        self.assertEqual(transform_label("", (320, 240), (128, 85, 215, 140)), "")

    def test_rejects_clipped_positive(self):
        with self.assertRaises(ValueError):
            transform_label("0 0.95 0.5 0.1 0.1", (320, 240), (128, 85, 215, 140))


if __name__ == "__main__":
    unittest.main()
