from pathlib import Path
import io
import json
import math
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from scripts.so101_exclusive_bus import ExclusiveFollowerLease, PreflightError, SystemBusProbe
from scripts.so101_follower_transport import SO101FollowerTransport
from scripts.staged_cycle_execution import JOINT_UNITS, StagedCycle


GOAL = {name: (50.0 if name == "gripper" else 2.0) for name in JOINT_UNITS}


class FakeProbe:
    def __init__(self):
        self.controls_idle = True
        self.serial = "5AE6058306"
        self.pids = set()

    def lelab_controls_idle(self):
        return self.controls_idle

    def serial_short(self, port):
        return self.serial

    def owner_pids(self, port):
        return self.pids


class FakeBus:
    def __init__(self):
        self.closed_with = None
        self.motors = {name: SimpleNamespace(id=index + 1)
                       for index, name in enumerate(JOINT_UNITS)}
        self.goal_raw = 2020
        self.present_raw = 2015
        self.read_calls = []

    def disconnect(self, disable_torque):
        self.closed_with = disable_torque

    def sync_read(self, register, *, normalize, num_retry=0):
        if normalize is not False:
            raise AssertionError("unexpected normalized sync read")
        if register == "Present_Position":
            return {name: 2000 + index for index, name in enumerate(JOINT_UNITS)}
        if register == "Goal_Position":
            return {name: 2020 + index for index, name in enumerate(JOINT_UNITS)}
        if register == "Moving":
            return {name: 0 for name in JOINT_UNITS}
        if register == "Present_Load":
            return {name: 24 + index for index, name in enumerate(JOINT_UNITS)}
        raise AssertionError("unexpected raw read")

    def _unnormalize(self, ids_values):
        return {motor_id: int(2000 + value * 10)
                for motor_id, value in ids_values.items()}

    def _normalize(self, ids_values):
        return {motor_id: (value - 2000) / 10
                for motor_id, value in ids_values.items()}

    def read(self, register, motor, *, normalize, num_retry):
        self.read_calls.append((register, motor, normalize, num_retry))
        values = {
            "Goal_Position": self.goal_raw,
            "Present_Position": self.present_raw,
            "Moving": 0,
            "Present_Load": 24,
            "Present_Temperature": 38,
        }
        return values[register]


class FakeRobot:
    def __init__(self):
        self.bus = FakeBus()
        self.sent = []
        self.observed = {f"{name}.pos": value for name, value in GOAL.items()}

    def send_action(self, action):
        self.sent.append(dict(action))
        if "elbow_flex.pos" in action:
            self.bus.goal_raw = int(2000 + action["elbow_flex.pos"] * 10)
        return action

    def get_observation(self):
        return dict(self.observed)


class ExclusiveTransportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.probe = FakeProbe()
        self.lease = ExclusiveFollowerLease(
            self.probe, port=Path("/dev/fake-follower"),
            lock_path=Path(self.temp.name) / "owner.lock", own_pid=4321)

    def tearDown(self):
        self.lease.release()
        self.temp.cleanup()

    def test_rejects_live_lelab_wrong_usb_or_port_owner(self):
        for change, reason in (({"controls_idle": False}, "lelab_motor_control_not_idle"),
                               ({"serial": "leader"}, "wrong_follower_usb_identity"),
                               ({"pids": {123}}, "follower_port_busy")):
            self.probe = FakeProbe()
            for key, value in change.items():
                setattr(self.probe, key, value)
            self.lease.probe = self.probe
            with self.assertRaisesRegex(PreflightError, reason):
                self.lease.acquire()
        self.assertIsNone(self.lease._lock_file)

    def test_rejects_second_program_lease_and_runtime_overlap(self):
        self.lease.acquire()
        second = ExclusiveFollowerLease(
            FakeProbe(), port=self.lease.port,
            lock_path=self.lease.lock_path, own_pid=5555)
        with self.assertRaises(PreflightError):
            second.acquire()
        self.probe.pids = {4321}
        self.lease.mark_connected()
        self.probe.controls_idle = False
        with self.assertRaisesRegex(PreflightError, "lelab_motor_control_started"):
            self.lease.ensure_exclusive()

    def test_action_shape_units_and_fresh_observation_through_executor(self):
        self.lease.acquire()
        self.probe.pids = {4321}
        self.lease.mark_connected()
        robot = FakeRobot()
        adapter = SO101FollowerTransport(robot, self.lease)
        with self.assertRaisesRegex(PreflightError, "start_pose_not_verified"):
            adapter.send_goal(GOAL)
        adapter.verify_start_pose(GOAL, {name: 0.5 for name in JOINT_UNITS})
        controller = StagedCycle(adapter, {name: 0.5 for name in JOINT_UNITS},
                                 timeout_s=0.1, feedback_max_age_s=0.05,
                                 stable_s=0.0, poll_s=0.001)
        controller.start_stage("approach", GOAL, approved=True)
        self.assertTrue(controller.wait_worker(1))
        self.assertEqual(controller.command_state, "TRANSMITTED_UNACKNOWLEDGED")
        self.assertEqual(controller.reach_state, "GOAL_REACHED")
        self.assertEqual(controller.task_state, "USER_CONFIRMATION_REQUIRED")
        self.assertEqual(robot.sent, [{f"{name}.pos": value for name, value in GOAL.items()}])
        self.assertEqual(adapter.read_feedback().positions, GOAL)
        self.assertEqual(adapter.read_raw_feedback()["elbow_flex"], 2002)
        with self.assertRaisesRegex(PreflightError, "command_stop_and_site_stability"):
            adapter.close_after_site_confirmation(controller, object_supported=True)
        controller.request_stop()
        self.assertTrue(controller.verify_stop_completed())
        with self.assertRaisesRegex(PreflightError, "command_production_stopped"):
            adapter.send_goal(GOAL)
        self.assertTrue(controller.verify_arm_stopped(
            motion_tolerances={name: 0.5 for name in JOINT_UNITS},
            window_s=0.005, timeout_s=0.1, human_confirmed=True))
        with self.assertRaisesRegex(PreflightError, "command_stop_and_site_stability"):
            adapter.close_after_site_confirmation(controller, object_supported=False)
        adapter.close_after_site_confirmation(controller, object_supported=True)
        self.assertIs(robot.bus.closed_with, False)

    def test_restart_blocks_send_even_after_connection(self):
        self.lease.acquire()
        self.probe.pids = {4321}
        self.lease.mark_connected()
        robot = FakeRobot()
        adapter = SO101FollowerTransport(robot, self.lease)
        adapter.verify_start_pose(GOAL, {name: 0.5 for name in JOINT_UNITS})
        self.probe.controls_idle = False
        with self.assertRaisesRegex(PreflightError, "lelab_motor_control_started"):
            adapter.send_goal(GOAL)
        self.assertEqual(robot.sent, [])

    def test_invalid_or_failed_recheck_revokes_start_permission(self):
        self.lease.acquire()
        self.probe.pids = {4321}
        self.lease.mark_connected()
        robot = FakeRobot()
        adapter = SO101FollowerTransport(robot, self.lease)
        tolerance = {name: 0.5 for name in JOINT_UNITS}
        with self.assertRaisesRegex(PreflightError, "invalid_start_pose_contract"):
            adapter.verify_start_pose({**GOAL, "elbow_flex": math.nan}, tolerance)
        adapter.verify_start_pose(GOAL, tolerance)
        with self.assertRaisesRegex(PreflightError, "start_pose_mismatch"):
            adapter.verify_start_pose({**GOAL, "elbow_flex": 20.0}, tolerance)
        with self.assertRaisesRegex(PreflightError, "start_pose_not_verified"):
            adapter.send_goal(GOAL)
        self.assertEqual(robot.sent, [])

    def test_goal_uses_servo_calibration_not_urdf_as_runtime_block(self):
        self.lease.acquire()
        self.probe.pids = {4321}
        self.lease.mark_connected()
        robot = FakeRobot()
        bounds = {**{name: (-100.0, 100.0) for name in JOINT_UNITS},
                  "gripper": (0.0, 100.0)}
        adapter = SO101FollowerTransport(robot, self.lease, calibrated_bounds=bounds)
        adapter.verify_start_pose(GOAL, {name: 0.5 for name in JOINT_UNITS})
        accepted = {**GOAL, "elbow_flex": 94.0}
        self.assertEqual(adapter.send_goal(accepted), accepted)
        self.assertEqual(len(robot.sent), 1)
        for changed in ({**GOAL, "elbow_flex": 100.001},
                        {**GOAL, "gripper": 100.001}):
            with self.assertRaisesRegex(ValueError, "goal_outside_follower_servo_calibration"):
                adapter.send_goal(changed)
        self.assertEqual(len(robot.sent), 1)

    def test_gripper_only_send_requires_start_latch_and_honors_stop_latch(self):
        self.lease.acquire()
        self.probe.pids = {4321}
        self.lease.mark_connected()
        robot = FakeRobot()
        adapter = SO101FollowerTransport(robot, self.lease)

        with self.assertRaisesRegex(PreflightError, "start_pose_not_verified"):
            adapter.send_gripper_goal_only(35.0)
        adapter.verify_start_pose(GOAL, {name: 0.5 for name in JOINT_UNITS})
        adapter.stop_commands()
        with self.assertRaisesRegex(PreflightError, "command_production_stopped"):
            adapter.send_gripper_goal_only(35.0)
        self.assertEqual(robot.sent, [])

    def test_gripper_only_send_validates_finite_calibrated_target(self):
        self.lease.acquire()
        self.probe.pids = {4321}
        self.lease.mark_connected()
        robot = FakeRobot()
        adapter = SO101FollowerTransport(robot, self.lease)
        adapter.verify_start_pose(GOAL, {name: 0.5 for name in JOINT_UNITS})

        for invalid in (math.nan, math.inf, -math.inf, True, "35"):
            with self.assertRaisesRegex(ValueError, "invalid_gripper_goal"):
                adapter.send_gripper_goal_only(invalid)
        for outside in (-0.001, 100.001):
            with self.assertRaisesRegex(
                    ValueError, "goal_outside_follower_servo_calibration"):
                adapter.send_gripper_goal_only(outside)
        self.assertEqual(robot.sent, [])

    def test_gripper_only_send_uses_exact_singleton_action_and_can_repeat(self):
        self.lease.acquire()
        self.probe.pids = {4321}
        self.lease.mark_connected()
        robot = FakeRobot()
        adapter = SO101FollowerTransport(robot, self.lease)
        adapter.verify_start_pose(GOAL, {name: 0.5 for name in JOINT_UNITS})

        self.assertEqual(
            adapter.send_gripper_goal_only(35), {"gripper": 35.0})
        self.assertEqual(
            adapter.send_gripper_goal_only(36.5), {"gripper": 36.5})
        self.assertEqual(robot.sent, [
            {"gripper.pos": 35.0},
            {"gripper.pos": 36.5},
        ])
        self.assertTrue(all(set(action) == {"gripper.pos"}
                            for action in robot.sent))

    def test_gripper_only_send_rejects_non_singleton_sdk_return(self):
        self.lease.acquire()
        self.probe.pids = {4321}
        self.lease.mark_connected()
        robot = FakeRobot()
        adapter = SO101FollowerTransport(robot, self.lease)
        adapter.verify_start_pose(GOAL, {name: 0.5 for name in JOINT_UNITS})

        def mismatched_return(action):
            robot.sent.append(dict(action))
            return {**action, "elbow_flex.pos": 2.0}

        robot.send_action = mismatched_return
        with self.assertRaisesRegex(ValueError, "send_action_return_shape_mismatch"):
            adapter.send_gripper_goal_only(35.0)
        self.assertEqual(robot.sent, [{"gripper.pos": 35.0}])
        self.assertFalse(adapter._busy)
        self.assertTrue(adapter._ever_sent)

    def test_gripper_only_send_failure_is_still_a_write_attempt(self):
        self.lease.acquire()
        self.probe.pids = {4321}
        self.lease.mark_connected()
        robot = FakeRobot()
        adapter = SO101FollowerTransport(robot, self.lease)
        adapter.verify_start_pose(GOAL, {name: 0.5 for name in JOINT_UNITS})

        def failed_send(action):
            robot.sent.append(dict(action))
            raise RuntimeError("sdk_write_failed")

        robot.send_action = failed_send
        with self.assertRaisesRegex(RuntimeError, "sdk_write_failed"):
            adapter.send_gripper_goal_only(35.0)
        self.assertEqual(robot.sent, [{"gripper.pos": 35.0}])
        self.assertFalse(adapter._busy)
        self.assertTrue(adapter._ever_sent)
        with self.assertRaisesRegex(
                PreflightError, "unstarted_session_site_confirmation_required"):
            adapter.close_without_motion(arm_stable=True, object_supported=True)

    def test_read_only_session_can_close_without_goal_or_torque_disable(self):
        self.lease.acquire()
        self.probe.pids = {4321}
        self.lease.mark_connected()
        robot = FakeRobot()
        adapter = SO101FollowerTransport(robot, self.lease)
        adapter.read_feedback()
        adapter.read_raw_feedback()
        with self.assertRaisesRegex(PreflightError, "site_confirmation_required"):
            adapter.close_without_motion(arm_stable=False, object_supported=True)
        adapter.close_without_motion(arm_stable=True, object_supported=True)
        self.assertIs(robot.bus.closed_with, False)
        self.assertIsNone(self.lease._lock_file)

    def test_continuous_following_telemetry_reads_all_required_raw_registers(self):
        self.lease.acquire()
        self.probe.pids = {4321}
        self.lease.mark_connected()
        adapter = SO101FollowerTransport(FakeRobot(), self.lease)
        sample = adapter.read_following_telemetry()
        self.assertEqual(set(sample.positions), set(JOINT_UNITS))
        self.assertEqual(sample.goal_raw["elbow_flex"], 2022)
        self.assertEqual(sample.present_raw["elbow_flex"], 2002)
        self.assertEqual(sample.positions["elbow_flex"], 0.2)
        self.assertEqual(sample.moving["elbow_flex"], 0)
        self.assertEqual(sample.present_load["elbow_flex"], 26)
        self.assertEqual(sample.temperature_c["elbow_flex"], 38)
        temperature_reads = [call for call in adapter.robot.bus.read_calls
                             if call[0] == "Present_Temperature"]
        self.assertEqual(
            temperature_reads,
            [("Present_Temperature", name, False, 2) for name in JOINT_UNITS],
        )
        self.assertEqual(adapter.robot.sent, [])

    def test_escape_telemetry_reads_temperature_and_status_individually(self):
        self.lease.acquire()
        self.probe.pids = {4321}
        self.lease.mark_connected()
        adapter = SO101FollowerTransport(FakeRobot(), self.lease)
        sample = adapter.read_escape_telemetry()
        self.assertEqual(sample.goal_raw["elbow_flex"], 2020)
        self.assertEqual(sample.present_raw["elbow_flex"], 2015)
        self.assertEqual(sample.positions["elbow_flex"], 1.5)
        self.assertEqual(sample.temperature_c["elbow_flex"], 38)
        self.assertEqual(adapter.robot.sent, [])
        self.assertTrue(all(call[0] in {
            "Goal_Position", "Present_Position", "Moving", "Present_Load",
            "Present_Temperature"
        } for call in adapter.robot.bus.read_calls))

    def test_elbow_diagnostic_uses_raw_readback_and_read_only_settle(self):
        self.lease.acquire()
        self.probe.pids = {4321}
        self.lease.mark_connected()
        robot = FakeRobot()
        adapter = SO101FollowerTransport(robot, self.lease)
        adapter.verify_start_pose(GOAL, {name: 0.5 for name in JOINT_UNITS})
        adapter.configure_elbow_diagnostic(total_waypoints=20, tail_waypoints=1)
        adapter.send_goal(GOAL)
        adapter.read_feedback()
        adapter.send_goal(GOAL)
        adapter.read_feedback()
        with (patch("scripts.so101_follower_transport.time.monotonic",
                    side_effect=[0.0, 0.5, 1.0, 1.5, 2.0]),
              patch("scripts.so101_follower_transport.time.sleep")):
            settle = adapter.collect_final_elbow_settle(
                duration_s=2.0, interval_s=0.15)
        report = adapter.elbow_diagnostic_report()
        self.assertEqual(len(settle), 4)
        self.assertEqual(len(report["samples"]), 5)
        first = report["samples"][0]
        self.assertEqual(first["waypoint_index"], 2)
        self.assertEqual(first["calculated_target_raw"], 2020)
        self.assertEqual(first["goal_position_raw_readback"], 2020)
        self.assertEqual(first["present_position_raw"], 2015)
        self.assertEqual(first["goal_minus_present_raw"], 5)
        self.assertEqual(first["feedback_deg"], 1.5)
        self.assertEqual(first["error_deg"], -0.5)
        self.assertEqual(first["moving"], 0)
        self.assertEqual(first["present_load"], 24)
        self.assertIn("timestamp", first)
        self.assertIn("send_time", first)
        self.assertIn("send_time_unix_ns", first)
        self.assertIn("send_time_monotonic_ns", first)
        self.assertIn("feedback_time", first)
        self.assertGreaterEqual(
            first["feedback_time_monotonic_ns"],
            first["feedback_read_started_monotonic_ns"])
        self.assertTrue(all(call[0] in {
            "Goal_Position", "Present_Position", "Moving", "Present_Load"
        } for call in robot.bus.read_calls))
        self.assertEqual(len(robot.sent), 2)

    def test_system_probe_parses_identity_and_unowned_port(self):
        port = Path("/dev/ttyACM0")
        with patch.object(Path, "exists", return_value=True), \
             patch("scripts.so101_exclusive_bus.FIXED_PORT_OCCUPANCY_HELPER") as helper:
            helper.is_file.return_value = False
            probe = SystemBusProbe()
            from subprocess import CompletedProcess
            responses = {
                "udevadm": CompletedProcess([], 0,
                    "ID_SERIAL_SHORT=5AE6058306\n", ""),
                "fuser": CompletedProcess([], 1, "", ""),
            }
            probe._run = lambda argv: responses[argv[0]]
            self.assertEqual(probe.serial_short(port), "5AE6058306")
            self.assertEqual(probe.owner_pids(port), set())
            responses["fuser"] = CompletedProcess([], 0, "4321 9876\n", "")
            self.assertEqual(probe.owner_pids(port), {4321, 9876})

    def test_system_probe_requires_privileged_scan_for_incomplete_fuser_result(self):
        from subprocess import CompletedProcess

        port = Path("/dev/ttyACM0")
        with patch.object(Path, "exists", return_value=True), \
             patch("scripts.so101_exclusive_bus.FIXED_PORT_OCCUPANCY_HELPER") as helper:
            helper.is_file.return_value = False
            probe = SystemBusProbe()
            calls = []

            def run(argv):
                calls.append(argv)
                if argv[0] == "fuser":
                    return CompletedProcess(argv, 1, "", "Cannot stat /proc/1/fd/0: Permission denied\n")
                return CompletedProcess(argv, 1, "", "")

            probe._run = run
            self.assertEqual(probe.owner_pids(port), set())
            self.assertEqual(calls, [["fuser", str(port)], ["sudo", "-n", "fuser", str(port)]])

    def test_lelab_control_probe_fails_closed_if_any_task_active(self):
        probe = SystemBusProbe()

        def idle_response(url, timeout):
            field = dict(probe.CONTROL_STATES)[url.rsplit("/", 1)[-1]]
            return io.BytesIO(json.dumps({field: False}).encode())

        with patch("scripts.so101_exclusive_bus.urlopen", side_effect=idle_response):
            self.assertTrue(probe.lelab_controls_idle())

        def active_response(url, timeout):
            field = dict(probe.CONTROL_STATES)[url.rsplit("/", 1)[-1]]
            return io.BytesIO(json.dumps({field: field == "recording_active"}).encode())

        with patch("scripts.so101_exclusive_bus.urlopen", side_effect=active_response):
            self.assertFalse(probe.lelab_controls_idle())


if __name__ == "__main__":
    unittest.main()
