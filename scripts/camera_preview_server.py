#!/usr/bin/env python3
"""Persistent MJPEG preview for the SO-101 overhead cameras."""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import cv2
import numpy as np

from medicine_review_web import MedicineReviewStore


class FrameStore:
    def __init__(self, label: str) -> None:
        self.label = label
        self._condition = threading.Condition()
        self.jpeg: bytes | None = None
        self.updated_at = 0.0
        self.frames = 0
        self.error: str | None = "starting"

    def update(self, jpeg: bytes) -> None:
        with self._condition:
            self.jpeg = jpeg
            self.updated_at = time.monotonic()
            self.frames += 1
            self.error = None
            self._condition.notify_all()

    def fail(self, message: str) -> None:
        with self._condition:
            self.error = message
            self._condition.notify_all()

    def wait_for_frame(self, last_frames: int, timeout: float = 2.0) -> tuple[bytes | None, int]:
        with self._condition:
            if self.frames == last_frames:
                self._condition.wait(timeout)
            return self.jpeg, self.frames

    def status(self) -> dict[str, object]:
        with self._condition:
            age = None if not self.updated_at else round(time.monotonic() - self.updated_at, 3)
            return {
                "label": self.label,
                "ok": age is not None and age < 5.0,
                "frames": self.frames,
                "age_seconds": age,
                "error": self.error,
            }

    def snapshot(self, max_age: float = 2.0) -> bytes:
        with self._condition:
            age = None if not self.updated_at else time.monotonic() - self.updated_at
            if self.jpeg is None or age is None or age > max_age:
                raise RuntimeError("fresh camera frame is unavailable")
            return bytes(self.jpeg)


def encode_jpeg(frame: np.ndarray) -> bytes | None:
    ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 82])
    return encoded.tobytes() if ok else None


def read_exact(stream, size: int) -> bytes | None:
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        chunk = stream.read(remaining)
        if not chunk:
            return None
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def run_astra(store: FrameStore, stop_event: threading.Event, binary: str) -> None:
    frame_bytes = 640 * 480 * 3
    while not stop_event.is_set():
        environment = os.environ.copy()
        environment["OPENNI2_REDIST"] = "/opt/orbbec-openni2"
        old_library_path = environment.get("LD_LIBRARY_PATH")
        environment["LD_LIBRARY_PATH"] = "/opt/orbbec-openni2" + (
            f":{old_library_path}" if old_library_path else ""
        )
        process = None
        try:
            process = subprocess.Popen([binary], stdout=subprocess.PIPE, env=environment)
            assert process.stdout is not None
            while not stop_event.is_set():
                raw = read_exact(process.stdout, frame_bytes)
                if raw is None:
                    raise RuntimeError(f"frame pipe ended (exit={process.poll()})")
                rgb = np.frombuffer(raw, dtype=np.uint8).reshape((480, 640, 3))
                jpeg = encode_jpeg(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
                if jpeg is not None:
                    store.update(jpeg)
        except Exception as error:  # service must recover from camera reconnects
            store.fail(str(error))
        finally:
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
        stop_event.wait(2.0)


def video_index(device: str) -> int:
    resolved = os.path.realpath(device)
    match = re.search(r"video(\d+)$", resolved)
    if match:
        return int(match.group(1))
    return int(device)


def run_realsense(store: FrameStore, stop_event: threading.Event, device: str) -> None:
    while not stop_event.is_set():
        capture = cv2.VideoCapture(video_index(device), cv2.CAP_V4L2)
        capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"YUYV"))
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        capture.set(cv2.CAP_PROP_FPS, 30)
        if not capture.isOpened():
            store.fail(f"cannot open {device}")
            capture.release()
            stop_event.wait(2.0)
            continue
        failures = 0
        while not stop_event.is_set():
            ok, frame = capture.read()
            if not ok:
                failures += 1
                store.fail(f"frame read failed ({failures})")
                if failures >= 10:
                    break
                continue
            failures = 0
            jpeg = encode_jpeg(frame)
            if jpeg is not None:
                store.update(jpeg)
        capture.release()
        stop_event.wait(1.0)


PAGE = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SO-101 Vision Console</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#101215;color:#f1f3f5;font-family:system-ui,sans-serif}header{padding:14px 20px;background:#191c20;position:sticky;top:0;z-index:2}
h1{font-size:20px;margin:0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:12px;padding:12px}
figure,.panel,.card{margin:0;background:#1d2126;border:1px solid #30363d;border-radius:10px;overflow:hidden}figcaption,.panel h2{padding:10px 12px;font-weight:650;margin:0;font-size:16px}
img{display:block;width:100%;height:auto;background:#000}.panel{margin:0 12px 12px;padding:14px}.controls{display:flex;gap:8px;flex-wrap:wrap}button{border:0;border-radius:7px;padding:10px 14px;font-weight:700;cursor:pointer}.positive{background:#2f9e44;color:white}.negative{background:#1971c2;color:white}.approve{background:#37b24d;color:white}.exclude{background:#495057;color:white}.copy{background:#7048e8;color:white}.stats{display:flex;gap:12px;flex-wrap:wrap;margin:12px 0;color:#ced4da}.message{min-height:24px;color:#ffd43b}.reviews{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px}.card img{aspect-ratio:4/3;object-fit:contain}.card .body{padding:10px}.badge{display:inline-block;padding:3px 7px;border-radius:999px;background:#343a40;font-size:12px}.blocked{color:#ff8787}.note{font-size:13px;color:#adb5bd}.joint-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px;margin:12px 0}.joint{background:#15181c;border:1px solid #30363d;border-radius:7px;padding:9px}.joint b{display:block;color:#adb5bd;font-size:12px}.joint span{font-family:ui-monospace,monospace;font-size:16px}.ok{color:#69db7c}.waiting{color:#ffd43b}.error{color:#ff8787}
</style></head><body><header><h1>SO-101 비전 콘솔 · 카메라 전용</h1></header><main class="grid">
<figure><figcaption>천장 정면 · Orbbec Astra</figcaption><img src="/astra.mjpg" alt="Astra overhead preview"></figure>
<figure><figcaption>천장 사선 · Intel RealSense D435</figcaption><img src="/realsense.mjpg" alt="RealSense angled preview"></figure>
</main><section class="panel"><h2>로봇 좌표 teach 모니터 · 읽기 전용</h2><p class="note">LeLab의 기존 WebSocket 방송만 구독합니다. 이 화면은 시리얼 포트를 열거나 텔레오퍼레이션을 시작·정지하지 않습니다. 실제 teach 전 TCP offset과 World 기준점을 별도로 확정해야 합니다.</p><div id="jointStatus" class="message waiting">WebSocket 연결 중…</div><div id="jointGrid" class="joint-grid"></div><div class="controls"><button class="copy" onclick="copyJointSample()">현재 관절값 JSON 복사</button></div><p id="jointMessage" class="note"></p></section><section class="panel"><h2>약통 표본 촬영 · 학습 후보</h2><p class="note">수집이 종료된 기존 학습 후보 큐입니다. 추가 촬영은 아래의 독립 평가 큐를 사용하세요.</p><div class="controls"><button class="positive" disabled title="학습 후보 수집 종료">학습 양성 수집 종료</button><button class="negative" disabled title="학습 후보 수집 종료">학습 음성 수집 종료</button></div><div id="message" class="message">아래 ‘평가 양성 촬영’과 ‘평가 음성 촬영’만 사용하세요.</div><div id="stats" class="stats"></div><div id="reviews" class="reviews"></div></section><section class="panel"><h2>독립 평가 표본 촬영 · 별도 큐</h2><p class="note">학습 후보와 섞이지 않습니다. 양성은 기존 학습 박스 중심과 3px 미만일 때만 중복으로 차단됩니다. 위치·회전·자세를 바꾸고 손을 화면 밖으로 뺀 뒤 한 장씩 촬영하세요.</p><div class="controls"><button class="positive" onclick="captureEval('positive')">평가 양성 촬영</button><button class="negative" onclick="captureEval('negative')">평가 음성 촬영</button></div><div id="evalMessage" class="message"></div><div id="evalStats" class="stats"></div><div id="evalReviews" class="reviews"></div></section>
<script>
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const jointOrder=['Rotation','Pitch','Elbow','Wrist_Pitch','Wrist_Roll','Jaw'];let latestJointSample=null,jointSocket=null,jointRetry=null;
function setJointStatus(text,kind){jointStatus.textContent=text;jointStatus.className='message '+kind}
function renderJoints(joints){jointGrid.innerHTML=jointOrder.map(name=>`<div class="joint"><b>${esc(name)}</b><span>${Number(joints[name]).toFixed(5)} rad</span></div>`).join('')}
function connectJointStream(){clearTimeout(jointRetry);const scheme=location.protocol==='https:'?'wss':'ws';jointSocket=new WebSocket(`${scheme}://${location.hostname}:8000/ws/joint-data`);jointSocket.onopen=()=>setJointStatus('WebSocket 연결됨 · 텔레오퍼레이션 관절 방송 대기','waiting');jointSocket.onmessage=event=>{try{const data=JSON.parse(event.data);if(data.type!=='joint_update'||!data.joints)return;latestJointSample={unit:'rad',joints:data.joints,source:'LeLab /ws/joint-data',captured_at_unix:data.timestamp,use_for_robot_world_fit:false,note:'TCP/world point not attached'};renderJoints(data.joints);setJointStatus('관절 방송 수신 중 · 시리얼 추가 접근 없음','ok')}catch(e){setJointStatus('관절 메시지 해석 오류: '+e.message,'error')}};jointSocket.onerror=()=>setJointStatus('WebSocket 오류 · LeLab 8000 상태 확인 필요','error');jointSocket.onclose=()=>{setJointStatus('WebSocket 재연결 대기','waiting');jointRetry=setTimeout(connectJointStream,2000)}}
async function copyJointSample(){if(!latestJointSample){jointMessage.textContent='아직 수신된 관절값이 없습니다. 텔레오퍼레이션이 활성일 때 방송됩니다.';return}try{await navigator.clipboard.writeText(JSON.stringify(latestJointSample,null,2));jointMessage.textContent='현재 관절값을 복사했습니다. World point/TCP가 없으므로 transform fit에는 바로 사용하지 마세요.'}catch(e){jointMessage.textContent='복사 실패: '+e.message}}
async function api(url,options){const r=await fetch(url,options);const d=await r.json();if(!r.ok)throw new Error(d.error||r.statusText);return d}
async function captureItem(expected){message.textContent='촬영 중…';try{const d=await api('/api/capture',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({expected})});message.textContent=`저장됨: ${d.stem} · ${d.status}`;await refresh()}catch(e){message.textContent=e.message}}
async function decide(stem,decision){try{await api('/api/review/'+encodeURIComponent(stem),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({decision,note:'web review'})});await refresh()}catch(e){message.textContent=e.message}}
async function refresh(){try{const d=await api('/api/review');stats.innerHTML=Object.entries(d.counts).map(([k,v])=>`<span><b>${esc(k)}</b> ${v}</span>`).join('');reviews.innerHTML=d.items.map(x=>`<article class="card"><img src="/review/overlay/${encodeURIComponent(x.stem)}.png?${Date.now()}" alt="review"><div class="body"><span class="badge ${x.status==='blocked'?'blocked':''}">${esc(x.status)}</span> <b>${esc(x.expected)}</b><p>${esc((x.block_reasons||[]).join(', ')||'자동 검사 통과 · 사람 검토 필요')}</p>${x.status==='pending_review'?`<div class="controls"><button class="approve" onclick="decide('${x.stem}','approve')">승인</button><button class="exclude" onclick="decide('${x.stem}','exclude')">제외</button></div>`:x.status==='blocked'?`<button class="exclude" onclick="decide('${x.stem}','exclude')">제외 처리</button>`:''}</div></article>`).join('')}catch(e){message.textContent=e.message}}
async function captureEval(expected){evalMessage.textContent='평가 촬영 중…';try{const d=await api('/api/eval/capture',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({expected})});evalMessage.textContent=`평가 저장됨: ${d.stem} · ${d.status}`;await refreshEval()}catch(e){evalMessage.textContent=e.message}}
async function decideEval(stem,decision){try{await api('/api/eval/review/'+encodeURIComponent(stem),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({decision,note:'independent evaluation web review'})});await refreshEval()}catch(e){evalMessage.textContent=e.message}}
async function refreshEval(){try{const d=await api('/api/eval/review');evalStats.innerHTML=Object.entries(d.counts).map(([k,v])=>`<span><b>${esc(k)}</b> ${v}</span>`).join('');evalReviews.innerHTML=d.items.map(x=>`<article class="card"><img src="/eval/overlay/${encodeURIComponent(x.stem)}.png?${Date.now()}" alt="evaluation review"><div class="body"><span class="badge ${x.status==='blocked'?'blocked':''}">${esc(x.status)}</span> <b>${esc(x.expected)}</b><p>${esc((x.block_reasons||[]).join(', ')||'자동 검사 통과 · 사람 검토 필요')}</p>${x.status==='pending_review'?`<div class="controls"><button class="approve" onclick="decideEval('${x.stem}','approve')">평가 승인</button><button class="exclude" onclick="decideEval('${x.stem}','exclude')">제외</button></div>`:x.status==='blocked'?`<button class="exclude" onclick="decideEval('${x.stem}','exclude')">제외 처리</button>`:''}</div></article>`).join('')}catch(e){evalMessage.textContent=e.message}}
connectJointStream();refresh();refreshEval();setInterval(refresh,5000);setInterval(refreshEval,5000);
</script></body></html>""".encode("utf-8")


class PreviewServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, handler, stores: dict[str, FrameStore], review_store: MedicineReviewStore,
                 eval_store: MedicineReviewStore):
        super().__init__(address, handler)
        self.stores = stores
        self.review_store = review_store
        self.eval_store = eval_store


class Handler(BaseHTTPRequestHandler):
    server: PreviewServer

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"{self.client_address[0]} - {fmt % args}", flush=True)

    def send_json(self, value: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> dict:
        if self.headers.get_content_type() != "application/json":
            raise ValueError("Content-Type은 application/json이어야 합니다")
        length = int(self.headers.get("Content-Length", "0"))
        if not 0 < length <= 4096:
            raise ValueError("잘못된 요청 크기입니다")
        value = json.loads(self.rfile.read(length))
        if not isinstance(value, dict):
            raise ValueError("JSON object가 필요합니다")
        return value

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(PAGE)))
            self.end_headers()
            self.wfile.write(PAGE)
            return
        if path == "/health":
            status = {name: store.status() for name, store in self.server.stores.items()}
            body = json.dumps(status, ensure_ascii=False).encode("utf-8")
            code = HTTPStatus.OK if all(item["ok"] for item in status.values()) else HTTPStatus.SERVICE_UNAVAILABLE
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/api/review":
            self.send_json(self.server.review_store.summary())
            return
        if path == "/api/eval/review":
            self.send_json(self.server.eval_store.summary())
            return
        match = re.fullmatch(r"/(review|eval)/(image|overlay)/([A-Za-z0-9_-]+)\.png", path)
        if match:
            store = self.server.review_store if match.group(1) == "review" else self.server.eval_store
            folder = "images" if match.group(2) == "image" else "overlays"
            image_path = store.root / folder / f"{match.group(3)}.png"
            if not image_path.is_file():
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            body = image_path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "image/png")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        routes = {"/astra.mjpg": "astra", "/realsense.mjpg": "realsense"}
        camera = routes.get(path)
        if camera is None:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.end_headers()
        frames = -1
        try:
            while True:
                jpeg, frames = self.server.stores[camera].wait_for_frame(frames)
                if jpeg is None:
                    continue
                self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n")
                self.wfile.write(f"Content-Length: {len(jpeg)}\r\n\r\n".encode("ascii"))
                self.wfile.write(jpeg)
                self.wfile.write(b"\r\n")
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            payload = self.read_json()
            if path == "/api/capture":
                jpeg = self.server.stores["astra"].snapshot()
                self.send_json(self.server.review_store.capture(jpeg, payload.get("expected")))
                return
            if path == "/api/eval/capture":
                jpeg = self.server.stores["astra"].snapshot()
                self.send_json(self.server.eval_store.capture(jpeg, payload.get("expected")))
                return
            match = re.fullmatch(r"/api/review/([A-Za-z0-9_-]+)", path)
            if match:
                result = self.server.review_store.decide(
                    match.group(1), payload.get("decision"), payload.get("note", "")
                )
                self.send_json(result)
                return
            match = re.fullmatch(r"/api/eval/review/([A-Za-z0-9_-]+)", path)
            if match:
                result = self.server.eval_store.decide(
                    match.group(1), payload.get("decision"), payload.get("note", "")
                )
                self.send_json(result)
                return
            self.send_error(HTTPStatus.NOT_FOUND)
        except FileNotFoundError as error:
            self.send_json({"error": f"항목을 찾을 수 없습니다: {error}"}, HTTPStatus.NOT_FOUND)
        except (ValueError, RuntimeError, OSError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", default=8010, type=int)
    parser.add_argument("--astra-pipe", default="/opt/orbbec-openni2/bin/orbbec-rgb-pipe")
    parser.add_argument(
        "--review-root",
        type=Path,
        default=Path("/home/jetson3/so101-medicine-bootstrap/web-review-queue-v1"),
    )
    parser.add_argument(
        "--reference-positive",
        type=Path,
        default=Path("/home/jetson3/so101-medicine-bootstrap/provisional-fullframe-v2"),
    )
    parser.add_argument(
        "--eval-root",
        type=Path,
        default=Path("/home/jetson3/so101-medicine-bootstrap/evaluation-web-v1"),
    )
    parser.add_argument(
        "--eval-reference-positive",
        type=Path,
        default=Path("/home/jetson3/so101-medicine-bootstrap/training-candidates-audit-v1"),
    )
    parser.add_argument(
        "--realsense-device",
        default="/dev/v4l/by-id/usb-Intel_R__RealSense_TM__Depth_Camera_435_Intel_R__RealSense_TM__Depth_Camera_435_236223023645-video-index0",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    stop_event = threading.Event()
    stores = {"astra": FrameStore("천장 정면 Astra"), "realsense": FrameStore("천장 사선 RealSense")}
    workers = [
        threading.Thread(target=run_astra, args=(stores["astra"], stop_event, args.astra_pipe), daemon=True),
        threading.Thread(target=run_realsense, args=(stores["realsense"], stop_event, args.realsense_device), daemon=True),
    ]
    for worker in workers:
        worker.start()

    review_store = MedicineReviewStore(args.review_root, args.reference_positive)
    eval_store = MedicineReviewStore(
        args.eval_root,
        args.eval_reference_positive,
        near_duplicate_px=3.0,
    )
    server = PreviewServer((args.host, args.port), Handler, stores, review_store, eval_store)

    def stop(_signum, _frame) -> None:
        stop_event.set()
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        stop_event.set()
        server.server_close()
        for worker in workers:
            worker.join(timeout=3)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
