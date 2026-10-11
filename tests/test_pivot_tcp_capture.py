import math
import tempfile
import time
import unittest
from pathlib import Path

import numpy as np

from scripts.pivot_tcp_capture import settled_joint_snapshot, solve_pivot
from scripts.teach_capture_web import CaptureState, JOINT_NAMES
from scripts.urdf_forward_kinematics import axis_rotation


def synthetic_captures(count=6, corrupt_last=False):
    offset = np.array([42.0, -18.0, 31.0])
    fixed = np.array([-70.0, -210.0, 95.0])
    angles = [
        (0.0, 0.0, 0.0),
        (0.35, 0.0, 0.0),
        (0.0, -0.4, 0.0),
        (0.0, 0.0, 0.45),
        (0.25, -0.3, 0.2),
        (-0.3, 0.2, -0.25),
    ]
    captures = []
    for index, (rx, ry, rz) in enumerate(angles[:count]):
        rotation = (axis_rotation(np.array([1.0, 0.0, 0.0]), rx)
                    @ axis_rotation(np.array([0.0, 1.0, 0.0]), ry)
                    @ axis_rotation(np.array([0.0, 0.0, 1.0]), rz))
        origin = fixed - rotation @ offset
        if corrupt_last and index == count - 1:
            origin += np.array([12.0, 0.0, 0.0])
        captures.append({
            "pose_id": index + 1,
            "fk_tool_rotation": rotation.tolist(),
            "fk_tool_origin_mm": origin.tolist(),
        })
    return captures


class PivotTcpCaptureTests(unittest.TestCase):
    def test_exact_pivot_recovers_offset_and_reports_all_residuals(self):
        result = solve_pivot(synthetic_captures())
        np.testing.assert_allclose(result["estimated_tcp_offset_gripper_mm"],
                                   [42.0, -18.0, 31.0], atol=1e-9)
        self.assertEqual(result["rank"], 6)
        self.assertEqual(len(result["pose_residuals_mm"]), 6)
        self.assertLess(result["rms_residual_mm"], 1e-9)
        self.assertFalse(result["robot_enabled"])
        self.assertFalse(result["motion_authorized"])

    def test_corrupted_pose_produces_nonzero_residual(self):
        result = solve_pivot(synthetic_captures(corrupt_last=True))
        self.assertGreater(result["rms_residual_mm"], 1.0)
        self.assertGreater(result["max_residual_mm"], result["rms_residual_mm"])

    def test_requires_five_poses(self):
        with self.assertRaisesRegex(ValueError, "at least 5"):
            solve_pivot(synthetic_captures(4))

    def test_settled_snapshot_uses_fresh_unique_samples(self):
        state = CaptureState()
        now = time.monotonic_ns()
        for index in range(15):
            values = {name: 0.001 * index for name in JOINT_NAMES}
            state.add_joint({"type": "joint_update", "timestamp": 100.0 + index,
                             "joints": values},
                            received_ns=now - (14 - index) * 20_000_000,
                            received_unix_ns=1_000_000_000 + index)
        result = settled_joint_snapshot(state, now)
        self.assertEqual(len(result["samples"]), 15)
        self.assertLess(result["max_std_rad"], 0.01)
        self.assertAlmostEqual(result["means"]["Elbow"], 0.007)
        with self.assertRaisesRegex(ValueError, "fresh"):
            settled_joint_snapshot(state, now + 1_000_000_000)


if __name__ == "__main__":
    unittest.main()
