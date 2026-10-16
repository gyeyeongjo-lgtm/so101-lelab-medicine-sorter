import unittest

from scripts.sync_follower_goal_to_present_only import AXES, sync_goal_present_only


class Motor:
    def __init__(self, motor_id):
        self.id = motor_id


class FakeBus:
    def __init__(self):
        self.motors = {axis: Motor(i + 1) for i, axis in enumerate(AXES)}
        self.present = {axis: 1000 + i for i, axis in enumerate(AXES)}
        self.goal = {axis: 0 for axis in AXES}
        self.torque = {axis: 0 for axis in AXES}
        self.moving = {axis: 0 for axis in AXES}
        self.temperature = {axis: 38 for axis in AXES}
        self.writes = []

    def sync_read(self, register, *, normalize, num_retry):
        assert normalize is False and num_retry == 2
        return dict({
            "Present_Position": self.present,
            "Goal_Position": self.goal,
            "Torque_Enable": self.torque,
            "Moving": self.moving,
            "Present_Temperature": self.temperature,
        }[register])

    def _normalize(self, values):
        return values

    def sync_write(self, register, values, *, normalize, num_retry):
        self.writes.append((register, dict(values)))
        assert register == "Goal_Position"
        assert normalize is False and num_retry == 1
        self.goal = dict(values)


class GoalSyncTests(unittest.TestCase):
    def test_exact_raw_one_write_torque_stays_off(self):
        bus = FakeBus()
        result = sync_goal_present_only(bus, sleep_fn=lambda _: None)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["max_goal_present_raw_diff"], 0)
        self.assertEqual(bus.writes, [("Goal_Position", bus.present)])
        self.assertEqual(set(bus.torque.values()), {0})

    def test_moving_blocks_before_write(self):
        bus = FakeBus()
        bus.moving["elbow_flex"] = 1
        with self.assertRaisesRegex(RuntimeError, "follower_moving"):
            sync_goal_present_only(bus, sleep_fn=lambda _: None)
        self.assertEqual(bus.writes, [])

    def test_torque_on_blocks_before_write(self):
        bus = FakeBus()
        bus.torque["gripper"] = 1
        with self.assertRaisesRegex(RuntimeError, "torque_not_all_off"):
            sync_goal_present_only(bus, sleep_fn=lambda _: None)
        self.assertEqual(bus.writes, [])

    def test_goal_change_blocks_before_write(self):
        bus = FakeBus()
        def change(_):
            bus.goal["gripper"] = 500
        with self.assertRaisesRegex(RuntimeError, "goal_changed_before_sync"):
            sync_goal_present_only(bus, sleep_fn=change)
        self.assertEqual(bus.writes, [])

    def test_present_drift_blocks_before_write(self):
        bus = FakeBus()
        def drift(_):
            bus.present["elbow_flex"] += 1
        with self.assertRaisesRegex(RuntimeError, "present_not_stable_before_sync"):
            sync_goal_present_only(bus, sleep_fn=drift)
        self.assertEqual(bus.writes, [])

    def test_readback_mismatch_no_retry(self):
        bus = FakeBus()
        def corrupt(register, values, *, normalize, num_retry):
            bus.writes.append((register, dict(values)))
            bus.goal = dict(values)
            bus.goal["elbow_flex"] += 1
        bus.sync_write = corrupt
        with self.assertRaisesRegex(RuntimeError, "goal_readback_mismatch"):
            sync_goal_present_only(bus, sleep_fn=lambda _: None)
        self.assertEqual(len(bus.writes), 1)


if __name__ == "__main__":
    unittest.main()
