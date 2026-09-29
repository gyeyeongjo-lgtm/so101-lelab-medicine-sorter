#!/usr/bin/env python3
"""Freeze a reviewed, independent medicine-detection evaluation set.

The source must contain approved web-review exports. Close positive centers are
deduplicated without modifying the source. The output is evaluation-only: it
never marks data as training-ready or enables robot control.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from prepare_medicine_training_candidates import (
    choose_representatives,
    load_source,
    write_contact_sheet,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--positive-center-distance-px", type=float, default=3.0)
    parser.add_argument("--negative-dhash-distance", type=int, default=8)
    parser.add_argument("--required-positive", type=int, default=10)
    parser.add_argument("--required-negative", type=int, default=5)
    return parser.parse_args()


def validate_approved(records) -> None:
    for record in records:
        metadata = json.loads(record.metadata.read_text(encoding="utf-8"))
        if metadata.get("status") != "approved":
            raise ValueError(f"source is not approved: {record.stem}")
        if metadata.get("label_status") != "human_reviewed_web_capture":
            raise ValueError(f"source is not human-reviewed: {record.stem}")
        if metadata.get("training_ready") is not False:
            raise ValueError(f"training safety flag is invalid: {record.stem}")
        if metadata.get("robot_target") is not False:
            raise ValueError(f"robot safety flag is invalid: {record.stem}")


def deduplicate_negative_scenes(records, max_distance: int, cv2):
    negatives = [record for record in records if record.kind == "negative"]
    positives = [record for record in records if record.kind == "positive"]
    hashes = []
    for record in negatives:
        image = cv2.imread(str(record.image), cv2.IMREAD_GRAYSCALE)
        resized = cv2.resize(image, (9, 8), interpolation=cv2.INTER_AREA)
        hashes.append((resized[:, 1:] > resized[:, :-1]).reshape(-1))

    parent = list(range(len(negatives)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for left in range(len(negatives)):
        for right in range(left):
            distance = int((hashes[left] != hashes[right]).sum())
            if distance <= max_distance:
                union(left, right)

    groups = {}
    for index, record in enumerate(negatives):
        groups.setdefault(find(index), []).append((index, record))

    selected = list(positives)
    excluded = []
    for group in groups.values():
        representative_index, representative = max(group, key=lambda item: item[1].sharpness)
        selected.append(representative)
        for index, record in group:
            if record is representative:
                continue
            distance = int((hashes[index] != hashes[representative_index]).sum())
            excluded.append({
                "stem": record.output_stem,
                "reason": "negative_scene_near_duplicate",
                "representative": representative.output_stem,
                "dhash_distance": distance,
            })
    return selected, excluded


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise ValueError("output already exists; evaluation preparation never overwrites")

    import cv2

    records = load_source("eval", args.source, cv2)
    validate_approved(records)
    selected, excluded = choose_representatives(records, args.positive_center_distance_px)
    selected, negative_excluded = deduplicate_negative_scenes(
        selected, args.negative_dhash_distance, cv2
    )
    excluded.extend(negative_excluded)
    positives = [record for record in selected if record.kind == "positive"]
    negatives = [record for record in selected if record.kind == "negative"]
    if len(positives) != args.required_positive or len(negatives) != args.required_negative:
        raise ValueError(
            "evaluation count mismatch after deduplication: "
            f"positive={len(positives)} negative={len(negatives)}"
        )

    for folder in ("images", "labels", "metadata", "reports"):
        (args.output / folder).mkdir(parents=True, exist_ok=False)
    for record in selected:
        output_stem = record.output_stem
        shutil.copy2(record.image, args.output / "images" / f"{output_stem}.png")
        shutil.copy2(record.label, args.output / "labels" / f"{output_stem}.txt")
        metadata = json.loads(record.metadata.read_text(encoding="utf-8"))
        metadata.update({
            "prepared_source": str(args.source),
            "prepared_source_stem": record.stem,
            "split": "test",
            "evaluation_ready_for_detection": True,
            "training_ready": False,
            "medicine_identity_verified": False,
            "robot_target": False,
        })
        (args.output / "metadata" / f"{output_stem}.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    write_contact_sheet(positives, args.output / "reports" / "positive-contact-sheet.jpg", "evaluation positive", cv2)
    write_contact_sheet(negatives, args.output / "reports" / "negative-contact-sheet.jpg", "evaluation negative", cv2)
    evaluation_profile = (
        "pharmacy_target_presence_smoke"
        if args.required_negative == 1
        else "independent_detection_evaluation"
    )
    audit = {
        "status": (
            "READY_FOR_OFFLINE_DETECTION_SMOKE_EVALUATION"
            if evaluation_profile == "pharmacy_target_presence_smoke"
            else "READY_FOR_OFFLINE_DETECTION_EVALUATION"
        ),
        "evaluation_profile": evaluation_profile,
        "scope": "full_frame",
        "split": "test",
        "image_size": [640, 480],
        "class_names": {"0": "white_medicine_bottle_model"},
        "source": str(args.source),
        "input_records": len(records),
        "selected_positive": len(positives),
        "selected_negative": len(negatives),
        "excluded_count": len(excluded),
        "positive_center_distance_px": args.positive_center_distance_px,
        "negative_dhash_distance": args.negative_dhash_distance,
        "selected_stems": [record.output_stem for record in selected],
        "excluded": excluded,
        "smoke_evaluation_ready": True,
        "independent_evaluation_ready": evaluation_profile == "independent_detection_evaluation",
        "false_positive_rate_ready": False,
        "training_ready": False,
        "medicine_identity_verified": False,
        "robot_enabled": False,
        "note": (
            "Pharmacy target-presence smoke evaluation with one unique empty scene; "
            "do not report a robust false-positive rate. Never use these images for training or robot commands."
            if evaluation_profile == "pharmacy_target_presence_smoke"
            else "Evaluation-only split. Never use these images for training or robot commands."
        ),
    }
    (args.output / "audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"READY positive={len(positives)} negative={len(negatives)} "
        f"excluded={len(excluded)} output={args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
