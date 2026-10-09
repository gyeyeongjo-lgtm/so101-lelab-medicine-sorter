import unittest

from scripts.safe_start_leader_targets import leader_targets


class LeaderTargetsTests(unittest.TestCase):
    def test_historical_offsets_are_used_only_when_explicitly_supplied(self):
        result = leader_targets(leader_elbow=94.593, follower_elbow=97.538,
                                leader_flex=55.297, follower_flex=57.714)
        self.assertAlmostEqual(result["teleop_compensation"]["elbow_flex"], 2.945)
        self.assertAlmostEqual(result["leader_target"]["elbow_flex"], 29.49456043956044)
        self.assertAlmostEqual(result["leader_target"]["wrist_flex"], 3.121461538461538)
        self.assertEqual(result["leader_target"]["shoulder_pan"],
                         result["follower_target"]["shoulder_pan"])
        self.assertFalse(result["motion_authorized"])

    def test_fresh_offsets_change_target_and_caps_block(self):
        result = leader_targets(leader_elbow=80.0, follower_elbow=81.0,
                                leader_flex=20.0, follower_flex=18.0)
        self.assertAlmostEqual(result["leader_target"]["elbow_flex"], 31.43956043956044)
        self.assertAlmostEqual(result["leader_target"]["wrist_flex"], 7.538461538461538)
        with self.assertRaisesRegex(ValueError, "cap_exceeded"):
            leader_targets(leader_elbow=80, follower_elbow=84,
                           leader_flex=20, follower_flex=18)


if __name__ == "__main__":
    unittest.main()
