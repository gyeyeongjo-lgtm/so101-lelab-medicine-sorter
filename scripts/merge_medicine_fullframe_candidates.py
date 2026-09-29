#!/usr/bin/env python3
"""Merge provisional full-frame positives and reviewed negatives without overwrite."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--positive-source", required=True, type=Path)
    parser.add_argument("--negative-source", required=True, action="append", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def label_kind(content: str) -> str:
    if not content.strip():
        return "negative"
    parts = content.split()
    if len(parts) != 5 or parts[0] != "0":
        raise ValueError("positive label must contain one class-0 normalized xywh row")
    values = [float(value) for value in parts[1:]]
    if not all(0 < value <= 1 for value in values):
        raise ValueError("positive label values must be in (0, 1]")
    return "positive"


def collect_source(source: Path, expected_kind: str, cv2):
    images = {path.stem: path for path in (source / "images").glob("*.png")}
    labels = {path.stem: path for path in (source / "labels").glob("*.txt")}
    metadata = {path.stem: path for path in (source / "metadata").glob("*.json")}
    if not images or set(images) != set(labels) or set(images) != set(metadata):
        raise ValueError(f"incomplete source pairs: {source}")
    records = []
    for stem in sorted(images):
        image = cv2.imread(str(images[stem]), cv2.IMREAD_COLOR)
        if image is None or image.shape[:2] != (480, 640):
            raise ValueError(f"source image must be 640x480: {stem}")
        if label_kind(labels[stem].read_text(encoding="utf-8")) != expected_kind:
            raise ValueError(f"unexpected label kind in {source}: {stem}")
        meta = json.loads(metadata[stem].read_text(encoding="utf-8"))
        if meta.get("training_ready") is not False or meta.get("robot_target") is not False:
            raise ValueError(f"source safety flags are missing: {stem}")
        records.append((stem, images[stem], labels[stem], metadata[stem]))
    return records


def main():
    args = parse_args()
    if args.output.exists():
        raise ValueError("output already exists; merges never overwrite")
    import cv2

    positives = collect_source(args.positive_source, "positive", cv2)
    negatives = []
    for source in args.negative_source:
        negatives.extend(collect_source(source, "negative", cv2))
    stems = [record[0] for record in positives + negatives]
    if len(stems) != len(set(stems)):
        raise ValueError("duplicate stems across input datasets")
    for name in ("images", "labels", "metadata"):
        (args.output / name).mkdir(parents=True, exist_ok=False)
    for stem, image, label, metadata in positives + negatives:
        shutil.copy2(image, args.output / "images" / image.name)
        shutil.copy2(label, args.output / "labels" / label.name)
        shutil.copy2(metadata, args.output / "metadata" / metadata.name)
    (args.output / "dataset.json").write_text(json.dumps({
        "scope": "full_frame",
        "image_size": [640, 480],
        "positive_proposals": len(positives),
        "reviewed_negatives": len(negatives),
        "positive_source": str(args.positive_source),
        "negative_sources": [str(source) for source in args.negative_source],
        "positive_label_status": "provisional_color_based_proposal",
        "negative_label_status": "visually_reviewed_empty_label",
        "review_required": True,
        "training_ready": False,
        "medicine_identity_verified": False,
        "robot_enabled": False,
        "note": "Combined review dataset only. More diverse positives/negatives and an independent evaluation split are required before training.",
    }, indent=2) + "\n", encoding="utf-8")
    print(f"MERGED total={len(stems)} positive={len(positives)} negative={len(negatives)} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
