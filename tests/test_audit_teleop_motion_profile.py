import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.audit_teleop_motion_profile import audit_motion_profile
from scripts.audit_teleop_trace import JOINT_NAMES


def make_trace(root: Path, times: list[float], elbows: list[float]) -> tuple[Path, Path]:
    trace = root / "trace"
    trace.mkdir()
    records = []
    for index, (stamp, elbow) in enumerate(zip(times, elbows)):
        joints = {joint: 0.0 for joint in JOINT_NAMES}
        joints["Elbow"] = elbow
        records.append({"source_unix": stamp, "received_unix_ns": 1_000_000_000 + index * 50_000_000,
                        "joints_rad": joints})
    raw = b"".join((json.dumps(row) + "\n").encode() for row in records)
    (trace / "joints.jsonl").write_bytes(raw)
    (trace / "manifest.json").write_text(json.dumps({
        "joint_file": "joints.jsonl", "joint_file_sha256": hashlib.sha256(raw).hexdigest(),
        "sample_count": len(records),
    }))
    limits = root / "limits.json"
    limits.write_text(json.dumps({"source_sha256": "fixture", "joints": {
        joint: [-2.0, 2.0] for joint in JOINT_NAMES
    }}))
    return trace, limits


class MotionProfileTests(unittest.TestCase):
    def test_observed_changes_do_not_authorize_motion(self):
        with tempfile.TemporaryDirectory() as temporary:
            trace, limits = make_trace(Path(temporary), [1.0, 1.05, 1.1], [0.0, 0.1, 0.1])
            result = audit_motion_profile(trace, limits)
            self.assertEqual(result["valid_adjacent_pairs"], 2)
            self.assertEqual(result["joints"]["Elbow"]["unchanged_adjacent_pairs"], 1)
            self.assertAlmostEqual(result["joints"]["Elbow"]["max_observed_finite_difference_deg_s"],
                                   114.592, places=3)
            self.assertFalse(result["continuous_path_verified"])
            self.assertFalse(result["motion_authorized"])

    def test_gaps_and_reversed_source_are_disclosed(self):
        with tempfile.TemporaryDirectory() as temporary:
            trace, limits = make_trace(Path(temporary), [1.0, 1.4, 1.3], [0.0, 0.1, 0.2])
            result = audit_motion_profile(trace, limits)
            self.assertEqual(result["source_gaps_over_200ms"], 1)
            self.assertEqual(result["invalid_timestamp_pairs"], 1)
            self.assertEqual(result["valid_adjacent_pairs"], 1)

    def test_hash_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            trace, limits = make_trace(Path(temporary), [1.0], [0.0])
            (trace / "joints.jsonl").write_text("changed")
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                audit_motion_profile(trace, limits)

    def test_source_has_no_control_route(self):
        source = (Path(__file__).resolve().parents[1] / "scripts" /
                  "audit_teleop_motion_profile.py").read_text()
        for forbidden in ("/move-arm", "/stop-teleoperation", "serial.Serial", "Goal_Position"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
