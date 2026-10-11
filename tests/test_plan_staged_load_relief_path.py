import json
import unittest
from pathlib import Path

from scripts.plan_staged_load_relief_path import plan
from scripts.urdf_forward_kinematics import UrdfKinematics


ROOT = Path(__file__).resolve().parents[1]


class StagedLoadReliefPathTests(unittest.TestCase):
    def setUp(self):
        self.request = {
            "start_joint_deg": {
                "shoulder_pan": -9.538,
                "shoulder_lift": -94.725,
                "elbow_flex": 87.956,
                "wrist_flex": 71.956,
                "wrist_roll": -15.165,
            },
            "endpoint_joint_deg": {
                "shoulder_pan": -0.014220,
                "shoulder_lift": 11.507515,
                "elbow_flex": 14.866481,
                "wrist_flex": 12.933013,
                "wrist_roll": 13.899293,
            },
            "failed_waypoint_target_deg": {
                "shoulder_pan": -8.292299094176851,
                "shoulder_lift": -80.82565737804252,
                "elbow_flex": 78.5457427127452,
                "wrist_flex": 64.23340439170175,
                "wrist_roll": -11.285642468727534,
            },
            "failed_waypoint_feedback_deg": {
                "shoulder_pan": -8.835164835164836,
                "shoulder_lift": -81.01098901098901,
                "elbow_flex": 82.5934065934066,
                "wrist_flex": 64.92307692307692,
                "wrist_roll": -11.648351648351648,
            },
            "tcp_offset_gripper_mm": [-51.748354423376675, -73.03374105992054, -54.53173724769001],
            "object_xy_mm": [-62.635354, -295.315566],
            "maximum_joint_step_deg": 1.0,
            "servo_bounds_deg": {
                "shoulder_pan": [-116.374, 116.374],
                "shoulder_lift": [-99.846, 99.846],
                "elbow_flex": [-95.011, 95.011],
                "wrist_flex": [-98.615, 98.615],
                "wrist_roll": [-154.352, 154.352],
            },
            "candidate_specs": [
                {"candidate": "A_MINIMAL", "unload_lift_deg": -75.0, "unload_elbow_deg": 70.0},
                {"candidate": "B_BALANCED", "unload_lift_deg": -70.0, "unload_elbow_deg": 65.0},
                {"candidate": "C_CONSERVATIVE", "unload_lift_deg": -65.0, "unload_elbow_deg": 60.0},
            ],
        }
        self.kinematics = UrdfKinematics.from_file(
            ROOT / ".local/c-red-pivot-tcp-table-20261011-s01/so101_new_calib.urdf"
        )

    def test_failed_waypoint_fk_is_reconstructed(self):
        result = plan(self.request, self.kinematics)
        self.assertAlmostEqual(result["failed_waypoint"]["target_fk_tcp_xyz_mm"][2], 72.599527, places=5)
        self.assertAlmostEqual(result["failed_waypoint"]["feedback_fk_tcp_xyz_mm"][2], 63.669029, places=5)

    def test_candidates_hold_elbow_while_unloading_lift(self):
        result = plan(self.request, self.kinematics)
        for candidate in result["candidates"]:
            stage = candidate["stages"][0]
            self.assertAlmostEqual(stage["elbow_angle_deg"], 87.956)
            self.assertGreater(stage["joint_delta_deg"]["shoulder_lift"], 0)

    def test_all_candidates_pass_bounded_fk_proxies_and_servo_bounds(self):
        result = plan(self.request, self.kinematics)
        for candidate in result["candidates"]:
            self.assertTrue(candidate["valid"])
            self.assertTrue(candidate["servo_bounds_pass"])
            self.assertTrue(candidate["tcp_height_proxy_pass"])
            self.assertTrue(candidate["pre_final_object_direction_proxy_pass"])
            for stage in candidate["stages"]:
                self.assertLessEqual(stage["maximum_joint_step_deg"], 1.0)

    def test_endpoint_is_unchanged_and_minimal_candidate_is_selected(self):
        result = plan(self.request, self.kinematics)
        self.assertEqual(result["recommended_candidate"], "A_MINIMAL")
        endpoint = result["candidates"][0]["stages"][-1]["joints_deg"]
        self.assertEqual(endpoint, self.request["endpoint_joint_deg"])

    def test_fresh3_strong_unload_candidates_hold_elbow_and_pass_fk_proxies(self):
        request = json.loads((
            ROOT / ".local/c-red-pivot-tcp-table-20261011-s01/"
            "strong_unload_request_fresh3_20261011.json"
        ).read_text())
        result = plan(request, self.kinematics)
        self.assertEqual(
            [candidate["candidate"] for candidate in result["candidates"]],
            ["LIFT_NEG65", "LIFT_NEG60", "LIFT_NEG55", "LIFT_NEG50"],
        )
        for candidate in result["candidates"]:
            self.assertTrue(candidate["valid"])
            self.assertTrue(candidate["servo_bounds_pass"])
            self.assertTrue(candidate["tcp_height_proxy_pass"])
            self.assertTrue(candidate["pre_final_object_direction_proxy_pass"])
            self.assertAlmostEqual(
                candidate["stages"][0]["elbow_angle_deg"],
                request["start_joint_deg"]["elbow_flex"],
                places=6,
            )


if __name__ == "__main__":
    unittest.main()
