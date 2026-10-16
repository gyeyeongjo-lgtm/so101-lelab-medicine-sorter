import json
import tempfile
import unittest
from pathlib import Path

from medicine_sorter.config import load_config
from medicine_sorter.fixed_demo import (
    JOINTS, StrictWriteGate, establish_hold, load_demo_settings,
    routes_from_snapshot, run_demo, slot_for_pixel, smooth_interpolation,
    stage_names_for_routes,
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

    def sync_read(self, register, *, normalize, num_retry):
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

    def test_pixel_slots(self):
        self.assertEqual(slot_for_pixel((300, 220), self.settings.slots), "slot1")
        self.assertEqual(slot_for_pixel((380, 220), self.settings.slots), "slot2")
        self.assertEqual(slot_for_pixel((450, 220), self.settings.slots), "slot3")

    def test_outside_or_boundary_gap_fails(self):
        with self.assertRaisesRegex(ValueError, "not_in_exactly_one"):
            slot_for_pixel((100, 100), self.settings.slots)

    def test_routes_C_red_B_blue_and_A_is_explicitly_ignored(self):
        routes, ignored = routes_from_snapshot(snapshot(), self.settings)
        self.assertEqual([(item.bottle_type, item.destination) for item in routes],
                         [("C", "red"), ("B", "blue")])
        self.assertEqual(ignored[0]["bottle_type"], "A")
        self.assertEqual(ignored[0]["reason"], "destination_rule_not_defined")

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

    def test_dry_run_never_constructs_hardware_session(self):
        def forbidden_factory(*_args, **_kwargs):
            raise AssertionError("hardware session must not be constructed")

        result = run_demo(self.config, self.settings, dry_run=True, step=False,
                          snapshot_loader=lambda _url: snapshot(),
                          session_factory=forbidden_factory)
        self.assertEqual(result["status"], "FIXED_DEMO_PLAN")
        self.assertEqual(result["serial_open"], 0)
        self.assertEqual(result["motor_command"], 0)

    def test_module_has_no_sudo_ownership_path(self):
        source = (ROOT / "medicine_sorter/fixed_demo.py").read_text(encoding="utf-8")
        self.assertNotIn("sudo", source)
        self.assertNotIn("fuser", source)
        self.assertNotIn("lsof", source)


if __name__ == "__main__":
    unittest.main()
