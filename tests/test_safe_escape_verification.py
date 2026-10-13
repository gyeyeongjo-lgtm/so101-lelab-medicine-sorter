import json
from pathlib import Path
import unittest

from scripts.safe_escape_verification import evaluate_escape_motion


FIXTURES = Path(__file__).with_name("fixtures")
TERMINAL_TOLERANCES = {
    "shoulder_pan": 0.5,
    "shoulder_lift": 1.5,
    "elbow_flex": 1.5,
    "wrist_flex": 0.5,
    "wrist_roll": 0.5,
    "gripper": 1.0,
}


def evaluate_fixture(name):
    document = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return evaluate_escape_motion(
        **document,
        terminal_tolerances=TERMINAL_TOLERANCES,
        feedback_fresh=True,
        communication_ok=True,
        settled=True,
    )


class SafeEscapeVerificationTests(unittest.TestCase):
    def test_actual_one_degree_no_motion_fixture_fails(self):
        result = evaluate_fixture("safe_escape_1deg_no_motion.json")
        self.assertFalse(result["pass"])
        self.assertFalse(result["movement_ok"])
        self.assertEqual(result["load_limit_status"], "NOT_DEFINED")
        self.assertFalse(result["grasp_tcp_z_increased"])

    def test_synthetic_two_degree_half_motion_and_tcp_rise_passes(self):
        result = evaluate_fixture("safe_escape_2deg_synthetic_pass.json")
        self.assertTrue(result["pass"])
        self.assertTrue(result["movement_ok"])
        self.assertTrue(result["grasp_tcp_z_increased"])
        self.assertTrue(result["load_ok"])
        self.assertTrue(result["temperature_ok"])
        self.assertTrue(result["noncommanded_drift_ok"])
        self.assertFalse(all(result["terminal_within_tolerance"].values()))
        self.assertFalse(result["terminal_tolerance_gates_escape_pass"])

    def test_missing_verified_load_limit_is_diagnostic_not_a_gate(self):
        document = json.loads(
            (FIXTURES / "safe_escape_2deg_synthetic_pass.json").read_text())
        document["verified_abs_load_limit"] = None
        result = evaluate_escape_motion(
            **document,
            terminal_tolerances=TERMINAL_TOLERANCES,
            feedback_fresh=True,
            communication_ok=True,
            settled=True,
        )
        self.assertTrue(result["pass"])
        self.assertEqual(result["load_limit_status"], "NOT_DEFINED")
        self.assertFalse(result["load_gate_enabled"])
        self.assertEqual(
            result["load_gate_result"], "NOT_APPLICABLE_NOT_DEFINED")
        self.assertIsNone(result["load_ok"])

    def test_signed_load_delta_is_reported(self):
        result = evaluate_fixture("safe_escape_2deg_synthetic_pass.json")
        self.assertEqual(result["present_load_delta"], {
            "shoulder_pan": -12,
            "shoulder_lift": 14,
            "elbow_flex": -4,
            "wrist_flex": 12,
            "wrist_roll": -8,
            "gripper": 0,
        })

    def test_future_verified_load_limit_still_gates_when_defined(self):
        document = json.loads(
            (FIXTURES / "safe_escape_2deg_synthetic_pass.json").read_text())
        document["verified_abs_load_limit"] = 100
        result = evaluate_escape_motion(
            **document,
            terminal_tolerances=TERMINAL_TOLERANCES,
            feedback_fresh=True,
            communication_ok=True,
            settled=True,
        )
        self.assertFalse(result["pass"])
        self.assertTrue(result["load_gate_enabled"])
        self.assertEqual(result["load_gate_result"], "FAIL")

    def test_temperature_above_55_blocks(self):
        document = json.loads(
            (FIXTURES / "safe_escape_2deg_synthetic_pass.json").read_text())
        document["temperature_c"]["elbow_flex"] = 56
        result = evaluate_escape_motion(
            **document,
            terminal_tolerances=TERMINAL_TOLERANCES,
            feedback_fresh=True,
            communication_ok=True,
            settled=True,
        )
        self.assertFalse(result["pass"])
        self.assertFalse(result["temperature_ok"])

    def test_more_than_two_degree_step_is_rejected(self):
        document = json.loads(
            (FIXTURES / "safe_escape_2deg_synthetic_pass.json").read_text())
        document["requested_target"]["shoulder_pan"] = 2.01
        with self.assertRaisesRegex(ValueError, "exceeds_two_degrees"):
            evaluate_escape_motion(
                **document,
                terminal_tolerances=TERMINAL_TOLERANCES,
                feedback_fresh=True,
                communication_ok=True,
                settled=True,
            )

    def test_terminal_tolerance_is_diagnostic_only(self):
        document = json.loads(
            (FIXTURES / "safe_escape_2deg_synthetic_pass.json").read_text())
        result = evaluate_escape_motion(
            **document,
            terminal_tolerances=TERMINAL_TOLERANCES,
            feedback_fresh=True,
            communication_ok=True,
            settled=True,
        )
        self.assertTrue(result["pass"])
        self.assertFalse(all(result["terminal_within_tolerance"].values()))
        self.assertFalse(result["terminal_tolerance_gates_escape_pass"])


if __name__ == "__main__":
    unittest.main()
