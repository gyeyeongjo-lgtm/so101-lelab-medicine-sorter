#!/usr/bin/env python3
"""Export separate, unapproved YOLO label proposals from a reviewed ROI queue.

This never edits source images or previous datasets. Labels remain provisional;
the output is explicitly not training-ready or a medicine identity decision.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path


DEFAULT_IMAGE_SIZE = (174, 110)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", required=True, type=Path)
    parser.add_argument("--proposals", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--exclude", nargs="*", default=[])
    parser.add_argument("--image-folder", default="roi_640")
    parser.add_argument("--bbox-key", default="bbox_xywh_174x110")
    parser.add_argument("--scope", choices=("pickup_roi_only", "full_frame"), default="pickup_roi_only")
    parser.add_argument(
        "--stem-prefix",
        default="",
        help="Safe prefix added to exported image/label/metadata stems.",
    )
    return parser.parse_args()


def bbox_to_label(bbox, size=DEFAULT_IMAGE_SIZE):
    if not isinstance(bbox, list) or len(bbox) != 4 or any(
        not isinstance(value, int) or isinstance(value, bool) for value in bbox
    ):
        raise ValueError("bbox must contain four integer xywh values")
    x, y, width, height = bbox
    image_width, image_height = size
    if width <= 0 or height <= 0 or x < 0 or y < 0:
        raise ValueError("bbox must have positive size and non-negative origin")
    if x + width > image_width or y + height > image_height:
        raise ValueError("bbox exceeds ROI image")
    values = ((x + width / 2) / image_width, (y + height / 2) / image_height,
              width / image_width, height / image_height)
    return "0 " + " ".join(f"{value:.8f}" for value in values) + "\n"


def prefixed_stem(prefix, stem):
    if not isinstance(prefix, str) or not re.fullmatch(r"[A-Za-z0-9_-]*", prefix):
        raise ValueError("stem prefix must contain only letters, numbers, underscores or hyphens")
    output_stem = f"{prefix}{stem}"
    if not output_stem or not re.fullmatch(r"[A-Za-z0-9_-]+", output_stem):
        raise ValueError("exported stem is invalid")
    return output_stem


def prepare_records(queue, proposals_path, excludes, image_folder, bbox_key, cv2):
    proposal_data = json.loads(proposals_path.read_text(encoding="utf-8"))
    if proposal_data.get("source_queue") != str(queue):
        raise ValueError("proposal source queue mismatch")
    proposals = proposal_data.get("proposals")
    if not isinstance(proposals, list) or not proposals:
        raise ValueError("proposals must be a non-empty list")
    image_size_value = proposal_data.get("image_size", list(DEFAULT_IMAGE_SIZE))
    if (
        not isinstance(image_size_value, list)
        or len(image_size_value) != 2
        or not all(isinstance(value, int) and value > 0 for value in image_size_value)
    ):
        raise ValueError("proposal image_size must contain two positive integers")
    image_size = tuple(image_size_value)
    stems = [record.get("stem") for record in proposals]
    if len(stems) != len(set(stems)) or not all(isinstance(stem, str) for stem in stems):
        raise ValueError("proposal stems must be unique strings")
    if not excludes <= set(stems):
        raise ValueError("excluded stem is not a proposal")
    prepared = []
    for record in proposals:
        stem = record["stem"]
        if stem in excludes:
            continue
        if record.get("review_status") != "proposal_only" or record.get("label") is not None:
            raise ValueError(f"unexpected source proposal state: {stem}")
        source_image = queue / image_folder / f"{stem}.png"
        image = cv2.imread(str(source_image), cv2.IMREAD_COLOR)
        if image is None or image.shape[:2] != (image_size[1], image_size[0]):
            raise ValueError(f"missing or wrong-sized ROI image: {stem}")
        bbox = record.get(bbox_key)
        label = bbox_to_label(bbox, image_size)
        prepared.append((stem, source_image, bbox, label))
    if not prepared:
        raise ValueError("no proposals remain after exclusions")
    return prepared, image_size


def main():
    args = parse_args()
    if args.output.exists():
        raise ValueError("output already exists; source and prior exports are preserved")
    if not args.output.parent.is_dir():
        raise ValueError("output parent does not exist")
    import cv2

    excludes = set(args.exclude)
    prepared, image_size = prepare_records(
        args.queue, args.proposals, excludes, args.image_folder, args.bbox_key, cv2
    )
    for name in ("images", "labels", "metadata"):
        (args.output / name).mkdir(parents=True, exist_ok=False)
    for stem, source_image, bbox, label in prepared:
        output_stem = prefixed_stem(args.stem_prefix, stem)
        shutil.copy2(source_image, args.output / "images" / f"{output_stem}.png")
        (args.output / "labels" / f"{output_stem}.txt").write_text(label, encoding="utf-8")
        (args.output / "metadata" / f"{output_stem}.json").write_text(json.dumps({
            "source_queue": str(args.queue),
            "source_stem": stem,
            "exported_stem": output_stem,
            "source_image_folder": args.image_folder,
            "scope": args.scope,
            "class_id": 0,
            "class_name": "white_medicine_bottle_model",
            "bbox_xywh": bbox,
            "image_size": list(image_size),
            "label_status": "provisional_color_based_proposal",
            "review_required": True,
            "training_ready": False,
            "medicine_identity_verified": False,
            "robot_target": False,
        }, indent=2) + "\n", encoding="utf-8")
    (args.output / "dataset.json").write_text(json.dumps({
        "scope": args.scope,
        "source_image_folder": args.image_folder,
        "stem_prefix": args.stem_prefix,
        "image_size": list(image_size),
        "positive_proposals": len(prepared),
        "excluded_stems": sorted(excludes),
        "label_status": "provisional_color_based_proposal",
        "review_required": True,
        "training_ready": False,
        "medicine_identity_verified": False,
        "robot_enabled": False,
        "note": "These are proposal labels, not verified ground truth. Check whole-object boxes, duplicates and an independent evaluation split before training.",
    }, indent=2) + "\n", encoding="utf-8")
    print(f"PROVISIONAL_EXPORT count={len(prepared)} excluded={len(excludes)} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
