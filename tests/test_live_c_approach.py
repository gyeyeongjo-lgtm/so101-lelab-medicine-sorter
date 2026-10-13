from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import numpy as np
import yaml

from scripts.continuous_following_execution import (
    ContinuousFollowingCycle, FollowingTelemetry,
)
from scripts.live_c_approach import (
    ARM_NAMES, CURRENT_TO_C_START_POSE, PRE_APPROACH_SCOPE,
    RETURN_TO_PICK_READY_SCOPE, SCOPE_CONTRACTS, STRICT_POSE_TOLERANCES_DEG,
    WRIST_LEAD_PHASE_GATE_POLICY, WRIST_LEAD_PHASE_NAME,
    final_tolerances_for_plan, interpolate_goals, interpolate_staged_goals,
    load_plan, load_verified_fk_kinematics, run,
    validate_staged_reference_start, verify_wrist_lead_phase_gate,
    wrist_lead_phase_goals,
)
from scripts.plan_pick_grasp_tcp_ik import (
    _path_report, _transform, axis_error_deg, rotation_error_deg, tcp_position_mm,
)
from scripts.urdf_forward_kinematics import UrdfKinematics
from scripts.staged_cycle_execution import JOINT_UNITS, STAGES


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

    def test_safe_high_to_new_grasp_tcp_pre_approach_plan(self):
        path = Path("configs/live_c_pre_approach_from_safe_high_20261012.json")
        plan = load_plan(path)
        self.assertEqual(plan["start_pose_name"], "SAFE_HIGH")
        self.assertEqual(plan["run_phrase"], "RUN SAFE HIGH TO C PRE APPROACH")
        self.assertEqual(plan["tcp_frame"], "PICK_GRASP_OPENING_CENTER")
        self.assertTrue(plan["orientation_solved"])
        self.assertFalse(plan["collision_checked"])

        poses = yaml.safe_load(Path("configs/poses.yaml").read_text())
        recorded = poses["poses"]["SAFE_HIGH"]["joints"]
        expected_start = {
            name: recorded[name]["degree_mean"] for name in ARM_NAMES
        }
        self.assertEqual(plan["staged_reference_start_arm_deg"], expected_start)
        start = {**expected_start, "gripper": recorded["gripper"]["degree_mean"]}
        goals = interpolate_staged_goals(
            start, plan["staged_intermediate_arm_deg"],
            plan["target_arm_deg"], plan["maximum_joint_step_deg"])
        self.assertEqual(len(goals), 146)
        samples = np.asarray([
            [start[name] for name in ARM_NAMES],
            *[[goal[name] for name in ARM_NAMES] for goal in goals],
        ])
        self.assertLessEqual(
            float(np.max(np.abs(np.diff(samples, axis=0)))), 1.0 + 1e-12)

        urdf = Path(".local/c-red-pivot-tcp-table-20261011-s01/so101_new_calib.urdf")
        kinematics = UrdfKinematics.from_file(urdf)
        offset = np.asarray(plan["tcp_offset_gripper_mm"], dtype=float)
        target = np.asarray(plan["target_robot_xyz_mm"], dtype=float)
        report = _path_report(
            kinematics, samples, offset,
            np.asarray([
                [-116.374, 116.374], [-99.846, 99.846], [-95.011, 95.011],
                [-98.615, 98.615], [-154.352, 154.352],
            ]), 54.659)
        final_tcp = tcp_position_mm(kinematics, samples[-1], offset)
        self.assertLess(float(np.linalg.norm(final_tcp - target)), 1e-4)
        self.assertGreaterEqual(report["minimum_tcp_table_proxy_margin_mm"], 45.341)
        self.assertGreaterEqual(
            report["minimum_nonadjacent_centerline_distance_mm"], 64.775)
        self.assertGreaterEqual(report["minimum_servo_margin_deg"], 21.736)

        reference = _transform(kinematics, np.asarray([
            18.065934065934066, -11.296703296703297, 60.0,
            -32.30769230769231, -11.56043956043956,
        ]))[:3, :3]
        actual = _transform(kinematics, samples[-1])[:3, :3]
        self.assertLess(rotation_error_deg(actual, reference), 3.1)
        self.assertLess(axis_error_deg(-actual[:, 2], -reference[:, 2]), 3.1)
        self.assertLess(axis_error_deg(actual[:, 0], reference[:, 0]), 0.7)

    def test_home_to_new_grasp_tcp_pre_approach_plan(self):
        path = Path("configs/live_c_pre_approach_from_home_20261012.json")
        plan = load_plan(path)
        self.assertEqual(plan["start_pose_name"], "HOME")
        self.assertEqual(plan["run_phrase"], "RUN HOME TO C PRE APPROACH")
        self.assertEqual(plan["start_pose_tolerance_deg"], {
            "shoulder_pan": 0.5,
            "shoulder_lift": 1.5,
            "elbow_flex": 1.5,
            "wrist_flex": 0.5,
            "wrist_roll": 0.5,
        })
        self.assertEqual(plan["tcp_frame"], "PICK_GRASP_OPENING_CENTER")
        self.assertFalse(plan["collision_checked"])

        poses = yaml.safe_load(Path("configs/poses.yaml").read_text())
        recorded = poses["poses"]["HOME"]["joints"]
        expected_start = {
            name: recorded[name]["degree_mean"] for name in ARM_NAMES
        }
        self.assertEqual(plan["staged_reference_start_arm_deg"], expected_start)
        start = {**expected_start, "gripper": recorded["gripper"]["degree_mean"]}
        goals = interpolate_staged_goals(
            start, plan["staged_intermediate_arm_deg"],
            plan["target_arm_deg"], plan["maximum_joint_step_deg"])
        self.assertEqual(len(goals), 62)
        samples = np.asarray([
            [start[name] for name in ARM_NAMES],
            *[[goal[name] for name in ARM_NAMES] for goal in goals],
        ])
        self.assertLessEqual(
            float(np.max(np.abs(np.diff(samples, axis=0)))), 1.0 + 1e-12)

        first_stage = plan["staged_intermediate_arm_deg"][0]
        self.assertEqual(first_stage["elbow_flex"], expected_start["elbow_flex"])
        self.assertEqual(first_stage["wrist_flex"], expected_start["wrist_flex"])
        self.assertGreater(first_stage["shoulder_lift"], expected_start["shoulder_lift"])

        urdf = Path(".local/c-red-pivot-tcp-table-20261011-s01/so101_new_calib.urdf")
        kinematics = UrdfKinematics.from_file(urdf)
        offset = np.asarray(plan["tcp_offset_gripper_mm"], dtype=float)
        target = np.asarray(plan["target_robot_xyz_mm"], dtype=float)
        report = _path_report(
            kinematics, samples, offset,
            np.asarray([
                [-116.374, 116.374], [-99.846, 99.846], [-95.011, 95.011],
                [-98.615, 98.615], [-154.352, 154.352],
            ]), 54.659)
        final_tcp = tcp_position_mm(kinematics, samples[-1], offset)
        self.assertLess(float(np.linalg.norm(final_tcp - target)), 1e-4)
        self.assertGreaterEqual(report["minimum_tcp_table_proxy_margin_mm"], 26.376)
        self.assertGreaterEqual(
            report["minimum_nonadjacent_centerline_distance_mm"], 55.827)
        self.assertGreaterEqual(report["minimum_servo_margin_deg"], 17.604)

    def test_home_start_gate_uses_existing_per_joint_tolerances(self):
        plan = load_plan(Path(
            "configs/live_c_pre_approach_from_home_20261012.json"))
        reference = plan["staged_reference_start_arm_deg"]
        fresh = {**reference, "gripper": 2.0}
        fresh["shoulder_lift"] += 1.49
        fresh["wrist_flex"] += 0.49
        validate_staged_reference_start(
            fresh, reference, tolerance_deg=plan["start_pose_tolerance_deg"])
        fresh["wrist_flex"] += 0.02
        with self.assertRaisesRegex(RuntimeError, "staged_reference_start_mismatch"):
            validate_staged_reference_start(
                fresh, reference, tolerance_deg=plan["start_pose_tolerance_deg"])

    def test_pick_ready_start_gate_uses_recorded_pose_and_per_joint_tolerances(self):
        poses = yaml.safe_load(Path("configs/poses.yaml").read_text())
        self.assertEqual(poses["pose_status"]["PICK_READY"], "RECORDED")
        recorded = poses["poses"]["PICK_READY"]["joints"]
        reference = {
            name: recorded[name]["degree_mean"] for name in ARM_NAMES
        }
        tolerances = {
            "shoulder_pan": 0.5,
            "shoulder_lift": 1.5,
            "elbow_flex": 1.5,
            "wrist_flex": 0.5,
            "wrist_roll": 0.5,
        }
        raw = json.loads(Path(
            "configs/live_c_pre_approach_from_home_20261012.json"
        ).read_text())
        raw.update({
            "start_pose_name": "PICK_READY",
            "run_phrase": "RUN PICK READY TO C PRE APPROACH",
            "start_pose_tolerance_deg": tolerances,
            "staged_reference_start_arm_deg": reference,
        })
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plan.json"
            path.write_text(json.dumps(raw))
            plan = load_plan(path)

        self.assertEqual(plan["start_pose_name"], "PICK_READY")
        self.assertEqual(plan["run_phrase"],
                         "RUN PICK READY TO C PRE APPROACH")
        self.assertEqual(plan["staged_reference_start_arm_deg"], reference)
        self.assertEqual(plan["start_pose_tolerance_deg"], tolerances)

        fresh = {**reference, "gripper": recorded["gripper"]["degree_mean"]}
        fresh["shoulder_lift"] += 1.49
        fresh["wrist_flex"] += 0.49
        validate_staged_reference_start(
            fresh, reference, tolerance_deg=plan["start_pose_tolerance_deg"])
        fresh["wrist_flex"] += 0.02
        with self.assertRaisesRegex(RuntimeError,
                                    "staged_reference_start_mismatch"):
            validate_staged_reference_start(
                fresh, reference,
                tolerance_deg=plan["start_pose_tolerance_deg"])

    def test_pick_ready_to_new_grasp_tcp_pre_approach_plan(self):
        plan = load_plan(Path(
            "configs/live_c_pre_approach_from_pick_ready_20261013.json"))
        self.assertEqual(plan["start_pose_name"], "PICK_READY")
        self.assertEqual(plan["run_phrase"],
                         "RUN PICK READY TO C PRE APPROACH")
        self.assertEqual(plan["start_pose_tolerance_deg"], {
            "shoulder_pan": 0.5,
            "shoulder_lift": 1.5,
            "elbow_flex": 1.5,
            "wrist_flex": 0.5,
            "wrist_roll": 0.5,
        })
        self.assertEqual(plan["tcp_frame"], "PICK_GRASP_OPENING_CENTER")
        self.assertEqual(plan["calibration_pin_tcp_usage"], "CALIBRATION_ONLY")
        self.assertTrue(plan["orientation_solved"])
        self.assertFalse(plan["collision_checked"])
        self.assertFalse(plan["motion_authorized"])

        poses = yaml.safe_load(Path("configs/poses.yaml").read_text())
        recorded = poses["poses"]["PICK_READY"]["joints"]
        expected_start = {
            name: recorded[name]["degree_mean"] for name in ARM_NAMES
        }
        self.assertEqual(plan["staged_reference_start_arm_deg"], expected_start)
        start = {**expected_start, "gripper": recorded["gripper"]["degree_mean"]}
        validate_staged_reference_start(
            start, expected_start,
            tolerance_deg=plan["start_pose_tolerance_deg"])

        goals = interpolate_staged_goals(
            start, plan["staged_intermediate_arm_deg"],
            plan["target_arm_deg"], plan["maximum_joint_step_deg"])
        self.assertEqual(len(goals), 63)
        samples = np.asarray([
            [start[name] for name in ARM_NAMES],
            *[[goal[name] for name in ARM_NAMES] for goal in goals],
        ])
        self.assertLessEqual(
            float(np.max(np.abs(np.diff(samples, axis=0)))), 1.0 + 1e-12)

        urdf = Path(".local/c-red-pivot-tcp-table-20261011-s01/so101_new_calib.urdf")
        kinematics = UrdfKinematics.from_file(urdf)
        offset = np.asarray(plan["tcp_offset_gripper_mm"], dtype=float)
        target = np.asarray(plan["target_robot_xyz_mm"], dtype=float)
        tcp_path = np.asarray([
            tcp_position_mm(kinematics, joints, offset) for joints in samples
        ])
        report = _path_report(
            kinematics, samples, offset,
            np.asarray([
                [-116.374, 116.374], [-99.846, 99.846], [-95.011, 95.011],
                [-98.615, 98.615], [-154.352, 154.352],
            ]), 54.659)
        self.assertLess(float(np.linalg.norm(tcp_path[-1] - target)), 1e-4)
        self.assertLessEqual(float(np.max(np.diff(tcp_path[:, 2]))), 1e-9)
        self.assertGreaterEqual(report["minimum_tcp_table_proxy_margin_mm"], 45.341)
        self.assertGreaterEqual(report["minimum_nonbase_link_origin_z_mm"] - 54.659,
                                40.222)
        self.assertGreaterEqual(
            report["minimum_nonadjacent_centerline_distance_mm"], 64.775)
        self.assertGreaterEqual(report["minimum_servo_margin_deg"], 24.419)
        self.assertEqual(report["self_collision_centerline_proxy"], "PASS")
        self.assertEqual(report["environment_collision_proxy"],
                         "TCP_POINT_ONLY_PASS")
        self.assertEqual(report["full_mesh_collision_status"], "NOT_VERIFIED")

        reference = _transform(kinematics, np.asarray([
            18.065934065934066, -11.296703296703297, 60.0,
            -32.30769230769231, -11.56043956043956,
        ]))[:3, :3]
        actual = _transform(kinematics, samples[-1])[:3, :3]
        self.assertLess(rotation_error_deg(actual, reference), 3.1)
        self.assertLess(axis_error_deg(-actual[:, 2], -reference[:, 2]), 3.1)
        self.assertLess(axis_error_deg(actual[:, 0], reference[:, 0]), 0.7)

    def test_pick_ready_start_contract_requires_per_joint_tolerances(self):
        raw = json.loads(Path(
            "configs/live_c_pre_approach_from_home_20261012.json"
        ).read_text())
        raw.update({
            "start_pose_name": "PICK_READY",
            "run_phrase": "RUN PICK READY TO C PRE APPROACH",
            "start_pose_tolerance_deg": 1.0,
        })
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plan.json"
            path.write_text(json.dumps(raw))
            with self.assertRaisesRegex(
                    ValueError, "approach_start_contract_invalid"):
                load_plan(path)

    def test_actual_pre_approach_return_to_pick_ready_plan(self):
        return_path = Path(
            "configs/live_c_return_to_pick_ready_20261013.json")
        with self.assertRaisesRegex(ValueError,
                                    "approach_plan_contract_mismatch"):
            load_plan(return_path)
        plan = load_plan(return_path,
                         expected_scope=RETURN_TO_PICK_READY_SCOPE)
        self.assertEqual(plan["start_pose_name"],
                         "C_PRE_APPROACH_ACTUAL_ATTEMPT1")
        self.assertEqual(plan["target_pose_name"], "PICK_READY")
        self.assertEqual(plan["run_phrase"],
                         "RUN C PRE APPROACH TO PICK READY")
        self.assertFalse(plan["motion_authorized"])
        self.assertFalse(plan["collision_checked"])
        self.assertEqual(
            plan["offline_path_validation"]["full_mesh_environment"],
            "NOT_VERIFIED")

        forward = load_plan(Path(
            "configs/live_c_pre_approach_from_pick_ready_20261013.json"))
        self.assertEqual(plan["staged_intermediate_arm_deg"],
                         list(reversed(forward["staged_intermediate_arm_deg"])))
        poses = yaml.safe_load(Path("configs/poses.yaml").read_text())
        recorded = poses["poses"]["PICK_READY"]["joints"]
        expected_target = {
            name: recorded[name]["degree_mean"] for name in ARM_NAMES
        }
        self.assertEqual(plan["target_arm_deg"], expected_target)

        start = {**plan["staged_reference_start_arm_deg"],
                 "gripper": recorded["gripper"]["degree_mean"]}
        validate_staged_reference_start(
            start, plan["staged_reference_start_arm_deg"],
            tolerance_deg=plan["start_pose_tolerance_deg"])
        goals = interpolate_staged_goals(
            start, plan["staged_intermediate_arm_deg"],
            plan["target_arm_deg"], plan["maximum_joint_step_deg"])
        self.assertEqual(len(goals), 61)
        self.assertTrue(all(goal["gripper"] == start["gripper"]
                            for goal in goals))
        samples = np.asarray([
            [start[name] for name in ARM_NAMES],
            *[[goal[name] for name in ARM_NAMES] for goal in goals],
        ])
        self.assertLessEqual(
            float(np.max(np.abs(np.diff(samples, axis=0)))), 1.0 + 1e-12)

        urdf = Path(".local/c-red-pivot-tcp-table-20261011-s01/so101_new_calib.urdf")
        kinematics = UrdfKinematics.from_file(urdf)
        offset = np.asarray(plan["tcp_offset_gripper_mm"], dtype=float)
        tcp_path = np.asarray([
            tcp_position_mm(kinematics, joints, offset) for joints in samples
        ])
        report = _path_report(
            kinematics, samples, offset,
            np.asarray([
                [-116.374, 116.374], [-99.846, 99.846], [-95.011, 95.011],
                [-98.615, 98.615], [-154.352, 154.352],
            ]), 54.659)
        self.assertLess(float(np.linalg.norm(
            tcp_path[-1] - np.asarray(plan["target_robot_xyz_mm"]))), 1e-6)
        self.assertGreaterEqual(float(np.min(np.diff(tcp_path[:, 2]))), -1e-9)
        self.assertGreaterEqual(report["minimum_tcp_table_proxy_margin_mm"],
                                38.948)
        self.assertGreaterEqual(
            report["minimum_nonadjacent_centerline_distance_mm"], 64.775)
        self.assertGreaterEqual(report["minimum_servo_margin_deg"], 24.285)
        self.assertEqual(report["self_collision_centerline_proxy"], "PASS")
        self.assertEqual(report["environment_collision_proxy"],
                         "TCP_POINT_ONLY_PASS")
        self.assertEqual(report["full_mesh_collision_status"], "NOT_VERIFIED")

    def test_return_scope_uses_distinct_confirmation_and_pass_marker(self):
        plan_path = Path("configs/live_c_return_to_pick_ready_20261013.json")
        plan = load_plan(plan_path, expected_scope=RETURN_TO_PICK_READY_SCOPE)
        start = {**plan["staged_reference_start_arm_deg"], "gripper": 2.080783}
        final = {**plan["target_arm_deg"], "gripper": start["gripper"]}

        class Feedback:
            def __init__(self, positions):
                self.positions = positions
                self.received_monotonic = time.monotonic()

        class FakeTransport:
            def __init__(self):
                self.feedback = [Feedback(start), Feedback(final)]
                self.closed = False
                self.stopped = False

            def read_feedback(self):
                return self.feedback.pop(0)

            def verify_start_pose(self, *_args, **_kwargs):
                return None

            def stop_commands(self):
                self.stopped = True

            def close_after_site_confirmation(self, *_args, **_kwargs):
                self.closed = True

        class FakeController:
            last = None

            def __init__(self, transport, *_args, **_kwargs):
                self.transport = transport
                self.reach_state = "IDLE"
                self.task_state = "IDLE"
                self.waypoints_reached = 0
                self.failure = None
                self.confirmed_stage = None
                FakeController.last = self

            def start_stage(self, stage, goals, *, approved):
                self.stage = stage
                self.goals = goals
                self.approved = approved
                self.waypoints_reached = len(goals)
                self.reach_state = "GOAL_REACHED"
                self.task_state = "USER_CONFIRMATION_REQUIRED"

            def wait_worker(self, _timeout):
                return True

            def confirm_task_result(self, *, stage, human_observed, result):
                self.confirmed_stage = stage
                self.human_observed = human_observed
                self.result = result

            def request_stop(self):
                return None

            def verify_stop_completed(self, *, timeout_s):
                return timeout_s > 0

            def verify_arm_stopped(self, **_kwargs):
                return True

        answers = iter([
            "RUN C PRE APPROACH TO PICK READY",
            "PICK_READY CONFIRMED",
            "STOPPED",
        ])
        prompts = []

        def answer(prompt):
            prompts.append(prompt)
            return next(answers)

        transport = FakeTransport()
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "return.jsonl"
            output = io.StringIO()
            with patch("scripts.live_c_approach.ContinuousFollowingCycle",
                       FakeController), redirect_stdout(output):
                result = run(
                    plan_path, live=True,
                    confirm_scope=RETURN_TO_PICK_READY_SCOPE,
                    following_log_output=log, input_fn=answer,
                    transport_factory=lambda: transport)
        self.assertEqual(result, 0)
        self.assertEqual(FakeController.last.stage, "approach")
        self.assertEqual(FakeController.last.confirmed_stage,
                         "approach")
        self.assertTrue(transport.stopped)
        self.assertTrue(transport.closed)
        self.assertIn("Type PICK_READY CONFIRMED", prompts[1])
        self.assertIn("PICK_READY_REACHED waypoints=61", output.getvalue())
        self.assertIn("PICK_READY_RETURN_PASS", output.getvalue())
        self.assertNotIn("PRE_APPROACH_PASS", output.getvalue())

    def test_return_scope_requires_recorded_pick_ready_final_tolerances(self):
        plan_path = Path("configs/live_c_return_to_pick_ready_20261013.json")
        plan = load_plan(plan_path, expected_scope=RETURN_TO_PICK_READY_SCOPE)
        start = {**plan["staged_reference_start_arm_deg"], "gripper": 2.080783}
        final = {**plan["target_arm_deg"], "gripper": start["gripper"]}
        final["wrist_flex"] += 0.6

        class Feedback:
            def __init__(self, positions):
                self.positions = positions
                self.received_monotonic = time.monotonic()

        class FakeTransport:
            def __init__(self):
                self.feedback = [Feedback(start), Feedback(final)]
                self.stopped = False

            def read_feedback(self):
                return self.feedback.pop(0)

            def verify_start_pose(self, *_args, **_kwargs):
                return None

            def stop_commands(self):
                self.stopped = True

            def close_after_site_confirmation(self, *_args, **_kwargs):
                return None

        class FakeController:
            def __init__(self, _transport, tolerances, **_kwargs):
                self.tolerances = tolerances
                self.reach_state = "IDLE"
                self.task_state = "IDLE"
                self.waypoints_reached = 0
                self.failure = None

            def start_stage(self, _stage, goals, *, approved):
                self.waypoints_reached = len(goals)
                self.reach_state = "GOAL_REACHED"
                self.task_state = "USER_CONFIRMATION_REQUIRED"

            def wait_worker(self, _timeout):
                return True

            def request_stop(self):
                return None

            def verify_stop_completed(self, *, timeout_s):
                return timeout_s > 0

            def verify_arm_stopped(self, **_kwargs):
                return True

        answers = iter(["RUN C PRE APPROACH TO PICK READY", "STOPPED"])
        transport = FakeTransport()
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "return.jsonl"
            output = io.StringIO()
            errors = io.StringIO()
            with patch("scripts.live_c_approach.ContinuousFollowingCycle",
                       FakeController), redirect_stdout(output), redirect_stderr(errors):
                result = run(
                    plan_path, live=True,
                    confirm_scope=RETURN_TO_PICK_READY_SCOPE,
                    following_log_output=log, input_fn=lambda _prompt: next(answers),
                    transport_factory=lambda: transport)

        self.assertEqual(result, 1)
        self.assertTrue(transport.stopped)
        self.assertIn("final_fresh_feedback_outside_tolerance",
                      errors.getvalue())
        self.assertNotIn("PICK_READY_RETURN_PASS", output.getvalue())

    def test_current_to_c_contract_requires_exact_phrase_and_axis_tolerances(self):
        source = Path("configs/live_c_pre_approach_from_current_20261013.json")
        raw = json.loads(source.read_text())
        plan = load_plan(source)

        self.assertEqual(plan["scope"], PRE_APPROACH_SCOPE)
        self.assertEqual(plan["start_pose_name"], CURRENT_TO_C_START_POSE)
        self.assertEqual(plan["run_phrase"], "RUN CURRENT TO C PRE APPROACH")
        self.assertEqual(plan["start_pose_tolerance_deg"],
                         STRICT_POSE_TOLERANCES_DEG)
        self.assertEqual(plan["wrist_lead_phase"], WRIST_LEAD_PHASE_NAME)
        self.assertEqual(plan["wrist_lead_phase_waypoints"], 2)
        self.assertEqual(plan["wrist_lead_phase_gate"],
                         WRIST_LEAD_PHASE_GATE_POLICY)
        self.assertEqual(plan["wrist_lead_phase_target_arm_deg"],
                         plan["staged_intermediate_arm_deg"][0])
        self.assertEqual(plan["minimum_fresh_gripper_open_percent"], 35.0)
        self.assertEqual(final_tolerances_for_plan(plan), {
            **STRICT_POSE_TOLERANCES_DEG,
            "gripper": 2.0,
        })

        # Existing PICK_READY PRE_APPROACH keeps its historical terminal
        # policy; the stricter contract is local to attempt-2-current.
        historical = load_plan(Path(
            "configs/live_c_pre_approach_from_pick_ready_20261013.json"))
        self.assertEqual(final_tolerances_for_plan(historical), {
            name: (2.0 if name == "gripper" else 1.6)
            for name in JOINT_UNITS
        })

        for key, value in (
            ("run_phrase", "RUN PICK READY TO C PRE APPROACH"),
            ("start_pose_tolerance_deg", {
                **STRICT_POSE_TOLERANCES_DEG,
                "wrist_flex": 0.51,
            }),
        ):
            invalid = {**raw, key: value}
            with self.subTest(key=key), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "invalid-current-to-c.json"
                path.write_text(json.dumps(invalid))
                with self.assertRaisesRegex(
                        ValueError, "approach_start_contract_invalid"):
                    load_plan(path)

        for key, value in (
            ("wrist_lead_phase_waypoints", 3),
            ("minimum_fresh_gripper_open_percent", 34.9),
            ("wrist_lead_phase_gate", {
                **WRIST_LEAD_PHASE_GATE_POLICY,
                "target_tolerance_deg": 0.6,
            }),
        ):
            invalid = {**raw, key: value}
            with self.subTest(key=key), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "invalid-phase.json"
                path.write_text(json.dumps(invalid))
                with self.assertRaisesRegex(
                        ValueError, "wrist_lead_phase_contract_invalid"):
                    load_plan(path)

    def test_wrist_lead_phase_gate_uses_fresh_feedback_and_fk(self):
        plan = load_plan(Path(
            "configs/live_c_pre_approach_from_current_20261013.json"))
        start = {**plan["staged_reference_start_arm_deg"], "gripper": 35.0}
        goals = wrist_lead_phase_goals(start, plan)
        self.assertEqual(len(goals), 2)
        previous = start
        for goal in goals:
            self.assertAlmostEqual(
                goal["wrist_flex"] - previous["wrist_flex"], -1.0)
            self.assertTrue(all(goal[name] == previous[name]
                                for name in JOINT_UNITS
                                if name != "wrist_flex"))
            previous = goal

        zeros = {name: 0 for name in JOINT_UNITS}
        telemetry = FollowingTelemetry(
            positions=goals[-1],
            received_monotonic=time.monotonic(),
            goal_raw=zeros,
            present_raw=zeros,
            moving=zeros,
            present_load=zeros,
            temperature_c={name: 30 for name in JOINT_UNITS},
        )
        kinematics = load_verified_fk_kinematics(
            Path(".local/c-red-pivot-tcp-table-20261011-s01/so101_new_calib.urdf"),
            plan["urdf_sha256"],
        )
        report = verify_wrist_lead_phase_gate(
            telemetry,
            fresh_start=start,
            phase_target=goals[-1],
            gate_policy=plan["wrist_lead_phase_gate"],
            kinematics=kinematics,
            tcp_offset_mm=plan["tcp_offset_gripper_mm"],
        )
        self.assertTrue(report["pass"])
        self.assertGreater(report["grasp_tcp_delta_z_mm"], 0.0)
        self.assertAlmostEqual(report["achieved_delta_deg"], -2.0)

        moving = dict(zeros)
        moving["wrist_flex"] = 1
        unsettled = FollowingTelemetry(
            positions=goals[-1],
            received_monotonic=time.monotonic(),
            goal_raw=zeros,
            present_raw=zeros,
            moving=moving,
            present_load=zeros,
            temperature_c={name: 30 for name in JOINT_UNITS},
        )
        with self.assertRaisesRegex(RuntimeError,
                                    "wrist_lead_phase_not_settled"):
            verify_wrist_lead_phase_gate(
                unsettled,
                fresh_start=start,
                phase_target=goals[-1],
                gate_policy=plan["wrist_lead_phase_gate"],
                kinematics=kinematics,
                tcp_offset_mm=plan["tcp_offset_gripper_mm"],
            )

        drifted_positions = dict(goals[-1])
        drifted_positions["shoulder_pan"] += 1.01
        drifted = FollowingTelemetry(
            positions=drifted_positions,
            received_monotonic=time.monotonic(),
            goal_raw=zeros,
            present_raw=zeros,
            moving=zeros,
            present_load=zeros,
            temperature_c={name: 30 for name in JOINT_UNITS},
        )
        with self.assertRaisesRegex(RuntimeError,
                                    "non_commanded_drift_exceeded"):
            verify_wrist_lead_phase_gate(
                drifted,
                fresh_start=start,
                phase_target=goals[-1],
                gate_policy=plan["wrist_lead_phase_gate"],
                kinematics=kinematics,
                tcp_offset_mm=plan["tcp_offset_gripper_mm"],
            )

    def test_current_route_closed_gripper_blocks_before_any_send(self):
        plan_path = Path(
            "configs/live_c_pre_approach_from_current_20261013.json")
        plan = load_plan(plan_path)
        start = {**plan["staged_reference_start_arm_deg"], "gripper": 2.264382}

        class Feedback:
            def __init__(self, positions):
                self.positions = positions
                self.received_monotonic = time.monotonic()

        class Bus:
            def __init__(self):
                self.disconnected = False

            def disconnect(self, *, disable_torque):
                self.disconnected = not disable_torque

        class Lease:
            def __init__(self):
                self.released = False

            def release(self):
                self.released = True

        class NoSendTransport:
            def __init__(self):
                self.robot = type("Robot", (), {"bus": Bus()})()
                self.lease = Lease()
                self.sent = []
                self.stopped = False

            def read_feedback(self):
                return Feedback(start)

            def send_goal(self, goal):
                self.sent.append(goal)
                return goal

            def stop_commands(self):
                self.stopped = True

        transport = NoSendTransport()
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "closed-gripper.jsonl"
            errors = io.StringIO()
            with redirect_stderr(errors):
                result = run(
                    plan_path, live=True,
                    confirm_scope=PRE_APPROACH_SCOPE,
                    following_log_output=log,
                    fk_urdf_path=Path(
                        ".local/c-red-pivot-tcp-table-20261011-s01/"
                        "so101_new_calib.urdf"),
                    input_fn=lambda _prompt: "RUN CURRENT TO C PRE APPROACH",
                    transport_factory=lambda: transport,
                )
        self.assertEqual(result, 1)
        self.assertEqual(transport.sent, [])
        self.assertTrue(transport.stopped)
        self.assertTrue(transport.robot.bus.disconnected)
        self.assertTrue(transport.lease.released)
        self.assertIn("fresh_gripper_below_minimum_open", errors.getvalue())

    def test_current_route_gate_precedes_coupled_targets(self):
        plan_path = Path(
            "configs/live_c_pre_approach_from_current_20261013.json")
        plan = load_plan(plan_path)
        start = {**plan["staged_reference_start_arm_deg"], "gripper": 35.0}

        class Feedback:
            def __init__(self, positions):
                self.positions = dict(positions)
                self.received_monotonic = time.monotonic()

        class FakeTransport:
            def __init__(self):
                self.positions = dict(start)
                self.stopped = False
                self.closed = False

            def read_feedback(self):
                return Feedback(self.positions)

            def verify_start_pose(self, *_args, **_kwargs):
                return Feedback(self.positions)

            def stop_commands(self):
                self.stopped = True

            def close_after_site_confirmation(self, *_args, **_kwargs):
                self.closed = True

        class FakeController:
            instances = []
            moving_at_gate = 1

            def __init__(self, transport, *_args, **_kwargs):
                self.transport = transport
                self.reach_state = "IDLE"
                self.task_state = "IDLE"
                self.waypoints_reached = 0
                self.failure = None
                FakeController.instances.append(self)

            def start_stage(self, stage, goals, *, approved):
                self.stage = stage
                self.goals = goals
                self.approved = approved
                self.transport.positions = dict(goals[-1])
                self.waypoints_reached = len(goals)
                self.reach_state = "GOAL_REACHED"
                self.task_state = "USER_CONFIRMATION_REQUIRED"

            def wait_worker(self, _timeout):
                return True

            def _read_telemetry(self):
                zeros = {name: 0 for name in JOINT_UNITS}
                moving = dict(zeros)
                moving["wrist_flex"] = self.moving_at_gate
                return FollowingTelemetry(
                    positions=dict(self.transport.positions),
                    received_monotonic=time.monotonic(),
                    goal_raw=zeros,
                    present_raw=zeros,
                    moving=moving,
                    present_load=zeros,
                    temperature_c={name: 30 for name in JOINT_UNITS},
                )

            def _abort(self, **kwargs):
                self.aborted = kwargs
                self.failure = kwargs["reason"]
                return False

            def _emit(self, **kwargs):
                self.emitted = kwargs

            def confirm_task_result(self, *, stage, human_observed, result):
                self.confirmed = (stage, human_observed, result)

            def request_stop(self):
                return None

            def verify_stop_completed(self, *, timeout_s):
                return timeout_s > 0

            def verify_arm_stopped(self, **_kwargs):
                return True

        answers = iter(["RUN CURRENT TO C PRE APPROACH", "STOPPED"])
        transport = FakeTransport()
        FakeController.instances = []
        with tempfile.TemporaryDirectory() as directory:
            errors = io.StringIO()
            with patch("scripts.live_c_approach.ContinuousFollowingCycle",
                       FakeController), redirect_stderr(errors):
                result = run(
                    plan_path, live=True,
                    confirm_scope=PRE_APPROACH_SCOPE,
                    following_log_output=Path(directory) / "gate-fail.jsonl",
                    fk_urdf_path=Path(
                        ".local/c-red-pivot-tcp-table-20261011-s01/"
                        "so101_new_calib.urdf"),
                    input_fn=lambda _prompt: next(answers),
                    transport_factory=lambda: transport,
                )
        self.assertEqual(result, 1)
        self.assertEqual(len(FakeController.instances), 1)
        self.assertEqual(len(FakeController.instances[0].goals), 2)
        self.assertIn("wrist_lead_phase_gate_failed",
                      FakeController.instances[0].failure)
        self.assertTrue(transport.stopped)
        self.assertTrue(transport.closed)
        self.assertIn("wrist_lead_phase_not_settled", errors.getvalue())

        # With the same open start and a passing phase sample, the runner may
        # create the coupled controller only after the gate report is emitted.
        FakeController.instances = []
        FakeController.moving_at_gate = 0
        transport = FakeTransport()
        answers = iter([
            "RUN CURRENT TO C PRE APPROACH", "APPROACH CONFIRMED", "STOPPED",
        ])
        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            with patch("scripts.live_c_approach.ContinuousFollowingCycle",
                       FakeController), redirect_stdout(output):
                result = run(
                    plan_path, live=True,
                    confirm_scope=PRE_APPROACH_SCOPE,
                    following_log_output=Path(directory) / "gate-pass.jsonl",
                    fk_urdf_path=Path(
                        ".local/c-red-pivot-tcp-table-20261011-s01/"
                        "so101_new_calib.urdf"),
                    input_fn=lambda _prompt: next(answers),
                    transport_factory=lambda: transport,
                )
        self.assertEqual(result, 0)
        self.assertEqual(len(FakeController.instances), 2)
        self.assertEqual(len(FakeController.instances[0].goals), 2)
        self.assertGreater(len(FakeController.instances[1].goals), 0)
        self.assertIn("WRIST_LEAD_PHASE_GATE_PASS", output.getvalue())
        self.assertIn("PRE_APPROACH_PASS", output.getvalue())

    def test_current_to_c_scope_runs_real_continuous_stage_contract(self):
        start = {name: 0.0 for name in JOINT_UNITS}
        goal = {
            **{name: 0.25 for name in ARM_NAMES},
            "gripper": start["gripper"],
        }

        class ImmediateFollowingTransport:
            def __init__(self):
                self.positions = dict(start)
                self.stopped = False

            def send_goal(self, requested):
                self.positions = dict(requested)
                return dict(requested)

            def read_following_telemetry(self):
                zeros = {name: 0 for name in JOINT_UNITS}
                return FollowingTelemetry(
                    positions=dict(self.positions),
                    received_monotonic=time.monotonic(),
                    goal_raw=zeros,
                    present_raw=zeros,
                    moving=zeros,
                    present_load=zeros,
                    temperature_c={name: 30 for name in JOINT_UNITS},
                )

            def stop_commands(self):
                self.stopped = True

            def is_quiescent(self):
                return self.stopped

        transport = ImmediateFollowingTransport()
        controller = ContinuousFollowingCycle(
            transport,
            {**STRICT_POSE_TOLERANCES_DEG, "gripper": 2.0},
            planned_start=start,
            following_limits={name: 2.5 for name in ARM_NAMES},
            max_joint_step_deg=1.0,
            cadence_s=0.001,
            no_progress_timeout_s=0.1,
            progress_epsilon_deg=0.1,
            final_timeout_s=0.2,
            feedback_max_age_s=0.5,
            stable_s=0.0,
            poll_s=0.001,
        )
        contract = SCOPE_CONTRACTS[PRE_APPROACH_SCOPE]
        controller.start_stage(contract["stage"], [goal], approved=True)
        self.assertTrue(controller.wait_worker(0.5))
        self.assertEqual(controller.stage, STAGES[0])
        self.assertEqual(controller.reach_state, "GOAL_REACHED")
        self.assertEqual(controller.task_state, "USER_CONFIRMATION_REQUIRED")
        controller.confirm_task_result(
            stage=contract["stage"], human_observed=True, result=True)
        controller.request_stop()
        self.assertTrue(controller.verify_stop_completed(timeout_s=0.1))

    def test_pre_approach_completion_contract_is_unchanged(self):
        contract = SCOPE_CONTRACTS[PRE_APPROACH_SCOPE]
        self.assertEqual(contract["stage"], "approach")
        self.assertEqual(contract["reached_marker"], "APPROACH_REACHED")
        self.assertEqual(contract["completion_phrase"], "APPROACH CONFIRMED")
        self.assertEqual(contract["pass_marker"], "PRE_APPROACH_PASS")

    def test_one_shot_scope_contracts_use_existing_first_controller_stage(self):
        for contract in SCOPE_CONTRACTS.values():
            self.assertEqual(contract["stage"], STAGES[0])

    def test_rejects_unknown_live_approval_phrase(self):
        source = Path("configs/live_c_pre_approach_from_safe_high_20261012.json")
        raw = json.loads(source.read_text())
        raw["run_phrase"] = "RUN SOMETHING ELSE"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plan.json"
            path.write_text(json.dumps(raw))
            with self.assertRaisesRegex(ValueError, "approach_start_contract_invalid"):
                load_plan(path)

    def test_rejects_home_tolerance_above_existing_limit(self):
        source = Path("configs/live_c_pre_approach_from_home_20261012.json")
        raw = json.loads(source.read_text())
        raw["start_pose_tolerance_deg"]["elbow_flex"] = 1.51
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plan.json"
            path.write_text(json.dumps(raw))
            with self.assertRaisesRegex(ValueError, "approach_start_contract_invalid"):
                load_plan(path)

    def test_rejects_phrase_for_the_wrong_start_pose(self):
        source = Path("configs/live_c_pre_approach_from_home_20261012.json")
        raw = json.loads(source.read_text())
        raw["run_phrase"] = "RUN SAFE HIGH TO C PRE APPROACH"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plan.json"
            path.write_text(json.dumps(raw))
            with self.assertRaisesRegex(ValueError, "approach_start_contract_invalid"):
                load_plan(path)

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
