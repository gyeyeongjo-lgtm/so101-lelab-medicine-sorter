import unittest

import numpy as np

from scripts.pivot_tcp_table_capture import SEQUENCE, reflected_rigid_fit


def captures(repeat_shift=(0.0, 0.0), holdout_shift=(0.0, 0.0)):
    table = {
        "P1": [300.0, 400.0], "P2": [50.0, 380.0], "P3": [60.0, 200.0],
        "P4": [150.0, 280.0], "H1": [250.0, 340.0],
    }
    theta = np.deg2rad(17.0)
    rotation = np.array([[np.cos(theta), -np.sin(theta)],
                         [np.sin(theta), np.cos(theta)]])
    translation = np.array([270.0, -580.0])
    result = {}
    for name in SEQUENCE:
        mark = name.removeprefix("Repeat_")
        reflected = np.array([-table[mark][0], table[mark][1]])
        robot = rotation @ reflected + translation
        if name == "H1":
            robot += holdout_shift
        if name.startswith("Repeat_"):
            robot += repeat_shift
        result[name] = {
            "table_xy_mm": table[mark],
            "corrected_physical_tcp_xyz_mm": [robot[0], robot[1], 50.0],
        }
    return result


class PivotTcpTableCaptureTests(unittest.TestCase):
    def test_fit_reserves_all_three_independent_points(self):
        result = reflected_rigid_fit(captures())
        self.assertEqual(result["status"], "CALIBRATION_CANDIDATE_SINGLE_DIGIT")
        self.assertLess(result["fit_rms_mm"], 1e-9)
        self.assertLess(result["h1_error_mm"], 1e-9)
        self.assertLess(result["repeat_p1_direct_error_mm"], 1e-9)
        self.assertLess(result["repeat_p3_transform_error_mm"], 1e-9)
        self.assertEqual(result["independent_points"], ["H1", "Repeat_P1", "Repeat_P3"])
        self.assertFalse(result["robot_enabled"])

    def test_large_repeat_is_rejected(self):
        result = reflected_rigid_fit(captures(repeat_shift=(12.0, 0.0)))
        self.assertEqual(result["status"], "REJECTED_FIT_OR_REPEAT")
        self.assertAlmostEqual(result["repeat_p1_direct_error_mm"], 12.0)

    def test_requires_complete_new_session(self):
        data = captures()
        del data["Repeat_P3"]
        with self.assertRaisesRegex(ValueError, "seven"):
            reflected_rigid_fit(data)


if __name__ == "__main__":
    unittest.main()
