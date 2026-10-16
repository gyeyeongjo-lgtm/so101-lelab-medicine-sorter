import contextlib
import io
from pathlib import Path
import tempfile
import unittest

from scripts.atomic_hold_restore import (
    AXES, OneShotRawWrites, main, run_exclusive_session,
)
from scripts.so101_exclusive_bus import ExclusiveFollowerLease


class Clock:
    def __init__(self):
        self.now = 0.0
        self.on_sleep = lambda: None

    def monotonic(self):
        return self.now

    def sleep(self, duration):
        self.now += duration
        self.on_sleep()


class Probe:
    def __init__(self):
        self.idle = True
        self.serial = "5AE6058306"
        self.pids = set()

    def lelab_controls_idle(self):
        return self.idle

    def serial_short(self, _port):
        return self.serial

    def owner_pids(self, _port):
        return self.pids


class FakeBus:
    def __init__(self, probe):
        self.probe = probe
        self.present = dict(zip(AXES, (2066, 1098, 2901, 2503, 1612, 490)))
        self.goal = dict.fromkeys(AXES, 0)
        self.torque = dict.fromkeys(AXES, 0)
        self.moving = dict.fromkeys(AXES, 0)
        self.temperature = dict.fromkeys(AXES, 37)
        self.is_connected = False
        self.connect_calls = self.disconnect_calls = self.seal_calls = 0
        self.writes = []
        self.on_write = lambda _register: None
        self.on_read = lambda _register: None
        self.on_connect = lambda: None

    def connect(self, *, handshake):
        assert handshake is False
        self.connect_calls += 1
        self.is_connected = True
        self.probe.pids = {4321}
        self.on_connect()

    def disconnect(self, *, disable_torque):
        assert disable_torque is False
        self.disconnect_calls += 1
        self.probe.pids = set()
        self.is_connected = False

    def sync_read(self, register, *, normalize, num_retry):
        assert normalize is False and num_retry == 0
        assert self.is_connected
        self.on_read(register)
        return dict({"Present_Position": self.present, "Goal_Position": self.goal,
                     "Torque_Enable": self.torque, "Moving": self.moving}[register])

    def read(self, register, axis, *, normalize, num_retry):
        assert register == "Present_Temperature" and normalize is False and num_retry == 0
        return self.temperature[axis]

    def sync_write(self, register, values, *, normalize, num_retry):
        assert self.is_connected and self.seal_calls == 1
        assert normalize is False and num_retry == 0
        assert set(values) == set(AXES)
        self.writes.append((register, dict(values)))
        if register == "Goal_Position":
            assert set(self.torque.values()) == {0}
            self.goal = dict(values)
        elif register == "Torque_Enable":
            assert self.goal == self.present
            assert set(values.values()) == {1}
            self.torque = dict(values)
        else:
            raise AssertionError("config write")
        self.on_write(register)

    def write(self, *_args, **_kwargs):
        raise AssertionError("individual write forbidden")

    def enable_torque(self, *_args, **_kwargs):
        raise AssertionError("implicit torque API forbidden")

    disable_torque = write
    write_calibration = write
    configure_motors = write

    def _unnormalize(self, *_args, **_kwargs):
        raise AssertionError("raw must not be recalculated")


class AtomicHoldRestoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.probe = Probe()
        self.lease = ExclusiveFollowerLease(
            self.probe, port=Path("/fake/follower"),
            lock_path=Path(self.tmp.name) / "exclusive.lock", own_pid=4321)
        self.bus = FakeBus(self.probe)
        self.clock = Clock()
        self.audit = []
        self.stop = False

    def tearDown(self):
        self.lease.release()
        self.tmp.cleanup()

    def run_restore(self):
        def seal(bus):
            bus.seal_calls += 1
        return run_exclusive_session(
            lease=self.lease, bus_factory=lambda: self.bus, seal=seal,
            stop_requested=lambda: self.stop, audit=self.audit,
            monotonic=self.clock.monotonic, sleep=self.clock.sleep)

    def assert_aborted(self, text, writes):
        with self.assertRaisesRegex((RuntimeError, OSError), text):
            self.run_restore()
        self.assertEqual(len(self.bus.writes), writes)
        self.assertFalse(self.lease.connected)
        self.assertFalse(self.bus.is_connected)
        self.assertIsNone(self.lease._lock_file)

    def test_same_raw_once_then_torque_once_single_session_three_seconds(self):
        intended = dict(self.bus.present)
        result = self.run_restore()
        self.assertEqual(result["status"], "HOLD_RESTORED")
        self.assertEqual(self.bus.writes, [
            ("Goal_Position", intended), ("Torque_Enable", dict.fromkeys(AXES, 1))])
        self.assertGreaterEqual(result["stability_seconds"], 3.0)
        self.assertGreaterEqual(result["stability_samples"], 31)
        self.assertEqual(self.bus.connect_calls, 1)
        self.assertEqual(self.bus.seal_calls, 1)
        self.assertEqual(self.bus.disconnect_calls, 1)
        self.assertEqual(self.bus.goal["gripper"], intended["gripper"])
        self.assertEqual(result["config_writes"], 0)

    def test_preexisting_partial_torque_on_no_write(self):
        self.bus.torque["gripper"] = 1
        self.assert_aborted("unexpected_torque", 0)

    def test_three_seconds_is_sample_span_not_slow_post_read_probe(self):
        original_guard = self.lease.ensure_exclusive
        delayed = False
        def guard():
            nonlocal delayed
            original_guard()
            if (not delayed and self.audit and
                    self.audit[-1]["phase"] == "POST_ENABLE_STABILITY"):
                self.clock.now += 4.0
                delayed = True
        self.lease.ensure_exclusive = guard
        result = self.run_restore()
        observed = [row["monotonic"] for row in self.audit
                    if row["phase"] in ("IMMEDIATE_AFTER_ENABLE", "POST_ENABLE_STABILITY")]
        self.assertGreaterEqual(observed[-1] - observed[0], 3.0)
        self.assertEqual(result["stability_seconds"], observed[-1] - observed[0])

    def test_preexisting_all_torque_on_no_write(self):
        self.bus.torque = dict.fromkeys(AXES, 1)
        self.assert_aborted("unexpected_torque", 0)

    def test_moving_no_write(self):
        self.bus.moving["elbow_flex"] = 1
        self.assert_aborted("unexpected_moving", 0)

    def test_temperature_fault_no_write(self):
        self.bus.temperature["elbow_flex"] = 56
        self.assert_aborted("temperature_fault", 0)

    def test_invalid_raw_no_write(self):
        self.bus.present["gripper"] = 0
        self.assert_aborted("present_raw_outside", 0)

    def test_noninteger_raw_no_write(self):
        self.bus.present["gripper"] = 490.5
        self.assert_aborted("invalid_raw_register", 0)

    def test_pre_sync_goal_change_no_write(self):
        reads = 0
        def mutate(register):
            nonlocal reads
            if register == "Goal_Position":
                reads += 1
                if reads == 2:
                    self.bus.goal["gripper"] = 1
        self.bus.on_read = mutate
        self.assert_aborted("unexpected_goal_change", 0)

    def test_readback_mismatch_no_enable(self):
        self.bus.on_write = lambda _reg: self.bus.goal.update(gripper=999)
        self.assert_aborted("unexpected_goal_change", 1)

    def test_torque_changed_while_syncing_no_enable(self):
        self.bus.on_write = lambda _reg: self.bus.torque.update(gripper=1)
        self.assert_aborted("unexpected_torque", 1)

    def test_present_drift_while_syncing_no_enable(self):
        self.bus.on_write = lambda _reg: self.bus.present.update(gripper=491)
        self.assert_aborted("unexpected_present_drift", 1)

    def test_goal_write_communication_error_no_retry(self):
        def fail(_register):
            raise OSError("ambiguous_goal_write")
        self.bus.on_write = fail
        self.assert_aborted("ambiguous_goal_write", 1)
        self.assertEqual(self.audit[-1]["write_attempts"]["Goal_Position"], 1)

    def test_torque_write_communication_error_no_retry_or_rollback(self):
        def fail(register):
            if register == "Torque_Enable":
                raise OSError("ambiguous_torque_write")
        self.bus.on_write = fail
        self.assert_aborted("ambiguous_torque_write", 2)
        self.assertEqual(self.audit[-1]["write_attempts"]["Torque_Enable"], 1)

    def test_partial_enable_no_automatic_disable(self):
        def partial(register):
            if register == "Torque_Enable":
                self.bus.torque["elbow_flex"] = 0
        self.bus.on_write = partial
        self.assert_aborted("unexpected_torque", 2)

    def test_immediate_motion_no_further_write(self):
        def move(register):
            if register == "Torque_Enable":
                self.bus.moving["elbow_flex"] = 1
        self.bus.on_write = move
        self.assert_aborted("unexpected_moving", 2)

    def test_drift_during_three_seconds_no_further_write(self):
        self.clock.on_sleep = lambda: self.bus.present.update(gripper=491)
        self.assert_aborted("unexpected_present_drift", 2)

    def test_goal_mutation_during_three_seconds_no_further_write(self):
        self.clock.on_sleep = lambda: self.bus.goal.update(gripper=491)
        self.assert_aborted("unexpected_goal_change", 2)

    def test_torque_drop_during_three_seconds_no_further_write(self):
        self.clock.on_sleep = lambda: self.bus.torque.update(gripper=0)
        self.assert_aborted("unexpected_torque", 2)

    def test_read_error_after_enable_no_further_write(self):
        def fail(register):
            if self.bus.torque["gripper"] == 1:
                raise OSError("read_failure")
        self.bus.on_read = fail
        self.assert_aborted("read_failure", 2)

    def test_stop_before_sync_no_write(self):
        self.stop = True
        self.assert_aborted("stop_requested", 0)

    def test_stop_after_sync_no_enable(self):
        def stop(_register):
            self.stop = True
        self.bus.on_write = stop
        self.assert_aborted("stop_requested", 1)

    def test_stop_after_enable_no_further_write(self):
        def stop():
            self.stop = True
        self.clock.on_sleep = stop
        self.assert_aborted("stop_requested", 2)

    def test_active_lelab_no_connect(self):
        self.probe.idle = False
        self.assert_aborted("lelab_motor_control_not_idle", 0)
        self.assertEqual(self.bus.connect_calls, 0)

    def test_wrong_usb_no_connect(self):
        self.probe.serial = "wrong_device"
        self.assert_aborted("wrong_follower_usb", 0)
        self.assertEqual(self.bus.connect_calls, 0)

    def test_existing_port_owner_no_connect(self):
        self.probe.pids = {9876}
        self.assert_aborted("port_busy", 0)
        self.assertEqual(self.bus.connect_calls, 0)

    def test_competing_lease_cannot_acquire_same_session_lock(self):
        rival = ExclusiveFollowerLease(
            self.probe, port=self.lease.port, lock_path=self.lease.lock_path,
            own_pid=9876)
        rival.acquire()
        try:
            self.assert_aborted("", 0)
            self.assertEqual(self.bus.connect_calls, 0)
        finally:
            rival.release()

    def test_competing_controller_mid_session_no_extra_write(self):
        self.bus.on_write = lambda _reg: self.probe.pids.add(9876)
        self.assert_aborted("not_exclusive", 1)

    def test_active_lelab_mid_session_no_extra_write(self):
        def started(_register):
            self.probe.idle = False
        self.bus.on_write = started
        self.assert_aborted("started_during_program", 1)

    def test_connect_write_blocked_before_it_can_reach_bus(self):
        self.bus.on_connect = lambda: self.bus.sync_write(
            "Torque_Enable", dict.fromkeys(AXES, 1), normalize=False, num_retry=0)
        self.assert_aborted("forbidden_sync_write", 0)

    def test_firewall_rejects_config_individual_torque_and_unsolicited_goal(self):
        gate = OneShotRawWrites(self.bus)
        for name in ("write", "enable_torque", "disable_torque",
                     "write_calibration", "configure_motors"):
            with self.assertRaisesRegex(RuntimeError, "forbidden_write"):
                getattr(self.bus, name)()
        with self.assertRaisesRegex(RuntimeError, "forbidden_sync_write"):
            self.bus.sync_write("Goal_Position", self.bus.present, normalize=False, num_retry=0)
        gate.stop()
        with self.assertRaisesRegex(RuntimeError, "already_attempted_or_stopped"):
            gate.send("Goal_Position", self.bus.present)
        self.assertEqual(self.bus.writes, [])

    def test_handoff_requires_complete_restore_and_releases_only_sync_write(self):
        gate = OneShotRawWrites(self.bus)
        with self.assertRaisesRegex(RuntimeError, "handoff_before_complete"):
            gate.handoff_to_teaching()
        gate.stop()
        gate.attempts = {"Goal_Position": 1, "Torque_Enable": 1}
        gate.handoff_to_teaching()
        self.assertIs(self.bus.sync_write, gate._original_sync_write)
        for name in ("write", "enable_torque", "disable_torque",
                     "write_calibration", "configure_motors"):
            with self.assertRaisesRegex(RuntimeError, "forbidden_write"):
                getattr(self.bus, name)()

    def test_default_cli_does_not_import_hardware_or_open_port(self):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main([]), 0)
        self.assertIn('"serial_open": 0', output.getvalue())
        self.assertEqual(self.bus.connect_calls, 0)


if __name__ == "__main__":
    unittest.main()
