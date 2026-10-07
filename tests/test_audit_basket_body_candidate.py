import unittest
from pathlib import Path

import cv2
import numpy as np

from scripts.audit_basket_body_candidate import propose_body_bbox


class BasketBodyCandidateTests(unittest.TestCase):
    def test_brown_rectangle_is_only_a_candidate(self):
        image = np.full((480, 640, 3), 255, np.uint8)
        color = cv2.cvtColor(np.uint8([[[22, 130, 120]]]), cv2.COLOR_HSV2BGR)[0, 0]
        cv2.rectangle(image, (320, 260), (419, 329), tuple(map(int, color)), -1)
        result = propose_body_bbox(image)
        self.assertEqual(result["status"], "BODY_BBOX_CANDIDATE")
        self.assertEqual(result["bbox_xywh_px"], [320, 260, 100, 70])
        self.assertFalse(result["basket_mouth_detected"])
        self.assertFalse(result["basket_pose_authorized"])
        self.assertFalse(result["robot_enabled"])
        self.assertFalse(result["motion_authorized"])

    def test_missing_color_does_not_invent_pose(self):
        result = propose_body_bbox(np.full((480, 640, 3), 255, np.uint8))
        self.assertEqual(result["status"], "NO_BODY_CANDIDATE")
        self.assertIsNone(result["bbox_xywh_px"])

    def test_wrong_image_size_rejected(self):
        with self.assertRaisesRegex(ValueError, "640x480"):
            propose_body_bbox(np.zeros((240, 320, 3), np.uint8))

    def test_source_has_no_robot_control_route(self):
        source = (Path(__file__).resolve().parents[1] / "scripts" /
                  "audit_basket_body_candidate.py").read_text()
        for forbidden in ("/move-arm", "/stop-teleoperation", "serial.Serial", "Goal_Position"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
