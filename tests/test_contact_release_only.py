import unittest

from scripts.contact_release_only import (
    ARM_JOINTS, BASELINE_GOAL_RAW, BASELINE_PRESENT_RAW, JOINTS,
    make_write_firewall, run_contact_release,
)


class Calibration:
    range_min = 0
    range_max = 4095


class Motor:
    def __init__(self, motor_id):
        self.id = motor_id


class FakeBus:
    def __init__(self):
        self.motors = {name: Motor(i + 1) for i, name in enumerate(JOINTS)}
        self.calibration = {name: Calibration() for name in JOINTS}
        self.raw_present = dict(BASELINE_PRESENT_RAW)
        self.raw_goal = dict(BASELINE_GOAL_RAW)
        self.position = {name: (20.0 if name == "gripper" else 10.0)
                         for name in JOINTS}
        self.torque = {name: 1 for name in JOINTS}
        self.moving = {name: 0 for name in JOINTS}
        self.temperature = {name: 35 for name in JOINTS}
        self.writes = []
        self.config_writes = 0
        self.torque_writes = 0

    def sync_read(self, register, *, normalize=True, num_retry=2):
        assert num_retry == 2
        if register == "Present_Position":
            return dict(self.position if normalize else self.raw_present)
        if register == "Goal_Position":
            return dict(self.raw_goal)
        if register == "Torque_Enable":
            return dict(self.torque)
        if register == "Moving":
            return dict(self.moving)
        if register == "Present_Temperature":
            return dict(self.temperature)
        raise AssertionError(register)

    def _normalize(self, values):
        return values

    def read(self, register, name, *, normalize, num_retry):
        assert register == "Present_Temperature"
        assert normalize is False and num_retry == 2
        return self.temperature[name]

    def sync_write(self, register, values, *args, **kwargs):
        self.writes.append((register, dict(values)))

    def write(self, *_args, **_kwargs):
        self.config_writes += 1

    def write_calibration(self, *_args, **_kwargs):
        self.config_writes += 1

    def configure_motors(self, *_args, **_kwargs):
        self.config_writes += 1

    def enable_torque(self, *_args, **_kwargs):
        self.torque_writes += 1

    def disable_torque(self, *_args, **_kwargs):
        self.torque_writes += 1


class FakeFollower:
    def __init__(self):
        self.bus = FakeBus()


class FakeLeader:
    def __init__(self):
        self.bus = FakeBus()
        self.bus.torque = {name: 0 for name in JOINTS}
        self.position = {f"{name}.pos": (20.0 if name == "gripper" else 10.0)
                         for name in JOINTS}

    def get_action(self):
        return dict(self.position)


class Clock:
    def __init__(self):
        self.t = 0.0

    def monotonic(self):
        return self.t

    def sleep(self, duration):
        self.t += duration


def fk(degrees):
    return [0.0, 0.0, degrees["shoulder_lift"]]


class ContactReleaseOnlyTests(unittest.TestCase):
    def setup_case(self):
        follower = FakeFollower()
        leader = FakeLeader()
        clock = Clock()
        armed = {"yes": False}
        writes = make_write_firewall(follower.bus,
                                     allow_arm_goal=lambda: armed["yes"])
        return follower, leader, clock, armed, writes

    def test_startup_and_first_goal_skipped_then_arm_only(self):
        follower, leader, clock, armed, writes = self.setup_case()

        def arm_confirm():
            self.assertEqual(writes, [])  # 3 seconds + origin: no Goal.
            return True

        post_arm_checks = {"count": 0}
        def stop_requested():
            if armed["yes"] is True and len(writes) == 0:
                post_arm_checks["count"] += 1
                if post_arm_checks["count"] == 2:
                    leader.position["shoulder_lift.pos"] += 1.0
                    leader.position["gripper.pos"] -= 15.0  # Must be ignored.
                    armed["yes"] = "moved"
            return len(writes) >= 1

        def send_arm(action, _previous_elbow):
            follower.bus.sync_write("Goal_Position",
                                    {key.removesuffix(".pos"): value
                                     for key, value in action.items()})
            return dict(action)

        result = run_contact_release(
            leader=leader, follower=follower, fk=fk, send_arm=send_arm,
            stop_requested=stop_requested, arm_confirm=arm_confirm,
            enable_arm_goals=lambda: armed.update(yes=True),
            monotonic=clock.monotonic, sleep=clock.sleep)
        self.assertEqual(result["status"], "STOPPED")
        self.assertTrue(result["first_goal_skipped"])
        self.assertGreaterEqual(result["stillness_samples"], 30)
        self.assertEqual(result["arm_goal_sends"], 1)
        self.assertEqual(len(result["final_read_only"]), 3)
        self.assertEqual(len(writes), 1)
        self.assertEqual(set(writes[0]), set(ARM_JOINTS))
        self.assertEqual(follower.bus.config_writes, 0)
        self.assertEqual(follower.bus.torque_writes, 0)

    def test_stop_before_arm_no_goal(self):
        follower, leader, clock, armed, writes = self.setup_case()
        result = run_contact_release(
            leader=leader, follower=follower, fk=fk,
            send_arm=lambda *_: self.fail("send unexpectedly called"),
            stop_requested=lambda: False, arm_confirm=lambda: False,
            enable_arm_goals=lambda: self.fail("armed unexpectedly"),
            monotonic=clock.monotonic, sleep=clock.sleep)
        self.assertEqual(result["status"], "STOPPED_BEFORE_ARM")
        self.assertEqual(writes, [])

    def test_torque_off_aborts_before_goal(self):
        follower, leader, clock, armed, writes = self.setup_case()
        follower.bus.torque["elbow_flex"] = 0
        with self.assertRaisesRegex(RuntimeError, "requires_unchanged_torque_on"):
            run_contact_release(
                leader=leader, follower=follower, fk=fk,
                send_arm=lambda *_: self.fail("send unexpectedly called"),
                stop_requested=lambda: False, arm_confirm=lambda: True,
                enable_arm_goals=lambda: self.fail("armed unexpectedly"),
                monotonic=clock.monotonic, sleep=clock.sleep)
        self.assertEqual(writes, [])

    def test_leader_not_passive_aborts_before_goal(self):
        follower, leader, clock, armed, writes = self.setup_case()
        leader.bus.torque["shoulder_lift"] = 1
        with self.assertRaisesRegex(RuntimeError, "leader_not_passive"):
            run_contact_release(
                leader=leader, follower=follower, fk=fk,
                send_arm=lambda *_: self.fail("send unexpectedly called"),
                stop_requested=lambda: False, arm_confirm=lambda: True,
                enable_arm_goals=lambda: self.fail("armed unexpectedly"),
                monotonic=clock.monotonic, sleep=clock.sleep)
        self.assertEqual(writes, [])

    def test_leader_motion_during_stillness_aborts(self):
        follower, leader, clock, armed, writes = self.setup_case()
        def move(_duration):
            clock.sleep(_duration)
            leader.position["shoulder_lift.pos"] += 1.0
        with self.assertRaisesRegex(RuntimeError, "leader_moved_during_startup"):
            run_contact_release(
                leader=leader, follower=follower, fk=fk,
                send_arm=lambda *_: self.fail("send unexpectedly called"),
                stop_requested=lambda: False, arm_confirm=lambda: True,
                enable_arm_goals=lambda: self.fail("armed unexpectedly"),
                monotonic=clock.monotonic, sleep=move)
        self.assertEqual(writes, [])

    def test_downward_target_aborts_without_goal(self):
        follower, leader, clock, armed, writes = self.setup_case()
        def arm_confirm():
            return True
        post_arm_checks = {"count": 0}
        def stop_requested():
            if armed["yes"] is True:
                post_arm_checks["count"] += 1
                if post_arm_checks["count"] == 2:
                    leader.position["shoulder_lift.pos"] -= 1.0
                    armed["yes"] = "moved"
            return False
        with self.assertRaisesRegex(RuntimeError, "target_not_upward"):
            run_contact_release(
                leader=leader, follower=follower, fk=fk,
                send_arm=lambda *_: self.fail("send unexpectedly called"),
                stop_requested=stop_requested, arm_confirm=arm_confirm,
                enable_arm_goals=lambda: armed.update(yes=True),
                monotonic=clock.monotonic, sleep=clock.sleep)
        self.assertEqual(writes, [])

    def test_firewall_denies_torque_config_gripper_and_prearm_arm(self):
        follower, leader, clock, armed, writes = self.setup_case()
        bus = follower.bus
        with self.assertRaisesRegex(RuntimeError, "forbids_config_or_torque"):
            bus.disable_torque()
        with self.assertRaisesRegex(RuntimeError, "forbids_config_or_torque"):
            bus.write("Operating_Mode", "gripper", 0)
        with self.assertRaisesRegex(RuntimeError, "forbids_config_or_torque"):
            bus.write_calibration({})
        with self.assertRaisesRegex(RuntimeError, "forbids_non_arm_goal"):
            bus.sync_write("Goal_Position", {name: 10 for name in ARM_JOINTS})
        armed["yes"] = True
        with self.assertRaisesRegex(RuntimeError, "forbids_non_arm_goal"):
            bus.sync_write("Goal_Position", {name: 10 for name in JOINTS})
        self.assertEqual(writes, [])
        self.assertEqual(bus.config_writes, 0)
        self.assertEqual(bus.torque_writes, 0)


if __name__ == "__main__":
    unittest.main()
