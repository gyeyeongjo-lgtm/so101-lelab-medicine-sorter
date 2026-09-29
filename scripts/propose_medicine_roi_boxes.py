#!/usr/bin/env python3
"""Draw whole-bottle box proposals for human review; emit no YOLO labels."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", required=True, type=Path)
    parser.add_argument("--screen", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def propose_bbox(body, image_size=(174, 110)):
    """Conservative cap/body box from a purple-body component; not ground truth."""
    x, y, width, height = body
    image_width, image_height = image_size
    x1, y1 = x - 5, y - 18
    x2, y2 = x + width + 5, y + height + 3
    if x1 < 0 or y1 < 0 or x2 > image_width or y2 > image_height:
        raise ValueError("proposal would cross ROI edge")
    return [x1, y1, x2 - x1, y2 - y1]


def main():
    args = parse_args()
    if args.output.exists():
        raise ValueError("output already exists; proposals never overwrite")
    import cv2

    screen = json.loads(args.screen.read_text(encoding="utf-8"))
    proposals = []
    prepared = []
    for record in screen["results"]:
        if record["screening_status"] != "needs_human_review":
            continue
        stem = record["stem"]
        image = cv2.imread(str(args.queue / "roi_640" / f"{stem}.png"))
        if image is None or image.shape[:2] != (110, 174):
            raise ValueError(f"invalid ROI image: {stem}")
        bbox = propose_bbox(record["purple_body_bbox_xywh_174x110"])
        x, y, width, height = bbox
        overlay = image.copy()
        cv2.rectangle(overlay, (x, y), (x + width - 1, y + height - 1), (0, 0, 255), 1)
        prepared.append((stem, overlay))
        proposals.append({
            "stem": stem,
            "bbox_xywh_174x110": bbox,
            "review_status": "proposal_only",
            "label": None,
        })
    (args.output / "overlays").mkdir(parents=True)
    for stem, overlay in prepared:
        if not cv2.imwrite(str(args.output / "overlays" / f"{stem}.png"), overlay):
            raise OSError(f"could not write overlay: {stem}")
    (args.output / "proposals.json").write_text(json.dumps({
        "source_queue": str(args.queue),
        "training_ready": False,
        "labels_generated": False,
        "note": "Visual proposals only; check cap, base, occlusion and duplicates before any label export.",
        "proposals": proposals,
    }, indent=2) + "\n", encoding="utf-8")
    print(f"PROPOSALS count={len(proposals)} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
