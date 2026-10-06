import tempfile
import hashlib
import json
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import websocket

from scripts.observe_teleop_trace import (CameraEvidence, TraceAudit, cached_camera_worker,
                                         check_camera_source, record)
from scripts.teach_capture_web import CaptureState, JOINT_NAMES


def joint_message(source_unix, pitch=0.0):
    values = {name: 0.0 for name in JOINT_NAMES}
    values["Pitch"] = pitch
    return {"type": "joint_update", "timestamp": source_unix, "joints": values}


class TraceAuditTests(unittest.TestCase):
    def test_camera_evidence_writes_receive_time_and_hash_once(self):
        jpeg = b"\xff\xd8test\xff\xd9"

        def one_frame(state, name, _base_url, _stop):
            state.add_frame(name, jpeg, 1_000_000_000, 2_000_000_000)

        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            with patch("scripts.observe_teleop_trace.cached_camera_worker", side_effect=one_frame):
                evidence = CameraEvidence("http://localhost:8000", folder, ("ceiling",))
                evidence.start()
                evidence.threads[0].join(timeout=1)
                with patch("scripts.observe_teleop_trace.time.monotonic_ns", return_value=1_000_000_000):
                    evidence.sample()
                    evidence.state.add_frame("ceiling", jpeg, 1_100_000_000, 2_000_000_000)
                    evidence.sample()
                summary = evidence.finish()
            self.assertEqual(summary["ceiling"]["frame_count"], 1)
            index = json.loads((folder / "ceiling" / "frames.jsonl").read_text())
            self.assertEqual(index["sha256"], hashlib.sha256(jpeg).hexdigest())
            self.assertEqual((folder / "ceiling" / index["filename"]).read_bytes(), jpeg)

    def test_camera_source_must_be_fresh_loopback_and_read_only(self):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return None

            def read(self, *_):
                return json.dumps({"camera_age_ms": {"ceiling": 12.0},
                                   "errors": {"ceiling": None}, "robot_control": False}).encode()

        with patch("scripts.observe_teleop_trace.urllib.request.urlopen", return_value=Response()) as request:
            check_camera_source("http://127.0.0.1:8030", ("ceiling",))
            request.assert_called_once_with("http://127.0.0.1:8030/api/status", timeout=2)
        with self.assertRaisesRegex(ValueError, "loopback"):
            check_camera_source("http://192.168.50.20:8000", ("ceiling",))
        with patch("scripts.observe_teleop_trace.urllib.request.urlopen", return_value=Response()):
            with patch("scripts.observe_teleop_trace.MAX_FRAME_AGE_NS", 10_000_000):
                with self.assertRaisesRegex(RuntimeError, "not fresh"):
                    check_camera_source("http://127.0.0.1:8030", ("ceiling",))

    def test_cached_camera_worker_keeps_original_receive_timestamp(self):
        class Response:
            headers = {"X-Frame-Received-Unix-Ns": "2000000000"}

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return None

            def read(self, *_):
                return b"\xff\xd8frame\xff\xd9"

        state = CaptureState()
        stop = threading.Event()
        with patch("scripts.observe_teleop_trace.urllib.request.urlopen", return_value=Response()), \
             patch("scripts.observe_teleop_trace.time.time_ns", return_value=2_100_000_000):
            stop.wait = lambda _: stop.set()
            cached_camera_worker(state, "ceiling", "http://127.0.0.1:8030", stop)
        self.assertEqual(state.latest_frame("ceiling").received_unix_ns, 2_000_000_000)

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
        for forbidden in ("/move-arm", "/stop-teleoperation", "/joint-positions",
                          "/camera-preview", "serial.Serial"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
