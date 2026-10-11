import json
import math
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.c_red_five_point_calibration import (POINTS, Session, paired_snapshot,
                                                   urdf_model_limit_warnings)
from scripts.teach_capture_web import CaptureState, JOINT_NAMES
from scripts.vision_guided_geometry import fit_table_to_robot_xy


class FivePointCalibrationTests(unittest.TestCase):
    def test_read_only_fk_model_limit_disagreement_is_warning_not_block(self):
        limits = {"Elbow": (-1.74533, math.pi / 2)}
        joints = {"Elbow": math.radians(96.308)}
        warnings = urdf_model_limit_warnings(joints, limits)
        self.assertEqual(warnings[0]["joint"], "Elbow")
        self.assertEqual(warnings[0]["warning"], "OUTSIDE_URDF_MODEL_NOT_A_SERVO_LIMIT")

    def test_receive_time_pair_rejects_stale_camera_and_unsettled_arm(self):
        state = CaptureState()
        now = time.monotonic_ns()
        values = {name: 0.0 for name in JOINT_NAMES}
        for index in range(15):
            state.add_joint({"type": "joint_update", "timestamp": 1000 + index * .05,
                             "joints": values},
                            received_ns=now - (14 - index) * 50_000_000,
                            received_unix_ns=10_000_000_000 + index * 50_000_000)
        state.add_frame("ceiling", b"\xff\xd8test\xff\xd9",
                        received_ns=now - 30_000_000, received_unix_ns=11_000_000_000)
        pair = paired_snapshot(state, now)
        self.assertLessEqual(pair["receive_gap_ms"], 250)
        self.assertEqual(pair["joint"].joints["Elbow"], 0.0)
        with self.assertRaisesRegex(ValueError, "fresh"):
            paired_snapshot(state, now + 1_000_000_000)

    def test_se2_never_reflects_and_holdout_is_not_in_fit(self):
        points = [[0, 0], [200, 0], [200, 140], [0, 140], [100, 70]]
        theta = math.radians(20)
        rotation = np.asarray([[math.cos(theta), -math.sin(theta)],
                               [math.sin(theta), math.cos(theta)]])
        translation = np.asarray([80.0, -120.0])
        records = []
        for index, point in enumerate(points):
            robot = np.asarray(point) @ rotation + translation
            if index == 4:
                robot += [3.0, -4.0]
            records.append({"name": POINTS[index], "role": "holdout" if index == 4 else "fit",
                            "table_xy_mm": point, "robot_tcp_xy_mm": robot.tolist(),
                            "alignment_verified": True, "hover_height_verified": True,
                            "tcp_verified": True, "image_joint_synchronized": True})
        doc = {"schema_version": 1, "unit": "mm", "tcp_offset_verified": True,
               "tcp_offset_gripper_link_mm": [0, 0, 0], "points": records}
        result = fit_table_to_robot_xy(doc)
        self.assertEqual(result["status"], "ACCEPTED_HOLDOUT_PASS")
        self.assertEqual(result["holdout_max_mm"], 5.0)
        self.assertAlmostEqual(result["determinant"], 1.0)
        self.assertEqual(result["train_max_mm"], 0.0)
        reflected = {**doc, "points": [dict(r, robot_tcp_xy_mm=[-r["table_xy_mm"][0],
                                                           r["table_xy_mm"][1]]) for r in records]}
        result = fit_table_to_robot_xy(reflected)
        self.assertEqual(result["status"], "REJECTED_FIT_OR_HOLDOUT")
        self.assertAlmostEqual(result["determinant"], 1.0)

    def test_session_fit_blocks_hover_z_spread_and_stores_holdout_vector(self):
        with tempfile.TemporaryDirectory() as temporary:
            session = Session(CaptureState(), None, None, np.zeros(3), Path(temporary),
                              "http://invalid.local", "workspace-sha")
            for index, point in enumerate(([0, 0], [200, 0], [200, 140], [0, 140], [100, 70])):
                session.captures[POINTS[index]] = {
                    "point_id": POINTS[index], "role": "holdout" if index == 4 else "fit",
                    "table_xy_mm": point,
                    "robot_tcp_xyz_mm": [point[0] + 80, point[1] - 120, 100 if index < 4 else 108],
                }
            with self.assertRaisesRegex(ValueError, "hover TCP Z differs"):
                session.fit()
            session.captures["H1"]["robot_tcp_xyz_mm"][2] = 100
            result = session.fit()
            self.assertEqual(result["status"], "ACCEPTED_HOLDOUT_PASS")
            self.assertEqual(result["holdout_error_vector_robot_xy_mm"], [0.0, 0.0])
            self.assertTrue((Path(temporary) / "table_to_robot_fit.json").is_file())
            calibration = json.loads(
                (Path(temporary) / "table_to_robot_calibration.json").read_text())
            self.assertEqual([point["name"] for point in calibration["points"]], list(POINTS))
            self.assertEqual(fit_table_to_robot_xy(calibration)["status"], "ACCEPTED_HOLDOUT_PASS")

    def test_tcp_reference_cannot_be_guessed_or_changed_after_capture(self):
        with tempfile.TemporaryDirectory() as temporary:
            session = Session(CaptureState(), None, None, None, Path(temporary),
                              "http://invalid.local", "workspace-sha")
            with self.assertRaisesRegex(ValueError, "confirmed"):
                session.set_tcp_reference([20.2, 18.8, -23.4],
                                          physical_reference_confirmed=False,
                                          description="jaw pivot center")
            reference = session.set_tcp_reference([20.2, 18.8, -23.4],
                                                  physical_reference_confirmed=True,
                                                  description="jaw pivot center")
            self.assertEqual(reference["tcp_offset_gripper_link_mm"], [20.2, 18.8, -23.4])
            session.captures["P1"] = {}
            with self.assertRaisesRegex(ValueError, "after a point was captured"):
                session.set_tcp_reference([0, 0, 0], physical_reference_confirmed=True,
                                          description="another physical point")

    def test_red_opening_requires_independent_table_measurement(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = CaptureState()
            state.add_frame("ceiling", b"\xff\xd8test\xff\xd9")
            session = Session(state, None, None, None, Path(temporary),
                              "http://invalid.local", "workspace-sha")
            with self.assertRaisesRegex(ValueError, "physical measurement"):
                session.capture_red_opening([280, 200], physical_table_measurement_confirmed=False)
            with patch("scripts.c_red_five_point_calibration.frame_geometry",
                       return_value={"id4_marker_table_xy_mm": [282, 102],
                                     "aruco_ids": [0, 1, 2, 3, 4],
                                     "aruco_quality": {"stable_corner_rms_px": 0.1}}):
                record = session.capture_red_opening([280, 200],
                                                     physical_table_measurement_confirmed=True)
            self.assertEqual(record["opening_offset_from_marker_table_mm"], [-2.0, 98.0])
            self.assertTrue(record["opening_offset_verified"])


if __name__ == "__main__":
    unittest.main()
