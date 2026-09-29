#!/usr/bin/env python3
"""Package audited medicine frames into a non-destructive YOLO dataset.

Training candidates are split by capture-time blocks, not individual frames,
to reduce leakage from consecutive captures. A separate evaluation directory
is copied only to the test split. This tool opens no camera or robot interface
and never overwrites an existing output directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from prepare_medicine_training_candidates import parse_label


@dataclass(frozen=True)
class Sample:
    stem: str
    image: Path
    label: Path
    metadata: Path
    kind: str
    captured_at: datetime | None


@dataclass
class CaptureGroup:
    key: str
    samples: list[Sample]
    fixed_train: bool = False

    @property
    def positive(self) -> int:
        return sum(sample.kind == "positive" for sample in self.samples)

    @property
    def negative(self) -> int:
        return sum(sample.kind == "negative" for sample in self.samples)


def parse_web_timestamp(stem: str) -> datetime | None:
    if not stem.startswith("web_"):
        return None
    raw = stem.removeprefix("web_").split("_", 1)[0]
    try:
        return datetime.strptime(raw, "%Y%m%dT%H%M%S")
    except ValueError:
        return None


def load_samples(root: Path) -> list[Sample]:
    images = {path.stem: path for path in (root / "images").glob("*.png")}
    labels = {path.stem: path for path in (root / "labels").glob("*.txt")}
    metadata = {path.stem: path for path in (root / "metadata").glob("*.json")}
    if not images or set(images) != set(labels) or set(images) != set(metadata):
        raise ValueError(f"incomplete image/label/metadata pairs: {root}")
    audit_path = root / "audit.json"
    if not audit_path.exists():
        raise ValueError(f"missing audit.json: {root}")
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    if audit.get("robot_enabled") is not False:
        raise ValueError("source audit does not explicitly block robot control")

    samples = []
    for stem in sorted(images):
        kind, _ = parse_label(labels[stem].read_text(encoding="utf-8"))
        meta = json.loads(metadata[stem].read_text(encoding="utf-8"))
        if meta.get("training_ready") is not False:
            raise ValueError(f"source training safety flag is invalid: {stem}")
        if meta.get("robot_target") is not False:
            raise ValueError(f"source robot safety flag is invalid: {stem}")
        samples.append(Sample(
            stem=stem,
            image=images[stem],
            label=labels[stem],
            metadata=metadata[stem],
            kind=kind,
            captured_at=parse_web_timestamp(stem),
        ))
    return samples


def build_capture_groups(samples: list[Sample], gap_seconds: float) -> list[CaptureGroup]:
    groups = []
    timed = sorted((sample for sample in samples if sample.captured_at), key=lambda item: item.captured_at)
    current: CaptureGroup | None = None
    for sample in timed:
        if (
            current is None
            or (sample.captured_at - current.samples[-1].captured_at).total_seconds() > gap_seconds
        ):
            current = CaptureGroup(key=f"web-block-{len(groups):03d}", samples=[])
            groups.append(current)
        current.samples.append(sample)

    untimed = [sample for sample in samples if sample.captured_at is None]
    if untimed:
        groups.insert(0, CaptureGroup(key="untimed-source", samples=untimed, fixed_train=True))
    return groups


def choose_validation_groups(groups: list[CaptureGroup], val_fraction: float) -> set[str]:
    selectable = [group for group in groups if not group.fixed_train]
    total_positive = sum(group.positive for group in groups)
    total_negative = sum(group.negative for group in groups)
    target_positive = max(1, round(total_positive * val_fraction))
    target_negative = max(1, round(total_negative * val_fraction))

    # Keep complete capture blocks together. Hash ordering makes ties stable.
    selectable.sort(key=lambda group: hashlib.sha256(group.key.encode()).hexdigest())
    states: dict[tuple[int, int], tuple[str, ...]] = {(0, 0): ()}
    for group in selectable:
        additions = {}
        for (positive, negative), chosen in states.items():
            state = (positive + group.positive, negative + group.negative)
            additions.setdefault(state, chosen + (group.key,))
        for state, chosen in additions.items():
            states.setdefault(state, chosen)

    def score(item):
        (positive, negative), chosen = item
        missing_class = int(positive == 0) + int(negative == 0)
        distance = abs(positive - target_positive) + abs(negative - target_negative)
        overshoot = max(0, positive - target_positive) + max(0, negative - target_negative)
        return missing_class, distance, overshoot, len(chosen), chosen

    (selected_positive, selected_negative), chosen = min(states.items(), key=score)
    if selected_positive == 0 or selected_negative == 0:
        raise ValueError("cannot create validation split containing both classes")
    if selected_positive >= total_positive or selected_negative >= total_negative:
        raise ValueError("validation split would consume an entire class")
    return set(chosen)


def copy_split(samples: list[Sample], split: str, output: Path) -> list[str]:
    stems = []
    for sample in sorted(samples, key=lambda item: item.stem):
        shutil.copy2(sample.image, output / "images" / split / f"{sample.stem}.png")
        shutil.copy2(sample.label, output / "labels" / split / f"{sample.stem}.txt")
        stems.append(sample.stem)
    return stems


def count_kinds(samples: list[Sample]) -> dict[str, int]:
    return {
        "positive": sum(sample.kind == "positive" for sample in samples),
        "negative": sum(sample.kind == "negative" for sample in samples),
        "total": len(samples),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--training-source", required=True, type=Path)
    parser.add_argument("--test-source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--validation-fraction", type=float, default=0.2)
    parser.add_argument("--capture-gap-seconds", type=float, default=30.0)
    args = parser.parse_args()
    if not 0 < args.validation_fraction < 0.5:
        parser.error("--validation-fraction must be between 0 and 0.5")
    if args.capture_gap_seconds <= 0:
        parser.error("--capture-gap-seconds must be positive")
    return args


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise ValueError("output already exists; dataset preparation never overwrites")

    candidates = load_samples(args.training_source)
    test = load_samples(args.test_source)
    test_audit = json.loads((args.test_source / "audit.json").read_text(encoding="utf-8"))
    if test_audit.get("smoke_evaluation_ready") is not True:
        raise ValueError("test source is not marked smoke_evaluation_ready")
    candidate_hashes = {hashlib.sha256(sample.image.read_bytes()).hexdigest() for sample in candidates}
    overlap = [sample.stem for sample in test if hashlib.sha256(sample.image.read_bytes()).hexdigest() in candidate_hashes]
    if overlap:
        raise ValueError(f"test images overlap training candidates: {overlap}")

    groups = build_capture_groups(candidates, args.capture_gap_seconds)
    validation_keys = choose_validation_groups(groups, args.validation_fraction)
    validation = [sample for group in groups if group.key in validation_keys for sample in group.samples]
    train = [sample for group in groups if group.key not in validation_keys for sample in group.samples]

    for split in ("train", "val", "test"):
        (args.output / "images" / split).mkdir(parents=True, exist_ok=False)
        (args.output / "labels" / split).mkdir(parents=True, exist_ok=False)
    manifest = {
        "status": "READY_FOR_OFFLINE_YOLO_TRAINING_SMOKE",
        "class_names": {"0": "white_medicine_bottle_model"},
        "image_size": [640, 480],
        "training_source": str(args.training_source),
        "test_source": str(args.test_source),
        "validation_fraction_requested": args.validation_fraction,
        "capture_gap_seconds": args.capture_gap_seconds,
        "validation_group_keys": sorted(validation_keys),
        "splits": {
            "train": {**count_kinds(train), "stems": copy_split(train, "train", args.output)},
            "val": {**count_kinds(validation), "stems": copy_split(validation, "val", args.output)},
            "test": {**count_kinds(test), "stems": copy_split(test, "test", args.output)},
        },
        "offline_training_ready": True,
        "smoke_evaluation_ready": True,
        "independent_evaluation_ready": False,
        "false_positive_rate_ready": False,
        "medicine_identity_verified": False,
        "robot_enabled": False,
        "note": (
            "Target-presence prototype only. Validation uses capture-time blocks; test has one unique empty scene. "
            "Do not claim a robust false-positive rate or use detections as robot commands."
        ),
    }
    (args.output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (args.output / "data.yaml").write_text(
        "path: .\ntrain: images/train\nval: images/val\ntest: images/test\n"
        "names:\n  0: white_medicine_bottle_model\n",
        encoding="utf-8",
    )
    print(
        "READY "
        f"train={count_kinds(train)} val={count_kinds(validation)} test={count_kinds(test)} "
        f"output={args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
