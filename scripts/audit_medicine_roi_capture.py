#!/usr/bin/env python3
"""Screen one preview ROI queue for obvious crop failures; never create labels.

The colour gate is specific to the current purple/white empty bottle model.
Passing this screen is *not* a positive label or evidence of an independent
training sample. Human whole-object and duplicate review remains required.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--edge-margin-px", type=int, default=8)
    return parser.parse_args()


def screen_body_bbox(bbox, size, margin):
    """Return only a conservative screen result, never an acceptance decision."""
    if bbox is None:
        return "hold_no_purple_body"
    x, y, width, height = bbox
    image_width, image_height = size
    if min(x, image_width - (x + width), image_height - (y + height)) < margin:
        return "reject_body_at_roi_edge"
    return "needs_human_review"


def purple_body_bbox(image, cv2, np):
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(
        hsv,
        np.array((120, 70, 20), dtype=np.uint8),
        np.array((160, 255, 255), dtype=np.uint8),
    )
    _, _, stats, _ = cv2.connectedComponentsWithStats(mask)
    components = [
        (int(row[4]), tuple(int(value) for value in row[:4]))
        for row in stats[1:]
        if row[4] >= 40 and row[1] >= 15 and row[3] >= 8
    ]
    return max(components, default=(0, None))[1]


def audit_queue(queue, margin, cv2, np):
    manifest = json.loads((queue / "manifest.json").read_text(encoding="utf-8"))
    stems = [record["stem"] for record in manifest["candidates"]]
    if len(stems) != len(set(stems)):
        raise ValueError("duplicate candidate stems")
    results = []
    for stem in stems:
        paths = [queue / folder / f"{stem}.png" for folder in
                 ("roi", "context", "roi_640", "context_640")]
        images = [cv2.imread(str(path)) for path in paths]
        if any(image is None for image in images):
            raise ValueError(f"incomplete image quartet: {stem}")
        if [image.shape[:2] for image in images] != [
            (55, 87), (240, 320), (110, 174), (480, 640)
        ]:
            raise ValueError(f"image shape mismatch: {stem}")
        bbox = purple_body_bbox(images[2], cv2, np)
        results.append({
            "stem": stem,
            "purple_body_bbox_xywh_174x110": list(bbox) if bbox else None,
            "screening_status": screen_body_bbox(bbox, (174, 110), margin),
            "label": None,
        })
    return {
        "source_queue": str(queue),
        "scope": "current purple/white empty bottle model only",
        "edge_margin_px": margin,
        "training_ready": False,
        "labels_generated": False,
        "note": "Only obvious ROI crop failures are screened. Every remaining image needs human whole-object and duplicate review.",
        "results": results,
    }


def main():
    args = parse_args()
    if args.edge_margin_px < 1:
        raise ValueError("edge margin must be positive")
    if args.output.exists():
        raise ValueError("output already exists; audits never overwrite")
    import cv2
    import numpy as np

    report = audit_queue(args.queue, args.edge_margin_px, cv2, np)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    counts = {}
    for result in report["results"]:
        status = result["screening_status"]
        counts[status] = counts.get(status, 0) + 1
    print(f"AUDIT total={len(report['results'])} statuses={counts} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
