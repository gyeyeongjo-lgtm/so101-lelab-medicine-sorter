import contextlib
import io
import os
from pathlib import Path
import tempfile
import unittest

from scripts.atomic_hold_restore import AXES, OneShotRawWrites
from scripts.relative_start_teleop import ACTION_KEYS, JOINTS, oversized_arm_steps
from scripts.single_session_demo import main, run_single_session_lifecycle
from scripts.supervised_teaching_from_current_hold import run_teaching_from_hold
from scripts.teleop_cycle_trace import CycleTrace


class Clock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, duration):
        self.now += duration


class FakeFollowerBus:
    def __init__(self):
        self.present = dict(zip(AXES, (2021, 835, 3091, 2585, 1942, 487)))
        self.goal = dict(zip(AXES, (2025, 839, 3093, 2570, 1941, 481)))
        self.torque = dict.fromkeys(AXES, 0)
        self.moving = dict.fromkeys(AXES, 0)
        self.temperature = dict.fromkeys(AXES, 37)
        self.is_connected = False
        self.connect_calls = 0
        self.disconnect_calls = []
        self.atomic_packets = []
        self.teaching_packets = []

    def connect(self, *, handshake):
        assert handshake is False
        self.connect_calls += 1
        self.is_connected = True

    def disconnect(self, *, disable_torque):
        self.disconnect_calls.append(disable_torque)
        if disable_torque:
            self.torque = dict.fromkeys(AXES, 0)
        self.is_connected = False

    def sync_read(self, register, *, normalize=False, num_retry=0):
        assert self.is_connected
        return dict({
            "Present_Position": self.present,
            "Goal_Position": self.goal,
            "Torque_Enable": self.torque,
            "Moving": self.moving,
        }[register])

    def read(self, register, axis, *, normalize, num_retry):
        assert self.is_connected
        assert register == "Present_Temperature"
        assert normalize is False and num_retry == 0
        return self.temperature[axis]

    def sync_write(self, register, values, *args, **kwargs):
        assert self.is_connected
        if kwargs == {"normalize": False, "num_retry": 0}:
            self.atomic_packets.append((register, dict(values)))
            if register == "Goal_Position":
                assert set(self.torque.values()) == {0}
                self.goal = dict(values)
            elif register == "Torque_Enable":
                assert self.goal == self.present
                assert set(values.values()) == {1}
                self.torque = dict(values)
            else:
                raise AssertionError("unexpected atomic packet")
        else:
            assert register == "Goal_Position"
            self.teaching_packets.append(dict(values))

    def write(self, *_args, **_kwargs):
        raise AssertionError("config write forbidden")

    enable_torque = write
    disable_torque = write
    write_calibration = write
    configure_motors = write


class SingleSessionDemoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.old_ticket = os.environ.get("LELAB_TELEOP_TRACE_ONCE_TICKET")
        self.addCleanup(self.restore_ticket)
        self.ticket = Path(self.temp.name) / "once.ticket"
        self.ticket.touch()
        os.environ["LELAB_TELEOP_TRACE_ONCE_TICKET"] = str(self.ticket)
        self.trace = CycleTrace(Path(self.temp.name) / "trace",
                                capture_kind="empirical_relative_teaching")
        self.addCleanup(self.close_trace)
        self.clock = Clock()
        self.bus = FakeFollowerBus()
        self.gate = OneShotRawWrites(self.bus)
        self.bus.connect(handshake=False)
        self.leader = {key: 4.7 if key == "gripper.pos" else 10.0
                       for key in ACTION_KEYS}
        self.follower_action = dict(self.leader)
        self.armed = False
        self.sent = []

    def restore_ticket(self):
        if self.old_ticket is None:
            os.environ.pop("LELAB_TELEOP_TRACE_ONCE_TICKET", None)
        else:
            os.environ["LELAB_TELEOP_TRACE_ONCE_TICKET"] = self.old_ticket

    def close_trace(self):
        if not self.trace.closed:
            self.trace.finish(stop_reason="worker_error")

    def diagnostics(self):
        present = dict(self.bus.present)
        goal = dict(self.bus.goal)
        return {
            "present_raw": present,
            "goal_raw": goal,
            "present_degree_or_percent": {name: float(present[name]) for name in JOINTS},
            "goal_degree_or_percent": {name: float(goal[name]) for name in JOINTS},
            "moving": dict(self.bus.moving),
            "temperature_c": dict(self.bus.temperature),
            "present_load_diagnostic": dict.fromkeys(JOINTS, 0),
            "fk_grasp_tcp_mm": [0.0, 0.0, 80.0],
        }

    def test_hold_and_teaching_share_one_connection_and_keep_two_degree_cap(self):
        def stop_requested():
            if self.armed:
                self.leader["elbow_flex.pos"] = 15.3
            return len(self.sent) >= 3

        def send(action, _previous_elbow):
            self.assertTrue(self.bus.is_connected)
            self.assertTrue(self.armed)
            values = {name: action[f"{name}.pos"] for name in JOINTS}
            self.bus.sync_write("Goal_Position", values)
            self.sent.append(dict(action))
            return dict(action)

        def teaching(pre_connect):
            return run_teaching_from_hold(
                trace=self.trace, pre_connect=pre_connect,
                read_leader=lambda: dict(self.leader),
                read_leader_torque=lambda: dict.fromkeys(JOINTS, 0),
                read_follower_action=lambda: dict(self.follower_action),
                read_diagnostics=self.diagnostics,
                read_follower_torque=lambda: dict(self.bus.torque),
                bounds={name: (-4000.0, 4000.0) for name in JOINTS},
                send_guarded=send,
                enable_goals=lambda: setattr(self, "armed", True),
                arm_confirm=lambda: True, stop_requested=stop_requested,
                monotonic=self.clock.monotonic, sleep=self.clock.sleep,
                hold_policy="quantized")

        result = run_single_session_lifecycle(
            follower_bus=self.bus, atomic_writes=self.gate,
            guard=lambda: None, stop_requested=stop_requested,
            hold_audit=[], goals_enabled=lambda: self.armed,
            read_transition=self.diagnostics,
            read_transition_torque=lambda: dict(self.bus.torque),
            run_teaching=teaching,
            monotonic=self.clock.monotonic, sleep=self.clock.sleep)

        self.assertTrue(self.bus.is_connected)
        self.assertEqual(self.bus.connect_calls, 1)
        self.assertEqual(self.bus.disconnect_calls, [])
        self.assertEqual([packet[0] for packet in self.bus.atomic_packets],
                         ["Goal_Position", "Torque_Enable"])
        self.assertEqual(result["torque_on_write_attempts"], 1)
        self.assertEqual(result["torque_off_write_attempts"], 0)
        self.assertEqual(result["disconnects_between_stages"], 0)
        self.assertTrue(result["teaching"]["first_goal_skipped"])
        self.assertEqual(result["teaching"]["goal_sends"], 3)
        self.assertLessEqual(result["teaching"]["max_emitted_arm_step_deg"], 2.0)
        before = self.follower_action
        for command in self.sent:
            self.assertFalse(oversized_arm_steps(command, before))
            before = command

        manifest = self.trace.finish(stop_reason="teleoperation_inactive")
        self.assertTrue(manifest["data_complete"])
        self.assertFalse(self.ticket.exists())
        self.bus.disconnect(disable_torque=False)
        self.assertEqual(self.bus.disconnect_calls, [False])
        self.assertEqual(set(self.bus.torque.values()), {1})

    def test_default_cli_is_hardware_free(self):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main([]), 0)
        self.assertIn('"serial_open": 0', output.getvalue())
        self.assertEqual(self.bus.connect_calls, 1)


if __name__ == "__main__":
    unittest.main()
