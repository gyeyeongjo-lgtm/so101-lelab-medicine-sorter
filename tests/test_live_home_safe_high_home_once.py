import unittest
from pathlib import Path

from scripts.live_home_safe_high_home_once import (
    SCOPE, build_offline_report, load_context, run,
)


ROOT = Path(__file__).resolve().parents[1]


def context():
    return load_context(
        poses_path=ROOT / "configs/poses.yaml",
        tcp_path=ROOT / "configs/c_pick_grasp_tcp_candidate_20261012.json",
        escape_path=ROOT / "configs/c_pick_safe_escape_only_20261012.json",
        calibration_path=(
            ROOT / "configs/so101_follower_calibration_bounds_20261008.json"),
        urdf_path=(
            ROOT / ".local/c-red-pivot-tcp-table-20261011-s01/so101_new_calib.urdf"),
    )


class HomeSafeHighHomeOnceTests(unittest.TestCase):
    def test_recorded_round_trip_offline_metrics(self):
        plan, report = build_offline_report(context())
        self.assertEqual(report["home_to_safe_high_waypoint_count"], 78)
        self.assertEqual(report["safe_high_to_home_waypoint_count"], 78)
        self.assertLessEqual(report["maximum_per_joint_step_deg"], 2.0)
        self.assertTrue(report["home_to_safe_high_z_monotonic_non_decreasing"])
        self.assertTrue(report["safe_high_to_home_z_monotonic_non_increasing"])
        self.assertTrue(report["final_home_exact_in_plan"])
        self.assertTrue(report["offline_constraints_pass"])
        self.assertEqual([item.name for item in plan.segments], [
            "SAFE_HIGH_EXCEPT_PAN", "PAN_ALIGNMENT",
            "HOME_EXCEPT_PAN", "HOME_PAN_ALIGNMENT",
        ])

    def test_dry_run_never_constructs_transport(self):
        called = []
        result = run(
            context=context(), live=False, confirm_scope=None,
            transport_factory=lambda: called.append(True))
        self.assertEqual(result, 0)
        self.assertEqual(called, [])

    def test_wrong_phrase_does_not_construct_transport(self):
        called = []
        result = run(
            context=context(), live=True, confirm_scope=SCOPE,
            input_fn=lambda _prompt: "NO",
            transport_factory=lambda: called.append(True))
        self.assertEqual(result, 2)
        self.assertEqual(called, [])


if __name__ == "__main__":
    unittest.main()
