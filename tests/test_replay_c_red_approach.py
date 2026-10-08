import unittest

from scripts.replay_c_red_approach import (
    TrialAbort, check_feedback, run_timed_segment,
)
from scripts.staged_cycle_execution import Feedback, JOINT_UNITS


class FakeClock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class FakeTransport:
    def __init__(self, clock):
        self.clock = clock
        self.sent = []
        self.goal = None
        self.start_checked = False

    def verify_start_pose(self, goal, tolerances):
        self.start_checked = True
        return Feedback(dict(goal), self.clock())

    def send_goal(self, goal):
        self.goal = dict(goal)
        self.sent.append(self.goal)
        self.clock.now += 0.001
        return self.goal

    def read_feedback(self):
        self.clock.now += 0.001
        return Feedback(dict(self.goal), self.clock.now)


def point(seq, elapsed, pan):
    goal = {
        "shoulder_pan": pan, "shoulder_lift": -22.0, "elbow_flex": 32.0,
        "wrist_flex": 5.0, "wrist_roll": -20.0, "gripper": 3.5,
    }
    return {"seq": seq, "elapsed_from_safe_start_s": elapsed,
            "goal": goal, "observed_feedback": dict(goal)}


# Recorded follower-command elbow/lift/wrist values for targets 20–35.
# Other axes are fixed in this fake-bus test; no recorded trajectory is edited.
TARGETS_20_35 = (
    (31642, -22.329670330, 36.131868132, 5.538461538),
    (31659, -22.505494505, 35.956043956, 5.450549451),
    (31668, -23.472527473, 35.868131868, 5.362637363),
    (31677, -24.000000000, 35.956043956, 4.395604396),
    (31686, -24.175824176, 36.395604396, 2.549450549),
    (31695, -24.263736264, 36.483516484, 0.967032967),
    (31704, -24.263736264, 36.835164835, 0.000000000),
    (31723, -24.791208791, 37.538461538, -0.351648352),
    (31733, -26.373626374, 37.890109890, -0.263736264),
    (31743, -27.868131868, 38.769230769, -0.263736264),
    (31752, -29.362637363, 39.560439560, -0.263736264),
    (31756, -30.329670330, 40.000000000, -0.263736264),
    (31761, -31.472527473, 40.703296703, -0.263736264),
    (31766, -32.615384615, 41.582417582, -0.263736264),
    (31772, -33.934065934, 42.637362637, -0.263736264),
    (31777, -34.901098901, 43.516483516, -0.263736264),
)

# Existing 4x trial feedback through target 28, with the two target-28 reads
# retained so the fake bus has the same joint-motion context as target 29.
FEEDBACK_20_28 = (
    ((-20.000000, 36.967033, 5.582418),),
    ((-20.000000, 36.967033, 5.582418),),
    ((-20.000000, 36.967033, 5.582418),),
    ((-20.263736, 36.967033, 5.582418),),
    ((-20.791209, 36.967033, 5.406593),),
    ((-20.967033, 37.054945, 3.472527),),
    ((-21.054945, 37.054945, 1.978022),),
    ((-21.142857, 37.582418, 1.274725),),
    ((-21.670330, 38.197802, 0.835165),
     (-22.989011, 38.549451, 0.835165)),
)


def recorded_interval_points():
    points = [point(28363, 0.0, 11.0)]
    for index, (seq, lift, elbow, flex) in enumerate(TARGETS_20_35, 1):
        target = point(seq, index * 0.1, 11.0)
        target["goal"].update(shoulder_lift=lift, elbow_flex=elbow, wrist_flex=flex)
        target["observed_feedback"] = dict(target["goal"])
        points.append(target)
    return points


class IntervalTransport(FakeTransport):
    def __init__(self, clock, target29_samples):
        super().__init__(clock)
        self.target29_samples = list(target29_samples)
        self.reads_this_target = 0

    def send_goal(self, goal):
        self.reads_this_target = 0
        return super().send_goal(goal)

    def read_feedback(self):
        sample = super().read_feedback()
        self.reads_this_target += 1
        if 1 <= len(self.sent) <= 9:
            samples = FEEDBACK_20_28[len(self.sent) - 1]
            lift, elbow, flex = samples[min(self.reads_this_target - 1, len(samples) - 1)]
            return Feedback({**sample.positions, "shoulder_lift": lift,
                             "elbow_flex": elbow, "wrist_flex": flex},
                            sample.received_monotonic)
        if len(self.sent) == 10:  # target 29 is the tenth goal in 20–35
            changes = self.target29_samples.pop(0) if self.target29_samples else self._last_changes
            self._last_changes = changes
            return Feedback({**sample.positions, **changes}, sample.received_monotonic)
        return sample


class ApproachReplayTests(unittest.TestCase):
    def test_sends_only_after_scaled_timestamps_and_reads_fresh_feedback(self):
        clock = FakeClock()
        fake = FakeTransport(clock)
        points = [point(28363, 0.0, 11.0), point(30000, 1.0, 12.0),
                  point(45133, 2.0, 13.0)]
        count = run_timed_segment(points, fake, time_scale=2.0,
                                  clock=clock, sleep=clock.sleep)
        self.assertTrue(fake.start_checked)
        self.assertEqual(count, 2)
        self.assertEqual([goal["shoulder_pan"] for goal in fake.sent], [12.0, 13.0])
        self.assertGreaterEqual(clock.now, 104.0)

    def test_bad_tracking_or_urdf_margin_aborts_before_next_goal(self):
        goal = point(30000, 1.0, 12.0)["goal"]
        with self.assertRaisesRegex(TrialAbort, "tracking_guard_exceeded"):
            check_feedback({**goal, "shoulder_pan": 18.0}, goal, goal)
        with self.assertRaisesRegex(TrialAbort, "urdf_margin_below_5deg"):
            check_feedback({**goal, "elbow_flex": 89.0}, goal, goal)
        # Demonstration feedback is a comparison record, not another target.
        check_feedback(goal, {**goal, "gripper": goal["gripper"] + 30.0}, goal)

    def test_waits_for_bounded_tracking_settle_without_sending_next_goal(self):
        clock = FakeClock()

        class LaggingTransport(FakeTransport):
            def __init__(self, clock):
                super().__init__(clock)
                self.reads_for_goal = 0

            def send_goal(self, goal):
                self.reads_for_goal = 0
                return super().send_goal(goal)

            def read_feedback(self):
                sample = super().read_feedback()
                self.reads_for_goal += 1
                lag = 4.0 if self.reads_for_goal == 1 else 2.0
                return Feedback({**sample.positions,
                                 "shoulder_pan": sample.positions["shoulder_pan"] + lag},
                                sample.received_monotonic)

        fake = LaggingTransport(clock)
        samples = []
        timing = []
        points = [point(28363, 0.0, 11.0), point(30000, 1.0, 12.0),
                  point(45133, 2.0, 13.0)]
        count = run_timed_segment(points, fake, time_scale=2.0,
                                  clock=clock, sleep=clock.sleep,
                                  on_feedback=lambda p, sent, observed:
                                      samples.append((p["seq"], observed.positions["shoulder_pan"])),
                                  on_timing=timing.append)
        self.assertEqual(count, 2)
        self.assertEqual([seq for seq, _ in samples], [30000, 30000, 45133, 45133])
        self.assertEqual([row["settle_reads"] for row in timing], [1, 1])
        self.assertGreaterEqual(timing[1]["scheduled_send_monotonic"],
                                timing[0]["final_feedback_monotonic"] + 2.0)

    def test_dense_recorded_95_105_gaps_rebase_after_feedback_without_catchup(self):
        # Actual candidate 4x gaps in the 95–105 region are as short as 16 ms.
        # A measured send/read cycle was about 87 ms, without any settle reads.
        gaps_4x = (0.064471, 0.016821, 0.063950, 0.031631, 0.047779,
                   0.032198, 0.047583, 0.032066, 0.047923, 0.016098)
        clock = FakeClock()

        class SerialLatencyTransport(FakeTransport):
            def __init__(self, clock):
                super().__init__(clock)
                self.send_times = []
                self.feedback_times = []

            def send_goal(self, goal):
                self.send_times.append(self.clock())
                self.goal = dict(goal)
                self.sent.append(self.goal)
                self.clock.now += 0.040
                return self.goal

            def read_feedback(self):
                self.clock.now += 0.047
                self.feedback_times.append(self.clock())
                return Feedback(dict(self.goal), self.clock())

        fake = SerialLatencyTransport(clock)
        points = [point(28363, 0.0, 11.0), point(34157, 1.0, 11.0)]
        elapsed = 1.0
        for index, gap in enumerate(gaps_4x, 1):
            elapsed += gap / 4.0
            points.append(point(34157 + index, elapsed, 11.0))
        timing = []
        count = run_timed_segment(points, fake, time_scale=4.0,
                                  clock=clock, sleep=clock.sleep,
                                  on_timing=timing.append)
        self.assertEqual(count, 11)
        self.assertEqual(len(timing), 11)
        self.assertEqual(timing[0]["target_index"], 1)
        self.assertEqual(timing[-1]["target_index"], 11)
        self.assertTrue(all(row["send_return_monotonic"] >= row["send_call_monotonic"]
                            and row["first_feedback_read_ended_monotonic"] >=
                            row["feedback_read_started_monotonic"]
                            and row["guard_state"] == "PASS" for row in timing))
        self.assertTrue(all(row["minimum_arm_urdf_margin_deg"] >= 5
                            and max(row["command_feedback_abs_error"].values()) == 0
                            for row in timing))
        self.assertTrue(all(row["settle_reads"] == 0 for row in timing))
        self.assertGreater(timing[-1]["cumulative_delay_s"], 0.9)
        for index, gap in enumerate(gaps_4x, 1):
            self.assertGreaterEqual(fake.send_times[index] + 1e-9,
                                    fake.feedback_times[index - 1] + gap)

    def test_scheduler_overrun_guard_still_blocks_a_real_clock_stall(self):
        clock = FakeClock()
        fake = FakeTransport(clock)
        points = [point(28363, 0.0, 11.0), point(30000, 0.02, 11.0)]
        with self.assertRaisesRegex(TrialAbort, "scheduler_overrun:seq=30000"):
            run_timed_segment(points, fake, time_scale=2.0,
                              clock=clock, sleep=lambda seconds: clock.sleep(seconds + 0.6))
        self.assertEqual(fake.sent, [])

    def test_rejects_unscaled_speed(self):
        clock = FakeClock()
        fake = FakeTransport(clock)
        with self.assertRaisesRegex(ValueError, "time_scale"):
            run_timed_segment([point(28363, 0.0, 11.0)], fake,
                              time_scale=1.0, clock=clock, sleep=clock.sleep)
        self.assertEqual(fake.sent, [])

    def test_growing_feedback_error_stops_before_fourth_target(self):
        clock = FakeClock()

        class GrowingErrorTransport(FakeTransport):
            def read_feedback(self):
                sample = super().read_feedback()
                error = 1.7 + len(self.sent) * 0.3
                return Feedback({**sample.positions,
                                 "shoulder_pan": sample.positions["shoulder_pan"] + error},
                                sample.received_monotonic)

        fake = GrowingErrorTransport(clock)
        points = [point(28363, 0.0, 11.0)] + [
            point(28363 + index, float(index), 11.0 + index * 0.1)
            for index in range(1, 5)]
        with self.assertRaisesRegex(TrialAbort, "tracking_error_growing"):
            run_timed_segment(points, fake, time_scale=2.0,
                              clock=clock, sleep=clock.sleep)
        self.assertEqual(len(fake.sent), 3)

    def test_target_20_35_allows_small_elbow_transient_while_lift_settles(self):
        clock = FakeClock()
        elbow_target = TARGETS_20_35[9][2]
        lift_target = TARGETS_20_35[9][1]
        fake = IntervalTransport(clock, [
            {"shoulder_lift": lift_target + 4.351648352,
             "elbow_flex": elbow_target - 0.043956044},
            {"shoulder_lift": lift_target + 3.0,
             "elbow_flex": elbow_target + 0.75},
        ])
        logged = []
        count = run_timed_segment(recorded_interval_points(), fake, time_scale=4.0,
                                  clock=clock, sleep=clock.sleep,
                                  on_feedback=lambda p, sent, observed:
                                      logged.append((p["seq"], dict(observed.positions))))
        self.assertEqual(count, 16)
        self.assertEqual(len([row for row in logged if row[0] == 31743]), 2)
        self.assertEqual(len(fake.sent), 16)

    def test_target_29_logs_abort_sample_then_blocks_persistent_elbow_growth(self):
        clock = FakeClock()
        elbow_target = TARGETS_20_35[9][2]
        lift_target = TARGETS_20_35[9][1]
        fake = IntervalTransport(clock, [
            {"shoulder_lift": lift_target + 4.351648352,
             "elbow_flex": elbow_target - 0.043956044},
            {"shoulder_lift": lift_target + 4.2,
             "elbow_flex": elbow_target + 2.0},
            {"shoulder_lift": lift_target + 4.1,
             "elbow_flex": elbow_target + 2.7},
        ])
        logged = []
        sample_timing = []
        with self.assertRaisesRegex(TrialAbort, "tracking_error_growing_during_settle:elbow_flex"):
            run_timed_segment(recorded_interval_points(), fake, time_scale=4.0,
                              clock=clock, sleep=clock.sleep,
                              on_feedback=lambda p, sent, observed:
                                  logged.append((p["seq"], dict(observed.positions))),
                              on_sample_timing=sample_timing.append)
        self.assertEqual(len(fake.sent), 10)
        self.assertEqual(len([row for row in logged if row[0] == 31743]), 3)
        self.assertAlmostEqual(logged[-1][1]["elbow_flex"], elbow_target + 2.7)
        self.assertEqual(sample_timing[-1]["seq"], 31743)
        self.assertEqual(sample_timing[-1]["guard_state"], "PENDING_CHECK")
        self.assertAlmostEqual(sample_timing[-1]["command_feedback_abs_error"]["elbow_flex"], 2.7)

    def test_target_29_over_four_degree_error_still_blocks_after_settle_timeout(self):
        clock = FakeClock()
        elbow_target = TARGETS_20_35[9][2]
        lift_target = TARGETS_20_35[9][1]
        fake = IntervalTransport(clock, [
            {"shoulder_lift": lift_target + 4.351648352,
             "elbow_flex": elbow_target - 0.043956044},
            {"shoulder_lift": lift_target + 3.0,
             "elbow_flex": elbow_target + 4.1},
        ])
        logged = []
        with self.assertRaisesRegex(TrialAbort, "tracking_settle_timeout:tracking_guard_exceeded:elbow_flex"):
            run_timed_segment(recorded_interval_points(), fake, time_scale=4.0,
                              clock=clock, sleep=clock.sleep,
                              on_feedback=lambda p, sent, observed:
                                  logged.append((p["seq"], dict(observed.positions))))
        self.assertEqual(len(fake.sent), 10)
        self.assertGreaterEqual(len([row for row in logged if row[0] == 31743]), 2)

    def test_target_29_far_tracking_error_logs_then_aborts_immediately(self):
        clock = FakeClock()
        elbow_target = TARGETS_20_35[9][2]
        lift_target = TARGETS_20_35[9][1]
        fake = IntervalTransport(clock, [
            {"shoulder_lift": lift_target + 4.351648352,
             "elbow_flex": elbow_target - 0.043956044},
            {"shoulder_lift": lift_target + 3.0,
             "elbow_flex": elbow_target + 6.0},
        ])
        logged = []
        with self.assertRaisesRegex(TrialAbort, "tracking_guard_far_exceeded:elbow_flex"):
            run_timed_segment(recorded_interval_points(), fake, time_scale=4.0,
                              clock=clock, sleep=clock.sleep,
                              on_feedback=lambda p, sent, observed:
                                  logged.append((p["seq"], dict(observed.positions))))
        self.assertEqual(len(fake.sent), 10)
        self.assertEqual(len([row for row in logged if row[0] == 31743]), 2)

    def test_target_29_urdf_margin_violation_logs_then_aborts_immediately(self):
        clock = FakeClock()
        elbow_target = TARGETS_20_35[9][2]
        lift_target = TARGETS_20_35[9][1]
        fake = IntervalTransport(clock, [
            {"shoulder_lift": lift_target + 4.351648352,
             "elbow_flex": elbow_target - 0.043956044},
            {"shoulder_lift": lift_target + 3.0, "elbow_flex": 90.1},
        ])
        logged = []
        with self.assertRaisesRegex(TrialAbort, "urdf_margin_below_5deg:elbow_flex"):
            run_timed_segment(recorded_interval_points(), fake, time_scale=4.0,
                              clock=clock, sleep=clock.sleep,
                              on_feedback=lambda p, sent, observed:
                                  logged.append((p["seq"], dict(observed.positions))))
        self.assertEqual(len(fake.sent), 10)
        self.assertEqual(len([row for row in logged if row[0] == 31743]), 2)
        self.assertEqual(logged[-1][1]["elbow_flex"], 90.1)


if __name__ == "__main__":
    unittest.main()
