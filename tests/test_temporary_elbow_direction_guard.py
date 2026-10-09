import logging
import unittest

from scripts.temporary_elbow_direction_guard import (
    enforce_elbow_target, guarded_elbow_send,
    evaluate_elbow_target, evaluate_elbow_recovery_target,
    guarded_elbow_recovery_send,
)


class TemporaryElbowDirectionGuardTests(unittest.TestCase):
    def test_fake_bus_holds_upper_request_then_resumes_away_without_ending_session(self):
        class FakeBus:
            current = 96.307692

            def read(self, register, motor, *, num_retry):
                self.last_read = (register, motor, num_retry)
                return self.current

        class FakeRobot:
            calibration = {"elbow_flex": {"range_min": 880, "range_max": 3087}}
            def __init__(self):
                self.bus = FakeBus()
                self.sent = []

            def send_action(self, action):
                self.sent.append(dict(action))
                return dict(action)

        robot = FakeRobot()
        logger = logging.getLogger("test.elbow_fake_bus")
        action = {"shoulder_pan.pos": 11.74, "elbow_flex.pos": 96.5,
                  "wrist_flex.pos": 5.54}
        self.assertIsNone(guarded_elbow_send(robot, action, 96.307692, logger))
        self.assertEqual(robot.sent, [])
        self.assertEqual(robot.bus.last_read, ("Present_Position", "elbow_flex", 0))
        action["elbow_flex.pos"] = 95.5
        self.assertEqual(guarded_elbow_send(robot, action, 96.307692, logger), action)
        robot.bus.current = 95.5
        action["elbow_flex.pos"] = 94.5
        self.assertEqual(guarded_elbow_send(robot, action, 95.5, logger), action)
        self.assertEqual(len(robot.sent), 2)
        self.assertEqual(robot.sent[0]["shoulder_pan.pos"], 11.74)
        self.assertEqual(robot.sent[0]["wrist_flex.pos"], 5.54)

    def test_near_upper_moving_toward_limit_is_blocked(self):
        result = evaluate_elbow_target(86.99, 87.8, 86.99)
        self.assertEqual(result.action, "HOLD")
        self.assertEqual(result.reason, "blocked_toward_upper_limit")
        self.assertAlmostEqual(result.upper_margin_deg, 3.01)

    def test_near_upper_moving_away_is_allowed(self):
        result = evaluate_elbow_target(86.99, 86.0, 86.99)
        self.assertEqual(result.action, "SEND")
        self.assertIsNone(result.reason)

    def test_many_small_decreases_toward_safe_start_are_allowed(self):
        previous = 86.99
        for target in [85.99 - i for i in range(53)] + [32.44]:
            result = evaluate_elbow_target(previous, target, previous)
            self.assertEqual(result.action, "SEND")
            self.assertIsNone(result.reason, (target, result.reason))
            previous = target

    def test_target_above_urdf_is_always_blocked(self):
        result = evaluate_elbow_target(89.5, 90.1, 89.5)
        self.assertEqual((result.action, result.reason),
                         ("ABORT", "target_outside_servo_calibration"))

        class Robot:
            calibration = {"elbow_flex": {"range_min": 880, "range_max": 3087}}
            def __init__(self):
                self.bus = type("Bus", (), {"read": lambda *_a, **_kw: 89.5})()
                self.sent = []

            def send_action(self, action):
                self.sent.append(action)
                return action

        robot = Robot()
        with self.assertRaisesRegex(RuntimeError, "target_outside_servo_calibration"):
            guarded_elbow_send(robot, {"elbow_flex.pos": 97.1}, 89.5,
                               logging.getLogger("test.hard_urdf"))
        self.assertEqual(robot.sent, [])

    def test_lower_limit_direction_is_symmetric(self):
        self.assertEqual(
            (evaluate_elbow_target(-96.99, -97.8, -96.99).action,
             evaluate_elbow_target(-96.99, -97.8, -96.99).reason),
            ("HOLD", "blocked_toward_lower_limit"),
        )
        self.assertEqual(evaluate_elbow_target(-96.99, -96.0, -96.99).action, "SEND")
        self.assertEqual((evaluate_elbow_target(-99.5, -100.01, -99.5).action,
                          evaluate_elbow_target(-99.5, -100.01, -99.5).reason),
                         ("ABORT", "target_outside_servo_calibration"))

    def test_large_away_jump_is_blocked_without_clipping(self):
        result = evaluate_elbow_target(86.99, 80.0, 86.99)
        self.assertEqual(result.action, "ABORT")
        self.assertEqual(result.reason, "command_step_over_2_deg")
        self.assertEqual(result.target_deg, 80.0)

    def test_small_steps_cannot_creep_into_limit_reserve(self):
        result = evaluate_elbow_target(87.9, 88.1, 87.9)
        self.assertEqual((result.action, result.reason),
                         ("HOLD", "blocked_toward_upper_limit"))

    def test_decision_diagnostics_are_logged_before_hold_and_abort(self):
        logger = logging.getLogger("test.temporary_elbow_direction_guard")
        with self.assertLogs(logger, level="INFO") as captured:
            self.assertEqual(enforce_elbow_target(88.747, 88.835, 88.747, logger).action,
                             "HOLD")
            self.assertEqual(enforce_elbow_target(88.747, 88.0, 88.747, logger).action,
                             "SEND")
            with self.assertRaisesRegex(RuntimeError, "target_outside_servo_calibration"):
                enforce_elbow_target(89.5, 90.1, 89.5, logger)
        line = captured.output[0]
        for field in (
            "joint=elbow_flex",
            "current=88.747",
            "requested_target=88.835",
            "delta=0.088",
            "lower_margin=188.747",
            "upper_margin=1.253",
            "direction=toward_limit",
            "limit=upper",
            "action=HOLD",
            "reason=blocked_toward_upper_limit",
        ):
            self.assertIn(field, line)
        self.assertIn("action=SEND", captured.output[1])
        self.assertIn("action=ABORT", captured.output[2])

    def test_feedback_and_send_errors_still_abort(self):
        class BrokenFeedback:
            def read(self, *_args, **_kwargs):
                raise TimeoutError("feedback_timeout")

        class Robot:
            calibration = {"elbow_flex": {"range_min": 880, "range_max": 3087}}
            bus = BrokenFeedback()

            def send_action(self, _action):
                raise IOError("transport_failure")

        robot = Robot()
        action = {"elbow_flex.pos": 88.0}
        with self.assertRaisesRegex(TimeoutError, "feedback_timeout"):
            guarded_elbow_send(robot, action, 88.0, logging.getLogger("test.feedback"))

        robot.bus = type("GoodFeedback", (), {"read": lambda *_a, **_kw: 88.0})()
        with self.assertRaisesRegex(IOError, "transport_failure"):
            guarded_elbow_send(robot, action, 88.0, logging.getLogger("test.transport"))

    def test_manual_guard_uses_servo_calibration_not_urdf_upper(self):
        bounds = {"lower_deg": -97.010989, "upper_deg": 97.010989}
        self.assertEqual(evaluate_elbow_target(96.307692, 95.5, 96.307692,
                                               **bounds).action, "SEND")
        self.assertEqual(evaluate_elbow_target(96.307692, 96.5, 96.307692,
                                               **bounds).action, "HOLD")
        result = evaluate_elbow_target(96.307692, 97.1, 96.307692, **bounds)
        self.assertEqual((result.action, result.reason),
                         ("ABORT", "target_outside_servo_calibration"))

    def test_recovery_outside_upper_holds_until_small_inward_target_then_sends_once(self):
        logger = logging.getLogger("test.elbow_recovery")
        feedback = {"shoulder_pan": 20.97, "shoulder_lift": -42.42,
                    "elbow_flex": 90.33, "wrist_flex": -30.99,
                    "wrist_roll": 2.86, "gripper": 22.03}

        class FakeBus:
            def sync_read(self, register, *, num_retry):
                self.last_read = (register, num_retry)
                return dict(feedback)

        class FakeRobot:
            bus = FakeBus()

            def __init__(self):
                self.sent = []

            def send_action(self, action):
                self.sent.append(dict(action))
                return dict(action)

        robot = FakeRobot()
        action = {f"{joint}.pos": value for joint, value in feedback.items()}
        self.assertIsNone(guarded_elbow_recovery_send(robot, action, 90.33, logger))
        self.assertEqual(robot.sent, [])
        action["elbow_flex.pos"] = 90.1
        self.assertIsNone(guarded_elbow_recovery_send(robot, action, 90.33, logger))
        self.assertEqual(robot.sent, [])
        action["elbow_flex.pos"] = 89.0
        action["shoulder_pan.pos"] = feedback["shoulder_pan"] + 0.5
        sent = guarded_elbow_recovery_send(robot, action, 90.33, logger)
        self.assertEqual(robot.bus.last_read, ("Present_Position", 0))
        self.assertEqual(sent["elbow_flex.pos"], 89.0)
        self.assertEqual(sent["shoulder_pan.pos"], feedback["shoulder_pan"])
        self.assertEqual(len(robot.sent), 1)
        feedback["elbow_flex"] = 89.7
        self.assertIsNone(guarded_elbow_recovery_send(robot, action, 89.0, logger))
        feedback["elbow_flex"] = 89.1
        self.assertIsNone(guarded_elbow_recovery_send(robot, action, 89.0, logger))
        self.assertEqual(len(robot.sent), 1)

    def test_recovery_never_sends_outside_target_or_large_jump(self):
        self.assertEqual(evaluate_elbow_target(90.33, 89.0, 90.33).reason,
                         "feedback_outside_servo_calibration")
        for target in (90.1, 90.33, 90.8, 89.7, 88.7):
            self.assertEqual(evaluate_elbow_recovery_target(90.33, target, 90.33).action,
                             "HOLD")
        self.assertEqual(evaluate_elbow_recovery_target(90.33, 89.0, 90.33).action,
                         "SEND")
        self.assertEqual(evaluate_elbow_recovery_target(90.33, 89.0, 92.0).action,
                         "ABORT")
        self.assertEqual(evaluate_elbow_recovery_target(91.01, 89.0, 91.01).action,
                         "ABORT")
        self.assertEqual(evaluate_elbow_recovery_target(96.307692, 89.0, 96.307692).action,
                         "ABORT")
        self.assertEqual(evaluate_elbow_recovery_target(-100.1, -99.0, -100.1).action,
                         "ABORT")

    def test_recovery_non_elbow_mismatch_and_feedback_errors_abort_without_send(self):
        class FakeBus:
            def sync_read(self, *_args, **_kwargs):
                return {"shoulder_pan": 20.0, "shoulder_lift": -42.0,
                        "elbow_flex": 90.33, "wrist_flex": -31.0,
                        "wrist_roll": 3.0, "gripper": 22.0}

        class FakeRobot:
            bus = FakeBus()

            def __init__(self):
                self.sent = []

            def send_action(self, action):
                self.sent.append(action)
                return action

        robot = FakeRobot()
        action = {"shoulder_pan.pos": 23.0, "shoulder_lift.pos": -42.0,
                  "elbow_flex.pos": 89.0, "wrist_flex.pos": -31.0,
                  "wrist_roll.pos": 3.0, "gripper.pos": 22.0}
        with self.assertRaisesRegex(RuntimeError, "shoulder_pan_alignment_or_feedback"):
            guarded_elbow_recovery_send(robot, action, 90.33,
                                        logging.getLogger("test.recovery_other_axis"))
        self.assertEqual(robot.sent, [])
        robot.bus.sync_read = lambda *_a, **_kw: (_ for _ in ()).throw(TimeoutError("feedback_timeout"))
        with self.assertRaisesRegex(TimeoutError, "feedback_timeout"):
            guarded_elbow_recovery_send(robot, action, 90.33,
                                        logging.getLogger("test.recovery_feedback"))
        self.assertEqual(robot.sent, [])


if __name__ == "__main__":
    unittest.main()
