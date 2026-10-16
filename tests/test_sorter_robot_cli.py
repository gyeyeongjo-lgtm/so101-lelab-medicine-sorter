import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from medicine_sorter.cli import main
from medicine_sorter.errors import SorterError
from medicine_sorter.models import TaskPlan
from medicine_sorter.robot import (LiveRobotAdapter, MockRobotAdapter, RobotController,
                                   RobotStatusSnapshot, SO101ReadOnlyStatusAdapter)


ROOT = Path(__file__).resolve().parents[1]


class SorterRobotCliTests(unittest.TestCase):
    def test_import_does_not_import_lerobot_or_open_device(self):
        self.assertNotIn("lerobot", sys.modules)
        adapter = LiveRobotAdapter({"live_ready": False})
        with self.assertRaises(SorterError) as caught:
            adapter.connect()
        self.assertEqual(caught.exception.code, "live_control_not_validated")
        self.assertNotIn("lerobot", sys.modules)

    def test_controller_rejects_mock_live_mode_mismatch(self):
        plan = TaskPlan("x", 4, ("approach",), "live", True)
        with self.assertRaises(SorterError) as caught:
            RobotController(MockRobotAdapter()).run(plan)
        self.assertEqual(caught.exception.code, "plan_adapter_mode_mismatch")

    def test_partial_connect_failure_is_closed_without_stop_write(self):
        class PartialConnectFailure(MockRobotAdapter):
            def connect(self):
                self.connected = True
                raise SorterError("connect_failed", "partial", "connected", "port를 확인해 주세요")

        adapter = PartialConnectFailure()
        plan = TaskPlan("x", 4, ("approach",), "recorded_mock", False)
        with self.assertRaises(SorterError) as caught:
            RobotController(adapter).run(plan)
        self.assertEqual(caught.exception.code, "connect_failed")
        self.assertTrue(adapter.closed)
        self.assertFalse(adapter.stopped)

    def invoke(self, args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(args)
        return code, json.loads(output.getvalue())

    def test_status_and_validate_are_hardware_free(self):
        for mode in ("status", "validate-config"):
            code, payload = self.invoke(["--config", str(ROOT / "configs/system.example.json"), mode])
            self.assertEqual(code, 0)
            self.assertEqual(payload["serial_open"], 0)
            self.assertEqual(payload["camera_open"], 0)
            self.assertEqual(payload["motor_write"], 0)
            self.assertFalse(payload["task_readiness"]["full_sort"]["ready"])
            self.assertTrue(payload["task_readiness"]["robot_status"]["ready"])

    def test_robot_status_cli_uses_status_only_adapter(self):
        class FakeStatusAdapter:
            def __init__(self):
                self.connected = False
                self.closed = False

            def connect(self):
                self.connected = True

            def read_status(self):
                self.assert_connected = self.connected
                values = {name: 0 for name in SO101ReadOnlyStatusAdapter.MOTOR_NAMES}
                return RobotStatusSnapshot("/dev/ttyACM1", "5AE6058306", values, values,
                                           values, values, values, 30, 0, False)

            def close(self):
                self.closed = True

        adapter = FakeStatusAdapter()
        code, payload = self.invoke_with_factory(
            ["--config", str(ROOT / "configs/system.example.json"), "robot-status"],
            lambda _config: adapter,
        )
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "ROBOT_STATUS_READ_ONLY")
        self.assertEqual(payload["state_change_writes"], 0)
        self.assertTrue(adapter.assert_connected)
        self.assertTrue(adapter.closed)

    def invoke_with_factory(self, args, factory):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(args, status_adapter_factory=factory)
        return code, json.loads(output.getvalue())

    def test_cli_mock_flow(self):
        code, payload = self.invoke([
            "--config", str(ROOT / "configs/system.example.json"), "mock-run",
            "--scene", str(ROOT / "configs/mock_scene.example.json"),
            "--command", "작은 약통 하나를 파란 바구니에 넣어",
        ])
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "MOCK_COMPLETED")
        self.assertFalse(payload["physical_motion"])
        self.assertEqual(payload["destination_marker_id"], 6)

    def test_live_fails_before_device_access_with_specific_missing_items(self):
        code, payload = self.invoke([
            "--config", str(ROOT / "configs/system.example.json"), "live",
            "--scene", str(ROOT / "configs/mock_scene.example.json"),
            "--command", "작은 약통을 파란 바구니에 넣어",
        ])
        self.assertEqual(code, 2)
        self.assertEqual(payload["error"], "live_configuration_incomplete")
        self.assertIn("table_to_robot_base", payload["observed"]["missing_or_unverified"])


class ReadOnlyStatusAdapterTests(unittest.TestCase):
    class FakeSerial:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    class FakeProbe:
        def __init__(self, serial="5AE6058306"):
            self.serial = serial
            self.bus = None

        def serial_short(self, _port):
            return self.serial

        def owner_pids(self, _port):
            if self.bus is not None and self.bus.connected:
                return {os.getpid()}
            return set()

    class FakeBus:
        def __init__(self, probe, *, fail_connect=False, fail_read=False):
            self.probe = probe
            self.probe.bus = self
            self.connected = False
            self.fail_connect = fail_connect
            self.fail_read = fail_read
            self.read_calls = []
            self.disconnect_calls = []
            self.port_handler = SimpleNamespace(ser=ReadOnlyStatusAdapterTests.FakeSerial())

        def connect(self, *, handshake):
            if handshake is not False:
                raise AssertionError("handshake must be false")
            self.connected = True
            if self.fail_connect:
                raise RuntimeError("partial connect failure")

        def disconnect(self, *, disable_torque):
            self.disconnect_calls.append(disable_torque)
            self.connected = False

        def read(self, register, motor, *, normalize, num_retry):
            self.read_calls.append((register, motor, normalize, num_retry))
            if self.fail_read:
                raise RuntimeError("communication failure")
            values = {"Goal_Position": 2001, "Present_Position": 2000,
                      "Torque_Enable": 1, "Moving": 0, "Present_Temperature": 37}
            return values[register]

        def write(self, *_args, **_kwargs):
            raise AssertionError("write must be firewalled")

        def sync_write(self, *_args, **_kwargs):
            raise AssertionError("sync_write must be firewalled")

        def enable_torque(self, *_args, **_kwargs):
            raise AssertionError("enable_torque must be firewalled")

        def disable_torque(self, *_args, **_kwargs):
            raise AssertionError("disable_torque must be firewalled")

    def make_adapter(self, probe, bus, directory):
        return SO101ReadOnlyStatusAdapter(
            port="/dev/ttyACM1", expected_serial="5AE6058306", probe=probe,
            bus_factory=lambda _port: bus, exclusive_seal=lambda _bus: None,
            lock_path=Path(directory) / "status.lock",
        )

    def test_wrong_identity_blocks_before_bus_creation(self):
        probe = self.FakeProbe(serial="leader")
        created = []
        with tempfile.TemporaryDirectory() as directory:
            adapter = SO101ReadOnlyStatusAdapter(
                port="/dev/ttyACM1", expected_serial="5AE6058306", probe=probe,
                bus_factory=lambda _port: created.append(True),
                exclusive_seal=lambda _bus: None,
                lock_path=Path(directory) / "status.lock",
            )
            with self.assertRaises(SorterError) as caught:
                RobotController(adapter).read_status()
        self.assertEqual(caught.exception.code, "wrong_follower_usb_identity")
        self.assertEqual(created, [])

    def test_status_reads_raw_registers_without_state_change(self):
        probe = self.FakeProbe()
        bus = self.FakeBus(probe)
        with tempfile.TemporaryDirectory() as directory:
            snapshot = RobotController(self.make_adapter(probe, bus, directory)).read_status()
        self.assertEqual(snapshot.read_requests, 30)
        self.assertEqual(snapshot.state_change_writes, 0)
        self.assertEqual(snapshot.goal_raw["elbow_flex"], 2001)
        self.assertEqual(snapshot.present_raw["elbow_flex"], 2000)
        self.assertTrue(all(call[2] is False and call[3] == 0 for call in bus.read_calls))
        self.assertEqual(bus.disconnect_calls, [False])
        self.assertTrue(bus.port_handler.ser.closed)

    def test_partial_connect_failure_releases_serial_and_lock(self):
        probe = self.FakeProbe()
        bus = self.FakeBus(probe, fail_connect=True)
        with tempfile.TemporaryDirectory() as directory:
            lock_path = Path(directory) / "status.lock"
            adapter = self.make_adapter(probe, bus, directory)
            with self.assertRaises(SorterError) as caught:
                RobotController(adapter).read_status()
            self.assertIsNone(adapter._lock_file)
            self.assertTrue(bus.port_handler.ser.closed)
        self.assertEqual(caught.exception.code, "robot_status_connect_failed")

    def test_read_failure_has_no_retry_and_closes_without_torque_change(self):
        probe = self.FakeProbe()
        bus = self.FakeBus(probe, fail_read=True)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(SorterError) as caught:
                RobotController(self.make_adapter(probe, bus, directory)).read_status()
        self.assertEqual(caught.exception.code, "robot_status_read_failed")
        self.assertEqual(len(bus.read_calls), 1)
        self.assertEqual(bus.read_calls[0][3], 0)
        self.assertEqual(bus.disconnect_calls, [False])
