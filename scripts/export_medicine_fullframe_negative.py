#!/usr/bin/env python3
"""Export one visually reviewed empty full-frame medicine negative."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-image", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--stem", default="empty_fullframe_001")
    return parser.parse_args()


def eligible_body_boxes(stats):
    boxes = []
    for row in stats:
        x, y, width, height, area = (int(value) for value in row)
        if (
            100 <= area <= 1000
            and 180 <= x <= 480
            and 175 <= y <= 315
            and 8 <= width <= 45
            and 8 <= height <= 60
        ):
            boxes.append([x, y, width, height])
    return boxes


def main():
    args = parse_args()
    if args.output.exists():
        raise ValueError("output already exists; negatives never overwrite")
    if not args.stem or "/" in args.stem:
        raise ValueError("invalid output stem")
    import cv2
    import numpy as np

    image = cv2.imread(str(args.source_image), cv2.IMREAD_COLOR)
    if image is None or image.shape[:2] != (480, 640):
        raise ValueError("source image must be 640x480")
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(
        hsv,
        np.array((120, 70, 20), dtype=np.uint8),
        np.array((160, 255, 255), dtype=np.uint8),
    )
    _, _, stats, _ = cv2.connectedComponentsWithStats(mask)
    bodies = eligible_body_boxes(stats[1:])
    if bodies:
        raise ValueError(f"possible target bottle bodies remain: {bodies}")

    for name in ("images", "labels", "metadata"):
        (args.output / name).mkdir(parents=True, exist_ok=False)
    shutil.copy2(args.source_image, args.output / "images" / f"{args.stem}.png")
    (args.output / "labels" / f"{args.stem}.txt").write_text("", encoding="utf-8")
    (args.output / "metadata" / f"{args.stem}.json").write_text(json.dumps({
        "source_image": str(args.source_image),
        "scope": "full_frame",
        "image_size": [640, 480],
        "class_id": 0,
        "class_name": "white_medicine_bottle_model",
        "label_status": "visually_reviewed_empty_negative",
        "automatic_body_candidates": 0,
        "review_required": False,
        "training_ready": False,
        "medicine_identity_verified": False,
        "robot_target": False,
    }, indent=2) + "\n", encoding="utf-8")
    (args.output / "dataset.json").write_text(json.dumps({
        "scope": "full_frame",
        "image_size": [640, 480],
        "positive": 0,
        "negative": 1,
        "label_status": "visually_reviewed_empty_negative",
        "training_ready": False,
        "robot_enabled": False,
        "note": "One visually reviewed empty scene is valid but insufficient negative diversity.",
    }, indent=2) + "\n", encoding="utf-8")
    print(f"NEGATIVE_EXPORT count=1 stem={args.stem} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
