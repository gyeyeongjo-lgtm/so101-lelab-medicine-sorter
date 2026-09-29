import unittest
from pathlib import Path


SERVER_SOURCE = (Path(__file__).resolve().parents[1] / "scripts" / "camera_preview_server.py").read_text(
    encoding="utf-8"
)


class CameraPreviewJointWebSocketTests(unittest.TestCase):
    def test_joint_monitor_uses_broadcast_websocket_only(self):
        self.assertIn("/ws/joint-data", SERVER_SOURCE)
        self.assertIn("use_for_robot_world_fit:false", SERVER_SOURCE)
        self.assertNotIn("/joint-positions", SERVER_SOURCE)

    def test_page_has_no_robot_control_endpoint(self):
        self.assertNotIn("/move-arm", SERVER_SOURCE)
        self.assertNotIn("/stop-teleoperation", SERVER_SOURCE)

    def test_independent_evaluation_queue_is_separate(self):
        self.assertIn("/api/eval/capture", SERVER_SOURCE)
        self.assertIn("evaluation-web-v1", SERVER_SOURCE)
        self.assertIn("training-candidates-audit-v1", SERVER_SOURCE)


if __name__ == "__main__":
    unittest.main()
