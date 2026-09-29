#!/usr/bin/env python3
"""File-backed, camera-only medicine capture and review queue.

The queue never opens a camera, controls a robot, or marks a dataset as
training-ready. It receives a fresh JPEG from the existing preview service.
"""

from __future__ import annotations

import json
import math
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

REFERENCE_IDS = {0, 1, 2, 3}
SEARCH_XYXY = (180, 175, 480, 315)
STEM_PATTERN = re.compile(r"[A-Za-z0-9_-]+")


def atomic_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def marker_centers(frame) -> dict[int, tuple[float, float]]:
    import cv2

    detector = cv2.aruco.ArucoDetector(
        cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50),
        cv2.aruco.DetectorParameters(),
    )
    found: dict[int, tuple[float, float]] = {}
    for scale in (1, 2, 3):
        view = frame if scale == 1 else cv2.resize(
            frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR
        )
        corners, ids, _ = detector.detectMarkers(view)
        if ids is None:
            continue
        for corner, marker_id in zip(corners, ids.flatten()):
            marker_id = int(marker_id)
            if marker_id in REFERENCE_IDS and marker_id not in found:
                center = corner.reshape(4, 2).mean(axis=0) / scale
                found[marker_id] = (float(center[0]), float(center[1]))
        if set(found) == REFERENCE_IDS:
            break
    return found


def eligible_bodies(stats) -> list[list[int]]:
    bodies = []
    for row in stats:
        x, y, width, height, area = (int(value) for value in row)
        if 100 <= area <= 1000 and 8 <= width <= 45 and 8 <= height <= 60:
            bodies.append([x, y, width, height])
    return sorted(bodies)


def purple_bodies(frame) -> list[list[int]]:
    import cv2
    import numpy as np

    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(
        hsv,
        np.array((120, 70, 20), dtype=np.uint8),
        np.array((160, 255, 255), dtype=np.uint8),
    )
    _, _, stats, _ = cv2.connectedComponentsWithStats(mask)
    return [body for body in eligible_bodies(stats[1:]) if body_in_workspace(body)]


def proposed_bbox(body: list[int], image_size: tuple[int, int] = (640, 480)) -> list[int]:
    x, y, width, height = body
    image_width, image_height = image_size
    x1, y1 = x - 5, y - 18
    x2, y2 = x + width + 5, y + height + 3
    if x1 < 0 or y1 < 0 or x2 > image_width or y2 > image_height:
        raise ValueError("제안 박스가 화면 밖입니다")
    return [x1, y1, x2 - x1, y2 - y1]


def body_in_workspace(body: list[int]) -> bool:
    x, y, _, _ = body
    x1, y1, x2, y2 = SEARCH_XYXY
    return x1 <= x <= x2 and y1 <= y <= y2


def bbox_center(box: list[int]) -> tuple[float, float]:
    return box[0] + box[2] / 2, box[1] + box[3] / 2


def yolo_label(box: list[int], image_size: tuple[int, int] = (640, 480)) -> str:
    x, y, width, height = box
    image_width, image_height = image_size
    values = (
        (x + width / 2) / image_width,
        (y + height / 2) / image_height,
        width / image_width,
        height / image_height,
    )
    return "0 " + " ".join(f"{value:.8f}" for value in values) + "\n"


class MedicineReviewStore:
    def __init__(
        self,
        root: Path,
        reference_positive: Path | None = None,
        near_duplicate_px: float = 12.0,
    ) -> None:
        self.root = root
        self.reference_positive = reference_positive
        if near_duplicate_px <= 0:
            raise ValueError("near_duplicate_px는 0보다 커야 합니다")
        self.near_duplicate_px = float(near_duplicate_px)
        self._lock = threading.Lock()
        for folder in ("images", "overlays", "metadata", "exports/images", "exports/labels", "exports/metadata"):
            (root / folder).mkdir(parents=True, exist_ok=True)

    def _new_stem(self) -> str:
        base = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
        stem = base
        counter = 1
        while (self.root / "metadata" / f"{stem}.json").exists():
            counter += 1
            stem = f"{base}_{counter}"
        return stem

    def _known_centers(self) -> list[tuple[float, float]]:
        centers = []
        roots = [self.root / "exports" / "metadata"]
        if self.reference_positive is not None:
            roots.append(self.reference_positive / "metadata")
        for root in roots:
            if not root.is_dir():
                continue
            for path in root.glob("*.json"):
                try:
                    metadata = json.loads(path.read_text(encoding="utf-8"))
                    box = metadata.get("bbox_xywh") or metadata.get("bbox_xywh_640x480")
                    if isinstance(box, list) and len(box) == 4:
                        centers.append(bbox_center(box))
                except (OSError, ValueError, TypeError, json.JSONDecodeError):
                    continue
        return centers

    def capture(self, jpeg: bytes, expected: str) -> dict:
        import cv2
        import numpy as np

        if expected not in {"positive", "negative"}:
            raise ValueError("expected는 positive 또는 negative여야 합니다")
        frame = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is None or frame.shape[:2] != (480, 640):
            raise ValueError("Astra 최신 frame이 640x480 BGR이 아닙니다")
        references = marker_centers(frame)
        bodies = purple_bodies(frame)
        bbox = None
        nearest = None
        reasons = []
        if set(references) != REFERENCE_IDS:
            reasons.append("reference_markers_missing")
        if expected == "positive":
            if len(bodies) != 1:
                reasons.append("workspace_target_count_not_one")
            else:
                bbox = proposed_bbox(bodies[0])
                known = self._known_centers()
                if known:
                    center = bbox_center(bbox)
                    nearest = min(math.dist(center, item) for item in known)
                    if nearest < self.near_duplicate_px:
                        reasons.append("near_duplicate")
        elif bodies:
            reasons.append("target_present_in_negative")
        status = "pending_review" if not reasons else "blocked"
        with self._lock:
            stem = self._new_stem()
            image_path = self.root / "images" / f"{stem}.png"
            overlay_path = self.root / "overlays" / f"{stem}.png"
            overlay = frame.copy()
            for body in bodies:
                x, y, width, height = body
                cv2.rectangle(overlay, (x, y), (x + width - 1, y + height - 1), (0, 165, 255), 1)
            if bbox is not None:
                x, y, width, height = bbox
                cv2.rectangle(overlay, (x, y), (x + width - 1, y + height - 1), (0, 0, 255), 2)
            if not cv2.imwrite(str(image_path), frame) or not cv2.imwrite(str(overlay_path), overlay):
                raise OSError("검토 이미지를 저장하지 못했습니다")
            metadata = {
                "stem": stem,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "expected": expected,
                "status": status,
                "block_reasons": reasons,
                "reference_ids": sorted(references),
                "reference_centers": {str(key): list(value) for key, value in references.items()},
                "workspace_purple_body_candidates": bodies,
                "bbox_xywh_640x480": bbox,
                "nearest_positive_center_px": None if nearest is None else round(nearest, 3),
                "near_duplicate_threshold_px": self.near_duplicate_px,
                "review_note": None,
                "training_ready": False,
                "medicine_identity_verified": False,
                "robot_target": False,
            }
            atomic_json(self.root / "metadata" / f"{stem}.json", metadata)
        return metadata

    def items(self) -> list[dict]:
        records = []
        for path in sorted((self.root / "metadata").glob("*.json"), reverse=True):
            try:
                records.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                continue
        return records

    def summary(self) -> dict:
        records = self.items()
        counts = {"total": len(records), "pending": 0, "approved": 0, "excluded": 0, "blocked": 0}
        for record in records:
            status = record.get("status")
            key = "pending" if status == "pending_review" else status
            if key in counts:
                counts[key] += 1
        return {"counts": counts, "items": records[:100], "training_ready": False, "robot_enabled": False}

    def decide(self, stem: str, decision: str, note: str) -> dict:
        if not STEM_PATTERN.fullmatch(stem):
            raise ValueError("잘못된 stem입니다")
        if decision not in {"approve", "exclude"}:
            raise ValueError("decision은 approve 또는 exclude여야 합니다")
        path = self.root / "metadata" / f"{stem}.json"
        with self._lock:
            if not path.is_file():
                raise FileNotFoundError(stem)
            metadata = json.loads(path.read_text(encoding="utf-8"))
            if metadata["status"] in {"approved", "excluded"}:
                raise ValueError("이미 검토가 끝난 항목입니다")
            if decision == "approve" and metadata["status"] == "blocked":
                raise ValueError("자동 차단된 항목은 승인할 수 없습니다")
            metadata["status"] = "approved" if decision == "approve" else "excluded"
            metadata["review_note"] = note.strip() or None
            metadata["reviewed_at"] = datetime.now(timezone.utc).isoformat()
            if decision == "approve":
                source = self.root / "images" / f"{stem}.png"
                image_target = self.root / "exports" / "images" / f"{stem}.png"
                image_target.write_bytes(source.read_bytes())
                box = metadata.get("bbox_xywh_640x480")
                label = yolo_label(box) if metadata["expected"] == "positive" else ""
                (self.root / "exports" / "labels" / f"{stem}.txt").write_text(label, encoding="utf-8")
                export_metadata = dict(metadata)
                export_metadata.update({
                    "scope": "full_frame",
                    "class_id": 0,
                    "class_name": "white_medicine_bottle_model",
                    "label_status": "human_reviewed_web_capture",
                })
                atomic_json(self.root / "exports" / "metadata" / f"{stem}.json", export_metadata)
            atomic_json(path, metadata)
        return metadata
