import unittest

import numpy as np

from scripts.diagnose_aruco_reference_gaps import (
    corrected_xy,
    four_point_homography,
    marker_centers_from_edge_gaps,
)


class ReferenceGapDiagnosticTests(unittest.TestCase):
    def test_recovers_center_positions_from_black_square_gaps(self):
        expected = {
            0: np.array([0.0, 0.0]),
            1: np.array([400.0, 0.0]),
            2: np.array([400.0, 345.0]),
            3: np.array([0.0, 345.0]),
        }
        size = {0: 75.0, 1: 70.0, 2: 70.0, 3: 70.0}
        gaps = {}
        for a, b in ((0, 1), (1, 2), (2, 3), (3, 0), (0, 2), (1, 3)):
            separation = np.maximum(np.abs(expected[a] - expected[b]) - (size[a] + size[b]) / 2, 0.0)
            gaps[f"{a}-{b}"] = float(np.linalg.norm(separation))
        fitted, residuals = marker_centers_from_edge_gaps(
            {"reference_measurements_mm": gaps, "marker_size_mm": 70.0, "marker_size_by_id_mm": {"0": 75.0}}
        )
        for index in range(4):
            np.testing.assert_allclose(fitted[index], expected[index], atol=1e-5)
        self.assertLess(max(abs(value) for value in residuals.values()), 1e-5)

    def test_old_to_new_homography_maps_four_references(self):
        old = {0: np.array([0.0, 0.0]), 1: np.array([330.0, 0.0]), 2: np.array([330.0, 275.0]), 3: np.array([0.0, 275.0])}
        new = {0: np.array([0.0, 0.0]), 1: np.array([400.0, 0.0]), 2: np.array([400.0, 345.0]), 3: np.array([0.0, 345.0])}
        transform = four_point_homography(old, new)
        for index in range(4):
            np.testing.assert_allclose(corrected_xy(transform, old[index]), new[index], atol=1e-8)


if __name__ == "__main__":
    unittest.main()
