import unittest

import numpy as np

from scripts.fit_fixed_point_tcp import fit_fixed_point
from scripts.urdf_forward_kinematics import axis_rotation


def samples(holdout_shift=None, holdout_jaw=0.08):
    tip = np.array([10.0, -8.0, -120.0])
    fixed = np.array([70.0, -250.0, 40.0])
    angles = [(0, 0, 0), (0.3, 0, 0), (0, 0.35, 0), (0, 0, -0.4), (0.2, -0.25, 0.3)]
    result = []
    for index, (rx, ry, rz) in enumerate(angles):
        rotation = (axis_rotation(np.array([1, 0, 0]), rx)
                    @ axis_rotation(np.array([0, 1, 0]), ry)
                    @ axis_rotation(np.array([0, 0, 1]), rz))
        origin = fixed - rotation @ tip
        if index == 4 and holdout_shift is not None:
            origin = origin + np.asarray(holdout_shift)
        result.append({"name": f"pose{index+1}", "point": "P5", "rotation": rotation,
                       "origin_mm": origin, "jaw_rad": holdout_jaw if index == 4 else 0.08})
    return result


class FixedPointTcpTests(unittest.TestCase):
    def test_exact_pivot_numeric_pass_still_blocks_motion(self):
        result = fit_fixed_point(samples())
        self.assertEqual(result["status"], "NUMERIC_PASS_PHYSICAL_QA_PENDING")
        self.assertEqual(result["rank"], 6)
        self.assertAlmostEqual(result["holdout_error_mm"], 0.0, places=8)
        self.assertFalse(result["robot_enabled"])
        self.assertFalse(result["motion_authorized"])

    def test_jaw_change_is_reported_but_link_fk_must_model_it(self):
        result = fit_fixed_point(samples(holdout_jaw=0.05))
        self.assertAlmostEqual(result["holdout_jaw_delta_rad"], 0.03)
        self.assertNotIn("holdout_jaw_mismatch", result["rejection_reasons"])

    def test_holdout_error_is_rejected(self):
        result = fit_fixed_point(samples(holdout_shift=[12, 0, 0]))
        self.assertIn("holdout_error_above_limit", result["rejection_reasons"])

    def test_identical_orientations_are_unobservable(self):
        data = samples()
        for sample in data:
            sample["rotation"] = np.eye(3)
        result = fit_fixed_point(data)
        self.assertIn("pivot_rank_below_6", result["rejection_reasons"])

    def test_requires_independent_holdout(self):
        with self.assertRaises(ValueError):
            fit_fixed_point(samples()[:4])


if __name__ == "__main__":
    unittest.main()
