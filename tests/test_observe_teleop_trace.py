import tempfile
import json
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import websocket

from scripts.observe_teleop_trace import TraceAudit, record
from scripts.teach_capture_web import JOINT_NAMES


def joint_message(source_unix, pitch=0.0):
    values = {name: 0.0 for name in JOINT_NAMES}
    values["Pitch"] = pitch
    return {"type": "joint_update", "timestamp": source_unix, "joints": values}


class TraceAuditTests(unittest.TestCase):
    def test_tracks_gaps_steps_and_source_time_duplicates(self):
        audit = TraceAudit()
        self.assertIsNone(audit.add({"type": "other"}, 1_000_000_000, 5_000_000_000))
        first = audit.add(joint_message(10.0, 0.1), 1_000_000_000, 5_000_000_000)
        second = audit.add(joint_message(10.0, 0.3), 1_050_000_000, 5_050_000_000)
        self.assertEqual(first["joints_rad"]["Pitch"], 0.1)
        self.assertEqual(second["source_unix"], 10.0)
        self.assertEqual(audit.summary()["sample_count"], 2)
        self.assertEqual(audit.summary()["max_receive_gap_ms"], 50.0)
        self.assertAlmostEqual(audit.summary()["max_consecutive_step_rad"]["Pitch"], 0.2)
        self.assertEqual(audit.summary()["duplicate_or_reverse_source_times"], 1)

    def test_inactive_teleop_creates_no_trace_folder(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "trace"
            with patch("scripts.observe_teleop_trace.teleop_active", return_value=False):
                with self.assertRaisesRegex(RuntimeError, "inactive"):
                    record("http://localhost:8000", root, 1)
            self.assertFalse(root.exists())

    def test_active_trace_stops_when_teleop_ends_and_is_never_replay_authorized(self):
        class FakeSocket:
            def __init__(self):
                self.calls = 0
                self.closed = False

            def settimeout(self, value):
                self.timeout = value

            def recv(self):
                self.calls += 1
                if self.calls == 1:
                    return json.dumps(joint_message(10.0, 0.2))
                time.sleep(0.55)
                raise websocket.WebSocketTimeoutException()

            def close(self):
                self.closed = True

        fake = FakeSocket()
        with tempfile.TemporaryDirectory() as temporary:
            with patch("scripts.observe_teleop_trace.teleop_active", side_effect=[True, True, False]), \
                 patch("websocket.create_connection", return_value=fake):
                result = record("http://localhost:8000", Path(temporary), 5)
            manifest = json.loads((Path(result["folder"]) / "manifest.json").read_text())
            self.assertEqual(manifest["stop_reason"], "teleoperation_inactive")
            self.assertEqual(manifest["sample_count"], 1)
            self.assertFalse(manifest["use_for_replay"])
            self.assertFalse(manifest["robot_enabled"])
            self.assertFalse(manifest["motion_authorized"])
            self.assertTrue(fake.closed)

    def test_source_has_no_control_routes(self):
        source = (Path(__file__).resolve().parents[1] / "scripts" / "observe_teleop_trace.py").read_text()
        for forbidden in ("/move-arm", "/stop-teleoperation", "/joint-positions", "serial.Serial"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
