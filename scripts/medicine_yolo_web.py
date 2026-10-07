#!/usr/bin/env python3
"""Serve a robot-read-only live medicine-detection overlay from a camera source.

Optional manual capture writes human-labeled raw JPEG review candidates locally.
There is no LeLab, serial, torque, USB, or robot-control endpoint.
"""

from __future__ import annotations

import argparse
import base64
from collections import deque
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import secrets
import subprocess
import threading
import time
from io import BufferedReader
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen

from detect_medicine_onnx import decode_detections, letterbox
from medicine_fixed_slot_command import (DEFAULT_SLOTS, decide_fixed_slot_command,
                                        parse_command, validate_slots)
from medicine_sort_dry_run import DEFAULT_RULES, decide_manual_pixel, validate_rules


INDEX_HTML = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>약통 판정·로컬 사진 저장</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#10151c;color:#e8eef6;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
main{max-width:1320px;margin:auto;padding:24px}h1{font-size:24px;margin:0 0 8px}.note{color:#aebdce;margin-bottom:16px}
.badge{display:inline-block;background:#183b2a;color:#83efaf;padding:5px 9px;border-radius:999px;font-weight:700}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:14px}.view{margin:0}.view figcaption{padding:7px 2px;color:#cfe1f5;font-weight:700}
img{display:block;width:100%;background:#05080b;border:1px solid #2a3949;border-radius:10px}
pre{white-space:pre-wrap;background:#18212b;padding:12px;border-radius:8px;color:#cfe1f5}
</style></head><body><main>
<h1>약통 판정·로컬 사진 저장</h1>
<div class="note"><span class="badge">ROBOT DISABLED</span> 천장 정면에는 YOLO와 ArUco 작업대 투영 좌표를 표시하고, 사선 카메라는 상태 확인용입니다. 좌표는 높이 보정 전 dry-run으로 로봇 목표점이 아닙니다.</div>
<section class="grid">
<figure class="view"><figcaption>천장 정면 · Astra · YOLO</figcaption><img src="/stream.mjpg" alt="medicine detection stream"></figure>
<figure class="view"><figcaption>천장 사선 · RealSense D435</figcaption><img src="/angled.mjpg" alt="angled camera stream"></figure>
</section>
<section><h2>수동 위치 지정 · 사진 저장</h2>
<p>움직임이 멈춘 장면에서 A/B/C를 사람이 확인하고 프레임을 고정한 뒤 약통 가운데를 클릭하세요. 판정 뒤 <b>사진·라벨 로컬 저장</b>을 눌러야 파일이 남습니다. 이 화면은 팔을 움직이지 않습니다.</p>
<label>확인한 약통 <select id="manual-label"><option value="">종류를 선택하세요</option><option value="A">A 큰 약통</option><option value="B">B 중간 약통</option><option value="C">C 작은 약통</option></select></label>
<button id="freeze" type="button">현재 프레임 고정</button>
<p><img id="manual-frame" alt="고정한 정면 프레임; 클릭해 약통 위치 지정"></p><button id="manual-save" type="button" disabled>사진·라벨 로컬 저장</button><pre id="manual-result">프레임을 고정하세요.</pre></section>
<section><h2>고정 배치 명령 미리보기 · 로봇 구동 없음</h2>
<p>왼쪽 C·가운데 B·오른쪽 A 배치에서 현재 보이는 약통과 바구니 마커를 검사합니다. 입력한 명령은 저장하거나 실행하지 않습니다.</p>
<label>목적지 명령 <input id="route-command" type="text" size="48" autocomplete="off" placeholder="예: A를 빨간색, B도 빨간색 박스"></label>
<button id="route-preview" type="button">명령 판정만</button><pre id="route-result">명령을 입력하세요.</pre></section>
<pre id="status">상태 읽는 중…</pre>
<script>
let frozen=null, frozenAt=0, selected=null;
async function poll(){try{const r=await fetch('/health',{cache:'no-store'}),d=await r.json();document.querySelector('#status').textContent=JSON.stringify(d,null,2);document.querySelector('#manual-save').hidden=!d.manual_capture_enabled}catch(e){document.querySelector('#status').textContent=String(e)}}
async function freeze(){const out=document.querySelector('#manual-result');selected=null;document.querySelector('#manual-save').disabled=true;try{const r=await fetch('/manual-frame.json',{cache:'no-store'});const d=await r.json();if(!r.ok||!d.snapshot.ok||d.snapshot.frame_age_s>0.75){out.textContent='카메라 프레임이 신선하지 않습니다.';return}frozen=d.snapshot;frozenAt=Date.now();const img=document.querySelector('#manual-frame');img.src='data:image/jpeg;base64,'+d.jpeg_base64;out.textContent='고정 프레임 '+frozen.sequence+' — 약통 중심을 클릭하세요.'}catch(e){out.textContent=String(e)}}
function iou(a,b){const w=Math.max(0,Math.min(a[2],b[2])-Math.max(a[0],b[0])),h=Math.max(0,Math.min(a[3],b[3])-Math.max(a[1],b[1]));const overlap=w*h;return overlap/((a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-overlap)}
function choose(e){const out=document.querySelector('#manual-result'),img=e.currentTarget;selected=null;document.querySelector('#manual-save').disabled=true;if(!frozen||!img.naturalWidth){out.textContent='먼저 프레임을 고정하세요.';return}if(Date.now()-frozenAt>10000){out.textContent='고정 프레임이 10초를 넘었습니다. 다시 고정하세요.';return}const label=document.querySelector('#manual-label').value,rules={A:[6,'blue'],B:[5,'green'],C:[4,'red']};if(!rules[label]){out.textContent='실제 약통 종류 A/B/C를 먼저 확인하고 선택하세요.';return}const rect=img.getBoundingClientRect(),x=(e.clientX-rect.left)*img.naturalWidth/rect.width,y=(e.clientY-rect.top)*img.naturalHeight/rect.height,t=frozen.table,[id,color]=rules[label];let reason=null;if(!t||!t.ready||!Array.isArray(t.required_ids)||!Array.isArray(t.detected_ids)||!t.required_ids.every(n=>t.detected_ids.includes(n)))reason='작업대 기준 마커 누락';else if(!t.detected_ids.includes(id)||!t.basket_markers||!t.basket_markers[id]||t.basket_markers[id].color!==color||!t.basket_mapping||t.basket_mapping[id]!==color)reason='목표 바구니 마커 불일치';const boxes=(frozen.detections||[]).filter(d=>Array.isArray(d.xyxy)&&d.xyxy.length===4&&d.xyxy[0]<=x&&x<=d.xyxy[2]&&d.xyxy[1]<=y&&y<=d.xyxy[3]).sort((a,b)=>b.confidence-a.confidence);if(!reason&&!boxes.length)reason='클릭점에 약통 검출 상자 없음';if(!reason&&boxes.some(d=>iou(boxes[0].xyxy,d.xyxy)<0.5))reason='여러 물체 후보가 겹침';const roiMatch=boxes.length>0&&boxes[0].inside_pickup_roi===true;const result={status:reason?'BLOCKED':'DRY_RUN_ROUTE_ONLY',reason,frame_sequence:frozen.sequence,clicked_pixel:[Math.round(x),Math.round(y)],human_label:label,target_marker_id:reason?null:id,target_color:reason?null:color,overlapping_boxes:boxes.length,pickup_roi_match:roiMatch,robot_enabled:false,motion_authorized:false,note:roiMatch?'클릭점은 로봇 집기 좌표가 아닙니다. 실제 색·물체 신원은 사람이 확인해야 합니다.':'기존 픽업 구역 밖입니다. 목적지 제안만 가능하고 자동 집기는 금지입니다.'};out.textContent=JSON.stringify(result,null,2);if(!reason){selected={label,sequence:frozen.sequence,pixel:[x,y],identity_confirmed:true};document.querySelector('#manual-save').disabled=false}}
async function saveManual(){const out=document.querySelector('#manual-result'),button=document.querySelector('#manual-save');if(!selected){out.textContent='먼저 약통 중심을 클릭하세요.';return}button.disabled=true;try{const r=await fetch('/api/manual-capture',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(selected)});const d=await r.json();out.textContent=JSON.stringify(d,null,2);if(!r.ok)out.textContent+='\\n다시 프레임을 고정해 촬영하세요.'}catch(e){out.textContent=String(e)}}
async function previewCommand(){const input=document.querySelector('#route-command'),out=document.querySelector('#route-result'),button=document.querySelector('#route-preview');if(!input.value.trim()){out.textContent='명령을 입력하세요.';return}button.disabled=true;try{const r=await fetch('/api/command-preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({command:input.value})});const d=await r.json();out.textContent=JSON.stringify(d,null,2)}catch(e){out.textContent=String(e)}finally{button.disabled=false}}
document.querySelector('#freeze').addEventListener('click',freeze);document.querySelector('#manual-frame').addEventListener('click',choose);document.querySelector('#manual-save').addEventListener('click',saveManual);document.querySelector('#route-preview').addEventListener('click',previewCommand);window.addEventListener('pageshow',()=>{document.querySelector('#manual-label').value='';document.querySelector('#route-command').value='';selected=null;document.querySelector('#manual-save').disabled=true});poll();setInterval(poll,1500)
</script>
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


def mjpeg_jpegs(stream, stop_event, chunk_size: int = 65536):
    """Yield the newest complete JPEG in each network chunk, retaining partial frames."""
    buffer = bytearray()
    start_marker = b"\xff\xd8"
    end_marker = b"\xff\xd9"
    while not stop_event.is_set():
        chunk = stream.read(chunk_size)
        if not chunk:
            return
        buffer.extend(chunk)
        latest = None
        while True:
            start = buffer.find(start_marker)
            if start < 0:
                trailing_ff = buffer.endswith(b"\xff")
                buffer.clear()
                if trailing_ff:
                    buffer.extend(b"\xff")
                break
            end = buffer.find(end_marker, start + 2)
            if end < 0:
                if start:
                    del buffer[:start]
                if len(buffer) > 2_000_000:
                    buffer.clear()
                break
            latest = bytes(buffer[start:end + 2])
            del buffer[:end + 2]
        if latest is not None:
            yield latest


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


def detect_table_markers(cv2_module, detector, image, expected_ids: set[int]):
    """Keep original detections and retry only missing IDs after contrast equalization."""
    gray = cv2_module.cvtColor(image, cv2_module.COLOR_BGR2GRAY)
    corners, ids, _ = detector.detectMarkers(gray)
    detected = {} if ids is None else {
        int(marker_id): marker_corners
        for marker_corners, marker_id in zip(corners, ids.flatten())
    }
    recovered = []
    missing = expected_ids - detected.keys()
    if missing:
        equalized = cv2_module.equalizeHist(gray)
        retry_corners, retry_ids, _ = detector.detectMarkers(equalized)
        if retry_ids is not None:
            for marker_corners, marker_id in zip(retry_corners, retry_ids.flatten()):
                marker_id = int(marker_id)
                if marker_id in missing:
                    detected[marker_id] = marker_corners
                    recovered.append(marker_id)
    return detected, sorted(recovered)


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
        marker_corners, recovered_ids = detect_table_markers(
            cv2, self.detector, image, set(self.reference_ids) | set(self.basket_ids)
        )
        detected_ids = sorted(marker_corners)
        if marker_corners:
            cv2.aruco.drawDetectedMarkers(
                overlay,
                [marker_corners[marker_id] for marker_id in detected_ids],
                np.asarray(detected_ids, dtype=np.int32).reshape(-1, 1),
            )
        detected = {
            marker_id: corners.reshape(4, 2).mean(axis=0)
            for marker_id, corners in marker_corners.items()
        }
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
            "equalized_fallback_ids": recovered_ids,
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
        self._pending_raw_jpeg = None
        self.frame_history = deque(maxlen=96)
        self.saved_sequences = set()

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
                "ok": self.jpeg is not None and self.error is None and age is not None and age < 5,
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

    def snapshot_with_jpeg(self):
        """Return one internally consistent frame and status for manual review."""
        with self.lock:
            age = None if self.updated_monotonic is None else round(time.monotonic() - self.updated_monotonic, 3)
            snapshot = {
                "ok": self.jpeg is not None and self.error is None and age is not None and age < 5,
                "sequence": self.sequence,
                "frame_age_s": age,
                "detections": self.detections,
                "table": self.table_status,
                "error": self.error,
                "robot_enabled": False,
            }
            jpeg = self.jpeg
        return snapshot, jpeg

    def save_manual_capture(self, output_root: Path, rules: dict, *, label: str,
                            sequence: int, pixel: tuple[float, float]) -> dict:
        """Save one exact raw frame as a review candidate, never as training truth."""
        with self.lock:
            if sequence in self.saved_sequences:
                raise ValueError("this frame was already saved")
            record = next((item for item in self.frame_history if item["sequence"] == sequence), None)
            if record is None:
                raise ValueError("frozen frame is no longer available; freeze again")
            snapshot = {
                "ok": True,
                "robot_enabled": False,
                "sequence": sequence,
                "frame_age_s": time.monotonic() - record["monotonic"],
                "table": record["table"],
                "detections": record["detections"],
            }
            decision = decide_manual_pixel(snapshot, label, pixel, sequence, rules, max_age_s=15.0)
            if decision["status"] != "DRY_RUN_ROUTE_ONLY":
                raise ValueError(f"capture refused: {decision['reason']}")
            raw_jpeg = record["raw_jpeg"]
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
            folder = output_root / f"{stamp}_{label}_{sequence}_{secrets.token_hex(3)}"
            folder.mkdir(parents=True, exist_ok=False)
            (folder / "ceiling.jpg").write_bytes(raw_jpeg)
            metadata = {
                "capture_kind": "manual_bottle_candidate",
                "review_status": "FOR_REVIEW",
                "human_verified_label": label,
                "frame_sequence": sequence,
                "clicked_pixel": [round(pixel[0], 2), round(pixel[1], 2)],
                "raw_jpeg_sha256": hashlib.sha256(raw_jpeg).hexdigest(),
                "image_size_px": record["image_size_px"],
                "decision": decision,
                "source": str(self.device),
                "training_ready": False,
                "robot_enabled": False,
                "motion_authorized": False,
            }
            (folder / "metadata.json").write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            self.saved_sequences.add(sequence)
        return {"status": "SAVED_FOR_REVIEW", "folder": str(folder),
                "frame_sequence": sequence, "human_verified_label": label,
                "training_ready": False, "robot_enabled": False, "motion_authorized": False}

    def _frames(self):
        cv2, np = self.cv2, self.np
        if is_http_jpeg(self.device) and self.raw_rgb_command is None:
            while not self.stop_event.is_set():
                try:
                    with urlopen(self.device, timeout=3) as response:
                        jpeg = response.read(2_000_000)
                    image = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
                    if image is None:
                        raise ValueError("JPEG decode failed")
                    self._pending_raw_jpeg = jpeg
                    yield image
                except Exception as exc:
                    with self.lock:
                        self.error = f"cached JPEG source failed: {exc}"
                self.stop_event.wait(0.25)
            return
        if is_http_stream(self.device) and self.raw_rgb_command is None:
            with urlopen(self.device, timeout=5) as stream:
                for jpeg in mjpeg_jpegs(stream, self.stop_event):
                    image = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
                    if image is not None:
                        self._pending_raw_jpeg = jpeg
                        yield image
            return
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
                raw_jpeg = self._pending_raw_jpeg
                if raw_jpeg is None:
                    raw_ok, raw_buffer = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 90])
                    if not raw_ok:
                        with self.lock:
                            self.error = "raw JPEG encoding failed"
                        continue
                    raw_jpeg = raw_buffer.tobytes()
                self._pending_raw_jpeg = None
                with self.lock:
                    self.sequence += 1
                    self.jpeg = buffer.tobytes()
                    self.detections = detections
                    self.inference_ms = inference_ms
                    self.table_status = table_status
                    self.updated_monotonic = time.monotonic()
                    self.frame_history.append({
                        "sequence": self.sequence,
                        "monotonic": self.updated_monotonic,
                        "raw_jpeg": raw_jpeg,
                        "image_size_px": [int(image.shape[1]), int(image.shape[0])],
                        "detections": detections,
                        "table": table_status,
                    })
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


def is_http_stream(source: str) -> bool:
    return source.startswith(("http://", "https://"))


def is_http_jpeg(source: str) -> bool:
    return is_http_stream(source) and source.split("?", 1)[0].endswith(".jpg")


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
        if is_http_jpeg(self.device):
            while not self.stop_event.is_set():
                try:
                    with urlopen(self.device, timeout=3) as response:
                        jpeg = response.read(2_000_000)
                    if not jpeg.startswith(b"\xff\xd8"):
                        raise ValueError("invalid JPEG")
                    with self.lock:
                        self.sequence += 1
                        self.jpeg = jpeg
                        self.updated_monotonic = time.monotonic()
                        self.error = None
                except Exception as exc:
                    with self.lock:
                        self.error = f"cached JPEG source failed: {exc}"
                self.stop_event.wait(0.25)
            return
        if is_http_stream(self.device):
            while not self.stop_event.is_set():
                try:
                    with urlopen(self.device, timeout=5) as stream:
                        for jpeg in mjpeg_jpegs(stream, self.stop_event):
                            with self.lock:
                                self.sequence += 1
                                self.jpeg = jpeg
                                self.updated_monotonic = time.monotonic()
                                self.error = None
                    if not self.stop_event.is_set():
                        with self.lock:
                            self.error = "MJPEG stream ended"
                except Exception as exc:
                    with self.lock:
                        self.error = f"MJPEG stream failed: {exc}"
                self.stop_event.wait(1)
            return
        while not self.stop_event.is_set():
            if is_http_stream(self.device):
                cap = cv2.VideoCapture(self.device)
            else:
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
    server_version = "MedicineYoloReview/1.1"

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
            snapshot["manual_capture_enabled"] = self.server.allow_manual_capture
            if self.angled_worker is not None:
                angled = self.angled_worker.snapshot()
                snapshot["angled_camera"] = angled
                snapshot["ok"] = snapshot["ok"] and angled["ok"]
            self._json(snapshot)
        elif path == "/detections.json":
            snapshot = self.worker.snapshot()
            self._json({"detections": snapshot["detections"], "sequence": snapshot["sequence"], "robot_enabled": False})
        elif path == "/manual-frame.json":
            snapshot, jpeg = self.worker.snapshot_with_jpeg()
            self._json({"snapshot": snapshot, "jpeg_base64": None if jpeg is None else base64.b64encode(jpeg).decode("ascii")})
        elif path == "/stream.mjpg":
            self._stream(self.worker)
        elif path == "/angled.mjpg" and self.angled_worker is not None:
            self._stream(self.angled_worker)
        else:
            self._json({"detail": "Not Found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path not in ("/api/manual-capture", "/api/command-preview"):
            self._json({"detail": "No robot-control endpoint"}, HTTPStatus.METHOD_NOT_ALLOWED)
            return
        if path == "/api/manual-capture" and not self.server.allow_manual_capture:
            self._json({"error": "manual capture is disabled", "robot_enabled": False},
                       HTTPStatus.FORBIDDEN)
            return
        try:
            if self.headers.get_content_type() != "application/json":
                raise ValueError("application/json is required")
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 1024:
                raise ValueError("request body size is invalid")
            payload = json.loads(self.rfile.read(length))
            if path == "/api/command-preview":
                if not isinstance(payload, dict) or not isinstance(payload.get("command"), str):
                    raise ValueError("command text is required")
                assignments = parse_command(payload["command"])
                result = decide_fixed_slot_command(
                    self.worker.snapshot(), assignments, self.server.fixed_slots
                )
                self._json(result)
                return
            if not isinstance(payload, dict) or payload.get("identity_confirmed") is not True:
                raise ValueError("human A/B/C identity confirmation is required")
            pixel = payload.get("pixel")
            if not isinstance(pixel, list) or len(pixel) != 2:
                raise ValueError("pixel must be [x, y]")
            saved = self.worker.save_manual_capture(
                self.server.manual_capture_root, self.server.manual_rules,
                label=payload.get("label"), sequence=payload.get("sequence"), pixel=tuple(pixel)
            )
            self._json(saved)
        except (ValueError, OSError, TypeError, json.JSONDecodeError) as error:
            self._json({"error": str(error), "robot_enabled": False}, HTTPStatus.BAD_REQUEST)

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
    parser.add_argument("--manual-capture-root", type=Path,
                        default=Path(".local/medicine-manual-captures"),
                        help="local Git-ignored folder for human-labeled raw JPEG review candidates")
    parser.add_argument("--allow-manual-capture", action="store_true",
                        help="opt in to local-only manual JPEG saving; does not enable robot control")
    parser.add_argument("--fixed-slots", type=Path, default=DEFAULT_SLOTS,
                        help="provisional fixed-layout slot ranges for read-only command preview")
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
    server.manual_capture_root = args.manual_capture_root
    server.manual_rules = validate_rules(json.loads(DEFAULT_RULES.read_text(encoding="utf-8")))
    server.fixed_slots = validate_slots(json.loads(args.fixed_slots.read_text(encoding="utf-8")))
    server.allow_manual_capture = args.allow_manual_capture
    angled_worker = PreviewWorker(args.angled_device, fourcc=args.angled_fourcc) if args.angled_device else None
    server.angled_worker = angled_worker
    worker.start()
    if angled_worker is not None:
        angled_worker.start()
    source = args.raw_rgb_command or args.device
    print(f"ROBOT_DISABLED http://{args.host}:{args.port} source={source} "
          f"manual_capture={args.allow_manual_capture}", flush=True)
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
