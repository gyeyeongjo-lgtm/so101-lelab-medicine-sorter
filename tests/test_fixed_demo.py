import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from medicine_sorter.config import load_config
from medicine_sorter.fixed_demo import (
    GRIPPER_POSES, JOINTS, POSE_NAMES, POST_GOAL_READ_RETRIES,
    TEACH_GOAL_PRESENT_RAW_TOLERANCE, StrictWriteGate,
    clamp_to_calibrated_inner_range, establish_hold, load_demo_settings,
    load_partial_pose_file, parse_destination_rules, routes_from_snapshot,
    resolve_robot_ports, run_demo, save_pose_file, slot_for_pixel,
    smooth_interpolation, stage_names_for_routes, target_for_stage,
    validate_demo_settings,
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
                "7": [300.0, 220.0],
                "8": [380.0, 220.0],
                "9": [450.0, 220.0],
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
        self.assertIn("green_above", POSE_NAMES)
        self.assertIn("green_release", POSE_NAMES)

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
                         [("C", "red"), ("B", "blue")])
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

    def test_stage_order_has_grasp_close_lift_release_open_home(self):
        routes, _ = routes_from_snapshot(snapshot(centers={"7": [300, 220]}), self.settings)
        stages = stage_names_for_routes(routes)
        self.assertEqual(stages, [
            "home", "gripper_open", "slot1_pre", "slot1_grasp",
            "gripper_closed", "slot1_lift", "red_above", "red_release",
            "gripper_open", "red_above", "home",
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
        self.assertEqual(len(stages), 33)
        for index, route in enumerate(routes):
            chunk = stages[index * 11:(index + 1) * 11]
            self.assertEqual(chunk, [
                "home", "gripper_open", f"{route.slot}_pre", f"{route.slot}_grasp",
                "gripper_closed", f"{route.slot}_lift", f"{route.destination}_above",
                f"{route.destination}_release", "gripper_open",
                f"{route.destination}_above", "home",
            ])

    def test_only_explicit_gripper_stages_change_gripper(self):
        current = {joint: 10.0 + index for index, joint in enumerate(JOINTS)}
        poses = {}
        for index, name in enumerate(POSE_NAMES):
            poses[name] = {joint: 100.0 + index * 10 + joint_index
                           for joint_index, joint in enumerate(JOINTS)}
        poses["gripper_open"]["gripper"] = 90.0
        poses["gripper_closed"]["gripper"] = 10.0
        routes, _ = routes_from_snapshot(
            snapshot(), self.settings, {"A": "green", "B": "red", "C": "blue"})
        for stage in stage_names_for_routes(routes):
            previous_gripper = current["gripper"]
            target = target_for_stage(stage, current, poses[stage])
            if stage == "gripper_open":
                self.assertEqual(target["gripper"], 90.0)
            elif stage == "gripper_closed":
                self.assertEqual(target["gripper"], 10.0)
            else:
                self.assertEqual(target["gripper"], previous_gripper)
                self.assertEqual({joint: target[joint] for joint in JOINTS[:-1]},
                                 {joint: poses[stage][joint] for joint in JOINTS[:-1]})
            current = target
        self.assertEqual(GRIPPER_POSES, {"gripper_open", "gripper_closed"})

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
        self.assertEqual(set(self.settings.velocity.values()), {20.0})
        self.assertEqual(set(self.settings.acceleration.values()), {60.0})
        self.assertEqual(self.settings.settle_tolerance["gripper"], 100.0)
        self.assertEqual(TEACH_GOAL_PRESENT_RAW_TOLERANCE, 40)

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

    def test_module_has_no_sudo_ownership_path(self):
        source = (ROOT / "medicine_sorter/fixed_demo.py").read_text(encoding="utf-8")
        self.assertNotIn("sudo", source)
        self.assertNotIn("fuser", source)
        self.assertNotIn("lsof", source)


if __name__ == "__main__":
    unittest.main()
