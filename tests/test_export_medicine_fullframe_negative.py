import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from export_medicine_fullframe_negative import eligible_body_boxes


class NegativeExportTests(unittest.TestCase):
    def test_finds_target_sized_body_in_workspace(self):
        self.assertEqual(
            eligible_body_boxes([[332, 232, 21, 19, 318]]),
            [[332, 232, 21, 19]],
        )

    def test_ignores_large_background_and_outside_component(self):
        self.assertEqual(
            eligible_body_boxes([[170, 100, 100, 200, 8000], [100, 240, 20, 20, 300]]),
            [],
        )


if __name__ == "__main__":
    unittest.main()
