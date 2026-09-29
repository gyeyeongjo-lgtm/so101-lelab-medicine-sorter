#!/usr/bin/env python3
"""Generate an exact-aspect ChArUco board raster for print embedding."""

from __future__ import annotations

import argparse
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dictionary", default="DICT_4X4_50")
    parser.add_argument("--squares-x", type=int, default=6)
    parser.add_argument("--squares-y", type=int, default=8)
    parser.add_argument("--square-mm", type=float, default=30.0)
    parser.add_argument("--marker-mm", type=float, default=22.0)
    parser.add_argument("--first-id", type=int, default=10)
    parser.add_argument("--pixels-per-mm", type=int, default=20)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.squares_x < 2 or args.squares_y < 2:
        raise SystemExit("squares-x and squares-y must be at least 2")
    if not 0 < args.marker_mm < args.square_mm:
        raise SystemExit("marker-mm must be positive and smaller than square-mm")
    if args.pixels_per_mm < 4:
        raise SystemExit("pixels-per-mm must be at least 4")

    import cv2
    import numpy as np

    dictionary_id = getattr(cv2.aruco, args.dictionary, None)
    if dictionary_id is None:
        raise SystemExit(f"Unknown dictionary: {args.dictionary}")
    dictionary = cv2.aruco.getPredefinedDictionary(dictionary_id)
    marker_count = (args.squares_x * args.squares_y) // 2
    ids = np.arange(args.first_id, args.first_id + marker_count, dtype=np.int32)
    if ids[-1] >= len(dictionary.bytesList):
        raise SystemExit("Requested marker IDs exceed dictionary capacity")

    board = cv2.aruco.CharucoBoard(
        (args.squares_x, args.squares_y),
        args.square_mm,
        args.marker_mm,
        dictionary,
        ids,
    )
    width = round(args.squares_x * args.square_mm * args.pixels_per_mm)
    height = round(args.squares_y * args.square_mm * args.pixels_per_mm)
    image = board.generateImage((width, height), marginSize=0, borderBits=1)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(args.output), image):
        raise SystemExit(f"Failed to write {args.output}")
    print(
        f"{args.output} {width}x{height}px; "
        f"board={args.squares_x * args.square_mm:g}x{args.squares_y * args.square_mm:g}mm; "
        f"ids={ids[0]}-{ids[-1]}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
