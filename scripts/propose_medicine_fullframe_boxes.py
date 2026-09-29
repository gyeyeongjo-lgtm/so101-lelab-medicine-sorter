#!/usr/bin/env python3
"""Propose full-frame bottle boxes from the current purple-body model."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


SEARCH_XYXY = (180, 175, 480, 315)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--exclude", nargs="*", default=[])
    return parser.parse_args()


def select_body(stats):
    eligible = []
    for row in stats:
        x, y, width, height, area = (int(value) for value in row)
        if (
            100 <= area <= 1000
            and 180 <= x <= 480
            and 175 <= y <= 315
            and 8 <= width <= 45
            and 8 <= height <= 60
        ):
            eligible.append((area, [x, y, width, height]))
    if len(eligible) != 1:
        raise ValueError(f"expected exactly one bottle body candidate, found {len(eligible)}")
    return eligible[0][1]


def propose_bbox(body, image_size=(640, 480)):
    x, y, width, height = body
    image_width, image_height = image_size
    x1, y1 = x - 5, y - 18
    x2, y2 = x + width + 5, y + height + 3
    if x1 < 0 or y1 < 0 or x2 > image_width or y2 > image_height:
        raise ValueError("full-frame proposal is out of bounds")
    return [x1, y1, x2 - x1, y2 - y1]


def main():
    args = parse_args()
    if args.output.exists():
        raise ValueError("output already exists; proposals never overwrite")
    excludes = set(args.exclude)
    import cv2
    import numpy as np

    manifest = json.loads((args.queue / "manifest.json").read_text(encoding="utf-8"))
    stems = [record["stem"] for record in manifest["candidates"]]
    if not excludes <= set(stems):
        raise ValueError("excluded stem is not present in queue")
    prepared = []
    proposals = []
    for stem in stems:
        if stem in excludes:
            continue
        image = cv2.imread(str(args.queue / "context_640" / f"{stem}.png"))
        if image is None or image.shape[:2] != (480, 640):
            raise ValueError(f"missing or wrong-sized context: {stem}")
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(
            hsv,
            np.array((120, 70, 20), dtype=np.uint8),
            np.array((160, 255, 255), dtype=np.uint8),
        )
        _, _, stats, _ = cv2.connectedComponentsWithStats(mask)
        body = select_body(stats[1:])
        bbox = propose_bbox(body)
        x, y, width, height = bbox
        overlay = image.copy()
        cv2.rectangle(overlay, (x, y), (x + width - 1, y + height - 1), (0, 0, 255), 2)
        prepared.append((stem, overlay))
        proposals.append({
            "stem": stem,
            "purple_body_bbox_xywh_640x480": body,
            "bbox_xywh_640x480": bbox,
            "review_status": "proposal_only",
            "label": None,
        })
    (args.output / "overlays").mkdir(parents=True)
    for stem, overlay in prepared:
        if not cv2.imwrite(str(args.output / "overlays" / f"{stem}.png"), overlay):
            raise OSError(f"could not write overlay: {stem}")
    (args.output / "proposals.json").write_text(json.dumps({
        "source_queue": str(args.queue),
        "image_size": [640, 480],
        "search_xyxy": list(SEARCH_XYXY),
        "excluded_stems": sorted(excludes),
        "training_ready": False,
        "labels_generated": False,
        "medicine_identity_verified": False,
        "robot_enabled": False,
        "note": "Full-frame visual proposals only. Human whole-object, occlusion and duplicate review remains required.",
        "proposals": proposals,
    }, indent=2) + "\n", encoding="utf-8")
    print(f"FULLFRAME_PROPOSALS count={len(proposals)} excluded={len(excludes)} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
