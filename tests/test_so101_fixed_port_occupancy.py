import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import so101_fixed_port_occupancy as helper
from scripts.so101_exclusive_bus import PreflightError, SystemBusProbe


class Completed:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class FixedPortOccupancyTests(unittest.TestCase):
    def test_helper_rejects_every_argument(self):
        error = io.StringIO()
        with patch("sys.stderr", error):
            self.assertEqual(helper.main(["helper", "/dev/ttyACM0"]), 64)
        self.assertIn("no arguments", error.getvalue())

    def test_helper_has_only_two_fixed_ports(self):
        self.assertEqual(helper.PORTS,
                         (Path("/dev/ttyACM0"), Path("/dev/ttyACM1")))

    def test_probe_parses_free_and_occupied_without_device_open(self):
        output = ("/dev/ttyACM0\tFREE\t-\t-\n"
                  "/dev/ttyACM1\tOCCUPIED\t4321\tpython\n")
        probe = SystemBusProbe()
        with patch("scripts.so101_exclusive_bus.FIXED_PORT_OCCUPANCY_HELPER") as path, \
             patch.object(Path, "exists", return_value=True), \
             patch.object(probe, "_run", return_value=Completed(stdout=output)) as run:
            path.is_file.return_value = True
            path.__str__.return_value = "/usr/local/sbin/so101-fixed-port-occupancy"
            self.assertEqual(probe.owner_pids(Path("/dev/ttyACM0")), set())
            self.assertEqual(probe.owner_pids(Path("/dev/ttyACM1")), {4321})
            self.assertEqual(run.call_args.args[0][0:2], ["sudo", "-n"])

    def test_probe_rejects_unlisted_port_before_running_lookup(self):
        probe = SystemBusProbe()
        with patch.object(Path, "exists", return_value=True), \
             patch.object(probe, "_run") as run:
            with self.assertRaisesRegex(PreflightError, "outside_fixed_scope"):
                probe.owner_pids(Path("/dev/ttyUSB0"))
            run.assert_not_called()

    def test_probe_fails_closed_on_incomplete_or_extra_path_output(self):
        probe = SystemBusProbe()
        for output in (
            "/dev/ttyACM0\tFREE\t-\t-\n",
            "/dev/ttyACM0\tFREE\t-\t-\n/dev/ttyACM1\tFREE\t-\t-\n"
            "/dev/ttyUSB0\tFREE\t-\t-\n",
        ):
            with self.subTest(output=output), \
                 patch("scripts.so101_exclusive_bus.FIXED_PORT_OCCUPANCY_HELPER") as path, \
                 patch.object(Path, "exists", return_value=True), \
                 patch.object(probe, "_run", return_value=Completed(stdout=output)):
                path.is_file.return_value = True
                with self.assertRaisesRegex(PreflightError, "port_ownership_unknown"):
                    probe.owner_pids(Path("/dev/ttyACM0"))

    def test_probe_maps_helper_query_error_to_unknown_not_free(self):
        probe = SystemBusProbe()
        with patch("scripts.so101_exclusive_bus.FIXED_PORT_OCCUPANCY_HELPER") as path, \
             patch.object(Path, "exists", return_value=True), \
             patch.object(probe, "_run", return_value=Completed(
                 returncode=1, stderr="query failed")):
            path.is_file.return_value = True
            with self.assertRaisesRegex(PreflightError, "port_ownership_unknown"):
                probe.owner_pids(Path("/dev/ttyACM0"))


if __name__ == "__main__":
    unittest.main()
