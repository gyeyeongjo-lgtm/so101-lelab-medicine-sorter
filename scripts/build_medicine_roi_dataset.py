#!/usr/bin/env python3
"""Derive a pickup-ROI-only bootstrap dataset without changing source images."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--crop-xyxy", type=int, nargs=4, required=True)
    return parser.parse_args()


def transform_label(
    line: str, image_size: tuple[int, int], crop_xyxy: tuple[int, int, int, int]
) -> str:
    if not line.strip():
        return ""
    parts = line.split()
    if len(parts) != 5 or parts[0] != "0":
        raise ValueError("expected exactly one class-0 xywh label")
    width, height = image_size
    x1, y1, x2, y2 = crop_xyxy
    cx, cy, bw, bh = (float(value) for value in parts[1:])
    bx1, by1 = (cx - bw / 2) * width, (cy - bh / 2) * height
    bx2, by2 = (cx + bw / 2) * width, (cy + bh / 2) * height
    tolerance = 1e-4
    if bx1 < x1 - tolerance or by1 < y1 - tolerance or bx2 > x2 + tolerance or by2 > y2 + tolerance:
        raise ValueError("positive label would be clipped by the ROI crop")
    roi_width, roi_height = x2 - x1, y2 - y1
    values = (
        (cx * width - x1) / roi_width,
        (cy * height - y1) / roi_height,
        (bw * width) / roi_width,
        (bh * height) / roi_height,
    )
    if not all(0 <= value <= 1 for value in values):
        raise ValueError("ROI label is outside normalized range")
    return "0 " + " ".join(f"{value:.8f}" for value in values) + "\n"


def main() -> int:
    args = parse_args()
    x1, y1, x2, y2 = args.crop_xyxy
    if not (0 <= x1 < x2 and 0 <= y1 < y2):
        raise ValueError("crop must satisfy non-negative x1<x2 and y1<y2")
    if args.output.exists():
        raise ValueError("output directory already exists; sources are never overwritten")

    import cv2

    images = sorted((args.source / "images").glob("*.png"))
    if not images:
        raise ValueError("source contains no PNG images")
    prepared = []
    for image_path in images:
        stem = image_path.stem
        label_path = args.source / "labels" / f"{stem}.txt"
        metadata_path = args.source / "metadata" / f"{stem}.json"
        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if image is None or not label_path.is_file() or not metadata_path.is_file():
            raise ValueError(f"incomplete source pair: {stem}")
        height, width = image.shape[:2]
        if x2 > width or y2 > height:
            raise ValueError(f"crop exceeds image bounds: {stem}")
        label = transform_label(label_path.read_text(encoding="utf-8"), (width, height), (x1, y1, x2, y2))
        prepared.append((stem, image[y1:y2, x1:x2].copy(), label))

    for kind in ("images", "labels", "metadata"):
        (args.output / kind).mkdir(parents=True)
    positive = 0
    for stem, image, label in prepared:
        if not cv2.imwrite(str(args.output / "images" / f"{stem}.png"), image):
            raise OSError(f"could not save crop: {stem}")
        (args.output / "labels" / f"{stem}.txt").write_text(label, encoding="utf-8")
        (args.output / "metadata" / f"{stem}.json").write_text(
            json.dumps(
                {
                    "source_stem": stem,
                    "source_dataset": str(args.source),
                    "crop_xyxy_original_px": [x1, y1, x2, y2],
                    "scope": "pickup_roi_only",
                    "label_status": "reviewed_bootstrap_pseudo_label" if label else "roi_negative_visual_review_required",
                    "training_ready": False,
                },
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )
        positive += bool(label)
    (args.output / "dataset.json").write_text(
        json.dumps(
            {
                "scope": "pickup_roi_only",
                "crop_xyxy_original_px": [x1, y1, x2, y2],
                "source_dataset": str(args.source),
                "positive": positive,
                "negative": len(prepared) - positive,
                "training_ready": False,
                "note": "Original full-frame negatives contain the target bottle outside the pickup ROI. Visual audit and more diverse frames are required before training.",
            },
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    print(f"ROI_DATASET output={args.output} total={len(prepared)} positive={positive} negative={len(prepared)-positive}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
