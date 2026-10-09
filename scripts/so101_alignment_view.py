#!/usr/bin/env python3
"""Read-only live leader/follower joint alignment view for teleop preflight.

The viewer owns both serial ports exclusively and must be stopped before LeLab
teleoperation. It never invokes connect()/configure() on a robot or teleoperator,
and never writes a motor register or changes torque.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import signal
import termios
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from serial.tools import list_ports

from lerobot.robots.so_follower import SO101Follower, SO101FollowerConfig
from lerobot.teleoperators.so_leader import SO101Leader, SO101LeaderConfig


JOINTS = ("shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll")
EXPECTED_SERIALS = {"leader": "5AE6085272", "follower": "5AE6058306"}
PORTS = {"leader": "/dev/ttyACM1", "follower": "/dev/ttyACM0"}


def require_lelab_off() -> None:
    for endpoint, key in (
        ("teleoperation-status", "teleoperation_active"),
        ("recording-status", "recording_active"),
        ("inference-status", "inference_active"),
    ):
        with urllib.request.urlopen(f"http://127.0.0.1:8000/{endpoint}", timeout=2) as response:
            value = json.load(response)
        if value.get(key) is not False:
            raise RuntimeError(f"LeLab {endpoint} is not explicitly inactive")


def require_port_identities() -> None:
    observed = {port.device: port.serial_number for port in list_ports.comports()}
    for role, path in PORTS.items():
        if observed.get(path) != EXPECTED_SERIALS[role]:
            raise RuntimeError(f"{role} canonical serial identity mismatch at {path}")


def forbid_write(*_args, **_kwargs):
    raise RuntimeError("motor write/torque API forbidden in alignment viewer")


class Reader:
    def __init__(self):
        self.buses = {}
        devices = {
            "leader": SO101Leader(SO101LeaderConfig(port=PORTS["leader"], id="so-101")),
            "follower": SO101Follower(SO101FollowerConfig(port=PORTS["follower"], id="so-101")),
        }
        try:
            for role in ("leader", "follower"):
                bus = devices[role].bus
                for method in ("write", "sync_write", "enable_torque", "disable_torque"):
                    if hasattr(bus, method):
                        setattr(bus, method, forbid_write)
                bus.connect(handshake=False)
                self.buses[role] = bus
                fcntl.ioctl(bus.port_handler.ser.fileno(), termios.TIOCEXCL)
                if not bus.is_calibrated:
                    raise RuntimeError(f"{role} calibration is not loaded")
        except BaseException:
            self.close()
            raise

    def read(self) -> dict:
        require_lelab_off()
        rows = {}
        for role, bus in self.buses.items():
            raw = bus.sync_read("Present_Position", normalize=False, num_retry=0)
            by_id = {bus.motors[name].id: value for name, value in raw.items()}
            normalized = bus._normalize(by_id)
            rows[role] = {
                "raw": raw,
                "degree": {name: normalized[bus.motors[name].id] for name in raw},
            }
        delta = {
            name: rows["leader"]["degree"][name] - rows["follower"]["degree"][name]
            for name in JOINTS
        }
        return {
            "unix_ns": time.time_ns(),
            "leader": rows["leader"],
            "follower": rows["follower"],
            "difference_degree": delta,
            "within_2_degree": all(abs(value) <= 2 for value in delta.values()),
            "teleop_allowed_while_viewer_owns_ports": False,
            "motor_write_calls": 0,
            "torque_change_calls": 0,
        }

    def close(self) -> None:
        for role in ("follower", "leader"):
            bus = self.buses.pop(role, None)
            if bus is not None:
                bus.disconnect(disable_torque=False)


PAGE = """<!doctype html><html lang=ko><meta charset=utf-8>
<title>SO-101 리더 정렬</title>
<style>body{font:18px system-ui;margin:2rem;max-width:900px}table{border-collapse:collapse;width:100%}
td,th{border-bottom:1px solid #ccc;padding:.65rem;text-align:right}th:first-child,td:first-child{text-align:left}
.bad{color:#b00020;font-weight:700}.good{color:#087b35;font-weight:700}
.note{background:#fff2d5;padding:1rem;margin-bottom:1.2rem}</style>
<h1>SO-101 리더 관절 정렬 · 읽기 전용</h1>
<div class=note>LeLab 텔레옵은 OFF. 리더만 손으로 움직이세요. 이 화면을 종료하고 두 USB 포트가 해제되기 전에는 텔레옵을 시작하지 마세요.</div>
<p id=status>측정 중…</p><table><thead><tr><th>관절</th><th>리더 °</th><th>팔로워 °</th><th>차이 °</th><th>목표</th></tr></thead><tbody id=rows></tbody></table>
<p>팔로워가 관절 한계에 가까우므로 ±2° 표시는 정렬의 1차 기준일 뿐, 텔레옵 시작 승인 자체는 아닙니다. 시작 전 별도 확인이 필요합니다.</p>
<script>
const names=['shoulder_pan','shoulder_lift','elbow_flex','wrist_flex','wrist_roll'];
const labels=['어깨 회전','어깨 들기','팔꿈치','손목 굽힘','손목 회전'];
async function refresh(){
 try{
  const r=await fetch('/api/joints',{cache:'no-store'});
  if(!r.ok)throw Error(await r.text());
  const d=await r.json();
  document.getElementById('status').textContent=`${new Date(d.unix_ns/1e6).toLocaleTimeString()} · 명령 전송 0회 · 토크 변경 0회 · ${d.within_2_degree?'5축 ±2° 이내':'정렬 미완료'}`;
  document.getElementById('status').className=d.within_2_degree?'good':'bad';
  document.getElementById('rows').innerHTML=names.map((n,i)=>{
   const v=d.difference_degree[n],ok=Math.abs(v)<=2;
   return `<tr><td>${labels[i]} (${n})</td><td>${d.leader.degree[n].toFixed(2)}</td><td>${d.follower.degree[n].toFixed(2)}</td><td class=${ok?'good':'bad'}>${v>=0?'+':''}${v.toFixed(2)}</td><td>±2°</td></tr>`
  }).join('');
 }catch(e){document.getElementById('status').textContent='측정 중단: '+e;document.getElementById('status').className='bad'}
}
refresh();setInterval(refresh,700);
</script></html>"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8031)
    args = parser.parse_args()
    require_lelab_off()
    require_port_identities()
    reader = Reader()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            try:
                if self.path == "/":
                    content, kind = PAGE.encode(), "text/html; charset=utf-8"
                elif self.path == "/api/joints":
                    content = json.dumps(reader.read(), separators=(",", ":")).encode()
                    kind = "application/json"
                else:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", kind)
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            except Exception as error:
                self.send_error(503, f"read-only measurement unavailable: {type(error).__name__}")

    try:
        server = HTTPServer((args.host, args.port), Handler)
    except BaseException:
        reader.close()
        raise
    signal.signal(signal.SIGTERM, lambda _sig, _frame: (_ for _ in ()).throw(KeyboardInterrupt()))
    print(f"SO101_ALIGNMENT_VIEW_READY port={args.port}", flush=True)
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        reader.close()
        print("SO101_ALIGNMENT_VIEW_CLOSED ports_released=True", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
