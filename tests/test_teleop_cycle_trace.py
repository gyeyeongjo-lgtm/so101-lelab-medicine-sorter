import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.teleop_cycle_trace import CycleTrace, MOTORS, PHASES, append_event


def action(value=0.0):
    return {f"{name}.pos": value for name in MOTORS}


def feedback(value=0.0):
    return {name: value for name in MOTORS}


class CycleTraceTests(unittest.TestCase):
    def test_one_shot_ticket_allows_only_the_new_session(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ticket = root / "one-session.ticket"
            ticket.touch()
            with patch.dict("os.environ", {"LELAB_TELEOP_TRACE_ONCE_TICKET": str(ticket)}):
                trace = CycleTrace(root / "first")
                self.assertFalse(ticket.exists())
                trace.finish(stop_reason="teleoperation_inactive")
                with self.assertRaises(FileNotFoundError):
                    CycleTrace(root / "second")
            self.assertFalse((root / "second").exists())

    def test_records_all_six_leader_command_and_fresh_feedback_once_per_cycle(self):
        calls = []

        def leader():
            calls.append("leader")
            return action(1.0)

        def send(values):
            calls.append("send")
            self.assertEqual(values, action(1.0))
            return action(1.5)

        def read():
            calls.append("feedback")
            return feedback(1.25)

        with tempfile.TemporaryDirectory() as temporary:
            session = Path(temporary) / "run"
            trace = CycleTrace(session)
            first = trace.capture_cycle(leader, send, read)
            for phase in PHASES:
                append_event(session, phase)
            second = trace.capture_cycle(leader, send, read)
            manifest = trace.finish(stop_reason="teleoperation_inactive")
            rows = [json.loads(line) for line in (session / "cycles.jsonl").read_text().splitlines()]
            self.assertEqual(calls, ["leader", "send", "feedback"] * 2)
            self.assertEqual(first["follower_command"], {name: 1.5 for name in MOTORS})
            self.assertEqual(first["follower_feedback"], {name: 1.25 for name in MOTORS})
            self.assertEqual(rows[1]["seq"], second["seq"])
            self.assertEqual(manifest["cycle_count"], 2)
            self.assertTrue(manifest["data_complete"])
            self.assertFalse(manifest["physical_task_success_verified"])
            self.assertFalse(manifest["automatic_replay_authorized"])
            with self.assertRaisesRegex(RuntimeError, "finalized"):
                append_event(session, "approach")

    def test_rejects_incomplete_leader_before_sending(self):
        sent = []
        with tempfile.TemporaryDirectory() as temporary:
            session = Path(temporary) / "run"
            trace = CycleTrace(session)
            with self.assertRaisesRegex(ValueError, "leader"):
                trace.capture_cycle(lambda: {"elbow_flex.pos": 1.0},
                                    lambda values: sent.append(values), lambda: feedback())
            manifest = trace.finish(stop_reason="worker_error")
            self.assertFalse(sent)
            self.assertEqual(manifest["error_count"], 1)
            self.assertFalse(manifest["data_complete"])
            self.assertEqual(json.loads((session / "errors.jsonl").read_text())["stage"], "leader_read")

    def test_feedback_failure_is_not_a_complete_cycle(self):
        with tempfile.TemporaryDirectory() as temporary:
            session = Path(temporary) / "run"
            trace = CycleTrace(session)
            with self.assertRaisesRegex(ValueError, "follower feedback"):
                trace.capture_cycle(lambda: action(), lambda _: action(), lambda: {"gripper": 0})
            manifest = trace.finish(stop_reason="worker_error")
            self.assertEqual(manifest["cycle_count"], 0)
            self.assertEqual(manifest["error_count"], 1)
            self.assertFalse(manifest["data_complete"])

    def test_phase_markers_do_not_claim_completion_when_out_of_order(self):
        with tempfile.TemporaryDirectory() as temporary:
            session = Path(temporary) / "run"
            trace = CycleTrace(session)
            trace.capture_cycle(lambda: action(), lambda _: action(), lambda: feedback())
            for phase in reversed(PHASES):
                append_event(session, phase)
            trace.capture_cycle(lambda: action(), lambda _: action(), lambda: feedback())
            manifest = trace.finish(stop_reason="teleoperation_inactive")
            self.assertFalse(manifest["phase_markers_in_order"])
            self.assertFalse(manifest["data_complete"])


if __name__ == "__main__":
    unittest.main()
