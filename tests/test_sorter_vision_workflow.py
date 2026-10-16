import json
import tempfile
import threading
import unittest
from pathlib import Path

from medicine_sorter.config import load_config
from medicine_sorter.errors import SorterError
from medicine_sorter.models import BasketColor, BottleSize, SortCommand
from medicine_sorter.robot import MockRobotAdapter, RobotController
from medicine_sorter.vision import load_scene, select_basket, select_target
from medicine_sorter.workflow import STAGES, SorterApplication


ROOT = Path(__file__).resolve().parents[1]


class SorterVisionWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.config = load_config(ROOT / "configs/system.example.json")
        self.scene_path = ROOT / "configs/mock_scene.example.json"
        self.scene = load_scene(self.scene_path, self.config, recorded=True)

    def modified_scene(self, update):
        raw = json.loads(self.scene_path.read_text())
        update(raw)
        directory = tempfile.TemporaryDirectory()
        path = Path(directory.name) / "scene.json"
        path.write_text(json.dumps(raw))
        return directory, path

    def test_selects_requested_size_and_independent_color(self):
        command = SortCommand("sort", "medicine_bottle", BottleSize.LARGE, BasketColor.RED)
        self.assertEqual(select_target(self.scene, command).observation_id, "frame-001-A")
        self.assertEqual(select_basket(self.scene, command, self.config).marker_id, 4)

    def test_no_target_uncertain_target_and_missing_basket_fail(self):
        command = SortCommand("sort", "medicine_bottle", BottleSize.LARGE, BasketColor.RED)
        cases = [
            (lambda raw: raw.update(bottles=[]), "target_not_found"),
            (lambda raw: raw["bottles"][0].update(size=None, graspable=False), "target_not_found"),
            (lambda raw: raw.update(baskets=raw["baskets"][1:]), "destination_not_verified"),
            (lambda raw: raw["baskets"][0].update(marker_id=5), "destination_not_verified"),
        ]
        for update, code in cases:
            directory, path = self.modified_scene(update)
            try:
                scene = load_scene(path, self.config, recorded=True)
                with self.assertRaises(SorterError) as caught:
                    (select_target(scene, command) if code == "target_not_found"
                     else select_basket(scene, command, self.config))
                self.assertEqual(caught.exception.code, code)
            finally:
                directory.cleanup()

    def test_stale_depth_and_config_mismatch_fail(self):
        cases = [
            (lambda raw: raw.update(observed_at_s=1.0), {"recorded": False, "now_s": 3.0}, "stale_scene"),
            (lambda raw: raw.update(rgb_depth_aligned=False), {"recorded": True}, "rgb_depth_mismatch"),
            (lambda raw: raw.update(config_id="old"), {"recorded": True}, "scene_config_mismatch"),
        ]
        for update, kwargs, code in cases:
            directory, path = self.modified_scene(update)
            try:
                with self.assertRaises(SorterError) as caught:
                    load_scene(path, self.config, **kwargs)
                self.assertEqual(caught.exception.code, code)
            finally:
                directory.cleanup()

    def test_multiple_candidates_use_table_origin_distance_or_tie_blocks(self):
        command = SortCommand("sort", "medicine_bottle", BottleSize.LARGE, BasketColor.RED)
        def add_candidate(raw):
            extra = dict(raw["bottles"][0])
            extra.update(observation_id="frame-001-A2", table_position_mm=[300, 300, 45])
            raw["bottles"].append(extra)
        directory, path = self.modified_scene(add_candidate)
        try:
            self.assertEqual(select_target(load_scene(path, self.config, recorded=True), command).observation_id,
                             "frame-001-A")
        finally:
            directory.cleanup()

        def tie(raw):
            extra = dict(raw["bottles"][0])
            extra.update(observation_id="frame-001-A2", table_position_mm=[160.1, 260, 45])
            raw["bottles"].append(extra)
        directory, path = self.modified_scene(tie)
        try:
            with self.assertRaises(SorterError) as caught:
                select_target(load_scene(path, self.config, recorded=True), command)
            self.assertEqual(caught.exception.code, "multiple_targets_tied")
        finally:
            directory.cleanup()

    def test_mock_end_to_end_does_not_claim_physical_success(self):
        adapter = MockRobotAdapter()
        app = SorterApplication(self.config, RobotController(adapter))
        result = app.run_recorded_mock("큰 약통 하나를 빨간 바구니에 넣어", self.scene_path)
        self.assertEqual(result.status, "MOCK_COMPLETED")
        self.assertEqual(result.completed_stages, STAGES)
        self.assertEqual(result.result_verification, "MOCK_ONLY")
        self.assertFalse(result.physical_motion)
        self.assertTrue(adapter.closed)

    def test_failure_stops_and_closes_without_retry(self):
        adapter = MockRobotAdapter(fail_stage="gripper_close")
        app = SorterApplication(self.config, RobotController(adapter))
        with self.assertRaises(SorterError) as caught:
            app.run_recorded_mock("큰 약통을 빨간 바구니에 넣어", self.scene_path)
        self.assertEqual(caught.exception.code, "mock_stage_failed")
        self.assertEqual(adapter.executed.count("approach"), 1)
        self.assertTrue(adapter.stopped)
        self.assertTrue(adapter.closed)

    def test_busy_task_is_rejected(self):
        app = SorterApplication(self.config, RobotController(MockRobotAdapter()))
        app._lock.acquire()
        try:
            with self.assertRaises(SorterError) as caught:
                app.run_recorded_mock("큰 약통을 빨간 바구니에 넣어", self.scene_path)
            self.assertEqual(caught.exception.code, "task_already_running")
        finally:
            app._lock.release()
