import io
from pathlib import Path
import time
import unittest
from unittest.mock import patch

import numpy as np

from scripts.continuous_following_execution import FollowingTelemetry
from scripts.live_wrist_escape_z_plus_20 import (
    CONFIRM_PHRASE, RUN_PHRASE, SCOPE, build_next_wrist_goal, load_plan, run,
)
from scripts.plan_pick_grasp_tcp_ik import JOINTS, tcp_position_mm
from scripts.staged_cycle_execution import JOINT_UNITS
from scripts.staged_cycle_execution import Feedback
from scripts.urdf_forward_kinematics import UrdfKinematics


PLAN = Path("configs/c_pick_responsive_joint_escape_20261012.json")
URDF = Path(".local/c-red-pivot-tcp-table-20261011-s01/so101_new_calib.urdf")


class FakeBus:
    def disconnect(self, *, disable_torque):
        if disable_torque:
            raise AssertionError("wrist escape must preserve torque")


class FakeTransport:
    def __init__(self, start, *, movement_fraction=1.0):
        self.current = dict(start)
        self.goal = dict(start)
        self.movement_fraction = movement_fraction
        self.sent = []
        self.start_verified = False
        self.stop_calls = 0
        self.close_calls = 0
        self.robot = type("Robot", (), {"bus": FakeBus()})()
        self.lease = type("Lease", (), {"release": lambda self: None})()

    def read_escape_telemetry(self):
        return FollowingTelemetry(
            positions=dict(self.current),
            received_monotonic=time.monotonic(),
            goal_raw={name: int(round(self.goal[name] * 10))
                      for name in JOINT_UNITS},
            present_raw={name: int(round(self.current[name] * 10))
                         for name in JOINT_UNITS},
            moving={name: 0 for name in JOINT_UNITS},
            present_load={name: (32 if name == "wrist_flex" else 0)
                          for name in JOINT_UNITS},
            temperature_c={name: 35 for name in JOINT_UNITS},
        )

    def send_goal(self, goal):
        if not self.start_verified:
            raise AssertionError("transport start-pose latch was not armed")
        before = dict(self.current)
        self.goal = dict(goal)
        self.sent.append(dict(goal))
        self.current = {
            name: before[name] + self.movement_fraction * (goal[name] - before[name])
            for name in JOINT_UNITS
        }
        return dict(goal)

    def verify_start_pose(self, expected, tolerances):
        if any(abs(self.current[name] - expected[name]) > tolerances[name]
               for name in JOINT_UNITS):
            raise AssertionError("fake start mismatch")
        self.start_verified = True
        return Feedback(dict(self.current), time.monotonic())

    def stop_commands(self):
        self.stop_calls += 1

    def close_after_site_confirmation(self, controller, *, object_supported):
        self.close_calls += 1

    def close_without_motion(self, *, arm_stable, object_supported):
        self.close_calls += 1


class FakeController:
    def __init__(self, *_args, **_kwargs):
        pass

    def request_stop(self):
        pass

    def verify_stop_completed(self, *, timeout_s):
        return True

    def verify_arm_stopped(self, **_kwargs):
        return True


def settled_immediately(transport, **_kwargs):
    return transport.read_escape_telemetry(), []


class LiveWristEscapeTests(unittest.TestCase):
    def _start(self):
        plan = load_plan(PLAN)
        return {
            **dict(zip(JOINTS, plan["current_arm_joints_deg"])),
            "gripper": 2.019584,
        }

    def test_offline_next_step_commands_only_wrist_and_is_bounded(self):
        plan = load_plan(PLAN)
        kinematics = UrdfKinematics.from_file(URDF)
        start = self._start()
        offset = np.asarray(plan["pick_grasp_tcp_offset_gripper_mm"], dtype=float)
        start_q = np.asarray([start[name] for name in JOINTS], dtype=float)
        start_z = tcp_position_mm(kinematics, start_q, offset)[2]
        goal, report = build_next_wrist_goal(
            start,
            target_z_mm=float(start_z + 20.0),
            kinematics=kinematics,
            grasp_offset_mm=offset,
            bounds_deg=np.asarray(plan["servo_bounds_deg"], dtype=float),
            maximum_step_deg=2.0,
            completion_tolerance_mm=0.05,
            table_reference_z_mm=float(plan["table_contact_reference_z_mm"]),
            minimum_centerline_mm=float(
                plan["minimum_self_collision_centerline_mm"]),
        )
        self.assertIsNotNone(goal)
        self.assertGreater(report["predicted_step_z_gain_mm"], 0.0)
        for name in JOINT_UNITS:
            delta = goal[name] - start[name]
            if name == "wrist_flex":
                self.assertGreater(abs(delta), 0.0)
                self.assertLessEqual(abs(delta), 2.0)
            else:
                self.assertEqual(delta, 0.0)

    def test_dry_run_opens_no_transport(self):
        opened = []
        self.assertEqual(run(
            PLAN, live=False, confirm_scope=None,
            transport_factory=lambda: opened.append(True)), 0)
        self.assertEqual(opened, [])

    def test_fake_live_reaches_only_plus_twenty_and_stops(self):
        transport = FakeTransport(self._start(), movement_fraction=1.0)
        answers = iter([RUN_PHRASE, CONFIRM_PHRASE, "STOPPED"])
        with patch(
            "scripts.live_wrist_escape_z_plus_20.wait_for_escape_settle",
            side_effect=settled_immediately,
        ), patch("sys.stdout", new_callable=io.StringIO) as stdout:
            result = run(
                PLAN, live=True, confirm_scope=SCOPE,
                input_fn=lambda _prompt: next(answers),
                transport_factory=lambda: transport,
                urdf_path_factory=lambda: URDF,
                controller_factory=FakeController,
            )
        self.assertEqual(result, 0)
        self.assertEqual(len(transport.sent), 4)
        self.assertIn("WRIST_ESCAPE_Z_PLUS_20_PASS", stdout.getvalue())
        self.assertIn('"automatic_plus_30_or_40":false', stdout.getvalue())
        self.assertIn('"load_gate_enabled":false', stdout.getvalue())
        self.assertTrue(all(
            all(abs(goal[name] - previous[name]) <= 2.0 + 1e-12
                for name in JOINT_UNITS)
            for previous, goal in zip([self._start(), *transport.sent[:-1]], transport.sent)
        ))

    def test_first_failed_step_latches_off_without_second_target(self):
        transport = FakeTransport(self._start(), movement_fraction=0.0)
        answers = iter([RUN_PHRASE, "STOPPED"])
        with patch(
            "scripts.live_wrist_escape_z_plus_20.wait_for_escape_settle",
            side_effect=settled_immediately,
        ), patch("sys.stdout", new_callable=io.StringIO) as stdout:
            result = run(
                PLAN, live=True, confirm_scope=SCOPE,
                input_fn=lambda _prompt: next(answers),
                transport_factory=lambda: transport,
                urdf_path_factory=lambda: URDF,
                controller_factory=FakeController,
            )
        self.assertEqual(result, 1)
        self.assertEqual(len(transport.sent), 1)
        self.assertNotIn("WRIST_ESCAPE_Z_PLUS_20_PASS", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
