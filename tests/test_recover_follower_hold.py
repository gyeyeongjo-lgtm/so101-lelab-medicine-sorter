import unittest

from scripts.recover_follower_hold import recover_current_hold


AXES = ("shoulder_pan", "shoulder_lift", "elbow_flex",
        "wrist_flex", "wrist_roll", "gripper")


class Calibration:
    range_min = 100
    range_max = 4000


class FakeBus:
    def __init__(self):
        self.present = {name: 2000 + index for index, name in enumerate(AXES)}
        self.goal = {name: 0 for name in AXES}
        self.torque = {name: 0 for name in AXES}
        self.calibration = {name: Calibration() for name in AXES}
        self.enable_calls = 0
        self.disable_calls = 0
        self.corrupt_goal = False
        self.drift_before_enable = False
        self.move_after_enable = False

    def sync_read(self, register, *, normalize, num_retry):
        self.assert_raw(normalize, num_retry)
        if register == "Present_Position":
            if self.move_after_enable and any(self.torque.values()):
                return {**self.present, "elbow_flex": self.present["elbow_flex"] + 20}
            if self.drift_before_enable and any(self.goal.values()) and not any(self.torque.values()):
                return {**self.present, "elbow_flex": self.present["elbow_flex"] + 20}
            return dict(self.present)
        if register == "Goal_Position":
            value = dict(self.goal)
            if self.corrupt_goal and any(value.values()):
                value["elbow_flex"] += 1
            return value
        if register == "Torque_Enable":
            return dict(self.torque)
        if register == "Moving":
            return {name: 0 for name in AXES}
        raise AssertionError(register)

    @staticmethod
    def assert_raw(normalize, num_retry):
        if normalize is not False or num_retry != 2:
            raise AssertionError("expected raw three-attempt read")

    def sync_write(self, register, values, *, normalize, num_retry):
        if register != "Goal_Position" or normalize is not False or num_retry != 2:
            raise AssertionError("unexpected write")
        self.goal = dict(values)

    def enable_torque(self, num_retry):
        self.enable_calls += 1
        self.torque = {name: 1 for name in AXES}

    def disable_torque(self, num_retry):
        self.disable_calls += 1
        self.torque = {name: 0 for name in AXES}


class RecoverFollowerHoldTests(unittest.TestCase):
    def test_exact_current_goal_then_torque_and_stationary_confirmation(self):
        bus = FakeBus()
        result = recover_current_hold(
            bus, input_fn=lambda _: "HOLD CONFIRMED", sleep_fn=lambda _: None)
        self.assertEqual(result["status"], "CURRENT_POSE_HOLD_RECOVERED")
        self.assertEqual(bus.goal, bus.present)
        self.assertEqual(bus.enable_calls, 1)
        self.assertEqual(bus.disable_calls, 0)
        self.assertTrue(all(row["delta"] == 0 for row in result["rows"]))

    def test_goal_readback_mismatch_never_enables_torque(self):
        bus = FakeBus()
        bus.corrupt_goal = True
        with self.assertRaisesRegex(RuntimeError, "goal_readback_mismatch"):
            recover_current_hold(bus, input_fn=lambda _: "HOLD CONFIRMED",
                                 sleep_fn=lambda _: None)
        self.assertEqual(bus.enable_calls, 0)

    def test_zero_goal_never_enables_torque(self):
        bus = FakeBus()
        bus.present["gripper"] = 0
        with self.assertRaisesRegex(RuntimeError, "fresh_present_outside_hardware_raw_range"):
            recover_current_hold(bus, input_fn=lambda _: "HOLD CONFIRMED",
                                 sleep_fn=lambda _: None)
        self.assertEqual(bus.enable_calls, 0)

    def test_drift_before_enable_never_enables_torque(self):
        bus = FakeBus()
        bus.drift_before_enable = True
        with self.assertRaisesRegex(RuntimeError, "arm_drifted_before_torque_enable"):
            recover_current_hold(bus, input_fn=lambda _: "HOLD CONFIRMED",
                                 sleep_fn=lambda _: None)
        self.assertEqual(bus.enable_calls, 0)

    def test_unexpected_motion_response_disables_torque(self):
        bus = FakeBus()
        with self.assertRaisesRegex(RuntimeError, "unexpected_motion_reported"):
            recover_current_hold(bus, input_fn=lambda _: "UNEXPECTED MOVEMENT",
                                 sleep_fn=lambda _: None)
        self.assertEqual(bus.enable_calls, 1)
        self.assertEqual(bus.disable_calls, 1)
        self.assertTrue(all(value == 0 for value in bus.torque.values()))

    def test_measured_motion_after_enable_disables_torque(self):
        bus = FakeBus()
        bus.move_after_enable = True
        with self.assertRaisesRegex(RuntimeError, "unexpected_motion_after_torque_enable"):
            recover_current_hold(bus, input_fn=lambda _: "HOLD CONFIRMED",
                                 sleep_fn=lambda _: None)
        self.assertEqual(bus.enable_calls, 1)
        self.assertEqual(bus.disable_calls, 1)
        self.assertTrue(all(value == 0 for value in bus.torque.values()))


if __name__ == "__main__":
    unittest.main()
