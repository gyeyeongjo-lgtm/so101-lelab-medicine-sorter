#!/usr/bin/env python3
"""Record a user-operated LeLab joint broadcast without controlling the robot.

This is evidence only. It never starts/stops teleoperation or opens serial ports.
The JSONL contains receive timestamps, not a controller-grade trajectory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import threading
import time
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

if __package__:
    from scripts.teach_capture_web import CAMERAS, CaptureState, JOINT_NAMES, camera_worker, parse_joint
else:
    from teach_capture_web import CAMERAS, CaptureState, JOINT_NAMES, camera_worker, parse_joint


def teleop_active(base_url: str) -> bool:
    with urllib.request.urlopen(base_url + "/teleoperation-status", timeout=2) as response:
        status = json.load(response)
    return status.get("teleoperation_active") is True


class TraceAudit:
    def __init__(self) -> None:
        self.count = 0
        self.first_receive_ns: int | None = None
        self.last_receive_ns: int | None = None
        self.last_source_unix: float | None = None
        self.max_receive_gap_ms = 0.0
        self.max_step_rad = {name: 0.0 for name in JOINT_NAMES}
        self.duplicate_or_reverse_source_times = 0
        self.last_joints: dict[str, float] | None = None

    def add(self, message: object, received_ns: int, received_unix_ns: int) -> dict | None:
        joint = parse_joint(message, received_ns, received_unix_ns)
        if joint is None:
            return None
        if self.last_receive_ns is not None:
            self.max_receive_gap_ms = max(
                self.max_receive_gap_ms, (received_ns - self.last_receive_ns) / 1e6)
        if self.last_source_unix is not None and joint.source_unix <= self.last_source_unix:
            self.duplicate_or_reverse_source_times += 1
        if self.last_joints is not None:
            for name in JOINT_NAMES:
                self.max_step_rad[name] = max(
                    self.max_step_rad[name], abs(joint.joints[name] - self.last_joints[name]))
        self.count += 1
        if self.first_receive_ns is None:
            self.first_receive_ns = received_ns
        self.last_receive_ns = received_ns
        self.last_source_unix = joint.source_unix
        self.last_joints = joint.joints
        return {"received_unix_ns": received_unix_ns, "source_unix": joint.source_unix,
                "joints_rad": joint.joints}

    def summary(self) -> dict:
        duration_s = (None if self.first_receive_ns is None or self.last_receive_ns is None
                      else round((self.last_receive_ns - self.first_receive_ns) / 1e9, 3))
        return {"sample_count": self.count, "receive_span_s": duration_s,
                "max_receive_gap_ms": round(self.max_receive_gap_ms, 3),
                "max_consecutive_step_rad": self.max_step_rad,
                "duplicate_or_reverse_source_times": self.duplicate_or_reverse_source_times}


class CameraEvidence:
    """Sample existing LeLab MJPEG receivers; do not open V4L2 devices."""

    def __init__(self, base_url: str, folder: Path, names: tuple[str, ...]):
        self.state = CaptureState()
        self.stop_event = threading.Event()
        self.threads = [
            threading.Thread(target=camera_worker, args=(self.state, name, base_url, self.stop_event), daemon=True)
            for name in names
        ]
        self.names = names
        self.folder = folder
        self.last_frame_ns = {name: None for name in names}
        self.counts = {name: 0 for name in names}
        self.indexes = {}

    def start(self) -> None:
        for name in self.names:
            (self.folder / name).mkdir()
            self.indexes[name] = (self.folder / name / "frames.jsonl").open("w", encoding="utf-8")
        for thread in self.threads:
            thread.start()

    def sample(self) -> None:
        for name in self.names:
            try:
                frame = self.state.latest_frame(name)
            except ValueError:
                continue
            if frame.received_ns == self.last_frame_ns[name]:
                continue
            filename = f"{frame.received_unix_ns}.jpg"
            (self.folder / name / filename).write_bytes(frame.jpeg)
            self.indexes[name].write(json.dumps({
                "filename": filename,
                "received_unix_ns": frame.received_unix_ns,
                "sha256": hashlib.sha256(frame.jpeg).hexdigest(),
            }, separators=(",", ":")) + "\n")
            self.indexes[name].flush()
            self.last_frame_ns[name] = frame.received_ns
            self.counts[name] += 1

    def finish(self) -> dict:
        self.stop_event.set()
        for thread in self.threads:
            thread.join(timeout=1)
        for index in self.indexes.values():
            index.close()
        status = self.state.status()
        return {
            name: {
                "frame_count": self.counts[name],
                "index_sha256": hashlib.sha256((self.folder / name / "frames.jsonl").read_bytes()).hexdigest(),
                "receiver_error_at_end": status["errors"][name],
            }
            for name in self.names
        }


def record(base_url: str, output_root: Path, max_seconds: int,
           camera_names: tuple[str, ...] = ()) -> dict:
    if not teleop_active(base_url):
        raise RuntimeError("LeLab teleoperation is inactive; no trace created")
    if any(name not in CAMERAS for name in camera_names) or len(set(camera_names)) != len(camera_names):
        raise ValueError("camera names must be unique known LeLab cameras")
    import websocket

    parts = urlsplit(base_url)
    ws_url = ("wss" if parts.scheme == "https" else "ws") + "://" + parts.netloc + "/ws/joint-data"
    socket = websocket.create_connection(ws_url, timeout=2)
    socket.settimeout(0.25)
    stem = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ") + "_" + uuid.uuid4().hex[:8]
    folder = output_root / stem
    audit = TraceAudit()
    cameras = CameraEvidence(base_url, folder, camera_names) if camera_names else None
    camera_summary = {}
    cameras_started = False
    reason = "max_duration"
    started_ns = time.monotonic_ns()
    next_status_ns = started_ns
    next_camera_ns = started_ns
    try:
        folder.mkdir(parents=True, exist_ok=False)
        if cameras is not None:
            cameras.start()
            cameras_started = True
        with (folder / "joints.jsonl").open("w", encoding="utf-8") as output:
            while time.monotonic_ns() - started_ns < max_seconds * 1_000_000_000:
                now_ns = time.monotonic_ns()
                if cameras is not None and now_ns >= next_camera_ns:
                    cameras.sample()
                    next_camera_ns = now_ns + 200_000_000
                if now_ns >= next_status_ns:
                    try:
                        active = teleop_active(base_url)
                    except (OSError, ValueError) as error:
                        reason = "status_unavailable: " + str(error)[:120]
                        break
                    if not active:
                        reason = "teleoperation_inactive"
                        break
                    next_status_ns = now_ns + 500_000_000
                try:
                    payload = socket.recv()
                except websocket.WebSocketTimeoutException:
                    continue
                if not payload:
                    reason = "joint_stream_closed"
                    break
                received_ns = time.monotonic_ns()
                received_unix_ns = time.time_ns()
                try:
                    message = json.loads(payload)
                except (json.JSONDecodeError, TypeError):
                    continue
                sample = audit.add(message, received_ns, received_unix_ns)
                if sample is not None:
                    output.write(json.dumps(sample, separators=(",", ":")) + "\n")
                    output.flush()
    except KeyboardInterrupt:
        reason = "operator_interrupted"
    except (OSError, websocket.WebSocketException) as error:
        reason = "joint_stream_error: " + str(error)[:120]
    finally:
        socket.close()
        if cameras_started:
            camera_summary = cameras.finish()
    raw = (folder / "joints.jsonl").read_bytes()
    manifest = {
        "schema_version": 1, "capture_kind": "user_operated_teleop_joint_observation",
        "stop_reason": reason, "joint_file": "joints.jsonl",
        "joint_file_sha256": hashlib.sha256(raw).hexdigest(), **audit.summary(),
        "source": "/ws/joint-data", "timing": "Mac receive-time; not motor command or camera exposure-time",
        "camera_video_recorded": any(item["frame_count"] for item in camera_summary.values()),
        "camera_evidence_complete": bool(camera_names) and all(
            camera_summary.get(name, {}).get("frame_count", 0) > 0 for name in camera_names),
        "camera_evidence": camera_summary,
        "camera_timing": "Mac receive-time samples; not synchronized exposure-time video",
        "use_for_replay": False,
        "robot_enabled": False, "motion_authorized": False,
    }
    (folder / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return {"folder": str(folder), **manifest}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lelab-url", default="http://192.168.50.20:8000")
    parser.add_argument("--output-root", type=Path, default=Path(".local/teleop-traces"))
    parser.add_argument("--max-seconds", type=int, default=180)
    parser.add_argument("--camera-evidence", action="store_true",
                        help="Sample ceiling and oblique LeLab MJPEG frames into the ignored trace folder")
    args = parser.parse_args()
    parts = urlsplit(args.lelab_url)
    if parts.scheme not in ("http", "https") or not parts.netloc or parts.path not in ("", "/"):
        parser.error("--lelab-url must be an HTTP(S) origin without a path")
    if not 1 <= args.max_seconds <= 300:
        parser.error("--max-seconds must be 1–300")
    try:
        result = record(args.lelab_url.rstrip("/"), args.output_root, args.max_seconds,
                        ("ceiling", "oblique") if args.camera_evidence else ())
    except (OSError, RuntimeError, ImportError) as error:
        parser.exit(2, f"trace not started: {error}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
