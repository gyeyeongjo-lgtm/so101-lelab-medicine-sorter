import sys
import unittest
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from stable_aruco_table import reference_homography


class StableArucoTableTests(unittest.TestCase):
    def setUp(self):
        centers = {0: (500, 430), 1: (220, 430), 2: (250, 230), 3: (480, 230), 4: (310, 345)}
        square = np.array([[-10, -10], [10, -10], [10, 10], [-10, 10]], dtype=float)
        self.old = {marker: (np.array(center) + square).reshape(1, 4, 2)
                    for marker, center in centers.items()}
        self.new = {marker: corners + np.array([2.0, -1.0])
                    for marker, corners in self.old.items()}
        self.new[2] = self.new[2] + np.array([0.0, 15.0])
        self.table = {0: (0, 0), 1: (400, 0), 2: (400, 350), 3: (0, 350)}

    def test_moved_id2_is_holdout_not_used_in_projection(self):
        matrix, quality = reference_homography(cv2, self.old, self.new, self.table)
        self.assertLess(quality["stable_corner_rms_px"], 0.001)
        self.assertAlmostEqual(quality["id2_holdout_drift_px"], 15.0, places=3)
        self.assertFalse(quality["id2_used_in_live_fit"])
        current = np.array([[[312.0, 344.0]]], dtype=float)
        projected = cv2.perspectiveTransform(current, matrix)[0, 0]
        old_matrix, _ = cv2.findHomography(
            np.array([self.old[i].reshape(4, 2).mean(axis=0) for i in (0, 1, 2, 3)]),
            np.array([self.table[i] for i in (0, 1, 2, 3)], dtype=float), 0)
        expected = cv2.perspectiveTransform(np.array([[[310.0, 345.0]]], dtype=float), old_matrix)[0, 0]
        np.testing.assert_allclose(projected, expected, atol=0.001)

    def test_stable_marker_movement_blocks(self):
        self.new[3] = self.new[3] + np.array([0.0, 15.0])
        with self.assertRaisesRegex(ValueError, "stable ArUco geometry changed"):
            reference_homography(cv2, self.old, self.new, self.table)

    def test_basket_can_be_removed_for_five_point_capture(self):
        without_basket = {key: value for key, value in self.new.items() if key != 4}
        _, quality = reference_homography(cv2, self.old, without_basket,
                                          self.table, require_id4=False)
        self.assertEqual(quality["stable_ids"], [0, 1, 3])
        with self.assertRaisesRegex(ValueError, "required"):
            reference_homography(cv2, self.old, without_basket, self.table)

    def test_id2_can_be_occluded_during_five_point_capture(self):
        visible = {key: value for key, value in self.new.items() if key not in (2, 4)}
        _, quality = reference_homography(cv2, self.old, visible,
                                          self.table, require_id4=False)
        self.assertEqual(quality["stable_ids"], [0, 1, 3])
        self.assertIsNone(quality["id2_holdout_drift_px"])


if __name__ == "__main__":
    unittest.main()
