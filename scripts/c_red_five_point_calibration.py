#!/usr/bin/env python3
"""Read-only five-point table→robot capture; never opens a robot bus.

The operator first clicks five fixed marks in a live ceiling frame. At each
stationary teleop pose, one capture pairs a fresh frame with fresh follower
broadcast feedback by *receive time*, computes a physically verified rigid
TCP's FK, and stores both original timestamps. Exposure-time synchronization
is not available. P1–P4 fit SE(2); H1 is held out entirely.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import threading
import time
import xml.etree.ElementTree as ET
import urllib.error
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import cv2
import numpy as np

from medicine_yolo_web import TableMapper, detect_table_markers, project_table_xy
from stable_aruco_table import STABLE_IDS, StableTableReference
from teach_capture_web import CaptureState, camera_worker, joint_worker, lelab_teleop_active
from urdf_forward_kinematics import UrdfKinematics
from vision_guided_geometry import fit_table_to_robot_xy


POINTS = ("P1", "P2", "P3", "P4", "H1")
URDF_SHA256 = "443d38d756e01bac7d3455b24430047ddc6427105e0d3454b2003116f5f67236"
MAX_PAIR_GAP_NS = 250_000_000
MAX_FRAME_AGE_NS = 750_000_000
MAX_JOINT_AGE_NS = 400_000_000


def urdf_model_limit_warnings(joints: dict[str, float],
                              limits: dict[str, tuple[float, float]]) -> list[dict]:
    """Report model disagreement; never gate read-only feedback or FK."""
    warnings = []
    for name, (lower, upper) in limits.items():
        value = float(joints[name])
        if not math.isfinite(value):
            raise ValueError(f"nonfinite follower feedback: {name}")
        if value < lower or value > upper:
            warnings.append({"joint": name, "observed_deg": round(math.degrees(value), 3),
                             "model_lower_deg": round(math.degrees(lower), 3),
                             "model_upper_deg": round(math.degrees(upper), 3),
                             "warning": "OUTSIDE_URDF_MODEL_NOT_A_SERVO_LIMIT"})
    return warnings


def read_urdf_model_limits(urdf: Path) -> dict[str, tuple[float, float]]:
    root = ET.parse(urdf).getroot()
    limits = {}
    for joint in root.findall("joint"):
        if joint.get("type") != "revolute":
            continue
        element = joint.find("limit")
        if element is not None:
            limits[joint.attrib["name"]] = (float(element.attrib["lower"]),
                                             float(element.attrib["upper"]))
    return limits


def frame_geometry(jpeg: bytes, mapper: TableMapper, pixel: list[float],
                   reference: StableTableReference) -> dict:
    image = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None or image.shape[:2] != (480, 640):
        raise ValueError("fresh 640x480 ceiling JPEG required")
    if len(pixel) != 2 or not all(math.isfinite(float(v)) for v in pixel):
        raise ValueError("finite pixel center required")
    if not (0 <= pixel[0] < 640 and 0 <= pixel[1] < 480):
        raise ValueError("point pixel outside ceiling image")
    table = reference.analyze(image, require_id4=False)
    homography = table["homography"]
    centers = table["centers_px"]
    x, y = project_table_xy(np, homography, float(pixel[0]), float(pixel[1]))
    if not all(math.isfinite(v) for v in (x, y)):
        raise ValueError("table point projection invalid")
    return {
        "table_xy_mm": [round(x, 3), round(y, 3)],
        "aruco_ids": table["aruco_ids"],
        "equalized_fallback_ids": table["equalized_fallback_ids"],
        "aruco_quality": table["quality"],
        "reference_centers_px": {str(i): [round(float(v), 3) for v in centers[i]]
                                 for i in table["quality"]["stable_ids"]},
        "id4_marker_table_xy_mm": (
            [round(v, 3) for v in table["id4_marker_table_xy_mm"]]
            if table["id4_marker_table_xy_mm"] is not None else None),
    }


def capture_geometry(jpeg: bytes, mapper: TableMapper, registration: dict,
                     reference: StableTableReference) -> tuple[dict, float]:
    """Verify camera stability while allowing the arm to hide one anchor."""
    previous = registration["aruco"]["reference_centers_px"]
    try:
        geometry = frame_geometry(jpeg, mapper, registration["pixel_px"], reference)
        drift = max(float(np.linalg.norm(
            np.asarray(geometry["reference_centers_px"][str(i)]) -
            np.asarray(previous[str(i)]))) for i in STABLE_IDS)
        table_shift = float(np.linalg.norm(
            np.asarray(geometry["table_xy_mm"]) -
            np.asarray(registration["table_xy_mm"])))
        if drift > 2.0:
            raise ValueError(f"camera/table marks moved by {drift:.3f} px; register point again")
        if table_shift > 3.0:
            raise ValueError("registered table mark no longer projects to same XY")
        return geometry, drift
    except ValueError as error:
        if "live frame lacks required stable/table/basket ArUco IDs" not in str(error):
            raise
    image = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None or image.shape[:2] != (480, 640):
        raise ValueError("fresh 640x480 ceiling JPEG required")
    corners, fallback = detect_table_markers(
        cv2, mapper.detector, image,
        set(mapper.reference_ids) | set(mapper.basket_ids))
    visible = [i for i in STABLE_IDS if i in corners and str(i) in previous]
    if len(visible) < 2:
        raise ValueError("arm occludes more than one stable ArUco anchor")
    centers = {i: corners[i].reshape(4, 2).mean(axis=0) for i in visible}
    drift = max(float(np.linalg.norm(centers[i] - np.asarray(previous[str(i)])))
                for i in visible)
    if drift > 2.0:
        raise ValueError(f"visible camera/table marks moved by {drift:.3f} px; register point again")
    geometry = dict(registration["aruco"])
    quality = dict(geometry["aruco_quality"])
    quality.update({"capture_occlusion_fallback": True,
                    "capture_visible_stable_ids": visible})
    geometry.update({"aruco_ids": sorted(corners),
                     "equalized_fallback_ids": fallback,
                     "aruco_quality": quality,
                     "capture_visible_centers_px": {
                         str(i): [round(float(v), 3) for v in centers[i]] for i in visible}})
    return geometry, drift


def paired_snapshot(state: CaptureState, now_ns: int | None = None) -> dict:
    now_ns = now_ns or time.monotonic_ns()
    with state.lock:
        frames = tuple(state.frames["ceiling"])
        recent = [joint for joint in state.joints if now_ns - joint.received_ns <= 1_500_000_000]
    joints = recent[-15:]
    if len(joints) < 15 or now_ns - joints[-1].received_ns > MAX_JOINT_AGE_NS:
        raise ValueError("15 fresh follower broadcasts required while teleop is active")
    if len({joint.source_unix for joint in joints}) != 15:
        raise ValueError("nonunique follower broadcast timestamps")
    std = max(statistics.pstdev(joint.joints[name] for joint in joints)
              for name in joints[-1].joints)
    if std > 0.01:
        raise ValueError("follower has not settled")
    if not frames:
        raise ValueError("ceiling frame unavailable")
    frame = min(frames, key=lambda item: abs(item.received_ns - joints[-1].received_ns))
    joint = min(joints, key=lambda item: abs(item.received_ns - frame.received_ns))
    gap = abs(frame.received_ns - joint.received_ns)
    if now_ns - frame.received_ns > MAX_FRAME_AGE_NS or gap > MAX_PAIR_GAP_NS:
        raise ValueError("camera/follower pair stale or more than 250 ms apart")
    return {"frame": frame, "joint": joint, "joint_std_rad": std,
            "receive_gap_ms": round(gap / 1e6, 3)}


def tcp_fk_mm(kinematics: UrdfKinematics, joints: dict[str, float], offset_mm: np.ndarray) -> list[float]:
    pose = kinematics.forward(joints, "base", "gripper")
    xyz = pose[:3, 3] * 1000.0 + pose[:3, :3] @ offset_mm
    if not np.isfinite(xyz).all():
        raise ValueError("nonfinite TCP FK")
    return [round(float(value), 3) for value in xyz]


class Session:
    def __init__(self, state: CaptureState, mapper: TableMapper, kinematics: UrdfKinematics,
                 offset_mm: np.ndarray | None, root: Path, lelab_url: str, workspace_sha: str,
                 table_reference: StableTableReference | None = None,
                 reference_image_sha: str | None = None,
                 model_limits: dict[str, tuple[float, float]] | None = None):
        self.state, self.mapper, self.kinematics = state, mapper, kinematics
        self.offset_mm, self.root, self.lelab_url = offset_mm, root, lelab_url
        self.workspace_sha = workspace_sha
        self.table_reference = table_reference
        self.reference_image_sha = reference_image_sha
        self.model_limits = model_limits or {}
        self.lock = threading.Lock()
        self.registered: dict[str, dict] = {}
        self.captures: dict[str, dict] = {}
        self.red_opening: dict | None = None
        self.tcp_reference: dict | None = None
        # A read-only receiver restart must not discard completed manual points.
        for point in POINTS:
            registered_path = self.root / f"registered_{point}.json"
            if registered_path.is_file():
                record = json.loads(registered_path.read_text())
                if record.get("point_id") != point:
                    raise ValueError(f"invalid saved registration for {point}")
                self.registered[point] = record
            capture_path = self.root / f"capture_{point}.json"
            if capture_path.is_file():
                record = json.loads(capture_path.read_text())
                if (record.get("point_id") != point or
                        record.get("workspace_config_sha256") != self.workspace_sha or
                        record.get("table_reference_image_sha256") != self.reference_image_sha):
                    raise ValueError(f"saved capture provenance mismatch for {point}")
                if self.offset_mm is None or not np.allclose(
                        record.get("tcp_offset_gripper_link_mm"), self.offset_mm):
                    raise ValueError(f"saved capture TCP mismatch for {point}")
                self.captures[point] = record

    def set_tcp_reference(self, offset_mm: list[float], *, physical_reference_confirmed: bool,
                          description: str) -> dict:
        if not physical_reference_confirmed:
            raise ValueError("the selected rigid physical reference must be confirmed")
        offset = np.asarray(offset_mm, dtype=float)
        if offset.shape != (3,) or not np.isfinite(offset).all() or np.linalg.norm(offset) > 200:
            raise ValueError("finite measured gripper-link TCP offset within 200 mm required")
        if not isinstance(description, str) or len(description.strip()) < 8:
            raise ValueError("describe the exact nonmoving physical point")
        with self.lock:
            if self.captures:
                raise ValueError("cannot change TCP reference after a point was captured")
            self.offset_mm = offset
            self.tcp_reference = {
                "description": description.strip(),
                "tcp_offset_gripper_link_mm": offset.tolist(),
                "physical_reference_confirmed": True,
                "source": "operator-confirmed rigid point and independently known URDF-frame offset",
            }
            self.root.mkdir(parents=True, exist_ok=True)
            (self.root / "tcp_reference.json").write_text(json.dumps(self.tcp_reference, indent=2) + "\n")
        return self.tcp_reference

    def capture_red_opening(self, opening_table_xy_mm: list[float],
                            *, physical_table_measurement_confirmed: bool) -> dict:
        """Bind one independently measured table-plane opening point to live ID4.

        A click on the raised basket rim alone is not a table-plane measurement.
        The resulting offset is restricted to this fixed camera/basket layout.
        """
        if not physical_table_measurement_confirmed:
            raise ValueError("opening table XY needs an independent physical measurement")
        opening = np.asarray(opening_table_xy_mm, dtype=float)
        if opening.shape != (2,) or not np.isfinite(opening).all():
            raise ValueError("finite measured opening table XY required")
        frame = self.state.latest_frame("ceiling")
        geometry = frame_geometry(frame.jpeg, self.mapper, [320.0, 240.0], self.table_reference)
        marker = geometry["id4_marker_table_xy_mm"]
        if marker is None:
            raise ValueError("red basket ID4 not visible")
        offset = opening - np.asarray(marker)
        record = {
            "schema_version": 1, "marker_id": 4, "color": "red", "unit": "mm",
            "opening_table_xy_mm": [round(float(v), 3) for v in opening],
            "reference_id4_marker_table_xy_mm": marker,
            "opening_offset_from_marker_table_mm": [round(float(v), 3) for v in offset],
            "opening_offset_verified": True,
            "verification_scope": "fixed_camera_and_fixed_basket_layout_only",
            "measurement": "independent physical table-plane XY; not raised-rim pixel homography",
            "aruco_ids": geometry["aruco_ids"],
            "aruco_quality": geometry["aruco_quality"],
            "frame_received_unix_ns": frame.received_unix_ns,
            "frame_sha256": hashlib.sha256(frame.jpeg).hexdigest(),
            "workspace_config_sha256": self.workspace_sha,
            "table_reference_image_sha256": self.reference_image_sha,
            "robot_enabled": False, "motion_authorized": False,
        }
        with self.lock:
            self.root.mkdir(parents=True, exist_ok=True)
            (self.root / "red_opening.json").write_text(json.dumps(record, indent=2) + "\n")
            self.red_opening = record
        return record

    def register(self, point: str, pixel: list[float]) -> dict:
        if point not in POINTS:
            raise ValueError("point must be P1–P4 or H1")
        frame = self.state.latest_frame("ceiling")
        geometry = frame_geometry(frame.jpeg, self.mapper, pixel, self.table_reference)
        record = {"point_id": point, "role": "holdout" if point == "H1" else "fit",
                  "pixel_px": [float(v) for v in pixel], "table_xy_mm": geometry["table_xy_mm"],
                  "registered_frame_received_unix_ns": frame.received_unix_ns,
                  "registered_frame_sha256": hashlib.sha256(frame.jpeg).hexdigest(),
                  "aruco": geometry}
        with self.lock:
            if point in self.captures:
                raise ValueError("captured point cannot be registered again")
            self.registered[point] = record
            self.root.mkdir(parents=True, exist_ok=True)
            (self.root / f"registered_{point}.json").write_text(json.dumps(record, indent=2) + "\n")
        return record

    def capture(self, point: str, *, stationary_confirmed: bool, alignment_confirmed: bool,
                hover_height_confirmed: bool) -> dict:
        if point not in POINTS:
            raise ValueError("point must be P1–P4 or H1")
        if not (stationary_confirmed and alignment_confirmed and hover_height_confirmed):
            raise ValueError("stationary, same physical mark and equal hover height must be confirmed")
        if self.offset_mm is None:
            raise ValueError("rigid TCP offset from gripper link is not physically verified")
        if not lelab_teleop_active(self.lelab_url):
            raise ValueError("LeLab teleoperation inactive; no capture")
        with self.lock:
            if point in self.captures:
                raise ValueError("point already captured")
            registration = self.registered.get(point)
        if registration is None:
            raise ValueError("fixed table mark pixel must be registered before hover")
        pair = paired_snapshot(self.state)
        frame, joint = pair["frame"], pair["joint"]
        geometry, drift = capture_geometry(
            frame.jpeg, self.mapper, registration, self.table_reference)
        record = {
            "point_id": point, "role": "holdout" if point == "H1" else "fit",
            "pixel_px": registration["pixel_px"], "table_xy_mm": geometry["table_xy_mm"],
            "follower_5axis_rad": {name: joint.joints[name] for name in
                                   ("Rotation", "Pitch", "Elbow", "Wrist_Pitch", "Wrist_Roll")},
            "follower_jaw_rad": joint.joints["Jaw"],
            "robot_tcp_xyz_mm": tcp_fk_mm(self.kinematics, joint.joints, self.offset_mm),
            "urdf_model_limit_warnings": urdf_model_limit_warnings(
                joint.joints, self.model_limits),
            "tcp_offset_gripper_link_mm": self.offset_mm.tolist(),
            "tcp_reference": self.tcp_reference,
            "frame_received_unix_ns": frame.received_unix_ns,
            "joint_received_unix_ns": joint.received_unix_ns,
            "joint_source_unix": joint.source_unix,
            "frame_joint_receive_gap_ms": pair["receive_gap_ms"],
            "joint_window_max_std_rad": round(pair["joint_std_rad"], 8),
            "frame_sha256": hashlib.sha256(frame.jpeg).hexdigest(),
            "aruco": geometry, "max_reference_pixel_drift": round(drift, 3),
            "workspace_config_sha256": self.workspace_sha,
            "table_reference_image_sha256": self.reference_image_sha,
            "alignment_verified": True, "hover_height_verified": True,
            "tcp_verified": True, "image_joint_synchronized": True,
            "synchronization": "receive-time pair only; camera exposure and motor sample times unknown",
            "robot_enabled": False, "motion_authorized": False,
        }
        with self.lock:
            if point in self.captures:
                raise ValueError("point already captured")
            self.root.mkdir(parents=True, exist_ok=True)
            (self.root / f"capture_{point}.json").write_text(json.dumps(record, indent=2) + "\n")
            (self.root / f"capture_{point}.jpg").write_bytes(frame.jpeg)
            self.captures[point] = record
        return record

    def fit(self) -> dict:
        with self.lock:
            if set(self.captures) != set(POINTS):
                raise ValueError("four fit points and independent H1 are required")
            records = [self.captures[name] for name in POINTS]
        heights = [record["robot_tcp_xyz_mm"][2] for record in records]
        spread = max(heights) - min(heights)
        if spread > 5.0:
            raise ValueError(f"hover TCP Z differs by {spread:.3f} mm; fit blocked")
        document = {
            "schema_version": 1, "unit": "mm", "workspace_config_sha256": self.workspace_sha,
            "table_reference_image_sha256": self.reference_image_sha,
            "tcp_offset_gripper_link_mm": self.offset_mm.tolist(), "tcp_offset_verified": True,
            "points": [{"name": record["point_id"], "role": record["role"],
                        "table_xy_mm": record["table_xy_mm"],
                        "robot_tcp_xy_mm": record["robot_tcp_xyz_mm"][:2],
                        "alignment_verified": True, "hover_height_verified": True,
                        "tcp_verified": True, "image_joint_synchronized": True}
                       for record in records],
        }
        result = fit_table_to_robot_xy(document)
        result["tcp_z_spread_mm"] = round(spread, 3)
        result["holdout_error_vector_robot_xy_mm"] = None
        if "rotation_row_xy" in result:
            h = records[-1]
            prediction = np.asarray(h["table_xy_mm"]) @ np.asarray(result["rotation_row_xy"]) + np.asarray(result["translation_xy_mm"])
            difference = prediction - np.asarray(h["robot_tcp_xyz_mm"][:2])
            result["holdout_error_vector_robot_xy_mm"] = [round(float(v), 3) for v in difference]
        result["workspace_config_sha256"] = self.workspace_sha
        result["table_reference_image_sha256"] = self.reference_image_sha
        result["robot_enabled"] = False
        result["motion_authorized"] = False
        # The IK preview revalidates the raw correspondences itself. Preserve
        # that input separately from the fit report; a matrix alone cannot
        # prove that H1 was excluded or that the workspace frame matches.
        document["robot_enabled"] = False
        document["motion_authorized"] = False
        (self.root / "table_to_robot_calibration.json").write_text(
            json.dumps(document, indent=2) + "\n")
        (self.root / "table_to_robot_fit.json").write_text(json.dumps(result, indent=2) + "\n")
        return result


PAGE = b"""<!doctype html><html lang=ko><meta charset=utf-8><title>SO-101 5-point capture</title>
<style>body{font:16px system-ui;background:#15191f;color:#eee;margin:20px}img{width:min(640px,100%);display:block;cursor:crosshair}button,select{font:inherit;padding:8px;margin:8px}pre{white-space:pre-wrap}</style>
<h2>5-point calibration capture (read only)</h2><p>First click each fixed table mark while visible. During supervised LeLab teleop, hover the same rigid point at the same height, stop, then capture once. This page cannot move the robot.</p>
<select id=p><option>P1</option><option>P2</option><option>P3</option><option>P4</option><option>H1</option></select>
<img id=frame src=/frame.jpg><label><input id=confirmed type=checkbox>Same rigid point, same hover height, fully stopped</label><button onclick=cap()>Capture stationary point</button><button onclick=fit()>Fit 4 + hold out H1</button><pre id=out></pre>
<script>const img=document.getElementById('frame'),out=document.getElementById('out');async function post(path,data){let r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});out.textContent=JSON.stringify(await r.json(),null,2)}img.onclick=e=>{let b=img.getBoundingClientRect();post('/api/register',{point:p.value,pixel:[(e.clientX-b.left)*640/b.width,(e.clientY-b.top)*480/b.height]})};function cap(){if(!confirmed.checked){out.textContent='Confirm the stationary equal-height alignment first';return}post('/api/capture',{point:p.value,stationary_confirmed:true,alignment_confirmed:true,hover_height_confirmed:true});confirmed.checked=false}function fit(){post('/api/fit',{})}setInterval(()=>{if(img.complete)img.src='/frame.jpg?t='+Date.now()},350);</script>"""


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, session: Session):
        super().__init__(address, Handler)
        self.session = session


class Handler(BaseHTTPRequestHandler):
    server: Server

    def log_message(self, fmt: str, *args: object) -> None:
        return

    def send(self, value: bytes, mime: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(value)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(value)

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        try:
            if path == "/":
                self.send(PAGE, "text/html; charset=utf-8")
            elif path == "/frame.jpg":
                self.send(self.server.session.state.latest_frame("ceiling").jpeg, "image/jpeg")
            elif path == "/api/status":
                s = self.server.session
                self.send(json.dumps({"receivers": s.state.status(), "registered": list(s.registered),
                                      "captured": list(s.captures), "tcp_ready": s.offset_mm is not None,
                                      "red_opening_measured": s.red_opening is not None,
                                      "robot_control": False}).encode(), "application/json")
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
        except ValueError as error:
            self.send(json.dumps({"error": str(error)}).encode(), "application/json", HTTPStatus.SERVICE_UNAVAILABLE)

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        if path not in ("/api/register", "/api/capture", "/api/fit", "/api/red-opening", "/api/tcp"):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            if self.headers.get_content_type() != "application/json":
                raise ValueError("JSON required")
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 1024:
                raise ValueError("invalid request size")
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict):
                raise ValueError("JSON object required")
            s = self.server.session
            if path == "/api/register":
                result = s.register(data.get("point"), data.get("pixel"))
            elif path == "/api/tcp":
                result = s.set_tcp_reference(data.get("offset_mm"),
                                             physical_reference_confirmed=data.get("physical_reference_confirmed") is True,
                                             description=data.get("description"))
            elif path == "/api/capture":
                result = s.capture(data.get("point"), stationary_confirmed=data.get("stationary_confirmed") is True,
                                   alignment_confirmed=data.get("alignment_confirmed") is True,
                                   hover_height_confirmed=data.get("hover_height_confirmed") is True)
            elif path == "/api/red-opening":
                result = s.capture_red_opening(data.get("opening_table_xy_mm"),
                                               physical_table_measurement_confirmed=data.get("physical_table_measurement_confirmed") is True)
            else:
                result = s.fit()
            self.send(json.dumps(result, ensure_ascii=False).encode(), "application/json")
        except (ValueError, OSError, TypeError, urllib.error.URLError, json.JSONDecodeError) as error:
            self.send(json.dumps({"error": str(error)}).encode(), "application/json", HTTPStatus.BAD_REQUEST)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lelab-url", default="http://192.168.50.20:8000")
    parser.add_argument("--workspace-config", type=Path, required=True)
    parser.add_argument("--urdf", type=Path, required=True)
    parser.add_argument("--reference-image", type=Path, required=True,
                        help="saved pre-drift ceiling JPEG with ID0–3")
    parser.add_argument("--tcp-offset-mm", type=float, nargs=3,
                        help="independently measured fixed point in URDF gripper-link coordinates")
    parser.add_argument("--tcp-verified", action="store_true")
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8034)
    args = parser.parse_args()
    if args.host not in ("127.0.0.1", "::1"):
        parser.error("capture server must be loopback only")
    if hashlib.sha256(args.urdf.read_bytes()).hexdigest() != URDF_SHA256:
        parser.error("installed URDF SHA mismatch")
    if args.tcp_verified != (args.tcp_offset_mm is not None):
        parser.error("TCP offset and physical verification flag must be supplied together")
    if args.tcp_offset_mm is not None and not all(math.isfinite(v) for v in args.tcp_offset_mm):
        parser.error("TCP offset must be finite")
    import websocket  # noqa: F401 - fail before binding if receiver unavailable
    state = CaptureState()
    mapper = TableMapper(args.workspace_config, cv2, np)
    reference = StableTableReference(cv2, np, mapper, args.reference_image)
    offset = None if args.tcp_offset_mm is None else np.asarray(args.tcp_offset_mm, dtype=float)
    session = Session(state, mapper, UrdfKinematics.from_file(args.urdf), offset,
                      args.output_root, args.lelab_url.rstrip("/"),
                      hashlib.sha256(args.workspace_config.read_bytes()).hexdigest(), reference,
                      hashlib.sha256(args.reference_image.read_bytes()).hexdigest(),
                      read_urdf_model_limits(args.urdf))
    stop = threading.Event()
    workers = [threading.Thread(target=camera_worker, args=(state, "ceiling", session.lelab_url, stop), daemon=True),
               threading.Thread(target=joint_worker, args=(state, session.lelab_url, stop), daemon=True)]
    server = Server((args.host, args.port), session)
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
