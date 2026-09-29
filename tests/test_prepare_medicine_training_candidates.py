import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from prepare_medicine_training_candidates import Record, choose_representatives, parse_label


def record(stem, x, sharpness=1.0, priority=1, image_hash=None):
    path = Path(f"/{stem}")
    return Record(
        source="test", stem=stem, image=path, label=path, metadata=path,
        kind="positive", bbox=(x / 640, 0.5, 0.05, 0.08),
        image_hash=image_hash or stem, sharpness=sharpness, review_priority=priority,
    )


class PrepareMedicineCandidatesTests(unittest.TestCase):
    def test_parse_label(self):
        self.assertEqual(parse_label("")[0], "negative")
        kind, bbox = parse_label("0 0.5 0.5 0.1 0.2\n")
        self.assertEqual(kind, "positive")
        self.assertEqual(bbox, (0.5, 0.5, 0.1, 0.2))

    def test_rejects_out_of_frame_box(self):
        with self.assertRaises(ValueError):
            parse_label("0 0.02 0.5 0.1 0.2")

    def test_near_cluster_prefers_human_review_then_sharpness(self):
        low = record("low", 100, sharpness=99, priority=1)
        reviewed = record("reviewed", 105, sharpness=5, priority=2)
        far = record("far", 140, sharpness=1, priority=1)
        kept, excluded = choose_representatives([low, reviewed, far], 12)
        self.assertEqual({item.stem for item in kept}, {"reviewed", "far"})
        self.assertEqual(excluded[0]["representative"], "test_reviewed")

    def test_exact_duplicate_is_removed(self):
        first = record("a", 100, image_hash="same")
        second = record("b", 150, image_hash="same")
        kept, excluded = choose_representatives([first, second], 12)
        self.assertEqual(len(kept), 1)
        self.assertEqual(excluded[0]["reason"], "exact_image_duplicate")


if __name__ == "__main__":
    unittest.main()
