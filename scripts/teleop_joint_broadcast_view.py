"""Read-only live LeLab joint-broadcast display; never opens a motor port."""

from __future__ import annotations

import json
import math
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import websocket


SOURCE = "ws://192.168.50.20:8000/ws/joint-data"
TARGETS = {
    "Rotation": 11.74, "Pitch": -22.33, "Elbow": 32.44,
    "Wrist_Pitch": 5.54, "Wrist_Roll": -20.40,
}
latest = {"received": 0.0, "degrees": {}, "jaw_rad": None, "error": "waiting for broadcast"}
guard = threading.Lock()


def receive_forever() -> None:
    while True:
        try:
            ws = websocket.create_connection(SOURCE, timeout=5)
            try:
                while True:
                    message = json.loads(ws.recv())
                    joints = message.get("joints", {})
                    if not all(name in joints for name in TARGETS):
                        continue
                    degrees = {name: math.degrees(float(joints[name])) for name in TARGETS}
                    jaw = joints.get("Jaw")
                    with guard:
                        latest.update(received=time.time(), degrees=degrees,
                                      jaw_rad=jaw, error=None)
            finally:
                ws.close()
        except Exception as error:
            with guard:
                latest["error"] = type(error).__name__
            time.sleep(0.5)


PAGE = """<!doctype html><html lang=ko><meta charset=utf-8>
<title>SO-101 관절 방송 · 읽기 전용</title>
<style>body{font:20px system-ui;margin:2rem;max-width:950px}table{border-collapse:collapse;width:100%}
td,th{padding:.6rem;border-bottom:1px solid #ddd;text-align:right}td:first-child,th:first-child{text-align:left}
.ok{color:#06723c}.bad{color:#b00020}.note{background:#fff1d4;padding:1rem}</style>
<h1>SO-101 현재 관절 · safe_start 비교</h1>
<p class=note>LeLab 방송을 읽기만 합니다. USB·모터·토크에 접근하지 않습니다.
방송은 실제 제어 명령이 아니며, 최종 자세는 LeLab 종료 뒤 새 follower 피드백으로 다시 확인해야 합니다.</p>
<p id=status>수신 대기 중</p><table><thead><tr><th>관절</th><th>현재 °</th><th>목표 °</th><th>차이 °</th></tr></thead><tbody id=rows></tbody></table>
<p id=jaw></p>
<script>
const names=['Rotation','Pitch','Elbow','Wrist_Pitch','Wrist_Roll'];
const labels=['Pan','Lift','Elbow','Wrist Flex','Wrist Roll'];
const target=[11.74,-22.33,32.44,5.54,-20.40];
async function refresh(){try{let r=await fetch('/api',{cache:'no-store'}),d=await r.json();
let age=Date.now()/1000-d.received;
document.getElementById('status').textContent=d.error||age>2?'방송 지연/끊김 — 움직임 중단 후 확인 필요':'방송 신선함 '+age.toFixed(1)+'초';
document.getElementById('status').className=d.error||age>2?'bad':'ok';
document.getElementById('rows').innerHTML=names.map((n,i)=>{let v=d.degrees[n],e=v-target[i],ok=Math.abs(e)<=3;
return `<tr><td>${labels[i]}</td><td>${v.toFixed(2)}</td><td>${target[i].toFixed(2)}</td><td class=${ok?'ok':'bad'}>${e>=0?'+':''}${e.toFixed(2)}</td></tr>`}).join('');
document.getElementById('jaw').textContent='Jaw 방송: '+Number(d.jaw_rad).toFixed(3)+' rad (gripper %가 아님)';
}catch(e){document.getElementById('status').textContent='방송 확인 실패';document.getElementById('status').className='bad'}}
setInterval(refresh,250);refresh();</script></html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api":
            with guard:
                data = dict(latest)
            body = json.dumps(data).encode()
            content_type = "application/json"
        elif self.path == "/":
            body = PAGE.encode()
            content_type = "text/html; charset=utf-8"
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    threading.Thread(target=receive_forever, daemon=True).start()
    server = HTTPServer(("127.0.0.1", 8032), Handler)
    print("READ_ONLY_JOINT_VIEW_READY http://127.0.0.1:8032/", flush=True)
    try:
        server.serve_forever(poll_interval=0.2)
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
