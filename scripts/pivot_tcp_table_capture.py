#!/usr/bin/env python3
"""Capture a fresh seven-point table↔robot set using a fixed pivot TCP.

The tool only subscribes to LeLab joint broadcasts. It has no robot bus,
teleoperation, torque, or motor-command path. Table marks are loaded from a
previous registration set and cannot be changed through this server.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import numpy as np

try:
    from scripts.pivot_tcp_capture import settled_joint_snapshot
    from scripts.teach_capture_web import CaptureState, joint_worker
    from scripts.urdf_forward_kinematics import UrdfKinematics
except ModuleNotFoundError:  # Direct execution from scripts/.
    from pivot_tcp_capture import settled_joint_snapshot
    from teach_capture_web import CaptureState, joint_worker
    from urdf_forward_kinematics import UrdfKinematics


URDF_SHA256 = "443d38d756e01bac7d3455b24430047ddc6427105e0d3454b2003116f5f67236"
SEQUENCE = ("P1", "P2", "P3", "P4", "H1", "Repeat_P1", "Repeat_P3")
FIT_POINTS = ("P1", "P2", "P3", "P4")
ARM_JOINTS = ("Rotation", "Pitch", "Elbow", "Wrist_Pitch", "Wrist_Roll")


def load_registered_marks(root: Path) -> tuple[dict[str, list[float]], dict[str, str]]:
    marks = {}
    hashes = {}
    for name in ("P1", "P2", "P3", "P4", "H1"):
        path = root / f"registered_{name}.json"
        raw = path.read_bytes()
        document = json.loads(raw)
        xy = document.get("table_xy_mm")
        if document.get("point_id") != name or not isinstance(xy, list) or len(xy) != 2:
            raise ValueError(f"invalid saved registration: {path}")
        values = [float(value) for value in xy]
        if not all(math.isfinite(value) for value in values):
            raise ValueError(f"non-finite saved registration: {path}")
        marks[name] = values
        hashes[name] = hashlib.sha256(raw).hexdigest()
    return marks, hashes


def reflected_rigid_fit(captures: dict[str, dict]) -> dict:
    if any(name not in captures for name in SEQUENCE):
        raise ValueError("all seven captures are required")
    table = np.asarray([
        [-captures[name]["table_xy_mm"][0], captures[name]["table_xy_mm"][1]]
        for name in FIT_POINTS
    ], dtype=np.float64)
    robot = np.asarray([
        captures[name]["corrected_physical_tcp_xyz_mm"][:2] for name in FIT_POINTS
    ], dtype=np.float64)
    table_center = table.mean(axis=0)
    robot_center = robot.mean(axis=0)
    u, _, vt = np.linalg.svd((table - table_center).T @ (robot - robot_center))
    correction = np.eye(2)
    correction[-1, -1] = np.sign(np.linalg.det(u @ vt))
    rotation_row = u @ correction @ vt
    translation = robot_center - table_center @ rotation_row
    prediction = table @ rotation_row + translation
    vectors = robot - prediction
    residuals = np.linalg.norm(vectors, axis=1)

    def predict(record: dict) -> tuple[np.ndarray, np.ndarray, float]:
        xy = record["table_xy_mm"]
        reflected = np.asarray([-xy[0], xy[1]], dtype=np.float64)
        predicted = reflected @ rotation_row + translation
        actual = np.asarray(record["corrected_physical_tcp_xyz_mm"][:2])
        vector = actual - predicted
        return predicted, vector, float(np.linalg.norm(vector))

    h_prediction, h_vector, h_error = predict(captures["H1"])
    p1_prediction, p1_vector, p1_error = predict(captures["Repeat_P1"])
    p3_prediction, p3_vector, p3_error = predict(captures["Repeat_P3"])
    p1_direct_vector = (
        np.asarray(captures["Repeat_P1"]["corrected_physical_tcp_xyz_mm"][:2]) -
        np.asarray(captures["P1"]["corrected_physical_tcp_xyz_mm"][:2])
    )
    p3_direct_vector = (
        np.asarray(captures["Repeat_P3"]["corrected_physical_tcp_xyz_mm"][:2]) -
        np.asarray(captures["P3"]["corrected_physical_tcp_xyz_mm"][:2])
    )
    rotation_column = rotation_row.T
    combined = rotation_column @ np.diag([-1.0, 1.0])
    homogeneous = np.eye(3)
    homogeneous[:2, :2] = combined
    homogeneous[:2, 2] = translation
    direct_p1 = float(np.linalg.norm(p1_direct_vector))
    direct_p3 = float(np.linalg.norm(p3_direct_vector))
    rms = float(np.sqrt(np.mean(np.square(residuals))))
    maximum = float(np.max(residuals))
    independent = (h_error, direct_p1, direct_p3, p1_error, p3_error)
    return {
        "schema_version": 1,
        "status": (
            "CALIBRATION_CANDIDATE_SINGLE_DIGIT"
            if maximum < 10.0 and all(value < 10.0 for value in independent)
            else "REJECTED_FIT_OR_REPEAT"
        ),
        "table_pretransform": "[-table_x, table_y]",
        "fit_points": list(FIT_POINTS),
        "independent_points": ["H1", "Repeat_P1", "Repeat_P3"],
        "fit_residual_vectors_robot_xy_mm": dict(zip(FIT_POINTS, vectors.tolist())),
        "fit_residuals_mm": dict(zip(FIT_POINTS, residuals.tolist())),
        "fit_rms_mm": rms,
        "fit_max_mm": maximum,
        "h1_prediction_robot_xy_mm": h_prediction.tolist(),
        "h1_error_vector_mm": h_vector.tolist(),
        "h1_error_mm": h_error,
        "repeat_p1_direct_vector_mm": p1_direct_vector.tolist(),
        "repeat_p1_direct_error_mm": direct_p1,
        "repeat_p1_prediction_robot_xy_mm": p1_prediction.tolist(),
        "repeat_p1_transform_error_vector_mm": p1_vector.tolist(),
        "repeat_p1_transform_error_mm": p1_error,
        "repeat_p3_direct_vector_mm": p3_direct_vector.tolist(),
        "repeat_p3_direct_error_mm": direct_p3,
        "repeat_p3_prediction_robot_xy_mm": p3_prediction.tolist(),
        "repeat_p3_transform_error_vector_mm": p3_vector.tolist(),
        "repeat_p3_transform_error_mm": p3_error,
        "rotation_reflected_table_to_robot_column": rotation_column.tolist(),
        "rotation_deg": math.degrees(math.atan2(rotation_column[1, 0], rotation_column[0, 0])),
        "translation_robot_xy_mm": translation.tolist(),
        "homogeneous_original_table_to_robot_with_x_reflection": homogeneous.tolist(),
        "combined_determinant": float(np.linalg.det(combined)),
        "single_digit_threshold_mm": 10.0,
        "robot_enabled": False,
        "motion_authorized": False,
    }


class CalibrationSession:
    def __init__(self, state: CaptureState, kinematics: UrdfKinematics, root: Path,
                 session_id: str, marks: dict[str, list[float]], mark_hashes: dict[str, str],
                 tcp_offset_mm: np.ndarray, urdf_sha256: str):
        self.state = state
        self.kinematics = kinematics
        self.root = root
        self.session_id = session_id
        self.marks = marks
        self.mark_hashes = mark_hashes
        self.tcp_offset_mm = tcp_offset_mm
        self.urdf_sha256 = urdf_sha256
        self.lock = threading.Lock()
        self.captures: dict[str, dict] = {}
        manifest_path = root / "session_manifest.json"
        expected = {
            "schema_version": 1,
            "session_id": session_id,
            "sequence": list(SEQUENCE),
            "table_marks_mm": marks,
            "registration_sha256": mark_hashes,
            "tcp_offset_gripper_mm": tcp_offset_mm.tolist(),
            "urdf_sha256": urdf_sha256,
            "registration_editing": False,
            "prior_capture_imported": False,
            "robot_enabled": False,
            "motion_authorized": False,
        }
        if manifest_path.exists():
            if json.loads(manifest_path.read_text(encoding="utf-8")) != expected:
                raise ValueError("existing session manifest does not match requested session")
        else:
            if any(root.iterdir()):
                raise ValueError("new calibration output root is not empty")
            manifest_path.write_text(json.dumps(expected, indent=2) + "\n", encoding="utf-8")
        for name in SEQUENCE:
            path = root / f"capture_{name}.json"
            if not path.exists():
                break
            record = json.loads(path.read_text(encoding="utf-8"))
            if record.get("session_id") != session_id or record.get("capture_id") != name:
                raise ValueError(f"capture provenance mismatch: {path}")
            self.captures[name] = record

    def next_point(self) -> str | None:
        return next((name for name in SEQUENCE if name not in self.captures), None)

    def status(self) -> dict:
        receiver = self.state.status()
        with self.lock:
            next_point = self.next_point()
            captured = list(self.captures)
        base = None if next_point is None else next_point.removeprefix("Repeat_")
        return {
            "session_id": self.session_id,
            "dataset_root": str(self.root),
            "captured": captured,
            "captured_count": len(captured),
            "next_point": next_point,
            "next_table_xy_mm": None if base is None else self.marks[base],
            "joint_age_ms": receiver["joint_age_ms"],
            "joint_error": receiver["errors"]["joints"],
            "registration_editing": False,
            "prior_capture_imported": False,
            "robot_control": False,
        }

    def capture(self, point: str, *, physical_mark_confirmed: bool,
                stationary_confirmed: bool, hover_height_confirmed: bool) -> dict:
        with self.lock:
            expected = self.next_point()
        if point != expected:
            raise ValueError(f"next capture must be {expected}")
        if not (physical_mark_confirmed and stationary_confirmed and hover_height_confirmed):
            raise ValueError("physical mark, complete stop, and hover height must be confirmed")
        snapshot = settled_joint_snapshot(self.state)
        transform = self.kinematics.forward(snapshot["means"], "base", "gripper")
        corrected = transform[:3, 3] * 1000.0 + transform[:3, :3] @ self.tcp_offset_mm
        mark = point.removeprefix("Repeat_")
        record = {
            "schema_version": 1,
            "session_id": self.session_id,
            "capture_id": point,
            "point_name": mark,
            "role": "fit" if point in FIT_POINTS else "independent_validation",
            "table_xy_mm": self.marks[mark],
            "registration_sha256": self.mark_hashes[mark],
            "follower_5axis_rad": {name: snapshot["means"][name] for name in ARM_JOINTS},
            "follower_5axis_deg": {
                name: math.degrees(snapshot["means"][name]) for name in ARM_JOINTS
            },
            "follower_jaw_rad": snapshot["means"]["Jaw"],
            "joint_max_std_rad": snapshot["max_std_rad"],
            "joint_samples": [
                {"joints_rad": sample.joints, "source_unix": sample.source_unix,
                 "received_unix_ns": sample.received_unix_ns}
                for sample in snapshot["samples"]
            ],
            "fk_gripper_origin_mm": (transform[:3, 3] * 1000.0).tolist(),
            "fk_gripper_rotation": transform[:3, :3].tolist(),
            "tcp_offset_gripper_mm": self.tcp_offset_mm.tolist(),
            "corrected_physical_tcp_xyz_mm": corrected.tolist(),
            "urdf_sha256": self.urdf_sha256,
            "physical_mark_confirmed": True,
            "stationary_confirmed": True,
            "hover_height_confirmed": True,
            "captured_unix_ns": time.time_ns(),
            "prior_capture_imported": False,
            "robot_enabled": False,
            "motion_authorized": False,
        }
        path = self.root / f"capture_{point}.json"
        with self.lock:
            if self.next_point() != point or path.exists():
                raise ValueError("capture destination changed; capture again")
            path.write_text(json.dumps(record, indent=2, allow_nan=False) + "\n",
                            encoding="utf-8")
            self.captures[point] = record
        return record

    def fit(self) -> dict:
        with self.lock:
            captures = dict(self.captures)
        result = reflected_rigid_fit(captures)
        result.update({
            "session_id": self.session_id,
            "tcp_offset_gripper_mm": self.tcp_offset_mm.tolist(),
            "urdf_sha256": self.urdf_sha256,
        })
        path = self.root / "reflected_table_robot_fit.json"
        encoded = json.dumps(result, indent=2, allow_nan=False) + "\n"
        if path.exists() and path.read_text(encoding="utf-8") != encoded:
            raise ValueError("refusing to overwrite a different fit")
        path.write_text(encoded, encoding="utf-8")
        return result


PAGE = """<!doctype html><html lang=ko><meta charset=utf-8><title>Pivot TCP 7-point capture</title>
<style>body{font:16px system-ui;max-width:900px;margin:24px auto;padding:0 16px}button{font-size:18px;padding:10px;margin:6px}pre{white-space:pre-wrap;background:#111;color:#ddd;padding:12px}label{display:block;margin:10px 0}</style>
<h2>새 Pivot-TCP table↔robot 7-point session</h2><p>기존 mark XY는 고정되어 있으며 이 페이지에서 수정할 수 없습니다. joint broadcast/FK만 읽고 로봇 명령은 보내지 않습니다.</p>
<div id=status></div><label><input id=mark type=checkbox> 동일한 오른쪽 강체점이 표시된 mark 중심에 맞음</label><label><input id=stopped type=checkbox> 완전히 정지함</label><label><input id=height type=checkbox> 가능한 동일 hover 높이를 유지함</label>
<button onclick=cap()>현재 순서 캡처</button><button onclick=fit()>7/7 fit</button><pre id=out></pre>
<script>let current=null;async function api(path,data){let r=await fetch(path,{method:data?'POST':'GET',headers:{'Content-Type':'application/json'},body:data?JSON.stringify(data):undefined});let j=await r.json();if(!r.ok)throw Error(j.error||r.status);return j}async function refresh(){try{let s=await api('/api/status');current=s.next_point;status.textContent=`session ${s.session_id} | ${s.captured_count}/7 | next ${s.next_point||'완료'} | table ${JSON.stringify(s.next_table_xy_mm)} | joint age ${s.joint_age_ms} ms`}catch(e){status.textContent=e}}async function cap(){try{out.textContent=JSON.stringify(await api('/api/capture',{point:current,physical_mark_confirmed:mark.checked,stationary_confirmed:stopped.checked,hover_height_confirmed:height.checked}),null,2);mark.checked=stopped.checked=height.checked=false;refresh()}catch(e){out.textContent=String(e)}}async function fit(){try{out.textContent=JSON.stringify(await api('/api/fit',{}),null,2)}catch(e){out.textContent=String(e)}}setInterval(refresh,500);refresh();</script>""".encode("utf-8")


class Server(ThreadingHTTPServer):
    def __init__(self, address, session: CalibrationSession):
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
            data = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))) or b"{}")
            if self.path == "/api/capture":
                result = self.server.session.capture(
                    data.get("point"),
                    physical_mark_confirmed=data.get("physical_mark_confirmed") is True,
                    stationary_confirmed=data.get("stationary_confirmed") is True,
                    hover_height_confirmed=data.get("hover_height_confirmed") is True,
                )
            else:
                result = self.server.session.fit()
            self.send_json(result)
        except (ValueError, KeyError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)

    def log_message(self, *_args) -> None:
        return


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lelab-url", default="http://192.168.50.20:8000")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8034)
    parser.add_argument("--urdf", required=True, type=Path)
    parser.add_argument("--expected-urdf-sha256", default=URDF_SHA256)
    parser.add_argument("--registrations-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--tcp-offset-mm", required=True, type=float, nargs=3)
    args = parser.parse_args()
    if args.host not in ("127.0.0.1", "::1"):
        parser.error("capture page must bind to loopback only")
    parts = urlsplit(args.lelab_url)
    if parts.scheme not in ("http", "https") or not parts.netloc or parts.path not in ("", "/"):
        parser.error("--lelab-url must be an HTTP(S) origin without a path")
    urdf_sha = hashlib.sha256(args.urdf.read_bytes()).hexdigest()
    if urdf_sha != args.expected_urdf_sha256.lower():
        parser.error("URDF SHA-256 does not match expected installed source")
    offset = np.asarray(args.tcp_offset_mm, dtype=np.float64)
    if offset.shape != (3,) or not np.isfinite(offset).all():
        parser.error("finite XYZ TCP offset required")
    marks, hashes = load_registered_marks(args.registrations_root)
    args.output_root.mkdir(parents=True, exist_ok=True)
    state = CaptureState()
    session = CalibrationSession(state, UrdfKinematics.from_file(args.urdf), args.output_root,
                                 args.session_id, marks, hashes, offset, urdf_sha)
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
