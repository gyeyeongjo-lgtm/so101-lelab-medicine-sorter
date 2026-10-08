import unittest

import cv2
import numpy as np

from scripts.audit_c_red_cap_candidate_offline import cap_components


class CapCandidateTests(unittest.TestCase):
    def setUp(self):
        self.image = np.full((480, 640, 3), (145, 95, 55), np.uint8)
        # Bright top and bottom basket trim should not count as a medicine cap.
        cv2.rectangle(self.image, (286, 265), (343, 270), (235, 235, 235), -1)
        cv2.rectangle(self.image, (286, 315), (343, 324), (235, 235, 235), -1)

    def test_empty_basket_trim_is_not_cap(self):
        self.assertEqual(cap_components(self.image, (316, 347)), [])

    def test_large_white_cap_is_candidate(self):
        cv2.circle(self.image, (316, 289), 13, (240, 240, 240), -1)
        self.assertEqual(len(cap_components(self.image, (316, 347))), 1)

    def test_wrong_image_size_is_rejected(self):
        with self.assertRaises(ValueError):
            cap_components(self.image[:400], (316, 347))


if __name__ == "__main__":
    unittest.main()
