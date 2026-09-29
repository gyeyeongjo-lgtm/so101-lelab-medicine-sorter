import json
import sys
from pathlib import Path
import tempfile
import unittest

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from depth_foreground_candidates import (
    bbox_to_yolo,
    deproject_dense_depth,
    load_pickup_candidate_filter,
    load_pickup_roi,
    select_pickup_candidate,
    validate_reviewed_bbox,
)


class PickupRoiTests(unittest.TestCase):
    def test_dense_deprojection_preserves_depth_z(self):
        rays = np.array([[0.04, -0.12], [-0.2, 0.1]], dtype=np.float64)
        depth = np.array([788.0, 900.0], dtype=np.float64)
        points = deproject_dense_depth(np, rays, depth)

        np.testing.assert_array_equal(depth, [788.0, 900.0])
        np.testing.assert_allclose(points, [[31.52, -94.56, 788.0], [-180.0, 90.0, 900.0]])

    def test_reviewed_bbox_must_contain_selected_depth_box(self):
        validate_reviewed_bbox([147, 105, 15, 25], [147, 105, 15, 13], 320, 240)
        with self.assertRaises(ValueError):
            validate_reviewed_bbox([147, 105, 15, 12], [147, 105, 15, 13], 320, 240)
        with self.assertRaises(ValueError):
            validate_reviewed_bbox([310, 105, 15, 25], [311, 105, 13, 13], 320, 240)

    def test_load_pickup_roi(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workspace.json"
            path.write_text(
                json.dumps(
                    {"pickup_roi_table_mm": {"x": [80, 220], "y": [200, 300]}}
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                load_pickup_roi(path),
                {"x": [80.0, 220.0], "y": [200.0, 300.0]},
            )

    def test_load_pickup_candidate_filter(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workspace.json"
            path.write_text(
                json.dumps(
                    {
                        "pickup_candidate_filter": {
                            "min_area_px": 100,
                            "max_area_px": 500,
                            "min_height_median_mm": 70,
                            "max_height_median_mm": 120,
                        }
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                load_pickup_candidate_filter(path),
                {
                    "min_area_px": 100.0,
                    "max_area_px": 500.0,
                    "min_height_median_mm": 70.0,
                    "max_height_median_mm": 120.0,
                },
            )

    def test_selects_largest_candidate_inside_pickup_roi(self):
        candidates = [
            {"candidate_id": "C0", "table_xy_mm": [140, 430], "area_px": 900, "height_median_mm": 90},
            {"candidate_id": "C1", "table_xy_mm": [140, 242], "area_px": 53, "height_median_mm": 42},
            {"candidate_id": "C2", "table_xy_mm": [150, 250], "area_px": 30, "height_median_mm": 60},
        ]

        selected = select_pickup_candidate(
            candidates, {"x": [80.0, 220.0], "y": [200.0, 300.0]}
        )

        self.assertIs(selected, candidates[1])

    def test_returns_none_when_pickup_roi_is_empty(self):
        candidates = [
            {"candidate_id": "C0", "table_xy_mm": [140, 430], "area_px": 900, "height_median_mm": 90}
        ]

        self.assertIsNone(
            select_pickup_candidate(
                candidates, {"x": [80.0, 220.0], "y": [200.0, 300.0]}
            )
        )

    def test_rejects_partial_fragment_inside_roi(self):
        candidates = [
            {
                "candidate_id": "C5",
                "table_xy_mm": [194, 267],
                "area_px": 35,
                "height_median_mm": 44,
            }
        ]
        candidate_filter = {
            "min_area_px": 100.0,
            "max_area_px": 500.0,
            "min_height_median_mm": 70.0,
            "max_height_median_mm": 120.0,
        }

        self.assertIsNone(
            select_pickup_candidate(
                candidates,
                {"x": [80.0, 220.0], "y": [200.0, 300.0]},
                candidate_filter,
            )
        )

    def test_bbox_to_yolo_adds_and_clips_margin(self):
        self.assertEqual(
            bbox_to_yolo([1, 2, 10, 20], 100, 50, margin_px=3),
            (0.07, 0.25, 0.14, 0.5),
        )


if __name__ == "__main__":
    unittest.main()
