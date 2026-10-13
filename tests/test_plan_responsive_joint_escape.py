import hashlib
import json
from pathlib import Path
import unittest

from scripts.plan_responsive_joint_escape import plan
from scripts.urdf_forward_kinematics import UrdfKinematics


REQUEST = Path("configs/c_pick_responsive_joint_escape_20261012.json")
URDF = Path(".local/c-red-pivot-tcp-table-20261011-s01/so101_new_calib.urdf")


class ResponsiveJointEscapeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = json.loads(REQUEST.read_text(encoding="utf-8"))
        cls.result = plan(
            cls.document,
            UrdfKinematics.from_file(URDF),
            hashlib.sha256(URDF.read_bytes()).hexdigest(),
        )

    def test_fk_sensitivity_selects_negative_wrist_flex_direction(self):
        sensitivity = self.result["fk_z_sensitivity_mm_per_deg"]
        self.assertAlmostEqual(sensitivity["shoulder_pan"], 0.0, places=3)
        self.assertLess(sensitivity["wrist_flex"], -2.4)
        self.assertEqual(self.result["selected_direction_deg_sign"], -1)

    def test_four_monotonic_bounded_candidates_hold_unresponsive_joints(self):
        self.assertEqual(len(self.result["candidates"]), 4)
        start = self.result["current_arm_joints_deg"]
        for candidate in self.result["candidates"]:
            self.assertTrue(candidate["offline_constraints_pass"])
            self.assertLessEqual(candidate["maximum_joint_step_deg"], 2.0)
            self.assertTrue(candidate["predicted_z_monotonic_increase"])
            self.assertTrue(candidate["table_proxy_not_worse_than_start"])
            self.assertEqual(candidate["self_collision_centerline_proxy"], "PASS")
            self.assertEqual(candidate["servo_range"], "PASS")
            endpoint = candidate["endpoint_joints_deg"]
            for joint in ("shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_roll"):
                self.assertAlmostEqual(endpoint[joint], start[joint], places=6)

    def test_recommendation_is_the_requested_first_twenty_mm_stage(self):
        self.assertEqual(
            self.result["recommended_candidate"],
            "WRIST_ESCAPE_Z_PLUS_20",
        )
        chosen = next(
            candidate for candidate in self.result["candidates"]
            if candidate["name"] == self.result["recommended_candidate"]
        )
        self.assertAlmostEqual(chosen["predicted_cumulative_z_gain_mm"], 20.0)
        self.assertLess(chosen["maximum_xy_drift_mm"], 16.0)
        self.assertLess(
            chosen["waypoints"][-1]["tool_axis_change_deg"], 8.0)
        self.assertLess(
            chosen["waypoints"][-1]["jaw_axis_change_deg"], 8.0)

    def test_planner_has_no_motion_authority(self):
        self.assertEqual(self.result["actual_motor_command_count"], 0)
        self.assertFalse(self.result["follower_port_opened"])
        self.assertFalse(self.result["goal_or_torque_changed"])
        self.assertFalse(self.result["motion_authorized"])
        self.assertEqual(self.result["phase_c"], "HOLD")
        self.assertEqual(self.result["full_mesh_collision_status"], "NOT_VERIFIED")


if __name__ == "__main__":
    unittest.main()
