#!/usr/bin/env python3
"""Run the medicine YOLO ONNX model on saved images using OpenCV DNN.

This is an offline/read-only detector. It does not open cameras, serial ports,
LeLab endpoints, or robot controls. Optional overlays and JSON are written only
to new paths; existing output paths are never overwritten.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp"}


def letterbox(image, size: int, cv2, np):
    height, width = image.shape[:2]
    scale = min(size / width, size / height)
    resized_width = round(width * scale)
    resized_height = round(height * scale)
    resized = cv2.resize(image, (resized_width, resized_height), interpolation=cv2.INTER_LINEAR)
    pad_x = (size - resized_width) // 2
    pad_y = (size - resized_height) // 2
    canvas = np.full((size, size, 3), 114, dtype=np.uint8)
    canvas[pad_y:pad_y + resized_height, pad_x:pad_x + resized_width] = resized
    return canvas, scale, pad_x, pad_y


def decode_detections(
    raw_output,
    image_width: int,
    image_height: int,
    scale: float,
    pad_x: int,
    pad_y: int,
    confidence_threshold: float,
    iou_threshold: float,
    cv2,
    np,
):
    rows = np.squeeze(raw_output)
    if rows.ndim != 2:
        raise ValueError(f"unexpected ONNX output shape: {raw_output.shape}")
    if rows.shape[0] <= 256 and rows.shape[1] > rows.shape[0]:
        rows = rows.T
    if rows.shape[1] < 5:
        raise ValueError(f"ONNX output must contain xywh and class scores: {raw_output.shape}")

    boxes = []
    confidences = []
    class_ids = []
    for row in rows:
        scores = row[4:]
        class_id = int(np.argmax(scores))
        confidence = float(scores[class_id])
        if confidence < confidence_threshold:
            continue
        center_x, center_y, width, height = map(float, row[:4])
        x1 = (center_x - width / 2 - pad_x) / scale
        y1 = (center_y - height / 2 - pad_y) / scale
        x2 = (center_x + width / 2 - pad_x) / scale
        y2 = (center_y + height / 2 - pad_y) / scale
        x1, y1 = max(0.0, x1), max(0.0, y1)
        x2, y2 = min(float(image_width), x2), min(float(image_height), y2)
        if x2 <= x1 or y2 <= y1:
            continue
        boxes.append([x1, y1, x2 - x1, y2 - y1])
        confidences.append(confidence)
        class_ids.append(class_id)

    indices = cv2.dnn.NMSBoxes(boxes, confidences, confidence_threshold, iou_threshold)
    if len(indices) == 0:
        return []
    detections = []
    for index in np.asarray(indices).reshape(-1):
        x, y, width, height = boxes[int(index)]
        detections.append({
            "class_id": class_ids[int(index)],
            "class_name": "white_medicine_bottle_model",
            "confidence": round(confidences[int(index)], 6),
            "xyxy": [round(x, 3), round(y, 3), round(x + width, 3), round(y + height, 3)],
        })
    return sorted(detections, key=lambda item: item["confidence"], reverse=True)


def iter_images(source: Path) -> list[Path]:
    if source.is_file() and source.suffix.lower() in IMAGE_SUFFIXES:
        return [source]
    if source.is_dir():
        return sorted(path for path in source.iterdir() if path.suffix.lower() in IMAGE_SUFFIXES)
    raise ValueError(f"source must be an image or directory: {source}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", type=Path, help="new directory for overlay images")
    parser.add_argument("--json-output", type=Path, help="new JSON report path")
    parser.add_argument("--image-size", type=int, default=640)
    parser.add_argument("--confidence", type=float, default=0.25)
    parser.add_argument("--iou", type=float, default=0.7)
    args = parser.parse_args()
    if not 0 < args.confidence < 1 or not 0 < args.iou < 1:
        parser.error("--confidence and --iou must be between 0 and 1")
    if args.output and args.output.exists():
        parser.error("--output already exists; detector never overwrites")
    if args.json_output and args.json_output.exists():
        parser.error("--json-output already exists; detector never overwrites")
    return args


def main() -> int:
    args = parse_args()
    import cv2
    import numpy as np

    if not args.model.is_file():
        raise ValueError(f"model does not exist: {args.model}")
    images = iter_images(args.source)
    if not images:
        raise ValueError(f"no images found: {args.source}")
    if args.output:
        args.output.mkdir(parents=True, exist_ok=False)

    net = cv2.dnn.readNetFromONNX(str(args.model))
    report = []
    for path in images:
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"failed to decode image: {path}")
        prepared, scale, pad_x, pad_y = letterbox(image, args.image_size, cv2, np)
        blob = cv2.dnn.blobFromImage(prepared, 1 / 255.0, (args.image_size, args.image_size), swapRB=True)
        net.setInput(blob)
        raw_output = net.forward()
        detections = decode_detections(
            raw_output,
            image.shape[1],
            image.shape[0],
            scale,
            pad_x,
            pad_y,
            args.confidence,
            args.iou,
            cv2,
            np,
        )
        report.append({"image": str(path), "detections": detections})
        if args.output:
            overlay = image.copy()
            for detection in detections:
                x1, y1, x2, y2 = (round(value) for value in detection["xyxy"])
                cv2.rectangle(overlay, (x1, y1), (x2, y2), (0, 255, 0), 2)
                label = f"medicine {detection['confidence']:.2f}"
                cv2.putText(overlay, label, (x1, max(18, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2)
            if not cv2.imwrite(str(args.output / path.name), overlay):
                raise OSError(f"failed to write overlay: {path.name}")

    payload = {
        "status": "OFFLINE_DETECTION_ONLY",
        "model": str(args.model),
        "confidence_threshold": args.confidence,
        "iou_threshold": args.iou,
        "images": report,
        "robot_enabled": False,
    }
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
