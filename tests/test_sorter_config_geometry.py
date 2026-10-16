import json
import math
import tempfile
import unittest
from pathlib import Path

from medicine_sorter.config import load_config
from medicine_sorter.errors import SorterError
from medicine_sorter.geometry import RigidTransform, m_to_mm, mm_to_m


ROOT = Path(__file__).resolve().parents[1]


class SorterConfigGeometryTests(unittest.TestCase):
    def test_example_config_is_valid_and_live_blocked(self):
        config = load_config(ROOT / "configs/system.example.json")
        readiness = config.readiness("full_sort")
        self.assertFalse(readiness["live_ready"])
        self.assertIn("table_to_robot_base", readiness["missing_or_unverified"])
        self.assertIn("robot.live_enabled", readiness["missing_or_unverified"])

    def test_readiness_is_task_specific(self):
        config = load_config(ROOT / "configs/system.example.json")
        self.assertTrue(config.readiness("offline_mock")["ready"])
        self.assertTrue(config.readiness("robot_status")["ready"])
        self.assertTrue(config.readiness("robot_calibration")["ready"])
        self.assertFalse(config.readiness("camera_status")["ready"])
        teaching = config.readiness("supervised_teaching")
        fixed_demo = config.readiness("fixed_demo")
        self.assertNotIn("camera_intrinsics",
                         config.readiness("robot_status")["missing_or_unverified"])
        self.assertNotIn("motion_paths",
                         config.readiness("robot_status")["missing_or_unverified"])
        self.assertNotIn("motion_paths", teaching["missing_or_unverified"])
        self.assertIn("torque_lifecycle", teaching["missing_or_unverified"])
        self.assertIn("tcp", fixed_demo["missing_or_unverified"])
        self.assertIn("motion_paths", fixed_demo["missing_or_unverified"])
        self.assertIn("torque_lifecycle", fixed_demo["missing_or_unverified"])
        self.assertNotIn("camera_intrinsics", fixed_demo["missing_or_unverified"])
        self.assertNotIn("camera_to_table", fixed_demo["missing_or_unverified"])
        self.assertNotIn("table_to_robot_base", fixed_demo["missing_or_unverified"])
        self.assertNotIn("basket_openings", fixed_demo["missing_or_unverified"])
        self.assertIn("motion_paths",
                      config.readiness("full_sort")["missing_or_unverified"])
        self.assertIn("torque_lifecycle",
                      config.readiness("full_sort")["missing_or_unverified"])

    def test_fixed_demo_can_be_verified_without_camera_to_robot_transform(self):
        raw = json.loads((ROOT / "configs/system.example.json").read_text())
        raw["robot"]["live_enabled"] = True
        for name in ("joint", "tcp", "motion_paths", "torque_lifecycle"):
            raw["calibration"][name] = {"status": "verified"}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps(raw))
            config = load_config(path)
        self.assertTrue(config.readiness("supervised_teaching")["ready"])
        self.assertTrue(config.readiness("fixed_demo")["ready"])
        self.assertFalse(config.readiness("full_sort")["ready"])
        self.assertIn("table_to_robot_base",
                      config.readiness("full_sort")["missing_or_unverified"])

    def test_invalid_units_and_duplicate_mapping_fail(self):
        raw = json.loads((ROOT / "configs/system.example.json").read_text())
        for mutate, code in [
            (lambda item: item.update(units={"length": "m", "angle": "rad"}),
             "unsupported_internal_units"),
            (lambda item: item["baskets"]["red"].update(marker_id=5),
             "duplicate_basket_marker"),
        ]:
            changed = json.loads(json.dumps(raw))
            mutate(changed)
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "config.json"
                path.write_text(json.dumps(changed))
                with self.assertRaises(SorterError) as caught:
                    load_config(path)
                self.assertEqual(caught.exception.code, code)

    def test_unique_onsite_basket_ids_are_configurable(self):
        raw = json.loads((ROOT / "configs/system.example.json").read_text())
        for color, marker_id in {"red": 14, "green": 15, "blue": 16}.items():
            raw["baskets"][color]["marker_id"] = marker_id
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps(raw))
            config = load_config(path)
        self.assertEqual({color.value: marker_id for color, marker_id in config.basket_markers.items()},
                         {"red": 14, "green": 15, "blue": 16})

    def test_transform_direction_inverse_and_composition(self):
        identity = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
        t_b_w = RigidTransform("B", "W", identity, (10.0, -20.0, 30.0))
        self.assertEqual(t_b_w.name, "T_B_W")
        self.assertEqual(t_b_w.apply_mm((1.0, 2.0, 3.0)), (11.0, -18.0, 33.0))
        recovered = t_b_w.inverse().apply_mm(t_b_w.apply_mm((4.0, 5.0, 6.0)))
        for actual, expected in zip(recovered, (4.0, 5.0, 6.0)):
            self.assertAlmostEqual(actual, expected)
        t_c_b = RigidTransform("C", "B", identity, (1.0, 2.0, 3.0))
        self.assertEqual(t_b_w.then(t_c_b).apply_mm((0.0, 0.0, 0.0)),
                         (11.0, -18.0, 33.0))

    def test_units_and_bad_rotation(self):
        self.assertEqual(mm_to_m(1250.0), 1.25)
        self.assertEqual(m_to_mm(1.25), 1250.0)
        with self.assertRaisesRegex(ValueError, "rotation_not_orthonormal"):
            RigidTransform("B", "W", ((1, 0, 0), (0, 2, 0), (0, 0, 1)), (0, 0, 0))
        with self.assertRaises(ValueError):
            mm_to_m(math.nan)
