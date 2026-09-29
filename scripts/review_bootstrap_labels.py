#!/usr/bin/env python3
"""Review whole-object boxes in a local bootstrap dataset; never controls a robot."""

from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import tempfile
from pathlib import Path

from depth_foreground_candidates import bbox_to_yolo, validate_reviewed_bbox


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--reviews", required=True, type=Path)
    parser.add_argument("--backup-dir", type=Path)
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args()


def prepare_review(
    metadata: dict, reviewed_bbox: list[int], note: str, width: int, height: int
) -> tuple[str, dict]:
    selected = metadata.get("selected_candidate")
    if not isinstance(selected, dict) or not isinstance(selected.get("bbox_xywh"), list):
        raise ValueError("metadata requires a selected depth candidate")
    if not isinstance(reviewed_bbox, list) or len(reviewed_bbox) != 4 or not all(
        isinstance(value, int) and not isinstance(value, bool) for value in reviewed_bbox
    ):
        raise ValueError("reviewed bbox must contain four integer xywh values")
    if not isinstance(note, str) or not note.strip():
        raise ValueError("review note is required")
    source_bbox = selected["bbox_xywh"]
    validate_reviewed_bbox(reviewed_bbox, source_bbox, width, height)
    previous = metadata.get("yolo_pseudo_label")
    if not isinstance(previous, dict) or previous.get("class_id") != 0:
        raise ValueError("only existing class-0 positive labels can be reviewed")
    margin = previous.get("bbox_margin_px")
    if not isinstance(margin, int) or margin < 0:
        raise ValueError("existing bbox margin is invalid")
    values = bbox_to_yolo(reviewed_bbox, width, height, margin)
    updated = copy.deepcopy(metadata)
    updated.setdefault("label_review_history", []).append(copy.deepcopy(previous))
    updated["yolo_pseudo_label"] = {
        "class_id": 0,
        "bbox_margin_px": margin,
        "normalized_xywh": [round(value, 8) for value in values],
        "review_required": True,
        "source_candidate_bbox_xywh": source_bbox,
        "reviewed_bbox_xywh": reviewed_bbox,
        "review_note": note.strip(),
    }
    label = "0 " + " ".join(f"{value:.8f}" for value in values) + "\n"
    return label, updated


def atomic_write(path: Path, content: str) -> None:
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as handle:
        temp_path = Path(handle.name)
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def main() -> int:
    args = parse_args()
    if args.apply and args.backup_dir is None:
        raise ValueError("--apply requires --backup-dir")
    reviews = json.loads(args.reviews.read_text(encoding="utf-8"))
    if not isinstance(reviews, dict) or not reviews:
        raise ValueError("reviews must be a non-empty object keyed by image stem")
    if args.backup_dir is not None and args.backup_dir.exists():
        raise ValueError("backup directory must not already exist")

    import cv2

    prepared = []
    for stem, review in sorted(reviews.items()):
        if not isinstance(stem, str) or not stem.startswith("pose_"):
            raise ValueError(f"invalid positive stem: {stem!r}")
        if not isinstance(review, dict):
            raise ValueError(f"review for {stem} must be an object")
        image_path = args.dataset / "images" / f"{stem}.png"
        label_path = args.dataset / "labels" / f"{stem}.txt"
        metadata_path = args.dataset / "metadata" / f"{stem}.json"
        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if image is None or not label_path.is_file() or not metadata_path.is_file():
            raise ValueError(f"incomplete dataset pair: {stem}")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        label, updated = prepare_review(
            metadata, review.get("bbox_xywh"), review.get("note"), image.shape[1], image.shape[0]
        )
        if not label_path.read_text(encoding="utf-8").strip():
            raise ValueError(f"cannot review a negative label: {stem}")
        prepared.append((stem, label_path, metadata_path, label, updated))
        print(f"{stem}: {label.strip()} bbox={review['bbox_xywh']}")

    if not args.apply:
        print(f"DRY_RUN reviewed={len(prepared)}; no dataset files changed")
        return 0

    assert args.backup_dir is not None
    (args.backup_dir / "labels").mkdir(parents=True)
    (args.backup_dir / "metadata").mkdir()
    for stem, label_path, metadata_path, _, _ in prepared:
        shutil.copy2(label_path, args.backup_dir / "labels" / f"{stem}.txt")
        shutil.copy2(metadata_path, args.backup_dir / "metadata" / f"{stem}.json")
    for _, label_path, metadata_path, label, updated in prepared:
        atomic_write(label_path, label)
        atomic_write(metadata_path, json.dumps(updated, indent=2, ensure_ascii=False) + "\n")
    print(f"APPLIED reviewed={len(prepared)} backup={args.backup_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
