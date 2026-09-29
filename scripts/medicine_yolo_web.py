#!/usr/bin/env python3
"""Serve a read-only live medicine-detection overlay from a camera source.

The server exposes only HTML, health JSON, detection JSON, and MJPEG output.
It contains no LeLab, serial, torque, USB, or robot-control endpoint.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import threading
import time
from io import BufferedReader
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from detect_medicine_onnx import decode_detections, letterbox


INDEX_HTML = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>약통 YOLO 읽기 전용 프리뷰</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#10151c;color:#e8eef6;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
main{max-width:1320px;margin:auto;padding:24px}h1{font-size:24px;margin:0 0 8px}.note{color:#aebdce;margin-bottom:16px}
.badge{display:inline-block;background:#183b2a;color:#83efaf;padding:5px 9px;border-radius:999px;font-weight:700}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:14px}.view{margin:0}.view figcaption{padding:7px 2px;color:#cfe1f5;font-weight:700}
img{display:block;width:100%;background:#05080b;border:1px solid #2a3949;border-radius:10px}
pre{white-space:pre-wrap;background:#18212b;padding:12px;border-radius:8px;color:#cfe1f5}
</style></head><body><main>
<h1>약통 YOLO 읽기 전용 프리뷰</h1>
<div class="note"><span class="badge">ROBOT DISABLED</span> 천장 정면에는 YOLO와 ArUco 작업대 투영 좌표를 표시하고, 사선 카메라는 상태 확인용입니다. 좌표는 높이 보정 전 dry-run으로 로봇 목표점이 아닙니다.</div>
<section class="grid">
<figure class="view"><figcaption>천장 정면 · Astra · YOLO</figcaption><img src="/stream.mjpg" alt="medicine detection stream"></figure>
<figure class="view"><figcaption>천장 사선 · RealSense D435</figcaption><img src="/angled.mjpg" alt="angled camera stream"></figure>
</section>
<pre id="status">상태 읽는 중…</pre>
<script>async function poll(){try{const r=await fetch('/health',{cache:'no-store'});document.querySelector('#status').textContent=JSON.stringify(await r.json(),null,2)}catch(e){document.querySelector('#status').textContent=String(e)}}poll();setInterval(poll,1500)</script>
</main></body></html>"""


def read_exact(stream: BufferedReader, size: int) -> bytes:
    """Read one complete raw frame, returning b"" at a clean EOF."""
    chunks = []
    remaining = size
    while remaining:
        chunk = stream.read(remaining)
        if not chunk:
            return b""
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def project_table_xy(np_module, homography, u: float, v: float) -> tuple[float, float]:
    projected = np_module.asarray(homography, dtype=np_module.float64) @ np_module.asarray(
        [u, v, 1.0], dtype=np_module.float64
    )
    if abs(float(projected[2])) < 1e-12:
        raise ValueError("homography projected point at infinity")
    xy = projected[:2] / projected[2]
    return float(xy[0]), float(xy[1])


def inside_roi(point: tuple[float, float], roi: dict) -> bool:
    return roi["x"][0] <= point[0] <= roi["x"][1] and roi["y"][0] <= point[1] <= roi["y"][1]


class TableMapper:
    """Project image centers onto the ArUco-defined table plane for dry-run display."""

    def __init__(self, config_path: Path, cv2_module, np_module):
        raw = json.loads(config_path.read_text(encoding="utf-8"))
        markers = raw["markers"]
        self.cv2 = cv2_module
        self.np = np_module
        self.config_path = str(config_path)
        self.reference_centers = {
            int(marker_id): (float(point[0]), float(point[1]))
            for marker_id, point in markers["reference_centers_mm"].items()
        }
        self.reference_ids = sorted(self.reference_centers)
        self.basket_ids = {int(marker_id): str(color) for marker_id, color in markers.get("basket_ids", {}).items()}
        roi = raw["pickup_roi_table_mm"]
        self.roi = {
            "x": (float(roi["x"][0]), float(roi["x"][1])),
            "y": (float(roi["y"][0]), float(roi["y"][1])),
        }
        dictionary_name = markers.get("dictionary", "DICT_4X4_50")
        dictionary_id = getattr(cv2_module.aruco, dictionary_name)
        dictionary = cv2_module.aruco.getPredefinedDictionary(dictionary_id)
        parameters = cv2_module.aruco.DetectorParameters()
        parameters.cornerRefinementMethod = cv2_module.aruco.CORNER_REFINE_SUBPIX
        self.detector = cv2_module.aruco.ArucoDetector(dictionary, parameters)

    def analyze(self, image, overlay, detections: list[dict]) -> dict:
        cv2, np = self.cv2, self.np
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        corners, ids, _ = self.detector.detectMarkers(gray)
        detected_ids = [] if ids is None else [int(value) for value in ids.flatten()]
        if ids is not None:
            cv2.aruco.drawDetectedMarkers(overlay, corners, ids)
        detected = (
            {}
            if ids is None
            else {
                int(marker_id): marker_corners.reshape(4, 2).mean(axis=0)
                for marker_corners, marker_id in zip(corners, ids.flatten())
            }
        )
        common = sorted(set(detected).intersection(self.reference_centers))
        homography = None
        rms = None
        if len(common) == len(self.reference_ids):
            image_points = np.asarray([detected[marker_id] for marker_id in common], dtype=np.float64)
            table_points = np.asarray([self.reference_centers[marker_id] for marker_id in common], dtype=np.float64)
            homography, _ = cv2.findHomography(image_points, table_points, method=0)
            if homography is not None:
                projected = cv2.perspectiveTransform(image_points.reshape(-1, 1, 2), homography).reshape(-1, 2)
                rms = float(np.sqrt(np.mean(np.sum((projected - table_points) ** 2, axis=1))))

        inside_count = 0
        basket_markers = {}
        if homography is not None:
            for marker_id, color in self.basket_ids.items():
                if marker_id not in detected:
                    continue
                center = detected[marker_id]
                point = project_table_xy(np, homography, float(center[0]), float(center[1]))
                basket_markers[str(marker_id)] = {
                    "color": color,
                    "table_xy_mm": [round(point[0], 3), round(point[1], 3)],
                }
                label_color = {
                    "red": (0, 0, 255),
                    "green": (0, 255, 0),
                    "blue": (255, 0, 0),
                }.get(color.lower(), (255, 255, 0))
                cv2.putText(
                    overlay,
                    f"{color.upper()} ID{marker_id}",
                    (max(2, round(float(center[0])) - 30), min(image.shape[0] - 8, round(float(center[1])) + 44)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.42,
                    label_color,
                    2,
                )
        for detection in detections:
            detection["image_center_table_mm"] = None
            detection["inside_pickup_roi"] = False
            if homography is None:
                continue
            x1, y1, x2, y2 = detection["xyxy"]
            point = project_table_xy(np, homography, (x1 + x2) / 2, (y1 + y2) / 2)
            detection["image_center_table_mm"] = [round(point[0], 3), round(point[1], 3)]
            detection["inside_pickup_roi"] = inside_roi(point, self.roi)
            inside_count += int(detection["inside_pickup_roi"])
            center = (round((x1 + x2) / 2), round((y1 + y2) / 2))
            cv2.drawMarker(overlay, center, (0, 255, 255), cv2.MARKER_CROSS, 12, 2)
            text = f"table ({point[0]:.1f}, {point[1]:.1f}) mm"
            cv2.putText(
                overlay,
                text,
                (max(2, round(x1)), min(image.shape[0] - 8, round(y2) + 18)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (0, 255, 255),
                2,
            )
        return {
            "ready": homography is not None,
            "required_ids": self.reference_ids,
            "detected_ids": detected_ids,
            "reference_rms_mm": None if rms is None else round(rms, 6),
            "pickup_roi_table_mm": {"x": list(self.roi["x"]), "y": list(self.roi["y"])},
            "detections_inside_pickup_roi": inside_count,
            "basket_markers": basket_markers,
            "basket_mapping": {str(marker_id): color for marker_id, color in self.basket_ids.items()},
            "projection": "bbox image center projected onto table plane; object height not corrected",
            "robot_target_authorized": False,
        }


class DetectionWorker:
    def __init__(
        self,
        model: Path,
        device: str,
        image_size: int,
        confidence: float,
        iou: float,
        raw_rgb_command: Path | None = None,
        raw_width: int = 640,
        raw_height: int = 480,
        workspace_config: Path | None = None,
    ):
        import cv2
        import numpy as np

        self.cv2 = cv2
        self.np = np
        self.device = device
        self.raw_rgb_command = raw_rgb_command
        self.raw_width = raw_width
        self.raw_height = raw_height
        self.image_size = image_size
        self.confidence = confidence
        self.iou = iou
        self.net = cv2.dnn.readNetFromONNX(str(model))
        self.table_mapper = None if workspace_config is None else TableMapper(workspace_config, cv2, np)
        self.model = str(model)
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run, name="medicine-yolo-camera", daemon=True)
        self.sequence = 0
        self.jpeg = None
        self.detections = []
        self.inference_ms = None
        self.updated_monotonic = None
        self.error = None
        self.table_status = None
        self.capture_process = None

    def start(self):
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        process = self.capture_process
        if process is not None and process.poll() is None:
            process.terminate()
        self.thread.join(timeout=5)

    def snapshot(self):
        with self.lock:
            age = None if self.updated_monotonic is None else round(time.monotonic() - self.updated_monotonic, 3)
            return {
                "ok": self.jpeg is not None and self.error is None,
                "source": str(self.raw_rgb_command) if self.raw_rgb_command else self.device,
                "model": self.model,
                "sequence": self.sequence,
                "frame_age_s": age,
                "inference_ms": self.inference_ms,
                "detection_count": len(self.detections),
                "detections": self.detections,
                "table": self.table_status,
                "error": self.error,
                "robot_enabled": False,
            }

    def latest_jpeg(self):
        with self.lock:
            return self.sequence, self.jpeg

    def _frames(self):
        cv2, np = self.cv2, self.np
        if self.raw_rgb_command is not None:
            process = subprocess.Popen(
                [str(self.raw_rgb_command)],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env=os.environ.copy(),
            )
            self.capture_process = process
            assert process.stdout is not None
            frame_size = self.raw_width * self.raw_height * 3
            try:
                while not self.stop_event.is_set():
                    raw = read_exact(process.stdout, frame_size)
                    if not raw:
                        return
                    rgb = np.frombuffer(raw, dtype=np.uint8).reshape(self.raw_height, self.raw_width, 3)
                    yield cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        process.kill()
                self.capture_process = None
            return

        cap = cv2.VideoCapture(self.device, cv2.CAP_V4L2)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if not cap.isOpened():
            return
        try:
            while not self.stop_event.is_set():
                ok, image = cap.read()
                if not ok:
                    time.sleep(0.2)
                    continue
                yield image
        finally:
            cap.release()

    def _run(self):
        cv2, np = self.cv2, self.np
        try:
            frames = self._frames()
            for image in frames:
                if self.stop_event.is_set():
                    break
                started = time.perf_counter()
                prepared, scale, pad_x, pad_y = letterbox(image, self.image_size, cv2, np)
                blob = cv2.dnn.blobFromImage(
                    prepared, 1 / 255.0, (self.image_size, self.image_size), swapRB=True
                )
                self.net.setInput(blob)
                raw_output = self.net.forward()
                detections = decode_detections(
                    raw_output,
                    image.shape[1],
                    image.shape[0],
                    scale,
                    pad_x,
                    pad_y,
                    self.confidence,
                    self.iou,
                    cv2,
                    np,
                )
                inference_ms = round((time.perf_counter() - started) * 1000, 1)
                overlay = image.copy()
                table_status = (
                    None if self.table_mapper is None else self.table_mapper.analyze(image, overlay, detections)
                )
                for detection in detections:
                    x1, y1, x2, y2 = (round(value) for value in detection["xyxy"])
                    cv2.rectangle(overlay, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    label = f"medicine {detection['confidence']:.2f}"
                    cv2.putText(
                        overlay,
                        label,
                        (x1, max(18, y1 - 6)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.55,
                        (0, 255, 0),
                        2,
                    )
                encoded, buffer = cv2.imencode(".jpg", overlay, [cv2.IMWRITE_JPEG_QUALITY, 85])
                if not encoded:
                    with self.lock:
                        self.error = "JPEG encoding failed"
                    continue
                with self.lock:
                    self.sequence += 1
                    self.jpeg = buffer.tobytes()
                    self.detections = detections
                    self.inference_ms = inference_ms
                    self.table_status = table_status
                    self.updated_monotonic = time.monotonic()
                    self.error = None
            if not self.stop_event.is_set():
                with self.lock:
                    self.error = "camera source ended"
        except Exception as exc:
            with self.lock:
                self.error = f"camera source failed: {exc}"


def video_index(device: str) -> int | str:
    resolved = os.path.realpath(device)
    match = re.search(r"video(\d+)$", resolved)
    return int(match.group(1)) if match else device


class PreviewWorker:
    """Read and JPEG-encode a secondary V4L2 camera without inference."""

    def __init__(self, device: str, width: int = 640, height: int = 480, fourcc: str = "YUYV"):
        import cv2

        self.cv2 = cv2
        self.device = device
        self.width = width
        self.height = height
        self.fourcc = fourcc
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run, name="angled-camera-preview", daemon=True)
        self.sequence = 0
        self.jpeg = None
        self.updated_monotonic = None
        self.error = "starting"

    def start(self):
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        self.thread.join(timeout=5)

    def snapshot(self):
        with self.lock:
            age = None if self.updated_monotonic is None else round(time.monotonic() - self.updated_monotonic, 3)
            return {
                "ok": self.jpeg is not None and self.error is None and age is not None and age < 5,
                "device": self.device,
                "sequence": self.sequence,
                "frame_age_s": age,
                "error": self.error,
            }

    def latest_jpeg(self):
        with self.lock:
            return self.sequence, self.jpeg

    def _run(self):
        cv2 = self.cv2
        while not self.stop_event.is_set():
            cap = cv2.VideoCapture(video_index(self.device), cv2.CAP_V4L2)
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*self.fourcc))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            cap.set(cv2.CAP_PROP_FPS, 30)
            if not cap.isOpened():
                with self.lock:
                    self.error = f"failed to open {self.device}"
                cap.release()
                self.stop_event.wait(1)
                continue
            try:
                while not self.stop_event.is_set():
                    ok, image = cap.read()
                    if not ok:
                        with self.lock:
                            self.error = "frame read failed"
                        break
                    encoded, buffer = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 82])
                    if not encoded:
                        with self.lock:
                            self.error = "JPEG encoding failed"
                        continue
                    with self.lock:
                        self.sequence += 1
                        self.jpeg = buffer.tobytes()
                        self.updated_monotonic = time.monotonic()
                        self.error = None
            finally:
                cap.release()
            self.stop_event.wait(1)


class Handler(BaseHTTPRequestHandler):
    server_version = "MedicineYoloReadOnly/1.0"

    @property
    def worker(self):
        return self.server.worker

    @property
    def angled_worker(self):
        return self.server.angled_worker

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/":
            self._send(HTTPStatus.OK, "text/html; charset=utf-8", INDEX_HTML.encode())
        elif path == "/health":
            snapshot = self.worker.snapshot()
            if self.angled_worker is not None:
                angled = self.angled_worker.snapshot()
                snapshot["angled_camera"] = angled
                snapshot["ok"] = snapshot["ok"] and angled["ok"]
            self._json(snapshot)
        elif path == "/detections.json":
            snapshot = self.worker.snapshot()
            self._json({"detections": snapshot["detections"], "sequence": snapshot["sequence"], "robot_enabled": False})
        elif path == "/stream.mjpg":
            self._stream(self.worker)
        elif path == "/angled.mjpg" and self.angled_worker is not None:
            self._stream(self.angled_worker)
        else:
            self._json({"detail": "Not Found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self):
        self._json({"detail": "Read-only server"}, HTTPStatus.METHOD_NOT_ALLOWED)

    def _send(self, status, content_type, body):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, payload, status=HTTPStatus.OK):
        self._send(status, "application/json; charset=utf-8", (json.dumps(payload, ensure_ascii=False) + "\n").encode())

    def _stream(self, worker):
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        last_sequence = -1
        try:
            while True:
                sequence, jpeg = worker.latest_jpeg()
                if jpeg is None or sequence == last_sequence:
                    time.sleep(0.05)
                    continue
                last_sequence = sequence
                self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n")
                self.wfile.write(f"Content-Length: {len(jpeg)}\r\n\r\n".encode())
                self.wfile.write(jpeg)
                self.wfile.write(b"\r\n")
        except (BrokenPipeError, ConnectionResetError):
            return

    def log_message(self, format, *args):
        return


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--device", default="/dev/video8")
    parser.add_argument(
        "--raw-rgb-command",
        type=Path,
        help="Executable that writes packed RGB888 frames to stdout (bypasses V4L2)",
    )
    parser.add_argument("--raw-width", type=int, default=640)
    parser.add_argument("--raw-height", type=int, default=480)
    parser.add_argument("--angled-device", help="Optional secondary V4L2 camera shown without inference")
    parser.add_argument("--angled-fourcc", default="YUYV")
    parser.add_argument("--workspace-config", type=Path, help="Astra RGB-D workspace JSON for dry-run table projection")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8020)
    parser.add_argument("--image-size", type=int, default=640)
    parser.add_argument("--confidence", type=float, default=0.25)
    parser.add_argument("--iou", type=float, default=0.7)
    args = parser.parse_args()
    if not args.model.is_file():
        parser.error("--model does not exist")
    if args.raw_rgb_command is not None and not args.raw_rgb_command.is_file():
        parser.error("--raw-rgb-command does not exist")
    if args.workspace_config is not None and not args.workspace_config.is_file():
        parser.error("--workspace-config does not exist")
    if args.raw_width <= 0 or args.raw_height <= 0:
        parser.error("--raw-width and --raw-height must be positive")
    if len(args.angled_fourcc) != 4:
        parser.error("--angled-fourcc must contain exactly four characters")
    if not 0 < args.confidence < 1 or not 0 < args.iou < 1:
        parser.error("--confidence and --iou must be between 0 and 1")
    return args


def main():
    args = parse_args()
    worker = DetectionWorker(
        args.model,
        args.device,
        args.image_size,
        args.confidence,
        args.iou,
        raw_rgb_command=args.raw_rgb_command,
        raw_width=args.raw_width,
        raw_height=args.raw_height,
        workspace_config=args.workspace_config,
    )
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.worker = worker
    angled_worker = PreviewWorker(args.angled_device, fourcc=args.angled_fourcc) if args.angled_device else None
    server.angled_worker = angled_worker
    worker.start()
    if angled_worker is not None:
        angled_worker.start()
    source = args.raw_rgb_command or args.device
    print(f"READ_ONLY http://{args.host}:{args.port} source={source} robot_enabled=false", flush=True)
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        if angled_worker is not None:
            angled_worker.stop()
        worker.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
