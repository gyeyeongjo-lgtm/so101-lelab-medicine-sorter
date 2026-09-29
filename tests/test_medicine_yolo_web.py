import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from medicine_yolo_web import INDEX_HTML, inside_roi, project_table_xy, read_exact, video_index

import numpy as np


class MedicineYoloWebTests(unittest.TestCase):
    def test_page_is_read_only(self):
        self.assertIn("ROBOT DISABLED", INDEX_HTML)
        self.assertIn("/stream.mjpg", INDEX_HTML)
        self.assertIn("/angled.mjpg", INDEX_HTML)
        self.assertNotIn("move-arm", INDEX_HTML)
        self.assertNotIn("start-inference", INDEX_HTML)
        self.assertNotIn("stop-teleoperation", INDEX_HTML)

    def test_read_exact_combines_short_reads(self):
        class ShortStream:
            def __init__(self):
                self.parts = [b"ab", b"c", b"def"]

            def read(self, _size):
                return self.parts.pop(0) if self.parts else b""

        self.assertEqual(read_exact(ShortStream(), 6), b"abcdef")

    def test_read_exact_returns_empty_on_partial_eof(self):
        class PartialStream:
            def __init__(self):
                self.done = False

            def read(self, _size):
                if self.done:
                    return b""
                self.done = True
                return b"abc"

        self.assertEqual(read_exact(PartialStream(), 6), b"")

    def test_video_index_resolves_video_node(self):
        self.assertEqual(video_index("/dev/video4"), 4)

    def test_table_projection_and_roi_gate(self):
        homography = np.asarray([[2.0, 0.0, -20.0], [0.0, 2.0, -40.0], [0.0, 0.0, 1.0]])
        point = project_table_xy(np, homography, 60.0, 80.0)
        self.assertEqual(point, (100.0, 120.0))
        roi = {"x": (80.0, 220.0), "y": (100.0, 300.0)}
        self.assertTrue(inside_roi(point, roi))
        self.assertFalse(inside_roi((79.9, 120.0), roi))


if __name__ == "__main__":
    unittest.main()
