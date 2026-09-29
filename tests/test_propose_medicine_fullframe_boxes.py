import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from propose_medicine_fullframe_boxes import propose_bbox, select_body


class FullFrameProposalTests(unittest.TestCase):
    def test_selects_one_workspace_body(self):
        stats = [[170, 100, 100, 200, 8000], [332, 232, 21, 19, 318]]
        self.assertEqual(select_body(stats), [332, 232, 21, 19])

    def test_rejects_ambiguous_or_missing_body(self):
        with self.assertRaises(ValueError):
            select_body([])
        with self.assertRaises(ValueError):
            select_body([[332, 232, 21, 19, 318], [400, 240, 20, 20, 300]])

    def test_expands_to_full_bottle_box(self):
        self.assertEqual(propose_bbox([332, 232, 21, 19]), [327, 214, 31, 40])


if __name__ == "__main__":
    unittest.main()
