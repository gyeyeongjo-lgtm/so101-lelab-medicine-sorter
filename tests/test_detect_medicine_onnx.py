import sys
import unittest
from pathlib import Path

import cv2
import numpy as np


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from detect_medicine_onnx import decode_detections, letterbox


class DetectMedicineOnnxTests(unittest.TestCase):
    def test_letterbox_640_by_480(self):
        image = np.zeros((480, 640, 3), dtype=np.uint8)
        prepared, scale, pad_x, pad_y = letterbox(image, 640, cv2, np)
        self.assertEqual(prepared.shape, (640, 640, 3))
        self.assertEqual(scale, 1.0)
        self.assertEqual((pad_x, pad_y), (0, 80))

    def test_decodes_transposed_yolo_output(self):
        # One class: [cx, cy, width, height, class confidence].
        raw = np.zeros((1, 5, 6), dtype=np.float32)
        raw[0, :, 0] = [320.0, 320.0, 100.0, 80.0, 0.9]
        detections = decode_detections(raw, 640, 480, 1.0, 0, 80, 0.25, 0.7, cv2, np)
        self.assertEqual(len(detections), 1)
        self.assertEqual(detections[0]["xyxy"], [270.0, 200.0, 370.0, 280.0])

    def test_confidence_filter(self):
        raw = np.zeros((1, 5, 6), dtype=np.float32)
        raw[0, :, 0] = [320.0, 320.0, 100.0, 80.0, 0.1]
        self.assertEqual(decode_detections(raw, 640, 480, 1.0, 0, 80, 0.25, 0.7, cv2, np), [])


if __name__ == "__main__":
    unittest.main()
