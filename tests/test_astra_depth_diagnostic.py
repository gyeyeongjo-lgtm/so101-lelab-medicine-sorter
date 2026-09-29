import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "astra_depth_diagnostic.py"
SPEC = importlib.util.spec_from_file_location("astra_depth_diagnostic", MODULE_PATH)
diagnostic = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(diagnostic)


class MedianDepthRoiTests(unittest.TestCase):
    def test_filters_zero_and_out_of_range_values(self):
        depth = np.asarray(
            [
                [0, 0, 0, 0, 0],
                [0, 900, 910, 5000, 0],
                [0, 890, 905, 915, 0],
                [0, 880, 900, 920, 0],
                [0, 0, 0, 0, 0],
            ],
            dtype=np.uint16,
        )
        value, valid, total = diagnostic.median_depth_roi(depth, 2, 2, 1, 200, 4000)
        self.assertEqual(value, 902.5)
        self.assertEqual(valid, 8)
        self.assertEqual(total, 9)

    def test_clips_roi_at_image_edge(self):
        depth = np.full((4, 4), 750, dtype=np.uint16)
        value, valid, total = diagnostic.median_depth_roi(depth, 0, 0, 2, 200, 4000)
        self.assertEqual(value, 750.0)
        self.assertEqual(valid, 9)
        self.assertEqual(total, 9)

    def test_reports_missing_depth(self):
        depth = np.zeros((3, 3), dtype=np.uint16)
        value, valid, total = diagnostic.median_depth_roi(depth, 1, 1, 1, 200, 4000)
        self.assertIsNone(value)
        self.assertEqual(valid, 0)
        self.assertEqual(total, 9)


class FrameHeaderTests(unittest.TestCase):
    def test_skips_openni_startup_warning(self):
        expected = diagnostic.HEADER.pack(b"RGBD", 640, 480, 123, 456)
        stream = io.BytesIO(b"OpenNI warning\n" + expected + b"payload")
        self.assertEqual(diagnostic.read_frame_header(stream), expected)

    def test_returns_none_without_protocol_magic(self):
        self.assertIsNone(diagnostic.read_frame_header(io.BytesIO(b"warning only")))


class CoordinateTests(unittest.TestCase):
    def test_deprojects_registered_pixel_with_zero_distortion(self):
        matrix = np.asarray(
            [[500.0, 0.0, 320.0], [0.0, 500.0, 240.0], [0.0, 0.0, 1.0]]
        )
        point = diagnostic.deproject_registered_pixel(
            np, 370.0, 215.0, 1000.0, matrix
        )
        np.testing.assert_allclose(point, [100.0, -50.0, 1000.0])

    def test_inverts_rigid_transform_and_transforms_point(self):
        transform = np.eye(4)
        transform[:3, 3] = [10.0, -20.0, 30.0]
        inverse = diagnostic.invert_transform(np, transform)
        point = diagnostic.transform_point(np, transform, [1.0, 2.0, 3.0])
        restored = diagnostic.transform_point(np, inverse, point)
        np.testing.assert_allclose(restored, [1.0, 2.0, 3.0])

    def test_estimates_no_scale_rigid_transform(self):
        source = np.asarray(
            [[0.0, 0.0, 0.0], [100.0, 0.0, 0.0], [100.0, 80.0, 0.0], [0.0, 80.0, 0.0]]
        )
        rotation = np.asarray(
            [[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]]
        )
        translation = np.asarray([20.0, -30.0, 700.0])
        target = (rotation @ source.T).T + translation
        fit = diagnostic.estimate_rigid_transform(np, source, target)
        np.testing.assert_allclose(fit["transform"][:3, :3], rotation, atol=1e-10)
        np.testing.assert_allclose(fit["transform"][:3, 3], translation, atol=1e-10)
        self.assertAlmostEqual(fit["rms_mm"], 0.0, places=10)

    def test_depth_world_transform_reports_pairs_and_planarity(self):
        world = {
            0: (0.0, 0.0, 0.0),
            1: (100.0, 0.0, 0.0),
            2: (100.0, 80.0, 0.0),
            3: (0.0, 80.0, 0.0),
        }
        camera = {
            marker_id: np.asarray(point) + np.asarray([10.0, 20.0, 700.0])
            for marker_id, point in world.items()
        }
        pose = diagnostic.estimate_depth_world_transform(np, camera, world)
        self.assertIsNotNone(pose)
        assert pose is not None
        self.assertAlmostEqual(pose["fit_rms_mm"], 0.0, places=10)
        self.assertAlmostEqual(pose["plane_rms_mm"], 0.0, places=10)
        self.assertAlmostEqual(pose["pair_distances"]["0-2"]["delta_mm"], 0.0)
        restored = diagnostic.transform_point(np, pose["T_W_C"], camera[2])
        np.testing.assert_allclose(restored, world[2], atol=1e-10)

    def test_depth_plane_height_is_positive_toward_camera(self):
        world = {
            0: (0.0, 0.0, 0.0),
            1: (100.0, 0.0, 0.0),
            2: (100.0, 80.0, 0.0),
            3: (0.0, 80.0, 0.0),
        }
        camera = {
            marker_id: np.asarray(point) + np.asarray([10.0, 20.0, 700.0])
            for marker_id, point in world.items()
        }
        pose = diagnostic.estimate_depth_world_transform(np, camera, world)
        assert pose is not None
        self.assertLess(float(pose["plane_normal_toward_camera"] @ pose["plane_origin_camera_mm"]), 0)
        height = diagnostic.height_above_depth_plane(
            np,
            [60.0, 60.0, 650.0],
            pose["plane_origin_camera_mm"],
            pose["plane_normal_toward_camera"],
        )
        self.assertAlmostEqual(height, 50.0, places=10)

    def test_table_homography_projects_marker_centers(self):
        homography = np.asarray(
            [[2.0, 0.0, -20.0], [0.0, 2.0, -40.0], [0.0, 0.0, 1.0]]
        )

        class FakeCV2:
            def findHomography(self, image_points, table_points, method):
                return homography, np.ones((len(image_points), 1), dtype=np.uint8)

        world = {
            0: (0.0, 0.0, 0.0),
            1: (100.0, 0.0, 0.0),
            2: (100.0, 80.0, 0.0),
            3: (0.0, 80.0, 0.0),
        }
        centers = [(10.0, 20.0), (60.0, 20.0), (60.0, 60.0), (10.0, 60.0)]
        corners = [
            np.asarray([[[u - 1, v - 1], [u + 1, v - 1], [u + 1, v + 1], [u - 1, v + 1]]])
            for u, v in centers
        ]
        ids = np.asarray([[0], [1], [2], [3]], dtype=np.int32)
        result = diagnostic.estimate_table_homography(FakeCV2(), np, corners, ids, world)
        assert result is not None
        self.assertAlmostEqual(result["reference_rms_mm"], 0.0, places=10)
        np.testing.assert_allclose(
            diagnostic.project_table_xy(np, result["H_table_image"], 35.0, 40.0),
            [50.0, 40.0],
        )

    def test_scales_camera_matrix_for_low_bandwidth_mode(self):
        matrix = np.asarray(
            [[600.0, 0.0, 300.0], [0.0, 580.0, 250.0], [0.0, 0.0, 1.0]]
        )
        scaled = diagnostic.scale_camera_matrix(np, matrix, (640, 480), (320, 240))
        np.testing.assert_allclose(
            scaled,
            [[300.0, 0.0, 150.0], [0.0, 290.0, 125.0], [0.0, 0.0, 1.0]],
        )

    def test_loads_reference_centers_with_implicit_zero_z(self):
        payload = {
            "markers": {
                "reference_centers_mm": {
                    "0": [0, 0],
                    "1": [1, 0, 0],
                    "2": [1, 1],
                    "3": [0, 1, 0],
                }
            }
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workspace.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            centers = diagnostic.load_reference_centers(path)
        self.assertEqual(centers[0], (0.0, 0.0, 0.0))
        self.assertEqual(centers[2], (1.0, 1.0, 0.0))

    def test_loads_default_and_per_id_marker_sizes(self):
        payload = {
            "markers": {
                "marker_size_mm": 70,
                "marker_size_by_id_mm": {"0": 75},
            }
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workspace.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            default_size, overrides = diagnostic.load_marker_sizes(path)
        self.assertEqual(default_size, 70.0)
        self.assertEqual(overrides, {0: 75.0})

    def test_single_marker_pnp_uses_requested_marker_size(self):
        class FakeCV2:
            SOLVEPNP_ITERATIVE = 0
            SOLVEPNP_IPPE_SQUARE = 7

            def __init__(self):
                self.object_points = None

            def solvePnP(self, object_points, image_points, matrix, distortion, flags):
                self.object_points = object_points
                return True, np.zeros((3, 1)), np.asarray([[0.0], [0.0], [810.0]])

        fake = FakeCV2()
        z_mm = diagnostic.estimate_single_marker_pnp_z(
            fake,
            np,
            np.asarray([[[10, 10], [20, 10], [20, 20], [10, 20]]]),
            75.0,
            np.eye(3),
            np.zeros((5, 1)),
        )
        self.assertEqual(z_mm, 810.0)
        np.testing.assert_allclose(
            fake.object_points,
            [[-37.5, 37.5, 0], [37.5, 37.5, 0], [37.5, -37.5, 0], [-37.5, -37.5, 0]],
        )


if __name__ == "__main__":
    unittest.main()
