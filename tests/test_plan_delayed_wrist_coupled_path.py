import json
from pathlib import Path
import unittest

from scripts.plan_delayed_wrist_coupled_path import JOINTS, plan
from scripts.urdf_forward_kinematics import UrdfKinematics


ROOT = Path(__file__).resolve().parents[1]


class DelayedWristCoupledPathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.request = json.loads((
            ROOT / ".local/c-red-pivot-tcp-table-20261011-s01/"
            "delayed_wrist_request_fresh5_20261011.json"
        ).read_text())
        cls.result = plan(cls.request, UrdfKinematics.from_file(
            ROOT / ".local/c-red-pivot-tcp-table-20261011-s01/so101_new_calib.urdf"
        ))

    def test_candidates_are_bounded_monotonic_and_end_exactly(self):
        endpoint = {name: round(self.request["endpoint_joint_deg"][name], 6) for name in JOINTS}
        for candidate in self.result["candidates"]:
            self.assertTrue(candidate["valid"])
            self.assertTrue(candidate["object_xy_distance_monotonic"])
            self.assertLessEqual(candidate["maximum_joint_step_deg"], 1.0)
            self.assertLess(candidate["maximum_coupled_wrist_step_deg"], 0.8)
            self.assertGreater(candidate["minimum_servo_margin_deg"], 0.0)
            self.assertTrue(candidate["endpoint_exact"])
            self.assertEqual(candidate["waypoint_schedule"][-1]["joints_deg"], endpoint)

    def test_shoulder_elbow_geometry_remains_on_original_balanced_schedule(self):
        anchor = self.request["balanced_anchor_joint_deg"]
        endpoint = self.request["endpoint_joint_deg"]
        for candidate in self.result["candidates"]:
            for stage in candidate["waypoint_schedule"][:-1]:
                progress = stage["coupled_progress"]
                for joint in ("shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_roll"):
                    expected = anchor[joint] + (endpoint[joint] - anchor[joint]) * progress
                    self.assertAlmostEqual(stage["joints_deg"][joint], expected, places=6)

    def test_wrist_holds_until_each_delay_and_then_decreases(self):
        start_wrist = self.request["start_joint_deg"]["wrist_flex"]
        for candidate in self.result["candidates"]:
            delay = candidate["wrist_delay_fraction"]
            coupled = candidate["waypoint_schedule"][:-1]
            self.assertIn(delay, [stage["coupled_progress"] for stage in coupled])
            for stage in coupled:
                wrist = stage["joints_deg"]["wrist_flex"]
                if stage["coupled_progress"] <= delay:
                    self.assertAlmostEqual(wrist, start_wrist, places=6)
            values = [stage["joints_deg"]["wrist_flex"] for stage in candidate["waypoint_schedule"]]
            self.assertTrue(all(next_value <= value + 1e-9
                                for value, next_value in zip(values, values[1:])))

    def test_smallest_valid_delay_is_recommended(self):
        self.assertEqual(self.result["recommended_candidate"], "WRIST_DELAY_25")


if __name__ == "__main__":
    unittest.main()
