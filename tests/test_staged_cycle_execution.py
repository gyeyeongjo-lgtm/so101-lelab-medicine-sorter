import threading
import time
import unittest

from scripts.staged_cycle_execution import Feedback, JOINT_UNITS, StagedCycle


GOAL = {name: (50.0 if name == "gripper" else 1.0) for name in JOINT_UNITS}
TOLERANCES = {name: (2.0 if name == "gripper" else 0.5) for name in JOINT_UNITS}


class FakeTransport:
    def __init__(self):
        self.sent = []
        self.positions = dict(GOAL)
        self.feedback_time = None
        self.started = threading.Event()
        self.release_send = threading.Event()
        self.block_send = False
        self.quiescent = True
        self.clip = False

    def send_goal(self, goal):
        self.started.set()
        if self.block_send:
            self.release_send.wait(1)
        self.sent.append(dict(goal))
        return {**goal, "elbow_flex": goal["elbow_flex"] + 1} if self.clip else goal

    def read_feedback(self):
        return Feedback(self.positions, self.feedback_time if self.feedback_time is not None
                        else time.monotonic())

    def is_quiescent(self):
        return self.quiescent


def cycle(transport, **policy):
    return StagedCycle(transport, TOLERANCES, timeout_s=policy.get("timeout_s", 0.1),
                       feedback_max_age_s=policy.get("feedback_max_age_s", 0.05),
                       stable_s=policy.get("stable_s", 0), poll_s=0.001)


class StagedCycleTests(unittest.TestCase):
    def test_final_waypoint_uses_only_final_timeout_override(self):
        fake = FakeTransport()

        class RecordingCycle(StagedCycle):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.seen_timeouts = []

            def _run_goal(self, goal, *, timeout_s):
                self.seen_timeouts.append(timeout_s)
                self.reach_state = "GOAL_REACHED"
                self.waypoints_reached += 1
                return True

        controller = RecordingCycle(
            fake, TOLERANCES, timeout_s=0.1, final_timeout_s=0.25,
            feedback_max_age_s=0.05, stable_s=0, poll_s=0.001)
        controller.start_stage("approach", [GOAL, GOAL, GOAL], approved=True)
        self.assertTrue(controller.wait_worker(1))
        self.assertEqual(controller.seen_timeouts, [0.1, 0.1, 0.25])

    def test_send_reach_and_task_are_distinct_and_no_auto_advance(self):
        fake = FakeTransport()
        controller = cycle(fake)
        with self.assertRaisesRegex(ValueError, "approval"):
            controller.start_stage("approach", GOAL, approved=False)
        controller.start_stage("approach", GOAL, approved=True)
        self.assertTrue(controller.wait_worker(1))
        self.assertEqual(controller.command_state, "TRANSMITTED_UNACKNOWLEDGED")
        self.assertEqual(controller.reach_state, "GOAL_REACHED")
        self.assertEqual(controller.task_state, "USER_CONFIRMATION_REQUIRED")
        self.assertEqual(len(fake.sent), 1)
        with self.assertRaisesRegex(ValueError, "previous_task"):
            controller.start_stage("grasp", GOAL, approved=True)
        with self.assertRaisesRegex(ValueError, "independent"):
            controller.confirm_task_result(stage="approach", human_observed=False, result=True)
        controller.confirm_task_result(stage="approach", human_observed=True, result=True)
        self.assertEqual(controller.stage_index, 1)
        self.assertEqual(len(fake.sent), 1)

    def test_stale_feedback_times_out_and_cannot_advance(self):
        fake = FakeTransport()
        fake.positions = dict(GOAL)
        fake.feedback_time = time.monotonic() - 10
        controller = cycle(fake, timeout_s=0.03, feedback_max_age_s=0.001,
                           stable_s=0.02)
        controller.start_stage("approach", GOAL, approved=True)
        self.assertTrue(controller.wait_worker(1))
        self.assertEqual(controller.reach_state, "TIMED_OUT")
        with self.assertRaisesRegex(ValueError, "previous_task"):
            controller.start_stage("grasp", GOAL, approved=True)

    def test_wrong_feedback_never_counts_as_reached(self):
        fake = FakeTransport()
        fake.positions["elbow_flex"] = 8
        controller = cycle(fake, timeout_s=0.02)
        controller.start_stage("approach", GOAL, approved=True)
        self.assertTrue(controller.wait_worker(1))
        self.assertEqual(controller.reach_state, "TIMED_OUT")

    def test_sequence_stops_at_first_unreached_waypoint(self):
        fake = FakeTransport()
        controller = cycle(fake, timeout_s=0.02)
        second = {**GOAL, "elbow_flex": 7.0}
        third = {**GOAL, "elbow_flex": 9.0}
        controller.start_stage("approach", [GOAL, second, third], approved=True)
        self.assertTrue(controller.wait_worker(1))
        self.assertEqual(controller.waypoints_reached, 1)
        self.assertEqual(controller.waypoints_transmitted, 2)
        self.assertEqual(controller.reach_state, "TIMED_OUT")
        self.assertEqual(len(fake.sent), 2)
        self.assertEqual(controller.task_state, "UNVERIFIED")

    def test_new_feedback_detects_pose_drift_before_next_stage_send(self):
        fake = FakeTransport()
        controller = cycle(fake)
        controller.start_stage("approach", GOAL, approved=True)
        self.assertTrue(controller.wait_worker(1))
        controller.confirm_task_result(stage="approach", human_observed=True, result=True)
        fake.positions = {**GOAL, "elbow_flex": 8.0}
        controller.start_stage("grasp", GOAL, approved=True)
        self.assertTrue(controller.wait_worker(1))
        self.assertEqual(controller.failure, "current_pose_mismatch_or_stale")
        self.assertEqual(controller.command_state, "NOT_SENT")
        self.assertEqual(len(fake.sent), 1)

    def test_clipped_send_is_rejected_not_reached(self):
        fake = FakeTransport()
        fake.clip = True
        controller = cycle(fake)
        controller.start_stage("approach", GOAL, approved=True)
        self.assertTrue(controller.wait_worker(1))
        self.assertEqual(controller.command_state, "REJECTED_OR_CLIPPED")
        self.assertEqual(controller.reach_state, "NOT_REACHED")

    def test_stop_waits_for_inflight_send_and_transport_quiescence(self):
        fake = FakeTransport()
        fake.block_send = True
        fake.quiescent = False
        controller = cycle(fake)
        controller.start_stage("approach", GOAL, approved=True)
        self.assertTrue(fake.started.wait(1))
        controller.request_stop()
        self.assertEqual(controller.command_stop_state, "REQUESTED")
        self.assertEqual(controller.arm_stop_state, "NOT_VERIFIED")
        self.assertFalse(controller.verify_stop_completed(timeout_s=0.001))
        self.assertEqual(controller.command_stop_state, "PENDING")
        fake.release_send.set()
        self.assertTrue(controller.wait_worker(1))
        self.assertFalse(controller.verify_stop_completed())
        fake.quiescent = True
        self.assertTrue(controller.verify_stop_completed())
        self.assertEqual(controller.command_stop_state, "COMPLETED")
        self.assertEqual(controller.arm_stop_state, "NOT_VERIFIED")
        with self.assertRaisesRegex(ValueError, "worker_active_or_stop"):
            controller.start_stage("approach", GOAL, approved=True)
        self.assertEqual(len(fake.sent), 1)

    def test_stop_before_stage_never_sends(self):
        fake = FakeTransport()
        controller = cycle(fake)
        controller.request_stop()
        self.assertTrue(controller.verify_stop_completed())
        with self.assertRaisesRegex(ValueError, "worker_active_or_stop"):
            controller.start_stage("approach", GOAL, approved=True)
        self.assertEqual(fake.sent, [])

    def test_arm_stillness_is_separate_from_command_stop(self):
        fake = FakeTransport()
        controller = cycle(fake)
        controller.request_stop()
        self.assertTrue(controller.verify_stop_completed())
        self.assertEqual(controller.arm_stop_state, "NOT_VERIFIED")
        policy = {name: 0.1 for name in JOINT_UNITS}
        self.assertFalse(controller.verify_arm_stopped(
            motion_tolerances=policy, window_s=0.005, timeout_s=0.03,
            human_confirmed=False))
        self.assertTrue(controller.verify_arm_stopped(
            motion_tolerances=policy, window_s=0.005, timeout_s=0.03,
            human_confirmed=True))
        self.assertEqual(controller.arm_stop_state, "FEEDBACK_AND_HUMAN_CONFIRMED")


if __name__ == "__main__":
    unittest.main()
