#!/usr/bin/env python3
"""Record a user-operated LeLab joint broadcast without controlling the robot.

This is evidence only. It never starts/stops teleoperation or opens serial ports.
The JSONL contains receive timestamps, not a controller-grade trajectory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

if __package__:
    from scripts.teach_capture_web import JOINT_NAMES, parse_joint
else:
    from teach_capture_web import JOINT_NAMES, parse_joint


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


def record(base_url: str, output_root: Path, max_seconds: int) -> dict:
    if not teleop_active(base_url):
        raise RuntimeError("LeLab teleoperation is inactive; no trace created")
    import websocket

    parts = urlsplit(base_url)
    ws_url = ("wss" if parts.scheme == "https" else "ws") + "://" + parts.netloc + "/ws/joint-data"
    socket = websocket.create_connection(ws_url, timeout=2)
    socket.settimeout(0.25)
    stem = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ") + "_" + uuid.uuid4().hex[:8]
    folder = output_root / stem
    audit = TraceAudit()
    reason = "max_duration"
    started_ns = time.monotonic_ns()
    next_status_ns = started_ns
    try:
        folder.mkdir(parents=True, exist_ok=False)
        with (folder / "joints.jsonl").open("w", encoding="utf-8") as output:
            while time.monotonic_ns() - started_ns < max_seconds * 1_000_000_000:
                now_ns = time.monotonic_ns()
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
    raw = (folder / "joints.jsonl").read_bytes()
    manifest = {
        "schema_version": 1, "capture_kind": "user_operated_teleop_joint_observation",
        "stop_reason": reason, "joint_file": "joints.jsonl",
        "joint_file_sha256": hashlib.sha256(raw).hexdigest(), **audit.summary(),
        "source": "/ws/joint-data", "timing": "Mac receive-time; not motor command or camera exposure-time",
        "camera_video_recorded": False, "use_for_replay": False,
        "robot_enabled": False, "motion_authorized": False,
    }
    (folder / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return {"folder": str(folder), **manifest}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lelab-url", default="http://192.168.50.20:8000")
    parser.add_argument("--output-root", type=Path, default=Path(".local/teleop-traces"))
    parser.add_argument("--max-seconds", type=int, default=180)
    args = parser.parse_args()
    parts = urlsplit(args.lelab_url)
    if parts.scheme not in ("http", "https") or not parts.netloc or parts.path not in ("", "/"):
        parser.error("--lelab-url must be an HTTP(S) origin without a path")
    if not 1 <= args.max_seconds <= 300:
        parser.error("--max-seconds must be 1–300")
    try:
        result = record(args.lelab_url.rstrip("/"), args.output_root, args.max_seconds)
    except (OSError, RuntimeError, ImportError) as error:
        parser.exit(2, f"trace not started: {error}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
