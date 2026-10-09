from pathlib import Path
import unittest
from unittest.mock import patch

from scripts.replay_c_red_phase import run_one_phase


CANDIDATE = (Path(__file__).resolve().parents[1] / ".local/teleop-cycle-traces/"
             "2026-10-09-c-red/analysis/trajectory_candidate.json")


class FakeTransport:
    def __init__(self):
        self.stopped = 0
        self.disconnected = 0
        self.released = 0
        self.robot = type("Robot", (), {})()
        self.robot.bus = type("Bus", (), {"disconnect": self.disconnect})()
        self.lease = type("Lease", (), {"release": self.release})()

    def stop_commands(self):
        self.stopped += 1

    def disconnect(self, *, disable_torque):
        if disable_torque is not False:
            raise AssertionError("torque change attempted")
        self.disconnected += 1

    def release(self):
        self.released += 1


@unittest.skipUnless(CANDIDATE.exists(), "private recorded candidate unavailable")
class RecordedPhaseLiveGateTests(unittest.TestCase):
    def test_default_is_dry_run_without_transport(self):
        self.assertEqual(run_one_phase("grasp", CANDIDATE), 0)

    def test_wrong_scope_or_phrase_never_opens_transport(self):
        with self.assertRaisesRegex(ValueError, "scope_mismatch"):
            run_one_phase("grasp", CANDIDATE, live=True, confirm_scope="place")
        called = []
        result = run_one_phase("grasp", CANDIDATE, live=True,
                               confirm_scope="grasp", input_fn=lambda prompt: "NO",
                               transport_factory=lambda: called.append(True))
        self.assertEqual(result, 2)
        self.assertEqual(called, [])

    def test_single_grasp_success_needs_stillness_and_human_result(self):
        fake = FakeTransport()
        prompts = iter(["RUN GRASP", "STOPPED", "C HELD"])
        with patch("scripts.replay_c_red_phase.run_timed_segment", return_value=459) as run, \
             patch("scripts.replay_c_red_phase.read_stillness", return_value=True):
            result = run_one_phase("grasp", CANDIDATE, live=True,
                                   confirm_scope="grasp", input_fn=lambda prompt: next(prompts),
                                   transport_factory=lambda: fake)
        self.assertEqual(result, 0)
        self.assertEqual(run.call_count, 1)
        self.assertEqual((fake.stopped, fake.disconnected, fake.released), (1, 1, 1))

    def test_abort_never_runs_another_phase_and_closes_without_torque_change(self):
        fake = FakeTransport()
        prompts = iter(["RUN TRANSPORT", "STOPPED"])
        with patch("scripts.replay_c_red_phase.run_timed_segment",
                   side_effect=RuntimeError("tracking_guard_exceeded")) as run, \
             patch("scripts.replay_c_red_phase.read_stillness", return_value=True):
            result = run_one_phase("transport", CANDIDATE, live=True,
                                   confirm_scope="transport", input_fn=lambda prompt: next(prompts),
                                   transport_factory=lambda: fake)
        self.assertEqual(result, 1)
        self.assertEqual(run.call_count, 1)
        self.assertEqual((fake.stopped, fake.disconnected, fake.released), (1, 1, 1))


if __name__ == "__main__":
    unittest.main()
