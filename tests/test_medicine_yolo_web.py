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
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from medicine_yolo_web import (
    DetectionWorker, Handler, INDEX_HTML, TableMapper, detect_table_markers, inside_roi, is_http_jpeg, is_http_stream,
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
        self.assertIn("/api/table-point", INDEX_HTML)
        self.assertIn("작업대 평면 지점", INDEX_HTML)
        self.assertIn("높이가 있는 점", INDEX_HTML)
        self.assertIn("명령 판정만", INDEX_HTML)
        self.assertIn("document.querySelector('#route-command').value=''", INDEX_HTML)
        self.assertIn("window.addEventListener('pageshow'", INDEX_HTML)
        self.assertIn("out.textContent+='\\n다시 프레임", INDEX_HTML)
        self.assertNotIn("out.textContent+='\n다시 프레임", INDEX_HTML)
        self.assertIn("작업대 변환이 유효하지 않습니다.\\n'+JSON.stringify", INDEX_HTML)
        self.assertNotIn("작업대 변환이 유효하지 않습니다.\n'+JSON.stringify", INDEX_HTML)
        self.assertIn("tableClickHistory=[]", INDEX_HTML)
        self.assertIn("tableClickHistory.push(d)", INDEX_HTML)
        self.assertIn("click_history:tableClickHistory", INDEX_HTML)

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

    def test_frozen_table_point_uses_exact_frame_homography(self):
        worker = DetectionWorker.__new__(DetectionWorker)
        worker.lock = threading.Lock()
        worker.np = np
        worker.frame_history = deque([{
            "sequence": 42,
            "monotonic": time.monotonic(),
            "image_size_px": [640, 480],
            "table": {
                "validity": "VALID_CURRENT_FRAME",
                "observed_at_utc": "2026-10-16T12:00:00+00:00",
                "homography_image_to_table": [[2.0, 0.0, -20.0], [0.0, 2.0, -40.0], [0.0, 0.0, 1.0]],
                "coordinate_space": "undistorted_full_frame",
                "workspace_config": {"path": "/config.json", "sha256": "abc"},
                "intrinsic_calibration": {"path": "/intrinsic.json", "sha256": "def"},
            },
        }])
        result = worker.project_table_point(sequence=42, pixel=(60.0, 80.0))
        self.assertEqual(result["table_xy_mm"], [100.0, 120.0])
        self.assertEqual(result["observed_at_utc"], "2026-10-16T12:00:00+00:00")
        self.assertEqual(result["transform_validity"], "VALID_CURRENT_FRAME")
        self.assertEqual(result["pixel_coordinate_space"], "undistorted_full_frame")
        self.assertIn("z=0", result["surface_assumption"])
        self.assertFalse(result["motion_authorized"])
        with self.assertRaisesRegex(ValueError, "no longer available"):
            worker.project_table_point(sequence=41, pixel=(60.0, 80.0))

    def test_table_point_endpoint_uses_requested_frozen_sequence(self):
        body = json.dumps({"sequence": 42, "pixel": [60.0, 80.0]}).encode()
        headers = Message()
        headers["Content-Type"] = "application/json"
        headers["Content-Length"] = str(len(body))
        calls = []
        handler = Handler.__new__(Handler)
        handler.path = "/api/table-point"
        handler.headers = headers
        handler.rfile = io.BytesIO(body)
        handler.server = SimpleNamespace(worker=SimpleNamespace(
            project_table_point=lambda **kwargs: calls.append(kwargs) or {
                "status": "TABLE_PLANE_POINT",
                "frame_sequence": kwargs["sequence"],
                "table_xy_mm": [100.0, 120.0],
                "robot_enabled": False,
                "motion_authorized": False,
            }
        ))
        responses = []
        handler._json = lambda payload, status=HTTPStatus.OK: responses.append((status, payload))
        handler.do_POST()
        self.assertEqual(calls, [{"sequence": 42, "pixel": (60.0, 80.0)}])
        self.assertEqual(responses[0][0], HTTPStatus.OK)
        self.assertEqual(responses[0][1]["table_xy_mm"], [100.0, 120.0])
        self.assertFalse(responses[0][1]["motion_authorized"])

    def test_table_mapper_loads_and_applies_intrinsic_without_resize_or_crop(self):
        import cv2

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            intrinsic = {
                "camera_matrix": [[100.0, 0.0, 2.0], [0.0, 100.0, 1.5], [0.0, 0.0, 1.0]],
                "dist_coeffs": [0.0, 0.0, 0.0, 0.0, 0.0],
                "image_size": [4, 3],
                "reprojection_rms_px": 0.478,
            }
            config = {
                "camera": {"intrinsic_file": "intrinsic.json",
                           "rgb": {"width": 4, "height": 3, "fps": 30, "format": "RGB888"}},
                "markers": {"dictionary": "DICT_4X4_50", "marker_size_mm": 70.0,
                            "marker_size_by_id_mm": {"7": 30.0},
                            "reference_centers_mm": {"0": [0, 0, 0], "1": [100, 0, 0],
                                                     "2": [100, 100, 0], "3": [0, 100, 0]},
                            "basket_ids": {}, "object_ids": {"7": "small"}},
                "pickup_roi_table_mm": {"x": [0, 100], "y": [0, 100], "status": "stale"},
                "transforms": {"world_axes": "+X ID0 to ID1; +Y into board; +Z above"},
            }
            (root / "intrinsic.json").write_text(json.dumps(intrinsic), encoding="utf-8")
            config_path = root / "workspace.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            mapper = TableMapper(config_path, cv2, np)
            frame = np.arange(36, dtype=np.uint8).reshape(3, 4, 3)
            prepared = mapper.prepare_frame(frame)
            self.assertEqual(prepared.shape, frame.shape)
            self.assertEqual(mapper.intrinsic_image_size, (4, 3))
            self.assertEqual(mapper.marker_sizes_mm[7], 30.0)
            with self.assertRaisesRegex(ValueError, "does not match intrinsic"):
                mapper.prepare_frame(np.zeros((2, 4, 3), dtype=np.uint8))

    def test_basket_marker_projection_is_not_presented_as_basket_center(self):
        class FakeCV2:
            FONT_HERSHEY_SIMPLEX = 0
            LINE_AA = 1
            MARKER_CROSS = 2
            aruco = SimpleNamespace(drawDetectedMarkers=lambda *_args: None)

            @staticmethod
            def findHomography(_image_points, _table_points, method=0):
                return np.eye(3), None

            @staticmethod
            def perspectiveTransform(points, _homography):
                return points

            @staticmethod
            def putText(*_args):
                return None

            @staticmethod
            def circle(*_args):
                return None

            @staticmethod
            def drawMarker(*_args):
                return None

            @staticmethod
            def arrowedLine(*_args, **_kwargs):
                return None

        mapper = TableMapper.__new__(TableMapper)
        mapper.cv2, mapper.np = FakeCV2, np
        mapper.detector = object()
        mapper.reference_centers = {0: (0, 0), 1: (100, 0), 2: (100, 100), 3: (0, 100)}
        mapper.reference_ids = [0, 1, 2, 3]
        mapper.basket_ids = {5: "green"}
        mapper.object_ids = {}
        mapper.dictionary_name = "DICT_4X4_50"
        mapper.marker_sizes_mm = {0: 70.0, 1: 70.0, 2: 70.0, 3: 70.0, 5: 70.0}
        mapper.roi = {"x": (0, 100), "y": (0, 100)}
        mapper.roi_enabled = True
        mapper.roi_status = "verified"
        mapper.axis_convention = "+X ID0 to ID1; +Y into board; +Z above"
        mapper.config_path = "/config.json"
        mapper.config_sha256 = "abc"
        mapper.intrinsic_path = "/intrinsic.json"
        mapper.intrinsic_sha256 = "def"
        mapper.intrinsic_image_size = (640, 480)
        mapper.intrinsic_rms_px = 0.478
        mapper.capture = {"width": 640, "height": 480, "fps": 30, "format": "RGB888"}
        centers = {0: (0, 0), 1: (100, 0), 2: (100, 100), 3: (0, 100), 5: (60, 50)}
        corners = {marker_id: np.asarray([[[x, y]] * 4], dtype=np.float32)
                   for marker_id, (x, y) in centers.items()}
        image = np.zeros((480, 640, 3), dtype=np.uint8)
        with patch("medicine_yolo_web.detect_table_markers", return_value=(corners, [])):
            result = mapper.analyze(image, image.copy(), [])
        marker = result["basket_markers"]["5"]
        self.assertEqual(marker["table_xy_mm"], [60.0, 50.0])
        self.assertIsNone(marker["basket_center_table_xy_mm"])
        self.assertFalse(marker["basket_pose_verified"])
        self.assertFalse(result["basket_pose_authorized"])

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

    def test_missing_reference_never_reuses_previous_homography(self):
        class FakeCV2:
            FONT_HERSHEY_SIMPLEX = 0
            LINE_AA = 1
            MARKER_CROSS = 2
            aruco = SimpleNamespace(drawDetectedMarkers=lambda *_args: None)

            @staticmethod
            def findHomography(_image_points, _table_points, method=0):
                return np.eye(3), None

            @staticmethod
            def perspectiveTransform(points, _homography):
                return points

            @staticmethod
            def putText(*_args):
                return None

            @staticmethod
            def circle(*_args):
                return None

            @staticmethod
            def drawMarker(*_args):
                return None

            @staticmethod
            def arrowedLine(*_args, **_kwargs):
                return None

        mapper = TableMapper.__new__(TableMapper)
        mapper.cv2, mapper.np = FakeCV2, np
        mapper.detector = object()
        mapper.reference_centers = {0: (0, 0), 1: (100, 0), 2: (100, 100), 3: (0, 100)}
        mapper.reference_ids = [0, 1, 2, 3]
        mapper.basket_ids, mapper.object_ids = {}, {}
        mapper.dictionary_name = "DICT_4X4_50"
        mapper.marker_sizes_mm = {marker_id: 70.0 for marker_id in mapper.reference_ids}
        mapper.roi = {"x": (0, 100), "y": (0, 100)}
        mapper.roi_enabled, mapper.roi_status = False, "stale"
        mapper.axis_convention = "+X ID0 to ID1; +Y into board; +Z above"
        mapper.config_path, mapper.config_sha256 = "/config.json", "abc"
        mapper.intrinsic_path, mapper.intrinsic_sha256 = "/intrinsic.json", "def"
        mapper.intrinsic_image_size, mapper.intrinsic_rms_px = (640, 480), 0.478
        mapper.capture = {"width": 640, "height": 480, "fps": 30, "format": "RGB888"}
        all_centers = {marker_id: (20 + marker_id * 30, 30 + marker_id * 20)
                       for marker_id in mapper.reference_ids}
        all_corners = {marker_id: np.asarray([[[x, y]] * 4], dtype=np.float32)
                       for marker_id, (x, y) in all_centers.items()}
        missing_one = {marker_id: corners for marker_id, corners in all_corners.items()
                       if marker_id != 1}
        image = np.zeros((480, 640, 3), dtype=np.uint8)
        with patch("medicine_yolo_web.detect_table_markers",
                   side_effect=[(all_corners, []), (missing_one, [])]):
            valid = mapper.analyze(image, image.copy(), [])
            invalid = mapper.analyze(image, image.copy(), [])
        self.assertEqual(valid["validity"], "VALID_CURRENT_FRAME")
        self.assertEqual(invalid["validity"], "INVALID_CURRENT_FRAME")
        self.assertEqual(invalid["invalid_reason"]["missing_reference_ids"], [1])
        self.assertIsNone(invalid["homography_image_to_table"])


if __name__ == "__main__":
    unittest.main()
