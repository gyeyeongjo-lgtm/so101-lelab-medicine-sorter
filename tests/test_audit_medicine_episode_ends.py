import importlib.util
from pathlib import Path
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/audit_medicine_episode_ends.py"
SPEC = importlib.util.spec_from_file_location("audit_medicine_episode_ends", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class EpisodeEndAuditTests(unittest.TestCase):
    def test_video_path_uses_recorded_file_index(self):
        row = {
            "videos/observation.images.ceiling_vertical/chunk_index": 0,
            "videos/observation.images.ceiling_vertical/file_index": 2,
        }
        path = MODULE.episode_video(Path("/dataset"), row, MODULE.CAMERA)
        self.assertEqual(
            path,
            Path("/dataset/videos/observation.images.ceiling_vertical/chunk-000/file-002.mp4"),
        )

    def test_video_path_rejects_negative_index(self):
        row = {
            "videos/observation.images.ceiling_vertical/chunk_index": 0,
            "videos/observation.images.ceiling_vertical/file_index": -1,
        }
        with self.assertRaises(ValueError):
            MODULE.episode_video(Path("/dataset"), row, MODULE.CAMERA)

    def test_target_is_last_frame_before_boundary(self):
        row = {
            "videos/observation.images.ceiling_vertical/from_timestamp": 32.0666666667,
            "videos/observation.images.ceiling_vertical/to_timestamp": 53.3,
        }
        self.assertAlmostEqual(MODULE.end_target(row, MODULE.CAMERA, 30), 53.2666666667)

    def test_target_does_not_precede_short_episode_start(self):
        row = {
            "videos/observation.images.ceiling_vertical/from_timestamp": 1.0,
            "videos/observation.images.ceiling_vertical/to_timestamp": 1.02,
        }
        self.assertEqual(MODULE.end_target(row, MODULE.CAMERA, 30), 1.0)

    def test_target_rejects_invalid_timing(self):
        row = {
            "videos/observation.images.ceiling_vertical/from_timestamp": 2.0,
            "videos/observation.images.ceiling_vertical/to_timestamp": 1.0,
        }
        with self.assertRaises(ValueError):
            MODULE.end_target(row, MODULE.CAMERA, 30)


if __name__ == "__main__":
    unittest.main()
