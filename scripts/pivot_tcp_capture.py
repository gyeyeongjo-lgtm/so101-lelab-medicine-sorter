#!/usr/bin/env python3
"""Read-only fixed-point pivot TCP capture from LeLab joint broadcasts.

This process subscribes to ``/ws/joint-data`` and evaluates URDF FK locally.
It never opens a serial device, sends a robot command, or changes torque.
The operator keeps one rigid physical TCP point fixed while changing tool
orientation, then captures 5--8 settled poses.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import numpy as np

try:
    from scripts.teach_capture_web import CaptureState, JOINT_NAMES, joint_worker
    from scripts.urdf_forward_kinematics import UrdfKinematics
except ModuleNotFoundError:  # Direct execution from scripts/.
    from teach_capture_web import CaptureState, JOINT_NAMES, joint_worker
    from urdf_forward_kinematics import UrdfKinematics


URDF_SHA256 = "443d38d756e01bac7d3455b24430047ddc6427105e0d3454b2003116f5f67236"
ARM_JOINTS = ("Rotation", "Pitch", "Elbow", "Wrist_Pitch", "Wrist_Roll")
MAX_JOINT_AGE_NS = 400_000_000
SETTLED_SAMPLE_COUNT = 15
MAX_JOINT_STD_RAD = 0.01
MIN_POSES = 5
MAX_POSES = 8


def rotation_to_rpy_deg(rotation: np.ndarray) -> list[float]:
    """Return extrinsic XYZ / URDF-style roll-pitch-yaw angles in degrees."""
    pitch = math.atan2(-float(rotation[2, 0]),
                       math.hypot(float(rotation[0, 0]), float(rotation[1, 0])))
    if abs(math.cos(pitch)) > 1e-9:
        roll = math.atan2(float(rotation[2, 1]), float(rotation[2, 2]))
        yaw = math.atan2(float(rotation[1, 0]), float(rotation[0, 0]))
    else:
        roll = math.atan2(-float(rotation[1, 2]), float(rotation[1, 1]))
        yaw = 0.0
    return [math.degrees(value) for value in (roll, pitch, yaw)]


def settled_joint_snapshot(state: CaptureState, now_ns: int | None = None) -> dict:
    """Select 15 fresh, unique, stationary broadcast samples."""
    now_ns = now_ns or time.monotonic_ns()
    with state.lock:
        recent = [sample for sample in state.joints
                  if now_ns - sample.received_ns <= 1_500_000_000]
    samples = recent[-SETTLED_SAMPLE_COUNT:]
    if (len(samples) < SETTLED_SAMPLE_COUNT or
            now_ns - samples[-1].received_ns > MAX_JOINT_AGE_NS):
        raise ValueError("15 fresh follower broadcasts are required")
    if len({sample.source_unix for sample in samples}) != SETTLED_SAMPLE_COUNT:
        raise ValueError("follower broadcast timestamps are not unique")
    means = {
        name: statistics.mean(sample.joints[name] for sample in samples)
        for name in JOINT_NAMES
    }
    stds = {
        name: statistics.pstdev(sample.joints[name] for sample in samples)
        for name in JOINT_NAMES
    }
    if not all(math.isfinite(value) for value in (*means.values(), *stds.values())):
        raise ValueError("non-finite follower feedback")
    if max(stds.values()) > MAX_JOINT_STD_RAD:
        raise ValueError(
            f"follower has not settled; max std={max(stds.values()):.6f} rad"
        )
    return {
        "samples": samples,
        "means": means,
        "stds": stds,
        "max_std_rad": max(stds.values()),
    }


def solve_pivot(captures: list[dict]) -> dict:
    """Fit p_fixed = t_i + R_i @ tcp_offset using every supplied pose."""
    if len(captures) < MIN_POSES:
        raise ValueError("at least 5 pivot poses are required")
    if len(captures) > MAX_POSES:
        raise ValueError("at most 8 pivot poses are supported")
    design_rows = []
    targets = []
    for capture in captures:
        rotation = np.asarray(capture["fk_tool_rotation"], dtype=np.float64)
        origin = np.asarray(capture["fk_tool_origin_mm"], dtype=np.float64)
        if rotation.shape != (3, 3) or origin.shape != (3,):
            raise ValueError("invalid FK pose shape")
        if not np.isfinite(rotation).all() or not np.isfinite(origin).all():
            raise ValueError("non-finite FK pose")
        design_rows.append(np.hstack((rotation, -np.eye(3))))
        targets.append(-origin)
    design = np.vstack(design_rows)
    target = np.concatenate(targets)
    solution, _, rank, singular_values = np.linalg.lstsq(design, target, rcond=None)
    tcp_offset = solution[:3]
    fixed_point = solution[3:]
    residual_vectors = []
    residuals = []
    for capture in captures:
        rotation = np.asarray(capture["fk_tool_rotation"], dtype=np.float64)
        origin = np.asarray(capture["fk_tool_origin_mm"], dtype=np.float64)
        vector = origin + rotation @ tcp_offset - fixed_point
        residual_vectors.append(vector.tolist())
        residuals.append(float(np.linalg.norm(vector)))
    condition = float(np.linalg.cond(design))
    return {
        "schema_version": 1,
        "status": "DIAGNOSTIC_ONLY",
        "equation": "p_fixed = t_i + R_i * tcp_offset",
        "tcp_frame": "gripper",
        "pose_count": len(captures),
        "pose_ids": [capture["pose_id"] for capture in captures],
        "estimated_tcp_offset_gripper_mm": tcp_offset.tolist(),
        "estimated_tcp_offset_norm_mm": float(np.linalg.norm(tcp_offset)),
        "estimated_fixed_point_base_mm": fixed_point.tolist(),
        "pose_residual_vectors_mm": residual_vectors,
        "pose_residuals_mm": residuals,
        "rms_residual_mm": float(np.sqrt(np.mean(np.square(residuals)))),
        "max_residual_mm": max(residuals),
        "rank": int(rank),
        "condition_number": condition,
        "singular_values": singular_values.tolist(),
        "observable": bool(rank == 6 and math.isfinite(condition)),
        "robot_enabled": False,
        "motion_authorized": False,
        "interpretation": (
            "A large/nonphysical offset or large residual means a fixed TCP offset alone "
            "does not explain the data; inspect joint convention/sign/zero, URDF lengths, "
            "tool origin, and duplicate calibration application."
        ),
    }


class PivotSession:
    def __init__(self, state: CaptureState, kinematics: UrdfKinematics,
                 output_root: Path, urdf_sha256: str):
        self.state = state
        self.kinematics = kinematics
        self.output_root = output_root
        self.urdf_sha256 = urdf_sha256
        self.lock = threading.Lock()
        self.captures: list[dict] = []
        for index in range(1, MAX_POSES + 1):
            path = output_root / f"pose_{index:02d}.json"
            if not path.is_file():
                break
            capture = json.loads(path.read_text(encoding="utf-8"))
            if capture.get("pose_id") != index or capture.get("urdf_sha256") != urdf_sha256:
                raise ValueError(f"saved pivot pose provenance mismatch: {path}")
            self.captures.append(capture)

    def status(self) -> dict:
        receiver = self.state.status()
        with self.lock:
            captured = [capture["pose_id"] for capture in self.captures]
        return {
            "mode": "READ_ONLY_PIVOT_TCP_DIAGNOSTIC",
            "tcp_frame": "gripper",
            "captured_pose_ids": captured,
            "captured_count": len(captured),
            "minimum_pose_count": MIN_POSES,
            "maximum_pose_count": MAX_POSES,
            "joint_age_ms": receiver["joint_age_ms"],
            "joint_error": receiver["errors"]["joints"],
            "robot_control": False,
            "motion_authorized": False,
        }

    def capture(self, *, point_fixed_confirmed: bool, stationary_confirmed: bool) -> dict:
        if not point_fixed_confirmed or not stationary_confirmed:
            raise ValueError("same physical point and complete stop must be confirmed")
        snapshot = settled_joint_snapshot(self.state)
        with self.lock:
            pose_id = len(self.captures) + 1
            if pose_id > MAX_POSES:
                raise ValueError("8 pivot poses already captured")
        transform = self.kinematics.forward(snapshot["means"], "base", "gripper")
        record = {
            "schema_version": 1,
            "pose_id": pose_id,
            "physical_constraint": "same rigid right-side end-effector point held at one physical point",
            "tcp_frame": "gripper",
            "follower_5axis_rad": {name: snapshot["means"][name] for name in ARM_JOINTS},
            "follower_5axis_deg": {
                name: math.degrees(snapshot["means"][name]) for name in ARM_JOINTS
            },
            "follower_jaw_rad": snapshot["means"]["Jaw"],
            "joint_std_rad": snapshot["stds"],
            "joint_max_std_rad": snapshot["max_std_rad"],
            "joint_samples": [
                {
                    "joints_rad": sample.joints,
                    "source_unix": sample.source_unix,
                    "received_unix_ns": sample.received_unix_ns,
                }
                for sample in snapshot["samples"]
            ],
            "fk_root_frame": "base",
            "fk_tool_frame": "gripper",
            "fk_tool_origin_mm": (transform[:3, 3] * 1000.0).tolist(),
            "fk_tool_rotation": transform[:3, :3].tolist(),
            "fk_tool_rpy_deg": rotation_to_rpy_deg(transform[:3, :3]),
            "urdf_sha256": self.urdf_sha256,
            "captured_unix_ns": time.time_ns(),
            "robot_enabled": False,
            "motion_authorized": False,
        }
        path = self.output_root / f"pose_{pose_id:02d}.json"
        with self.lock:
            if len(self.captures) + 1 != pose_id or path.exists():
                raise ValueError("pivot pose destination changed; capture again")
            path.write_text(json.dumps(record, indent=2, allow_nan=False) + "\n",
                            encoding="utf-8")
            self.captures.append(record)
        return record

    def fit(self) -> dict:
        with self.lock:
            captures = list(self.captures)
        result = solve_pivot(captures)
        result["urdf_sha256"] = self.urdf_sha256
        path = self.output_root / f"pivot_fit_{len(captures):02d}_poses.json"
        encoded = json.dumps(result, indent=2, allow_nan=False) + "\n"
        if path.exists() and path.read_text(encoding="utf-8") != encoded:
            raise ValueError(f"refusing to overwrite different fit result: {path.name}")
        path.write_text(encoded, encoding="utf-8")
        return result


PAGE = """<!doctype html><html lang=ko><meta charset=utf-8>
<title>SO-101 pivot TCP diagnostic</title><style>body{font:16px system-ui;max-width:900px;margin:24px auto;padding:0 16px}button{font-size:18px;padding:10px;margin:6px}pre{white-space:pre-wrap;background:#111;color:#ddd;padding:12px}label{display:block;margin:10px 0}</style>
<h2>Pivot TCP capture (read-only)</h2>
<p>오른쪽 강체 기준점을 한 physical point에 고정하고 tool orientation만 바꿉니다. 이 페이지는 관절 방송을 읽고 FK만 계산하며 로봇 명령을 보내지 않습니다.</p>
<div id=status></div>
<label><input id=fixed type=checkbox> 동일 강체점이 같은 physical point에 고정됨</label>
<label><input id=stopped type=checkbox> 팔이 완전히 정지함</label>
<button onclick=capturePose()>현재 pose 캡처</button><button onclick=fit()>5 pose 이상 fit</button>
<pre id=out></pre>
<script>
async function api(path,data){let r=await fetch(path,{method:data?'POST':'GET',headers:{'Content-Type':'application/json'},body:data?JSON.stringify(data):undefined});let j=await r.json();if(!r.ok)throw Error(j.error||r.status);return j}
async function refresh(){try{let s=await api('/api/status');status.textContent=`captured ${s.captured_count}/8 | joint age ${s.joint_age_ms} ms | ${s.joint_error||'joint stream OK'}`}catch(e){status.textContent=e}}
async function capturePose(){try{out.textContent=JSON.stringify(await api('/api/capture',{point_fixed_confirmed:fixed.checked,stationary_confirmed:stopped.checked}),null,2);fixed.checked=false;stopped.checked=false;refresh()}catch(e){out.textContent=String(e)}}
async function fit(){try{out.textContent=JSON.stringify(await api('/api/fit',{}),null,2)}catch(e){out.textContent=String(e)}}
setInterval(refresh,500);refresh();
</script>""".encode("utf-8")


class Server(ThreadingHTTPServer):
    def __init__(self, address, session: PivotSession):
        super().__init__(address, Handler)
        self.session = session


class Handler(BaseHTTPRequestHandler):
    server: Server

    def send_json(self, document: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(document, allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(PAGE)))
            self.end_headers()
            self.wfile.write(PAGE)
        elif self.path == "/api/status":
            self.send_json(self.server.session.status())
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if self.path not in ("/api/capture", "/api/fit"):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(length) or b"{}")
            if self.path == "/api/capture":
                result = self.server.session.capture(
                    point_fixed_confirmed=data.get("point_fixed_confirmed") is True,
                    stationary_confirmed=data.get("stationary_confirmed") is True,
                )
            else:
                result = self.server.session.fit()
            self.send_json(result)
        except (ValueError, KeyError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)

    def log_message(self, *_args) -> None:
        return


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lelab-url", default="http://192.168.50.20:8000")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8034)
    parser.add_argument("--urdf", required=True, type=Path)
    parser.add_argument("--expected-urdf-sha256", default=URDF_SHA256)
    parser.add_argument("--output-root", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.host not in ("127.0.0.1", "::1"):
        raise SystemExit("pivot capture page must bind to loopback only")
    parts = urlsplit(args.lelab_url)
    if parts.scheme not in ("http", "https") or not parts.netloc or parts.path not in ("", "/"):
        raise SystemExit("--lelab-url must be an HTTP(S) origin without a path")
    urdf_sha = hashlib.sha256(args.urdf.read_bytes()).hexdigest()
    if urdf_sha != args.expected_urdf_sha256.lower():
        raise SystemExit("URDF SHA-256 does not match expected installed source")
    try:
        import websocket  # noqa: F401
    except ImportError as error:
        raise SystemExit("websocket-client is required") from error
    args.output_root.mkdir(parents=True, exist_ok=True)
    state = CaptureState()
    session = PivotSession(state, UrdfKinematics.from_file(args.urdf),
                           args.output_root, urdf_sha)
    stop = threading.Event()
    worker = threading.Thread(target=joint_worker,
                              args=(state, args.lelab_url.rstrip("/"), stop), daemon=True)
    server = Server((args.host, args.port), session)
    worker.start()
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        server.server_close()
        worker.join(timeout=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
