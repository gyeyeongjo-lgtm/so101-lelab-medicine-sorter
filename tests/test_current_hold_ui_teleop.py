import sys
import threading
import time
import types
import unittest
from unittest.mock import patch

from scripts import current_hold_ui_teleop as ui


class Request:
    leader_port = "/dev/ttyACM0"
    follower_port = "/dev/ttyACM1"
    leader_config = "so-101.json"
    follower_config = "so-101.json"


class CurrentHoldUITeleopTests(unittest.TestCase):
    def setUp(self):
        self.record = types.SimpleNamespace(recording_active=False)
        self.rollout = types.SimpleNamespace(inference_active=False)
        sys.modules["scripts.record"] = self.record
        sys.modules["scripts.rollout"] = self.rollout
        with ui._state_lock:
            ui._phase = "INACTIVE"
            ui._worker = None
            ui._stop_event = None
            ui._startup_event = None
            ui._session_token = None
            ui._last_error = None
            ui._last_result = None
            ui._joint_cache = None
            ui._inactive_callback = None
        self.addCleanup(sys.modules.pop, "scripts.record", None)
        self.addCleanup(sys.modules.pop, "scripts.rollout", None)

    @staticmethod
    def fake_armed_worker(token, _request):
        with ui._state_lock:
            ui._phase = "ARMED"
            ui._startup_event.set()
        ui._stop_event.wait(timeout=2)
        callback = None
        with ui._state_lock:
            if token is ui._session_token:
                ui._phase = "INACTIVE"
                ui._worker = None
                ui._session_token = None
                callback = ui._inactive_callback
                ui._inactive_callback = None
        if callback:
            callback()

    def test_wrong_port_or_config_rejected_before_worker(self):
        for field, value in (("leader_port", "/dev/ttyUSB0"),
                             ("follower_config", "other.json")):
            request = Request()
            setattr(request, field, value)
            with patch.object(ui, "_run_session") as run:
                result = ui.start(request)
            self.assertFalse(result["success"])
            run.assert_not_called()

    def test_start_armed_duplicate_rejected_and_stop_cleans(self):
        inactive = []
        with patch.object(ui, "_run_session", side_effect=self.fake_armed_worker):
            result = ui.start(Request(), on_inactive=lambda: inactive.append(True))
            self.assertTrue(result["success"])
            self.assertTrue(result["recorder"] is False)
            self.assertEqual(ui.status()["phase"], "ARMED")
            duplicate = ui.start(Request())
            self.assertFalse(duplicate["success"])
            stopped = ui.stop()
        self.assertTrue(stopped["success"])
        self.assertEqual(ui.status()["phase"], "INACTIVE")
        self.assertEqual(inactive, [True])

    def test_recording_or_inference_blocks_start(self):
        for owner, field in ((self.record, "recording_active"),
                             (self.rollout, "inference_active")):
            setattr(owner, field, True)
            with patch.object(ui, "_run_session") as run:
                result = ui.start(Request())
            self.assertFalse(result["success"])
            run.assert_not_called()
            setattr(owner, field, False)

    def test_stop_during_startup_never_reports_armed(self):
        def waiting_worker(token, _request):
            ui._stop_event.wait(timeout=2)
            callback = None
            with ui._state_lock:
                if token is ui._session_token:
                    ui._startup_event.set()
                    ui._phase = "INACTIVE"
                    ui._worker = None
                    ui._session_token = None
                    callback = ui._inactive_callback
                    ui._inactive_callback = None
            if callback:
                callback()

        results = []
        with patch.object(ui, "_run_session", side_effect=waiting_worker):
            starter = threading.Thread(target=lambda: results.append(ui.start(Request())))
            starter.start()
            deadline = time.monotonic() + 1
            while ui.status()["phase"] != "STARTING" and time.monotonic() < deadline:
                time.sleep(0.001)
            stopped = ui.stop()
            starter.join(timeout=2)
        self.assertTrue(stopped["success"])
        self.assertFalse(results[0]["success"])

    def test_joint_positions_are_cache_only(self):
        self.assertFalse(ui.joint_positions()["success"])
        values = {"present_degree_or_percent": {
            "shoulder_pan": 10.0, "shoulder_lift": 20.0, "elbow_flex": 30.0,
            "wrist_flex": 40.0, "wrist_roll": 50.0, "gripper": 5.0}}
        ui._cache_diagnostics(values)
        result = ui.joint_positions()
        self.assertTrue(result["success"])
        self.assertAlmostEqual(result["joint_positions"]["Rotation"],
                               10.0 * 3.141592653589793 / 180.0)


if __name__ == "__main__":
    unittest.main()
