import io
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from scripts.live_c_approach_only import (
    RUN_PHRASE, SCOPE, load_approach_plan, run,
)
from scripts.staged_cycle_execution import Feedback, JOINT_UNITS


PLAN = Path("configs/live_c_approach_only_20261012.json")


class FakeBus:
    def disconnect(self, *, disable_torque):
        if disable_torque:
            raise AssertionError("torque must not be disabled by approach close")


class FakeTransport:
    def __init__(self, start):
        self.current = dict(start)
        self.stop_calls = 0
        self.close_calls = 0
        self.robot = type("Robot", (), {"bus": FakeBus()})()
        self.lease = type("Lease", (), {"release": lambda self: None})()

    def read_feedback(self):
        return Feedback(dict(self.current), time.monotonic())

    def verify_start_pose(self, goal, tolerances):
        return self.read_feedback()

    def stop_commands(self):
        self.stop_calls += 1

    def close_after_site_confirmation(self, controller, *, object_supported):
        self.close_calls += 1


class FakeController:
    instances = []

    def __init__(self, transport, *_args, **_kwargs):
        self.transport = transport
        self.reach_state = "IDLE"
        self.task_state = "IDLE"
        self.waypoints_reached = 0
        self.failure = None
        self.stage = None
        self.goals = None
        self.instances.append(self)

    def start_stage(self, stage, goals, *, approved):
        self.stage = stage
        self.goals = list(goals)
        self.transport.current = dict(self.goals[-1])
        self.reach_state = "GOAL_REACHED"
        self.task_state = "USER_CONFIRMATION_REQUIRED"
        self.waypoints_reached = len(self.goals)

    def wait_worker(self, timeout):
        return True

    def confirm_task_result(self, **_kwargs):
        return None

    def request_stop(self):
        return None

    def verify_stop_completed(self, *, timeout_s):
        return None

    def verify_arm_stopped(self, **_kwargs):
        return True


class LiveCApproachOnlyTests(unittest.TestCase):
    def setUp(self):
        FakeController.instances.clear()

    def test_plan_is_approach_only_and_preserves_existing_target(self):
        plan = load_approach_plan(PLAN)
        self.assertEqual(plan["scope"], SCOPE)
        self.assertEqual(plan["target_robot_xyz_mm"], [-62.635354, -295.315566, 80.0])
        self.assertEqual(plan["target_arm_deg"], {
            "shoulder_pan": -0.096486,
            "shoulder_lift": 17.400979,
            "elbow_flex": 14.407074,
            "wrist_flex": 10.648771,
            "wrist_roll": 14.577178,
        })
        self.assertEqual(plan["staged_intermediate_arm_deg"], [])

    def test_dry_run_never_opens_transport(self):
        opened = []
        self.assertEqual(run(
            PLAN, live=False, confirm_scope=None,
            transport_factory=lambda: opened.append(True)), 0)
        self.assertEqual(opened, [])

    def test_fake_live_runs_only_approach_and_holds_gripper(self):
        plan = load_approach_plan(PLAN)
        start = {**plan["required_start_arm_deg"], "gripper": 2.0195838433292534}
        transport = FakeTransport(start)
        answers = iter([RUN_PHRASE, "APPROACH CONFIRMED", "STOPPED"])
        with tempfile.TemporaryDirectory() as directory, \
                patch("scripts.live_c_approach_only.ContinuousFollowingCycle", FakeController), \
                patch("sys.stdout", new_callable=io.StringIO) as stdout:
            result = run(
                PLAN, live=True, confirm_scope=SCOPE,
                following_log_output=Path(directory) / "approach.jsonl",
                input_fn=lambda _prompt: next(answers),
                transport_factory=lambda: transport)
        self.assertEqual(result, 0)
        controller = FakeController.instances[-1]
        self.assertEqual(controller.stage, "approach")
        self.assertEqual(len(controller.goals), 6)
        self.assertTrue(all(goal["gripper"] == start["gripper"]
                            for goal in controller.goals))
        self.assertIn("APPROACH_PASS", stdout.getvalue())
        self.assertNotIn("GRASP_PASS", stdout.getvalue())
        self.assertNotIn("LIFT_PASS", stdout.getvalue())
        self.assertEqual(transport.stop_calls, 1)
        self.assertEqual(transport.close_calls, 1)

    def test_start_gate_rejects_pose_drift_before_controller(self):
        plan = load_approach_plan(PLAN)
        start = {**plan["required_start_arm_deg"], "gripper": 2.0}
        start["shoulder_lift"] += 1.01
        transport = FakeTransport(start)
        answers = iter([RUN_PHRASE])
        with tempfile.TemporaryDirectory() as directory, \
                patch("scripts.live_c_approach_only.ContinuousFollowingCycle", FakeController):
            result = run(
                PLAN, live=True, confirm_scope=SCOPE,
                following_log_output=Path(directory) / "approach.jsonl",
                input_fn=lambda _prompt: next(answers),
                transport_factory=lambda: transport)
        self.assertEqual(result, 1)
        self.assertEqual(FakeController.instances, [])
        self.assertEqual(transport.stop_calls, 1)


if __name__ == "__main__":
    unittest.main()
