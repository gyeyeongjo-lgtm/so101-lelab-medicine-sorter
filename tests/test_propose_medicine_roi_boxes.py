import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from propose_medicine_roi_boxes import propose_bbox


class BoxProposalTests(unittest.TestCase):
    def test_expands_body_for_cap_and_base(self):
        self.assertEqual(propose_bbox([76, 62, 21, 19]), [71, 44, 31, 40])

    def test_rejects_box_crossing_roi(self):
        with self.assertRaises(ValueError):
            propose_bbox([155, 68, 19, 19])


if __name__ == "__main__":
    unittest.main()
