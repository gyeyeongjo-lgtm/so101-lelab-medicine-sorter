import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from summarize_teleop_activity import summarize


JOINTS = ("Rotation", "Pitch", "Elbow", "Wrist_Pitch", "Wrist_Roll", "Jaw")


def sample(received_ns, rotation=0.0):
    pose = dict.fromkeys(JOINTS, 0.0)
    pose["Rotation"] = rotation
    return {"received_unix_ns": received_ns, "joints_rad": pose}


class ActivitySummaryTests(unittest.TestCase):
    def test_provisional_window_and_frame_coverage(self):
        samples = [sample(1_000_000_000), sample(2_000_000_000),
                   sample(3_000_000_000, 0.02), sample(4_000_000_000, 0.02)]
        frames = {"ceiling": [{"received_unix_ns": t} for t in
                              (1_500_000_000, 3_200_000_000, 3_700_000_000)]}
        result = summarize(samples, frames, 0.01)
        self.assertEqual(result["first_active_sample_index"], 2)
        self.assertEqual(result["initial_idle_duration_s"], 2)
        self.assertEqual(result["provisional_activity_duration_s"], 1)
        self.assertEqual(result["cameras"]["ceiling"]["frames_in_provisional_activity_window"], 2)
        self.assertEqual(result["cameras"]["ceiling"]["max_interframe_gap_s"], 0.5)
        self.assertFalse(result["training_ready"])
        self.assertFalse(result["motion_authorized"])

    def test_no_departure_is_not_a_demonstration(self):
        result = summarize([sample(1), sample(2, 0.01)], {"ceiling": []}, 0.01)
        self.assertEqual(result["status"], "NO_POSE_DEPARTURE")
        self.assertIsNone(result["first_active_sample_index"])
        self.assertEqual(result["joint_samples_in_window"], 0)

    def test_bad_timestamps_and_threshold_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "timestamps must increase"):
            summarize([sample(2), sample(1)], {}, 0.01)
        with self.assertRaisesRegex(ValueError, "positive finite threshold"):
            summarize([sample(1)], {}, float("nan"))


if __name__ == "__main__":
    unittest.main()
