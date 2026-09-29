#!/usr/bin/env python3
"""Build a non-destructive audited medicine detection candidate set.

The output remains training_ready=false. Positive frames closer than the
configured center distance are grouped and one representative is retained.
Exact duplicate images are also retained only once. No robot interfaces are
opened by this tool.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Record:
    source: str
    stem: str
    image: Path
    label: Path
    metadata: Path
    kind: str
    bbox: tuple[float, float, float, float] | None
    image_hash: str
    sharpness: float
    review_priority: int

    @property
    def output_stem(self) -> str:
        return f"{self.source}_{self.stem}"

    @property
    def center_px(self) -> tuple[float, float] | None:
        if self.bbox is None:
            return None
        return self.bbox[0] * 640.0, self.bbox[1] * 480.0


def parse_source(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("source must use NAME=/path format")
    name, raw_path = value.split("=", 1)
    if not name or not name.replace("-", "_").isalnum():
        raise argparse.ArgumentTypeError("source name must be alphanumeric with '-' or '_'")
    return name, Path(raw_path)


def parse_label(content: str) -> tuple[str, tuple[float, float, float, float] | None]:
    if not content.strip():
        return "negative", None
    parts = content.split()
    if len(parts) != 5 or parts[0] != "0":
        raise ValueError("positive label must contain one class-0 normalized xywh row")
    values = tuple(float(value) for value in parts[1:])
    if not all(0 < value <= 1 for value in values):
        raise ValueError("positive label values must be in (0, 1]")
    x, y, width, height = values
    if x - width / 2 < 0 or x + width / 2 > 1 or y - height / 2 < 0 or y + height / 2 > 1:
        raise ValueError("positive label extends outside the image")
    return "positive", values


def _sharpness(image, bbox, cv2) -> float:
    if bbox is None:
        crop = image
    else:
        x, y, width, height = bbox
        x1 = max(0, int((x - width / 2) * image.shape[1]))
        y1 = max(0, int((y - height / 2) * image.shape[0]))
        x2 = min(image.shape[1], int(math.ceil((x + width / 2) * image.shape[1])))
        y2 = min(image.shape[0], int(math.ceil((y + height / 2) * image.shape[0])))
        crop = image[y1:y2, x1:x2]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def load_source(name: str, root: Path, cv2) -> list[Record]:
    images = {path.stem: path for path in (root / "images").glob("*.png")}
    labels = {path.stem: path for path in (root / "labels").glob("*.txt")}
    metadata = {path.stem: path for path in (root / "metadata").glob("*.json")}
    if not images or set(images) != set(labels) or set(images) != set(metadata):
        raise ValueError(f"incomplete source pairs: {root}")
    records = []
    for stem in sorted(images):
        image_bytes = images[stem].read_bytes()
        image = cv2.imread(str(images[stem]), cv2.IMREAD_COLOR)
        if image is None or image.shape[:2] != (480, 640):
            raise ValueError(f"source image must be 640x480: {name}/{stem}")
        kind, bbox = parse_label(labels[stem].read_text(encoding="utf-8"))
        meta = json.loads(metadata[stem].read_text(encoding="utf-8"))
        if meta.get("training_ready") is not False or meta.get("robot_target") is not False:
            raise ValueError(f"source safety flags are missing: {name}/{stem}")
        label_status = str(meta.get("label_status", ""))
        priority = 2 if "human_reviewed" in label_status else 1
        records.append(Record(
            source=name,
            stem=stem,
            image=images[stem],
            label=labels[stem],
            metadata=metadata[stem],
            kind=kind,
            bbox=bbox,
            image_hash=hashlib.sha256(image_bytes).hexdigest(),
            sharpness=_sharpness(image, bbox, cv2),
            review_priority=priority,
        ))
    return records


def cluster_positives(records: list[Record], distance_px: float) -> list[list[Record]]:
    positives = [record for record in records if record.kind == "positive"]
    parent = list(range(len(positives)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for left, first in enumerate(positives):
        for right in range(left):
            second = positives[right]
            if math.dist(first.center_px, second.center_px) < distance_px:
                union(left, right)
    groups: dict[int, list[Record]] = {}
    for index, record in enumerate(positives):
        groups.setdefault(find(index), []).append(record)
    return list(groups.values())


def choose_representatives(records: list[Record], distance_px: float) -> tuple[list[Record], list[dict]]:
    kept = [record for record in records if record.kind == "negative"]
    excluded = []
    for group in cluster_positives(records, distance_px):
        representative = max(group, key=lambda item: (item.review_priority, item.sharpness, item.output_stem))
        kept.append(representative)
        for record in group:
            if record is not representative:
                excluded.append({
                    "stem": record.output_stem,
                    "reason": "positive_center_near_duplicate",
                    "representative": representative.output_stem,
                    "distance_px": round(math.dist(record.center_px, representative.center_px), 3),
                })

    unique = []
    seen_hashes: dict[str, Record] = {}
    for record in sorted(kept, key=lambda item: item.output_stem):
        if record.image_hash in seen_hashes:
            excluded.append({
                "stem": record.output_stem,
                "reason": "exact_image_duplicate",
                "representative": seen_hashes[record.image_hash].output_stem,
            })
        else:
            seen_hashes[record.image_hash] = record
            unique.append(record)
    return unique, excluded


def write_contact_sheet(records: list[Record], output: Path, title: str, cv2) -> None:
    import numpy as np

    thumb_width, thumb_height, label_height, columns = 240, 180, 32, 4
    rows = max(1, math.ceil(len(records) / columns))
    sheet = np.full((rows * (thumb_height + label_height), columns * thumb_width, 3), 245, dtype=np.uint8)
    for index, record in enumerate(records):
        row, column = divmod(index, columns)
        image = cv2.imread(str(record.image), cv2.IMREAD_COLOR)
        if record.bbox is not None:
            x, y, width, height = record.bbox
            x1, y1 = int((x - width / 2) * 640), int((y - height / 2) * 480)
            x2, y2 = int((x + width / 2) * 640), int((y + height / 2) * 480)
            cv2.rectangle(image, (x1, y1), (x2, y2), (0, 0, 255), 2)
        thumb = cv2.resize(image, (thumb_width, thumb_height), interpolation=cv2.INTER_AREA)
        y0, x0 = row * (thumb_height + label_height), column * thumb_width
        sheet[y0:y0 + thumb_height, x0:x0 + thumb_width] = thumb
        cv2.putText(sheet, record.output_stem[:34], (x0 + 4, y0 + thumb_height + 21),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (20, 20, 20), 1, cv2.LINE_AA)
    cv2.putText(sheet, title, (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
    if not cv2.imwrite(str(output), sheet):
        raise OSError(f"failed to write contact sheet: {output}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", action="append", required=True, type=parse_source)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--positive-center-distance-px", type=float, default=12.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise ValueError("output already exists; preparation never overwrites")
    import cv2

    records = []
    for name, root in args.source:
        records.extend(load_source(name, root, cv2))
    kept, excluded = choose_representatives(records, args.positive_center_distance_px)
    for folder in ("images", "labels", "metadata", "reports"):
        (args.output / folder).mkdir(parents=True, exist_ok=False)
    for record in kept:
        shutil.copy2(record.image, args.output / "images" / f"{record.output_stem}.png")
        shutil.copy2(record.label, args.output / "labels" / f"{record.output_stem}.txt")
        metadata = json.loads(record.metadata.read_text(encoding="utf-8"))
        metadata.update({"prepared_source": record.source, "prepared_source_stem": record.stem})
        (args.output / "metadata" / f"{record.output_stem}.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    positives = [record for record in kept if record.kind == "positive"]
    negatives = [record for record in kept if record.kind == "negative"]
    write_contact_sheet(positives, args.output / "reports" / "positive-contact-sheet.jpg", "positive", cv2)
    write_contact_sheet(negatives, args.output / "reports" / "negative-contact-sheet.jpg", "negative", cv2)
    audit = {
        "status": "REVIEW_REQUIRED_NOT_TRAINING_READY",
        "scope": "full_frame",
        "image_size": [640, 480],
        "class_names": {"0": "white_medicine_bottle_model"},
        "input_records": len(records),
        "kept_positive": len(positives),
        "kept_negative": len(negatives),
        "excluded_count": len(excluded),
        "positive_center_distance_px": args.positive_center_distance_px,
        "sources": {name: str(root) for name, root in args.source},
        "excluded": excluded,
        "training_ready": False,
        "independent_evaluation_ready": False,
        "medicine_identity_verified": False,
        "robot_enabled": False,
        "note": "Contact sheets require visual review. A separate capture session is required for independent evaluation.",
    }
    (args.output / "audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"PREPARED input={len(records)} positive={len(positives)} negative={len(negatives)} "
        f"excluded={len(excluded)} output={args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
