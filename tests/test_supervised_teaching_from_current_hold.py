import json
import importlib
import os
from pathlib import Path
import random
import tempfile
import sys
import types
import unittest
from unittest.mock import patch

from scripts.relative_start_teleop import ACTION_KEYS, JOINTS, oversized_arm_steps
from scripts.supervised_teaching_from_current_hold import (
    REFERENCE_GOAL_RAW, REFERENCE_PRESENT_RAW,
    QUANTIZED_REFERENCE_GOAL_RAW, QUANTIZED_REFERENCE_PRESENT_RAW,
    hold_stable_quantized, make_write_firewall, pre_arm_hold_stability,
    run_teaching_from_hold, slew_relative_target,
)
from scripts.teleop_cycle_trace import CycleTrace


class Clock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class FakeBus:
    def __init__(self):
        self.writes = []
        self.config_writes = 0
        self.torque_writes = 0

    def sync_write(self, register, values, *args, **kwargs):
        self.writes.append((register, dict(values)))

    def write(self, *args, **kwargs):
        self.config_writes += 1

    def write_calibration(self, *args, **kwargs):
        self.config_writes += 1

    def configure_motors(self, *args, **kwargs):
        self.config_writes += 1

    def enable_torque(self, *args, **kwargs):
        self.torque_writes += 1

    def disable_torque(self, *args, **kwargs):
        self.torque_writes += 1


def diagnostics():
    present = dict(REFERENCE_PRESENT_RAW)
    goal = dict(REFERENCE_GOAL_RAW)
    percent = {name: float(present[name]) for name in JOINTS}
    return {
        "goal_raw": goal,
        "present_raw": present,
        "goal_degree_or_percent": {name: float(goal[name]) for name in JOINTS},
        "present_degree_or_percent": percent,
        "moving": {name: 0 for name in JOINTS},
        "present_load_diagnostic": {name: 0 for name in JOINTS},
        "temperature_c": {name: 36 for name in JOINTS},
        "fk_grasp_tcp_mm": [0.0, 0.0, 80.0],
    }


class CurrentHoldTeachingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.previous_ticket = os.environ.pop("LELAB_TELEOP_TRACE_ONCE_TICKET", None)
        self.addCleanup(self.restore_ticket)
        self.ticket = Path(self.temp.name) / "once.ticket"
        self.ticket.touch()
        os.environ["LELAB_TELEOP_TRACE_ONCE_TICKET"] = str(self.ticket)
        self.trace = CycleTrace(Path(self.temp.name) / "trace",
                                capture_kind="empirical_relative_teaching")
        self.clock = Clock()
        self.leader = {f"{name}.pos": 4.7 if name == "gripper" else 10.0
                       for name in JOINTS}
        self.follower = dict(self.leader)
        self.armed = False
        self.sent = []
        self.sample = diagnostics()

    def restore_ticket(self):
        if self.previous_ticket is None:
            os.environ.pop("LELAB_TELEOP_TRACE_ONCE_TICKET", None)
        else:
            os.environ["LELAB_TELEOP_TRACE_ONCE_TICKET"] = self.previous_ticket

    def tearDown(self):
        if not self.trace.closed:
            self.trace.finish(stop_reason="worker_error")

    def run_case(self, *, stop=None, confirm=lambda: True,
                 hold_policy="exact_zero", read_follower_action=None,
                 pre_connect=None, sender=None):
        return run_teaching_from_hold(
            trace=self.trace, pre_connect=pre_connect or self.sample,
            read_leader=lambda: dict(self.leader),
            read_leader_torque=lambda: {name: 0 for name in JOINTS},
            read_follower_action=read_follower_action or (lambda: dict(self.follower)),
            read_diagnostics=lambda: dict(self.sample),
            read_follower_torque=lambda: {name: 1 for name in JOINTS},
            bounds={name: (-200.0, 200.0) for name in JOINTS},
            send_guarded=sender or self.send,
            enable_goals=lambda: setattr(self, "armed", True),
            arm_confirm=confirm,
            stop_requested=stop or (lambda: len(self.sent) > 0),
            monotonic=self.clock.monotonic, sleep=self.clock.sleep,
            hold_policy=hold_policy,
        )

    def send(self, action, _previous_elbow):
        self.assertTrue(self.armed)
        self.assertEqual(set(action), {f"{name}.pos" for name in JOINTS})
        self.sent.append(dict(action))
        return dict(action)

    def test_startup_recorder_first_goal_skipped_gripper_relative_open(self):
        def stop():
            if self.armed and not self.sent:
                self.leader["gripper.pos"] += 1.0
            return bool(self.sent)
        result = self.run_case(stop=stop)
        manifest = self.trace.finish(stop_reason="teleoperation_inactive")
        self.assertEqual(result["status"], "STOPPED")
        self.assertTrue(result["first_goal_skipped"])
        self.assertGreaterEqual(result["stillness_samples"], 30)
        self.assertEqual(result["goal_sends"], 1)
        self.assertEqual(self.sent[0]["gripper.pos"], 5.7)
        self.assertEqual(result["final_read_only_samples"], 3)
        self.assertTrue(manifest["data_complete"])
        rows = [json.loads(row) for row in self.trace.path.read_text().splitlines()]
        self.assertFalse(rows[0]["command_sent"])
        self.assertFalse(rows[0]["gripper_goal_sent"])
        self.assertTrue(rows[1]["gripper_goal_sent"])
        self.assertFalse(self.ticket.exists())
        self.assertTrue((self.trace.session_dir / "final_pose_3sample.json").is_file())

    def test_prearm_stop_no_send_ticket_preserved(self):
        result = self.run_case(confirm=lambda: False)
        self.trace.finish(stop_reason="worker_error")
        self.assertEqual(result["status"], "STOPPED_BEFORE_ARM")
        self.assertEqual(self.sent, [])
        self.assertTrue(self.ticket.exists())

    def test_graceful_stop_after_arm_saves_three_final_samples_without_goal(self):
        result = self.run_case(stop=lambda: self.armed)
        manifest = self.trace.finish(stop_reason="teleoperation_inactive")
        self.assertEqual(result["status"], "STOPPED")
        self.assertEqual(result["goal_sends"], 0)
        self.assertTrue(result["first_goal_skipped"])
        self.assertEqual(result["final_read_only_samples"], 3)
        self.assertEqual(self.sent, [])
        self.assertTrue(manifest["data_complete"])
        self.assertTrue((self.trace.session_dir / "final_pose_3sample.json").is_file())

    def test_torque_mismatch_before_arm_aborts_without_send(self):
        with self.assertRaisesRegex(RuntimeError, "torque_not_all_on"):
            run_teaching_from_hold(
                trace=self.trace, pre_connect=self.sample,
                read_leader=lambda: dict(self.leader),
                read_leader_torque=lambda: {name: 0 for name in JOINTS},
                read_follower_action=lambda: dict(self.follower),
                read_diagnostics=lambda: dict(self.sample),
                read_follower_torque=lambda: {name: 0 for name in JOINTS},
                bounds={name: (-200.0, 200.0) for name in JOINTS},
                send_guarded=self.send,
                enable_goals=lambda: setattr(self, "armed", True),
                arm_confirm=lambda: True, stop_requested=lambda: False,
                monotonic=self.clock.monotonic, sleep=self.clock.sleep)
        self.assertEqual(self.sent, [])
        self.assertTrue(self.ticket.exists())

    def test_one_raw_goal_present_gap_blocks_before_send(self):
        self.sample["present_raw"] = dict(self.sample["present_raw"])
        self.sample["present_raw"]["shoulder_lift"] += 1
        with self.assertRaisesRegex(RuntimeError, "goal_present_diff_exceeded"):
            self.run_case()
        self.assertEqual(self.sent, [])
        self.assertTrue(self.ticket.exists())

    def test_quantized_policy_is_explicit_and_preserves_exact_zero(self):
        self.sample["present_raw"] = dict(QUANTIZED_REFERENCE_PRESENT_RAW)
        self.sample["goal_raw"] = dict(QUANTIZED_REFERENCE_GOAL_RAW)
        with self.assertRaisesRegex(RuntimeError, "goal_present_diff_exceeded"):
            self.run_case()
        self.assertEqual(self.sent, [])
        result = self.run_case(confirm=lambda: False, hold_policy="quantized")
        self.assertEqual(result["status"], "STOPPED_BEFORE_ARM")
        self.assertEqual(self.sent, [])
        self.assertTrue(self.ticket.exists())

    def test_quantized_origin_after_stillness_recorder_arms_without_initial_goal(self):
        self.sample["present_raw"] = dict(QUANTIZED_REFERENCE_PRESENT_RAW)
        self.sample["goal_raw"] = dict(QUANTIZED_REFERENCE_GOAL_RAW)
        origin_times = []

        def read_follower():
            origin_times.append(self.clock.monotonic())
            return dict(self.follower)

        def stop():
            if self.armed and not self.sent:
                self.leader["gripper.pos"] += 1.0
            return bool(self.sent)

        result = self.run_case(stop=stop, hold_policy="quantized",
                               read_follower_action=read_follower)
        manifest = self.trace.finish(stop_reason="teleoperation_inactive")
        self.assertGreaterEqual(origin_times[0], 3.0)
        self.assertTrue(result["first_goal_skipped"])
        self.assertEqual(result["goal_sends"], 1)
        self.assertTrue(manifest["data_complete"])
        self.assertFalse(self.ticket.exists())

    def test_fresh_wrist_observation_is_origin_not_saved_reference(self):
        self.sample["present_raw"] = dict(QUANTIZED_REFERENCE_PRESENT_RAW)
        self.sample["present_raw"]["wrist_flex"] += 1
        self.sample["goal_raw"] = dict(QUANTIZED_REFERENCE_GOAL_RAW)
        self.follower["wrist_flex.pos"] += 0.0879120879120876

        def stop():
            if self.armed and not self.sent:
                self.leader["gripper.pos"] += 1.0
            return bool(self.sent)

        result = self.run_case(stop=stop, hold_policy="quantized")
        self.trace.finish(stop_reason="teleoperation_inactive")
        summary = json.loads((self.trace.session_dir / "startup_summary.json").read_text())
        self.assertFalse(result["reference_exact_match"])
        self.assertTrue(result["current_fresh_stability"])
        self.assertFalse(summary["REFERENCE_EXACT_MATCH"])
        self.assertTrue(summary["CURRENT_FRESH_STABILITY"])
        self.assertEqual(summary["reference_present_delta_raw"]["wrist_flex"], 1)
        self.assertEqual(self.sent[0]["wrist_flex.pos"], self.follower["wrist_flex.pos"])
        self.assertEqual(QUANTIZED_REFERENCE_PRESENT_RAW["wrist_flex"], 2497)

    def test_quantized_policy_still_rejects_preconnect_pose_change(self):
        self.sample["present_raw"] = dict(QUANTIZED_REFERENCE_PRESENT_RAW)
        self.sample["present_raw"]["wrist_flex"] += 1
        self.sample["goal_raw"] = dict(QUANTIZED_REFERENCE_GOAL_RAW)
        old_pre_connect = diagnostics()
        old_pre_connect["present_raw"] = dict(QUANTIZED_REFERENCE_PRESENT_RAW)
        old_pre_connect["goal_raw"] = dict(QUANTIZED_REFERENCE_GOAL_RAW)
        with self.assertRaisesRegex(RuntimeError, "pre_connect_follower_changed"):
            self.run_case(hold_policy="quantized", pre_connect=old_pre_connect)
        self.assertEqual(self.sent, [])
        self.assertTrue(self.ticket.exists())

    def test_pre_arm_two_raw_lift_gap_passes_without_changing_exact_policy(self):
        self.sample["present_raw"] = dict(QUANTIZED_REFERENCE_PRESENT_RAW)
        self.sample["present_raw"]["shoulder_lift"] += 1
        self.sample["present_raw"]["wrist_flex"] += 1
        self.sample["goal_raw"] = dict(QUANTIZED_REFERENCE_GOAL_RAW)
        self.assertFalse(hold_stable_quantized([self.sample, self.sample]))
        result = self.run_case(confirm=lambda: False, hold_policy="quantized")
        self.assertEqual(result["status"], "STOPPED_BEFORE_ARM")
        self.assertTrue(result["current_fresh_stability"])
        self.assertGreaterEqual(result["stillness_samples"], 30)
        self.assertEqual(self.sent, [])
        self.assertTrue(self.ticket.exists())

    def test_close_command_aborts_before_goal_send(self):
        def stop():
            if self.armed:
                self.leader["gripper.pos"] = 3.7
            return False
        with self.assertRaisesRegex(RuntimeError, "gripper_close_forbidden"):
            self.run_case(stop=stop)
        self.assertEqual(self.sent, [])

    def test_gripper_step_aborts_before_goal_send(self):
        def stop():
            if self.armed:
                self.leader["gripper.pos"] = 7.7
            return False
        with self.assertRaisesRegex(RuntimeError, "gripper_step_exceeds"):
            self.run_case(stop=stop)
        self.assertEqual(self.sent, [])

    def test_large_arm_request_is_emitted_over_three_cycles_and_logged(self):
        def stop():
            if self.armed:
                self.leader["elbow_flex.pos"] = 15.3
                self.leader["shoulder_pan.pos"] = 12.65
                self.leader["wrist_flex.pos"] = 8.675
                self.leader["gripper.pos"] = 6.2
            return len(self.sent) >= 3

        result = self.run_case(stop=stop)
        self.trace.finish(stop_reason="teleoperation_inactive")
        self.assertEqual(result["goal_sends"], 3)
        self.assertLessEqual(result["max_emitted_arm_step_deg"], 2.0)
        before = self.follower
        for command in self.sent:
            self.assertFalse(oversized_arm_steps(command, before))
            self.assertLessEqual(abs(command["gripper.pos"] - before["gripper.pos"]), 2.0)
            fraction = (command["elbow_flex.pos"] - 10.0) / 5.3
            self.assertAlmostEqual(command["shoulder_pan.pos"], 10.0 + 2.65 * fraction)
            self.assertAlmostEqual(command["wrist_flex.pos"], 10.0 - 1.325 * fraction)
            self.assertAlmostEqual(command["gripper.pos"], 4.7 + 1.5 * fraction)
            before = command
        self.assertEqual(self.sent[-1]["elbow_flex.pos"], 15.3)
        requests = [json.loads(row) for row in self.trace.requests_path.read_text().splitlines()]
        request = next(row for row in requests if row["phase"] == "PRE_GUARD_REQUEST")
        first_goal = next(row for row in requests if row["phase"] == "FIRST_SENT_GOAL")
        self.assertEqual(request["requested_target"]["elbow_flex"], 15.3)
        self.assertAlmostEqual(request["limited_joint_step_degree"]["elbow_flex"], 5.3)
        self.assertEqual(first_goal["requested_target"]["elbow_flex"], 12.0)
        cycles = [json.loads(row) for row in self.trace.path.read_text().splitlines()]
        self.assertEqual(cycles[1]["relative_target"]["elbow_flex"], 12.0)

    def test_sign_reversal_follows_newest_target_without_stale_queue(self):
        def stop():
            if self.armed:
                self.leader["elbow_flex.pos"] = 15.3 if not self.sent else 7.0
            return len(self.sent) >= 4

        self.run_case(stop=stop)
        self.assertEqual([row["elbow_flex.pos"] for row in self.sent], [12.0, 10.0, 8.0, 7.0])

    def test_hold_does_not_advance_slew_origin(self):
        candidates = []

        def sender(action, elbow):
            candidates.append(dict(action))
            if len(candidates) == 1:
                return None
            return self.send(action, elbow)

        def stop():
            if self.armed:
                self.leader["elbow_flex.pos"] = 15.3
            return len(self.sent) >= 3

        self.run_case(stop=stop, sender=sender)
        self.assertEqual(candidates[0], candidates[1])
        self.assertEqual([row["elbow_flex.pos"] for row in self.sent], [12.0, 14.0, 15.3])

    def test_slew_origin_uses_actual_sender_result(self):
        def sender(action, elbow):
            actual = dict(action)
            if not self.sent:
                actual["elbow_flex.pos"] -= 1.0
            return self.send(actual, elbow)

        def stop():
            if self.armed:
                self.leader["elbow_flex.pos"] = 15.3
            return len(self.sent) >= 4

        self.run_case(stop=stop, sender=sender)
        self.assertEqual([row["elbow_flex.pos"] for row in self.sent], [11.0, 13.0, 15.0, 15.3])

    def test_stop_during_slew_has_no_queued_remaining_sends(self):
        def stop():
            if self.armed:
                self.leader["elbow_flex.pos"] = 15.3
            return bool(self.sent)

        result = self.run_case(stop=stop)
        self.assertEqual(result["goal_sends"], 1)
        self.assertEqual(self.sent[0]["elbow_flex.pos"], 12.0)

    def test_stop_at_last_dispatch_boundary_sends_nothing(self):
        stop_checks_after_arm = 0

        def stop():
            nonlocal stop_checks_after_arm
            if self.armed:
                stop_checks_after_arm += 1
                self.leader["elbow_flex.pos"] = 15.3
            return stop_checks_after_arm >= 3

        result = self.run_case(stop=stop)
        self.assertEqual(result["goal_sends"], 0)
        self.assertEqual(self.sent, [])

    def test_full_out_of_range_request_aborts_before_small_first_step(self):
        def stop():
            if self.armed:
                self.leader["shoulder_pan.pos"] = 210.0
            return False

        with self.assertRaisesRegex(RuntimeError, "target_outside_calibrated_range"):
            self.run_case(stop=stop)
        self.assertEqual(self.sent, [])

    def test_arm_slew_cannot_hide_forbidden_gripper_open(self):
        def stop():
            if self.armed:
                self.leader["elbow_flex.pos"] = 30.0
                self.leader["gripper.pos"] = 7.7
            return False

        with self.assertRaisesRegex(RuntimeError, "gripper_step_exceeds_teaching_guard"):
            self.run_case(stop=stop)
        self.assertEqual(self.sent, [])

    def test_firewall_denies_config_torque_and_prearm_goal(self):
        bus = FakeBus()
        writes = make_write_firewall(bus, goals_enabled=lambda: self.armed)
        for operation in (
            lambda: bus.write("Operating_Mode", "gripper", 0),
            lambda: bus.write_calibration({}),
            lambda: bus.enable_torque(),
            lambda: bus.disable_torque(),
            lambda: bus.sync_write("Goal_Position", {name: 10 for name in JOINTS}),
        ):
            with self.assertRaises(RuntimeError):
                operation()
        self.assertEqual(writes, [])
        self.armed = True
        bus.sync_write("Goal_Position", {name: 10 for name in JOINTS})
        self.assertEqual(len(writes), 1)
        self.assertEqual(bus.config_writes, 0)
        self.assertEqual(bus.torque_writes, 0)


class RecorderOffTeleopTests(unittest.TestCase):
    """No recorder objects, ticket, files, or hardware are created by this mode."""

    def setUp(self):
        self.clock = Clock()
        self.leader = {key: 4.7 if key == "gripper.pos" else 10.0 for key in ACTION_KEYS}
        self.follower = dict(self.leader)
        self.sample = diagnostics()
        self.armed = False
        self.ready_times = []
        self.origin_times = []
        self.diagnostic_times = []
        self.sent = []

    def read_follower(self):
        self.origin_times.append(self.clock.monotonic())
        return dict(self.follower)

    def read_diagnostics(self):
        self.diagnostic_times.append(self.clock.monotonic())
        return dict(self.sample)

    def ready(self):
        self.assertEqual(self.sent, [])
        self.assertGreaterEqual(self.clock.monotonic(), 3.0)
        self.ready_times.append(self.clock.monotonic())
        self.armed = True

    def send(self, action, _elbow):
        self.assertTrue(self.armed)
        self.sent.append(dict(action))
        return dict(action)

    def run_case(self, **overrides):
        options = dict(
            trace=None, recorder_off=True, pre_connect=self.sample,
            read_leader=lambda: dict(self.leader),
            read_leader_torque=lambda: {name: 0 for name in JOINTS},
            read_follower_action=self.read_follower,
            read_diagnostics=self.read_diagnostics,
            read_follower_torque=lambda: {name: 1 for name in JOINTS},
            bounds={name: (-200.0, 200.0) for name in JOINTS},
            send_guarded=self.send, enable_goals=self.ready,
            arm_confirm=lambda: True, stop_requested=lambda: self.armed,
            monotonic=self.clock.monotonic, sleep=self.clock.sleep,
            hold_policy="quantized",
        )
        options.update(overrides)
        return run_teaching_from_hold(**options)

    def test_explicit_recorder_off_skips_files_ticket_and_initial_goal(self):
        with tempfile.TemporaryDirectory() as folder:
            ticket = Path(folder) / "must-not-be-consumed.ticket"
            ticket.touch()
            with patch.dict(os.environ, {"LELAB_TELEOP_TRACE_ONCE_TICKET": str(ticket)}), \
                    patch.object(Path, "write_text", side_effect=AssertionError("file write")), \
                    patch.object(CycleTrace, "__init__", side_effect=AssertionError("trace created")):
                result = self.run_case()
            self.assertTrue(ticket.exists())
            self.assertEqual(list(Path(folder).iterdir()), [ticket])
        self.assertEqual(result["status"], "STOPPED")
        self.assertTrue(result["first_goal_skipped"])
        self.assertEqual(result["goal_sends"], 0)
        self.assertEqual(self.sent, [])
        self.assertEqual(len(self.ready_times), 1)
        self.assertEqual(len(self.origin_times), 1)
        self.assertGreaterEqual(self.origin_times[0], 3.0)
        self.assertGreaterEqual(result["stillness_samples"], 30)
        self.assertEqual(result["final_read_only_samples"], 3)
        self.assertAlmostEqual(self.diagnostic_times[-1] - self.diagnostic_times[-3], 0.4)

    def test_missing_trace_is_not_implicit_recorder_off_permission(self):
        with self.assertRaisesRegex(RuntimeError, "empirical_recorder_required"):
            self.run_case(recorder_off=False)
        self.assertFalse(self.armed)
        self.assertEqual(self.diagnostic_times, [])

    def test_recorder_off_cannot_silently_ignore_existing_trace(self):
        with self.assertRaisesRegex(ValueError, "recorder_off_trace_conflict"):
            self.run_case(trace=object())
        self.assertFalse(self.armed)

    def test_slew_uses_shared_fraction_and_two_degree_guard_without_recorder(self):
        def stop():
            if self.armed:
                self.leader["elbow_flex.pos"] = 15.3
                self.leader["shoulder_pan.pos"] = 12.65
            return len(self.sent) >= 3

        result = self.run_case(stop_requested=stop)
        self.assertEqual(result["goal_sends"], 3)
        self.assertLessEqual(result["max_emitted_arm_step_deg"], 2.0)
        previous = self.follower
        for action in self.sent:
            self.assertFalse(oversized_arm_steps(action, previous))
            self.assertAlmostEqual(action["shoulder_pan.pos"] - 10.0,
                                   (action["elbow_flex.pos"] - 10.0) / 2.0)
            previous = action
        self.assertEqual(self.sent[-1]["elbow_flex.pos"], 15.3)

    def test_stop_discards_unsent_remaining_steps_without_recorder(self):
        def stop():
            if self.armed:
                self.leader["elbow_flex.pos"] = 15.3
            return bool(self.sent)

        result = self.run_case(stop_requested=stop)
        self.assertEqual(result["goal_sends"], 1)
        self.assertEqual(self.sent[0]["elbow_flex.pos"], 12.0)

    def test_sender_hold_does_not_advance_slew_origin_without_recorder(self):
        attempted = []

        def sender(action, elbow):
            attempted.append(dict(action))
            if len(attempted) == 1:
                return None
            return self.send(action, elbow)

        def stop():
            if self.armed:
                self.leader["elbow_flex.pos"] = 15.3
            return len(self.sent) >= 3

        result = self.run_case(stop_requested=stop, send_guarded=sender)
        self.assertEqual(result["goal_sends"], 3)
        self.assertEqual(attempted[0], attempted[1])
        self.assertEqual([row["elbow_flex.pos"] for row in self.sent], [12.0, 14.0, 15.3])

    def test_stop_before_ready_never_arms_or_sends(self):
        result = self.run_case(stop_requested=lambda: True)
        self.assertEqual(result["status"], "STOPPED_BEFORE_ARM")
        self.assertEqual(self.ready_times, [])
        self.assertEqual(self.sent, [])

    def test_recorder_off_retains_gripper_close_guard(self):
        def stop():
            if self.armed:
                self.leader["gripper.pos"] = 3.7
            return False

        with self.assertRaisesRegex(RuntimeError, "gripper_close_forbidden"):
            self.run_case(stop_requested=stop)
        self.assertEqual(self.sent, [])

    def test_recorder_off_retains_torque_on_startup_guard(self):
        with self.assertRaisesRegex(RuntimeError, "torque_not_all_on"):
            self.run_case(read_follower_torque=lambda: {name: 0 for name in JOINTS})
        self.assertFalse(self.armed)
        self.assertEqual(self.sent, [])

    def test_recorder_off_retains_three_second_present_goal_stillness(self):
        for field, error in (("present_raw", "present_drift_during_startup"),
                             ("goal_raw", "goal_changed_before_arm")):
            with self.subTest(field=field):
                self.setUp()

                def read_diagnostics():
                    sample = diagnostics()
                    if self.clock.monotonic() >= 1.5:
                        sample[field]["wrist_flex"] += 1
                    return sample

                with self.assertRaisesRegex(RuntimeError, error):
                    self.run_case(read_diagnostics=read_diagnostics)
                self.assertFalse(self.armed)
                self.assertEqual(self.sent, [])

    def test_recorder_off_retains_external_goal_change_abort(self):
        def read_diagnostics():
            sample = diagnostics()
            if self.armed:
                sample["goal_raw"]["wrist_flex"] += 1
            return sample

        with self.assertRaisesRegex(RuntimeError, "external_goal_change_during_teaching"):
            self.run_case(read_diagnostics=read_diagnostics, stop_requested=lambda: False)
        self.assertEqual(self.sent, [])

    def test_imports_use_containing_package_not_fixed_scripts_name(self):
        package_name = "fake_lelab_current_hold"
        package = types.ModuleType(package_name)
        package.__path__ = [str(Path(__file__).resolve().parents[1] / "scripts")]
        with patch.dict(sys.modules, {package_name: package}):
            module = importlib.import_module(
                f"{package_name}.supervised_teaching_from_current_hold")
            self.assertEqual(module.CycleTrace.__module__,
                             f"{package_name}.teleop_cycle_trace")
            self.assertEqual(module.capture_origins.__module__,
                             f"{package_name}.relative_start_teleop")


class CoordinatedSlewTests(unittest.TestCase):
    def test_boundaries_preserve_two_degree_cap(self):
        for delta, expected_count in ((1.5, 1), (2.0, 1), (2.1, 2), (4.0, 2),
                                      (5.3, 3), (-5.3, 3), (10.1, 6)):
            with self.subTest(delta=delta):
                previous = {key: 0.0 for key in ACTION_KEYS}
                requested = {**previous, "elbow_flex.pos": delta}
                steps = []
                while previous != requested and len(steps) < 20:
                    emitted, fraction = slew_relative_target(requested, previous)
                    self.assertGreater(fraction, 0.0)
                    self.assertLessEqual(fraction, 1.0)
                    self.assertFalse(oversized_arm_steps(emitted, previous))
                    steps.append(emitted["elbow_flex.pos"] - previous["elbow_flex.pos"])
                    previous = emitted
                self.assertEqual(previous, requested)
                self.assertEqual(len(steps), expected_count)
                if abs(delta) <= 2.0:
                    self.assertEqual(steps, [delta])

    def test_common_fraction_includes_gripper(self):
        before = {key: 10.0 for key in ACTION_KEYS}
        requested = dict(zip(ACTION_KEYS, (15.3, 7.35, 11.325, 6.0, 10.0, 11.0)))
        emitted, fraction = slew_relative_target(requested, before)
        self.assertAlmostEqual(fraction, 2.0 / 5.3)
        for key in ACTION_KEYS:
            self.assertAlmostEqual(emitted[key], before[key] + fraction * (requested[key] - before[key]))
        self.assertFalse(oversized_arm_steps(emitted, before))

    def test_floating_roundoff_never_relaxes_strict_guard(self):
        generator = random.Random(20261015)
        for _ in range(1000):
            before = {key: generator.uniform(-90.0, 90.0) for key in ACTION_KEYS}
            requested = {key: generator.uniform(-90.0, 90.0) for key in ACTION_KEYS}
            emitted, _fraction = slew_relative_target(requested, before)
            self.assertFalse(oversized_arm_steps(emitted, before))
            self.assertLessEqual(abs(emitted["gripper.pos"] - before["gripper.pos"]), 2.0)

    def test_invalid_or_nonfinite_input_fails(self):
        before = {key: 0.0 for key in ACTION_KEYS}
        for invalid in ({}, {**before, "elbow_flex.pos": float("nan")},
                        {**before, "elbow_flex.pos": float("inf")}):
            with self.assertRaises(ValueError):
                slew_relative_target(invalid, before)


class HoldStableQuantizedTests(unittest.TestCase):
    def samples(self, gap=0):
        first = diagnostics()
        first["present_raw"] = dict(QUANTIZED_REFERENCE_PRESENT_RAW)
        first["goal_raw"] = dict(first["present_raw"])
        first["goal_raw"]["shoulder_lift"] -= gap
        return [first, {
            **first,
            "present_raw": dict(first["present_raw"]),
            "goal_raw": dict(first["goal_raw"]),
            "moving": dict(first["moving"]),
            "temperature_c": dict(first["temperature_c"]),
        }]

    def test_stable_zero_raw_pass(self):
        self.assertTrue(hold_stable_quantized(self.samples(0)))

    def test_stable_one_raw_pass(self):
        self.assertTrue(hold_stable_quantized(self.samples(1)))

    def test_two_raw_fails(self):
        self.assertFalse(hold_stable_quantized(self.samples(2)))

    def test_moving_fails(self):
        samples = self.samples(1)
        samples[1]["moving"]["elbow_flex"] = 1
        self.assertFalse(hold_stable_quantized(samples))

    def test_present_drift_fails(self):
        samples = self.samples(1)
        samples[1]["present_raw"]["elbow_flex"] += 1
        self.assertFalse(hold_stable_quantized(samples))

    def test_goal_drift_fails(self):
        samples = self.samples(1)
        samples[1]["goal_raw"]["elbow_flex"] += 1
        self.assertFalse(hold_stable_quantized(samples))

    def test_recorded_six_samples_pass(self):
        samples = self.samples(1)
        samples[0]["goal_raw"]["wrist_roll"] -= 1
        samples[1]["goal_raw"]["wrist_roll"] -= 1
        self.assertTrue(hold_stable_quantized([samples[0], *(
            {**samples[1], "present_raw": dict(samples[1]["present_raw"]),
             "goal_raw": dict(samples[1]["goal_raw"])} for _ in range(5))]))

    def test_temperature_fault_fails(self):
        samples = self.samples(1)
        samples[1]["temperature_c"]["elbow_flex"] = 56
        self.assertFalse(hold_stable_quantized(samples))


class PreArmHoldStabilityTests(unittest.TestCase):
    def samples(self, gap=2):
        first = diagnostics()
        first["present_raw"] = dict(QUANTIZED_REFERENCE_PRESENT_RAW)
        first["goal_raw"] = dict(first["present_raw"])
        first["goal_raw"]["shoulder_lift"] -= gap
        second = {**first, "present_raw": dict(first["present_raw"]),
                  "goal_raw": dict(first["goal_raw"]),
                  "moving": dict(first["moving"]),
                  "temperature_c": dict(first["temperature_c"])}
        return [first, second]

    def test_observed_two_raw_and_ten_raw_stable_pass(self):
        self.assertTrue(pre_arm_hold_stability(self.samples(2)))
        self.assertTrue(pre_arm_hold_stability(self.samples(10)))

    def test_above_observed_bound_fails(self):
        self.assertFalse(pre_arm_hold_stability(self.samples(11)))

    def test_present_or_goal_drift_fails(self):
        samples = self.samples()
        samples[1]["present_raw"]["shoulder_lift"] += 1
        self.assertFalse(pre_arm_hold_stability(samples))
        samples = self.samples()
        samples[1]["goal_raw"]["shoulder_lift"] -= 1
        self.assertFalse(pre_arm_hold_stability(samples))

    def test_moving_or_temperature_fault_fails(self):
        samples = self.samples()
        samples[1]["moving"]["elbow_flex"] = 1
        self.assertFalse(pre_arm_hold_stability(samples))
        samples = self.samples()
        samples[1]["temperature_c"]["elbow_flex"] = 56
        self.assertFalse(pre_arm_hold_stability(samples))


if __name__ == "__main__":
    unittest.main()
