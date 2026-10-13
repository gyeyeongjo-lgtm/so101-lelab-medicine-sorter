import io
from pathlib import Path
import time
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from scripts.continuous_following_execution import FollowingTelemetry
from scripts.live_gripper_open_only import (
    EXPECTED_FEETECH_SOURCE_SHA256,
    EXPECTED_MOTORS_BUS_SOURCE_SHA256,
    EXPECTED_SO_FOLLOWER_SOURCE_SHA256,
    NEXT_RUN_PHRASE,
    RUN_PHRASE,
    SCOPE,
    SITE_CONFIRM_PHRASE,
    evaluate_gripper_open,
    load_plan,
    run,
)
from scripts.staged_cycle_execution import Feedback, JOINT_UNITS


PLAN = Path("configs/live_gripper_open_only_20261013.json")
EXPECTED_BUS_SOURCE_HASHES = {
    "feetech": EXPECTED_FEETECH_SOURCE_SHA256,
    "motors_bus": EXPECTED_MOTORS_BUS_SOURCE_SHA256,
}


class FakeBus:
    def __init__(self):
        self.disconnect_calls = []
        self.motors = {"gripper": SimpleNamespace(id=6)}
        self.calibration = {
            "gripper": SimpleNamespace(
                range_min=413, range_max=2047, drive_mode=0),
        }

    def _unnormalize(self, ids_values):
        result = {}
        for motor_id, percent in ids_values.items():
            item = self.calibration["gripper"]
            result[motor_id] = int(
                float(percent) * (item.range_max - item.range_min) / 100.0 +
                item.range_min)
        return result

    def _get_ids_values_dict(self, values):
        if set(values) != {"gripper"}:
            raise AssertionError("fake partial action must be gripper-only")
        return {self.motors["gripper"].id: values["gripper"]}

    def _normalize(self, ids_values):
        result = {}
        for motor_id, raw in ids_values.items():
            item = self.calibration["gripper"]
            result[motor_id] = (
                (int(raw) - item.range_min) * 100.0 /
                (item.range_max - item.range_min))
        return result

    def disconnect(self, *, disable_torque):
        if disable_torque:
            raise AssertionError("gripper-only close must preserve torque")
        self.disconnect_calls.append(disable_torque)


class FakeLease:
    def __init__(self):
        self.release_calls = 0

    def release(self):
        self.release_calls += 1


class FakeTransport:
    def __init__(self, positions, *, movement_fraction=1.0,
                 temperature_c=35, change_arm_goal_raw=False,
                 gripper_goal_raw=None, post_send_gripper_goal_raw=None):
        self.current = dict(positions)
        self.movement_fraction = movement_fraction
        self.temperature_c = temperature_c
        self.change_arm_goal_raw = change_arm_goal_raw
        self.post_send_gripper_goal_raw = post_send_gripper_goal_raw
        self.robot = type("Robot", (), {"bus": FakeBus()})()
        self.goal_raw = {name: 2000 + index
                         for index, name in enumerate(JOINT_UNITS)}
        self.present_raw = {name: 2100 + index
                            for index, name in enumerate(JOINT_UNITS)}
        gripper_id = self.robot.bus.motors["gripper"].id
        self.present_raw["gripper"] = self.robot.bus._unnormalize({
            gripper_id: float(self.current["gripper"]),
        })[gripper_id]
        self.goal_raw["gripper"] = (
            self.present_raw["gripper"] if gripper_goal_raw is None
            else int(gripper_goal_raw))
        self.gripper_only_sends = []
        self.full_goal_send_calls = 0
        self.start_verified = False
        self.stop_calls = 0
        self.close_after_calls = 0
        self.close_without_calls = 0
        self.lease = FakeLease()

    def read_escape_telemetry(self):
        return FollowingTelemetry(
            positions=dict(self.current),
            received_monotonic=time.monotonic(),
            goal_raw=dict(self.goal_raw),
            present_raw=dict(self.present_raw),
            moving={name: 0 for name in JOINT_UNITS},
            present_load={name: (60 if name == "gripper" else 20)
                          for name in JOINT_UNITS},
            temperature_c={name: self.temperature_c for name in JOINT_UNITS},
        )

    def read_feedback(self):
        return Feedback(dict(self.current), time.monotonic())

    def verify_start_pose(self, expected, tolerances):
        if any(abs(self.current[name] - expected[name]) > tolerances[name]
               for name in JOINT_UNITS):
            raise AssertionError("fake verify_start_pose mismatch")
        self.start_verified = True
        return self.read_feedback()

    def send_goal(self, _goal):
        self.full_goal_send_calls += 1
        raise AssertionError("full six-axis goal is forbidden")

    def send_gripper_goal_only(self, target_percent):
        if not self.start_verified:
            raise AssertionError("start-pose latch not armed")
        self.gripper_only_sends.append(float(target_percent))
        before = self.current["gripper"]
        motor_id = self.robot.bus.motors["gripper"].id
        target_raw = self.robot.bus._unnormalize({
            motor_id: float(target_percent),
        })[motor_id]
        quantized_target = self.robot.bus._normalize({
            motor_id: target_raw,
        })[motor_id]
        self.current["gripper"] = before + self.movement_fraction * (
            quantized_target - before)
        self.present_raw["gripper"] = self.robot.bus._unnormalize({
            motor_id: self.current["gripper"],
        })[motor_id]
        self.goal_raw["gripper"] = (
            target_raw if self.post_send_gripper_goal_raw is None
            else int(self.post_send_gripper_goal_raw))
        if self.change_arm_goal_raw:
            self.goal_raw["shoulder_lift"] += 1
        return {"gripper": float(target_percent)}

    def stop_commands(self):
        self.stop_calls += 1

    def is_quiescent(self):
        return True

    def close_after_site_confirmation(self, _controller, *, object_supported):
        if object_supported is not True:
            raise AssertionError("site must confirm support")
        self.close_after_calls += 1

    def close_without_motion(self, *, arm_stable, object_supported):
        if arm_stable is not True or object_supported is not True:
            raise AssertionError("read-only close contract")
        self.close_without_calls += 1


class FakeController:
    def __init__(self, transport, *_args, **_kwargs):
        self.transport = transport

    def request_stop(self):
        self.transport.stop_commands()

    def verify_stop_completed(self, *, timeout_s):
        return timeout_s > 0 and self.transport.is_quiescent()

    def verify_arm_stopped(self, *, human_confirmed, **_kwargs):
        return human_confirmed


def settled_immediately(transport, **_kwargs):
    sample = transport.read_escape_telemetry()
    record = {
        "present_raw": dict(sample.present_raw),
        "goal_raw": dict(sample.goal_raw),
        "present_deg_or_pp": dict(sample.positions),
        "moving": dict(sample.moving),
        "temperature_c": dict(sample.temperature_c),
    }
    sink = _kwargs.get("record_sink")
    if sink is not None:
        sink(record)
    return sample, [record]


class LiveGripperOpenOnlyTests(unittest.TestCase):
    def _start(self, *, gripper=None):
        plan = load_plan(PLAN)
        return {
            **plan["confirmed_start_arm_deg"],
            "gripper": (plan["confirmed_start_gripper_percent"]
                        if gripper is None else gripper),
        }

    def _run_live(self, transport, *, answers, post_transport=None):
        return run(
            PLAN,
            live=True,
            confirm_scope=SCOPE,
            input_fn=lambda _prompt: next(answers),
            transport_factory=lambda: transport,
            post_stop_transport_factory=(
                None if post_transport is None else lambda: post_transport),
            settle_fn=settled_immediately,
            controller_factory=FakeController,
            source_hash_fn=lambda _robot: EXPECTED_SO_FOLLOWER_SOURCE_SHA256,
            bus_source_hash_fn=lambda _robot: dict(EXPECTED_BUS_SOURCE_HASHES),
        )

    def test_plan_is_gripper_only_and_cannot_self_authorize(self):
        plan = load_plan(PLAN)
        self.assertEqual(plan["scope"], SCOPE)
        self.assertEqual(plan["run_phrase"], RUN_PHRASE)
        self.assertFalse(plan["motion_authorized"])
        self.assertFalse(plan["arm_joint_target_allowed"])
        self.assertFalse(plan["automatic_retry"])
        self.assertIsNone(plan["verified_abs_load_limit"])
        self.assertEqual(plan["requested_gripper_percent"], 35.0)
        self.assertEqual(plan["minimum_final_gripper_percent"], 35.0)
        self.assertEqual(plan["command_gripper_percent"], 35.0061199510404)
        self.assertEqual(plan["expected_command_raw"], 985)

    def test_fake_calibration_reproduces_35_percent_quantization_boundary(self):
        bus = FakeBus()
        raw_for_exact_35 = bus._unnormalize({6: 35.0})[6]
        feedback_for_exact_35 = bus._normalize({6: raw_for_exact_35})[6]
        plan = load_plan(PLAN)
        command = plan["command_gripper_percent"]
        command_raw = bus._unnormalize({6: command})[6]
        command_feedback = bus._normalize({6: command_raw})[6]
        self.assertEqual(raw_for_exact_35, 984)
        self.assertAlmostEqual(feedback_for_exact_35, 34.94492044063648)
        self.assertLess(feedback_for_exact_35, 35.0)
        self.assertEqual(command_raw, 985)
        self.assertAlmostEqual(command_feedback, 35.00611995104039)
        self.assertGreaterEqual(command_feedback, 35.0)

    def test_dry_run_opens_no_transport_and_sends_nothing(self):
        opened = []
        with patch("sys.stdout", new_callable=io.StringIO) as stdout:
            result = run(
                PLAN, live=False, confirm_scope=None,
                transport_factory=lambda: opened.append(True),
            )
        self.assertEqual(result, 0)
        self.assertEqual(opened, [])
        self.assertIn("no port opened; no send_action", stdout.getvalue())

    def test_wrong_run_phrase_opens_no_transport(self):
        opened = []
        result = run(
            PLAN, live=True, confirm_scope=SCOPE,
            input_fn=lambda _prompt: "RUN SOMETHING ELSE",
            transport_factory=lambda: opened.append(True),
        )
        self.assertEqual(result, 2)
        self.assertEqual(opened, [])

    def test_success_sends_one_singleton_gripper_action_then_read_only_gate(self):
        transport = FakeTransport(self._start())
        route_transport = FakeTransport(
            self._start(gripper=35.5), gripper_goal_raw=985)
        answers = iter([RUN_PHRASE, SITE_CONFIRM_PHRASE, "STOPPED"])
        with patch("sys.stdout", new_callable=io.StringIO) as stdout:
            result = self._run_live(
                transport, answers=answers, post_transport=route_transport)
        self.assertEqual(result, 0)
        self.assertEqual(transport.gripper_only_sends, [35.0061199510404])
        self.assertEqual(transport.full_goal_send_calls, 0)
        self.assertEqual(route_transport.gripper_only_sends, [])
        self.assertEqual(route_transport.full_goal_send_calls, 0)
        self.assertEqual(transport.close_after_calls, 1)
        self.assertEqual(route_transport.close_without_calls, 1)
        self.assertIn("GRIPPER_OPEN_PASS", stdout.getvalue())
        self.assertIn("current_to_c_start_gate\":\"PASS", stdout.getvalue())
        self.assertIn(f"NEXT_LIVE_COMMAND={NEXT_RUN_PHRASE}", stdout.getvalue())
        self.assertIn('"arm_target_sent":false', stdout.getvalue())

    def test_post_settle_allows_intermediate_gripper_moving_only(self):
        transport = FakeTransport(self._start())
        route_transport = FakeTransport(
            self._start(gripper=35.0), gripper_goal_raw=985)

        def settle_with_expected_gripper_motion(active, **_kwargs):
            sample = active.read_escape_telemetry()
            moving = dict(sample.moving)
            if active.gripper_only_sends:
                moving["gripper"] = 1
            return sample, [{
                "present_raw": dict(sample.present_raw),
                "goal_raw": dict(sample.goal_raw),
                "present_deg_or_pp": dict(sample.positions),
                "moving": moving,
                "temperature_c": dict(sample.temperature_c),
            }]

        answers = iter([RUN_PHRASE, SITE_CONFIRM_PHRASE, "STOPPED"])
        result = run(
            PLAN, live=True, confirm_scope=SCOPE,
            input_fn=lambda _prompt: next(answers),
            transport_factory=lambda: transport,
            post_stop_transport_factory=lambda: route_transport,
            settle_fn=settle_with_expected_gripper_motion,
            controller_factory=FakeController,
            source_hash_fn=lambda _robot: EXPECTED_SO_FOLLOWER_SOURCE_SHA256,
            bus_source_hash_fn=lambda _robot: dict(EXPECTED_BUS_SOURCE_HASHES),
        )
        self.assertEqual(result, 0)
        self.assertEqual(transport.gripper_only_sends, [35.0061199510404])

    def test_intermediate_arm_drift_blocks_even_if_final_sample_recovers(self):
        transport = FakeTransport(self._start())

        def settle_with_hidden_arm_drift(active, **_kwargs):
            sample = active.read_escape_telemetry()
            positions = dict(sample.positions)
            if active.gripper_only_sends:
                positions["elbow_flex"] += 1.01
            return sample, [{
                "present_raw": dict(sample.present_raw),
                "goal_raw": dict(sample.goal_raw),
                "present_deg_or_pp": positions,
                "moving": dict(sample.moving),
                "temperature_c": dict(sample.temperature_c),
            }]

        answers = iter([RUN_PHRASE, "STOPPED"])
        with patch("sys.stdout", new_callable=io.StringIO) as stdout:
            result = run(
                PLAN, live=True, confirm_scope=SCOPE,
                input_fn=lambda _prompt: next(answers),
                transport_factory=lambda: transport,
                settle_fn=settle_with_hidden_arm_drift,
                controller_factory=FakeController,
                source_hash_fn=lambda _robot: EXPECTED_SO_FOLLOWER_SOURCE_SHA256,
                bus_source_hash_fn=lambda _robot: dict(EXPECTED_BUS_SOURCE_HASHES),
            )
        self.assertEqual(result, 1)
        self.assertEqual(transport.gripper_only_sends, [35.0061199510404])
        self.assertIn('"post_send_settle_records"', stdout.getvalue())
        self.assertIn('"present_deg_or_pp"', stdout.getvalue())

    def test_no_gripper_progress_fails_after_exactly_one_send_without_route_gate(self):
        transport = FakeTransport(self._start(), movement_fraction=0.0)
        post_opened = []
        answers = iter([RUN_PHRASE, "STOPPED"])
        with patch("sys.stdout", new_callable=io.StringIO) as stdout:
            result = run(
                PLAN, live=True, confirm_scope=SCOPE,
                input_fn=lambda _prompt: next(answers),
                transport_factory=lambda: transport,
                post_stop_transport_factory=lambda: post_opened.append(True),
                settle_fn=settled_immediately,
                controller_factory=FakeController,
                source_hash_fn=lambda _robot: EXPECTED_SO_FOLLOWER_SOURCE_SHA256,
                bus_source_hash_fn=lambda _robot: dict(EXPECTED_BUS_SOURCE_HASHES),
            )
        self.assertEqual(result, 1)
        self.assertEqual(transport.gripper_only_sends, [35.0061199510404])
        self.assertEqual(transport.full_goal_send_calls, 0)
        self.assertEqual(post_opened, [])
        self.assertNotIn(f"NEXT_LIVE_COMMAND={NEXT_RUN_PHRASE}", stdout.getvalue())

    def test_positive_but_below_35_percent_fails_without_retry(self):
        transport = FakeTransport(self._start(), movement_fraction=0.9)
        answers = iter([RUN_PHRASE, "STOPPED"])
        result = self._run_live(transport, answers=answers)
        self.assertEqual(result, 1)
        self.assertEqual(transport.gripper_only_sends, [35.0061199510404])
        self.assertGreater(transport.current["gripper"], self._start()["gripper"])
        self.assertLess(transport.current["gripper"], 35.0)

    def test_post_stop_route_gate_failure_never_prints_next_command(self):
        transport = FakeTransport(self._start())
        route_transport = FakeTransport(
            self._start(gripper=34.9), gripper_goal_raw=985)
        answers = iter([RUN_PHRASE, SITE_CONFIRM_PHRASE, "STOPPED"])
        with patch("sys.stdout", new_callable=io.StringIO) as stdout:
            result = self._run_live(
                transport, answers=answers, post_transport=route_transport)
        self.assertEqual(result, 1)
        self.assertEqual(transport.gripper_only_sends, [35.0061199510404])
        self.assertEqual(route_transport.gripper_only_sends, [])
        self.assertNotIn(f"NEXT_LIVE_COMMAND={NEXT_RUN_PHRASE}", stdout.getvalue())

    def test_final_gripper_goal_raw_mismatch_fails_after_one_send(self):
        transport = FakeTransport(
            self._start(), post_send_gripper_goal_raw=984)
        answers = iter([RUN_PHRASE, "STOPPED"])
        result = self._run_live(transport, answers=answers)
        self.assertEqual(result, 1)
        self.assertEqual(transport.gripper_only_sends, [35.0061199510404])

    def test_post_stop_route_goal_raw_mismatch_blocks_next_command(self):
        transport = FakeTransport(self._start())
        route_transport = FakeTransport(
            self._start(gripper=35.00611995104039), gripper_goal_raw=984)
        answers = iter([RUN_PHRASE, SITE_CONFIRM_PHRASE, "STOPPED"])
        with patch("sys.stdout", new_callable=io.StringIO) as stdout:
            result = self._run_live(
                transport, answers=answers, post_transport=route_transport)
        self.assertEqual(result, 1)
        self.assertNotIn(f"NEXT_LIVE_COMMAND={NEXT_RUN_PHRASE}", stdout.getvalue())

    def test_post_stop_route_arm_goal_raw_change_blocks_next_command(self):
        transport = FakeTransport(self._start())
        route_transport = FakeTransport(
            self._start(gripper=35.00611995104039), gripper_goal_raw=985)
        route_transport.goal_raw["elbow_flex"] += 1
        answers = iter([RUN_PHRASE, SITE_CONFIRM_PHRASE, "STOPPED"])
        with patch("sys.stdout", new_callable=io.StringIO) as stdout:
            result = self._run_live(
                transport, answers=answers, post_transport=route_transport)
        self.assertEqual(result, 1)
        self.assertNotIn(f"NEXT_LIVE_COMMAND={NEXT_RUN_PHRASE}", stdout.getvalue())

    def test_runtime_so_follower_source_mismatch_blocks_before_send(self):
        transport = FakeTransport(self._start())
        result = run(
            PLAN, live=True, confirm_scope=SCOPE,
            input_fn=lambda _prompt: RUN_PHRASE,
            transport_factory=lambda: transport,
            settle_fn=settled_immediately,
            controller_factory=FakeController,
            source_hash_fn=lambda _robot: "0" * 64,
            bus_source_hash_fn=lambda _robot: dict(EXPECTED_BUS_SOURCE_HASHES),
        )
        self.assertEqual(result, 1)
        self.assertEqual(transport.gripper_only_sends, [])

    def test_runtime_partial_action_bus_source_mismatch_blocks_before_send(self):
        transport = FakeTransport(self._start())
        result = run(
            PLAN, live=True, confirm_scope=SCOPE,
            input_fn=lambda _prompt: RUN_PHRASE,
            transport_factory=lambda: transport,
            settle_fn=settled_immediately,
            controller_factory=FakeController,
            source_hash_fn=lambda _robot: EXPECTED_SO_FOLLOWER_SOURCE_SHA256,
            bus_source_hash_fn=lambda _robot: {
                "feetech": "0" * 64,
                "motors_bus": EXPECTED_MOTORS_BUS_SOURCE_SHA256,
            },
        )
        self.assertEqual(result, 1)
        self.assertEqual(transport.gripper_only_sends, [])

    def test_runtime_partial_action_axis_expansion_blocks_before_send(self):
        transport = FakeTransport(self._start())
        original = transport.robot.bus._get_ids_values_dict

        def expanded(values):
            result = original(values)
            result[1] = 0.0
            return result

        transport.robot.bus._get_ids_values_dict = expanded
        result = self._run_live(transport, answers=iter([RUN_PHRASE]))
        self.assertEqual(result, 1)
        self.assertEqual(transport.gripper_only_sends, [])

    def test_high_temperature_blocks_before_send(self):
        transport = FakeTransport(self._start(), temperature_c=56)
        result = self._run_live(transport, answers=iter([RUN_PHRASE]))
        self.assertEqual(result, 1)
        self.assertEqual(transport.gripper_only_sends, [])
        self.assertEqual(transport.full_goal_send_calls, 0)
        self.assertEqual(transport.close_without_calls, 1)

    def test_calibration_mismatch_blocks_before_send(self):
        transport = FakeTransport(self._start())
        transport.robot.bus.calibration["gripper"].range_max = 2046
        result = self._run_live(transport, answers=iter([RUN_PHRASE]))
        self.assertEqual(result, 1)
        self.assertEqual(transport.gripper_only_sends, [])
        self.assertEqual(transport.full_goal_send_calls, 0)
        self.assertEqual(transport.close_without_calls, 1)

    def test_start_arm_drift_blocks_before_send(self):
        start = self._start()
        start["wrist_flex"] += 0.51
        transport = FakeTransport(start)
        result = self._run_live(transport, answers=iter([RUN_PHRASE]))
        self.assertEqual(result, 1)
        self.assertEqual(transport.gripper_only_sends, [])
        self.assertEqual(transport.full_goal_send_calls, 0)

    def test_arm_goal_raw_change_fails_after_one_send(self):
        transport = FakeTransport(
            self._start(), change_arm_goal_raw=True)
        answers = iter([RUN_PHRASE, "STOPPED"])
        with patch("sys.stdout", new_callable=io.StringIO) as stdout:
            result = self._run_live(transport, answers=answers)
        self.assertEqual(result, 1)
        self.assertEqual(transport.gripper_only_sends, [35.0061199510404])
        self.assertEqual(transport.full_goal_send_calls, 0)
        self.assertNotIn("GRIPPER_OPEN_PASS", stdout.getvalue())

    def test_evaluator_rejects_arm_present_drift_over_one_degree(self):
        plan = load_plan(PLAN)
        transport = FakeTransport(self._start())
        before = transport.read_escape_telemetry()
        transport.send_gripper_goal_only = lambda _target: None
        transport.current["gripper"] = 35.0
        transport.current["shoulder_pan"] += 1.01
        after = transport.read_escape_telemetry()
        result = evaluate_gripper_open(before, after, plan)
        self.assertFalse(result["arm_present_drift_within_limit"])
        self.assertFalse(result["pass"])


if __name__ == "__main__":
    unittest.main()
