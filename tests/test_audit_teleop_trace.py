import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.audit_teleop_trace import JOINT_NAMES, audit


def write_fixture(root: Path, *, elbow: float, corrupt_hash: bool = False):
    trace = root / "trace"
    trace.mkdir()
    limits = root / "limits.json"
    limits.write_text(json.dumps({
        "source_sha256": "fixture-urdf",
        "joints": {name: [-1.0, 1.0] for name in JOINT_NAMES},
    }))
    positions = {name: 0.0 for name in JOINT_NAMES}
    positions["Elbow"] = elbow
    lines = [json.dumps({"source_unix": 1.0 + i * 0.05,
                         "received_unix_ns": 1_000_000_000 + i * 50_000_000,
                         "joints_rad": positions}) for i in range(2)]
    raw = ("\n".join(lines) + "\n").encode()
    (trace / "joints.jsonl").write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    (trace / "manifest.json").write_text(json.dumps({
        "joint_file": "joints.jsonl", "joint_file_sha256": "wrong" if corrupt_hash else digest,
        "sample_count": 2,
    }))
    return trace, limits


class TeleopTraceAuditTests(unittest.TestCase):
    def test_limit_mismatch_is_reported_without_motion_authority(self):
        with tempfile.TemporaryDirectory() as temporary:
            trace, limits = write_fixture(Path(temporary), elbow=1.2)
            result = audit(trace, limits)
            self.assertEqual(result["status"], "URDF_LIMIT_MISMATCH")
            self.assertEqual(result["violations"]["Elbow"]["above"], 2)
            self.assertAlmostEqual(result["violations"]["Elbow"]["max_excess_rad"], 0.2)
            self.assertFalse(result["use_for_replay"])
            self.assertFalse(result["robot_enabled"])
            self.assertFalse(result["motion_authorized"])

    def test_no_mismatch_still_never_authorizes_replay(self):
        with tempfile.TemporaryDirectory() as temporary:
            trace, limits = write_fixture(Path(temporary), elbow=0.2)
            result = audit(trace, limits)
            self.assertEqual(result["status"], "NO_URDF_LIMIT_MISMATCH_DETECTED")
            self.assertEqual(result["sample_count"], 2)
            self.assertFalse(result["use_for_replay"])

    def test_rejects_modified_trace(self):
        with tempfile.TemporaryDirectory() as temporary:
            trace, limits = write_fixture(Path(temporary), elbow=0.2, corrupt_hash=True)
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                audit(trace, limits)

    def test_camera_frame_hash_is_verified_when_present(self):
        with tempfile.TemporaryDirectory() as temporary:
            trace, limits = write_fixture(Path(temporary), elbow=0.2)
            camera = trace / "ceiling"
            camera.mkdir()
            jpeg = b"\xff\xd8frame\xff\xd9"
            (camera / "2000000000.jpg").write_bytes(jpeg)
            index = (json.dumps({
                "filename": "2000000000.jpg", "received_unix_ns": 2_000_000_000,
                "sha256": hashlib.sha256(jpeg).hexdigest(),
            }) + "\n").encode()
            (camera / "frames.jsonl").write_bytes(index)
            manifest_file = trace / "manifest.json"
            manifest = json.loads(manifest_file.read_text())
            manifest["camera_evidence"] = {"ceiling": {
                "frame_count": 1, "index_sha256": hashlib.sha256(index).hexdigest(),
            }}
            manifest_file.write_text(json.dumps(manifest))
            self.assertEqual(audit(trace, limits)["verified_camera_frames"], {"ceiling": 1})
            (camera / "2000000000.jpg").write_bytes(b"modified")
            with self.assertRaisesRegex(ValueError, "frame SHA-256 mismatch"):
                audit(trace, limits)

    def test_camera_completion_cannot_hide_empty_stream(self):
        with tempfile.TemporaryDirectory() as temporary:
            trace, limits = write_fixture(Path(temporary), elbow=0.2)
            camera = trace / "oblique"
            camera.mkdir()
            (camera / "frames.jsonl").write_bytes(b"")
            manifest_file = trace / "manifest.json"
            manifest = json.loads(manifest_file.read_text())
            manifest["camera_evidence"] = {"oblique": {
                "frame_count": 0, "index_sha256": hashlib.sha256(b"").hexdigest(),
            }}
            manifest["camera_evidence_complete"] = True
            manifest_file.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "marked complete"):
                audit(trace, limits)

    def test_source_has_no_robot_control_routes(self):
        source = (Path(__file__).resolve().parents[1] / "scripts" / "audit_teleop_trace.py").read_text()
        for forbidden in ("/move-arm", "/stop-teleoperation", "/joint-positions", "serial.Serial"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
