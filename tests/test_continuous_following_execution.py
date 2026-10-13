import time
import unittest

from scripts.continuous_following_execution import (
    ARM_NAMES,
    ContinuousFollowingCycle,
    FollowingTelemetry,
)
from scripts.live_c_approach import interpolate_goals
from scripts.staged_cycle_execution import Feedback, JOINT_UNITS


START = {name: (50.0 if name == "gripper" else 0.0) for name in JOINT_UNITS}
FINAL_TOLERANCES = {name: (2.0 if name == "gripper" else 1.6)
                    for name in JOINT_UNITS}
FOLLOWING_LIMITS = {name: (4.0 if name == "elbow_flex" else 2.5)
                    for name in ARM_NAMES}


def goal(value):
    return {name: (50.0 if name == "gripper" else float(value)) for name in JOINT_UNITS}


def offset(source, **changes):
    result = dict(source)
    for name, delta in changes.items():
        result[name] += delta
    return result


class FakeFollowingTransport:
    def __init__(self, samples, *, start=START, temperature_c=38,
                 moving_override=None):
        self.samples = [dict(sample) if not isinstance(sample, Exception) else sample
                        for sample in samples]
        self.start = dict(start)
        self.last_positions = dict(start)
        self.sent = []
        self.quiescent = True
        self.temperature_c = temperature_c
        self.moving_override = moving_override

    def send_goal(self, target):
        self.sent.append(dict(target))
        return dict(target)

    def read_following_telemetry(self):
        if self.samples:
            sample = self.samples.pop(0)
            if isinstance(sample, Exception):
                raise sample
            self.last_positions = dict(sample)
        positions = dict(self.last_positions)
        active_goal = self.sent[-1] if self.sent else self.start
        moving = {
            name: int(abs(positions[name] - active_goal[name]) > 0.1)
            for name in JOINT_UNITS
        }
        if self.moving_override is not None:
            moving = {name: int(self.moving_override) for name in JOINT_UNITS}
        return FollowingTelemetry(
            positions=positions,
            received_monotonic=time.monotonic(),
            goal_raw={name: round(active_goal[name] * 10) for name in JOINT_UNITS},
            present_raw={name: round(positions[name] * 10) for name in JOINT_UNITS},
            moving=moving,
            present_load={name: (140 if name == "elbow_flex" else 0)
                          for name in JOINT_UNITS},
            temperature_c={name: self.temperature_c for name in JOINT_UNITS},
        )

    def read_feedback(self):
        return Feedback(dict(self.last_positions), time.monotonic())

    def is_quiescent(self):
        return self.quiescent

    def stop_commands(self):
        pass


def make_cycle(fake, *, planned_start=START, no_progress=0.02, final_timeout=0.03):
    return ContinuousFollowingCycle(
        fake, FINAL_TOLERANCES,
        planned_start=planned_start,
        following_limits=FOLLOWING_LIMITS,
        max_joint_step_deg=1.0,
        cadence_s=0.001,
        no_progress_timeout_s=no_progress,
        progress_epsilon_deg=0.1,
        final_timeout_s=final_timeout,
        feedback_max_age_s=0.05,
        stable_s=0.002,
        poll_s=0.001,
    )


class ContinuousFollowingCycleTests(unittest.TestCase):
    def test_full_current_pose_to_existing_endpoint_uses_107_bounded_sends(self):
        start = {
            "shoulder_pan": -9.538461538461538,
            "shoulder_lift": -94.72527472527473,
            "elbow_flex": 87.95604395604396,
            "wrist_flex": 71.95604395604396,
            "wrist_roll": -15.164835164835164,
            "gripper": 1.9583843329253363,
        }
        target = {
            "shoulder_pan": -0.014220,
            "shoulder_lift": 11.507515,
            "elbow_flex": 14.866481,
            "wrist_flex": 12.933013,
            "wrist_roll": 13.899293,
        }
        goals = interpolate_goals(start, target, 1.0)
        samples = [start]
        for item in goals[:-1]:
            samples.append(offset(item, elbow_flex=3.0, shoulder_lift=2.0))
        samples.extend([goals[-1], goals[-1], goals[-1]])
        fake = FakeFollowingTransport(samples, start=start)
        controller = make_cycle(fake, planned_start=start, final_timeout=0.3)
        controller.start_stage("approach", goals, approved=True)
        self.assertTrue(controller.wait_worker(2))
        self.assertEqual(len(goals), 107)
        self.assertEqual(len(fake.sent), 107)
        self.assertEqual(controller.reach_state, "GOAL_REACHED")
        self.assertEqual(controller.task_state, "USER_CONFIRMATION_REQUIRED")
        for name in ARM_NAMES:
            self.assertAlmostEqual(fake.sent[-1][name], target[name], places=9)

    def test_two_to_three_degree_lag_continues_without_settling(self):
        goals = [goal(1), goal(2), goal(3)]
        fake = FakeFollowingTransport([
            START,
            offset(goals[0], elbow_flex=3.0, shoulder_lift=2.0),
            offset(goals[1], elbow_flex=2.5, shoulder_lift=2.0),
            goals[2], goals[2], goals[2],
        ])
        controller = make_cycle(fake)
        controller.start_stage("approach", goals, approved=True)
        self.assertTrue(controller.wait_worker(1))
        self.assertEqual(len(fake.sent), 3)
        self.assertEqual(controller.reach_state, "GOAL_REACHED")
        self.assertEqual(controller.task_state, "USER_CONFIRMATION_REQUIRED")
        self.assertFalse(any(row["action"] == "PAUSE" and
                             row["detail"] == "following_limit_exceeded"
                             for row in controller.following_log))
        self.assertTrue(all(row["temperature_c"] == {
            name: 38 for name in JOINT_UNITS
        } for row in controller.following_log))

    def test_temperature_over_55_blocks_before_any_send(self):
        fake = FakeFollowingTransport([START], temperature_c=56)
        controller = make_cycle(fake)
        controller.start_stage("approach", [goal(1)], approved=True)
        self.assertTrue(controller.wait_worker(1))
        self.assertEqual(fake.sent, [])
        self.assertIn("following_temperature_limit_exceeded", controller.failure)
        self.assertNotEqual(controller.reach_state, "GOAL_REACHED")

    def test_final_moving_nonzero_never_passes(self):
        final = goal(1)
        fake = FakeFollowingTransport(
            [START, final] + [final] * 30,
            moving_override=1,
        )
        controller = make_cycle(fake, final_timeout=0.01)
        controller.start_stage("approach", [final], approved=True)
        self.assertTrue(controller.wait_worker(1))
        self.assertEqual(len(fake.sent), 1)
        self.assertEqual(controller.failure, "final_joint_target_timeout")
        self.assertNotEqual(controller.reach_state, "GOAL_REACHED")
        self.assertNotEqual(controller.task_state, "USER_CONFIRMATION_REQUIRED")

    def test_elbow_over_four_degrees_pauses_then_resumes(self):
        goals = [goal(1), goal(2)]
        fake = FakeFollowingTransport([
            START,
            offset(goals[0], elbow_flex=4.5),
            offset(goals[0], elbow_flex=4.2),
            offset(goals[0], elbow_flex=3.5),
            goals[1], goals[1], goals[1],
        ])
        controller = make_cycle(fake)
        controller.start_stage("approach", goals, approved=True)
        self.assertTrue(controller.wait_worker(1))
        self.assertEqual(len(fake.sent), 2)
        actions = [row["action"] for row in controller.following_log]
        self.assertIn("PAUSE", actions)
        self.assertIn("RESUME", actions)
        self.assertLess(actions.index("PAUSE"), actions.index("RESUME"))
        self.assertEqual(controller.reach_state, "GOAL_REACHED")

    def test_no_progress_aborts_without_next_send_fallthrough(self):
        goals = [goal(1), goal(2)]
        stuck = offset(goals[0], elbow_flex=4.5)
        fake = FakeFollowingTransport([START, stuck] + [stuck] * 30)
        controller = make_cycle(fake, no_progress=0.01)
        controller.start_stage("approach", goals, approved=True)
        self.assertTrue(controller.wait_worker(1))
        self.assertEqual(len(fake.sent), 1)
        self.assertEqual(controller.failure, "following_no_progress_timeout")
        self.assertEqual(controller.following_log[-1]["action"], "ABORT")
        self.assertNotEqual(controller.task_state, "USER_CONFIRMATION_REQUIRED")

    def test_persistently_increasing_error_aborts_without_fallthrough(self):
        goals = [goal(1), goal(2)]
        fake = FakeFollowingTransport([
            START,
            offset(goals[0], elbow_flex=4.5),
            offset(goals[0], elbow_flex=4.7),
            offset(goals[0], elbow_flex=4.9),
            offset(goals[0], elbow_flex=5.1),
        ])
        controller = make_cycle(fake)
        controller.start_stage("approach", goals, approved=True)
        self.assertTrue(controller.wait_worker(1))
        self.assertEqual(len(fake.sent), 1)
        self.assertEqual(controller.failure, "following_error_persistently_increasing")
        self.assertEqual(controller.following_log[-1]["action"], "ABORT")

    def test_final_outside_one_point_six_never_passes(self):
        final = goal(1)
        outside = offset(final, elbow_flex=2.0)
        fake = FakeFollowingTransport([START, outside] + [outside] * 30)
        controller = make_cycle(fake, final_timeout=0.01)
        controller.start_stage("approach", [final], approved=True)
        self.assertTrue(controller.wait_worker(1))
        self.assertEqual(len(fake.sent), 1)
        self.assertEqual(controller.failure, "final_joint_target_timeout")
        self.assertNotEqual(controller.reach_state, "GOAL_REACHED")
        self.assertNotEqual(controller.task_state, "USER_CONFIRMATION_REQUIRED")

    def test_abnormal_step_aborts_before_any_send(self):
        fake = FakeFollowingTransport([START])
        controller = make_cycle(fake)
        controller.start_stage("approach", [goal(1.01)], approved=True)
        self.assertTrue(controller.wait_worker(1))
        self.assertEqual(fake.sent, [])
        self.assertIn("continuous_path_step", controller.failure)
        self.assertEqual(controller.following_log[-1]["action"], "ABORT")

    def test_feedback_error_aborts_without_next_send(self):
        goals = [goal(1), goal(2)]
        fake = FakeFollowingTransport([START, ConnectionError("bad packet")])
        controller = make_cycle(fake)
        controller.start_stage("approach", goals, approved=True)
        self.assertTrue(controller.wait_worker(1))
        self.assertEqual(len(fake.sent), 1)
        self.assertIn("following_feedback_error", controller.failure)
        self.assertEqual(controller.following_log[-1]["action"], "ABORT")


if __name__ == "__main__":
    unittest.main()
