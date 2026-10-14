import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.teleop_cycle_trace import (
    CycleTrace, MOTORS, PHASES, append_event, read_same_owner_diagnostics,
    verify_relative_start_stillness,
)


def action(value=0.0):
    return {f"{name}.pos": value for name in MOTORS}


def feedback(value=0.0):
    return {name: value for name in MOTORS}


def diagnostics():
    return {
        "goal_raw": {name: 2000 for name in MOTORS},
        "present_raw": {name: 1999 for name in MOTORS},
        "goal_degree_or_percent": {name: 1.0 for name in MOTORS},
        "present_degree_or_percent": {name: 0.9 for name in MOTORS},
        "moving": {name: 0 for name in MOTORS},
        "present_load_diagnostic": {name: -24 for name in MOTORS},
        "temperature_c": {name: 40 for name in MOTORS},
        "fk_grasp_tcp_mm": [-59.0, -287.0, 84.0],
    }


class CycleTraceTests(unittest.TestCase):
    def test_startup_stillness_reads_without_sending(self):
        clock = [0.0]
        def sleep(seconds):
            clock[0] += seconds
        result = verify_relative_start_stillness(
            read_leader=lambda: action(0.0),
            read_diagnostics=diagnostics,
            leader_origin=action(0.0),
            monotonic=lambda: clock[0], sleep=sleep,
        )
        self.assertGreaterEqual(result["samples"], 30)
        self.assertGreaterEqual(clock[0], 3.0)

    def test_startup_stillness_rejects_leader_motion_without_sending(self):
        reads = [0]
        def leader():
            reads[0] += 1
            return action(0.0 if reads[0] == 1 else 0.1)
        with self.assertRaisesRegex(RuntimeError, "leader moved"):
            verify_relative_start_stillness(
                read_leader=leader,
                read_diagnostics=diagnostics,
                leader_origin=action(0.0),
                monotonic=lambda: 0.0, sleep=lambda _: None,
            )

    def test_relative_observation_does_not_send_and_marks_hold(self):
        with tempfile.TemporaryDirectory() as temporary:
            trace = CycleTrace(Path(temporary) / "run", capture_kind="empirical_relative_teaching")
            row = trace.observe_relative_cycle(
                leader_action=action(1.0), relative_target=action(0.5),
                command_sent=False, read_feedback=lambda: feedback(0.0),
                read_diagnostics=lambda _: diagnostics(),
            )
            self.assertFalse(row["command_sent"])
            self.assertNotIn("follower_command", row)
            manifest = trace.finish(stop_reason="teleoperation_inactive")
            self.assertTrue(manifest["data_complete"])
            self.assertFalse(manifest["physical_task_success_verified"])
            self.assertFalse(manifest["automatic_replay_authorized"])

    def test_same_owner_reader_uses_only_read_calls(self):
        class FakeBus:
            def __init__(self):
                self.motors = {name: type("Motor", (), {"id": index})()
                               for index, name in enumerate(MOTORS, 1)}
                self.calls = []

            def sync_read(self, register, **kwargs):
                self.calls.append(("sync_read", register))
                return {name: 0 if register == "Moving" else 1999 for name in MOTORS}

            def read(self, register, name, **kwargs):
                self.calls.append(("read", register, name))
                return 40

            def _normalize(self, values):
                return {key: float(value) / 100 for key, value in values.items()}

        bus = FakeBus()
        robot = type("Robot", (), {"bus": bus})()
        values = read_same_owner_diagnostics(robot, lambda q: [q["elbow_flex"], 0, 84])
        self.assertEqual(values["fk_grasp_tcp_mm"], [19.99, 0.0, 84.0])
        self.assertEqual(len(bus.calls), 10)
        self.assertTrue(all(call[0] in ("sync_read", "read") for call in bus.calls))

    def test_empirical_teaching_diagnostics_share_cycle_and_preserve_signed_load(self):
        with tempfile.TemporaryDirectory() as temporary:
            trace = CycleTrace(Path(temporary) / "run")
            row = trace.capture_cycle(
                lambda: action(), lambda _: action(), lambda: feedback(),
                lambda _: diagnostics(),
            )
            self.assertEqual(row["follower_diagnostics"]["present_load_diagnostic"]["elbow_flex"], -24)
            self.assertEqual(row["follower_diagnostics"]["fk_grasp_tcp_mm"], [-59.0, -287.0, 84.0])
            trace.finish(stop_reason="teleoperation_inactive")

    def test_diagnostics_failure_excludes_incomplete_cycle(self):
        with tempfile.TemporaryDirectory() as temporary:
            trace = CycleTrace(Path(temporary) / "run")
            bad = diagnostics()
            bad["temperature_c"]["elbow_flex"] = 56
            with self.assertRaisesRegex(ValueError, "temperature safety gate"):
                trace.capture_cycle(
                    lambda: action(), lambda _: action(), lambda: feedback(),
                    lambda _: bad,
                )
            manifest = trace.finish(stop_reason="worker_error")
            self.assertEqual(manifest["cycle_count"], 0)
            self.assertEqual(manifest["error_count"], 1)
            error = json.loads((trace.session_dir / "errors.jsonl").read_text())
            self.assertEqual(error["stage"], "follower_diagnostics")

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
