import json
from pathlib import Path
import unittest

from scripts.plan_coupled_final_path import plan
from scripts.urdf_forward_kinematics import UrdfKinematics


ROOT = Path(__file__).resolve().parents[1]


class CoupledFinalPathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.request = json.loads((
            ROOT / ".local/c-red-pivot-tcp-table-20261011-s01/"
            "coupled_final_request_fresh4_20261011.json"
        ).read_text())
        cls.result = plan(cls.request, UrdfKinematics.from_file(
            ROOT / ".local/c-red-pivot-tcp-table-20261011-s01/so101_new_calib.urdf"
        ))

    def test_all_candidates_are_bounded_monotonic_and_in_bounds(self):
        for candidate in self.result["candidates"]:
            self.assertTrue(candidate["valid"])
            self.assertTrue(candidate["object_xy_distance_monotonic"])
            self.assertLessEqual(candidate["maximum_joint_step_deg"], 1.0)
            self.assertGreater(candidate["minimum_servo_margin_deg"], 0.0)

    def test_elbow_progress_never_leads_lift_progress(self):
        start = self.request["safe_anchor_joint_deg"]
        endpoint = self.request["endpoint_joint_deg"]
        for candidate in self.result["candidates"]:
            for stage, lift_fraction in zip(
                    candidate["joint_schedule"][1:-1], self.request["schedule_fractions"]):
                elbow = stage["joints_deg"]["elbow_flex"]
                elbow_fraction = ((elbow - start["elbow_flex"]) /
                                  (endpoint["elbow_flex"] - start["elbow_flex"]))
                self.assertLessEqual(elbow_fraction, lift_fraction + 1e-6)

    def test_balanced_coupled_is_selected_and_endpoint_is_exact(self):
        self.assertEqual(self.result["recommended_candidate"], "BALANCED_COUPLED")
        selected = next(item for item in self.result["candidates"]
                        if item["candidate"] == "BALANCED_COUPLED")
        self.assertEqual(selected["joint_schedule"][-1]["joints_deg"], {
            name: round(value, 6) for name, value in self.request["endpoint_joint_deg"].items()
        })


if __name__ == "__main__":
    unittest.main()
