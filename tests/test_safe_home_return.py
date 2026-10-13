import unittest

from scripts.safe_home_return import (
    attempt_safe_recovery, build_go_home_safe_plan, evaluate_return_waypoint,
    flatten_return_plan, go_home_safe,
)
from scripts.staged_cycle_execution import JOINT_UNITS


def pose(**changes):
    result = {name: 0.0 for name in JOINT_UNITS}
    result.update(changes)
    return result


class SafeHomeReturnTests(unittest.TestCase):
    def test_low_pose_requires_validated_escape(self):
        with self.assertRaisesRegex(ValueError, "requires_validated_safe_escape"):
            build_go_home_safe_plan(
                current=pose(), safe_high=pose(shoulder_lift=20), home=pose(),
                current_grasp_tcp_z_mm=60, table_reference_z_mm=55)

    def test_order_pan_delay_gripper_hold_and_two_degree_bound(self):
        current = pose(shoulder_pan=-10, shoulder_lift=-20, gripper=25)
        escape = pose(shoulder_pan=-9, shoulder_lift=-18, gripper=25)
        safe_high = pose(shoulder_pan=15, shoulder_lift=30, elbow_flex=10,
                         wrist_flex=-10, wrist_roll=5, gripper=80)
        home = pose(shoulder_pan=0, shoulder_lift=0, gripper=0)
        plan = build_go_home_safe_plan(
            current=current, safe_high=safe_high, home=home,
            current_grasp_tcp_z_mm=60, table_reference_z_mm=55,
            safe_escape_goals=[escape])
        self.assertEqual([item.name for item in plan.segments], [
            "SAFE_ESCAPE", "SAFE_HIGH_EXCEPT_PAN", "PAN_ALIGNMENT",
            "HOME_EXCEPT_PAN", "HOME_PAN_ALIGNMENT"])
        previous = current
        for segment in plan.segments:
            for goal in segment.goals:
                self.assertLessEqual(max(
                    abs(goal[name] - previous[name])
                    for name in JOINT_UNITS if name != "gripper"), 2.0 + 1e-9)
                self.assertEqual(goal["gripper"], 25)
                previous = goal
        no_pan = next(item for item in plan.segments
                      if item.name == "SAFE_HIGH_EXCEPT_PAN")
        self.assertTrue(all(goal["shoulder_pan"] == escape["shoulder_pan"]
                            for goal in no_pan.goals))
        home_no_pan = next(item for item in plan.segments
                           if item.name == "HOME_EXCEPT_PAN")
        self.assertTrue(all(goal["shoulder_pan"] == safe_high["shoulder_pan"]
                            for goal in home_no_pan.goals))
        flattened = flatten_return_plan(plan)
        self.assertEqual(flattened[-1][0], "HOME_PAN_ALIGNMENT")
        self.assertEqual(flattened[-1][1]["shoulder_pan"], home["shoulder_pan"])

    def test_failure_stops_and_never_runs_later_segment(self):
        plan = build_go_home_safe_plan(
            current=pose(shoulder_pan=-5),
            safe_high=pose(shoulder_pan=5, shoulder_lift=10),
            home=pose(), current_grasp_tcp_z_mm=100,
            table_reference_z_mm=55)
        called = []
        stopped = []

        def execute(name, _goals):
            called.append(name)
            return name != "PAN_ALIGNMENT"

        result = go_home_safe(
            plan, approved=True, execute_segment=execute,
            stop_commands=lambda: stopped.append(True))
        self.assertEqual(result["status"], "STOPPED")
        self.assertEqual(called, ["SAFE_HIGH_EXCEPT_PAN", "PAN_ALIGNMENT"])
        self.assertEqual(stopped, [True])
        self.assertFalse(result["further_motion"])

    def test_exception_does_not_trigger_recovery_motion(self):
        plan = build_go_home_safe_plan(
            current=pose(), safe_high=pose(shoulder_lift=10), home=pose(),
            current_grasp_tcp_z_mm=100, table_reference_z_mm=55)
        motions = []
        result = go_home_safe(
            plan, approved=True,
            execute_segment=lambda name, goals: (_ for _ in ()).throw(
                RuntimeError("feedback lost")),
            stop_commands=lambda: motions.append("STOP"))
        self.assertEqual(motions, ["STOP"])
        self.assertEqual(result["status"], "STOPPED")

    def test_safe_recovery_is_separate_and_requires_approval(self):
        with self.assertRaisesRegex(ValueError, "approval"):
            attempt_safe_recovery(
                approved=False, communication_ok=True, feedback_ok=True,
                planning_failure_only=True, recovery=lambda: True)
        self.assertTrue(attempt_safe_recovery(
            approved=True, communication_ok=True, feedback_ok=True,
            planning_failure_only=True, recovery=lambda: True))

    def test_return_waypoint_passes_with_fresh_settled_safe_motion(self):
        before = pose(shoulder_lift=10, elbow_flex=20, gripper=2)
        target = pose(shoulder_lift=11, elbow_flex=19, gripper=2)
        after = pose(shoulder_lift=10.7, elbow_flex=19.3, gripper=2)
        bounds = {name: (-100.0, 100.0) for name in JOINT_UNITS}
        result = evaluate_return_waypoint(
            present_before=before, requested_target=target,
            present_after=after, moving={name: 0 for name in JOINT_UNITS},
            present_load={name: 180 if name == "elbow_flex" else 0
                          for name in JOINT_UNITS},
            temperature_c={name: 45 for name in JOINT_UNITS},
            calibrated_bounds=bounds, table_proxy_margin_mm=50.0,
            minimum_table_proxy_margin_mm=44.0,
            self_collision_proxy_mm=60.0,
            minimum_self_collision_proxy_mm=55.0,
            feedback_fresh=True, communication_ok=True)
        self.assertTrue(result["pass"])
        self.assertFalse(result["present_load_numeric_gate"])

    def test_return_waypoint_fails_wrong_direction_temperature_or_proxy(self):
        before = pose(shoulder_lift=10, gripper=2)
        target = pose(shoulder_lift=11, gripper=2)
        after = pose(shoulder_lift=9.5, gripper=2)
        bounds = {name: (-100.0, 100.0) for name in JOINT_UNITS}
        result = evaluate_return_waypoint(
            present_before=before, requested_target=target,
            present_after=after, moving={name: 0 for name in JOINT_UNITS},
            present_load={name: 0 for name in JOINT_UNITS},
            temperature_c={name: 56 if name == "elbow_flex" else 40
                           for name in JOINT_UNITS},
            calibrated_bounds=bounds, table_proxy_margin_mm=43.0,
            minimum_table_proxy_margin_mm=44.0,
            self_collision_proxy_mm=54.0,
            minimum_self_collision_proxy_mm=55.0,
            feedback_fresh=True, communication_ok=True)
        self.assertFalse(result["pass"])
        self.assertFalse(result["movement_ok"])
        self.assertFalse(result["temperature_ok"])
        self.assertFalse(result["table_proxy_ok"])
        self.assertFalse(result["self_collision_proxy_ok"])


if __name__ == "__main__":
    unittest.main()
