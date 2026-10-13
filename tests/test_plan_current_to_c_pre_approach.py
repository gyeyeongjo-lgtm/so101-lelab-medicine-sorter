import hashlib
import json
from pathlib import Path
import unittest

from scripts.plan_current_to_c_pre_approach import ARM_NAMES, plan
from scripts.urdf_forward_kinematics import UrdfKinematics


ROOT = Path(__file__).resolve().parents[1]
REQUEST = ROOT / "configs/current_to_c_pre_approach_planning_20261013.json"
URDF = ROOT / ".local/c-red-pivot-tcp-table-20261011-s01/so101_new_calib.urdf"


class CurrentToCPreApproachPlannerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.request = json.loads(REQUEST.read_text(encoding="utf-8"))
        cls.digest = hashlib.sha256(URDF.read_bytes()).hexdigest()
        cls.result = plan(
            cls.request, UrdfKinematics.from_file(URDF), cls.digest)

    def test_fresh_start_and_fixed_endpoint_are_preserved(self):
        self.assertEqual(self.result["fresh_start_pose"],
                         "C_RETURN_ACTUAL_ATTEMPT2")
        self.assertEqual(self.result["joint_delta_start_to_target_deg"], {
            name: round(target - start, 6)
            for name, start, target in zip(
                ARM_NAMES,
                self.request["fresh_current_joints_deg"],
                self.request["pre_approach_joints_deg"],
            )
        })

    def test_compares_direct_two_and_three_degree_wrist_lead_schedules(self):
        self.assertEqual(len(self.result["candidates"]), 3)
        self.assertEqual(self.result["recommended_candidate"],
                         "WRIST_LEAD_2DEG")
        self.assertEqual(
            [candidate["candidate"] for candidate in self.result["candidates"]],
            ["DIRECT_COUPLED", "WRIST_LEAD_2DEG", "WRIST_LEAD_3DEG"],
        )
        for candidate in self.result["candidates"]:
            if candidate["candidate"] == "DIRECT_COUPLED":
                self.assertEqual(candidate["staged_intermediate_arm_deg"], [])
                continue
            stage = candidate["staged_intermediate_arm_deg"][0]
            start = self.request["fresh_current_joints_deg"]
            for index, name in enumerate(ARM_NAMES):
                if name != "wrist_flex":
                    self.assertAlmostEqual(stage[name], start[index], places=6)

    def test_recommended_exact_path_has_two_wrist_only_then_nine_coupled_goals(self):
        recommended = self.result["recommended"]
        self.assertEqual(recommended["waypoint_count"], 11)
        self.assertEqual(recommended["wrist_lead_delta_deg"], 2.0)
        progression = recommended["waypoint_progression"]
        start = progression[0]["joints_deg"]
        for sample in progression[1:3]:
            for name in ARM_NAMES:
                if name != "wrist_flex":
                    self.assertAlmostEqual(sample["joints_deg"][name], start[name], places=6)
        self.assertAlmostEqual(
            progression[2]["joints_deg"]["wrist_flex"],
            start["wrist_flex"] - 2.0,
            places=6,
        )
        self.assertEqual(recommended["negative_z_steps"], 0)
        self.assertEqual(recommended["increasing_c_xy_distance_steps"], 0)
        self.assertGreater(recommended["minimum_tcp_z_increase_per_waypoint_mm"], 0.0)

    def test_all_candidates_are_bounded_and_keep_existing_endpoint(self):
        target = self.request["target_robot_xyz_mm"]
        for candidate in self.result["candidates"]:
            self.assertTrue(candidate["valid"])
            self.assertLessEqual(candidate["maximum_joint_step_deg"], 1.0)
            self.assertEqual(candidate["negative_z_steps"], 0)
            self.assertEqual(candidate["increasing_c_xy_distance_steps"], 0)
            self.assertGreaterEqual(
                candidate["minimum_grasp_tcp_z_mm"], 89.193801)
            self.assertGreater(
                candidate["minimum_tcp_table_proxy_margin_mm"], 0.0)
            self.assertEqual(candidate["self_collision_proxy"], "PASS")
            self.assertGreater(candidate["minimum_servo_margin_deg"], 0.0)
            self.assertLess(candidate["final_grasp_tcp_target_error_mm"], 1e-3)
            self.assertEqual(candidate["full_mesh_environment"], "NOT_VERIFIED")
            final = candidate["waypoint_progression"][-1]["grasp_tcp_xyz_mm"]
            for actual, expected in zip(final, target):
                self.assertAlmostEqual(actual, expected, places=3)

    def test_recommended_result_is_offline_only(self):
        self.assertEqual(self.result["hardware_command_count"], 0)
        self.assertFalse(self.result["follower_port_opened"])
        self.assertFalse(self.result["goal_or_torque_changed"])
        self.assertFalse(self.result["motion_authorized"])

    def test_rejects_step_above_one_degree(self):
        request = {**self.request, "maximum_joint_step_deg": 1.01}
        with self.assertRaisesRegex(ValueError, "invalid CURRENT path request"):
            plan(request, UrdfKinematics.from_file(URDF), self.digest)


if __name__ == "__main__":
    unittest.main()
