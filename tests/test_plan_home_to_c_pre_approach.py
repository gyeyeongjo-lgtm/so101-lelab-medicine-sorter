import json
from pathlib import Path
import unittest

from scripts.plan_home_to_c_pre_approach import plan
from scripts.urdf_forward_kinematics import UrdfKinematics


class HomeToCPreApproachPlannerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.request = json.loads(Path(
            "configs/home_to_c_pre_approach_planning_20261012.json"
        ).read_text())
        cls.kinematics = UrdfKinematics.from_file(Path(
            ".local/c-red-pivot-tcp-table-20261011-s01/so101_new_calib.urdf"))

    def test_selects_smallest_evidence_backed_lift_relief(self):
        result = plan(self.request, self.kinematics)
        self.assertEqual(result["canonical_start_pose"], "HOME")
        self.assertEqual(result["recommended_candidate"], "LIFT_NEG60P0")
        self.assertEqual(result["motor_commands_sent"], 0)
        self.assertFalse(result["motion_authorized"])
        candidates = {row["candidate"]: row for row in result["candidates"]}
        self.assertFalse(candidates["LIFT_NEG65P0"]["valid"])
        self.assertEqual(
            candidates["LIFT_NEG65P0"]["expected_lift_relief_raw_delta"], 3)
        self.assertTrue(candidates["LIFT_NEG60P0"]["valid"])
        self.assertEqual(
            candidates["LIFT_NEG60P0"]["expected_lift_relief_raw_delta"], 60)

    def test_recommended_path_preserves_bounded_proxy_results(self):
        recommended = plan(self.request, self.kinematics)["recommended"]
        self.assertEqual(recommended["waypoint_count"], 62)
        self.assertLessEqual(recommended["maximum_joint_step_deg"], 1.0)
        self.assertGreaterEqual(
            recommended["minimum_tcp_table_proxy_margin_mm"], 26.376)
        self.assertGreaterEqual(
            recommended["minimum_self_collision_centerline_margin_mm"], 55.827)
        self.assertGreaterEqual(recommended["minimum_servo_margin_deg"], 17.604)
        self.assertEqual(recommended["full_mesh_environment"], "NOT_VERIFIED")

    def test_rejects_when_no_candidate_exceeds_measured_deadband(self):
        request = {**self.request, "minimum_effective_raw_delta": 200}
        with self.assertRaisesRegex(ValueError, "no valid evidence-backed HOME path"):
            plan(request, self.kinematics)


if __name__ == "__main__":
    unittest.main()
