import hashlib
import json
from pathlib import Path
import unittest

from scripts.analyze_wrist_escape_postmortem import analyze
from scripts.urdf_forward_kinematics import UrdfKinematics


TRIAL = Path("tests/fixtures/wrist_escape_z_plus20_attempt1.json")
URDF = Path(".local/c-red-pivot-tcp-table-20261011-s01/so101_new_calib.urdf")


class WristEscapePostmortemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        document = json.loads(TRIAL.read_text(encoding="utf-8"))
        cls.result = analyze(
            document,
            UrdfKinematics.from_file(URDF),
            hashlib.sha256(URDF.read_bytes()).hexdigest(),
        )

    def test_exact_trial_tcp_delta_is_reproduced(self):
        self.assertAlmostEqual(
            self.result["actual_grasp_tcp_z_delta_mm"], -0.998793, places=5,
        )

    def test_single_axis_contributions_explain_failure(self):
        contribution = self.result["exact_single_axis_contribution"]
        self.assertGreater(
            contribution["wrist_flex"]["exact_isolated_fk_z_contribution_mm"],
            4.3,
        )
        self.assertLess(
            contribution["shoulder_lift"]["exact_isolated_fk_z_contribution_mm"],
            -2.9,
        )
        self.assertLess(
            contribution["elbow_flex"]["exact_isolated_fk_z_contribution_mm"],
            -2.3,
        )

    def test_no_responsive_only_two_degree_step_survives_observed_drift(self):
        self.assertEqual(
            self.result["responsive_joints_at_50_percent"],
            ["shoulder_pan", "wrist_flex", "wrist_roll"],
        )
        self.assertEqual(self.result["responsive_only_candidate"], "NOT_FOUND")
        self.assertLess(
            self.result["best_evidence_constrained_responsive_only_step"]
            ["modeled_z_delta_mm"],
            0.0,
        )
        self.assertIsNone(self.result["next_live_command"])

    def test_analysis_has_no_hardware_authority(self):
        self.assertEqual(self.result["actual_motor_command_count"], 0)
        self.assertFalse(self.result["follower_port_opened"])
        self.assertFalse(self.result["motion_authorized"])
        self.assertEqual(self.result["phase_c"], "HOLD")


if __name__ == "__main__":
    unittest.main()
