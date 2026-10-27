import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from medicine_sorter.config import load_config
from medicine_sorter.errors import SorterError
from medicine_sorter.fixed_demo import (
    ALL_POSE_NAMES, FINISH_POSE_NAME, GRIPPER_POSES, JOINTS, POSE_NAMES,
    POST_GOAL_READ_RETRIES,
    PRESTART_MAX_TEMPERATURE_C_EXCLUSIVE, SegmentSafetyFault,
    TEACH_GOAL_PRESENT_RAW_TOLERANCE, TYPE_GRIPPER_POSES,
    WARM_START_MAX_TEMPERATURE_C_EXCLUSIVE,
    SMOOTH_FEEDBACK_PERIOD_S, SMOOTH_SAFETY_PERIOD_S,
    StrictWriteGate,
    analyze_motion_rows, clamp_to_calibrated_inner_range,
    calibrated_bounds,
    compare_actual_motion_logs, compare_pose_motion,
    establish_hold, load_demo_settings,
    execute_segment, load_partial_pose_file, load_pose_records, parse_destination_rules,
    routes_from_snapshot,
    resolve_robot_ports, roi_preview_annotations, run_demo,
    run_free_space_motion_test, save_pose_file,
    save_roi_preview, slot_for_pixel, smooth_interpolation, stage_names_for_routes,
    target_for_stage, teach, validate_demo_settings, _read_temperatures,
    _execute_time_based_commands,
    verify_expected_marker_layout, verify_prestart_temperatures,
)


ROOT = Path(__file__).resolve().parents[1]


def snapshot(*, centers=None, age=0.1):
    return {
        "ok": True,
        "sequence": 42,
        "frame_age_s": age,
        "detections": [],
        "table": {
            "coordinate_space": "undistorted_full_frame",
            "source_frame_size_px": [640, 480],
            "detected_marker_centers_px": centers or {
                "7": [450.0, 220.0],
                "8": [380.0, 220.0],
                "9": [300.0, 220.0],
            },
        },
    }


class FakeBus:
    def __init__(self):
        self.registers = {
            "Present_Position": {joint: 2000 + index for index, joint in enumerate(JOINTS)},
            "Goal_Position": {joint: 1900 for joint in JOINTS},
            "Torque_Enable": {joint: 0 for joint in JOINTS},
            "Moving": {joint: 0 for joint in JOINTS},
        }
        self.sent = []
        self.reads = []

    def sync_read(self, register, *, normalize, num_retry):
        self.reads.append((register, normalize, num_retry))
        return dict(self.registers[register])

    def read(self, register, joint, *, normalize, num_retry):
        if register == "Present_Temperature":
            return 30
        raise AssertionError(register)

    def sync_write(self, register, values, *, normalize, num_retry):
        self.sent.append((register, dict(values), normalize, num_retry))
        self.registers[register] = dict(values)

    def write(self, *_args, **_kwargs):
        raise AssertionError("unwrapped write")

    def enable_torque(self, *_args, **_kwargs):
        raise AssertionError("unwrapped torque")

    def disable_torque(self, *_args, **_kwargs):
        raise AssertionError("unwrapped torque")


class Clock:
    def __init__(self):
        self.value = 0.0

    def monotonic(self):
        return self.value

    def sleep(self, seconds):
        self.value += seconds


class FixedDemoTests(unittest.TestCase):
    def setUp(self):
        self.config = load_config(ROOT / "configs/system.example.json")
        self.settings = load_demo_settings(self.config)

    def test_fixed_marker_and_destination_contract(self):
        self.assertEqual(self.settings.marker_to_type, {7: "C", 8: "B", 9: "A"})
        self.assertEqual(self.settings.destinations, {"C": "red", "B": "blue"})
        self.assertEqual(len(POSE_NAMES), 18)
        self.assertEqual(len(ALL_POSE_NAMES), 22)
        self.assertEqual(FINISH_POSE_NAME, "finish")
        self.assertEqual(set(TYPE_GRIPPER_POSES), {
            "gripper_closed_A", "gripper_closed_B", "gripper_closed_C"})
        self.assertIn("green_above", POSE_NAMES)
        self.assertIn("green_release", POSE_NAMES)
        self.assertEqual(self.settings.roi_status, "verified")
        self.assertEqual(self.settings.expected_bottle_slots,
                         {"A": "slot1", "B": "slot2", "C": "slot3"})

    def test_calibrated_bounds_uses_loaded_calibration_without_live_limit_reads(self):
        class CalibrationOnlyBus:
            def __init__(self):
                self.motors = {
                    joint: SimpleNamespace(id=index + 1)
                    for index, joint in enumerate(JOINTS)
                }
                self.calibration = {
                    joint: SimpleNamespace(range_min=100, range_max=3900)
                    for joint in JOINTS
                }
                self.live_limit_reads = 0

            @property
            def is_calibrated(self):
                self.live_limit_reads += 1
                raise AssertionError("is_calibrated performs forbidden live limit reads")

            def _normalize(self, values):
                return {motor_id: (raw - 2000) / 10.0
                        for motor_id, raw in values.items()}

        bus = CalibrationOnlyBus()
        bounds = calibrated_bounds(SimpleNamespace(bus=bus))
        self.assertEqual(bus.live_limit_reads, 0)
        self.assertEqual(set(bounds), set(JOINTS))
        self.assertTrue(all(value == (-190.0, 190.0) for value in bounds.values()))

    def test_calibrated_bounds_fails_closed_on_incomplete_loaded_calibration(self):
        bus = SimpleNamespace(
            motors={joint: SimpleNamespace(id=index + 1)
                    for index, joint in enumerate(JOINTS)},
            calibration={joint: SimpleNamespace(range_min=100, range_max=3900)
                         for joint in JOINTS if joint != "elbow_flex"},
            _normalize=lambda values: values,
        )
        with self.assertRaisesRegex(RuntimeError, "stored_calibration_not_loaded"):
            calibrated_bounds(SimpleNamespace(bus=bus))

    def test_verified_three_bottle_layout_passes_and_mismatch_reports_reason(self):
        layout = verify_expected_marker_layout(snapshot(), self.settings)
        self.assertEqual(layout["status"], "PASS")
        self.assertEqual(layout["observed"]["A"]["slot"], "slot1")
        wrong = snapshot()
        wrong["table"]["detected_marker_centers_px"]["9"] = [450.0, 220.0]
        with self.assertRaises(SorterError) as caught:
            verify_expected_marker_layout(wrong, self.settings)
        self.assertEqual(caught.exception.code, "expected_marker_layout_mismatch")
        self.assertEqual(caught.exception.observed["failures"][0]["bottle_type"], "A")

    def test_pixel_slots(self):
        self.assertEqual(slot_for_pixel((300, 220), self.settings.slots), "slot1")
        self.assertEqual(slot_for_pixel((380, 220), self.settings.slots), "slot2")
        self.assertEqual(slot_for_pixel((450, 220), self.settings.slots), "slot3")

    def test_outside_or_boundary_gap_fails(self):
        with self.assertRaisesRegex(ValueError, "not_in_exactly_one"):
            slot_for_pixel((100, 100), self.settings.slots)

    def test_default_routes_C_red_B_blue_and_A_is_unselected(self):
        routes, ignored = routes_from_snapshot(snapshot(), self.settings)
        self.assertEqual([(item.bottle_type, item.destination) for item in routes],
                         [("B", "blue"), ("C", "red")])
        self.assertEqual(ignored[0]["bottle_type"], "A")
        self.assertEqual(ignored[0]["reason"], "not_selected_by_rule")

    def test_all_nine_bottle_destination_pairs_parse(self):
        for label in ("A", "B", "C"):
            for color in ("red", "blue", "green"):
                self.assertEqual(parse_destination_rules([f"{label}={color}"], {}),
                                 {label: color})

    def test_config_defaults_accept_any_valid_subset_not_only_C_red_B_blue(self):
        for rules in ({"A": "green"}, {"A": "red", "B": "red", "C": "red"}, {}):
            validate_demo_settings(replace(self.settings, destinations=rules))

    def test_same_basket_for_multiple_bottles_is_allowed(self):
        rules = parse_destination_rules(["A=green", "B=green", "C=green"], {})
        routes, ignored = routes_from_snapshot(snapshot(), self.settings, rules)
        self.assertEqual([route.destination for route in routes], ["green"] * 3)
        self.assertEqual(ignored, [])

    def test_A_marker_runs_when_rule_is_present_and_unspecified_are_skipped(self):
        rules = parse_destination_rules(["A=blue"], self.settings.destinations)
        routes, ignored = routes_from_snapshot(snapshot(), self.settings, rules)
        self.assertEqual([(route.marker_id, route.bottle_type, route.destination)
                          for route in routes], [(9, "A", "blue")])
        self.assertEqual({item["bottle_type"] for item in ignored}, {"B", "C"})

    def test_invalid_runtime_rules_fail(self):
        invalid = (["C-green"], ["D=red"], ["C=yellow"], ["C=red", "C=blue"])
        for tokens in invalid:
            with self.subTest(tokens=tokens), self.assertRaises(Exception):
                parse_destination_rules(tokens, self.settings.destinations)

    def test_stale_frame_fails(self):
        with self.assertRaisesRegex(Exception, "camera_frame_stale"):
            routes_from_snapshot(snapshot(age=2.0), self.settings)

    def test_wrong_coordinate_space_fails(self):
        data = snapshot()
        data["table"]["coordinate_space"] = "raw_frame"
        with self.assertRaisesRegex(Exception, "pixel_coordinate_space_mismatch"):
            routes_from_snapshot(data, self.settings)

    def test_roi_preview_marks_each_center_with_slot_or_outside(self):
        data = snapshot(centers={"0": [40, 40], "7": [300, 220], "8": [600, 400]})
        annotations = roi_preview_annotations(data, self.settings)
        self.assertEqual(annotations["frame_sequence"], 42)
        markers = {item["marker_id"]: item for item in annotations["markers"]}
        self.assertEqual(markers[7]["bottle_type"], "C")
        self.assertEqual(markers[7]["slot"], "slot1")
        self.assertEqual(markers[8]["bottle_type"], "B")
        self.assertEqual(markers[8]["slot"], "OUTSIDE")
        self.assertEqual(markers[0]["bottle_type"], None)

    def test_roi_preview_saves_exact_bundle_without_hardware(self):
        calls = []

        def renderer(jpeg, annotations, output):
            calls.append((jpeg, annotations["frame_sequence"], output))
            output.write_bytes(b"fake-png")

        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "roi.png"
            result = save_roi_preview(
                self.settings, output,
                bundle_loader=lambda url: (snapshot(), b"exact-frame-jpeg"),
                renderer=renderer)
            self.assertEqual(calls, [(b"exact-frame-jpeg", 42, output)])
            self.assertEqual(output.read_bytes(), b"fake-png")
            self.assertEqual(result["status"], "ROI_PREVIEW_SAVED")
            self.assertEqual(result["serial_open"], 0)
            self.assertEqual(result["motor_command"], 0)

    def test_roi_preview_rejects_non_png_before_camera_fetch(self):
        called = False

        def loader(_url):
            nonlocal called
            called = True
            raise AssertionError("must not fetch")

        with self.assertRaisesRegex(Exception, "output_must_be_png"):
            save_roi_preview(self.settings, Path("/tmp/roi.jpg"), bundle_loader=loader)
        self.assertFalse(called)

    def test_stage_order_has_grasp_close_lift_release_open_home(self):
        routes, _ = routes_from_snapshot(snapshot(centers={"7": [300, 220]}), self.settings)
        stages = stage_names_for_routes(routes)
        self.assertEqual(stages, [
            "home", "gripper_open", "slot1_pre", "slot1_grasp",
            "gripper_closed_C", "slot1_lift", "red_above", "red_release",
            "gripper_open", "red_above", "home", "finish",
        ])

    def test_green_stage_uses_taught_green_poses(self):
        routes, _ = routes_from_snapshot(
            snapshot(centers={"7": [300, 220]}), self.settings, {"C": "green"})
        stages = stage_names_for_routes(routes)
        self.assertIn("green_above", stages)
        self.assertIn("green_release", stages)

    def test_each_bottle_repeats_home_open_pick_place_home_sequence(self):
        routes, _ = routes_from_snapshot(
            snapshot(), self.settings, {"A": "green", "B": "red", "C": "blue"})
        stages = stage_names_for_routes(routes)
        self.assertEqual(len(stages), 34)
        for index, route in enumerate(routes):
            chunk = stages[index * 11:(index + 1) * 11]
            self.assertEqual(chunk, [
                "home", "gripper_open", f"{route.slot}_pre", f"{route.slot}_grasp",
                f"gripper_closed_{route.bottle_type}", f"{route.slot}_lift", f"{route.destination}_above",
                f"{route.destination}_release", "gripper_open",
                f"{route.destination}_above", "home",
            ])
        self.assertEqual(stages[-1], "finish")
        self.assertEqual(stages.count("finish"), 1)

    def test_only_explicit_gripper_stages_change_gripper(self):
        current = {joint: 10.0 + index for index, joint in enumerate(JOINTS)}
        poses = {}
        for index, name in enumerate(ALL_POSE_NAMES):
            poses[name] = {joint: 100.0 + index * 10 + joint_index
                           for joint_index, joint in enumerate(JOINTS)}
        poses["gripper_open"]["gripper"] = 90.0
        poses["gripper_closed_A"]["gripper"] = 30.0
        poses["gripper_closed_B"]["gripper"] = 20.0
        poses["gripper_closed_C"]["gripper"] = 10.0
        routes, _ = routes_from_snapshot(
            snapshot(), self.settings, {"A": "green", "B": "red", "C": "blue"})
        for stage in stage_names_for_routes(routes):
            previous_gripper = current["gripper"]
            target = target_for_stage(stage, current, poses[stage])
            if stage == "gripper_open":
                self.assertEqual(target["gripper"], 90.0)
            elif stage in TYPE_GRIPPER_POSES:
                expected = {"gripper_closed_A": 30.0,
                            "gripper_closed_B": 20.0,
                            "gripper_closed_C": 10.0}[stage]
                self.assertEqual(target["gripper"], expected)
            else:
                self.assertEqual(target["gripper"], previous_gripper)
                self.assertEqual({joint: target[joint] for joint in JOINTS[:-1]},
                                 {joint: poses[stage][joint] for joint in JOINTS[:-1]})
            current = target
        self.assertEqual(GRIPPER_POSES, {
            "gripper_open", "gripper_closed", *TYPE_GRIPPER_POSES})

    def test_usb_serials_select_roles_independent_of_acm_number(self):
        serials = {
            Path("/dev/ttyACM0"): "LEADER",
            Path("/dev/ttyACM1"): "OTHER",
            Path("/dev/ttyACM2"): "FOLLOWER",
        }
        follower, leader = resolve_robot_ports(
            "FOLLOWER", "LEADER", candidates=tuple(reversed(serials)),
            serial_reader=serials.__getitem__)
        self.assertEqual(follower, Path("/dev/ttyACM2"))
        self.assertEqual(leader, Path("/dev/ttyACM0"))

    def test_usb_role_resolution_fails_before_connect_on_missing_or_collision(self):
        serials = {Path("/dev/ttyACM0"): "FOLLOWER"}
        with self.assertRaisesRegex(RuntimeError, "leader_usb_serial_not_found"):
            resolve_robot_ports("FOLLOWER", "LEADER", candidates=tuple(serials),
                                serial_reader=serials.__getitem__)
        with self.assertRaisesRegex(RuntimeError, "serial_identity_collision"):
            resolve_robot_ports("SAME", "SAME", candidates=tuple(serials),
                                serial_reader=serials.__getitem__)

    def test_duplicate_usb_serial_is_rejected(self):
        serials = {
            Path("/dev/ttyACM0"): "FOLLOWER",
            Path("/dev/ttyACM1"): "FOLLOWER",
            Path("/dev/ttyACM2"): "LEADER",
        }
        with self.assertRaisesRegex(RuntimeError, "follower_usb_serial_ambiguous"):
            resolve_robot_ports("FOLLOWER", "LEADER", candidates=tuple(serials),
                                serial_reader=serials.__getitem__)

    def test_interpolation_preserves_common_fraction_and_two_degree_limit(self):
        start = {joint: 0.0 for joint in JOINTS}
        target = {joint: float(index * 10) for index, joint in enumerate(JOINTS, start=1)}
        points = smooth_interpolation(start, target, self.settings)
        previous = start
        for point in points:
            fractions = [(point[j] - start[j]) / (target[j] - start[j]) for j in JOINTS]
            self.assertLess(max(fractions) - min(fractions), 1e-9)
            for joint in JOINTS:
                limit = 2.0
                self.assertLessEqual(abs(point[joint] - previous[joint]), limit + 1e-9)
            previous = point
        self.assertEqual(points[-1], target)

    def test_interpolation_velocity_limit(self):
        start = {joint: 0.0 for joint in JOINTS}
        target = {joint: 10.0 for joint in JOINTS}
        points = smooth_interpolation(start, target, self.settings)
        previous = start
        for point in points:
            for joint in JOINTS:
                speed = abs(point[joint] - previous[joint]) / self.settings.control_period_s
                self.assertLessEqual(speed, self.settings.velocity[joint] + 1e-6)
            previous = point

    def test_segment_travel_limit_fails(self):
        start = {joint: 0.0 for joint in JOINTS}
        target = dict(start)
        target["shoulder_pan"] = 101.0
        with self.assertRaisesRegex(ValueError, "segment_travel_limit_exceeded"):
            smooth_interpolation(start, target, self.settings)

    def test_atomic_hold_exact_copy_then_torque_once(self):
        bus = FakeBus()
        gate = StrictWriteGate(bus)
        clock = Clock()
        result = establish_hold(bus, gate, sleep=clock.sleep, monotonic=clock.monotonic)
        self.assertEqual(result["hold"], "RESTORED_FROM_OFF")
        self.assertEqual(gate.counts["Goal_Position_raw_hold"], 1)
        self.assertEqual(gate.counts["Torque_Enable"], 1)
        self.assertEqual(bus.sent[0][1], bus.registers["Present_Position"])
        self.assertEqual(bus.sent[1][0], "Torque_Enable")
        self.assertIn(("Goal_Position", False, POST_GOAL_READ_RETRIES), bus.reads)
        self.assertIn(("Torque_Enable", False, POST_GOAL_READ_RETRIES), bus.reads)

    def test_goal_write_auto_enables_torque_without_second_torque_write(self):
        class AutoEnableBus(FakeBus):
            def sync_write(self, register, values, *, normalize, num_retry):
                super().sync_write(register, values, normalize=normalize, num_retry=num_retry)
                if register == "Goal_Position" and normalize is False:
                    self.registers["Torque_Enable"] = {joint: 1 for joint in JOINTS}

        bus = AutoEnableBus()
        gate = StrictWriteGate(bus)
        clock = Clock()
        result = establish_hold(bus, gate, sleep=clock.sleep, monotonic=clock.monotonic)
        self.assertEqual(result["hold"], "AUTO_ENABLED_BY_GOAL")
        self.assertEqual(gate.counts["Goal_Position_raw_hold"], 1)
        self.assertEqual(gate.counts["Torque_Enable"], 0)
        self.assertEqual([register for register, *_rest in bus.sent], ["Goal_Position"])

    def test_unarmed_write_is_blocked(self):
        bus = FakeBus()
        gate = StrictWriteGate(bus)
        with self.assertRaisesRegex(RuntimeError, "unarmed"):
            bus.sync_write("Goal_Position", {joint: 1 for joint in JOINTS},
                           normalize=False, num_retry=0)
        self.assertEqual(gate.counts["forbidden"], 1)

    def test_ctrl_c_hold_is_one_raw_goal_copy_without_torque_toggle(self):
        bus = FakeBus()
        gate = StrictWriteGate(bus)
        clock = Clock()
        establish_hold(bus, gate, sleep=clock.sleep, monotonic=clock.monotonic)
        fresh = dict(bus.registers["Present_Position"])
        gate.ctrl_c_hold(fresh)
        self.assertEqual(bus.sent[-1], ("Goal_Position", fresh, False, 0))
        self.assertEqual(gate.counts["Goal_Position_ctrl_c_hold"], 1)
        self.assertEqual(gate.counts["Torque_Enable"], 1)
        with self.assertRaisesRegex(RuntimeError, "ctrl_c_hold_not_allowed"):
            gate.ctrl_c_hold(fresh)

    def test_already_on_does_not_toggle(self):
        bus = FakeBus()
        bus.registers["Goal_Position"] = dict(bus.registers["Present_Position"])
        bus.registers["Torque_Enable"] = {joint: 1 for joint in JOINTS}
        gate = StrictWriteGate(bus)
        clock = Clock()
        result = establish_hold(bus, gate, sleep=clock.sleep, monotonic=clock.monotonic)
        self.assertEqual(result["hold"], "ALREADY_ON_NO_TOGGLE")
        self.assertEqual(bus.sent, [])

    def test_supervised_hold_can_accept_stable_gap_without_any_write(self):
        bus = FakeBus()
        bus.registers["Goal_Position"] = dict(bus.registers["Present_Position"])
        bus.registers["Goal_Position"]["wrist_flex"] -= 14
        bus.registers["Torque_Enable"] = {joint: 1 for joint in JOINTS}
        gate = StrictWriteGate(bus)
        clock = Clock()
        with self.assertRaisesRegex(RuntimeError, "already_on_goal_present_gap"):
            establish_hold(bus, gate, sleep=clock.sleep, monotonic=clock.monotonic)
        self.assertEqual(bus.sent, [])

        clock = Clock()
        result = establish_hold(
            bus, gate, max_existing_goal_present_gap_raw=40,
            sleep=clock.sleep, monotonic=clock.monotonic)
        self.assertEqual(result["hold"], "ALREADY_ON_NO_TOGGLE")
        self.assertEqual(result["max_existing_goal_present_gap_raw"], 40)
        self.assertEqual(bus.sent, [])

    def test_supervised_hold_accepts_sixty_but_rejects_more(self):
        bus = FakeBus()
        bus.registers["Goal_Position"] = dict(bus.registers["Present_Position"])
        bus.registers["Goal_Position"]["elbow_flex"] -= 60
        bus.registers["Torque_Enable"] = {joint: 1 for joint in JOINTS}
        gate = StrictWriteGate(bus)
        clock = Clock()
        result = establish_hold(
            bus, gate, max_existing_goal_present_gap_raw=60,
            sleep=clock.sleep, monotonic=clock.monotonic)
        self.assertEqual(result["max_existing_goal_present_gap_raw"], 60)
        self.assertEqual(bus.sent, [])
        with self.assertRaisesRegex(
                ValueError, "invalid_existing_goal_present_gap_tolerance"):
            establish_hold(bus, gate, max_existing_goal_present_gap_raw=61)
        self.assertEqual(bus.sent, [])

    def test_mixed_torque_fails_without_write(self):
        bus = FakeBus()
        bus.registers["Torque_Enable"]["gripper"] = 1
        gate = StrictWriteGate(bus)
        with self.assertRaisesRegex(RuntimeError, "mixed_torque_state"):
            establish_hold(bus, gate)
        self.assertEqual(bus.sent, [])

    def test_calibrated_target_clamps_one_degree_inside(self):
        bounds = {joint: (-10.0, 10.0) for joint in JOINTS}
        values = {joint: 0.0 for joint in JOINTS}
        values["wrist_flex"] = 107.0
        accepted, clamped = clamp_to_calibrated_inner_range(values, bounds)
        self.assertEqual(accepted["wrist_flex"], 9.0)
        self.assertEqual(clamped["wrist_flex"], (107.0, 9.0))

    def test_jetson_motion_and_teach_limits_are_reflected(self):
        self.assertEqual(self.settings.control_period_s, 0.05)
        self.assertEqual(set(self.settings.velocity.values()), {20.0})
        self.assertEqual(set(self.settings.acceleration.values()), {60.0})
        self.assertEqual(self.settings.settle_tolerance["gripper"], 100.0)
        self.assertEqual({self.settings.settle_tolerance[joint] for joint in JOINTS[:-1]}, {5.0})
        self.assertEqual(self.settings.settle_timeout_s, 8.0)
        self.assertEqual(TEACH_GOAL_PRESENT_RAW_TOLERANCE, 40)

    def test_offline_motion_comparison_preserves_endpoints_and_two_degree_cap(self):
        start = {joint: 0.0 for joint in JOINTS}
        target = {
            "shoulder_pan": 40.0, "shoulder_lift": 20.0,
            "elbow_flex": -15.0, "wrist_flex": 10.0,
            "wrist_roll": -5.0, "gripper": 80.0,
        }
        present_raw = {joint: 2000 for joint in JOINTS}
        poses = {
            name: {"position": dict(start), "present_raw": dict(present_raw)}
            for name in ALL_POSE_NAMES
        }
        poses["slot1_pre"] = {"position": target, "present_raw": dict(present_raw)}
        with tempfile.TemporaryDirectory() as folder:
            pose_path = Path(folder) / "poses.json"
            save_pose_file(pose_path, follower_serial="5AE6058306", poses=poses)
            result = compare_pose_motion(
                self.config, replace(self.settings, pose_path=pose_path),
                from_pose="home", to_pose="slot1_pre")
        self.assertEqual(result["status"], "MOTION_A_B_OFFLINE")
        self.assertTrue(result["same_start_end_pose"])
        self.assertEqual(result["actual_log_analysis"], "NOT_AVAILABLE")
        self.assertEqual(result["serial_open"], 0)
        self.assertEqual(result["motor_command"], 0)
        self.assertFalse(result["two_degree_cap_removed"])
        self.assertEqual(result["TORQUE_GAIN_CHANGED"], "NO")
        self.assertEqual(result["IK_CHANGED"], "NO")
        self.assertEqual(result["READY_FOR_SMOOTH_MOTION_TEST"],
                         "NO_NEEDS_FREE_SPACE_START_END_CONFIRMATION")
        self.assertGreater(result["smooth"]["command_count"],
                           result["original"]["command_count"])
        for profile in ("original", "smooth", "quintic"):
            for joint in JOINTS:
                self.assertLessEqual(
                    result[profile]["joints"][joint]["max_delta"], 2.0 + 1e-9)
                self.assertEqual(
                    result[profile]["joints"][joint]["direction_reversals"], 0)
        self.assertGreater(result["quintic"]["command_count"], 0)
        self.assertLessEqual(result["QUINTIC_MAX_STEP"], 2.0 + 1e-9)

    def test_actual_motion_log_analysis_reports_cadence_steps_and_oscillation(self):
        rows = []
        commands = [0.0, 1.0, 0.0]
        presents = [0.0, 0.5, 0.25]
        goals = [0.0, 1.0, 0.0]
        for index in range(3):
            command = {joint: commands[index] for joint in JOINTS}
            present = {joint: presents[index] for joint in JOINTS}
            goal = {joint: goals[index] for joint in JOINTS}
            rows.append({
                "planned_monotonic_ns": index * 50_000_000,
                "command_monotonic_ns": index * 50_000_000,
                "command_position": command,
                "present_position": present,
                "goal_present_error": {
                    joint: goal[joint] - present[joint] for joint in JOINTS},
                "moving": {joint: int(index == 1) for joint in JOINTS},
            })
        result = analyze_motion_rows(rows)
        self.assertAlmostEqual(result["command_interval_mean_s"], 0.05)
        self.assertAlmostEqual(result["command_interval_std_s"], 0.0)
        self.assertAlmostEqual(result["command_interval_max_s"], 0.05)
        self.assertEqual(result["deadline_miss_count"], 0)
        self.assertFalse(result["raw_feedback_available"])
        self.assertEqual(result["torque_enable_cycles"], "NOT_RECORDED")
        pan = result["joints"]["shoulder_pan"]
        self.assertEqual(pan["emitted_delta_per_cycle"], [1.0, -1.0])
        self.assertEqual(pan["max_delta"], 1.0)
        self.assertEqual(pan["direction_reversals"], 1)
        self.assertEqual(pan["present_velocity_direction_reversals"], 1)
        self.assertEqual(pan["moving_true_cycles"], 1)
        self.assertGreater(pan["goal_present_error_peak_to_peak"], 0.0)
        self.assertEqual(pan["goal_present_error_max_abs"], 0.5)

    def test_original_from_current_uses_fresh_start_and_point_one_second_baseline(self):
        current = {joint: float(index) for index, joint in enumerate(JOINTS)}
        finish = dict(current)
        finish["wrist_flex"] += 3.0
        present_raw = {joint: 2000 + index for index, joint in enumerate(JOINTS)}
        poses = {
            name: {"position": dict(current), "present_raw": dict(present_raw)}
            for name in ALL_POSE_NAMES
        }
        poses["finish"] = {"position": finish, "present_raw": dict(present_raw)}
        captured = {}

        class Session:
            def __init__(self, *_args, **_kwargs):
                bus = FakeBus()
                bus.registers["Present_Position"] = dict(current)
                bus.registers["Moving"] = {joint: 0 for joint in JOINTS}
                self.follower = SimpleNamespace(bus=bus)
                self.writes = SimpleNamespace(counts={"Goal_Position_motion": 0})

            def connect(self):
                return None

            def ctrl_c_hold(self):
                return True

            def close(self):
                return None

        class Recorder:
            def __init__(self, _path):
                self.count = 3

            def close(self):
                return None

        def fake_execute(_session, target, settings, **kwargs):
            captured["target"] = dict(target)
            captured["period"] = settings.control_period_s
            captured["profile"] = kwargs["motion_profile"]
            return {"temperatures_c": {joint: 30 for joint in JOINTS}}

        with tempfile.TemporaryDirectory() as folder:
            pose_path = Path(folder) / "poses.json"
            save_pose_file(pose_path, follower_serial="5AE6058306", poses=poses)
            settings = replace(self.settings, pose_path=pose_path)
            with (patch("medicine_sorter.fixed_demo.MotionTraceRecorder", Recorder),
                  patch("medicine_sorter.fixed_demo.verify_prestart_temperatures",
                        return_value={joint: 30 for joint in JOINTS}),
                  patch("medicine_sorter.fixed_demo.establish_hold",
                        return_value={"hold": "TEST"}),
                  patch("medicine_sorter.fixed_demo.execute_segment", fake_execute),
                  patch("medicine_sorter.fixed_demo.load_and_analyze_motion_log",
                        return_value={"sample_count": 3}),
                  patch("builtins.input", return_value="")):
                result = run_free_space_motion_test(
                    self.config, settings, from_pose=None, from_current=True,
                    to_pose="finish", motion_profile="original",
                    log_path=Path(folder) / "ignored.jsonl", step=True,
                    session_factory=Session, install_signal_handlers=False)
        self.assertEqual(result["from_pose"], "CURRENT")
        self.assertEqual(result["status"],
                         "FREE_SPACE_MOTION_TEST_EXTERNAL_CONFIRMATION_REQUIRED")
        self.assertFalse(result["encoder_motion_confirmed"])
        self.assertEqual(result["fresh_current_start"], current)
        self.assertEqual(captured["period"], 0.1)
        self.assertEqual(captured["profile"], "original")
        self.assertEqual(captured["target"]["wrist_flex"], finish["wrist_flex"])
        self.assertEqual(captured["target"]["gripper"], current["gripper"])

    def test_actual_motion_analysis_reports_raw_feedback_and_cycle_torque(self):
        rows = []
        for index in range(2):
            raw = {joint: 2000 + index for joint in JOINTS}
            values = {joint: float(index) for joint in JOINTS}
            rows.append({
                "planned_monotonic_ns": index * 50_000_000,
                "command_monotonic_ns": index * 50_000_000,
                "command_position": values,
                "present_position": values,
                "goal_present_error": {joint: 0.0 for joint in JOINTS},
                "present_raw": raw,
                "goal_raw": raw,
                "torque_enable": {joint: 1 for joint in JOINTS},
                "moving": {joint: index for joint in JOINTS},
            })
        result = analyze_motion_rows(rows)
        self.assertTrue(result["raw_feedback_available"])
        self.assertEqual(result["joints"]["wrist_flex"]["present_raw_net_delta"], 1)
        self.assertEqual(result["torque_enable_cycles"][0]["wrist_flex"], 1)
        self.assertEqual(result["moving_cycles"][1]["wrist_flex"], 1)

    def test_sparse_feedback_analysis_keeps_command_and_feedback_cadence_separate(self):
        rows = []
        for index in range(5):
            sampled = index in {0, 4}
            values = {joint: float(index) for joint in JOINTS}
            raw = {joint: 2000 + index for joint in JOINTS}
            rows.append({
                "sequence": index + 1,
                "planned_monotonic_ns": index * 25_000_000,
                "command_monotonic_ns": index * 25_000_000,
                "command_position": values,
                "feedback_monotonic_ns": index * 25_000_000 if sampled else None,
                "present_position": values if sampled else None,
                "goal_position": values if sampled else None,
                "goal_source": "commanded_sync_write_not_read_back",
                "goal_present_error": ({joint: 0.0 for joint in JOINTS}
                                       if sampled else None),
                "present_raw": raw if sampled else None,
                "goal_raw": None,
                "torque_enable": ({joint: 1 for joint in JOINTS}
                                  if sampled else None),
                "moving": ({joint: int(index == 0) for joint in JOINTS}
                           if sampled else None),
                "temperatures_c": ({joint: 32 for joint in JOINTS}
                                   if sampled else None),
            })
        result = analyze_motion_rows(rows)
        self.assertAlmostEqual(result["command_interval_mean_s"], 0.025)
        self.assertEqual(result["feedback_sample_count"], 2)
        self.assertAlmostEqual(result["feedback_interval_mean_s"], 0.1)
        self.assertTrue(result["raw_feedback_available"])
        self.assertFalse(result["goal_raw_feedback_available"])
        self.assertEqual(result["joints"]["elbow_flex"]["present_raw_net_delta"], 4)
        self.assertEqual(len(result["torque_enable_cycles"]), 2)
        self.assertEqual(len(result["temperature_samples"]), 2)
        self.assertEqual(result["goal_sources"],
                         ["commanded_sync_write_not_read_back"])

    def test_actual_log_comparison_reports_start_match_and_joint_metrics(self):
        def analysis(offset):
            return {
                "raw_feedback_available": True,
                "command_interval_mean_s": 0.1 - offset,
                "command_interval_std_s": 0.001,
                "command_interval_max_s": 0.11,
                "joints": {
                    joint: {
                        "max_delta": 1.5 - offset,
                        "goal_present_error_max_abs": 4.0 - offset,
                        "present_velocity_direction_reversals": int(offset == 0),
                        "present_raw_start": 2000 + index + int(offset * 10),
                        "present_raw_final": 2100 + index,
                    }
                    for index, joint in enumerate(JOINTS)
                },
            }

        with patch("medicine_sorter.fixed_demo.load_and_analyze_motion_log",
                   side_effect=[analysis(0.0), analysis(0.1)]):
            result = compare_actual_motion_logs(Path("original.jsonl"), Path("smooth.jsonl"))
        self.assertEqual(result["status"], "LIVE_MOTION_A_B_ANALYSIS")
        self.assertEqual(result["comparison"]["original_max_step_deg"], 1.5)
        self.assertEqual(result["comparison"]["smooth_max_step_deg"], 1.4)
        self.assertEqual(
            result["joints"]["elbow_flex"]
            ["start_present_raw_difference_smooth_minus_original"], 1)
        self.assertEqual(result["serial_open"], 0)
        self.assertEqual(result["motor_command"], 0)

    def test_original_rejects_smooth_only_options_before_session(self):
        with self.assertRaises(SorterError) as caught:
            run_free_space_motion_test(
                self.config, self.settings, from_pose="home", from_current=False,
                to_pose="red_above", motion_profile="original",
                log_path=Path(".local/fixed-demo-motion/unused.jsonl"), step=True,
                control_hz=40, free_space_velocity=20,
                session_factory=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                    AssertionError("session must not be constructed")),
                install_signal_handlers=False,
            )
        self.assertEqual(caught.exception.code, "original_profile_options_forbidden")

    def test_quintic_profile_has_zero_endpoint_slope_and_preserves_endpoint(self):
        start = {joint: 0.0 for joint in JOINTS}
        delta = {joint: 20.0 for joint in JOINTS}
        from medicine_sorter.fixed_demo import trajectory_position
        p0 = trajectory_position(start, delta, 0.0, profile="quintic")
        p1 = trajectory_position(start, delta, 1.0, profile="quintic")
        near_start = trajectory_position(start, delta, 0.001, profile="quintic")
        near_end = trajectory_position(start, delta, 0.999, profile="quintic")
        self.assertEqual(p0, start)
        self.assertEqual(p1, {joint: 20.0 for joint in JOINTS})
        self.assertLess(near_start["shoulder_pan"], 0.000001)
        self.assertGreater(near_end["shoulder_pan"], 19.999999)

    def test_smooth_profile_keeps_absolute_cadence_despite_write_latency(self):
        clock = Clock()

        class MotionBus(FakeBus):
            def __init__(self):
                super().__init__()
                self.registers["Present_Position"] = {joint: 0.0 for joint in JOINTS}
                self.registers["Goal_Position"] = {joint: 0.0 for joint in JOINTS}
                self.registers["Torque_Enable"] = {joint: 1 for joint in JOINTS}

        class Writes:
            def __init__(self, bus):
                self.bus = bus
                self.times = []
                self.sent = []

            def motion_goal(self, values):
                self.times.append(clock.value)
                self.sent.append(dict(values))
                self.bus.registers["Goal_Position"] = dict(values)
                self.bus.registers["Present_Position"] = dict(values)
                clock.value += 0.02

        bus = MotionBus()
        writes = Writes(bus)
        session = SimpleNamespace(
            follower=SimpleNamespace(bus=bus), writes=writes,
            bounds={joint: (-200.0, 200.0) for joint in JOINTS})
        target = {joint: 0.0 for joint in JOINTS}
        target["shoulder_pan"] = 20.0
        execute_segment(
            session, target, self.settings, stage="free_space",
            motion_profile="smooth", sleep=clock.sleep, monotonic=clock.monotonic)
        intervals = [current - previous
                     for previous, current in zip(writes.times, writes.times[1:])]
        self.assertTrue(intervals)
        self.assertTrue(all(abs(interval - self.settings.control_period_s) < 1e-9
                            for interval in intervals))
        previous = {joint: 0.0 for joint in JOINTS}
        for point in writes.sent:
            self.assertLessEqual(
                max(abs(point[joint] - previous[joint]) for joint in JOINTS),
                self.settings.max_step_deg + 1e-9)
            previous = point
        self.assertAlmostEqual(writes.sent[-1]["shoulder_pan"], 20.0)

    def test_smooth_live_uses_quintic_absolute_deadlines_and_decimated_reads(self):
        clock = Clock()

        class Writes:
            def __init__(self, bus):
                self.bus = bus
                self.times = []
                self.sent = []
                self.last_motion_write_completed_ns = None

            def motion_goal(self, values):
                started = clock.value
                self.times.append(started)
                self.sent.append(dict(values))
                self.bus.registers["Goal_Position"] = {
                    joint: int(round(values[joint])) for joint in JOINTS}
                clock.value += 0.005
                self.last_motion_write_completed_ns = int(clock.value * 1_000_000_000)
                return int(started * 1_000_000_000)

        bus = FakeBus()
        bus.registers["Present_Position"] = {joint: 0 for joint in JOINTS}
        bus.registers["Goal_Position"] = {joint: 0 for joint in JOINTS}
        bus.registers["Torque_Enable"] = {joint: 1 for joint in JOINTS}
        writes = Writes(bus)
        session = SimpleNamespace(follower=SimpleNamespace(bus=bus), writes=writes)
        settings = replace(self.settings, control_period_s=0.025)
        start = {joint: 0.0 for joint in JOINTS}
        target = dict(start)
        target["shoulder_lift"] = 20.0
        recorded = []

        def capture(*_args, **kwargs):
            recorded.append(kwargs)

        with patch("medicine_sorter.fixed_demo._record_motion_cycle", side_effect=capture):
            _execute_time_based_commands(
                session, start, target, settings, stage="free_space",
                recorder=object(), sleep=clock.sleep, monotonic=clock.monotonic,
                stop_requested=lambda: False)

        intervals = [current - previous
                     for previous, current in zip(writes.times, writes.times[1:])]
        self.assertTrue(intervals)
        self.assertTrue(all(abs(value - 0.025) < 1e-9 for value in intervals))
        self.assertLess(writes.sent[0]["shoulder_lift"], 0.01)
        self.assertAlmostEqual(writes.sent[-1]["shoulder_lift"], 20.0)
        previous = start
        for point in writes.sent:
            self.assertLessEqual(max(abs(point[joint] - previous[joint])
                                     for joint in JOINTS), 2.0 + 1e-9)
            previous = point
        self.assertTrue(all(row["profile"] == "smooth_quintic_absolute"
                            for row in recorded))
        feedback_samples = [row for row in recorded if row["present_raw"] is not None]
        safety_samples = [row for row in recorded if row["temperatures_c"] is not None]
        self.assertLess(len(feedback_samples), len(writes.sent))
        self.assertLess(len(safety_samples), len(feedback_samples))
        self.assertEqual(SMOOTH_FEEDBACK_PERIOD_S, 0.1)
        self.assertEqual(SMOOTH_SAFETY_PERIOD_S, 1.0)
        goal_reads = [item for item in bus.reads if item[0] == "Goal_Position"]
        self.assertEqual(len(goal_reads), len(feedback_samples))
        self.assertLess(len(goal_reads), len(writes.sent))

    def test_warm_start_allows_only_50_to_51_and_keeps_hard_limit(self):
        class WarmBus(FakeBus):
            def __init__(self, temperature):
                super().__init__()
                self.temperature = temperature
                self.motors = {joint: SimpleNamespace(id=index + 1)
                               for index, joint in enumerate(JOINTS)}

            def read(self, register, joint, *, normalize, num_retry):
                if register == "Present_Temperature":
                    return self.temperature if joint == "gripper" else 30
                return super().read(register, joint, normalize=normalize, num_retry=num_retry)

        with self.assertRaises(SegmentSafetyFault):
            verify_prestart_temperatures(WarmBus(50))
        allowed = verify_prestart_temperatures(
            WarmBus(51), limit_c_exclusive=WARM_START_MAX_TEMPERATURE_C_EXCLUSIVE)
        self.assertEqual(allowed["gripper"], 51)
        with self.assertRaises(SegmentSafetyFault):
            verify_prestart_temperatures(
                WarmBus(52), limit_c_exclusive=WARM_START_MAX_TEMPERATURE_C_EXCLUSIVE)
        self.assertEqual(PRESTART_MAX_TEMPERATURE_C_EXCLUSIVE, 50)

    def test_warm_start_is_rejected_for_auto_before_camera_or_session(self):
        def forbidden_loader(_url):
            raise AssertionError("camera must not be read")

        with self.assertRaises(SorterError) as caught:
            run_demo(self.config, self.settings, dry_run=False, step=False, auto=True,
                     warm_start_once=True, rules={"A": "green"},
                     snapshot_loader=forbidden_loader)
        self.assertEqual(caught.exception.code, "warm_start_requires_supervised_step")

    def test_teach_only_preserves_base_poses_and_adds_requested_gripper_poses(self):
        positions = {joint: float(index) for index, joint in enumerate(JOINTS)}
        present_raw = {joint: 2000 + index for index, joint in enumerate(JOINTS)}
        base = {
            name: {"position": dict(positions), "present_raw": dict(present_raw),
                   "captured_at_utc": f"base-{index}"}
            for index, name in enumerate(POSE_NAMES)
        }

        class Input:
            def isatty(self):
                return False

            def read(self, _count):
                return "\n"

        class Writes:
            def __init__(self):
                self.counts = {"Goal_Position_motion": 0}

            def motion_goal(self, _values):
                self.counts["Goal_Position_motion"] += 1

        class Session:
            def __init__(self, *_args, **_kwargs):
                bus = FakeBus()
                bus.registers["Present_Position"] = dict(present_raw)
                bus.registers["Goal_Position"] = dict(present_raw)
                self.follower = SimpleNamespace(bus=bus)
                self.leader = SimpleNamespace(
                    get_action=lambda: {f"{joint}.pos": float(index)
                                        for index, joint in enumerate(JOINTS)})
                self.writes = Writes()
                self.bounds = {joint: (-5000.0, 5000.0) for joint in JOINTS}
                self.follower_serial = "5AE6058306"

            def connect(self):
                return None

            def close(self):
                return None

        with tempfile.TemporaryDirectory() as folder:
            pose_path = Path(folder) / "poses.json"
            save_pose_file(pose_path, follower_serial="5AE6058306", poses=base)
            settings = replace(self.settings, pose_path=pose_path)
            fake_input = Input()
            with (patch("medicine_sorter.fixed_demo.establish_hold",
                        return_value={"hold": "TEST"}),
                  patch("medicine_sorter.fixed_demo.select.select",
                        return_value=([fake_input], [], [])),
                  patch("medicine_sorter.fixed_demo.sys.stdin", fake_input)):
                result = teach(
                    self.config, settings, only=list(TYPE_GRIPPER_POSES),
                    session_factory=Session)
            records = load_pose_records(
                pose_path, expected_serial="5AE6058306",
                required_names=POSE_NAMES + TYPE_GRIPPER_POSES)
            self.assertEqual(result["status"], "TEACH_ONLY_COMPLETE")
            self.assertEqual(result["saved_pose_names"], list(TYPE_GRIPPER_POSES))
            self.assertEqual(records["home"]["captured_at_utc"], "base-0")
            self.assertEqual(set(records), set(POSE_NAMES + TYPE_GRIPPER_POSES))

    def test_teach_only_finish_extends_existing_pose_file(self):
        positions = {joint: float(index) for index, joint in enumerate(JOINTS)}
        present_raw = {joint: 2000 + index for index, joint in enumerate(JOINTS)}
        base = {
            name: {"position": dict(positions), "present_raw": dict(present_raw),
                   "captured_at_utc": f"base-{index}"}
            for index, name in enumerate(POSE_NAMES + TYPE_GRIPPER_POSES)
        }

        class Input:
            def isatty(self):
                return False

            def read(self, _count):
                return "\n"

        class Writes:
            def __init__(self):
                self.counts = {"Goal_Position_motion": 0}

            def motion_goal(self, _values):
                self.counts["Goal_Position_motion"] += 1

        class Session:
            def __init__(self, *_args, **_kwargs):
                bus = FakeBus()
                bus.registers["Present_Position"] = dict(present_raw)
                bus.registers["Goal_Position"] = dict(present_raw)
                self.follower = SimpleNamespace(bus=bus)
                self.leader = SimpleNamespace(
                    get_action=lambda: {f"{joint}.pos": float(index)
                                        for index, joint in enumerate(JOINTS)})
                self.writes = Writes()
                self.bounds = {joint: (-5000.0, 5000.0) for joint in JOINTS}
                self.follower_serial = "5AE6058306"

            def connect(self):
                return None

            def close(self):
                return None

        with tempfile.TemporaryDirectory() as folder:
            pose_path = Path(folder) / "poses.json"
            save_pose_file(pose_path, follower_serial="5AE6058306", poses=base)
            settings = replace(self.settings, pose_path=pose_path)
            fake_input = Input()
            with (patch("medicine_sorter.fixed_demo.establish_hold",
                        return_value={"hold": "TEST"}),
                  patch("medicine_sorter.fixed_demo.select.select",
                        return_value=([fake_input], [], [])),
                  patch("medicine_sorter.fixed_demo.sys.stdin", fake_input)):
                result = teach(self.config, settings, only=["finish"],
                               session_factory=Session)
            records = load_pose_records(
                pose_path, expected_serial="5AE6058306", required_names=ALL_POSE_NAMES)
            self.assertEqual(result["status"], "TEACH_ONLY_COMPLETE")
            self.assertEqual(result["saved_pose_names"], ["finish"])
            self.assertEqual(set(records), set(ALL_POSE_NAMES))

    def test_teach_only_invalid_or_conflicting_options_fail_before_session(self):
        def forbidden_factory(*_args, **_kwargs):
            raise AssertionError("session must not be constructed")

        with self.assertRaisesRegex(SorterError, "teach_only_pose_names_invalid"):
            teach(self.config, self.settings, only=["unknown"],
                  session_factory=forbidden_factory)
        with self.assertRaisesRegex(SorterError, "teach_mode_conflict"):
            teach(self.config, self.settings, resume=True, only=["gripper_closed_A"],
                  session_factory=forbidden_factory)

    def test_blocked_type_gripper_is_reanchored_near_present(self):
        class MotionBus(FakeBus):
            def __init__(self):
                super().__init__()
                self.registers["Present_Position"] = {joint: 50.0 for joint in JOINTS}
                self.registers["Torque_Enable"] = {joint: 1 for joint in JOINTS}
                self.motors = {joint: SimpleNamespace(id=index + 1)
                               for index, joint in enumerate(JOINTS)}

            def read(self, register, joint, *, normalize, num_retry):
                if register == "Present_Position":
                    return self.registers[register][joint]
                return super().read(register, joint, normalize=normalize, num_retry=num_retry)

        class Writes:
            def __init__(self, bus):
                self.bus = bus
                self.sent = []

            def motion_goal(self, values):
                self.sent.append(dict(values))
                if values["gripper"] < 30.0:
                    self.bus.registers["Present_Position"]["gripper"] = 30.0
                else:
                    self.bus.registers["Present_Position"]["gripper"] = values["gripper"]

        bus = MotionBus()
        writes = Writes(bus)
        session = SimpleNamespace(
            follower=SimpleNamespace(bus=bus), writes=writes,
            bounds={joint: (-100.0, 100.0) for joint in JOINTS})
        target = {joint: 50.0 for joint in JOINTS}
        target["gripper"] = 10.0
        result = execute_segment(
            session, target, self.settings, stage="gripper_closed_A", sleep=lambda _s: None)
        self.assertEqual(result["contact_relief"]["motor_id"], 6)
        self.assertEqual(result["contact_relief"]["present_at_contact"], 30.0)
        self.assertEqual(result["final_target"]["gripper"], 29.0)
        self.assertEqual(writes.sent[-1]["gripper"], 29.0)

    def test_overload_temperature_read_preserves_id_status_and_holds_current(self):
        class FaultSession:
            instance = None

            def __init__(self, *_args, **_kwargs):
                FaultSession.instance = self
                bus = FakeBus()
                bus.registers["Torque_Enable"] = {joint: 1 for joint in JOINTS}
                bus.registers["Goal_Position"] = dict(bus.registers["Present_Position"])
                bus.motors = {joint: SimpleNamespace(id=index + 1)
                              for index, joint in enumerate(JOINTS)}
                self.follower = SimpleNamespace(bus=bus)
                self.writes = SimpleNamespace(counts={"Goal_Position_motion": 0,
                                                      "Goal_Position_ctrl_c_hold": 0})
                self.held = 0

            def connect(self):
                return None

            def ctrl_c_hold(self):
                self.held += 1
                self.writes.counts["Goal_Position_ctrl_c_hold"] += 1
                return True

            def close(self):
                return None

        poses = {name: {joint: 0.0 for joint in JOINTS} for name in ALL_POSE_NAMES}
        fault = SegmentSafetyFault("servo_status_error", {
            "stage": "home", "register": "Present_Temperature",
            "motor_name": "gripper", "motor_id": 6,
            "register_value": None, "servo_status": "OVERLOAD",
            "servo_status_bit": 32, "servo_status_value": 32,
            "driver_error": "Failed to read 'Present_Temperature' on id_=6. "
                            "[RxPacketError] Overload error!",
        })
        verified = replace(self.settings, roi_status="verified")
        with (patch("medicine_sorter.fixed_demo.load_pose_file", return_value=poses),
              patch("medicine_sorter.fixed_demo.establish_hold", return_value={"hold": "TEST"}),
              patch("medicine_sorter.fixed_demo.execute_segment", side_effect=fault)):
            with self.assertRaises(SorterError) as caught:
                run_demo(self.config, verified, dry_run=False, step=False, auto=True,
                         rules={"C": "red"},
                         snapshot_loader=lambda _url: snapshot(),
                         session_factory=FaultSession)
        observed = caught.exception.observed
        self.assertEqual(caught.exception.code, "demo_fault_current_position_held")
        self.assertEqual(observed["fault"]["motor_id"], 6)
        self.assertEqual(observed["fault"]["servo_status"], "OVERLOAD")
        self.assertEqual(observed["fault"]["servo_status_bit"], 32)
        self.assertEqual(observed["fault"]["servo_status_value"], 32)
        self.assertIn("Overload error", observed["fault"]["driver_error"])
        self.assertEqual(FaultSession.instance.held, 1)

    def test_temperature_read_overload_is_not_replaced_by_generic_failure(self):
        class OverloadBus(FakeBus):
            def __init__(self):
                super().__init__()
                self.motors = {joint: SimpleNamespace(id=index + 1)
                               for index, joint in enumerate(JOINTS)}

            def read(self, register, joint, *, normalize, num_retry):
                if register == "Present_Temperature" and joint == "gripper":
                    raise RuntimeError(
                        "Failed to read 'Present_Temperature' on id_=6 after 1 tries. "
                        "[RxPacketError] Overload error!")
                return super().read(register, joint, normalize=normalize, num_retry=num_retry)

        with self.assertRaises(SegmentSafetyFault) as caught:
            _read_temperatures(OverloadBus(), stage="blue_above")
        self.assertEqual(caught.exception.code, "servo_status_error")
        self.assertEqual(caught.exception.details["motor_id"], 6)
        self.assertEqual(caught.exception.details["servo_status"], "OVERLOAD")
        self.assertEqual(caught.exception.details["servo_status_value"], 32)
        self.assertEqual(len(caught.exception.details["values_read_before_fault"]), 5)
        self.assertIn("Present_Temperature", caught.exception.details["driver_error"])
        self.assertIn("Overload error", caught.exception.details["driver_error"])

    def test_temperature_limit_reports_motor_id_and_value(self):
        class HotBus(FakeBus):
            def __init__(self):
                super().__init__()
                self.motors = {joint: SimpleNamespace(id=index + 1)
                               for index, joint in enumerate(JOINTS)}

            def read(self, register, joint, *, normalize, num_retry):
                if register == "Present_Temperature" and joint == "wrist_roll":
                    return 61
                return super().read(register, joint, normalize=normalize, num_retry=num_retry)

        with self.assertRaises(SegmentSafetyFault) as caught:
            _read_temperatures(HotBus(), stage="blue_above")
        affected = caught.exception.details["affected_motors"]
        self.assertEqual(affected, [{"motor_name": "wrist_roll", "motor_id": 5,
                                     "temperature_c": 61, "limit_c": 55}])

    def test_partial_pose_file_accepts_only_ordered_prefix(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "poses.partial.json"
            positions = {joint: 0.0 for joint in JOINTS}
            present_raw = {joint: 2000 for joint in JOINTS}
            poses = {
                POSE_NAMES[0]: {"position": positions, "present_raw": present_raw},
                POSE_NAMES[1]: {"position": positions, "present_raw": present_raw},
            }
            save_pose_file(path, follower_serial="SERIAL", poses=poses)
            loaded = load_partial_pose_file(path, expected_serial="SERIAL")
            self.assertEqual(list(loaded), list(POSE_NAMES[:2]))

    def test_dry_run_never_constructs_hardware_session(self):
        def forbidden_factory(*_args, **_kwargs):
            raise AssertionError("hardware session must not be constructed")

        result = run_demo(self.config, self.settings, dry_run=True, step=False,
                          rules={"A": "green", "C": "blue"},
                          snapshot_loader=lambda _url: snapshot(),
                          session_factory=forbidden_factory)
        self.assertEqual(result["status"], "FIXED_DEMO_PLAN")
        self.assertEqual(result["serial_open"], 0)
        self.assertEqual(result["motor_command"], 0)
        self.assertEqual(result["destination_rules"], {"A": "green", "C": "blue"})
        self.assertEqual(result["marker_layout_preflight"]["status"], "PASS")
        self.assertEqual(result["motion_profile"], "smooth")
        self.assertEqual(result["control_hz"], 40)
        self.assertEqual(result["trajectory_curve"], "quintic")
        self.assertEqual(result["deadline_mode"], "absolute_deadline_skip_expired_ticks")
        self.assertEqual(result["arm_velocity_limit_deg_s"], 20)

        original = run_demo(
            self.config, self.settings, dry_run=True, step=False,
            motion_profile="original", rules={"A": "green"},
            snapshot_loader=lambda _url: snapshot(), session_factory=forbidden_factory)
        self.assertEqual(original["motion_profile"], "original")
        self.assertEqual(original["control_hz"], 20)
        self.assertEqual(original["trajectory_curve"], "cubic")
        self.assertEqual(original["deadline_mode"], "relative_sleep")

    def test_marker_layout_mismatch_blocks_before_session(self):
        def forbidden_factory(*_args, **_kwargs):
            raise AssertionError("hardware session must not be constructed")

        wrong = snapshot()
        wrong["table"]["detected_marker_centers_px"].pop("9")
        with self.assertRaisesRegex(SorterError, "expected_marker_layout_mismatch"):
            run_demo(self.config, self.settings, dry_run=False, step=False, auto=True,
                     rules={"A": "blue"}, snapshot_loader=lambda _url: wrong,
                     session_factory=forbidden_factory)

    def test_auto_runs_finish_once_after_home_without_input_and_reports_progress(self):
        class Session:
            def __init__(self, *_args, **_kwargs):
                bus = FakeBus()
                bus.registers["Torque_Enable"] = {joint: 1 for joint in JOINTS}
                bus.registers["Goal_Position"] = dict(bus.registers["Present_Position"])
                self.follower = SimpleNamespace(bus=bus)
                self.writes = SimpleNamespace(counts={"Goal_Position_motion": 0})

            def connect(self):
                return None

            def ctrl_c_hold(self):
                raise AssertionError("hold not expected")

            def close(self):
                return None

        poses = {name: {joint: 2000.0 for joint in JOINTS} for name in ALL_POSE_NAMES}
        progress = []
        segment_calls = []

        def fake_segment(_session, target, _settings, *, stage, **kwargs):
            segment_calls.append({
                "stage": stage,
                "motion_profile": kwargs["motion_profile"],
                "control_period_s": _settings.control_period_s,
                "max_step_deg": _settings.max_step_deg,
                "arm_velocity": _settings.velocity["shoulder_pan"],
            })
            return {"final_target": dict(target), "contact_relief": None,
                    "temperatures_c": {joint: 31 for joint in JOINTS}}

        with (patch("medicine_sorter.fixed_demo.load_pose_file", return_value=poses),
              patch("medicine_sorter.fixed_demo.establish_hold", return_value={"hold": "TEST"}),
              patch("medicine_sorter.fixed_demo.execute_segment", side_effect=fake_segment),
              patch("builtins.input", side_effect=AssertionError("auto must not call input"))):
            result = run_demo(
                self.config, self.settings, dry_run=False, step=False, auto=True,
                rules={"A": "blue"}, snapshot_loader=lambda _url: snapshot(),
                session_factory=Session, install_signal_handlers=False,
                progress_callback=progress.append)
        running = [item for item in progress if item["status"] == "RUNNING"]
        self.assertEqual(len(running), 12)
        self.assertEqual(running[0]["stage"], "home")
        self.assertEqual(running[-2]["stage"], "home")
        self.assertEqual(running[-1]["stage"], "finish")
        self.assertEqual(result["status"], "FIXED_DEMO_COMPLETE")
        self.assertEqual(result["motion_profile"], "smooth")
        self.assertTrue(all(call["motion_profile"] == "smooth" for call in segment_calls))
        self.assertTrue(all(call["control_period_s"] == 0.025 for call in segment_calls))
        self.assertTrue(all(call["max_step_deg"] == 2.0 for call in segment_calls))
        self.assertTrue(all(call["arm_velocity"] == 20.0 for call in segment_calls))
        self.assertEqual(result["prestart_temperatures_c"],
                         {joint: 30 for joint in JOINTS})
        self.assertEqual(result["final_temperatures_c"],
                         {joint: 31 for joint in JOINTS})

    def test_prestart_temperature_50_blocks_before_any_motor_write(self):
        class HotBus(FakeBus):
            def __init__(self):
                super().__init__()
                self.motors = {joint: SimpleNamespace(id=index + 1)
                               for index, joint in enumerate(JOINTS)}

            def read(self, register, joint, *, normalize, num_retry):
                if register == "Present_Temperature" and joint == "gripper":
                    return 50
                return super().read(register, joint, normalize=normalize, num_retry=num_retry)

        class Session:
            instance = None

            def __init__(self, *_args, **_kwargs):
                Session.instance = self
                self.follower = SimpleNamespace(bus=HotBus())
                self.writes = SimpleNamespace(counts={"Goal_Position_motion": 0})
                self.ctrl_hold_calls = 0

            def connect(self):
                return None

            def ctrl_c_hold(self):
                self.ctrl_hold_calls += 1
                return True

            def close(self):
                return None

        poses = {name: {joint: 0.0 for joint in JOINTS} for name in ALL_POSE_NAMES}
        with patch("medicine_sorter.fixed_demo.load_pose_file", return_value=poses):
            with self.assertRaises(SorterError) as caught:
                run_demo(self.config, self.settings, dry_run=False, step=False, auto=True,
                         rules={"A": "blue"}, snapshot_loader=lambda _url: snapshot(),
                         session_factory=Session, install_signal_handlers=False)
        self.assertEqual(caught.exception.code, "demo_startup_preflight_failed_no_motion")
        fault = caught.exception.observed["fault"]
        self.assertEqual(fault["affected_motors"][0]["motor_id"], 6)
        self.assertEqual(fault["affected_motors"][0]["temperature_c"], 50)
        self.assertEqual(Session.instance.writes.counts["Goal_Position_motion"], 0)
        self.assertEqual(Session.instance.ctrl_hold_calls, 0)

    def test_module_has_no_sudo_ownership_path(self):
        source = (ROOT / "medicine_sorter/fixed_demo.py").read_text(encoding="utf-8")
        self.assertNotIn("sudo", source)
        self.assertNotIn("fuser", source)
        self.assertNotIn("lsof", source)


if __name__ == "__main__":
    unittest.main()
