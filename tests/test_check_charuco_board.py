from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "check_charuco_board.py"
SPEC = importlib.util.spec_from_file_location("check_charuco_board", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CameraSourceTests(unittest.TestCase):
    def test_normalizes_linux_video_device_to_index(self) -> None:
        self.assertEqual(MODULE.normalize_camera_source("/dev/video4"), 4)
        self.assertEqual(MODULE.normalize_camera_source("4"), 4)
        self.assertEqual(MODULE.normalize_camera_source(4), 4)


if __name__ == "__main__":
    unittest.main()
