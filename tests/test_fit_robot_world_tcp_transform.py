import importlib.util
import math
import unittest
from pathlib import Path

import numpy as np


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "fit_robot_world_tcp_transform.py"
SPEC = importlib.util.spec_from_file_location("fit_robot_world_tcp_transform", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def rotation(axis, angle):
    vector = np.asarray(axis, dtype=float)
    vector /= np.linalg.norm(vector)
    return MODULE.rotation_exp(vector * angle)


class JointTcpFitTests(unittest.TestCase):
    def synthetic_document(self):
        world = np.array(
            [
                [0.0, 0.0, 0.0],
                [200.0, 0.0, 0.0],
                [200.0, 150.0, 0.0],
                [0.0, 150.0, 0.0],
                [100.0, 50.0, 0.0],
                [80.0, 120.0, 0.0],
            ]
        )
        world_rotation = rotation([0.2, -0.3, 0.7], 0.8)
        translation = np.array([120.0, -250.0, 90.0])
        tcp_offset = np.array([12.0, -8.0, 65.0])
        link_rotations = [
            rotation([1, 0, 0], 0.0),
            rotation([0, 1, 0], 0.3),
            rotation([0, 0, 1], -0.5),
            rotation([1, 1, 0], 0.45),
            rotation([1, 0, 1], -0.35),
            rotation([0, 1, 1], 0.55),
        ]
        records = []
        for index, (point, link_rotation) in enumerate(zip(world, link_rotations), 1):
            tcp_base = world_rotation @ point + translation
            link_origin = tcp_base - link_rotation @ tcp_offset
            records.append(
                {
                    "name": f"p{index}",
                    "world_mm": point.tolist(),
                    "gripper_link_origin_mm": link_origin.tolist(),
                    "gripper_link_rotation": link_rotation.tolist(),
                }
            )
        return {
            "unit": "mm",
            "convention": "T_B_W transforms a point from World into Robot Base",
            "pairs": records,
        }, world_rotation, translation, tcp_offset

    def test_recovers_noise_free_transform_and_tcp(self):
        document, expected_rotation, expected_translation, expected_tcp = self.synthetic_document()
        result = MODULE.build_result(
            document,
            {
                "max_rmse_mm": 0.01,
                "max_error_mm": 0.02,
                "max_condition_number": 10000.0,
                "max_tcp_offset_mm": 200.0,
            },
        )
        self.assertLess(result["rmse_mm"], 1e-5)
        self.assertTrue(np.allclose(np.asarray(result["T_B_W"])[:3, :3], expected_rotation, atol=1e-6))
        self.assertTrue(np.allclose(np.asarray(result["T_B_W"])[:3, 3], expected_translation, atol=1e-5))
        self.assertTrue(np.allclose(result["tcp_offset_gripper_link_mm"], expected_tcp, atol=1e-5))

    def test_rejects_high_residual(self):
        document, _, _, _ = self.synthetic_document()
        document["pairs"][-1]["gripper_link_origin_mm"][0] += 30.0
        result = MODULE.build_result(
            document,
            {
                "max_rmse_mm": 1.0,
                "max_error_mm": 2.0,
                "max_condition_number": 10000.0,
                "max_tcp_offset_mm": 200.0,
            },
        )
        self.assertEqual(result["status"], "REJECTED_NEEDS_MORE_OR_BETTER_TEACH_SAMPLES")
        self.assertIn("rmse_above_limit", result["rejection_reasons"])

    def test_optional_pair_selection(self):
        document, _, _, _ = self.synthetic_document()
        document["pairs"].append(
            {
                "name": "excluded_bad_pair",
                "world_mm": [100.0, 100.0, 0.0],
                "gripper_link_origin_mm": [999.0, 999.0, 999.0],
                "gripper_link_rotation": np.eye(3).tolist(),
            }
        )
        document["fit_pair_names"] = [f"p{index}" for index in range(1, 7)]
        result = MODULE.build_result(
            document,
            {
                "max_rmse_mm": 0.01,
                "max_error_mm": 0.02,
                "max_condition_number": 10000.0,
                "max_tcp_offset_mm": 200.0,
            },
        )
        self.assertEqual(result["source_pairs"], 6)
        self.assertNotIn("excluded_bad_pair", result["source_pair_names"])
        self.assertLess(result["rmse_mm"], 1e-5)

    def test_rotation_exp_is_proper_rotation(self):
        value = MODULE.rotation_exp(np.array([0.2, -0.4, 0.1]))
        self.assertTrue(np.allclose(value.T @ value, np.eye(3), atol=1e-10))
        self.assertTrue(math.isclose(float(np.linalg.det(value)), 1.0, abs_tol=1e-10))


if __name__ == "__main__":
    unittest.main()
