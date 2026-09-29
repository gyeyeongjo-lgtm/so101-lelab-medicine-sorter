#!/usr/bin/env python3
"""Collect diverse ChArUco views and calculate camera intrinsics."""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import subprocess
import time


def normalize_camera_source(value: str | int) -> str | int:
    if isinstance(value, int):
        return value
    if value.isdecimal():
        return int(value)
    prefix = "/dev/video"
    if value.startswith(prefix) and value[len(prefix) :].isdecimal():
        return int(value[len(prefix) :])
    return value


def read_exact(stream: object, size: int) -> bytes | None:
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        chunk = stream.read(remaining)
        if not chunk:
            return None
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


class OpenNIPipeCapture:
    """OpenCV-like capture wrapper for the Astra RGB raw-frame helper."""

    def __init__(self, binary: str, width: int, height: int) -> None:
        self.width = width
        self.height = height
        environment = os.environ.copy()
        environment["OPENNI2_REDIST"] = "/opt/orbbec-openni2"
        old_library_path = environment.get("LD_LIBRARY_PATH")
        environment["LD_LIBRARY_PATH"] = "/opt/orbbec-openni2" + (
            f":{old_library_path}" if old_library_path else ""
        )
        self.process = subprocess.Popen([binary], stdout=subprocess.PIPE, env=environment)

    def isOpened(self) -> bool:
        return self.process.poll() is None and self.process.stdout is not None

    def read(self):
        import cv2
        import numpy as np

        if self.process.stdout is None:
            return False, None
        raw = read_exact(self.process.stdout, self.width * self.height * 3)
        if raw is None:
            return False, None
        rgb = np.frombuffer(raw, dtype=np.uint8).reshape((self.height, self.width, 3))
        return True, cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

    def release(self) -> None:
        if self.process.stdout is not None:
            self.process.stdout.close()
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=2)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--camera", default="/dev/video4")
    parser.add_argument(
        "--openni-pipe",
        help="Raw RGB888 frame helper for an OpenNI camera; bypasses --camera/--fourcc",
    )
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--fourcc", default="MJPG", help="four-character V4L2 pixel format")
    parser.add_argument("--duration", type=float, default=60.0)
    parser.add_argument("--min-corners", type=int, default=12)
    parser.add_argument("--max-samples", type=int, default=30)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--calibration-out", type=Path, required=True)
    args = parser.parse_args()
    if len(args.fourcc) != 4:
        parser.error("--fourcc must contain exactly four characters")

    import cv2
    import numpy as np

    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    marker_ids = np.arange(10, 34, dtype=np.int32)
    board = cv2.aruco.CharucoBoard((6, 8), 30.0, 22.0, dictionary, marker_ids)
    detector = cv2.aruco.CharucoDetector(board)
    board_corners = board.getChessboardCorners().astype(np.float32)

    source = "openni-astra" if args.openni_pipe else normalize_camera_source(args.camera)
    if args.openni_pipe:
        if (args.width, args.height) != (640, 480):
            parser.error("the OpenNI RGB helper currently supports only 640x480")
        capture = OpenNIPipeCapture(args.openni_pipe, args.width, args.height)
    else:
        capture = cv2.VideoCapture(source, cv2.CAP_V4L2)
        capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*args.fourcc))
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
        capture.set(cv2.CAP_PROP_FPS, 30)
    if not capture.isOpened():
        raise RuntimeError(f"Could not open camera: {source}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    object_points = []
    image_points = []
    accepted_ids = []
    signatures = []
    previous = None
    stable_frames = 0
    last_saved = 0.0
    observed_frames = 0

    print("CAPTURE_START", flush=True)
    started = time.monotonic()
    try:
        while time.monotonic() - started < args.duration and len(image_points) < args.max_samples:
            ok, frame = capture.read()
            if not ok:
                continue
            observed_frames += 1
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            charuco_corners, charuco_ids, _, _ = detector.detectBoard(gray)
            if charuco_ids is None or len(charuco_ids) < args.min_corners:
                previous = None
                stable_frames = 0
                continue

            ids = charuco_ids.reshape(-1).astype(np.int32)
            points = charuco_corners.reshape(-1, 2).astype(np.float32)
            current = {int(marker_id): point for marker_id, point in zip(ids, points)}
            if previous is not None:
                common = sorted(set(previous).intersection(current))
                if len(common) >= 8:
                    displacement = np.mean(
                        [np.linalg.norm(current[key] - previous[key]) for key in common]
                    )
                    stable_frames = stable_frames + 1 if displacement < 1.5 else 0
                else:
                    stable_frames = 0
            previous = current
            if stable_frames < 3 or time.monotonic() - last_saved < 1.0:
                continue

            selected_objects = board_corners[ids]
            homography, _ = cv2.findHomography(selected_objects[:, :2], points)
            if homography is None:
                continue
            outline = np.asarray([[[0.0, 0.0], [180.0, 0.0], [180.0, 240.0], [0.0, 240.0]]], dtype=np.float32)
            projected = cv2.perspectiveTransform(outline, homography).reshape(-1, 2)
            signature = projected / np.asarray([args.width, args.height], dtype=np.float32)
            if signatures:
                difference = min(
                    float(np.sqrt(np.mean((signature - old_signature) ** 2)))
                    for old_signature in signatures
                )
                if difference < 0.018:
                    continue

            object_points.append(selected_objects.copy())
            image_points.append(points.reshape(-1, 1, 2).copy())
            accepted_ids.append(ids.tolist())
            signatures.append(signature.copy())
            last_saved = time.monotonic()
            filename = args.output_dir / f"view_{len(image_points):02d}.jpg"
            cv2.imwrite(str(filename), frame)
            print(
                f"CAPTURED {len(image_points)}/{args.max_samples} corners={len(ids)}",
                flush=True,
            )
    finally:
        capture.release()

    if len(image_points) < 10:
        raise RuntimeError(f"Only {len(image_points)} diverse views captured; need at least 10")

    rms, camera_matrix, distortion, rotations, translations = cv2.calibrateCamera(
        object_points,
        image_points,
        (args.width, args.height),
        None,
        None,
    )
    per_view_rms = []
    for objects, images, rotation, translation in zip(
        object_points, image_points, rotations, translations
    ):
        projected, _ = cv2.projectPoints(
            objects, rotation, translation, camera_matrix, distortion
        )
        difference = images.reshape(-1, 2) - projected.reshape(-1, 2)
        per_view_rms.append(float(math.sqrt(np.mean(np.sum(difference * difference, axis=1)))))

    calibration = {
        "camera": str(source),
        "fourcc": "RGB888" if args.openni_pipe else args.fourcc,
        "image_size": [args.width, args.height],
        "camera_matrix": camera_matrix.tolist(),
        "dist_coeffs": distortion.reshape(-1).tolist(),
        "reprojection_rms_px": float(rms),
        "per_view_rms_px": per_view_rms,
        "per_view_rms_mean_px": float(np.mean(per_view_rms)),
        "per_view_rms_max_px": float(np.max(per_view_rms)),
        "captured_views": len(image_points),
        "observed_frames": observed_frames,
        "corners_per_view": [len(ids) for ids in accepted_ids],
        "board": {
            "dictionary": "DICT_4X4_50",
            "squares": [6, 8],
            "square_length_mm": 30.0,
            "marker_length_mm": 22.0,
            "marker_ids": [10, 33],
        },
    }
    args.calibration_out.parent.mkdir(parents=True, exist_ok=True)
    args.calibration_out.write_text(
        json.dumps(calibration, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(calibration, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", flush=True)
        raise SystemExit(1)
