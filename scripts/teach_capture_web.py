#!/usr/bin/env python3
"""Read-only, receive-time paired camera/joint capture for SO-101 touch QA.

This process never opens robot serial devices, starts teleoperation, or changes
camera configuration. JPEGs and joint broadcasts are stored only under an
explicit local output directory, which should be Git-ignored.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import threading
import time
import urllib.error
import urllib.request
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


JOINT_NAMES = ("Rotation", "Pitch", "Elbow", "Wrist_Pitch", "Wrist_Roll", "Jaw")
POINT_NAMES = frozenset({"P1", "P2", "P3", "P4", "P5", "P6", "H1", "H2"})
CAMERAS = {"ceiling": 8, "oblique": 4}
MAX_JPEG_BYTES = 2_000_000
MAX_FRAME_AGE_NS = 750_000_000
MAX_JOINT_AGE_NS = 400_000_000
MAX_PAIR_GAP_NS = 250_000_000


@dataclass(frozen=True)
class Frame:
    jpeg: bytes
    received_ns: int
    received_unix_ns: int


@dataclass(frozen=True)
class Joint:
    joints: dict[str, float]
    source_unix: float
    received_ns: int
    received_unix_ns: int


def iter_jpegs(chunks):
    """Recover complete JPEGs across arbitrary MJPEG chunk boundaries."""
    buffer = bytearray()
    for chunk in chunks:
        if not chunk:
            break
        buffer.extend(chunk)
        while True:
            start = buffer.find(b"\xff\xd8")
            if start < 0:
                # A chunk may end at the first byte of the next JPEG marker.
                keep_ff = bool(buffer and buffer[-1] == 0xFF)
                buffer.clear()
                if keep_ff:
                    buffer.append(0xFF)
                break
            end = buffer.find(b"\xff\xd9", start + 2)
            if end < 0:
                if start:
                    del buffer[:start]
                if len(buffer) > MAX_JPEG_BYTES:
                    buffer.clear()
                break
            jpeg = bytes(buffer[start : end + 2])
            del buffer[: end + 2]
            if len(jpeg) <= MAX_JPEG_BYTES:
                yield jpeg


def parse_joint(message: object, received_ns: int, received_unix_ns: int) -> Joint | None:
    if not isinstance(message, dict) or message.get("type") != "joint_update":
        return None
    values = message.get("joints")
    timestamp = message.get("timestamp")
    if not isinstance(values, dict) or not isinstance(timestamp, (float, int)):
        return None
    try:
        joints = {name: float(values[name]) for name in JOINT_NAMES}
    except (KeyError, ValueError, TypeError):
        return None
    if not all(math.isfinite(value) for value in (*joints.values(), float(timestamp))):
        return None
    return Joint(joints, float(timestamp), received_ns, received_unix_ns)


class CaptureState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.frames: dict[str, deque[Frame]] = {name: deque(maxlen=90) for name in CAMERAS}
        self.joints: deque[Joint] = deque(maxlen=180)
        self.errors: dict[str, str | None] = {name: "connecting" for name in (*CAMERAS, "joints")}

    def add_frame(self, name: str, jpeg: bytes, received_ns: int | None = None,
                  received_unix_ns: int | None = None) -> None:
        if not (jpeg.startswith(b"\xff\xd8") and jpeg.endswith(b"\xff\xd9")):
            raise ValueError("incomplete JPEG")
        frame = Frame(jpeg, received_ns or time.monotonic_ns(), received_unix_ns or time.time_ns())
        with self.lock:
            self.frames[name].append(frame)
            self.errors[name] = None

    def add_joint(self, message: object, received_ns: int | None = None,
                  received_unix_ns: int | None = None) -> bool:
        joint = parse_joint(message, received_ns or time.monotonic_ns(), received_unix_ns or time.time_ns())
        if joint is None:
            return False
        with self.lock:
            self.joints.append(joint)
            self.errors["joints"] = None
        return True

    def fail(self, name: str, error: Exception | str) -> None:
        with self.lock:
            self.errors[name] = str(error)[:180]

    def connected(self, name: str) -> None:
        with self.lock:
            self.errors[name] = None

    def latest_frame(self, name: str, now_ns: int | None = None) -> Frame:
        now_ns = now_ns or time.monotonic_ns()
        with self.lock:
            frame = self.frames[name][-1] if self.frames[name] else None
        if frame is None or now_ns - frame.received_ns > MAX_FRAME_AGE_NS:
            raise ValueError(f"{name} frame is unavailable or stale")
        return frame

    def status(self, now_ns: int | None = None) -> dict:
        now_ns = now_ns or time.monotonic_ns()
        with self.lock:
            frame_ages = {
                name: None if not frames else round((now_ns - frames[-1].received_ns) / 1e6, 1)
                for name, frames in self.frames.items()
            }
            joint_age = None if not self.joints else round((now_ns - self.joints[-1].received_ns) / 1e6, 1)
            errors = dict(self.errors)
        return {
            "camera_age_ms": frame_ages,
            "joint_age_ms": joint_age,
            "errors": errors,
            "robot_control": False,
            "synchronization": "receive-time approximation; not camera exposure synchronization",
        }

    def select(self, point: str, now_ns: int | None = None) -> dict:
        if not isinstance(point, str) or point not in POINT_NAMES:
            raise ValueError("point must be P1–P6 or H1–H2")
        now_ns = now_ns or time.monotonic_ns()
        with self.lock:
            recent = [joint for joint in self.joints if now_ns - joint.received_ns <= 1_500_000_000]
            joints = recent[-15:]
            frames = {name: tuple(samples) for name, samples in self.frames.items()}
        if len(joints) < 15 or now_ns - joints[-1].received_ns > MAX_JOINT_AGE_NS:
            raise ValueError("15 fresh joint broadcasts are required while teleoperation is active")
        if len({joint.source_unix for joint in joints}) != len(joints):
            raise ValueError("joint timestamps are not unique")
        means = {name: statistics.mean(joint.joints[name] for joint in joints) for name in JOINT_NAMES}
        stds = {name: statistics.pstdev(joint.joints[name] for joint in joints) for name in JOINT_NAMES}
        if max(stds.values()) > 0.01 or max(joint.joints["Jaw"] for joint in joints) - min(
            joint.joints["Jaw"] for joint in joints
        ) > 0.02:
            raise ValueError("joint posture is not stable")
        target = joints[-1].received_ns
        selected: dict[str, Frame] = {}
        gaps: dict[str, float] = {}
        for name, samples in frames.items():
            if not samples:
                raise ValueError(f"{name} frame is unavailable")
            frame = min(samples, key=lambda item: abs(item.received_ns - target))
            gap = abs(frame.received_ns - target)
            if now_ns - frame.received_ns > MAX_FRAME_AGE_NS or gap > MAX_PAIR_GAP_NS:
                raise ValueError(f"{name} frame is not close enough to the joint sample")
            selected[name] = frame
            gaps[name] = round(gap / 1e6, 1)
        return {
            "point": point,
            "joints": joints,
            "frames": selected,
            "joint_mean_rad": means,
            "joint_max_std_rad": max(stds.values()),
            "frame_joint_receive_gap_ms": gaps,
        }


def lelab_teleop_active(base_url: str) -> bool:
    with urllib.request.urlopen(base_url + "/teleoperation-status", timeout=2) as response:
        result = json.load(response)
    return result.get("teleoperation_active") is True


def save_capture(root: Path, selected: dict) -> dict:
    stem = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ") + "_" + uuid.uuid4().hex[:8]
    folder = root / stem
    folder.mkdir(parents=True, exist_ok=False)
    images = {}
    for name, frame in selected["frames"].items():
        filename = f"{name}.jpg"
        (folder / filename).write_bytes(frame.jpeg)
        images[name] = {
            "filename": filename,
            "sha256": hashlib.sha256(frame.jpeg).hexdigest(),
            "received_unix_ns": frame.received_unix_ns,
        }
    metadata = {
        "schema_version": 1,
        "point": selected["point"],
        "images": images,
        "joint_samples": [
            {"joints_rad": joint.joints, "source_unix": joint.source_unix,
             "received_unix_ns": joint.received_unix_ns}
            for joint in selected["joints"]
        ],
        "joint_mean_rad": selected["joint_mean_rad"],
        "joint_max_std_rad": selected["joint_max_std_rad"],
        "frame_joint_receive_gap_ms": selected["frame_joint_receive_gap_ms"],
        "contact": "user asserted; visual review pending",
        "synchronization": "server receive-time approximation; exposure timestamps unavailable",
        "use_for_robot_world_fit": False,
        "robot_enabled": False,
        "motion_authorized": False,
    }
    (folder / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
    return {"stem": stem, "point": selected["point"], "folder": str(folder),
            "frame_joint_receive_gap_ms": selected["frame_joint_receive_gap_ms"],
            "joint_max_std_rad": selected["joint_max_std_rad"]}


PAGE = """<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>SO-101 접촉 증거 캡처</title>
<style>body{margin:0;background:#101820;color:#eef5fb;font-family:system-ui,sans-serif}main{max-width:1300px;margin:auto;padding:20px}h1{margin:0 0 8px;font-size:24px}.warn{background:#4b2a20;padding:12px;border-radius:8px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(350px,1fr));gap:12px}figure{margin:0}img{width:100%;background:#000;aspect-ratio:4/3;object-fit:contain;border:1px solid #425466;border-radius:8px}figcaption{margin:8px 0}section{background:#1b2936;border-radius:8px;padding:16px;margin-top:16px}button,select{padding:10px;font-size:16px;border-radius:6px}button{background:#36b37e;color:#081b13;border:0;font-weight:700}button:disabled{opacity:.4}pre{white-space:pre-wrap}label{display:block;margin:12px 0}</style></head><body><main>
<h1>SO-101 접촉 증거 캡처 · 읽기 전용</h1>
<p class="warn">로봇 시작·정지 기능은 없습니다. 현장 안전 확인과 별도 승인 후 기존 LeLab에서만 텔레옵을 조작하세요. 이 페이지의 사진·관절값은 검수 전 로봇 좌표에 사용하지 않습니다.</p>
<div class="grid"><figure><figcaption>천장 정면</figcaption><img id="ceiling" alt="ceiling"></figure><figure><figcaption>천장 사선</figcaption><img id="oblique" alt="oblique"></figure></div>
<section><h2>접촉 시점 저장</h2><p>표시한 손가락의 단단한 끝이 X 중심에 가볍게 닿고 완전히 멈춘 뒤 선택하세요. 두 영상과 최근 관절 방송 15개를 함께 보존합니다.</p><label>지점 <select id="point"><option>P1</option><option>P2</option><option>P3</option><option>P4</option><option>P5</option><option>P6</option><option>H1</option><option>H2</option></select></label><label><input id="confirmed" type="checkbox"> 현장에서 같은 플라스틱 끝의 실제 접촉과 안정 상태를 확인했습니다</label><button id="capture" onclick="capturePoint()">영상 + 관절값 저장</button><pre id="result"></pre></section>
<section><h2>수신 상태</h2><pre id="status">연결 중…</pre></section></main><script>
async function refresh(){for(const name of ['ceiling','oblique']){const image=document.getElementById(name);if(image.complete)image.src='/frame/'+name+'.jpg?t='+Date.now()}try{const r=await fetch('/api/status',{cache:'no-store'});document.getElementById('status').textContent=JSON.stringify(await r.json(),null,2)}catch(e){document.getElementById('status').textContent=String(e)}}
async function capturePoint(){const result=document.getElementById('result');if(!document.getElementById('confirmed').checked){result.textContent='현장 접촉 확인 체크가 필요합니다.';return}result.textContent='동시 자료 확인 중…';try{const r=await fetch('/api/capture',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({point:document.getElementById('point').value,contact_confirmed:true})});const d=await r.json();result.textContent=JSON.stringify(d,null,2)}catch(e){result.textContent=String(e)}}
refresh();setInterval(refresh,250);
</script></body></html>""".encode("utf-8")


class CaptureServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, state: CaptureState, output_root: Path, lelab_url: str):
        super().__init__(address, CaptureHandler)
        self.state = state
        self.output_root = output_root
        self.lelab_url = lelab_url


class CaptureHandler(BaseHTTPRequestHandler):
    server: CaptureServer

    def log_message(self, fmt: str, *args: object) -> None:
        return

    def send_bytes(self, body: bytes, content_type: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, value: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        self.send_bytes(json.dumps(value, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8", status)

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/":
            self.send_bytes(PAGE, "text/html; charset=utf-8")
        elif path == "/api/status":
            self.send_json(self.server.state.status())
        elif path in ("/frame/ceiling.jpg", "/frame/oblique.jpg"):
            name = path.split("/")[-1].split(".")[0]
            try:
                self.send_bytes(self.server.state.latest_frame(name).jpeg, "image/jpeg")
            except ValueError as error:
                self.send_json({"error": str(error)}, HTTPStatus.SERVICE_UNAVAILABLE)
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if urlsplit(self.path).path != "/api/capture":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            if self.headers.get_content_type() != "application/json":
                raise ValueError("application/json is required")
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 1024:
                raise ValueError("request body size is invalid")
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict) or payload.get("contact_confirmed") is not True:
                raise ValueError("user contact confirmation is required")
            if not lelab_teleop_active(self.server.lelab_url):
                raise ValueError("LeLab teleoperation is not active; capture refused")
            selected = self.server.state.select(payload.get("point"))
            self.send_json(save_capture(self.server.output_root, selected))
        except (ValueError, OSError, urllib.error.URLError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)


def camera_worker(state: CaptureState, name: str, base_url: str, stop: threading.Event) -> None:
    url = f"{base_url}/camera-preview/{CAMERAS[name]}"
    while not stop.is_set():
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                chunks = iter(lambda: response.read1(16_384), b"")
                for jpeg in iter_jpegs(chunks):
                    if stop.is_set():
                        return
                    state.add_frame(name, jpeg)
            state.fail(name, "camera stream closed")
        except (OSError, ValueError, urllib.error.URLError) as error:
            state.fail(name, error)
        stop.wait(2)


def joint_worker(state: CaptureState, base_url: str, stop: threading.Event) -> None:
    import websocket

    parts = urlsplit(base_url)
    ws_url = ("wss" if parts.scheme == "https" else "ws") + "://" + parts.netloc + "/ws/joint-data"
    while not stop.is_set():
        socket = None
        try:
            socket = websocket.create_connection(ws_url, timeout=3)
            state.connected("joints")
            while not stop.is_set():
                try:
                    message = socket.recv()
                except websocket.WebSocketTimeoutException:
                    continue
                if not message:
                    raise OSError("joint WebSocket closed")
                state.add_joint(json.loads(message))
        except (OSError, ValueError, websocket.WebSocketException, json.JSONDecodeError) as error:
            state.fail("joints", error)
        finally:
            if socket is not None:
                socket.close()
        stop.wait(2)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lelab-url", default="http://192.168.50.20:8000")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8030)
    parser.add_argument("--output-root", type=Path, default=Path(".local/teach-captures"))
    args = parser.parse_args()
    if args.host not in ("127.0.0.1", "::1"):
        parser.error("camera/joint evidence page must bind to loopback only")
    parts = urlsplit(args.lelab_url)
    if parts.scheme not in ("http", "https") or not parts.netloc or parts.path not in ("", "/"):
        parser.error("--lelab-url must be an HTTP(S) origin without a path")
    args.lelab_url = args.lelab_url.rstrip("/")
    args.output_root.mkdir(parents=True, exist_ok=True)
    state = CaptureState()
    stop = threading.Event()
    workers = [
        threading.Thread(target=camera_worker, args=(state, name, args.lelab_url, stop), daemon=True)
        for name in CAMERAS
    ]
    workers.append(threading.Thread(target=joint_worker, args=(state, args.lelab_url, stop), daemon=True))
    server = CaptureServer((args.host, args.port), state, args.output_root, args.lelab_url)
    for worker in workers:
        worker.start()
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        server.server_close()
        for worker in workers:
            worker.join(timeout=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
