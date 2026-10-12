import unittest

import numpy as np

from scripts.plan_pick_grasp_tcp_ik import _path_report, _progress_path, axis_error_deg


class PickGraspTcpIKTests(unittest.TestCase):
    def test_pin_and_grasp_offsets_are_not_the_same_candidate(self):
        pin = np.array([-51.748354, -73.033741, -54.531737])
        grasp = np.array([-4.748354, -12.033741, -124.531737])
        self.assertFalse(np.allclose(pin, grasp))
        self.assertAlmostEqual(float(np.linalg.norm(grasp - pin)), 104.067286, places=5)

    def test_progress_path_is_bounded_and_delays_wrist(self):
        start = np.zeros(5)
        end = np.array([10.0, -30.0, 50.0, -40.0, 20.0])
        path = _progress_path(start, end, maximum_step_deg=1.0,
                              wrist_delay_fraction=0.10)
        self.assertLessEqual(float(np.max(np.abs(np.diff(path, axis=0)))), 1.0)
        self.assertEqual(path[1, 3], 0.0)
        np.testing.assert_allclose(path[-1], end)

    def test_axis_error(self):
        self.assertEqual(axis_error_deg(np.array([0.0, 0.0, -1.0]),
                                        np.array([0.0, 0.0, -1.0])), 0.0)

    def test_path_report_separates_saved_start_from_commanded_waypoints(self):
        class FakeKinematics:
            def forward(self, joints, root, target):
                transform = np.eye(4)
                if target == "gripper":
                    transform[2, 3] = joints["Rotation"]
                return transform

        samples = np.array([[0.0, 0, 0, 0, 0], [1.0, 0, 0, 0, 0],
                            [2.0, 0, 0, 0, 0]])
        report = _path_report(
            FakeKinematics(), samples, np.zeros(3),
            np.tile([-180.0, 180.0], (5, 1)), 500.0,
        )
        self.assertEqual(report["minimum_sample_index_zero_is_saved_start"], 0)
        self.assertEqual(report["minimum_commanded_waypoint_one_based"], 1)


if __name__ == "__main__":
    unittest.main()
