from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

import yaml

from scripts.recorded_pose_config import build_pose_record, save_pose_records
from scripts.staged_cycle_execution import JOINT_UNITS


class RecordedPoseConfigTests(unittest.TestCase):
    def test_empirical_pose_preserves_ideal_ik_and_reports_difference(self):
        sample = {name: 1.0 for name in JOINT_UNITS}
        ideal = {name: 0.5 for name in JOINT_UNITS if name != "gripper"}
        record = build_pose_record(
            name="C_PREAPPROACH_EMPIRICAL",
            raw_samples=[sample] * 3,
            degree_samples=[sample] * 3,
            fk_grasp_tcp_samples_mm=[[1.0, 2.0, 3.0]] * 3,
            recorded_at="2026-10-14T15:00:00+09:00",
            note="User-confirmed physical C alignment",
            ideal_ik_joints_deg=ideal,
            ideal_ik_fk_grasp_tcp_mm=[0.0, 2.0, 3.0],
        )
        self.assertEqual(record["ideal_ik_reference"]["joint_difference_empirical_minus_ideal_deg"]["elbow_flex"], 0.5)
        self.assertEqual(record["ideal_ik_reference"]["task_space_position_error_norm_mm"], 1.0)

    def test_exactly_three_samples_store_mean_and_population_std(self):
        raw = [{name: 100 + index for name in JOINT_UNITS} for index in range(3)]
        degree = [{name: 10.0 + index for name in JOINT_UNITS} for index in range(3)]
        record = build_pose_record(
            name="HOME", raw_samples=raw, degree_samples=degree,
            fk_grasp_tcp_samples_mm=[[1, 2, 100], [2, 3, 101], [3, 4, 102]],
            recorded_at=datetime.now(timezone.utc).isoformat(), note="test only")
        self.assertEqual(record["sample_count"], 3)
        self.assertEqual(record["joints"]["shoulder_pan"]["raw_mean"], 101.0)
        self.assertGreater(record["joints"]["shoulder_pan"]["raw_std"], 0.0)
        self.assertEqual(record["fk_grasp_tcp_mm"]["z"], 101.0)

    def test_placeholder_or_partial_samples_are_rejected(self):
        sample = {name: 0 for name in JOINT_UNITS}
        with self.assertRaisesRegex(ValueError, "exactly_three"):
            build_pose_record(
                name="SAFE_HIGH", raw_samples=[sample, sample],
                degree_samples=[sample, sample],
                fk_grasp_tcp_samples_mm=[[0, 0, 100]] * 3,
                recorded_at=datetime.now(timezone.utc).isoformat(), note="test")

    def test_safe_high_can_be_saved_before_home_without_fake_values(self):
        raw = [{name: 100 for name in JOINT_UNITS}] * 3
        degree = [{name: 10.0 for name in JOINT_UNITS}] * 3
        record = build_pose_record(
            name="SAFE_HIGH", raw_samples=raw, degree_samples=degree,
            fk_grasp_tcp_samples_mm=[[1, 2, 200]] * 3,
            recorded_at=datetime.now(timezone.utc).isoformat(), note="measured")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "poses.yaml"
            save_pose_records(path, {"SAFE_HIGH": record})
            saved = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertEqual(saved["runtime_start_pose"], "PICK_READY")
            self.assertEqual(
                saved["pose_roles"]["HOME"], "STORAGE_PARKING_ONLY")
            self.assertEqual(saved["pose_status"]["SAFE_HIGH"], "RECORDED")
            self.assertEqual(saved["pose_status"]["HOME"], "NOT_RECORDED")
            self.assertEqual(saved["pose_status"]["PICK_READY"], "NOT_RECORDED")
            self.assertNotIn("HOME", saved["poses"])
            with self.assertRaisesRegex(ValueError, "both_required"):
                save_pose_records(
                    path, {"SAFE_HIGH": record}, require_complete=True)

    def test_pick_ready_records_temperature_without_changing_return_pair(self):
        raw = [{name: 200 + index for name in JOINT_UNITS} for index in range(3)]
        degree = [{name: 20.0 + index for name in JOINT_UNITS} for index in range(3)]
        temperature = [
            {name: 35.0 + index for name in JOINT_UNITS} for index in range(3)
        ]
        record = build_pose_record(
            name="PICK_READY", raw_samples=raw, degree_samples=degree,
            fk_grasp_tcp_samples_mm=[[1, 2, 180], [2, 3, 181], [3, 4, 182]],
            temperature_samples_c=temperature,
            recorded_at=datetime.now(timezone.utc).isoformat(), note="measured")
        self.assertEqual(record["temperature_c"]["elbow_flex"]["maximum"], 37.0)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "poses.yaml"
            save_pose_records(path, {"PICK_READY": record})
            saved = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertEqual(saved["pose_status"]["PICK_READY"], "RECORDED")
            self.assertEqual(saved["pose_status"]["HOME"], "NOT_RECORDED")
            self.assertEqual(saved["pose_status"]["SAFE_HIGH"], "NOT_RECORDED")

    def test_require_complete_allows_optional_pick_ready(self):
        raw = [{name: 100 for name in JOINT_UNITS}] * 3
        degree = [{name: 10.0 for name in JOINT_UNITS}] * 3
        records = {
            name: build_pose_record(
                name=name, raw_samples=raw, degree_samples=degree,
                fk_grasp_tcp_samples_mm=[[1, 2, 200]] * 3,
                recorded_at=datetime.now(timezone.utc).isoformat(), note="measured")
            for name in ("HOME", "SAFE_HIGH", "PICK_READY")
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "poses.yaml"
            save_pose_records(path, records, require_complete=True)
            saved = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertTrue(all(
                saved["pose_status"][name] == "RECORDED" for name in records))


if __name__ == "__main__":
    unittest.main()
