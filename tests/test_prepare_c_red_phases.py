import json
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts.prepare_c_red_phases import (
    FakeClock, FakeFollower, PHASE_END_SEQ, audit_phase, dry_run_cycle, load_phases,
)
from scripts.replay_c_red_approach import run_timed_segment


CANDIDATE = (Path(__file__).resolve().parents[1] / ".local/teleop-cycle-traces/"
             "2026-10-09-c-red/analysis/trajectory_candidate.json")


@unittest.skipUnless(CANDIDATE.exists(), "private recorded candidate unavailable")
class CRedPhasePreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.phases = load_phases(CANDIDATE)

    def test_phase_boundaries_and_original_follower_commands(self):
        self.assertEqual([points[-1]["seq"] for points in self.phases.values()],
                         list(PHASE_END_SEQ.values()))
        self.assertEqual(sum(len(points) - 1 for points in self.phases.values()), 1511)
        for previous, following in zip(list(self.phases.values()),
                                       list(self.phases.values())[1:]):
            self.assertEqual(previous[-1]["goal"], following[0]["goal"])

    def test_all_five_phases_pass_numeric_and_fake_bus_checks(self):
        result = dry_run_cycle(CANDIDATE, command="C를 빨강 바구니에 옮겨")
        self.assertEqual(result["total_fake_targets"], 1511)
        self.assertFalse(result["live_cycle_available"])
        self.assertEqual([r["targets"] for r in result["phases"]],
                         [640, 459, 141, 199, 72])
        self.assertTrue(all(r["minimum_arm_urdf_margin_deg"] >= 5.0
                            for r in result["phases"]))
        self.assertGreater(result["phases"][1]["gripper_start_percent"],
                           result["phases"][1]["gripper_end_percent"])

    def test_unprepared_command_is_blocked(self):
        with self.assertRaisesRegex(ValueError, "only_C_to_red"):
            dry_run_cycle(CANDIDATE, command="A를 빨강 바구니에 옮겨")

    def test_next_phase_not_run_after_first_failure(self):
        with patch("scripts.prepare_c_red_phases.audit_phase",
                   side_effect=ValueError("fake guard")) as audit:
            with self.assertRaisesRegex(ValueError, "fake guard"):
                dry_run_cycle(CANDIDATE)
            self.assertEqual(audit.call_count, 1)

    def test_urdf_violation_blocks_without_clipping(self):
        point = [dict(p) for p in self.phases["grasp"]]
        point[1] = {**point[1], "goal": {**point[1]["goal"], "elbow_flex": 90.1}}
        with self.assertRaisesRegex(ValueError, "numeric_guard_failed"):
            audit_phase("grasp", point)

    def test_full_approach_with_structured_logging_has_no_fake_schedule_regression(self):
        clock = FakeClock()
        fake = FakeFollower(clock)
        rows = []
        samples = []
        sample_timing = []
        count = run_timed_segment(
            self.phases["approach"], fake, time_scale=4.0,
            clock=clock, sleep=clock.sleep,
            on_feedback=lambda point, command, observed: samples.append(json.dumps({
                "seq": point["seq"], "feedback": observed.positions,
                "command_feedback_abs_error": {
                    name: abs(command[name] - observed.positions[name]) for name in command
                }, "guard_state": "PENDING_CHECK"})),
            on_timing=lambda timing: rows.append(json.dumps(timing)),
            on_sample_timing=lambda timing: sample_timing.append(json.dumps(timing)),
        )
        self.assertEqual((count, len(rows), len(samples), len(sample_timing)),
                         (640, 640, 640, 640))
        self.assertAlmostEqual(clock.now - 100.0, 324.679729772, places=5)
        first = json.loads(rows[0])
        for field in ("target_index", "seq", "nominal_interval_s",
                      "scheduled_send_monotonic", "send_call_monotonic",
                      "send_return_monotonic", "feedback_read_started_monotonic",
                      "first_feedback_read_ended_monotonic", "settle_elapsed_s",
                      "settle_start_monotonic", "settle_end_monotonic",
                      "command_feedback_abs_error", "minimum_arm_urdf_margin_deg",
                      "guard_state"):
            self.assertIn(field, first)


if __name__ == "__main__":
    unittest.main()
