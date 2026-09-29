import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from merge_medicine_fullframe_candidates import label_kind


class MergeCandidateTests(unittest.TestCase):
    def test_classifies_empty_and_positive_labels(self):
        self.assertEqual(label_kind(""), "negative")
        self.assertEqual(label_kind("0 0.5 0.5 0.1 0.2\n"), "positive")

    def test_rejects_invalid_label(self):
        with self.assertRaises(ValueError):
            label_kind("1 0.5 0.5 0.1 0.2")
        with self.assertRaises(ValueError):
            label_kind("0 1.2 0.5 0.1 0.2")


if __name__ == "__main__":
    unittest.main()
