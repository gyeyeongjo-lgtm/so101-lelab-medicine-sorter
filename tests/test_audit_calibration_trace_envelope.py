import hashlib
import json
import math
import tempfile
import unittest
from pathlib import Path

from scripts.audit_calibration_trace_envelope import (
    ARM_JOINTS,
    DEFAULT_CALIBRATION,
    audit_calibration_trace,
    load_calibration_bounds,
)
from scripts.audit_teleop_trace import JOINT_NAMES


def fixture(root: Path, elbow_rad: float) -> tuple[Path, Path, Path]:
    trace = root / "trace"
    trace.mkdir()
    positions = {joint: 0.0 for joint in JOINT_NAMES}
    positions["Elbow"] = elbow_rad
    raw = b"".join((json.dumps({
        "source_unix": 1.0 + index * 0.05,
        "received_unix_ns": 1_000_000_000 + index * 50_000_000,
        "joints_rad": positions,
    }) + "\n").encode() for index in range(2))
    (trace / "joints.jsonl").write_bytes(raw)
    (trace / "manifest.json").write_text(json.dumps({
        "joint_file": "joints.jsonl",
        "joint_file_sha256": hashlib.sha256(raw).hexdigest(),
        "sample_count": 2,
    }))
    urdf = root / "urdf.json"
    urdf.write_text(json.dumps({
        "source_sha256": "fixture",
        "joints": {joint: [-2.0, 2.0] for joint in JOINT_NAMES},
    }))
    calibration = root / "calibration.json"
    calibration.write_text(json.dumps({
        "schema_version": 1,
        "source_sha256": "a" * 64,
        "observed_on": "2026-10-08",
        "motor_model": "sts3215",
        "normalization_mode": "DEGREES",
        "resolution_steps": 4096,
        "arm_ranges_raw": {joint: [1000, 3000] for joint in ARM_JOINTS},
    }))
    return trace, calibration, urdf


class CalibrationTraceEnvelopeTests(unittest.TestCase):
    def test_near_calibration_limit_never_authorizes_motion(self):
        with tempfile.TemporaryDirectory() as temporary:
            trace, calibration, urdf = fixture(Path(temporary), elbow_rad=1.53)
            result = audit_calibration_trace(trace, calibration, urdf, near_limit_deg=1.0)
            self.assertEqual(result["status"], "OFFLINE_CALIBRATION_FILE_COMPARISON_ONLY")
            self.assertEqual(result["envelope"]["Elbow"]["outside_file_range_samples"], 0)
            self.assertEqual(result["envelope"]["Elbow"]["within_near_limit_samples"], 2)
            self.assertLess(result["envelope"]["Elbow"]["minimum_file_margin_deg"], 1)
            self.assertFalse(result["motion_authorized"])
            self.assertFalse(result["use_for_replay"])
            self.assertFalse(result["current_registers_checked"])

    def test_outside_calibration_file_range_is_reported_even_if_within_urdf(self):
        with tempfile.TemporaryDirectory() as temporary:
            trace, calibration, urdf = fixture(Path(temporary), elbow_rad=1.6)
            result = audit_calibration_trace(trace, calibration, urdf)
            self.assertEqual(result["urdf_audit_status"], "NO_URDF_LIMIT_MISMATCH_DETECTED")
            self.assertEqual(result["envelope"]["Elbow"]["outside_file_range_samples"], 2)
            self.assertLess(result["envelope"]["Elbow"]["minimum_file_margin_deg"], 0)

    def test_modified_joint_trace_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            trace, calibration, urdf = fixture(Path(temporary), elbow_rad=0.0)
            (trace / "joints.jsonl").write_text("modified\n")
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                audit_calibration_trace(trace, calibration, urdf)

    def test_invalid_calibration_bounds_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            trace, calibration, urdf = fixture(Path(temporary), elbow_rad=0.0)
            document = json.loads(calibration.read_text())
            document["arm_ranges_raw"]["Elbow"] = [True, 3000]
            calibration.write_text(json.dumps(document))
            with self.assertRaisesRegex(ValueError, "invalid raw calibration"):
                audit_calibration_trace(trace, calibration, urdf)

    def test_dated_installed_snapshot_matches_recorded_elbow_range(self):
        bounds, document = load_calibration_bounds(DEFAULT_CALIBRATION)
        self.assertEqual(document["arm_ranges_raw"]["Elbow"], [880, 3087])
        self.assertAlmostEqual(math.degrees(bounds["Elbow"]), 97.010989, places=5)

    def test_observed_radians_reverse_to_expected_raw_grid(self):
        with tempfile.TemporaryDirectory() as temporary:
            elbow_rad = (2500 - 2000) * 2 * math.pi / 4095
            trace, calibration, urdf = fixture(Path(temporary), elbow_rad=elbow_rad)
            result = audit_calibration_trace(trace, calibration, urdf)
            envelope = result["envelope"]["Elbow"]
            self.assertEqual(envelope["observed_max_implied_raw"], 2500)
            self.assertEqual(envelope["max_raw_quantization_residual_steps"], 0)

    def test_source_has_no_robot_control_routes(self):
        source = (Path(__file__).resolve().parents[1] /
                  "scripts/audit_calibration_trace_envelope.py").read_text()
        for forbidden in ("/move-arm", "/stop-teleoperation", "serial.Serial", "Goal_Position"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
