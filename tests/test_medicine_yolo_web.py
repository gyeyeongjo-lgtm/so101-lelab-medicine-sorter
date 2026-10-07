import sys
import json
import io
import tempfile
import threading
import time
import unittest
from collections import deque
from email.message import Message
from http import HTTPStatus
from pathlib import Path
from types import SimpleNamespace


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from medicine_yolo_web import (
    DetectionWorker, Handler, INDEX_HTML, detect_table_markers, inside_roi, is_http_jpeg, is_http_stream,
    mjpeg_jpegs, project_table_xy, read_exact, video_index,
)
from medicine_fixed_slot_command import DEFAULT_SLOTS, validate_slots
from medicine_sort_dry_run import DEFAULT_RULES, validate_rules

import numpy as np


class MedicineYoloWebTests(unittest.TestCase):
    def test_page_is_read_only(self):
        self.assertIn("ROBOT DISABLED", INDEX_HTML)
        self.assertIn("/stream.mjpg", INDEX_HTML)
        self.assertIn("/angled.mjpg", INDEX_HTML)
        self.assertNotIn("move-arm", INDEX_HTML)
        self.assertNotIn("start-inference", INDEX_HTML)
        self.assertNotIn("stop-teleoperation", INDEX_HTML)
        self.assertIn("/manual-frame.json", INDEX_HTML)
        self.assertIn("motion_authorized:false", INDEX_HTML)
        self.assertIn("pickup_roi_match:roiMatch", INDEX_HTML)
        self.assertIn("사진·라벨 로컬 저장", INDEX_HTML)
        self.assertIn("/api/command-preview", INDEX_HTML)
        self.assertIn("명령 판정만", INDEX_HTML)
        self.assertIn("document.querySelector('#route-command').value=''", INDEX_HTML)
        self.assertIn("window.addEventListener('pageshow'", INDEX_HTML)
        self.assertIn("out.textContent+='\\n다시 프레임", INDEX_HTML)
        self.assertNotIn("out.textContent+='\n다시 프레임", INDEX_HTML)

    def test_read_exact_combines_short_reads(self):
        class ShortStream:
            def __init__(self):
                self.parts = [b"ab", b"c", b"def"]

            def read(self, _size):
                return self.parts.pop(0) if self.parts else b""

        self.assertEqual(read_exact(ShortStream(), 6), b"abcdef")

    def test_read_exact_returns_empty_on_partial_eof(self):
        class PartialStream:
            def __init__(self):
                self.done = False

            def read(self, _size):
                if self.done:
                    return b""
                self.done = True
                return b"abc"

        self.assertEqual(read_exact(PartialStream(), 6), b"")

    def test_mjpeg_stream_keeps_last_complete_frame_and_partial_tail(self):
        class SplitStream:
            parts = [b"--\xff", b"\xd8A\xff\xd9--\xff\xd8B\xff\xd9--\xff\xd8C", b"\xff\xd9"]

            def read(self, _size):
                return self.parts.pop(0) if self.parts else b""

        self.assertEqual(
            list(mjpeg_jpegs(SplitStream(), threading.Event())),
            [b"\xff\xd8B\xff\xd9", b"\xff\xd8C\xff\xd9"],
        )

    def test_stale_detection_frame_is_not_healthy(self):
        worker = DetectionWorker.__new__(DetectionWorker)
        worker.lock = threading.Lock()
        worker.jpeg = b"jpeg"
        worker.error = None
        worker.updated_monotonic = time.monotonic() - 6
        worker.raw_rgb_command = None
        worker.device = "http://127.0.0.1:8000/camera-preview/8"
        worker.model = "model.onnx"
        worker.sequence = 2
        worker.inference_ms = 250.8
        worker.detections = []
        worker.table_status = None
        snapshot = worker.snapshot()
        self.assertFalse(snapshot["ok"])
        self.assertGreater(snapshot["frame_age_s"], 5)

    def test_manual_frame_keeps_jpeg_and_detection_sequence_together(self):
        worker = DetectionWorker.__new__(DetectionWorker)
        worker.lock = threading.Lock()
        worker.jpeg = b"jpeg-42"
        worker.error = None
        worker.updated_monotonic = time.monotonic()
        worker.sequence = 42
        worker.detections = [{"xyxy": [1, 2, 3, 4]}]
        worker.table_status = {"ready": True}
        snapshot, jpeg = worker.snapshot_with_jpeg()
        self.assertEqual((snapshot["sequence"], jpeg), (42, b"jpeg-42"))
        self.assertEqual(snapshot["detections"], worker.detections)
        self.assertFalse(snapshot["robot_enabled"])

    def test_manual_capture_saves_exact_raw_frame_once_for_review(self):
        worker = DetectionWorker.__new__(DetectionWorker)
        worker.lock = threading.Lock()
        worker.device = "http://127.0.0.1:8030/frame/ceiling.jpg"
        worker.saved_sequences = set()
        worker.frame_history = deque([{
            "sequence": 42,
            "monotonic": time.monotonic(),
            "raw_jpeg": b"\xff\xd8raw\xff\xd9",
            "image_size_px": [640, 480],
            "detections": [{"xyxy": [10, 10, 30, 30], "confidence": 0.9,
                            "inside_pickup_roi": False}],
            "table": {"ready": True, "required_ids": [0, 1, 2, 3],
                      "detected_ids": [0, 1, 2, 3, 4, 5, 6],
                      "basket_mapping": {"4": "red", "5": "green", "6": "blue"},
                      "basket_markers": {"4": {"color": "red"}, "5": {"color": "green"},
                                         "6": {"color": "blue"}}},
        }])
        rules = validate_rules(json.loads(DEFAULT_RULES.read_text(encoding="utf-8")))
        with tempfile.TemporaryDirectory() as temporary:
            result = worker.save_manual_capture(Path(temporary), rules, label="C",
                                                sequence=42, pixel=(20, 20))
            folder = Path(result["folder"])
            self.assertEqual((folder / "ceiling.jpg").read_bytes(), b"\xff\xd8raw\xff\xd9")
            metadata = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["human_verified_label"], "C")
            self.assertEqual(metadata["decision"]["target_marker_id"], 4)
            self.assertFalse(metadata["training_ready"])
            with self.assertRaisesRegex(ValueError, "already saved"):
                worker.save_manual_capture(Path(temporary), rules, label="C",
                                           sequence=42, pixel=(20, 20))

    def test_command_preview_endpoint_is_dry_run_only(self):
        body = json.dumps({"command": "A를 빨간색"}, ensure_ascii=False).encode()
        headers = Message()
        headers["Content-Type"] = "application/json"
        headers["Content-Length"] = str(len(body))
        handler = Handler.__new__(Handler)
        handler.path = "/api/command-preview"
        handler.headers = headers
        handler.rfile = io.BytesIO(body)
        handler.server = SimpleNamespace(
            worker=SimpleNamespace(snapshot=lambda: {
                "ok": True, "robot_enabled": False, "frame_age_s": 0.1, "sequence": 42,
                "table": {"ready": True, "detected_ids": [0, 1, 2, 3, 4],
                          "basket_mapping": {"4": "red"},
                          "basket_markers": {"4": {"color": "red"}}},
                "detections": [{"confidence": 0.95, "xyxy": [420, 200, 458, 252]}],
            }),
            fixed_slots=validate_slots(json.loads(DEFAULT_SLOTS.read_text(encoding="utf-8"))),
            allow_manual_capture=False,
        )
        responses = []
        handler._json = lambda payload, status=HTTPStatus.OK: responses.append((status, payload))
        handler.do_POST()
        self.assertEqual(responses[0][0], HTTPStatus.OK)
        self.assertEqual(responses[0][1]["routes"][0]["target_marker_id"], 4)
        self.assertFalse(responses[0][1]["motion_authorized"])
        self.assertFalse(responses[0][1]["robot_coordinates_included"])

    def test_video_index_resolves_video_node(self):
        self.assertEqual(video_index("/dev/video4"), 4)

    def test_existing_lelab_preview_is_an_http_stream(self):
        self.assertTrue(is_http_stream("http://127.0.0.1:8000/camera-preview/8"))
        self.assertFalse(is_http_stream("/dev/video8"))
        self.assertTrue(is_http_jpeg("http://127.0.0.1:8030/frame/ceiling.jpg"))
        self.assertFalse(is_http_jpeg("http://127.0.0.1:8000/camera-preview/8"))

    def test_table_projection_and_roi_gate(self):
        homography = np.asarray([[2.0, 0.0, -20.0], [0.0, 2.0, -40.0], [0.0, 0.0, 1.0]])
        point = project_table_xy(np, homography, 60.0, 80.0)
        self.assertEqual(point, (100.0, 120.0))
        roi = {"x": (80.0, 220.0), "y": (100.0, 300.0)}
        self.assertTrue(inside_roi(point, roi))
        self.assertFalse(inside_roi((79.9, 120.0), roi))

    def test_equalized_fallback_adds_only_missing_marker_without_replacing_original(self):
        class FakeCV2:
            COLOR_BGR2GRAY = 1

            @staticmethod
            def cvtColor(image, _code):
                return image

            @staticmethod
            def equalizeHist(image):
                return image + 1

        class FakeDetector:
            def detectMarkers(self, image):
                if image == 1:
                    return ["original-0"], np.asarray([[0]]), []
                return ["retry-0", "retry-4", "retry-9"], np.asarray([[0], [4], [9]]), []

        detected, recovered = detect_table_markers(FakeCV2, FakeDetector(), 1, {0, 4})
        self.assertEqual(detected, {0: "original-0", 4: "retry-4"})
        self.assertEqual(recovered, [4])


if __name__ == "__main__":
    unittest.main()
