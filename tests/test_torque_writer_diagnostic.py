import contextlib
import io
from pathlib import Path
import tempfile
import unittest

from scripts.torque_writer_diagnostic import (
    WriteAttemptBlocked, WriteAttemptFirewall, main,
)


class Motor:
    def __init__(self, motor_id):
        self.id = motor_id


class PortHandler:
    def __init__(self):
        self.raw_writes = []

    def writePort(self, data):
        self.raw_writes.append(bytes(data))


class Bus:
    def __init__(self):
        self.motors = {f"motor_{index}": Motor(index) for index in range(1, 7)}
        self.port_handler = PortHandler()
        self.real_writes = []

    def write(self, register, motor, value, **kwargs):
        self.real_writes.append((register, motor, value, kwargs))

    def sync_write(self, register, values, **kwargs):
        self.real_writes.append((register, values, kwargs))

    def enable_torque(self, motors=None, **kwargs):
        self.real_writes.append(("enable", motors, kwargs))

    def disable_torque(self, motors=None, **kwargs):
        self.real_writes.append(("disable", motors, kwargs))

    def configure_motors(self):
        self.real_writes.append(("configure",))

    def write_calibration(self, calibration):
        self.real_writes.append(("calibration", calibration))

    def _write(self, addr, length, motor_id, value, **kwargs):
        self.real_writes.append((addr, length, motor_id, value, kwargs))

    def _sync_write(self, addr, length, ids_values, **kwargs):
        self.real_writes.append((addr, length, ids_values, kwargs))


class TorqueWriterDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.bus = Bus()
        self.tick = 100
        self.firewall = WriteAttemptFirewall(
            self.bus, wall_time_ns=lambda: self.tick)

    def test_blocks_and_logs_named_torque_and_goal_writes(self):
        attempts = (
            lambda: self.bus.enable_torque(),
            lambda: self.bus.disable_torque(["motor_3"]),
            lambda: self.bus.write("Torque_Enable", "motor_2", 1),
            lambda: self.bus.sync_write(
                "Goal_Position", {name: 100 + index
                                  for index, name in enumerate(self.bus.motors)}),
        )
        for operation in attempts:
            with self.assertRaises(WriteAttemptBlocked):
                operation()
        self.assertEqual(self.bus.real_writes, [])
        self.assertEqual([row["register_name"] for row in self.firewall.attempts],
                         ["Torque_Enable", "Torque_Enable",
                          "Torque_Enable", "Goal_Position"])
        for row in self.firewall.attempts:
            self.assertEqual(row["event"], "WRITE_ATTEMPTED_BLOCKED")
            self.assertEqual(row["timestamp_unix_ns"], 100)
            self.assertTrue(row["motor_ids"])
            self.assertTrue(any("test_blocks_and_logs" in line
                                for line in row["python_call_stack"]))

    def test_blocks_low_level_and_raw_serial_bypasses(self):
        for operation in (
            lambda: self.bus._write(40, 1, 2, 1),
            lambda: self.bus._sync_write(42, 2, {1: 2048, 2: 2048}),
            lambda: self.bus.port_handler.writePort(b"\xff\xff\x01"),
        ):
            with self.assertRaises(WriteAttemptBlocked):
                operation()
        self.assertEqual(self.bus.real_writes, [])
        self.assertEqual(self.bus.port_handler.raw_writes, [])
        self.assertEqual([row["layer"] for row in self.firewall.attempts],
                         ["bus._write", "bus._sync_write", "port_handler.writePort"])

    def test_blocks_configuration_and_persists_audit(self):
        for operation in (
            self.bus.configure_motors,
            lambda: self.bus.write_calibration({"motor_1": {}}),
        ):
            with self.assertRaises(WriteAttemptBlocked):
                operation()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "audit.json"
            self.firewall.write_json(path)
            self.assertIn("WRITE_ATTEMPTED_BLOCKED", path.read_text())

    def test_restore_returns_original_methods(self):
        self.firewall.restore()
        self.bus.write("Torque_Enable", "motor_1", 1)
        self.assertEqual(len(self.bus.real_writes), 1)

    def test_default_cli_is_hardware_free(self):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main([]), 0)
        self.assertIn('"serial_open": 0', output.getvalue())


if __name__ == "__main__":
    unittest.main()
