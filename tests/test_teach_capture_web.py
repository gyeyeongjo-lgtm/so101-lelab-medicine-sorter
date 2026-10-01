import json
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

from scripts.teach_capture_web import (
    CaptureServer,
    CaptureState,
    JOINT_NAMES,
    iter_jpegs,
    save_capture,
)


def ready_state():
    state = CaptureState()
    now = time.monotonic_ns()
    for index in range(15):
        values = {name: 0.1 * position for position, name in enumerate(JOINT_NAMES)}
        state.add_joint(
            {"type": "joint_update", "timestamp": 1000.0 + index * 0.05, "joints": values},
            received_ns=now - (14 - index) * 50_000_000 - 30_000_000,
            received_unix_ns=2_000_000_000 + index * 50_000_000,
        )
    for name in ("ceiling", "oblique"):
        state.add_frame(name, b"\xff\xd8test-" + name.encode() + b"\xff\xd9",
                        received_ns=now - 40_000_000, received_unix_ns=2_700_000_000)
    return state, now


class TeachCaptureTests(unittest.TestCase):
    def test_mjpeg_parser_handles_split_frames(self):
        frames = list(iter_jpegs([b"noise\xff\xd8one\xff", b"\xd9--\xff\xd8two\xff\xd9"]))
        self.assertEqual(frames, [b"\xff\xd8one\xff\xd9", b"\xff\xd8two\xff\xd9"])
        self.assertEqual(list(iter_jpegs([b"boundary\xff", b"\xd8three\xff\xd9"])),
                         [b"\xff\xd8three\xff\xd9"])

    def test_capture_selects_stable_joint_window_and_both_frames(self):
        state, now = ready_state()
        result = state.select("P6", now_ns=now)
        self.assertEqual(len(result["joints"]), 15)
        self.assertEqual(set(result["frames"]), {"ceiling", "oblique"})
        self.assertLessEqual(max(result["frame_joint_receive_gap_ms"].values()), 250)
        with tempfile.TemporaryDirectory() as temporary:
            saved = save_capture(Path(temporary), result)
            folder = Path(saved["folder"])
            metadata = json.loads((folder / "metadata.json").read_text())
            self.assertEqual(metadata["point"], "P6")
            self.assertFalse(metadata["robot_enabled"])
            self.assertFalse(metadata["motion_authorized"])
            self.assertFalse(metadata["use_for_robot_world_fit"])
            self.assertEqual(len(metadata["joint_samples"]), 15)
            self.assertTrue((folder / "ceiling.jpg").is_file())
            self.assertTrue((folder / "oblique.jpg").is_file())
            self.assertFalse((folder / "wrist.jpg").exists())
            self.assertEqual(metadata["optional_camera_omitted"], ["wrist"])

    def test_fresh_wrist_frame_is_saved_without_becoming_required(self):
        state, now = ready_state()
        state.add_frame("wrist", b"\xff\xd8wrist\xff\xd9", received_ns=now - 50_000_000,
                        received_unix_ns=2_690_000_000)
        selected = state.select("P1", now_ns=now)
        self.assertEqual(set(selected["frames"]), {"ceiling", "oblique", "wrist"})
        self.assertEqual(selected["optional_camera_omitted"], [])
        with tempfile.TemporaryDirectory() as temporary:
            saved = save_capture(Path(temporary), selected)
            folder = Path(saved["folder"])
            self.assertTrue((folder / "wrist.jpg").is_file())
            self.assertIn("wrist", json.loads((folder / "metadata.json").read_text())["images"])

    def test_stale_wrist_frame_is_omitted_without_blocking_capture(self):
        state, now = ready_state()
        state.add_frame("wrist", b"\xff\xd8wrist\xff\xd9", received_ns=now - 1_000_000_000)
        selected = state.select("P1", now_ns=now)
        self.assertEqual(set(selected["frames"]), {"ceiling", "oblique"})
        self.assertEqual(selected["optional_camera_omitted"], ["wrist"])

    def test_rejects_stale_or_moving_data(self):
        state, now = ready_state()
        with self.assertRaisesRegex(ValueError, "point must"):
            state.select(["P6"], now_ns=now)
        with self.assertRaisesRegex(ValueError, "fresh joint"):
            state.select("P6", now_ns=now + 600_000_000)
        state, now = ready_state()
        with state.lock:
            last = state.joints[-1]
            state.joints[-1] = type(last)({**last.joints, "Pitch": 1.0}, last.source_unix,
                                         last.received_ns, last.received_unix_ns)
        with self.assertRaisesRegex(ValueError, "not stable"):
            state.select("P6", now_ns=now)

    def test_http_capture_refuses_inactive_teleoperation(self):
        state, _ = ready_state()
        with tempfile.TemporaryDirectory() as temporary:
            server = CaptureServer(("127.0.0.1", 0), state, Path(temporary), "http://invalid.local")
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                url = f"http://127.0.0.1:{server.server_port}/api/capture"
                payload = json.dumps({"point": "P6", "contact_confirmed": True}).encode()
                request = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
                with patch("scripts.teach_capture_web.lelab_teleop_active", return_value=False):
                    with self.assertRaises(urllib.error.HTTPError) as error:
                        urllib.request.urlopen(request, timeout=2)
                self.assertEqual(error.exception.code, 400)
                self.assertEqual(list(Path(temporary).iterdir()), [])
                server.state, _ = ready_state()
                with patch("scripts.teach_capture_web.lelab_teleop_active", return_value=True):
                    with urllib.request.urlopen(request, timeout=2) as response:
                        saved = json.load(response)
                self.assertEqual(saved["point"], "P6")
                self.assertTrue((Path(saved["folder"]) / "metadata.json").is_file())
            finally:
                server.shutdown()
                server.server_close()
                worker.join(timeout=2)

    def test_source_has_no_robot_control_routes(self):
        source = (Path(__file__).resolve().parents[1] / "scripts" / "teach_capture_web.py").read_text()
        for forbidden in ("/move-arm", "/stop-teleoperation", "/joint-positions", "serial.Serial"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
