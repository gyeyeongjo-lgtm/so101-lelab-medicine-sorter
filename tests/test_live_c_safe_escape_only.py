import io
from pathlib import Path
import time
import unittest
from unittest.mock import patch

from scripts.live_c_safe_escape_only import (
    CONFIRM_PHRASE, RUN_PHRASE, SCOPE, build_fresh_escape_goal, load_plan, run,
)
from scripts.continuous_following_execution import FollowingTelemetry
from scripts.staged_cycle_execution import Feedback, JOINT_UNITS


PLAN = Path("configs/c_pick_safe_escape_only_20261012.json")
URDF = Path(".local/c-red-pivot-tcp-table-20261011-s01/so101_new_calib.urdf")


class FakeBus:
    def disconnect(self, *, disable_torque):
        if disable_torque:
            raise AssertionError("escape close must preserve torque")


class FakeTransport:
    def __init__(self, start, *, movement_fraction=1.0):
        self.current = dict(start)
        self.start = dict(start)
        self.movement_fraction = movement_fraction
        self.goal = dict(start)
        self.sent = []
        self.stop_calls = 0
        self.close_calls = 0
        self.robot = type("Robot", (), {"bus": FakeBus()})()
        self.lease = type("Lease", (), {"release": lambda self: None})()
        self.calibrated_bounds = {name: (-200.0, 200.0) for name in JOINT_UNITS}

    def read_feedback(self):
        return Feedback(dict(self.current), time.monotonic())

    def verify_start_pose(self, expected, tolerances):
        return self.read_feedback()

    def send_goal(self, goal):
        self.sent.append(dict(goal))
        self.goal = dict(goal)
        self.current = {
            name: self.start[name] + self.movement_fraction * (
                goal[name] - self.start[name])
            for name in JOINT_UNITS
        }
        return dict(goal)

    def read_escape_telemetry(self):
        return FollowingTelemetry(
            positions=dict(self.current),
            received_monotonic=time.monotonic(),
            goal_raw={name: int(round(self.goal[name] * 10))
                      for name in JOINT_UNITS},
            present_raw={name: int(round(self.current[name] * 10))
                         for name in JOINT_UNITS},
            moving={name: 0 for name in JOINT_UNITS},
            present_load={name: 20 for name in JOINT_UNITS},
            temperature_c={name: 35 for name in JOINT_UNITS},
        )

    def is_quiescent(self):
        return True

    def stop_commands(self):
        self.stop_calls += 1

    def close_after_site_confirmation(self, controller, *, object_supported):
        self.close_calls += 1

    def close_without_motion(self, *, arm_stable, object_supported):
        self.close_calls += 1


class SafeEscapeOnlyTests(unittest.TestCase):
    def _start(self):
        plan = load_plan(PLAN)
        return {**plan["confirmed_fresh_arm_deg"], "gripper": 2.0195838433292534}

    def test_plan_is_exactly_two_degree_escape_and_not_self_authorized(self):
        plan = load_plan(PLAN)
        self.assertEqual(plan["scope"], SCOPE)
        self.assertEqual(plan["candidate_name"], "SAFE_ESCAPE_2DEG")
        self.assertFalse(plan["motion_authorized"])
        goal = build_fresh_escape_goal(
            self._start(), plan, {name: (-200.0, 200.0) for name in JOINT_UNITS})
        self.assertEqual(max(abs(goal[name] - self._start()[name]) for name in JOINT_UNITS), 2.0)
        self.assertEqual(goal["gripper"], self._start()["gripper"])

    def test_fresh_rebase_preserves_two_degree_escape_direction(self):
        plan = load_plan(PLAN)
        start = self._start()
        start.update(shoulder_pan=0.25, shoulder_lift=18.0, elbow_flex=15.0,
                     wrist_flex=10.0, wrist_roll=14.5)
        goal = build_fresh_escape_goal(
            start, plan, {name: (-200.0, 200.0) for name in JOINT_UNITS})
        self.assertEqual(
            [goal[name] - start[name] for name in (
                "shoulder_pan", "shoulder_lift", "elbow_flex",
                "wrist_flex", "wrist_roll")],
            [2.0, -2.0, -2.0, -2.0, 2.0])

    def test_dry_run_opens_no_transport(self):
        opened = []
        self.assertEqual(run(
            PLAN, live=False, confirm_scope=None,
            transport_factory=lambda: opened.append(True)), 0)
        self.assertEqual(opened, [])

    def test_fake_live_sends_exactly_one_fresh_relative_target(self):
        transport = FakeTransport(self._start())
        answers = iter([RUN_PHRASE, CONFIRM_PHRASE, "STOPPED"])
        plan = load_plan(PLAN)
        with patch("scripts.live_c_safe_escape_only.load_plan", return_value=plan), \
                patch("sys.stdout", new_callable=io.StringIO) as stdout:
            result = run(
                PLAN, live=True, confirm_scope=SCOPE,
                input_fn=lambda _prompt: next(answers),
                transport_factory=lambda: transport,
                urdf_path_factory=lambda: URDF)
        self.assertEqual(result, 0)
        self.assertEqual(len(transport.sent), 1)
        self.assertIn("SAFE_ESCAPE_PASS", stdout.getvalue())
        self.assertIn('"load_gate_enabled":false', stdout.getvalue())
        self.assertIn('"load_gate_result":"NOT_APPLICABLE_NOT_DEFINED"',
                      stdout.getvalue())
        self.assertIn('"present_load_delta"', stdout.getvalue())
        for forbidden in ("APPROACH_PASS", "GRASP_PASS", "LIFT_PASS"):
            self.assertNotIn(forbidden, stdout.getvalue())

    def test_half_motion_can_pass_even_when_terminal_tolerance_fails(self):
        transport = FakeTransport(self._start(), movement_fraction=0.5)
        answers = iter([RUN_PHRASE, CONFIRM_PHRASE, "STOPPED"])
        plan = load_plan(PLAN)
        plan["verified_abs_load_limit"] = 100
        with patch("scripts.live_c_safe_escape_only.load_plan", return_value=plan), \
                patch("sys.stdout", new_callable=io.StringIO) as stdout:
            result = run(
                PLAN, live=True, confirm_scope=SCOPE,
                input_fn=lambda _prompt: next(answers),
                transport_factory=lambda: transport,
                urdf_path_factory=lambda: URDF)
        self.assertEqual(result, 0)
        self.assertEqual(len(transport.sent), 1)
        self.assertIn('"terminal_tolerance_gates_escape_pass":false',
                      stdout.getvalue())

    def test_no_motion_fails_without_a_second_send(self):
        transport = FakeTransport(self._start(), movement_fraction=0.0)
        answers = iter([RUN_PHRASE, "STOPPED"])
        plan = load_plan(PLAN)
        plan["verified_abs_load_limit"] = 100
        with patch("scripts.live_c_safe_escape_only.load_plan", return_value=plan), \
                patch("sys.stdout", new_callable=io.StringIO) as stdout:
            result = run(
                PLAN, live=True, confirm_scope=SCOPE,
                input_fn=lambda _prompt: next(answers),
                transport_factory=lambda: transport,
                urdf_path_factory=lambda: URDF)
        self.assertEqual(result, 1)
        self.assertEqual(len(transport.sent), 1)
        self.assertNotIn("SAFE_ESCAPE_PASS", stdout.getvalue())
        for forbidden in ("APPROACH_PASS", "GRASP_PASS", "LIFT_PASS"):
            self.assertNotIn(forbidden, stdout.getvalue())

    def test_changed_site_pose_blocks_before_send(self):
        start = self._start()
        start["shoulder_lift"] += 0.51
        transport = FakeTransport(start)
        answers = iter([RUN_PHRASE])
        result = run(
            PLAN, live=True, confirm_scope=SCOPE,
            input_fn=lambda _prompt: next(answers),
            transport_factory=lambda: transport,
            urdf_path_factory=lambda: URDF)
        self.assertEqual(result, 1)
        self.assertEqual(transport.sent, [])
        self.assertEqual(transport.close_calls, 1)

    def test_nonpositive_table_proxy_blocks_before_send(self):
        plan = load_plan(PLAN)
        original = plan["minimum_commanded_table_proxy_margin_mm"]
        try:
            plan["minimum_commanded_table_proxy_margin_mm"] = 1000.0
            with patch("scripts.live_c_safe_escape_only.load_plan", return_value=plan):
                transport = FakeTransport(self._start())
                result = run(
                    PLAN, live=True, confirm_scope=SCOPE,
                    input_fn=lambda _prompt: RUN_PHRASE,
                    transport_factory=lambda: transport,
                    urdf_path_factory=lambda: URDF)
            self.assertEqual(result, 1)
            self.assertEqual(transport.sent, [])
        finally:
            plan["minimum_commanded_table_proxy_margin_mm"] = original


if __name__ == "__main__":
    unittest.main()
