import json
from pathlib import Path
import tempfile
import unittest

from scripts.live_c_approach import (
    ARM_NAMES, interpolate_goals, interpolate_staged_goals, load_plan,
    validate_staged_reference_start,
)
from scripts.staged_cycle_execution import JOINT_UNITS


class LiveCApproachTests(unittest.TestCase):
    def test_candidate_plan_loads(self):
        plan = load_plan(Path("configs/live_c_approach_candidate_20261011.json"))
        self.assertEqual(plan["scope"], "live_c_pre_approach_only")
        self.assertEqual(set(plan["target_arm_deg"]), set(ARM_NAMES))

    def test_current_plan_uses_exact_continuous_following_contract(self):
        plan = load_plan(Path("configs/live_c_approach_candidate_20261011_current.json"))
        self.assertEqual(plan["execution_mode"], "bounded_continuous_following")
        self.assertEqual(plan["maximum_joint_step_deg"], 1.0)
        self.assertEqual(plan["following_cadence_s"], 0.2)
        self.assertEqual(plan["following_error_limits_deg"]["elbow_flex"], 4.0)
        self.assertTrue(all(plan["following_error_limits_deg"][name] == 2.5
                            for name in ARM_NAMES if name != "elbow_flex"))
        self.assertEqual(plan["final_waypoint_timeout_s"], 5.0)

    def test_staged_plan_preserves_existing_endpoint_and_two_intermediates(self):
        plan = load_plan(Path("configs/live_c_approach_candidate_20261011_staged.json"))
        self.assertEqual(len(plan["staged_intermediate_arm_deg"]), 2)
        self.assertEqual(plan["target_arm_deg"], {
            "shoulder_pan": -0.014220,
            "shoulder_lift": 11.507515,
            "elbow_flex": 14.866481,
            "wrist_flex": 12.933013,
            "wrist_roll": 13.899293,
        })

    def test_interpolation_holds_gripper_and_limits_step(self):
        start = {name: 0.0 for name in JOINT_UNITS}
        start["gripper"] = 37.5
        target = {name: (9.0 if index % 2 else -7.0)
                  for index, name in enumerate(ARM_NAMES)}
        goals = interpolate_goals(start, target, 2.0)
        previous = start
        for goal in goals:
            self.assertEqual(goal["gripper"], 37.5)
            self.assertLessEqual(max(abs(goal[name] - previous[name])
                                     for name in ARM_NAMES), 2.0 + 1e-9)
            previous = goal
        self.assertEqual({name: goals[-1][name] for name in ARM_NAMES}, target)

    def test_tail_refinement_preserves_route_and_target(self):
        start = {name: 0.0 for name in JOINT_UNITS}
        start["gripper"] = 25.0
        target = {name: 20.0 for name in ARM_NAMES}
        base = interpolate_goals(start, target, 2.0)
        refined = interpolate_goals(
            start, target, 2.0,
            refine_last_waypoints=5, final_refinement_factor=2)
        self.assertEqual(len(base), 10)
        self.assertEqual(len(refined), 15)
        self.assertEqual(refined[:5], base[:5])
        self.assertEqual(refined[-1], base[-1])
        previous = start
        for goal in refined:
            self.assertEqual(goal["gripper"], 25.0)
            deltas = [goal[name] - previous[name] for name in ARM_NAMES]
            self.assertTrue(all(abs(delta - deltas[0]) < 1e-9 for delta in deltas))
            self.assertLessEqual(max(abs(delta) for delta in deltas), 2.0 + 1e-9)
            previous = goal
        tail_elbow_steps = [
            refined[index]["elbow_flex"] - refined[index - 1]["elbow_flex"]
            for index in range(6, len(refined))
        ]
        self.assertTrue(all(abs(step - 1.0) < 1e-9 for step in tail_elbow_steps))

    def test_staged_interpolation_hits_both_intermediates_without_joint_jump(self):
        plan = load_plan(Path("configs/live_c_approach_candidate_20261011_staged.json"))
        start = {**plan["staged_reference_start_arm_deg"], "gripper": 2.0}
        goals = interpolate_staged_goals(
            start, plan["staged_intermediate_arm_deg"], plan["target_arm_deg"], 1.0)
        self.assertEqual(len(goals), 125)
        previous = start
        seen = []
        for goal in goals:
            self.assertLessEqual(max(abs(goal[name] - previous[name])
                                     for name in ARM_NAMES), 1.0 + 1e-9)
            self.assertEqual(goal["gripper"], 2.0)
            arm = {name: goal[name] for name in ARM_NAMES}
            if arm in plan["staged_intermediate_arm_deg"]:
                seen.append(arm)
            previous = goal
        self.assertEqual(seen, plan["staged_intermediate_arm_deg"])
        for name in ARM_NAMES:
            self.assertAlmostEqual(goals[-1][name], plan["target_arm_deg"][name], places=9)

    def test_staged_start_gate_rejects_before_path_generation(self):
        plan = load_plan(Path("configs/live_c_approach_candidate_20261011_staged.json"))
        fresh = {**plan["staged_reference_start_arm_deg"], "gripper": 2.0}
        validate_staged_reference_start(fresh, plan["staged_reference_start_arm_deg"])
        fresh["elbow_flex"] += 1.01
        with self.assertRaisesRegex(RuntimeError, "staged_reference_start_mismatch"):
            validate_staged_reference_start(fresh, plan["staged_reference_start_arm_deg"])

    def test_fresh2_staged_plan_generates_107_targets(self):
        plan = load_plan(Path("configs/live_c_approach_candidate_20261011_staged_fresh2.json"))
        start = {**plan["staged_reference_start_arm_deg"], "gripper": 1.958384}
        goals = interpolate_staged_goals(
            start, plan["staged_intermediate_arm_deg"], plan["target_arm_deg"], 1.0)
        self.assertEqual(len(goals), 107)
        for name in ARM_NAMES:
            self.assertAlmostEqual(goals[-1][name], plan["target_arm_deg"][name], places=9)

    def test_strong_unload_fresh3_holds_elbow_before_lift_and_generates_105_targets(self):
        plan = load_plan(Path(
            "configs/live_c_approach_candidate_20261011_staged_strong_unload_fresh3.json"
        ))
        start = {**plan["staged_reference_start_arm_deg"], "gripper": 1.958384}
        first, second = plan["staged_intermediate_arm_deg"]
        self.assertAlmostEqual(first["elbow_flex"], start["elbow_flex"], places=9)
        self.assertGreater(first["shoulder_lift"], start["shoulder_lift"])
        self.assertEqual(first["shoulder_pan"], start["shoulder_pan"])
        self.assertEqual(first["wrist_roll"], start["wrist_roll"])
        goals = interpolate_staged_goals(
            start, plan["staged_intermediate_arm_deg"], plan["target_arm_deg"], 1.0)
        self.assertEqual(len(goals), 105)
        previous = start
        for goal in goals:
            self.assertLessEqual(max(abs(goal[name] - previous[name])
                                     for name in ARM_NAMES), 1.0 + 1e-9)
            previous = goal
        for name in ARM_NAMES:
            self.assertAlmostEqual(goals[-1][name], plan["target_arm_deg"][name], places=9)

    def test_coupled_final_fresh4_accepts_four_intermediates_and_generates_71_targets(self):
        plan = load_plan(Path(
            "configs/live_c_approach_candidate_20261011_coupled_final_fresh4.json"
        ))
        self.assertEqual(len(plan["staged_intermediate_arm_deg"]), 4)
        start = {**plan["staged_reference_start_arm_deg"], "gripper": 1.958384}
        goals = interpolate_staged_goals(
            start, plan["staged_intermediate_arm_deg"], plan["target_arm_deg"], 1.0)
        self.assertEqual(len(goals), 71)
        previous = start
        for goal in goals:
            self.assertLessEqual(max(abs(goal[name] - previous[name])
                                     for name in ARM_NAMES), 1.0 + 1e-9)
            previous = goal
        for name in ARM_NAMES:
            self.assertAlmostEqual(goals[-1][name], plan["target_arm_deg"][name], places=9)

    def test_delayed_wrist_fresh5_preserves_coupling_and_generates_71_targets(self):
        plan = load_plan(Path(
            "configs/live_c_approach_candidate_20261011_delayed_wrist_fresh5.json"
        ))
        self.assertEqual(len(plan["staged_intermediate_arm_deg"]), 4)
        start = {**plan["staged_reference_start_arm_deg"], "gripper": 2.203182}
        goals = interpolate_staged_goals(
            start, plan["staged_intermediate_arm_deg"], plan["target_arm_deg"], 1.0)
        self.assertEqual(len(goals), 71)
        # Wrist is held at the fresh value until the first 25% coupled stage.
        self.assertAlmostEqual(
            plan["staged_intermediate_arm_deg"][0]["wrist_flex"],
            start["wrist_flex"], places=6)
        previous = start
        for goal in goals:
            self.assertLessEqual(max(abs(goal[name] - previous[name])
                                     for name in ARM_NAMES), 1.0 + 1e-9)
            self.assertEqual(goal["gripper"], start["gripper"])
            previous = goal
        for name in ARM_NAMES:
            self.assertAlmostEqual(goals[-1][name], plan["target_arm_deg"][name], places=9)

    def test_plan_rejects_motion_authorized_or_wrong_port(self):
        source = Path("configs/live_c_approach_candidate_20261011.json")
        raw = json.loads(source.read_text())
        for change in ({"motion_authorized": True}, {"follower_port": "/dev/ttyACM0"}):
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "plan.json"
                path.write_text(json.dumps({**raw, **change}))
                with self.assertRaises(ValueError):
                    load_plan(path)

    def test_plan_rejects_missing_required_field(self):
        source = Path("configs/live_c_approach_candidate_20261011.json")
        raw = json.loads(source.read_text())
        del raw["source_frame_sha256"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plan.json"
            path.write_text(json.dumps(raw))
            with self.assertRaisesRegex(ValueError, "approach_plan_fields_missing"):
                load_plan(path)


if __name__ == "__main__":
    unittest.main()
