"""LeLab UI adapter for guarded no-reconfigure relative-start teleoperation.

The adapter never records and never calls calibration/configuration or torque
APIs.  It owns both serial buses in one worker, keeps the UI state active until
both buses and leases are released, and only returns ARMED after the retained
three-second current-HOLD gate and fresh-origin capture pass.
"""

from __future__ import annotations

import fcntl
import logging
import math
import os
from pathlib import Path
import termios
import threading
import time
from typing import Any, Callable

from .relative_start_teleop import JOINTS, calibrated_action_bounds
from .so101_exclusive_bus import ExclusiveFollowerLease, SystemBusProbe
from .supervised_teaching_from_current_hold import (
    _raw, make_write_firewall, run_teaching_from_hold,
)
from .teleop_cycle_trace import load_grasp_fk, read_same_owner_diagnostics
from .temporary_elbow_direction_guard import guarded_elbow_send


LOGGER = logging.getLogger(__name__)
FOLLOWER_PORT = Path("/dev/ttyACM1")
LEADER_PORT = Path("/dev/ttyACM0")
FOLLOWER_SERIAL = "5AE6058306"
LEADER_SERIAL = "5AE6085272"
CONFIG_FILE = "so-101.json"
CONFIG_ID = "so-101"
URDF_PATH = Path("/home/jetson3/so101-c-empirical-trace-20261014/so101_new_calib.urdf")
TCP_PATH = Path("/home/jetson3/so101-c-empirical-trace-20261014/c_pick_grasp_tcp_candidate_20261012.json")

_state_lock = threading.Lock()
_send_lock = threading.Lock()
_phase = "INACTIVE"
_worker: threading.Thread | None = None
_stop_event: threading.Event | None = None
_startup_event: threading.Event | None = None
_session_token: object | None = None
_last_error: str | None = None
_last_result: dict[str, Any] | None = None
_joint_cache: dict[str, float] | None = None
_joint_cache_time = 0.0
_inactive_callback: Callable[[], None] | None = None


def _request_value(request: Any, name: str) -> str:
    value = getattr(request, name, None)
    if not isinstance(value, str):
        raise RuntimeError(f"safe_ui_{name}_missing")
    return value


def _validate_request(request: Any) -> None:
    expected = {
        "leader_port": str(LEADER_PORT),
        "follower_port": str(FOLLOWER_PORT),
        "leader_config": CONFIG_FILE,
        "follower_config": CONFIG_FILE,
    }
    for field, required in expected.items():
        if _request_value(request, field) != required:
            raise RuntimeError(f"safe_ui_requires_{field}_{required}")


def _controls_available(token: object) -> bool:
    from . import record, rollout

    with _state_lock:
        owns_session = token is _session_token and _phase != "INACTIVE"
    return owns_session and not record.recording_active and not rollout.inference_active


class _OwnSessionProbe(SystemBusProbe):
    """Keep external controls idle while accepting this adapter's own UI flag."""

    def __init__(self, token: object):
        self.token = token

    def lelab_controls_idle(self) -> bool:
        return _controls_available(self.token)


def _goals_allowed(token: object) -> bool:
    with _state_lock:
        return (token is _session_token and _phase == "ARMED" and
                _stop_event is not None and not _stop_event.is_set())


def _cache_diagnostics(values: dict[str, Any]) -> None:
    mapping = {
        "shoulder_pan": "Rotation", "shoulder_lift": "Pitch",
        "elbow_flex": "Elbow", "wrist_flex": "Wrist_Pitch",
        "wrist_roll": "Wrist_Roll", "gripper": "Jaw",
    }
    positions = values["present_degree_or_percent"]
    cached = {urdf: math.radians(float(positions[motor]))
              for motor, urdf in mapping.items()}
    with _state_lock:
        global _joint_cache, _joint_cache_time
        _joint_cache = cached
        _joint_cache_time = time.time()


def _run_session(token: object, request: Any) -> None:
    global _phase, _worker, _session_token, _last_error, _last_result
    global _inactive_callback
    from lerobot.robots.so_follower import SO101Follower, SO101FollowerConfig
    from lerobot.teleoperators.so_leader import SO101Leader, SO101LeaderConfig

    follower_lease = ExclusiveFollowerLease(
        _OwnSessionProbe(token), port=FOLLOWER_PORT, serial_short=FOLLOWER_SERIAL)
    leader_lease = ExclusiveFollowerLease(
        _OwnSessionProbe(token), port=LEADER_PORT, serial_short=LEADER_SERIAL,
        lock_path=Path(follower_lease.lock_path).with_name("so101-leader-program.lock"))
    follower = leader = None
    try:
        follower_lease.acquire()
        leader_lease.acquire()
        follower = SO101Follower(SO101FollowerConfig(
            port=str(FOLLOWER_PORT), id=CONFIG_ID, cameras={}, use_degrees=True,
            max_relative_target=None, disable_torque_on_disconnect=False))
        leader = SO101Leader(SO101LeaderConfig(port=str(LEADER_PORT), id=CONFIG_ID))
        make_write_firewall(follower.bus, goals_enabled=lambda: _goals_allowed(token))
        make_write_firewall(leader.bus, goals_enabled=lambda: False)
        follower.bus.connect(handshake=False)
        fcntl.ioctl(follower.bus.port_handler.ser.fileno(), termios.TIOCEXCL)
        follower_lease.mark_connected()
        leader.bus.connect(handshake=False)
        fcntl.ioctl(leader.bus.port_handler.ser.fileno(), termios.TIOCEXCL)
        leader_lease.mark_connected()
        if not follower.bus.is_calibrated or not leader.bus.is_calibrated:
            raise RuntimeError("stored_calibration_not_loaded")
        follower.configure = leader.configure = lambda: (_ for _ in ()).throw(
            RuntimeError("safe_ui_configure_forbidden"))
        fk = load_grasp_fk(URDF_PATH, TCP_PATH)
        bounds = calibrated_action_bounds(follower)

        def ensure_owned() -> None:
            follower_lease.ensure_exclusive()
            leader_lease.ensure_exclusive()

        def diagnostics() -> dict[str, Any]:
            ensure_owned()
            values = read_same_owner_diagnostics(follower, fk)
            _cache_diagnostics(values)
            return values

        def read_leader() -> dict[str, float]:
            ensure_owned()
            return dict(leader.get_action())

        def read_follower_action() -> dict[str, float]:
            ensure_owned()
            values = follower.bus.sync_read("Present_Position")
            return {f"{name}.pos": float(values[name]) for name in JOINTS}

        def guarded_send(action: dict[str, float], previous_elbow: float | None):
            with _send_lock:
                if not _goals_allowed(token):
                    return None
                ensure_owned()
                return guarded_elbow_send(follower, action, previous_elbow, LOGGER)

        def enable_goals() -> None:
            global _phase
            with _send_lock:
                with _state_lock:
                    if (token is not _session_token or _stop_event is None or
                            _stop_event.is_set()):
                        raise RuntimeError("safe_ui_stopped_before_arming")
                    _phase = "ARMED"
                    assert _startup_event is not None
                    _startup_event.set()

        pre_connect = diagnostics()
        result = run_teaching_from_hold(
            trace=None, recorder_off=True, pre_connect=pre_connect,
            read_leader=read_leader,
            read_leader_torque=lambda: _raw(leader.bus, "Torque_Enable"),
            read_follower_action=read_follower_action,
            read_diagnostics=diagnostics,
            read_follower_torque=lambda: _raw(follower.bus, "Torque_Enable"),
            bounds=bounds, send_guarded=guarded_send, enable_goals=enable_goals,
            arm_confirm=lambda: _stop_event is not None and not _stop_event.is_set(),
            stop_requested=lambda: _stop_event is None or _stop_event.is_set(),
            hold_policy="quantized", max_run_s=180.0)
        with _state_lock:
            if token is _session_token:
                _last_result = result
    except Exception as error:
        LOGGER.exception("Safe UI teleoperation failed")
        with _state_lock:
            if token is _session_token:
                _last_error = f"{type(error).__name__}:{error}"
    finally:
        # Never use the default device disconnect: it may alter torque.
        if leader is not None and leader.bus.is_connected:
            leader.bus.disconnect(disable_torque=False)
        if follower is not None and follower.bus.is_connected:
            follower.bus.disconnect(disable_torque=False)
        leader_lease.release()
        follower_lease.release()
        callback = None
        with _state_lock:
            if token is _session_token:
                if _startup_event is not None:
                    _startup_event.set()
                _phase = "INACTIVE"
                _worker = None
                _session_token = None
                callback = _inactive_callback
                _inactive_callback = None
        if callback is not None:
            try:
                callback()
            except Exception:
                LOGGER.exception("Safe UI inactive callback failed")


def start(request: Any, websocket_manager=None,
          on_inactive: Callable[[], None] | None = None) -> dict[str, Any]:
    """Start and wait until the guarded worker is ARMED or fails."""
    del websocket_manager  # Joint polling uses the same-owner cache below.
    global _phase, _worker, _stop_event, _startup_event, _session_token
    global _last_error, _last_result, _joint_cache, _joint_cache_time
    global _inactive_callback
    try:
        _validate_request(request)
    except Exception as error:
        return {"success": False, "message": str(error)}
    from . import record, rollout
    with _state_lock:
        if _phase != "INACTIVE":
            return {"success": False, "message": "Safe teleoperation is already active"}
        if record.recording_active or rollout.inference_active:
            return {"success": False, "message": "Recording or inference is active"}
        token = object()
        _session_token = token
        _stop_event = threading.Event()
        _startup_event = threading.Event()
        _last_error = None
        _last_result = None
        _joint_cache = None
        _joint_cache_time = 0.0
        _inactive_callback = on_inactive
        _phase = "STARTING"
        worker = threading.Thread(target=_run_session, args=(token, request),
                                  name="safe-ui-teleoperation-worker", daemon=True)
        _worker = worker
        startup_event = _startup_event
        worker.start()
    if not startup_event.wait(timeout=15.0):
        with _send_lock:
            if _stop_event is not None:
                _stop_event.set()
        return {"success": False, "message": "Safe teleoperation startup timed out"}
    with _state_lock:
        if token is _session_token and _phase == "ARMED":
            return {"success": True, "message": "Safe relative-start teleoperation armed",
                    "leader_port": str(LEADER_PORT), "follower_port": str(FOLLOWER_PORT),
                    "recorder": False, "first_goal_skipped": True}
        message = _last_error or "Safe teleoperation stopped before arming"
    return {"success": False, "message": message}


def stop() -> dict[str, Any]:
    global _phase
    with _state_lock:
        if _phase == "INACTIVE" or _stop_event is None:
            return {"success": False, "message": "No safe teleoperation session is active"}
        worker = _worker
    # After this lock is acquired no later Goal packet can enter guarded_send.
    with _send_lock:
        assert _stop_event is not None
        _stop_event.set()
        with _state_lock:
            if _phase != "INACTIVE":
                _phase = "STOPPING"
    if worker is not None:
        worker.join(timeout=8.0)
    if worker is not None and worker.is_alive():
        return {"success": False,
                "message": "Stop accepted; worker is still cleaning up",
                "stopping": True}
    return {"success": True, "message": "Safe teleoperation stopped"}


def status() -> dict[str, Any]:
    with _state_lock:
        active = _phase != "INACTIVE"
        return {"teleoperation_active": active, "phase": _phase,
                "available_controls": {"stop_teleoperation": active},
                "last_error": _last_error, "message": "Safe teleoperation status"}


def joint_positions() -> dict[str, Any]:
    with _state_lock:
        if _joint_cache is None:
            return {"success": False, "message": "No cached safe teleoperation telemetry"}
        return {"success": True, "joint_positions": dict(_joint_cache),
                "timestamp": _joint_cache_time}
