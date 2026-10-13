"""Explicit SO-101 follower adapter for a separately approved live trial.

Importing this module never opens a port. ``open_live`` has no CLI entrypoint and
must only be called after a scoped hardware approval and site safety check.
"""

from __future__ import annotations

import fcntl
import hashlib
import importlib.util
import math
import termios
import time
from datetime import datetime
from typing import Mapping
from pathlib import Path

if __package__:
    from scripts.continuous_following_execution import FollowingTelemetry
    from scripts.so101_exclusive_bus import ExclusiveFollowerLease, PreflightError
    from scripts.staged_cycle_execution import Feedback, JOINT_UNITS, StagedCycle
else:
    from continuous_following_execution import FollowingTelemetry
    from so101_exclusive_bus import ExclusiveFollowerLease, PreflightError
    from staged_cycle_execution import Feedback, JOINT_UNITS, StagedCycle


EXPECTED_URDF_SHA256 = "443d38d756e01bac7d3455b24430047ddc6427105e0d3454b2003116f5f67236"
ARM_LIMITS_DEG = {
    "shoulder_pan": (math.degrees(-1.91986), math.degrees(1.91986)),
    "shoulder_lift": (math.degrees(-1.74533), math.degrees(1.74533)),
    "elbow_flex": (math.degrees(-1.74533), 90.0),
    "wrist_flex": (math.degrees(-1.65806), 95.0),
    "wrist_roll": (math.degrees(-2.79253), math.degrees(2.79253)),
}


def calibrated_goal_bounds(robot) -> dict[str, tuple[float, float]]:
    """Resolve actual loaded servo endpoints in send_action units.

    URDF limits remain a planning check for the final IK target.  They are not
    used as a hard block for bounded waypoints that monotonically return a
    fresh, servo-valid pose from just outside the model limit.
    """
    bus = getattr(robot, "bus", None)
    calibration = getattr(bus, "calibration", None)
    motors = getattr(bus, "motors", None)
    normalize = getattr(bus, "_normalize", None)
    if calibration is None or motors is None or not callable(normalize):
        raise PreflightError("follower_calibrated_range_unavailable")
    result = {}
    for name in JOINT_UNITS:
        try:
            item = calibration[name]
            raw_min = item.range_min if hasattr(item, "range_min") else item["range_min"]
            raw_max = item.range_max if hasattr(item, "range_max") else item["range_max"]
            if (not isinstance(raw_min, int) or not isinstance(raw_max, int) or
                    not 0 <= raw_min < raw_max < 4096):
                raise ValueError("invalid raw endpoints")
            motor_id = motors[name].id
            low = float(normalize({motor_id: raw_min})[motor_id])
            high = float(normalize({motor_id: raw_max})[motor_id])
        except Exception as error:
            raise PreflightError(f"follower_calibrated_range_unavailable:{name}") from error
        lower, upper = sorted((low, high))
        if not math.isfinite(lower) or not math.isfinite(upper) or lower >= upper:
            raise PreflightError(f"follower_calibrated_range_invalid:{name}")
        result[name] = (lower, upper)
    return result


def verify_installed_urdf() -> Path:
    """Fail closed if the live package uses a different model snapshot."""
    spec = importlib.util.find_spec("frontend")
    if spec is None or spec.origin is None:
        raise PreflightError("installed_urdf_unknown")
    path = Path(spec.origin).parent / "dist/so-101-urdf/urdf/so101_new_calib.urdf"
    try:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as error:
        raise PreflightError("installed_urdf_unknown") from error
    if digest != EXPECTED_URDF_SHA256:
        raise PreflightError("installed_urdf_changed")
    return path


class SO101FollowerTransport:
    def __init__(self, robot, lease: ExclusiveFollowerLease, *,
                 calibrated_bounds: Mapping[str, tuple[float, float]] | None = None):
        # Fake robot/lease injection is used by offline tests. Ownership and
        # connected calibration are established by open_live in production.
        self.robot = robot
        self.lease = lease
        self._busy = False
        self._start_verified = False
        self._commands_stopped = False
        self._ever_sent = False
        self._waypoint_send_count = 0
        self._elbow_diagnostic: dict | None = None
        self._elbow_pending_waypoint: dict | None = None
        # Direct construction is for offline fakes. Production open_live always
        # replaces this with the installed follower calibration.
        self.calibrated_bounds = dict(calibrated_bounds or {
            **ARM_LIMITS_DEG, "gripper": (0.0, 100.0),
        })
        if (set(self.calibrated_bounds) != set(JOINT_UNITS) or
                any(not math.isfinite(lower) or not math.isfinite(upper) or lower >= upper
                    for lower, upper in self.calibrated_bounds.values())):
            raise PreflightError("follower_calibrated_range_invalid")

    def configure_elbow_diagnostic(self, *, total_waypoints: int,
                                   tail_waypoints: int = 10) -> None:
        """Enable read-only raw Elbow telemetry for one approved trial."""
        if (type(total_waypoints) is not int or total_waypoints < 1 or
                type(tail_waypoints) is not int or
                not 1 <= tail_waypoints <= total_waypoints or self._ever_sent):
            raise ValueError("invalid_elbow_diagnostic_contract")
        self._elbow_diagnostic = {
            "total_waypoints": total_waypoints,
            "tail_waypoints": tail_waypoints,
            "samples": [],
        }
        self._elbow_pending_waypoint = None

    def _elbow_target_raw(self, target_deg: float) -> int:
        bus = self.robot.bus
        motor_id = bus.motors["elbow_flex"].id
        # This is the exact calibrated degree->raw conversion used by
        # FeetechMotorsBus.sync_write before its register sign encoding. A raw
        # Goal_Position read decodes that encoding, making these comparable.
        return int(bus._unnormalize({motor_id: float(target_deg)})[motor_id])

    def _elbow_feedback_deg(self, present_raw: int) -> float:
        bus = self.robot.bus
        motor_id = bus.motors["elbow_flex"].id
        return float(bus._normalize({motor_id: int(present_raw)})[motor_id])

    def _capture_elbow_sample(self, *, phase: str, waypoint_index: int,
                              target_deg: float, target_raw: int,
                              send_time: str, send_time_unix_ns: int,
                              send_time_monotonic_ns: int) -> dict:
        """Read only the four requested Elbow registers, individually."""
        bus = self.robot.bus
        feedback_read_started_unix_ns = time.time_ns()
        feedback_read_started_monotonic_ns = time.monotonic_ns()
        goal_raw = int(bus.read(
            "Goal_Position", "elbow_flex", normalize=False, num_retry=2))
        present_raw = int(bus.read(
            "Present_Position", "elbow_flex", normalize=False, num_retry=2))
        moving = int(bus.read(
            "Moving", "elbow_flex", normalize=False, num_retry=2))
        present_load = int(bus.read(
            "Present_Load", "elbow_flex", normalize=False, num_retry=2))
        feedback_deg = self._elbow_feedback_deg(present_raw)
        feedback_time_unix_ns = time.time_ns()
        feedback_time_monotonic_ns = time.monotonic_ns()
        feedback_time = datetime.now().astimezone().isoformat(timespec="milliseconds")
        row = {
            "phase": phase,
            "waypoint_index": waypoint_index,
            "send_time": send_time,
            "send_time_unix_ns": send_time_unix_ns,
            "send_time_monotonic_ns": send_time_monotonic_ns,
            "feedback_read_started_unix_ns": feedback_read_started_unix_ns,
            "feedback_read_started_monotonic_ns": feedback_read_started_monotonic_ns,
            "feedback_time": feedback_time,
            "feedback_time_unix_ns": feedback_time_unix_ns,
            "feedback_time_monotonic_ns": feedback_time_monotonic_ns,
            "target_deg": float(target_deg),
            "calculated_target_raw": int(target_raw),
            "goal_position_raw_readback": goal_raw,
            "present_position_raw": present_raw,
            "goal_minus_present_raw": goal_raw - present_raw,
            "feedback_deg": feedback_deg,
            "error_deg": feedback_deg - float(target_deg),
            "moving": moving,
            "present_load": present_load,
            "timestamp": feedback_time,
            "timestamp_unix_ns": feedback_time_unix_ns,
        }
        if self._elbow_diagnostic is not None:
            samples = self._elbow_diagnostic["samples"]
            samples.append(row)
            if phase == "waypoint":
                waypoint_rows = [item for item in samples if item["phase"] == "waypoint"]
                excess = len(waypoint_rows) - self._elbow_diagnostic["tail_waypoints"]
                while excess > 0:
                    for index, item in enumerate(samples):
                        if item["phase"] == "waypoint":
                            del samples[index]
                            break
                    excess -= 1
        return row

    def collect_final_elbow_settle(self, *, duration_s: float = 3.0,
                                   interval_s: float = 0.15) -> list[dict]:
        """After the last target, sample Elbow convergence without a write."""
        diagnostic = self._elbow_diagnostic
        if (diagnostic is None or
                not math.isfinite(duration_s) or not 2.0 <= duration_s <= 3.0 or
                not math.isfinite(interval_s) or not 0.1 <= interval_s <= 0.2):
            raise ValueError("invalid_elbow_settle_contract")
        if self._elbow_pending_waypoint is not None:
            self._capture_elbow_sample(
                phase="waypoint", **self._elbow_pending_waypoint)
            self._elbow_pending_waypoint = None
        if not diagnostic["samples"]:
            return []
        last = next((row for row in reversed(diagnostic["samples"])
                     if row["phase"] == "waypoint"), None)
        if last is None:
            return []
        rows = []
        started = time.monotonic()
        while True:
            rows.append(self._capture_elbow_sample(
                phase="final_settle",
                waypoint_index=last["waypoint_index"],
                target_deg=last["target_deg"],
                target_raw=last["calculated_target_raw"],
                send_time=last["send_time"],
                send_time_unix_ns=last["send_time_unix_ns"],
                send_time_monotonic_ns=last["send_time_monotonic_ns"]))
            remaining = duration_s - (time.monotonic() - started)
            if remaining <= 0:
                break
            time.sleep(min(interval_s, remaining))
        return rows

    def elbow_diagnostic_report(self) -> dict | None:
        if self._elbow_diagnostic is None:
            return None
        return {
            "schema_version": 1,
            "joint": "elbow_flex",
            "total_waypoints": self._elbow_diagnostic["total_waypoints"],
            "tail_waypoints": self._elbow_diagnostic["tail_waypoints"],
            "samples": list(self._elbow_diagnostic["samples"]),
        }

    @classmethod
    def open_live(cls, lease: ExclusiveFollowerLease, *, approval_confirmed: bool):
        """Open follower bus only; never connect leader/cameras or alter torque.

        LeLab motor-control tasks must be idle and the canonical follower port
        unused. TIOCEXCL prevents a later LeLab teleop from opening the same
        tty while this process owns it. Any failure closes without
        disabling torque and leaves motion unstarted.
        """
        if approval_confirmed is not True:
            raise PreflightError("live_hardware_approval_required")
        verify_installed_urdf()
        from lerobot.robots.so_follower import SO101Follower, SO101FollowerConfig

        lease.acquire()
        robot = None
        try:
            config = SO101FollowerConfig(
                port=str(lease.port), id="so-101", cameras={},
                use_degrees=True, max_relative_target=None,
                disable_torque_on_disconnect=False,
            )
            robot = SO101Follower(config)
            robot.bus.connect(handshake=False)
            serial = getattr(robot.bus.port_handler, "ser", None)
            if serial is None or not hasattr(serial, "fileno"):
                raise PreflightError("serial_exclusive_seal_unavailable")
            fcntl.ioctl(serial.fileno(), termios.TIOCEXCL)
            if not robot.bus.is_calibrated:
                raise PreflightError("follower_calibration_mismatch")
            bounds = calibrated_goal_bounds(robot)
            lease.mark_connected()
            return cls(robot, lease, calibrated_bounds=bounds)
        except Exception:
            if robot is not None and robot.bus.is_connected:
                robot.bus.disconnect(disable_torque=False)
            lease.release()
            raise

    def send_goal(self, goal: Mapping[str, float]) -> Mapping[str, float]:
        if self._commands_stopped:
            raise PreflightError("command_production_stopped")
        self.lease.ensure_exclusive()
        if not self._start_verified:
            raise PreflightError("start_pose_not_verified")
        if (set(goal) != set(JOINT_UNITS) or
                any(not isinstance(v, (int, float)) or not math.isfinite(v)
                    for v in goal.values())):
            raise ValueError("invalid_so101_goal")
        if any(not lower <= goal[name] <= upper
               for name, (lower, upper) in self.calibrated_bounds.items()):
            raise ValueError("goal_outside_follower_servo_calibration")
        action = {f"{name}.pos": float(goal[name]) for name in JOINT_UNITS}
        self._busy = True
        try:
            # SOFollower.send_action -> FeetechMotorsBus.sync_write Goal_Position.
            # Returned action is the *sent target*, not physical attainment.
            self._ever_sent = True
            sent = self.robot.send_action(action)
            if set(sent) != set(action):
                raise ValueError("send_action_return_shape_mismatch")
            if self._elbow_diagnostic is not None:
                self._waypoint_send_count += 1
                target_deg = float(goal["elbow_flex"])
                self._elbow_pending_waypoint = {
                    "waypoint_index": self._waypoint_send_count,
                    "target_deg": target_deg,
                    "target_raw": self._elbow_target_raw(target_deg),
                    "send_time": datetime.now().astimezone().isoformat(
                        timespec="milliseconds"),
                    "send_time_unix_ns": time.time_ns(),
                    "send_time_monotonic_ns": time.monotonic_ns(),
                }
            return {name: float(sent[f"{name}.pos"]) for name in JOINT_UNITS}
        finally:
            self._busy = False

    def verify_start_pose(self, expected: Mapping[str, float],
                          tolerances: Mapping[str, float]) -> Feedback:
        """Fresh follower feedback must match the first certified route pose."""
        self._start_verified = False
        if set(expected) != set(JOINT_UNITS) or set(tolerances) != set(JOINT_UNITS):
            raise PreflightError("invalid_start_pose_contract")
        if any(not isinstance(expected[name], (int, float)) or
               not math.isfinite(expected[name]) or
               not isinstance(tolerances[name], (int, float)) or
               not math.isfinite(tolerances[name]) or tolerances[name] <= 0
               for name in JOINT_UNITS):
            raise PreflightError("invalid_start_pose_contract")
        sample = self.read_feedback()
        if any(abs(sample.positions[name] - expected[name]) > tolerances[name]
               for name in JOINT_UNITS):
            raise PreflightError("start_pose_mismatch")
        self._start_verified = True
        return sample

    def read_feedback(self) -> Feedback:
        self.lease.ensure_exclusive()
        self._busy = True
        try:
            # get_observation -> new Present_Position sync_read; never echo goal.
            observed = self.robot.get_observation()
            received = time.monotonic()
            positions = {name: float(observed[f"{name}.pos"]) for name in JOINT_UNITS}
            if self._elbow_pending_waypoint is not None:
                self._capture_elbow_sample(
                    phase="waypoint", **self._elbow_pending_waypoint)
                self._elbow_pending_waypoint = None
            return Feedback(positions, received)
        finally:
            self._busy = False

    def read_raw_feedback(self) -> Mapping[str, int]:
        """Same owned bus, fresh unnormalized Present_Position for axis probe."""
        self.lease.ensure_exclusive()
        self._busy = True
        try:
            raw = self.robot.bus.sync_read("Present_Position", normalize=False)
            if set(raw) != set(JOINT_UNITS):
                raise ValueError("raw_feedback_shape_mismatch")
            return {name: int(raw[name]) for name in JOINT_UNITS}
        finally:
            self._busy = False

    def read_following_telemetry(self) -> FollowingTelemetry:
        """Read fresh raw following telemetry without producing a command."""
        self.lease.ensure_exclusive()
        self._busy = True
        try:
            bus = self.robot.bus
            registers = {
                "goal_raw": "Goal_Position",
                "present_raw": "Present_Position",
                "moving": "Moving",
                "present_load": "Present_Load",
            }
            values = {
                key: bus.sync_read(register, normalize=False, num_retry=2)
                for key, register in registers.items()
            }
            # Temperature is read per axis.  A prior grouped status read on
            # this hardware returned a mismatched packet, so the live safety
            # gate must not depend on that grouped status path.
            values["temperature_c"] = {
                name: int(bus.read(
                    "Present_Temperature", name, normalize=False, num_retry=2))
                for name in JOINT_UNITS
            }
            if any(set(item) != set(JOINT_UNITS) for item in values.values()):
                raise ValueError("following_telemetry_shape_mismatch")
            positions = {}
            for name, raw in values["present_raw"].items():
                motor_id = bus.motors[name].id
                positions[name] = float(bus._normalize({motor_id: int(raw)})[motor_id])
            return FollowingTelemetry(
                positions=positions,
                received_monotonic=time.monotonic(),
                goal_raw={name: int(value) for name, value in values["goal_raw"].items()},
                present_raw={name: int(value) for name, value in values["present_raw"].items()},
                moving={name: int(value) for name, value in values["moving"].items()},
                present_load={name: int(value) for name, value in values["present_load"].items()},
                temperature_c={name: int(value)
                               for name, value in values["temperature_c"].items()},
            )
        finally:
            self._busy = False

    def read_escape_telemetry(self) -> FollowingTelemetry:
        """Read per-axis escape telemetry, including temperature, without a write.

        Individual reads are deliberate: a prior grouped status read returned
        an incorrect packet on this hardware.  No value from a failed group
        read is used as an escape decision.
        """
        self.lease.ensure_exclusive()
        self._busy = True
        try:
            bus = self.robot.bus
            registers = {
                "goal_raw": "Goal_Position",
                "present_raw": "Present_Position",
                "moving": "Moving",
                "present_load": "Present_Load",
                "temperature_c": "Present_Temperature",
            }
            values = {
                key: {
                    name: int(bus.read(
                        register, name, normalize=False, num_retry=2))
                    for name in JOINT_UNITS
                }
                for key, register in registers.items()
            }
            positions = {}
            for name, raw in values["present_raw"].items():
                motor_id = bus.motors[name].id
                positions[name] = float(bus._normalize({motor_id: raw})[motor_id])
            return FollowingTelemetry(
                positions=positions,
                received_monotonic=time.monotonic(),
                goal_raw=values["goal_raw"],
                present_raw=values["present_raw"],
                moving=values["moving"],
                present_load=values["present_load"],
                temperature_c=values["temperature_c"],
            )
        finally:
            self._busy = False

    def is_quiescent(self) -> bool:
        return not self._busy

    def stop_commands(self) -> None:
        """Latch off all future sends; an in-flight write is checked separately."""
        self._commands_stopped = True

    def close_without_motion(self, *, arm_stable: bool,
                             object_supported: bool) -> None:
        """Release a read-only/preflight session only when no goal was attempted."""
        self.stop_commands()
        if (self._ever_sent or self._busy or arm_stable is not True or
                object_supported is not True):
            raise PreflightError("unstarted_session_site_confirmation_required")
        self.robot.bus.disconnect(disable_torque=False)
        self._start_verified = False
        self.lease.release()

    def close_after_site_confirmation(self, controller: StagedCycle, *,
                                      object_supported: bool) -> None:
        if (controller.transport is not self or
                controller.command_stop_state != "COMPLETED" or
                controller.arm_stop_state != "FEEDBACK_AND_HUMAN_CONFIRMED" or
                object_supported is not True or self._busy or
                not self.is_quiescent()):
            raise PreflightError("command_stop_and_site_stability_required")
        # Never disable torque blindly while an object could fall. If close
        # fails, keep the lease held rather than falsely releasing ownership.
        self.robot.bus.disconnect(disable_torque=False)
        self._start_verified = False
        self.lease.release()
