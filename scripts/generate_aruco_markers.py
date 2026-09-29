#!/usr/bin/env python3
"""Generate exact-size ArUco marker SVGs and PNG previews.

This tool only creates files. It never opens a camera or a robot device.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from xml.sax.saxutils import escape


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--dictionary", default="DICT_4X4_50")
    parser.add_argument("--ids", type=int, nargs="+", default=[0, 1, 2, 3])
    parser.add_argument("--size-mm", type=float, default=70.0)
    parser.add_argument("--border-bits", type=int, default=1)
    parser.add_argument("--preview-pixels", type=int, default=700)
    return parser.parse_args()


def require_aruco(dictionary_name: str):
    try:
        import cv2
    except ImportError as exc:
        raise SystemExit("OpenCV with cv2.aruco is required") from exc

    if not hasattr(cv2, "aruco"):
        raise SystemExit("This OpenCV build does not include cv2.aruco")
    dictionary_id = getattr(cv2.aruco, dictionary_name, None)
    if dictionary_id is None:
        raise SystemExit(f"Unknown ArUco dictionary: {dictionary_name}")
    return cv2, cv2.aruco.getPredefinedDictionary(dictionary_id)


def marker_modules(marker_image, marker_bits: int, border_bits: int) -> list[list[bool]]:
    modules = marker_bits + 2 * border_bits
    side = marker_image.shape[0]
    cells: list[list[bool]] = []
    for row in range(modules):
        values: list[bool] = []
        y = min(side - 1, int((row + 0.5) * side / modules))
        for col in range(modules):
            x = min(side - 1, int((col + 0.5) * side / modules))
            values.append(int(marker_image[y, x]) < 128)
        cells.append(values)
    return cells


def marker_svg(cells: list[list[bool]], size_mm: float, label: str | None = None) -> str:
    modules = len(cells)
    label_height = 8 if label else 0
    elements = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{size_mm:g}mm" '
            f'height="{size_mm + label_height:g}mm" viewBox="0 0 {modules} '
            f'{modules + label_height * modules / size_mm:g}">'
        ),
        f'<rect width="{modules}" height="{modules}" fill="white"/>',
    ]
    for row, values in enumerate(cells):
        for col, is_black in enumerate(values):
            if is_black:
                elements.append(f'<rect x="{col}" y="{row}" width="1" height="1" fill="black"/>')
    if label:
        y = modules + (label_height * modules / size_mm) * 0.72
        elements.append(
            f'<text x="{modules / 2:g}" y="{y:g}" text-anchor="middle" '
            f'font-family="sans-serif" font-size="0.42">{escape(label)}</text>'
        )
    elements.append("</svg>")
    return "\n".join(elements) + "\n"


def a4_sheet_svg(markers: list[tuple[int, list[list[bool]]]], size_mm: float, dictionary: str) -> str:
    page_w, page_h = 210.0, 297.0
    gap_x, gap_y = 20.0, 22.0
    start_x = (page_w - (2 * size_mm + gap_x)) / 2
    start_y = 35.0
    elements = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<svg xmlns="http://www.w3.org/2000/svg" width="210mm" height="297mm" viewBox="0 0 210 297">',
        '<rect width="210" height="297" fill="white"/>',
        '<text x="105" y="15" text-anchor="middle" font-family="sans-serif" font-size="5">'
        + escape(f"{dictionary} — print at 100% / actual size")
        + "</text>",
    ]
    for index, (marker_id, cells) in enumerate(markers):
        row, col = divmod(index, 2)
        x = start_x + col * (size_mm + gap_x)
        y = start_y + row * (size_mm + gap_y)
        modules = len(cells)
        cell_size = size_mm / modules
        elements.append(f'<rect x="{x:g}" y="{y:g}" width="{size_mm:g}" height="{size_mm:g}" fill="white"/>')
        for cell_row, values in enumerate(cells):
            for cell_col, is_black in enumerate(values):
                if is_black:
                    elements.append(
                        f'<rect x="{x + cell_col * cell_size:g}" y="{y + cell_row * cell_size:g}" '
                        f'width="{cell_size:g}" height="{cell_size:g}" fill="black"/>'
                    )
        elements.append(
            f'<text x="{x + size_mm / 2:g}" y="{y + size_mm + 6:g}" text-anchor="middle" '
            f'font-family="sans-serif" font-size="4">ID {marker_id}</text>'
        )
    elements.append(
        '<text x="105" y="286" text-anchor="middle" font-family="sans-serif" font-size="3.5">'
        + escape(f"Verify the outer black marker width = {size_mm:g} mm")
        + "</text>"
    )
    elements.append("</svg>")
    return "\n".join(elements) + "\n"


def main() -> int:
    args = parse_args()
    if args.size_mm <= 0 or args.preview_pixels < 60 or args.border_bits < 1:
        raise SystemExit("size-mm must be positive, preview-pixels >= 60, and border-bits >= 1")
    if len(set(args.ids)) != len(args.ids):
        raise SystemExit("Marker IDs must be unique")

    cv2, dictionary = require_aruco(args.dictionary)
    marker_bits = int(dictionary.markerSize)
    modules = marker_bits + 2 * args.border_bits
    preview_side = max(modules, (args.preview_pixels // modules) * modules)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    generated: list[tuple[int, list[list[bool]]]] = []
    for marker_id in args.ids:
        if marker_id < 0 or marker_id >= len(dictionary.bytesList):
            raise SystemExit(f"Marker ID {marker_id} is outside {args.dictionary}")
        image = cv2.aruco.generateImageMarker(dictionary, marker_id, preview_side, borderBits=args.border_bits)
        cells = marker_modules(image, marker_bits, args.border_bits)
        generated.append((marker_id, cells))
        stem = f"{args.dictionary.lower()}_id_{marker_id}_{args.size_mm:g}mm"
        if not cv2.imwrite(str(args.output_dir / f"{stem}.png"), image):
            raise SystemExit(f"Failed to write {stem}.png")
        (args.output_dir / f"{stem}.svg").write_text(
            marker_svg(cells, args.size_mm, f"{args.dictionary} ID {marker_id}"), encoding="utf-8"
        )

    sheet_name = f"{args.dictionary.lower()}_ids_{'-'.join(map(str, args.ids))}_{args.size_mm:g}mm_a4.svg"
    (args.output_dir / sheet_name).write_text(
        a4_sheet_svg(generated, args.size_mm, args.dictionary), encoding="utf-8"
    )
    print(f"Generated {len(args.ids)} markers and A4 sheet: {args.output_dir / sheet_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
