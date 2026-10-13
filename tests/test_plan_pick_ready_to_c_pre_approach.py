import hashlib
import json
from pathlib import Path
import unittest

import yaml

from scripts.plan_pick_ready_to_c_pre_approach import ARM_NAMES, plan
from scripts.urdf_forward_kinematics import UrdfKinematics


ROOT = Path(__file__).resolve().parents[1]
REQUEST = ROOT / "configs/pick_ready_to_c_pre_approach_planning_20261013.json"
URDF = ROOT / ".local/c-red-pivot-tcp-table-20261011-s01/so101_new_calib.urdf"


class PickReadyToCPreApproachPlannerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.request = json.loads(REQUEST.read_text(encoding="utf-8"))
        cls.digest = hashlib.sha256(URDF.read_bytes()).hexdigest()
        cls.result = plan(
            cls.request, UrdfKinematics.from_file(URDF), cls.digest)

    def test_start_is_the_recorded_pick_ready_pose(self):
        poses = yaml.safe_load((ROOT / "configs/poses.yaml").read_text(encoding="utf-8"))
        recorded = poses["poses"]["PICK_READY"]["joints"]
        expected = [recorded[name]["degree_mean"] for name in ARM_NAMES]
        self.assertEqual(self.request["pick_ready_joints_deg"], expected)
        self.assertEqual(self.result["canonical_start_pose"], "PICK_READY")
        self.assertFalse(self.result["home_path_or_absolute_lift_anchors_reused"])

    def test_candidates_use_relative_relief_and_delayed_wrist(self):
        self.assertEqual(len(self.result["candidates"]), 9)
        start = self.request["pick_ready_joints_deg"]
        absolute_home_anchors = {-65.0, -60.0, -55.0}
        for candidate in self.result["candidates"]:
            self.assertNotIn(candidate["lift_relief_target_deg"], absolute_home_anchors)
            self.assertAlmostEqual(
                candidate["lift_relief_target_deg"],
                start[1] + candidate["lift_relief_delta_deg"], places=6)
            first = candidate["staged_intermediate_arm_deg"][0]
            self.assertAlmostEqual(first["elbow_flex"], start[2], places=6)
            self.assertAlmostEqual(first["wrist_flex"], start[3], places=6)
            held = [
                stage for stage in candidate["tcp_orientation_progression"]
                if "WRIST_HOLD" in stage["stage"]
            ]
            self.assertTrue(held)
            for stage in held:
                self.assertAlmostEqual(
                    stage["joints_deg"]["wrist_flex"], start[3], places=6)

    def test_all_valid_candidates_preserve_endpoint_and_proxies(self):
        endpoint = dict(zip(ARM_NAMES, self.request["pre_approach_joints_deg"]))
        for candidate in self.result["candidates"]:
            self.assertTrue(candidate["valid"])
            self.assertLessEqual(candidate["maximum_joint_step_deg"], 1.0)
            self.assertGreater(candidate["minimum_tcp_table_proxy_margin_mm"], 0.0)
            self.assertEqual(candidate["self_collision_proxy"], "PASS")
            self.assertGreater(candidate["minimum_servo_margin_deg"], 0.0)
            self.assertLess(candidate["final_grasp_tcp_target_error_mm"], 1e-3)
            self.assertEqual(candidate["full_mesh_environment"], "NOT_VERIFIED")
            final = candidate["tcp_orientation_progression"][-1]
            for name, value in endpoint.items():
                self.assertAlmostEqual(final["joints_deg"][name], value, places=6)
            self.assertLess(final["tool_axis_error_deg"], 3.1)
            self.assertLess(final["jaw_axis_error_deg"], 0.7)

    def test_recommended_result_is_offline_only(self):
        recommended = self.result["recommended"]
        self.assertTrue(recommended["valid"])
        self.assertEqual(self.result["hardware_command_count"], 0)
        self.assertFalse(self.result["follower_port_opened"])
        self.assertFalse(self.result["goal_or_torque_changed"])
        self.assertFalse(self.result["motion_authorized"])
        self.assertEqual(self.result["full_mesh_environment"], "NOT_VERIFIED")

    def test_rejects_step_above_one_degree(self):
        request = {**self.request, "maximum_joint_step_deg": 1.01}
        with self.assertRaisesRegex(ValueError, "invalid PICK_READY path request"):
            plan(request, UrdfKinematics.from_file(URDF), self.digest)


if __name__ == "__main__":
    unittest.main()
