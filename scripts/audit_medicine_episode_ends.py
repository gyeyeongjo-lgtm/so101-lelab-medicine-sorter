#!/usr/bin/env python3
"""Read-only LeRobot v3 episode-end contact sheet for human review.

The script never opens cameras or robot controls. It deliberately reports
marker visibility and frames, not task success or medicine identity.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


CAMERA = "observation.images.ceiling_vertical"


def episode_video(root: Path, row: dict, camera: str) -> Path:
    key = f"videos/{camera}"
    chunk = int(row[f"{key}/chunk_index"])
    file = int(row[f"{key}/file_index"])
    if chunk < 0 or file < 0:
        raise ValueError("negative video index")
    return root / "videos" / camera / f"chunk-{chunk:03d}" / f"file-{file:03d}.mp4"


def end_target(row: dict, camera: str, fps: float) -> float:
    key = f"videos/{camera}"
    start = float(row[f"{key}/from_timestamp"])
    stop = float(row[f"{key}/to_timestamp"])
    if fps <= 0 or stop <= start:
        raise ValueError("invalid episode timing")
    return max(start, stop - 1.0 / fps)


def frame_at_or_before(video: Path, target_s: float, av):
    with av.open(str(video), mode="r") as container:
        stream = container.streams.video[0]
        stream.thread_type = "AUTO"
        seek_pts = max(0, int(max(0.0, target_s - 0.1) / float(stream.time_base)))
        container.seek(seek_pts, stream=stream, backward=True)
        selected = None
        for frame in container.decode(stream):
            timestamp = frame.time
            if timestamp is None:
                continue
            if timestamp <= target_s + 1e-3:
                selected = frame
            if timestamp >= target_s:
                break
        if selected is None:
            raise ValueError(f"no frame before {target_s:.3f}s in {video}")
        return selected.to_ndarray(format="bgr24"), float(selected.time)


def detect_marker_ids(image, cv2):
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    if hasattr(cv2.aruco, "ArucoDetector"):
        corners, ids, _ = cv2.aruco.ArucoDetector(dictionary).detectMarkers(image)
    else:
        corners, ids, _ = cv2.aruco.detectMarkers(image, dictionary)
    return (sorted(int(value) for value in ids.reshape(-1)) if ids is not None else []), corners, ids


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path,
                        help="new directory; existing paths are refused")
    parser.add_argument("--camera", default=CAMERA)
    parser.add_argument("--fps", type=float, default=30.0)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--limit", type=int, default=60)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output already exists; no overwrite")
    if args.start < 0 or args.limit <= 0 or args.fps <= 0:
        parser.error("invalid start, limit, or fps")

    import av
    import cv2
    import numpy as np
    import pyarrow.parquet as pq

    metadata = args.dataset / "meta/episodes/chunk-000/file-000.parquet"
    if not metadata.is_file():
        raise FileNotFoundError(metadata)
    prefix = f"videos/{args.camera}"
    columns = ["episode_index", "length"] + [
        f"{prefix}/{field}" for field in
        ("chunk_index", "file_index", "from_timestamp", "to_timestamp")
    ]
    rows = pq.read_table(metadata, columns=columns).to_pylist()
    selected = rows[args.start:args.start + args.limit]
    if not selected:
        raise ValueError("no episodes selected")

    args.output.mkdir(parents=True, exist_ok=False)
    width, height, cols = 320, 260, 5
    grid = np.zeros((height * ((len(selected) + cols - 1) // cols), width * cols, 3),
                    dtype=np.uint8)
    report = []
    for position, row in enumerate(selected):
        video = episode_video(args.dataset, row, args.camera)
        if not video.is_file():
            raise FileNotFoundError(video)
        target = end_target(row, args.camera, args.fps)
        frame, timestamp = frame_at_or_before(video, target, av)
        if abs(timestamp - target) > 0.25:
            raise ValueError(f"frame timestamp too far from target: {timestamp}, {target}")
        ids, corners, raw_ids = detect_marker_ids(frame, cv2)
        tile = cv2.resize(frame, (width, 240), interpolation=cv2.INTER_AREA)
        if raw_ids is not None:
            scale_x, scale_y = width / frame.shape[1], 240 / frame.shape[0]
            for marker, marker_id in zip(corners, raw_ids.reshape(-1)):
                points = marker.reshape(-1, 2).copy()
                points[:, 0] *= scale_x
                points[:, 1] *= scale_y
                points = points.astype(np.int32)
                cv2.polylines(tile, [points], True, (0, 255, 0), 1)
                cv2.putText(tile, str(int(marker_id)), tuple(points[0]),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        cv2.putText(grid, f"ep {row['episode_index']:02d} IDs {','.join(map(str, ids))}",
                    ((position % cols) * width + 3, (position // cols) * height + 254),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.43, (255, 255, 255), 1)
        grid[(position // cols) * height:(position // cols) * height + 240,
             (position % cols) * width:(position % cols + 1) * width] = tile
        report.append({
            "episode": int(row["episode_index"]),
            "video": str(video.relative_to(args.dataset)),
            "target_s": round(target, 4),
            "frame_s": round(timestamp, 4),
            "marker_ids": ids,
            "task_success": "NOT_VERIFIED",
        })

    sheet = args.output / "episode_ends.jpg"
    if not cv2.imwrite(str(sheet), grid, [cv2.IMWRITE_JPEG_QUALITY, 90]):
        raise OSError(f"failed to write {sheet}")
    (args.output / "manifest.json").write_text(json.dumps({
        "dataset": str(args.dataset),
        "camera": args.camera,
        "read_only_source": True,
        "motion_authorized": False,
        "episodes": report,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(report)} episode end frames extracted into {sheet}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
