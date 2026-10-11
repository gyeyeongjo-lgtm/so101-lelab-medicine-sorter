import math
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from c_red_vision_ik_dry_run import (
    ARM_JOINTS, FOLLOWER_CALIBRATION_SHA256, classify_bottle_detections,
    operational_bounds_rad, solve_phase_targets, solve_position_ik, tcp_position_mm,
    validate_c_metadata,
)
from vision_guided_geometry import (
    basket_opening_table_xy, fit_table_to_robot_xy, nearest_table_slot,
    table_to_robot_xy,
)


class LinearFakeKinematics:
    def forward(self, joints, root, target):
        assert (root, target) == ("base", "gripper")
        transform = np.eye(4)
        transform[:3, 3] = [joints[ARM_JOINTS[index]] for index in range(3)]
        return transform


class CRedVisionIKDryRunTests(unittest.TestCase):
    def setUp(self):
        self.kinematics = LinearFakeKinematics()
        self.bounds = np.tile([-math.pi, math.pi], (5, 1))
        self.offset = np.zeros(3)

    def test_pending_servo_bounds_cannot_be_used_for_autonomous_ik(self):
        config = {"status": "PENDING_PHYSICAL_VALIDATION", "unit": "deg",
                  "follower_calibration_sha256": FOLLOWER_CALIBRATION_SHA256,
                  "joint_bounds_deg": {name: [-90, 90] for name in ARM_JOINTS}}
        with self.assertRaisesRegex(ValueError, "not independently verified"):
            operational_bounds_rad(config)
        config["status"] = "VERIFIED_FOR_AUTONOMOUS_PLANNING"
        with self.assertRaisesRegex(ValueError, "not independently verified"):
            operational_bounds_rad(config)
        config["physical_clearance_verified"] = True
        np.testing.assert_allclose(np.rad2deg(operational_bounds_rad(config))[2], [-90, 90])
        config["joint_bounds_deg"]["Elbow"] = [-97, 97]
        with self.assertRaisesRegex(ValueError, "2 degree reserve"):
            operational_bounds_rad(config)

    def test_position_ik_reaches_target_and_checks_fk(self):
        result = solve_position_ik(
            self.kinematics, np.array([100.0, 50.0, 25.0]),
            np.zeros(5), self.offset, self.bounds,
        )
        self.assertEqual(result["status"], "NUMERIC_POSITION_IK_PASS")
        self.assertLessEqual(result["position_residual_mm"], 1.0)
        self.assertFalse(result["orientation_solved"])
        self.assertFalse(result["collision_checked"])

    def test_seed_outside_urdf_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "seed outside"):
            solve_position_ik(
                self.kinematics, np.zeros(3),
                np.array([181.0, 0.0, 0.0, 0.0, 0.0]), self.offset, self.bounds,
            )

    def test_unreachable_target_is_not_reported_as_pass(self):
        tight_bounds = np.tile([-0.1, 0.1], (5, 1))
        result = solve_position_ik(
            self.kinematics, np.array([1000.0, 0.0, 0.0]),
            np.zeros(5), self.offset, tight_bounds,
        )
        self.assertEqual(result["status"], "IK_UNREACHABLE_OR_UNCONVERGED")
        self.assertLessEqual(abs(result["joint_target_deg"]["Rotation"]), math.degrees(0.1) + 1e-6)

    def test_tcp_offset_is_included_in_fk(self):
        point = tcp_position_mm(self.kinematics, np.zeros(5), np.array([1.0, 2.0, 3.0]))
        np.testing.assert_allclose(point, [1.0, 2.0, 3.0])

    def test_saved_c_label_must_match_exact_image(self):
        validate_c_metadata({"human_verified_label": "C", "raw_jpeg_sha256": "abc"}, "abc")
        with self.assertRaisesRegex(ValueError, "does not match"):
            validate_c_metadata({"human_verified_label": "C", "raw_jpeg_sha256": "old"}, "abc")
        validate_c_metadata({"human_verified_label": "B", "raw_jpeg_sha256": "abc"}, "abc")

    def test_nearest_table_slot_uses_table_xy_not_human_label(self):
        slots = {"schema_version": 1, "unit": "mm", "slots": {
            "A": [75, 350], "B": [180, 335], "C": [290, 330]},
            "max_distance_mm": 45, "minimum_runner_up_gap_mm": 25}
        self.assertEqual(nearest_table_slot([289, 331], slots)["identity"], "C")
        self.assertIsNone(nearest_table_slot([230, 330], slots)["identity"])

    def test_missing_reference_or_red_marker_blocks_projection(self):
        slots = {"schema_version": 1, "unit": "mm", "slots": {
            "A": [75, 350], "B": [180, 335], "C": [290, 330]},
            "max_distance_mm": 45, "minimum_runner_up_gap_mm": 25}
        detection = {"confidence": 0.8, "xyxy": [305, 220, 331, 257],
                     "image_center_table_mm": [290.0, 330.0], "inside_pickup_roi": False,
                     "class_name": "white_medicine_bottle_model"}
        table = {"ready": True, "detected_ids": [0, 1, 2, 3, 4],
                 "basket_mapping": {"4": "red"},
                 "basket_markers": {"4": {"color": "red"}}}
        self.assertEqual(classify_bottle_detections([detection], table, slots)[0]["identity"], "C")
        for missing_id in (0, 4):
            incomplete = {**table, "detected_ids": [i for i in table["detected_ids"] if i != missing_id]}
            with self.assertRaisesRegex(ValueError, "marker missing"):
                classify_bottle_detections([detection], incomplete, slots)

    def test_missing_table_projection_blocks_numeric_target(self):
        slots = {"schema_version": 1, "unit": "mm", "slots": {
            "A": [75, 350], "B": [180, 335], "C": [290, 330]},
            "max_distance_mm": 45, "minimum_runner_up_gap_mm": 25}
        table = {"ready": True, "detected_ids": [0, 1, 2, 3, 4],
                 "basket_mapping": {"4": "red"},
                 "basket_markers": {"4": {"color": "red"}}}
        detection = {"confidence": 0.8, "xyxy": [305, 220, 331, 257],
                     "image_center_table_mm": None, "inside_pickup_roi": False,
                     "class_name": "white_medicine_bottle_model"}
        with self.assertRaisesRegex(ValueError, "projection missing"):
            classify_bottle_detections([detection], table, slots)

    def test_five_point_fit_and_independent_holdout(self):
        table = [[0, 0], [200, 0], [0, 150], [200, 150], [100, 75]]
        robot = [[50 - y, -100 + x] for x, y in table]
        records = [{"name": f"p{i}", "role": "fit" if i < 4 else "holdout",
                    "table_xy_mm": xy, "robot_tcp_xy_mm": rxy,
                    "contact_verified": True, "tcp_verified": True,
                    "image_joint_synchronized": True}
                   for i, (xy, rxy) in enumerate(zip(table, robot))]
        document = {"schema_version": 1, "unit": "mm", "points": records,
                    "tcp_offset_verified": True, "tcp_offset_gripper_link_mm": [1, 2, 3]}
        fit = fit_table_to_robot_xy(document)
        self.assertEqual(fit["status"], "ACCEPTED_HOLDOUT_PASS")
        np.testing.assert_allclose(table_to_robot_xy([100, 75], fit), robot[4], atol=0.001)
        document["points"][-1]["robot_tcp_xy_mm"] = [robot[4][0] + 20, robot[4][1]]
        self.assertEqual(fit_table_to_robot_xy(document)["status"], "REJECTED_FIT_OR_HOLDOUT")
        document["points"][-1]["table_xy_mm"] = table[0]
        with self.assertRaisesRegex(ValueError, "different table point"):
            fit_table_to_robot_xy(document)

    def test_unverified_tcp_pair_and_basket_offset_stay_blocked(self):
        with self.assertRaisesRegex(ValueError, "verified 3D grasp TCP"):
            fit_table_to_robot_xy({"schema_version": 1, "unit": "mm", "points": []})
        basket = basket_opening_table_xy([300, 130], {
            "marker_id": 4, "color": "red", "opening_offset_from_marker_table_mm": [-2, 99],
            "opening_offset_verified": False})
        self.assertEqual(basket["opening_table_xy_mm"], [298, 229])
        self.assertFalse(basket["offset_verified"])

    def test_five_discrete_ik_targets_have_urdf_and_fk_result(self):
        targets = solve_phase_targets(
            self.kinematics, self.bounds, self.offset,
            [100, 50], [50, 100],
            {"Z_SAFE": 75, "Z_APPROACH": 80, "Z_GRASP": 60,
             "Z_LIFT": 100, "Z_PLACE": 50},
            np.zeros(5),
        )
        self.assertEqual(list(targets), ["approach", "grasp", "lift", "red_basket_hover", "place"])
        self.assertTrue(all(target["status"] == "NUMERIC_POSITION_IK_PASS"
                            for target in targets.values()))
        self.assertTrue(all(target["minimum_reserved_urdf_margin_deg"] > 0
                            for target in targets.values()))

    def test_phase_ik_requires_observed_start_inside_selected_planning_limits(self):
        heights = {"Z_SAFE": 75, "Z_APPROACH": 80, "Z_GRASP": 60,
                   "Z_LIFT": 100, "Z_PLACE": 50}
        with self.assertRaisesRegex(ValueError, "observed follower start outside"):
            solve_phase_targets(self.kinematics, self.bounds, self.offset,
                                [100, 50], [50, 100], heights,
                                np.array([181, 0, 0, 0, 0]))


if __name__ == "__main__":
    unittest.main()
