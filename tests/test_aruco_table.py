import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


aruco_table = load_script("aruco_table", "scripts/aruco_table.py")
marker_generator = load_script("generate_aruco_markers", "scripts/generate_aruco_markers.py")


class ArucoConfigTests(unittest.TestCase):
    def write_config(self, data):
        temporary = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump(data, temporary)
        temporary.close()
        self.addCleanup(Path(temporary.name).unlink, missing_ok=True)
        return Path(temporary.name)

    def valid_config(self):
        return {
            "dictionary": "DICT_4X4_50",
            "marker_size_mm": 70,
            "marker_centers_mm": {
                "0": [0, 0],
                "1": [600, 0],
                "2": [600, 400],
                "3": [0, 400],
            },
            "camera": {"device": "/dev/video0", "width": 640, "height": 480, "fps": 30},
            "calibration_file": None,
        }

    def test_loads_and_normalizes_valid_config(self):
        config = aruco_table.load_config(self.write_config(self.valid_config()))
        self.assertEqual(config["marker_centers_mm"][2], (600.0, 400.0))
        self.assertEqual(config["marker_size_mm"], 70.0)

    def test_rejects_collinear_marker_coordinates(self):
        data = self.valid_config()
        data["marker_centers_mm"] = {
            "0": [0, 0],
            "1": [100, 0],
            "2": [200, 0],
            "3": [300, 0],
        }
        with self.assertRaisesRegex(ValueError, "collinear"):
            aruco_table.load_config(self.write_config(data))

    def test_rejects_duplicate_marker_coordinates(self):
        data = self.valid_config()
        data["marker_centers_mm"]["3"] = [0, 0]
        with self.assertRaisesRegex(ValueError, "unique"):
            aruco_table.load_config(self.write_config(data))

    def test_normalizes_linux_video_device_to_camera_index(self):
        self.assertEqual(aruco_table.normalize_camera_source("/dev/video4"), 4)
        self.assertEqual(aruco_table.normalize_camera_source("4"), 4)

    def test_camera_fourcc_defaults_to_mjpg(self):
        config = aruco_table.load_config(self.write_config(self.valid_config()))
        self.assertEqual(config["camera"]["fourcc"], "MJPG")

    def test_rejects_invalid_camera_fourcc(self):
        data = self.valid_config()
        data["camera"]["fourcc"] = "YUY"
        with self.assertRaisesRegex(ValueError, "fourcc"):
            aruco_table.load_config(self.write_config(data))


class MarkerSvgTests(unittest.TestCase):
    def test_svg_preserves_requested_physical_width(self):
        svg = marker_generator.marker_svg(
            [[True, False], [False, True]], 70.0, "DICT_4X4_50 ID 0"
        )
        self.assertIn('width="70mm"', svg)
        self.assertIn("DICT_4X4_50 ID 0", svg)
        self.assertEqual(svg.count('fill="black"'), 2)


if __name__ == "__main__":
    unittest.main()
