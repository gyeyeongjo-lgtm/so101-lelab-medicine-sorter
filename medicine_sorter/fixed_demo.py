from __future__ import annotations

import fcntl
import json
import math
import os
import select
import signal
import sys
import tempfile
import termios
import time
import tty
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.request import Request, urlopen

from .errors import SorterError


JOINTS = (
    "shoulder_pan", "shoulder_lift", "elbow_flex",
    "wrist_flex", "wrist_roll", "gripper",
)
ARM_JOINTS = JOINTS[:-1]
POSE_NAMES = (
    "home",
    "gripper_open", "gripper_closed",
    "slot1_pre", "slot1_grasp", "slot1_lift",
    "slot2_pre", "slot2_grasp", "slot2_lift",
    "slot3_pre", "slot3_grasp", "slot3_lift",
    "red_above", "red_release",
    "blue_above", "blue_release",
)
MAX_TEMPERATURE_C = 55


def _fail(code: str, observed: Any, expected: str, remedy: str) -> SorterError:
    return SorterError(code, observed, expected, remedy)


@dataclass(frozen=True)
class MarkerRoute:
    marker_id: int
    bottle_type: str
    slot: str
    destination: str
    center_px: tuple[float, float]

    def as_dict(self) -> dict[str, Any]:
        return {
            "marker_id": self.marker_id,
            "bottle_type": self.bottle_type,
            "slot": self.slot,
            "destination": self.destination,
            "marker_center_px": list(self.center_px),
        }


@dataclass(frozen=True)
class DemoSettings:
    pose_path: Path
    snapshot_url: str
    snapshot_max_age_s: float
    image_size_px: tuple[int, int]
    coordinate_space: str
    marker_to_type: dict[int, str]
    destinations: dict[str, str]
    slots: dict[str, tuple[float, float, float, float]]
    roi_status: str
    control_period_s: float
    max_step_deg: float
    max_gripper_step: float
    velocity: dict[str, float]
    acceleration: dict[str, float]
    max_segment_travel: dict[str, float]
    settle_tolerance: dict[str, float]
    settle_timeout_s: float


def load_demo_settings(config) -> DemoSettings:
    raw = config.raw.get("fixed_demo")
    if not isinstance(raw, dict):
        raise _fail("fixed_demo_config_missing", raw, "fixed_demo object",
                    "configs/system.example.json의 fixed_demo 설정을 확인해 주세요")
    try:
        pose_path = Path(raw["pose_file"])
        if not pose_path.is_absolute():
            pose_path = (config.path.parent.parent / pose_path).resolve()
        size = tuple(int(v) for v in raw["image_size_px"])
        slots = {
            str(name): tuple(float(v) for v in rect)
            for name, rect in raw["slot_pixel_rois"].items()
        }
        marker_to_type = {int(k): str(v) for k, v in raw["marker_id_to_type"].items()}
        destinations = {str(k): str(v) for k, v in raw["destination_rules"].items()}
        motion = raw["motion"]
        velocity = {joint: float(motion["max_velocity"][joint]) for joint in JOINTS}
        acceleration = {joint: float(motion["max_acceleration"][joint]) for joint in JOINTS}
        travel = {joint: float(motion["max_segment_travel"][joint]) for joint in JOINTS}
        tolerance = {joint: float(motion["settle_tolerance"][joint]) for joint in JOINTS}
        settings = DemoSettings(
            pose_path=pose_path,
            snapshot_url=str(raw["camera_snapshot_url"]),
            snapshot_max_age_s=float(raw["snapshot_max_age_s"]),
            image_size_px=(size[0], size[1]),
            coordinate_space=str(raw["pixel_coordinate_space"]),
            marker_to_type=marker_to_type,
            destinations=destinations,
            slots=slots,
            roi_status=str(raw.get("slot_roi_status", "UNSPECIFIED")),
            control_period_s=float(motion["control_period_s"]),
            max_step_deg=float(motion["max_emitted_step_deg"]),
            max_gripper_step=float(motion["max_gripper_step_percent"]),
            velocity=velocity,
            acceleration=acceleration,
            max_segment_travel=travel,
            settle_tolerance=tolerance,
            settle_timeout_s=float(motion["settle_timeout_s"]),
        )
    except (KeyError, TypeError, ValueError, IndexError) as error:
        raise _fail("fixed_demo_config_invalid", f"{type(error).__name__}: {error}",
                    "complete fixed_demo schema", "설정의 누락·수치 형식을 확인해 주세요") from error
    validate_demo_settings(settings)
    return settings


def validate_demo_settings(settings: DemoSettings) -> None:
    if settings.image_size_px != (640, 480):
        raise ValueError("fixed_demo_image_size_must_match_astra_640x480")
    if settings.coordinate_space != "undistorted_full_frame":
        raise ValueError("fixed_demo_coordinate_space_invalid")
    if set(settings.slots) != {"slot1", "slot2", "slot3"}:
        raise ValueError("fixed_demo_requires_slot1_slot2_slot3")
    width, height = settings.image_size_px
    for name, rect in settings.slots.items():
        if len(rect) != 4:
            raise ValueError(f"invalid_slot_rectangle:{name}")
        x1, y1, x2, y2 = rect
        if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
            raise ValueError(f"slot_rectangle_out_of_frame:{name}")
    names = sorted(settings.slots)
    for index, first_name in enumerate(names):
        a = settings.slots[first_name]
        for second_name in names[index + 1:]:
            b = settings.slots[second_name]
            if max(a[0], b[0]) < min(a[2], b[2]) and max(a[1], b[1]) < min(a[3], b[3]):
                raise ValueError(f"overlapping_slot_rois:{first_name}:{second_name}")
    if settings.marker_to_type != {7: "C", 8: "B", 9: "A"}:
        raise ValueError("fixed_demo_marker_mapping_must_be_7C_8B_9A")
    if settings.destinations != {"C": "red", "B": "blue"}:
        raise ValueError("fixed_demo_destination_rules_must_be_C_red_B_blue")
    if not 0 < settings.control_period_s <= 0.2:
        raise ValueError("invalid_control_period")
    if not 0 < settings.max_step_deg <= 2.0:
        raise ValueError("two_degree_limit_must_not_be_relaxed")
    if not 0 < settings.max_gripper_step <= 2.0:
        raise ValueError("invalid_gripper_step_limit")
    for values in (settings.velocity, settings.acceleration,
                   settings.max_segment_travel, settings.settle_tolerance):
        if set(values) != set(JOINTS) or any(not math.isfinite(v) or v <= 0 for v in values.values()):
            raise ValueError("invalid_joint_motion_limits")


def fetch_snapshot(url: str, *, timeout_s: float = 3.0) -> dict[str, Any]:
    request = Request(url, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=timeout_s) as response:
            payload = json.loads(response.read(3_000_000))
    except Exception as error:
        raise _fail("camera_snapshot_failed", f"{type(error).__name__}: {error}",
                    "Astra manual-frame.json 1회 응답", "8020 카메라 화면 상태를 확인해 주세요") from error
    if not isinstance(payload, dict) or not isinstance(payload.get("snapshot"), dict):
        raise _fail("camera_snapshot_invalid", type(payload).__name__, "snapshot object",
                    "카메라 서비스 버전을 확인해 주세요")
    return payload["snapshot"]


def slot_for_pixel(point: Sequence[float], slots: Mapping[str, Sequence[float]]) -> str:
    if len(point) != 2 or any(not isinstance(v, (int, float)) or isinstance(v, bool)
                              or not math.isfinite(float(v)) for v in point):
        raise ValueError("invalid_marker_center")
    x, y = map(float, point)
    matched = [name for name, (x1, y1, x2, y2) in slots.items()
               if x1 <= x < x2 and y1 <= y < y2]
    if len(matched) != 1:
        raise ValueError(f"marker_center_not_in_exactly_one_slot:{x:.3f},{y:.3f}:{matched}")
    return matched[0]


def routes_from_snapshot(snapshot: Mapping[str, Any], settings: DemoSettings) -> tuple[list[MarkerRoute], list[dict]]:
    if snapshot.get("ok") is not True:
        raise _fail("camera_not_ready", snapshot.get("error"), "ok=true",
                    "Astra 카메라 서비스를 확인해 주세요")
    age = snapshot.get("frame_age_s")
    if not isinstance(age, (int, float)) or isinstance(age, bool) or age > settings.snapshot_max_age_s:
        raise _fail("camera_frame_stale", age, f"<={settings.snapshot_max_age_s}s",
                    "카메라 프레임이 갱신되는지 확인해 주세요")
    table = snapshot.get("table")
    if not isinstance(table, Mapping):
        raise _fail("aruco_result_missing", table, "table marker result",
                    "Astra 서비스에 ArUco 작업대 설정이 로드됐는지 확인해 주세요")
    if table.get("coordinate_space") != settings.coordinate_space:
        raise _fail("pixel_coordinate_space_mismatch", table.get("coordinate_space"),
                    settings.coordinate_space, "resize/crop 없는 왜곡 보정 프레임을 사용해 주세요")
    if tuple(table.get("source_frame_size_px", ())) != settings.image_size_px:
        raise _fail("camera_image_size_mismatch", table.get("source_frame_size_px"),
                    str(list(settings.image_size_px)), "카메라 해상도와 ROI 설정을 맞춰 주세요")
    centers = table.get("detected_marker_centers_px")
    if not isinstance(centers, Mapping):
        raise _fail("aruco_centers_missing", centers, "detected_marker_centers_px",
                    "ArUco 검출 상태를 확인해 주세요")
    routes: list[MarkerRoute] = []
    ignored: list[dict] = []
    for marker_id, bottle_type in settings.marker_to_type.items():
        center = centers.get(str(marker_id))
        if center is None:
            continue
        try:
            slot = slot_for_pixel(center, settings.slots)
        except ValueError as error:
            raise _fail("bottle_marker_outside_slot", {"id": marker_id, "center": center},
                        "configured slot1..3 중 정확히 하나",
                        "약통을 고정 칸 안에 놓고 dry-run을 다시 확인해 주세요") from error
        destination = settings.destinations.get(bottle_type)
        if destination is None:
            ignored.append({"marker_id": marker_id, "bottle_type": bottle_type,
                            "slot": slot, "reason": "destination_rule_not_defined"})
            continue
        routes.append(MarkerRoute(marker_id, bottle_type, slot, destination,
                                  (float(center[0]), float(center[1]))))
    routes.sort(key=lambda route: route.center_px[0])
    if not routes:
        raise _fail("no_routable_bottle_marker", {"detected": sorted(centers), "ignored": ignored},
                    "slot 안의 ID7(C) 또는 ID8(B)", "C 또는 B 약통 마커가 보이게 놓아 주세요")
    return routes, ignored


def stage_names_for_routes(routes: Sequence[MarkerRoute]) -> list[str]:
    stages = ["home", "gripper_open"]
    for route in routes:
        stages.extend((
            f"{route.slot}_pre", f"{route.slot}_grasp", "gripper_closed",
            f"{route.slot}_lift", f"{route.destination}_above",
            f"{route.destination}_release", "gripper_open",
            f"{route.destination}_above", "home",
        ))
    return stages


def save_pose_file(path: Path, *, follower_serial: str, poses: Mapping[str, Mapping[str, Any]]) -> None:
    payload = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "follower_serial": follower_serial,
        "units": {"arm": "degree", "gripper": "percent", "raw": "servo_raw"},
        "poses": poses,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def load_pose_file(path: Path, *, expected_serial: str) -> dict[str, dict[str, float]]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise _fail("pose_file_load_failed", str(error), str(path),
                    "teach 명령으로 모든 자세를 먼저 저장해 주세요") from error
    if raw.get("schema_version") != 1 or raw.get("follower_serial") != expected_serial:
        raise _fail("pose_file_identity_mismatch", raw.get("follower_serial"), expected_serial,
                    "현재 follower에서 자세를 다시 티칭해 주세요")
    poses = raw.get("poses")
    missing = [name for name in POSE_NAMES if name not in poses] if isinstance(poses, dict) else list(POSE_NAMES)
    if missing:
        raise _fail("pose_file_incomplete", missing, "all fixed demo poses",
                    "teach 명령을 끝까지 완료해 주세요")
    result = {}
    for name in POSE_NAMES:
        values = poses[name].get("position") if isinstance(poses[name], dict) else None
        if not isinstance(values, dict) or set(values) != set(JOINTS):
            raise _fail("pose_values_invalid", name, "six joint positions",
                        "해당 자세를 다시 티칭해 주세요")
        converted = {joint: float(values[joint]) for joint in JOINTS}
        if any(not math.isfinite(v) for v in converted.values()):
            raise _fail("pose_values_nonfinite", name, "finite joint positions",
                        "pose JSON을 확인해 주세요")
        result[name] = converted
    return result


def smooth_interpolation(start: Mapping[str, float], target: Mapping[str, float],
                         settings: DemoSettings) -> list[dict[str, float]]:
    if set(start) != set(JOINTS) or set(target) != set(JOINTS):
        raise ValueError("interpolation_joint_keys_invalid")
    delta = {joint: float(target[joint]) - float(start[joint]) for joint in JOINTS}
    violations = {joint: abs(value) for joint, value in delta.items()
                  if abs(value) > settings.max_segment_travel[joint]}
    if violations:
        raise ValueError(f"segment_travel_limit_exceeded:{violations}")
    duration = settings.control_period_s
    for joint, distance in delta.items():
        duration = max(duration,
                       1.5 * abs(distance) / settings.velocity[joint],
                       math.sqrt(6.0 * abs(distance) / settings.acceleration[joint]))
    count = max(1, math.ceil(duration / settings.control_period_s))
    while True:
        points = []
        for index in range(1, count + 1):
            u = index / count
            fraction = u * u * (3.0 - 2.0 * u)
            points.append({joint: float(start[joint]) + fraction * delta[joint]
                           for joint in JOINTS})
        previous = {joint: float(start[joint]) for joint in JOINTS}
        okay = True
        for point in points:
            for joint in JOINTS:
                limit = settings.max_gripper_step if joint == "gripper" else settings.max_step_deg
                if abs(point[joint] - previous[joint]) > limit + 1e-9:
                    okay = False
            previous = point
        if okay:
            return points
        count += 1


def _serial_for_port(port: Path) -> str:
    if str(port) not in {"/dev/ttyACM0", "/dev/ttyACM1"}:
        raise RuntimeError(f"noncanonical_port:{port}")
    tty_device = (Path("/sys/class/tty") / port.name / "device").resolve()
    for directory in (tty_device, *tty_device.parents):
        candidate = directory / "serial"
        if candidate.is_file():
            value = candidate.read_text(encoding="utf-8").strip()
            if value:
                return value
    raise RuntimeError(f"usb_serial_not_found:{port}")


class PortLock:
    """Unprivileged process lock; TIOCEXCL seals the actual opened serial fd."""

    def __init__(self, role: str):
        runtime = Path(os.environ.get("XDG_RUNTIME_DIR", tempfile.gettempdir()))
        self.path = runtime / f"medicine-sorter-{os.getuid()}-{role}.lock"
        self.file = None

    def acquire(self) -> None:
        self.file = self.path.open("a+")
        fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def release(self) -> None:
        if self.file is not None:
            fcntl.flock(self.file.fileno(), fcntl.LOCK_UN)
            self.file.close()
            self.file = None


def _raw(bus, register: str) -> dict[str, int]:
    values = bus.sync_read(register, normalize=False, num_retry=0)
    if set(values) != set(JOINTS) or any(type(v) is not int for v in values.values()):
        raise RuntimeError(f"invalid_raw_register:{register}")
    return {joint: values[joint] for joint in JOINTS}


def _positions(bus) -> dict[str, float]:
    values = bus.sync_read("Present_Position", normalize=True, num_retry=0)
    if set(values) != set(JOINTS):
        raise RuntimeError("invalid_normalized_present")
    result = {joint: float(values[joint]) for joint in JOINTS}
    if any(not math.isfinite(value) for value in result.values()):
        raise RuntimeError("nonfinite_normalized_present")
    return result


class StrictWriteGate:
    """Block every write except the exact HOLD, motion, or Ctrl+C operation."""

    def __init__(self, bus):
        self.bus = bus
        self.original_sync_write = bus.sync_write
        self.mode = "closed"
        self.pending: tuple[str, dict[str, int | float], bool] | None = None
        self.counts = {"Goal_Position_raw_hold": 0, "Torque_Enable": 0,
                       "Goal_Position_motion": 0, "Goal_Position_ctrl_c_hold": 0,
                       "forbidden": 0}

        def denied(*_args, **_kwargs):
            self.counts["forbidden"] += 1
            raise RuntimeError("fixed_demo_forbidden_write")

        def checked(register, values, *args, **kwargs):
            pending, self.pending = self.pending, None
            normalized = kwargs.get("normalize", True)
            if args or kwargs.get("num_retry") != 0 or set(kwargs) - {"normalize", "num_retry"}:
                self.counts["forbidden"] += 1
                raise RuntimeError("fixed_demo_unexpected_write_signature")
            if (pending is None or register != pending[0] or dict(values) != pending[1]
                    or bool(normalized) != pending[2] or set(values) != set(JOINTS)):
                self.counts["forbidden"] += 1
                raise RuntimeError("fixed_demo_unarmed_sync_write")
            return self.original_sync_write(register, dict(values),
                                            normalize=normalized, num_retry=0)

        for name in ("write", "write_calibration", "configure_motors",
                     "enable_torque", "disable_torque"):
            if hasattr(bus, name):
                setattr(bus, name, denied)
        bus.sync_write = checked

    def _send(self, register: str, values: Mapping[str, int | float], normalize: bool) -> None:
        self.pending = (register, dict(values), normalize)
        try:
            self.bus.sync_write(register, dict(values), normalize=normalize, num_retry=0)
        finally:
            self.pending = None

    def atomic_goal_raw(self, values: Mapping[str, int]) -> None:
        if self.mode != "atomic" or self.counts["Goal_Position_raw_hold"]:
            raise RuntimeError("atomic_goal_not_allowed")
        self.counts["Goal_Position_raw_hold"] += 1
        self._send("Goal_Position", values, False)

    def atomic_torque_on(self) -> None:
        if (self.mode != "atomic" or self.counts["Torque_Enable"]
                or self.counts["Goal_Position_raw_hold"] != 1):
            raise RuntimeError("atomic_torque_not_allowed")
        self.counts["Torque_Enable"] += 1
        self._send("Torque_Enable", {joint: 1 for joint in JOINTS}, False)

    def arm_motion(self) -> None:
        if self.mode != "atomic":
            raise RuntimeError("motion_handoff_invalid")
        self.mode = "motion"

    def motion_goal(self, values: Mapping[str, float]) -> None:
        if self.mode != "motion":
            raise RuntimeError("motion_goal_not_armed")
        self.counts["Goal_Position_motion"] += 1
        self._send("Goal_Position", values, True)

    def ctrl_c_hold(self, values: Mapping[str, int]) -> None:
        if self.mode != "motion" or self.counts["Goal_Position_ctrl_c_hold"]:
            raise RuntimeError("ctrl_c_hold_not_allowed")
        self.counts["Goal_Position_ctrl_c_hold"] += 1
        self._send("Goal_Position", values, False)

    def close(self) -> None:
        self.mode = "closed"
        self.pending = None


def establish_hold(bus, writes: StrictWriteGate, *, sleep: Callable[[float], None] = time.sleep,
                   monotonic: Callable[[], float] = time.monotonic) -> dict[str, Any]:
    writes.mode = "atomic"
    present = _raw(bus, "Present_Position")
    torque = _raw(bus, "Torque_Enable")
    moving = _raw(bus, "Moving")
    if any(moving.values()):
        raise RuntimeError("moving_before_hold")
    if set(torque.values()) == {0}:
        writes.atomic_goal_raw(present)
        if _raw(bus, "Goal_Position") != present:
            raise RuntimeError("hold_goal_readback_mismatch")
        if set(_raw(bus, "Torque_Enable").values()) != {0}:
            raise RuntimeError("unexpected_torque_before_enable")
        writes.atomic_torque_on()
        hold_mode = "RESTORED_FROM_OFF"
    elif set(torque.values()) == {1}:
        goal = _raw(bus, "Goal_Position")
        if any(abs(goal[joint] - present[joint]) > 10 for joint in JOINTS):
            raise RuntimeError("already_on_goal_present_gap")
        hold_mode = "ALREADY_ON_NO_TOGGLE"
    else:
        raise RuntimeError("mixed_torque_state")
    expected_goal = _raw(bus, "Goal_Position")
    initial_present = _raw(bus, "Present_Position")
    started = monotonic()
    samples = 0
    while True:
        torque_now = _raw(bus, "Torque_Enable")
        goal_now = _raw(bus, "Goal_Position")
        present_now = _raw(bus, "Present_Position")
        moving_now = _raw(bus, "Moving")
        temperatures = {joint: int(bus.read("Present_Temperature", joint,
                                                    normalize=False, num_retry=0))
                        for joint in JOINTS}
        if set(torque_now.values()) != {1} or goal_now != expected_goal or any(moving_now.values()):
            raise RuntimeError("hold_stability_state_changed")
        if any(abs(present_now[joint] - initial_present[joint]) > 2 for joint in JOINTS):
            raise RuntimeError("hold_stability_present_drift")
        if any(not 0 <= value <= MAX_TEMPERATURE_C for value in temperatures.values()):
            raise RuntimeError("temperature_fault")
        samples += 1
        if monotonic() - started >= 3.0:
            break
        sleep(0.1)
    writes.arm_motion()
    return {"hold": hold_mode, "samples": samples, "writes": dict(writes.counts)}


def calibrated_bounds(robot) -> dict[str, tuple[float, float]]:
    bus = robot.bus
    if not bus.is_calibrated or not callable(getattr(bus, "_normalize", None)):
        raise RuntimeError("stored_calibration_not_loaded")
    result = {}
    for joint in JOINTS:
        motor_id = bus.motors[joint].id
        item = bus.calibration[joint]
        raw_min = item.range_min if hasattr(item, "range_min") else item["range_min"]
        raw_max = item.range_max if hasattr(item, "range_max") else item["range_max"]
        low = float(bus._normalize({motor_id: int(raw_min)})[motor_id])
        high = float(bus._normalize({motor_id: int(raw_max)})[motor_id])
        result[joint] = (min(low, high), max(low, high))
    return result


def ensure_in_bounds(values: Mapping[str, float], bounds: Mapping[str, tuple[float, float]]) -> None:
    violations = {joint: (values[joint], *bounds[joint]) for joint in JOINTS
                  if not bounds[joint][0] <= values[joint] <= bounds[joint][1]}
    if violations:
        raise RuntimeError(f"target_outside_calibrated_range:{violations}")


class HardwareSession:
    def __init__(self, config, *, include_leader: bool):
        robot = config.raw["robot"]
        self.follower_port = Path(robot["follower_port"])
        self.follower_serial = robot["follower_serial"]
        self.leader_port = Path(robot["leader_port"])
        self.leader_serial = robot.get("leader_serial")
        self.include_leader = include_leader
        self.follower_lock = PortLock("follower")
        self.leader_lock = PortLock("leader")
        self.follower = None
        self.leader = None
        self.writes = None
        self.bounds = None

    def connect(self) -> None:
        from lerobot.robots.so_follower import SO101Follower, SO101FollowerConfig
        from lerobot.teleoperators.so_leader import SO101Leader, SO101LeaderConfig

        if self.include_leader and (self.follower_port == self.leader_port
                                    or self.follower_serial == self.leader_serial):
            raise RuntimeError("leader_follower_identity_collision")
        if _serial_for_port(self.follower_port) != self.follower_serial:
            raise RuntimeError("follower_usb_serial_mismatch")
        if self.include_leader and _serial_for_port(self.leader_port) != self.leader_serial:
            raise RuntimeError("leader_usb_serial_mismatch")
        self.follower_lock.acquire()
        if self.include_leader:
            self.leader_lock.acquire()
        try:
            self.follower = SO101Follower(SO101FollowerConfig(
                port=str(self.follower_port), id="so-101", cameras={}, use_degrees=True,
                max_relative_target=None, disable_torque_on_disconnect=False))
            self.writes = StrictWriteGate(self.follower.bus)
            self.follower.bus.connect(handshake=False)
            fcntl.ioctl(self.follower.bus.port_handler.ser.fileno(), termios.TIOCEXCL)
            self.follower.configure = lambda: (_ for _ in ()).throw(RuntimeError("configure_forbidden"))
            self.bounds = calibrated_bounds(self.follower)
            if self.include_leader:
                self.leader = SO101Leader(SO101LeaderConfig(
                    port=str(self.leader_port), id="so-101"))
                StrictWriteGate(self.leader.bus)
                self.leader.bus.connect(handshake=False)
                fcntl.ioctl(self.leader.bus.port_handler.ser.fileno(), termios.TIOCEXCL)
                self.leader.configure = lambda: (_ for _ in ()).throw(RuntimeError("configure_forbidden"))
                if not self.leader.bus.is_calibrated:
                    raise RuntimeError("leader_stored_calibration_not_loaded")
                if set(_raw(self.leader.bus, "Torque_Enable").values()) != {0}:
                    raise RuntimeError("leader_must_be_torque_off")
        except BaseException:
            self.close()
            raise

    def ctrl_c_hold(self) -> bool:
        if self.follower is not None and self.writes is not None and self.writes.mode == "motion":
            self.writes.ctrl_c_hold(_raw(self.follower.bus, "Present_Position"))
            return True
        return False

    def close(self) -> None:
        if self.writes is not None:
            self.writes.close()
        first_error = None
        try:
            for robot in (self.leader, self.follower):
                bus = getattr(robot, "bus", None)
                if bus is None:
                    continue
                try:
                    if getattr(bus, "is_connected", False):
                        bus.disconnect(disable_torque=False)
                except BaseException as error:
                    if first_error is None:
                        first_error = error
                finally:
                    serial = getattr(getattr(bus, "port_handler", None), "ser", None)
                    if serial is not None and hasattr(serial, "close"):
                        serial.close()
        finally:
            self.leader_lock.release()
            self.follower_lock.release()
        if first_error is not None:
            raise first_error


def _relative_target(leader: Mapping[str, float], leader_origin: Mapping[str, float],
                     follower_origin: Mapping[str, float]) -> dict[str, float]:
    return {joint: follower_origin[joint] + (leader[f"{joint}.pos"] - leader_origin[f"{joint}.pos"])
            for joint in JOINTS}


def _slew_target(requested: Mapping[str, float], previous: Mapping[str, float],
                 settings: DemoSettings) -> dict[str, float]:
    delta = {joint: requested[joint] - previous[joint] for joint in JOINTS}
    fraction = 1.0
    for joint, value in delta.items():
        per_cycle_velocity = settings.velocity[joint] * settings.control_period_s
        limit = min(settings.max_gripper_step if joint == "gripper" else settings.max_step_deg,
                    per_cycle_velocity)
        if abs(value) > limit:
            fraction = min(fraction, limit / abs(value))
    return {joint: previous[joint] + fraction * delta[joint] for joint in JOINTS}


def teach(config, settings: DemoSettings, *, overwrite: bool = False,
          session_factory=HardwareSession) -> dict[str, Any]:
    if settings.pose_path.exists() and not overwrite:
        raise _fail("pose_file_already_exists", str(settings.pose_path), "new path or --overwrite",
                    "기존 티칭값을 보존하려면 파일을 백업해 주세요")
    session = session_factory(config, include_leader=True)
    captured: dict[str, dict[str, Any]] = {}
    old_terminal = None
    stopping = False

    def stop(_signum, _frame):
        nonlocal stopping
        stopping = True
        raise KeyboardInterrupt

    old_signals = {sig: signal.signal(sig, stop) for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        session.connect()
        hold = establish_hold(session.follower.bus, session.writes)
        leader_origin = dict(session.leader.get_action())
        follower_origin = _positions(session.follower.bus)
        previous = dict(follower_origin)
        print("티칭 시작: Enter=현재 자세 저장, q=중단, Ctrl+C=현재 위치 유지")
        if sys.stdin.isatty():
            old_terminal = termios.tcgetattr(sys.stdin.fileno())
            tty.setcbreak(sys.stdin.fileno())
        pose_index = 0
        while pose_index < len(POSE_NAMES) and not stopping:
            pose_name = POSE_NAMES[pose_index]
            leader_now = dict(session.leader.get_action())
            requested = _relative_target(leader_now, leader_origin, follower_origin)
            ensure_in_bounds(requested, session.bounds)
            emitted = _slew_target(requested, previous, settings)
            if any(abs(emitted[j] - previous[j]) >
                   (settings.max_gripper_step if j == "gripper" else settings.max_step_deg) + 1e-9
                   for j in JOINTS):
                raise RuntimeError("two_degree_slew_violation")
            if any(abs(emitted[j] - previous[j]) > 1e-9 for j in JOINTS):
                session.writes.motion_goal(emitted)
                previous = emitted
            print(f"\r[{pose_index + 1}/{len(POSE_NAMES)}] {pose_name} 자세에서 Enter ",
                  end="", flush=True)
            readable, _, _ = select.select([sys.stdin], [], [], settings.control_period_s)
            if not readable:
                continue
            key = sys.stdin.read(1)
            if key.lower() == "q":
                raise KeyboardInterrupt
            if key not in ("\n", "\r"):
                continue
            if any(_raw(session.follower.bus, "Moving").values()):
                print("\n아직 움직이는 중입니다. 정지 후 다시 Enter를 누르세요.")
                continue
            raw_present = _raw(session.follower.bus, "Present_Position")
            raw_goal = _raw(session.follower.bus, "Goal_Position")
            if any(abs(raw_goal[j] - raw_present[j]) > 10 for j in JOINTS):
                print("\nGoal-Present가 아직 수렴하지 않았습니다. 잠시 뒤 다시 Enter를 누르세요.")
                continue
            captured[pose_name] = {
                "position": _positions(session.follower.bus),
                "present_raw": raw_present,
                "captured_at_utc": datetime.now(timezone.utc).isoformat(),
            }
            pose_index += 1
            print(f"\n저장: {pose_name}")
        if stopping:
            raise KeyboardInterrupt
        save_pose_file(settings.pose_path, follower_serial=session.follower_serial, poses=captured)
        return {"status": "TEACH_COMPLETE", "pose_file": str(settings.pose_path),
                "pose_count": len(captured), "hold": hold,
                "write_counts": dict(session.writes.counts)}
    except KeyboardInterrupt:
        held = session.ctrl_c_hold()
        code = "teach_stopped_current_position_held" if held else "teach_stopped_before_motion_arm"
        raise _fail(code, len(captured), str(len(POSE_NAMES)),
                    "주변과 follower Torque/Goal 상태를 확인한 뒤 teach를 처음부터 다시 실행해 주세요")
    finally:
        if old_terminal is not None:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_terminal)
        for sig, handler in old_signals.items():
            signal.signal(sig, handler)
        session.close()


def _gripper_only(current: Mapping[str, float], taught: Mapping[str, float]) -> dict[str, float]:
    result = dict(current)
    result["gripper"] = taught["gripper"]
    return result


def execute_segment(session: HardwareSession, target: Mapping[str, float], settings: DemoSettings,
                    *, sleep: Callable[[float], None] = time.sleep) -> None:
    ensure_in_bounds(target, session.bounds)
    start = _positions(session.follower.bus)
    for point in smooth_interpolation(start, target, settings):
        session.writes.motion_goal(point)
        sleep(settings.control_period_s)
    deadline = time.monotonic() + settings.settle_timeout_s
    while True:
        present = _positions(session.follower.bus)
        moving = _raw(session.follower.bus, "Moving")
        if (not any(moving.values()) and
                all(abs(present[j] - target[j]) <= settings.settle_tolerance[j] for j in JOINTS)):
            break
        if time.monotonic() >= deadline:
            raise RuntimeError("segment_settle_timeout")
        time.sleep(settings.control_period_s)
    if set(_raw(session.follower.bus, "Torque_Enable").values()) != {1}:
        raise RuntimeError("torque_changed_during_demo")
    temperatures = [int(session.follower.bus.read("Present_Temperature", joint,
                                                  normalize=False, num_retry=0))
                    for joint in JOINTS]
    if any(not 0 <= value <= MAX_TEMPERATURE_C for value in temperatures):
        raise RuntimeError("temperature_fault")


def run_demo(config, settings: DemoSettings, *, dry_run: bool, step: bool,
             snapshot_loader: Callable[[str], dict[str, Any]] = fetch_snapshot,
             session_factory=HardwareSession) -> dict[str, Any]:
    snapshot = snapshot_loader(settings.snapshot_url)
    routes, ignored = routes_from_snapshot(snapshot, settings)
    stages = stage_names_for_routes(routes)
    result = {
        "status": "FIXED_DEMO_PLAN" if dry_run else "FIXED_DEMO_COMPLETE",
        "frame_sequence": snapshot.get("sequence"),
        "frame_age_s": snapshot.get("frame_age_s"),
        "slot_roi_status": settings.roi_status,
        "routes": [route.as_dict() for route in routes],
        "ignored_markers": ignored,
        "stages": stages,
        "yolo": {"optional": True, "detections_visible_in_camera_ui": True,
                 "detection_count": len(snapshot.get("detections", []))},
        "serial_open": 0,
        "motor_command": 0,
    }
    if dry_run:
        return result
    if settings.roi_status != "verified" and not step:
        raise _fail("provisional_slot_roi_requires_step", settings.roi_status, "--step",
                    "dry-run 결과의 ID·칸을 확인한 뒤 --step으로 감독 실행해 주세요")
    poses = load_pose_file(settings.pose_path,
                           expected_serial=config.raw["robot"]["follower_serial"])
    session = session_factory(config, include_leader=False)
    stopping = False

    def stop(_signum, _frame):
        nonlocal stopping
        stopping = True
        raise KeyboardInterrupt

    old_signals = {sig: signal.signal(sig, stop) for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        if step:
            print(json.dumps(result, ensure_ascii=False, indent=2))
            input("위 ID→칸→바구니 계획과 주변 clear를 확인했으면 Enter: ")
        session.connect()
        hold = establish_hold(session.follower.bus, session.writes)
        current = _positions(session.follower.bus)
        for index, stage in enumerate(stages, start=1):
            if stopping:
                raise KeyboardInterrupt
            target = (_gripper_only(current, poses[stage])
                      if stage in {"gripper_open", "gripper_closed"}
                      else poses[stage])
            if step:
                input(f"[{index}/{len(stages)}] {stage} 실행: 주변을 확인하고 Enter ")
            if stopping:
                raise KeyboardInterrupt
            execute_segment(session, target, settings)
            current = dict(target)
        result.update({"hold": hold, "serial_open": 1,
                       "motor_command": session.writes.counts["Goal_Position_motion"],
                       "write_counts": dict(session.writes.counts)})
        return result
    except KeyboardInterrupt:
        connected = session.follower is not None and session.writes is not None
        if connected:
            held = session.ctrl_c_hold()
            code = "demo_stopped_current_position_held" if held else "demo_stopped_before_motion_arm"
            raise _fail(code, True, "supervised completion",
                        "follower Torque/Goal 상태와 주변을 확인해 주세요")
        raise _fail("demo_stopped_before_robot_connect", True, "plan confirmation",
                    "로봇 명령은 없었으며 필요할 때 다시 실행해 주세요")
    finally:
        for sig, handler in old_signals.items():
            signal.signal(sig, handler)
        session.close()
