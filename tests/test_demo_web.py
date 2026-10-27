import threading
import time
import unittest
from pathlib import Path

from medicine_sorter.cli import build_parser
from medicine_sorter.config import load_config
from medicine_sorter.errors import SorterError
from medicine_sorter.fixed_demo import load_demo_settings
from medicine_sorter.web import DemoWebController, INDEX_HTML, parse_web_rules

ROOT = Path(__file__).resolve().parents[1]


class DemoWebTests(unittest.TestCase):
    def setUp(self):
        self.config = load_config(ROOT / "configs/system.example.json")
        self.settings = load_demo_settings(self.config)

    def test_cli_has_auto_and_web_8030(self):
        auto = build_parser().parse_args(["run", "--auto", "--rule", "A=blue"])
        warm = build_parser().parse_args(
            ["run", "--step", "--warm-start-once", "--rule", "A=green"])
        web = build_parser().parse_args(["web", "--port", "8030"])
        self.assertTrue(auto.auto)
        self.assertTrue(warm.step)
        self.assertTrue(warm.warm_start_once)
        self.assertEqual(web.mode, "web")
        self.assertEqual(web.port, 8030)

    def test_cli_has_offline_compare_and_single_segment_motion_test(self):
        compare = build_parser().parse_args([
            "motion-compare", "--from-pose", "home", "--to-pose", "finish"])
        motion = build_parser().parse_args([
            "motion-test", "--from-pose", "home", "--to-pose", "finish",
            "--profile", "smooth", "--log", ".local/test.jsonl", "--step"])
        current = build_parser().parse_args([
            "motion-test", "--from-current", "--to-pose", "finish",
            "--profile", "original", "--log", ".local/current.jsonl", "--step"])
        self.assertEqual(compare.mode, "motion-compare")
        self.assertEqual(compare.from_pose, "home")
        self.assertIsNone(compare.actual_log)
        self.assertEqual(motion.mode, "motion-test")
        self.assertEqual(motion.profile, "smooth")
        self.assertEqual(motion.stable_hold_gap_raw, 10)
        self.assertTrue(motion.step)
        self.assertTrue(current.from_current)
        self.assertIsNone(current.from_pose)
        self.assertEqual(current.profile, "original")

    def test_rule_parser_allows_three_colors_and_skip(self):
        self.assertEqual(parse_web_rules(
            {"A": "blue", "B": "red", "C": "skip"}),
            {"A": "blue", "B": "red"})
        with self.assertRaisesRegex(SorterError, "web_rule_destination_invalid"):
            parse_web_rules({"A": "yellow"})

    def test_html_contains_controls_status_and_camera(self):
        for required in ("계획 확인", "정지 — 현재 위치 HOLD", "/api/run",
                         "/api/stop", "stage_index", "temperatures_c",
                         "8020/stream.mjpg", "전원을 뽑고 식히세요"):
            self.assertIn(required, INDEX_HTML)

    def test_plan_is_camera_only_contract_and_start_is_auto(self):
        calls = []

        def fake_run(_config, _settings, **kwargs):
            calls.append(kwargs)
            if kwargs["dry_run"]:
                return {"status": "FIXED_DEMO_PLAN", "routes": []}
            kwargs["progress_callback"]({"status": "RUNNING", "stage": "home",
                                         "stage_index": 1, "stage_count": 11,
                                         "temperatures_c": {"gripper": 32}})
            return {"status": "FIXED_DEMO_COMPLETE",
                    "final_temperatures_c": {"gripper": 33}}

        controller = DemoWebController(self.config, self.settings, run_function=fake_run)
        plan = controller.plan({"A": "blue", "B": "skip", "C": "green"})
        self.assertEqual(plan["status"], "FIXED_DEMO_PLAN")
        self.assertTrue(calls[0]["dry_run"])
        controller.start({"A": "blue", "B": "red", "C": "green"})
        self.assertTrue(controller.wait(1.0))
        state = controller.snapshot()
        self.assertEqual(state["status"], "COMPLETE")
        self.assertEqual(state["temperatures_c"], {"gripper": 33})
        self.assertEqual(state["cooldown_notice"], "전원을 뽑고 식히세요")
        self.assertTrue(calls[1]["auto"])
        self.assertFalse(calls[1]["install_signal_handlers"])

    def test_stop_sets_event_and_worker_reports_stopped(self):
        entered = threading.Event()

        def blocking_run(_config, _settings, **kwargs):
            entered.set()
            self.assertTrue(kwargs["auto"])
            while not kwargs["stop_requested"]():
                time.sleep(0.005)
            raise SorterError("demo_stopped_current_position_held", True,
                              "completion", "상태 확인")

        controller = DemoWebController(self.config, self.settings, run_function=blocking_run)
        controller.start({"A": "blue", "B": "red", "C": "green"})
        self.assertTrue(entered.wait(1.0))
        self.assertEqual(controller.stop()["status"], "STOP_REQUESTED")
        self.assertTrue(controller.wait(1.0))
        state = controller.snapshot()
        self.assertEqual(state["status"], "STOPPED")
        self.assertEqual(state["last_error"]["error"],
                         "demo_stopped_current_position_held")
        self.assertFalse(state["running"])

if __name__ == "__main__":
    unittest.main()
