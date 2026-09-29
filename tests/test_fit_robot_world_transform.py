import sys
import unittest
from pathlib import Path

import numpy as np


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from fit_robot_world_transform import build_result, fit_rigid_transform, validate_pairs


class RobotWorldTransformTests(unittest.TestCase):
    def test_recovers_known_planar_rigid_transform(self):
        world = np.array([
            [0.0, 0.0, 0.0], [200.0, 0.0, 0.0], [200.0, 100.0, 0.0],
            [0.0, 100.0, 0.0], [80.0, 30.0, 0.0], [130.0, 70.0, 0.0],
        ])
        angle = np.deg2rad(25.0)
        rotation = np.array([
            [np.cos(angle), -np.sin(angle), 0.0],
            [np.sin(angle), np.cos(angle), 0.0],
            [0.0, 0.0, 1.0],
        ])
        translation = np.array([120.0, -35.0, 18.0])
        base = (rotation @ world.T).T + translation
        transform, residuals = fit_rigid_transform(world, base)
        np.testing.assert_allclose(transform[:3, :3], rotation, atol=1e-10)
        np.testing.assert_allclose(transform[:3, 3], translation, atol=1e-10)
        np.testing.assert_allclose(residuals, 0.0, atol=1e-10)

    def test_build_result_stays_motion_disabled(self):
        document = {
            "unit": "mm",
            "convention": "T_B_W transforms a point from World into Robot Base",
            "pairs": [
                {"name": "a", "world_mm": [0, 0, 0], "robot_base_mm": [10, 20, 30]},
                {"name": "b", "world_mm": [100, 0, 0], "robot_base_mm": [110, 20, 30]},
                {"name": "c", "world_mm": [100, 100, 0], "robot_base_mm": [110, 120, 30]},
                {"name": "d", "world_mm": [0, 100, 0], "robot_base_mm": [10, 120, 30]},
            ],
        }
        result = build_result(document)
        self.assertEqual(result["status"], "FIT_ONLY_REQUIRES_DRY_RUN_VALIDATION")
        self.assertFalse(result["robot_enabled"])
        self.assertLess(result["rmse_mm"], 1e-10)

    def test_rejects_collinear_or_missing_pairs(self):
        document = {
            "unit": "mm",
            "convention": "T_B_W transforms a point from World into Robot Base",
            "pairs": [
                {"name": str(i), "world_mm": [i, 0, 0], "robot_base_mm": [i, 0, 0]}
                for i in range(4)
            ],
        }
        with self.assertRaises(ValueError):
            validate_pairs(document)
        document["pairs"][3]["robot_base_mm"] = None
        with self.assertRaises(ValueError):
            validate_pairs(document)


if __name__ == "__main__":
    unittest.main()
