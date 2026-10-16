#!/usr/bin/env python3
"""Hardware-disconnected LeLab worker dry-run using only fake leader/follower.

Run with installed LeLab Python and an isolated staged directory. This never
imports the live service process, opens serial ports, or calls a real robot.
"""

from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from types import ModuleType, SimpleNamespace


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


def install_local_stubs() -> None:
    """Import the real worker source on a Mac without LeLab or serial packages."""
    def module(name):
        item = ModuleType(name)
        sys.modules[name] = item
        return item
    package = module("lelab")
    package.__path__ = []
    utils = module("lelab.utils")
    utils.__path__ = []
    module("lelab.utils.config").setup_calibration_files = lambda *_: ("fake-leader", "fake-follower")
    module("lelab.utils.devices").safe_disconnect_device = lambda device, _: setattr(device.bus, "is_connected", False)
    module("lelab.temporary_elbow_direction_guard").guarded_elbow_send = lambda robot, action, *_: robot.send_action(action)
    module("lelab.record").recording_active = False
    module("lelab.rollout").inference_active = False
    for name in ("lerobot", "lerobot.robots", "lerobot.teleoperators"):
        item = module(name)
        item.__path__ = []
    follower = module("lerobot.robots.so_follower")
    follower.SO101Follower = FakeFollower
    follower.SO101FollowerConfig = lambda **kwargs: SimpleNamespace(**kwargs)
    leader = module("lerobot.teleoperators.so_leader")
    leader.SO101Leader = FakeLeader
    leader.SO101LeaderConfig = lambda **kwargs: SimpleNamespace(**kwargs)


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
    teaching_armed = False

    def __init__(self, _config):
        self.bus = FakeBus()
        self.calibration = {}
        self.cameras = {}
        self.fake_action_calls = 0
        self.sent_actions = []
        self.instances.append(self)

    def configure(self):
        pass

    def send_action(self, action):
        if os.environ.get("LELAB_TELEOP_TRACE_ROOT") and os.environ.get("LELAB_TELEOP_TRACE_KIND") == "empirical_relative_teaching" and not self.teaching_armed:
            raise RuntimeError("fake follower send before teaching armed")
        self.fake_action_calls += 1
        self.sent_actions.append(dict(action))
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


def exercise_pre_arm_cases(trace_module, baseline: dict, root: Path) -> dict:
    def case(samples):
        clock = [0.0]
        events = []
        def read():
            return samples.pop(0)
        def advance(seconds):
            clock[0] += seconds
        return trace_module.pre_arm_settle(
            read_diagnostics=read, record=lambda phase, row: events.append(phase),
            pre_connect=baseline, first_post_connect=baseline,
            monotonic=lambda: clock[0], sleep=advance,
        ), events

    transient = []
    for moving in (1, 1, *([0] * 25)):
        row = copy.deepcopy(baseline)
        row["moving"] = {name: moving for name in MOTORS}
        transient.append(row)
    settled, events = case(transient)
    if events[-1] != "SETTLED" or settled["settled"]["moving"]["elbow_flex"] != 0:
        raise RuntimeError("transient Moving case did not settle")

    for label, change, expected in (
        ("goal", lambda row: row["goal_raw"].__setitem__("elbow_flex", 1), "Goal change"),
        ("drift", lambda row: row["present_degree_or_percent"].__setitem__("elbow_flex", 1.1), "drift"),
    ):
        row = copy.deepcopy(baseline)
        change(row)
        ticket = root / f"{label}.ticket"
        ticket.touch()
        previous = os.environ.get("LELAB_TELEOP_TRACE_ONCE_TICKET")
        os.environ["LELAB_TELEOP_TRACE_ONCE_TICKET"] = str(ticket)
        trace = trace_module.CycleTrace(root / f"{label}-abort", capture_kind="empirical_relative_teaching")
        try:
            try:
                trace_module.pre_arm_settle(
                    read_diagnostics=lambda: row,
                    record=trace.record_startup,
                    pre_connect=baseline, first_post_connect=baseline,
                    monotonic=lambda: 0.0, sleep=lambda _: None,
                )
            except RuntimeError as error:
                if expected not in str(error):
                    raise
                trace.record_startup_failure(error)
            else:
                raise RuntimeError(f"{label} did not abort")
            trace.finish(stop_reason="worker_error")
            if not ticket.exists():
                raise RuntimeError(f"{label} consumed ticket before arm")
        finally:
            if previous is None:
                os.environ.pop("LELAB_TELEOP_TRACE_ONCE_TICKET", None)
            else:
                os.environ["LELAB_TELEOP_TRACE_ONCE_TICKET"] = previous
    return {
        "transient_moving_then_settle": "PASS",
        "goal_change_abort_ticket_preserved": "PASS",
        "present_drift_abort_ticket_preserved": "PASS",
    }


def run(staged: Path, urdf: Path, tcp_json: Path, worker_dir: Path | None = None,
        local_stubs: bool = False) -> dict:
    if local_stubs:
        install_local_stubs()
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
        if not local_stubs:
            load_module("lelab.urdf_forward_kinematics", staged / "urdf_forward_kinematics.py")
        load_module("lelab.relative_start_teleop", staged / "relative_start_teleop.py")
        trace_module = load_module("lelab.teleop_cycle_trace", staged / "teleop_cycle_trace.py")
        if local_stubs:
            trace_module.load_grasp_fk = lambda *_: lambda _: [-59.0, -287.0, 84.0]
        fake_preconnect = trace_module.read_same_owner_diagnostics(
            FakeFollower("preflight"), trace_module.load_grasp_fk(urdf, tcp_json)
        )
        fake_preconnect["unix_ns"] = time.time_ns()
        pre_arm_cases = exercise_pre_arm_cases(trace_module, fake_preconnect, root)
        preconnect_path = root / "pre_connect.json"
        preconnect_path.write_text(json.dumps({
            "samples": [fake_preconnect], "motor_write_calls": 0,
            "torque_change_calls": 0,
        }), encoding="utf-8")
        ticket = root / "teaching.ticket"
        ticket.touch()
        os.environ["LELAB_TELEOP_TRACE_PRE_CONNECT_JSON"] = str(preconnect_path)
        os.environ["LELAB_TELEOP_TRACE_ONCE_TICKET"] = str(ticket)
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
        def simulated_pre_arm(**kwargs):
            clock = [0.0]
            def advance(seconds):
                clock[0] += seconds
            return trace_module.pre_arm_settle(
                **kwargs, monotonic=lambda: clock[0], sleep=advance
            )
        worker.pre_arm_settle = simulated_pre_arm
        original_capture = worker.capture_origins
        settle_passed = [False]
        def checked_settle(**kwargs):
            outcome = simulated_pre_arm(**kwargs)
            settle_passed[0] = True
            return outcome
        worker.pre_arm_settle = checked_settle
        def checked_capture(*args):
            if not settle_passed[0]:
                raise RuntimeError("relative_start origin captured before settle")
            return original_capture(*args)
        worker.capture_origins = checked_capture
        original_start = trace_module.CycleTrace.start_teaching
        def marked_start(self):
            original_start(self)
            FakeFollower.teaching_armed = True
        trace_module.CycleTrace.start_teaching = marked_start

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
        requests = [json.loads(line) for line in session.joinpath("requests.jsonl").read_text().splitlines()]
        if not requests or requests[0]["phase"] != "PRE_GUARD_REQUEST":
            raise RuntimeError("pre-guard request evidence missing")
        if not {"requested_target", "requested_delta_per_arm_joint", "limited_joint_step_degree",
                "actual_present_raw", "actual_grasp_tcp_xyz_mm"}.issubset(requests[0]):
            raise RuntimeError("pre-guard request fields missing")
        if len([row for row in requests if row["phase"] == "FIRST_SENT_GOAL"]) != 1:
            raise RuntimeError("first sent Goal must be recorded exactly once")
        startup_rows = [json.loads(line) for line in session.joinpath("startup.jsonl").read_text().splitlines()]
        startup_phases = [row["phase"] for row in startup_rows]
        if not {"PRE_CONNECT_PRESENT", "FIRST_POST_CONNECT", "PRE_ARM_SETTLE", "SETTLED"}.issubset(startup_phases):
            raise RuntimeError("fake pre-arm evidence missing")
        summary = json.loads(session.joinpath("startup_summary.json").read_text())
        if not {"PRE_CONNECT_PRESENT", "FIRST_POST_CONNECT_PRESENT", "FIRST_POST_CONNECT_GOAL",
                "FIRST_MOVING_STATE", "SETTLED_PRESENT", "SETTLED_GOAL",
                "drift_degree_per_arm_joint"}.issubset(summary):
            raise RuntimeError("fake startup summary incomplete")
        if ticket.exists():
            raise RuntimeError("fake armed session did not consume ticket")
        required = {"goal_raw", "present_raw", "goal_degree_or_percent",
                    "present_degree_or_percent", "moving", "present_load_diagnostic",
                    "temperature_c", "fk_grasp_tcp_mm"}
        if not all(set(row["follower_diagnostics"]) == required for row in rows):
            raise RuntimeError("fake trace fields missing")
        if not all(row["command_evidence"] == "guarded_relative_dispatch_boolean_no_motor_ack"
                   for row in rows):
            raise RuntimeError("absolute trace branch used")
        follower = FakeFollower.instances[-1]
        if not follower.sent_actions or any("gripper.pos" in action for action in follower.sent_actions):
            raise RuntimeError("empirical trace sent a gripper goal")
        if any(row["gripper_goal_sent"] for row in rows):
            raise RuntimeError("empirical trace mislabeled gripper goal")
        final_samples = [trace_module.read_same_owner_diagnostics(
            follower, trace_module.load_grasp_fk(urdf, tcp_json)) for _ in range(3)]
        final_path = root / "final_pose_3sample.json"
        final_path.write_text(json.dumps({"samples": final_samples}), encoding="utf-8")
        if len(json.loads(final_path.read_text())["samples"]) != 3:
            raise RuntimeError("three-sample output missing")
        if not local_stubs:
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
        os.environ.pop("LELAB_TELEOP_TRACE_ONCE_TICKET")
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
        if not any("gripper.pos" in action for action in FakeFollower.instances[-1].sent_actions):
            raise RuntimeError("ordinary relative-start gripper behavior changed")

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
            **pre_arm_cases,
            "fake_worker_startup": "PASS",
            "pre_arm_settle_and_first_cycle_logging": "PASS",
            "pre_guard_request_and_first_goal_logging": "PASS",
            "one_shot_consumed_after_start": "PASS",
            "relative_start_observation": "PASS",
            "empirical_gripper_goal_omitted": "PASS",
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
    parser.add_argument("--local-stubs", action="store_true",
                        help="Run fake worker on a host without LeLab/serial dependencies")
    args = parser.parse_args()
    print(json.dumps(run(args.staged, args.urdf, args.tcp_json, args.worker_dir,
                         args.local_stubs), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
