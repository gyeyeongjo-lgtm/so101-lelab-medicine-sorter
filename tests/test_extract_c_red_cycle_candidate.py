import unittest

from scripts.extract_c_red_cycle_candidate import (
    AXES, first_violation, interpolation_errors, rdp_indices,
)


def row(seq, elbow):
    values = {axis: 0.0 for axis in AXES}
    values["elbow_flex"] = elbow
    return {
        "seq": seq, "started_monotonic_ns": seq * 1_000_000_000,
        "follower_command": dict(values), "follower_feedback": dict(values),
    }


class ExtractCandidateTests(unittest.TestCase):
    def test_gap_splitting_rechecks_interpolation_error(self):
        rows = [row(i, elbow) for i, elbow in enumerate((0.0, 0.4, -0.4, 0.0))]
        times = [r["started_monotonic_ns"] for r in rows]
        indices = rdp_indices(rows, times, {0, 3}, (0.5,) * 6, 1.0, 1.0, 1.0, 1.0)
        self.assertEqual(indices, [0, 1, 2, 3])
        self.assertLessEqual(interpolation_errors(rows, times, indices)["elbow_flex"], 0.5)

    def test_first_violation_keeps_original_out_of_range_sample(self):
        rows = [row(i, elbow) for i, elbow in enumerate((89.9, 90.02, 90.3))]
        limits = {
            "Rotation": (-2, 2), "Pitch": (-2, 2), "Elbow": (-1.74533, 1.5708),
            "Wrist_Pitch": (-2, 2), "Wrist_Roll": (-3, 3),
        }
        self.assertEqual(first_violation(rows, limits, "follower_feedback", after_ns=0,
                                         joint="elbow_flex"), 1)
        self.assertEqual(rows[1]["follower_feedback"]["elbow_flex"], 90.02)


if __name__ == "__main__":
    unittest.main()
