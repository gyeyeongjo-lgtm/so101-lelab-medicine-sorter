#!/usr/bin/env python3
"""Hardware-disconnected LeLab worker dry-run using only fake leader/follower.

Run with installed LeLab Python and an isolated staged directory. This never
imports the live service process, opens serial ports, or calls a real robot.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace


MOTORS = (
    "shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper"
)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load staged module: {name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class FakeBus:
    def __init__(self):
        self.motors = {name: SimpleNamespace(id=index) for index, name in enumerate(MOTORS, 1)}
        self.calibration = {name: SimpleNamespace(range_min=-1000, range_max=3000)
                            for name in MOTORS}
        self.is_connected = False
        self.read_calls = 0
        self.fake_calibration_calls = 0

    def connect(self):
        self.is_connected = True

    def write_calibration(self, _calibration):
        self.fake_calibration_calls += 1

    def sync_read(self, register, *args, normalize=True, **kwargs):
        self.read_calls += 1
        if register == "Present_Position" and normalize:
            return {name: 0.0 for name in MOTORS}
        if register == "Moving":
            return {name: 0 for name in MOTORS}
        if register == "Present_Load":
            return {name: -24 for name in MOTORS}
        return {name: 0 for name in MOTORS}

    def read(self, register, name, **kwargs):
        assert register == "Present_Temperature" and name in MOTORS
        self.read_calls += 1
        return 40

    def _normalize(self, values):
        return {key: float(value) for key, value in values.items()}


class FakeFollower:
    instances = []

    def __init__(self, _config):
        self.bus = FakeBus()
        self.calibration = {}
        self.cameras = {}
        self.fake_action_calls = 0
        self.instances.append(self)

    def configure(self):
        pass

    def send_action(self, action):
        self.fake_action_calls += 1
        return dict(action)

    def get_observation(self):
        return {f"{name}.pos": 0.0 for name in MOTORS}


class FakeLeader:
    def __init__(self, _config):
        self.bus = FakeBus()
        self.calibration = {}

    def configure(self):
        pass

    def get_action(self):
        return {f"{name}.pos": 0.0 for name in MOTORS}


def run(staged: Path, urdf: Path, tcp_json: Path, worker_dir: Path | None = None) -> dict:
    import lelab

    worker_dir = staged if worker_dir is None else worker_dir

    with tempfile.TemporaryDirectory(prefix="empirical-teaching-fake-") as temporary:
        root = Path(temporary)
        os.environ.update({
            "LELAB_TELEOP_MODE": "relative_start",
            "LELAB_TELEOP_TRACE_KIND": "empirical_relative_teaching",
            "LELAB_TELEOP_TRACE_ROOT": str(root / "traces"),
            "LELAB_TELEOP_TRACE_URDF": str(urdf),
            "LELAB_TELEOP_TRACE_TCP_JSON": str(tcp_json),
        })
        (root / "traces").mkdir()
        load_module("lelab.urdf_forward_kinematics", worker_dir / "urdf_forward_kinematics.py")
        trace_module = load_module("lelab.teleop_cycle_trace", worker_dir / "teleop_cycle_trace.py")
        worker = load_module("lelab.teleoperate", worker_dir / "teleoperate.py")
        worker.SO101Follower = FakeFollower
        worker.SO101Leader = FakeLeader
        worker.setup_calibration_files = lambda *_: ("fake-leader", "fake-follower")
        worker.safe_disconnect_device = lambda device, _logger: setattr(device.bus, "is_connected", False)
        worker.guarded_elbow_send = lambda robot, action, _previous, _logger: robot.send_action(action)

        def simulated_stillness(**kwargs):
            clock = [0.0]
            def advance(seconds):
                clock[0] += seconds
            return trace_module.verify_relative_start_stillness(
                **kwargs, monotonic=lambda: clock[0], sleep=advance
            )
        worker.verify_relative_start_stillness = simulated_stillness

        request = worker.TeleoperateRequest(
            leader_port="/dev/fake-leader", follower_port="/dev/fake-follower",
            leader_config="fake", follower_config="fake",
        )
        outcome = worker.handle_start_teleoperation(request)
        if not outcome.get("success"):
            raise RuntimeError(f"fake startup failed: {outcome}")
        session = Path(outcome["trace_session_dir"])
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            if session.joinpath("cycles.jsonl").exists():
                rows = session.joinpath("cycles.jsonl").read_text().splitlines()
                if len(rows) >= 3:
                    break
            time.sleep(0.01)
        worker.handle_stop_teleoperation()
        manifest = json.loads(session.joinpath("manifest.json").read_text())
        rows = [json.loads(line) for line in session.joinpath("cycles.jsonl").read_text().splitlines()]
        if len(rows) < 3 or manifest["error_count"] or not manifest["data_complete"]:
            raise RuntimeError("fake trace incomplete")
        required = {"goal_raw", "present_raw", "goal_degree_or_percent",
                    "present_degree_or_percent", "moving", "present_load_diagnostic",
                    "temperature_c", "fk_grasp_tcp_mm"}
        if not all(set(row["follower_diagnostics"]) == required for row in rows):
            raise RuntimeError("fake trace fields missing")
        if not all(row["command_evidence"] == "guarded_relative_dispatch_boolean_no_motor_ack"
                   for row in rows):
            raise RuntimeError("absolute trace branch used")
        follower = FakeFollower.instances[-1]
        final_samples = [trace_module.read_same_owner_diagnostics(
            follower, trace_module.load_grasp_fk(urdf, tcp_json)) for _ in range(3)]
        final_path = root / "final_pose_3sample.json"
        final_path.write_text(json.dumps({"samples": final_samples}), encoding="utf-8")
        if len(json.loads(final_path.read_text())["samples"]) != 3:
            raise RuntimeError("three-sample output missing")
        sys.path.insert(0, str(staged))
        from recorded_pose_config import build_pose_record, save_pose_records
        ideal = {name: 0.0 for name in MOTORS[:-1]}
        pose = build_pose_record(
            name="C_PREAPPROACH_EMPIRICAL",
            raw_samples=[sample["present_raw"] for sample in final_samples],
            degree_samples=[sample["present_degree_or_percent"] for sample in final_samples],
            fk_grasp_tcp_samples_mm=[sample["fk_grasp_tcp_mm"] for sample in final_samples],
            temperature_samples_c=[sample["temperature_c"] for sample in final_samples],
            recorded_at=datetime.now(timezone.utc).isoformat(),
            note="FAKE_ONLY_NO_PHYSICAL_C_ALIGNMENT",
            ideal_ik_joints_deg=ideal,
            ideal_ik_fk_grasp_tcp_mm=[0.0, 0.0, 0.0],
        )
        pose_path = root / "poses.yaml"
        save_pose_records(pose_path, {"C_PREAPPROACH_EMPIRICAL": pose})
        if not pose_path.is_file() or pose["sample_count"] != 3:
            raise RuntimeError("fake empirical pose output missing")
        if follower.bus.is_connected or worker.teleoperation_active:
            raise RuntimeError("fake worker did not release bus")

        # With tracing disabled, the original relative-start branch must still
        # dispatch normally through the same fake guard.
        os.environ.pop("LELAB_TELEOP_TRACE_ROOT")
        untraced = worker.handle_start_teleoperation(request)
        if not untraced.get("success") or untraced.get("trace_session_dir") is not None:
            raise RuntimeError("untraced relative-start startup changed")
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and FakeFollower.instances[-1].fake_action_calls < 2:
            time.sleep(0.01)
        untraced_calls = FakeFollower.instances[-1].fake_action_calls
        worker.handle_stop_teleoperation()
        if untraced_calls < 2:
            raise RuntimeError("untraced relative-start dispatch broken")

        # The old absolute-cycle recorder remains intentionally incompatible
        # with relative-start; it must fail before any guarded fake dispatch.
        os.environ["LELAB_TELEOP_TRACE_ROOT"] = str(root / "traces")
        os.environ["LELAB_TELEOP_TRACE_KIND"] = "full_cycle"
        legacy = worker.handle_start_teleoperation(request)
        if not legacy.get("success"):
            raise RuntimeError("legacy trace fake startup failed unexpectedly")
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and worker.teleoperation_active:
            time.sleep(0.01)
        legacy_follower = FakeFollower.instances[-1]
        legacy_manifest = json.loads(Path(legacy["trace_session_dir"]).joinpath("manifest.json").read_text())
        if worker.teleoperation_active or legacy_follower.fake_action_calls != 0:
            raise RuntimeError("legacy absolute trace sent during relative-start")
        if legacy_manifest["stop_reason"] != "worker_error":
            raise RuntimeError("legacy trace collision not isolated")
        return {
            "fake_worker_startup": "PASS",
            "relative_start_observation": "PASS",
            "original_untraced_relative_start": "PASS",
            "legacy_absolute_trace_conflict": "FAIL_CLOSED_BEFORE_FAKE_DISPATCH",
            "cycle_count": len(rows),
            "goal_moving_load_temperature_fk": "PASS",
            "three_final_readonly_samples_and_output_file": "PASS",
            "real_serial_open": 0,
            "real_motor_command": 0,
            "real_goal_write": 0,
            "real_torque_write": 0,
            "fake_guarded_dispatch_calls": follower.fake_action_calls,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staged", type=Path, required=True)
    parser.add_argument("--urdf", type=Path, required=True)
    parser.add_argument("--tcp-json", type=Path, required=True)
    parser.add_argument("--worker-dir", type=Path,
                        help="Load the installed LeLab worker while keeping fake helpers staged")
    args = parser.parse_args()
    print(json.dumps(run(args.staged, args.urdf, args.tcp_json, args.worker_dir), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
