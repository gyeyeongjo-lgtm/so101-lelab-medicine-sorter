import unittest
import logging

from scripts.relative_start_teleop import (
    ACTION_KEYS,
    JOINTS,
    RelativeOrigins,
    calibrated_action_bounds,
    capture_origins,
    dispatch_guarded_relative_action,
    first_relative_target,
    out_of_range_targets,
    oversized_arm_steps,
    relative_target,
    teleop_mode,
)
from scripts.temporary_elbow_direction_guard import guarded_elbow_send


def action(**overrides):
    result = {key: (50.0 if key == "gripper.pos" else 0.0) for key in ACTION_KEYS}
    result.update({f"{joint}.pos": value for joint, value in overrides.items()})
    return result


class RelativeStartTeleopTests(unittest.TestCase):
    class FakeBus:
        def __init__(self, current):
            self.current = current
            self.register_writes = []

        def read(self, register, motor, *, num_retry):
            self.last_read = (register, motor, num_retry)
            return self.current

        def write(self, *args, **kwargs):
            self.register_writes.append(("write", args, kwargs))
            raise AssertionError("guard must not write motor registers")

        def sync_write(self, *args, **kwargs):
            self.register_writes.append(("sync_write", args, kwargs))
            raise AssertionError("guard must not write motor registers")

    class FakeRobot:
        calibration = {"elbow_flex": {"range_min": 880, "range_max": 3087}}

        def __init__(self, current):
            self.bus = RelativeStartTeleopTests.FakeBus(current)
            self.sent = []

        def send_action(self, target):
            self.sent.append(dict(target))
            return dict(target)

    def dispatch(self, robot, target, previous_elbow, previous_target):
        return dispatch_guarded_relative_action(
            target,
            previous_elbow,
            previous_target,
            lambda candidate, previous: guarded_elbow_send(
                robot, candidate, previous, logging.getLogger("test.relative_dispatch")
            ),
        )

    def test_absolute_remains_default_and_relative_is_explicit(self):
        self.assertEqual(teleop_mode({}), "absolute")
        self.assertEqual(teleop_mode({"LELAB_TELEOP_MODE": "relative_start"}), "relative_start")
        with self.assertRaisesRegex(ValueError, "unsupported"):
            teleop_mode({"LELAB_TELEOP_MODE": "relative"})

    def test_origin_reads_are_fresh_sequential_snapshots_and_issue_no_send(self):
        calls = []
        leader = action(elbow_flex=30.0)
        follower = {key.removesuffix(".pos"): value
                    for key, value in action(elbow_flex=90.0).items()}
        origins = capture_origins(
            lambda: calls.append("leader") or leader,
            lambda: calls.append("follower") or follower,
        )
        self.assertEqual(calls, ["leader", "follower"])
        self.assertEqual(origins.leader["elbow_flex.pos"], 30.0)
        self.assertEqual(origins.follower["elbow_flex.pos"], 90.0)

    def test_first_target_is_exact_follower_pose_even_if_leader_changes_next(self):
        origins = RelativeOrigins(action(elbow_flex=30.0), action(elbow_flex=90.0))
        first = first_relative_target(origins)
        self.assertEqual(first, origins.follower)

    def test_relative_arm_and_gripper_delta_use_calibrated_action_units(self):
        origins = RelativeOrigins(
            action(elbow_flex=30.0, gripper=20.0),
            action(elbow_flex=90.0, gripper=70.0),
        )
        target = relative_target(action(elbow_flex=25.0, gripper=15.0), origins)
        self.assertEqual(target["elbow_flex.pos"], 85.0)
        self.assertEqual(target["gripper.pos"], 65.0)
        self.assertEqual(target["shoulder_pan.pos"], 0.0)

    def test_loaded_calibration_limits_use_le_robot_normalization_for_all_six_axes(self):
        class Bus:
            motors = {joint: type("Motor", (), {"id": index + 1}) for index, joint in enumerate(JOINTS)}
            calibration = {
                joint: {"range_min": 100, "range_max": 900} for joint in JOINTS
            }

            @staticmethod
            def _normalize(raw):
                motor_id, value = next(iter(raw.items()))
                if motor_id == 6:
                    return {motor_id: ((value - 100) / 800) * 100}
                return {motor_id: ((value - 500) / 10)}

        class Robot:
            bus = Bus()

        bounds = calibrated_action_bounds(Robot())
        self.assertEqual(set(bounds), set(JOINTS))
        self.assertEqual(bounds["shoulder_pan"], (-40.0, 40.0))
        self.assertEqual(bounds["gripper"], (0.0, 100.0))

    def test_out_of_range_is_reported_without_clipping(self):
        target = action(elbow_flex=97.0, gripper=101.0)
        bounds = {joint: ((0.0, 100.0) if joint == "gripper" else (-90.0, 90.0))
                  for joint in JOINTS}
        violations = out_of_range_targets(target, bounds)
        self.assertEqual(violations["elbow_flex"], (97.0, -90.0, 90.0))
        self.assertEqual(violations["gripper"], (101.0, 0.0, 100.0))
        self.assertEqual(target["elbow_flex.pos"], 97.0)
        self.assertEqual(target["gripper.pos"], 101.0)

    def test_missing_non_finite_or_invalid_range_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "missing"):
            relative_target({"shoulder_pan.pos": 0.0}, RelativeOrigins(action(), action()))
        bad = action(elbow_flex=float("nan"))
        with self.assertRaisesRegex(ValueError, "non-finite"):
            capture_origins(lambda: bad, action)
        with self.assertRaisesRegex(ValueError, "invalid calibrated follower range"):
            out_of_range_targets(action(), {joint: (0.0, 0.0) for joint in JOINTS})

    def test_all_arm_axes_keep_existing_two_degree_single_step_guard(self):
        previous = action(gripper=20.0)
        target = action(shoulder_pan=2.1, wrist_roll=-2.2, gripper=35.0)
        violations = oversized_arm_steps(target, previous)
        self.assertEqual(violations["shoulder_pan"], (0.0, 2.1, 2.1))
        self.assertEqual(violations["wrist_roll"], (0.0, -2.2, -2.2))
        self.assertNotIn("gripper", violations)

    def test_arm_step_guard_accepts_first_stationary_target_and_two_degree_edge(self):
        previous = action(elbow_flex=90.0)
        self.assertEqual(oversized_arm_steps(dict(previous), previous), {})
        self.assertEqual(
            oversized_arm_steps(action(elbow_flex=88.0), previous), {}
        )

    def test_guard_hold_sends_zero_actions(self):
        previous = action(elbow_flex=96.307692)
        robot = self.FakeRobot(96.307692)
        result = self.dispatch(robot, action(elbow_flex=96.5), 96.307692, previous)
        self.assertFalse(result.sent)
        self.assertEqual(robot.sent, [])
        self.assertEqual(result.previous_relative_target, previous)

    def test_guard_send_sends_exactly_one_action(self):
        previous = action(elbow_flex=96.307692)
        target = action(elbow_flex=95.5)
        robot = self.FakeRobot(96.307692)
        result = self.dispatch(robot, target, 96.307692, previous)
        self.assertTrue(result.sent)
        self.assertEqual(robot.sent, [target])
        self.assertEqual(result.previous_relative_target, target)

    def test_guard_abort_sends_zero_actions(self):
        previous = action(elbow_flex=96.307692)
        robot = self.FakeRobot(96.307692)
        with self.assertRaisesRegex(RuntimeError, "target_outside_servo_calibration"):
            self.dispatch(robot, action(elbow_flex=97.1), 96.307692, previous)
        self.assertEqual(robot.sent, [])

    def test_hold_then_away_target_can_send_next_cycle(self):
        previous = action(elbow_flex=96.307692)
        robot = self.FakeRobot(96.307692)
        held = self.dispatch(robot, action(elbow_flex=96.5), 96.307692, previous)
        sent = self.dispatch(
            robot, action(elbow_flex=95.5),
            held.previous_elbow_target_deg, held.previous_relative_target,
        )
        self.assertFalse(held.sent)
        self.assertTrue(sent.sent)
        self.assertEqual(len(robot.sent), 1)
        self.assertEqual(robot.sent[0]["elbow_flex.pos"], 95.5)

    def test_hold_does_not_write_goal_or_torque_registers(self):
        previous = action(elbow_flex=96.307692)
        robot = self.FakeRobot(96.307692)
        self.dispatch(robot, action(elbow_flex=96.5), 96.307692, previous)
        self.assertEqual(robot.bus.register_writes, [])


if __name__ == "__main__":
    unittest.main()
