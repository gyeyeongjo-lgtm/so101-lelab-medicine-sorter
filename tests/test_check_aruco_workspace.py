from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "check_aruco_workspace.py"
SPEC = importlib.util.spec_from_file_location("check_aruco_workspace", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ParseIdsTests(unittest.TestCase):
    def test_accepts_comma_separated_and_repeated_ids(self) -> None:
        self.assertEqual(MODULE.parse_ids(["0,1", "2", "3,3"]), [0, 1, 2, 3])

    def test_rejects_out_of_dictionary_range(self) -> None:
        with self.assertRaises(ValueError):
            MODULE.parse_ids(["50"])

    def test_rejects_empty_ids(self) -> None:
        with self.assertRaises(ValueError):
            MODULE.parse_ids([""])

    def test_normalizes_linux_video_device_to_camera_index(self) -> None:
        self.assertEqual(MODULE.normalize_camera_source("/dev/video4"), 4)
        self.assertEqual(MODULE.normalize_camera_source("4"), 4)
