import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from prepare_yolo_medicine_dataset import (
    CaptureGroup,
    Sample,
    build_capture_groups,
    choose_validation_groups,
    parse_web_timestamp,
)


def sample(stem, kind, captured_at=None):
    path = Path(f"/{stem}")
    return Sample(stem, path, path, path, kind, captured_at)


class PrepareYoloMedicineDatasetTests(unittest.TestCase):
    def test_parse_web_timestamp(self):
        parsed = parse_web_timestamp("web_20260927T063256_123456Z")
        self.assertEqual(parsed, datetime(2026, 9, 27, 6, 32, 56))
        self.assertIsNone(parse_web_timestamp("legacy_candidate_001"))

    def test_capture_groups_keep_adjacent_frames_together(self):
        start = datetime(2026, 9, 27, 6, 0, 0)
        groups = build_capture_groups([
            sample("legacy_a", "positive"),
            sample("web_a", "positive", start),
            sample("web_b", "negative", start + timedelta(seconds=20)),
            sample("web_c", "positive", start + timedelta(seconds=70)),
        ], 30)
        self.assertTrue(groups[0].fixed_train)
        self.assertEqual([len(group.samples) for group in groups], [1, 2, 1])

    def test_validation_selection_contains_both_classes(self):
        groups = [
            CaptureGroup("fixed", [sample("legacy", "positive")], fixed_train=True),
            CaptureGroup("p1", [sample(f"p1-{i}", "positive") for i in range(3)]),
            CaptureGroup("p2", [sample(f"p2-{i}", "positive") for i in range(2)]),
            CaptureGroup("n1", [sample(f"n1-{i}", "negative") for i in range(2)]),
            CaptureGroup("n2", [sample("n2", "negative")]),
        ]
        selected = choose_validation_groups(groups, 0.25)
        validation = [s for g in groups if g.key in selected for s in g.samples]
        self.assertTrue(any(s.kind == "positive" for s in validation))
        self.assertTrue(any(s.kind == "negative" for s in validation))
        self.assertNotIn("fixed", selected)


if __name__ == "__main__":
    unittest.main()
