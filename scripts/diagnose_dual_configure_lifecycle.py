#!/usr/bin/env python3
"""Instrument the SO-101 dual-device recording initialization sequence.

WARNING: Unlike the read-only diagnostics, this script intentionally repeats
the existing calibration/configure sequence and toggles torque.  Run it only
after explicit onsite safety confirmation.  It never writes Goal_Position,
changes baudrate/return-delay arguments, opens cameras, or reconnects USB.

Two bounded trials distinguish the first follower read after:

1. both calibration writes plus follower configure; and
2. the exact recording order through follower and leader configure.

Every public register write/read and per-motor torque operation is timestamped.
The checkpoint reads call the installed SDK's low-level group-read once per
attempt so the numeric communication result is preserved instead of hidden by
the high-level retry exception.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


MOTOR_IDS = [1, 2, 3, 4, 5, 6]


def now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="milliseconds")


def error_record(exc: BaseException) -> dict[str, str]:
    return {"type": type(exc).__name__, "message": str(exc)}


def serial_number(port: str) -> str | None:
    from serial.tools import list_ports

    resolved = os.path.realpath(port)
    for candidate in list_ports.comports(include_links=True):
        if candidate.device in (port, resolved):
            return candidate.serial_number
    return None


def add_event(events: list[dict[str, Any]], trial_started: float, **fields: Any) -> None:
    events.append(
        {
            "at": now(),
            "elapsed_ms": round((time.monotonic() - trial_started) * 1000, 3),
            **fields,
        }
    )


def instrument_method(
    obj: Any,
    method_name: str,
    role: str,
    events: list[dict[str, Any]],
    trial_started: float,
) -> None:
    original: Callable[..., Any] = getattr(obj, method_name)

    def wrapped(*args: Any, **kwargs: Any) -> Any:
        safe_args = [repr(value) for value in args]
        safe_kwargs = {key: repr(value) for key, value in kwargs.items()}
        add_event(
            events,
            trial_started,
            kind="call_start",
            role=role,
            method=method_name,
            args=safe_args,
            kwargs=safe_kwargs,
        )
        started = time.monotonic()
        try:
            value = original(*args, **kwargs)
        except Exception as exc:
            add_event(
                events,
                trial_started,
                kind="call_error",
                role=role,
                method=method_name,
                duration_ms=round((time.monotonic() - started) * 1000, 3),
                error=error_record(exc),
            )
            raise
        add_event(
            events,
            trial_started,
            kind="call_ok",
            role=role,
            method=method_name,
            duration_ms=round((time.monotonic() - started) * 1000, 3),
        )
        return value

    setattr(obj, method_name, wrapped)


def instrument_bus(bus: Any, role: str, events: list[dict[str, Any]], trial_started: float) -> None:
    # write() captures every calibration/configure register operation,
    # including the per-motor Torque_Enable and Lock writes. read() captures
    # the Phase reads inside configure_motors. The public torque wrappers mark
    # the aggregate operation without changing its implementation.
    for method_name in ("write", "read", "enable_torque", "disable_torque"):
        instrument_method(bus, method_name, role, events, trial_started)


def input_waiting(bus: Any) -> int | None:
    serial_obj = getattr(bus.port_handler, "ser", None)
    if serial_obj is None:
        return None
    try:
        return int(serial_obj.in_waiting)
    except Exception:
        return None


def raw_group_read(bus: Any, data_name: str) -> dict[str, Any]:
    from lerobot.motors.motors_bus import get_address

    models = [motor.model for motor in bus.motors.values()]
    model = models[0]
    addr, length = get_address(bus.model_ctrl_table, model, data_name)
    before = input_waiting(bus)
    started = time.monotonic()
    try:
        values, comm = bus._sync_read(
            addr,
            length,
            MOTOR_IDS,
            num_retry=0,
            raise_on_error=False,
            err_msg=f"diagnostic {data_name}",
        )
        result = {
            "ok": bool(bus._is_comm_success(comm)),
            "comm": int(comm),
            "comm_text": bus.packet_handler.getTxRxResult(comm),
            "values": {str(key): value for key, value in values.items()},
        }
    except Exception as exc:
        result = {"ok": False, "exception": error_record(exc)}
    result.update(
        {
            "data_name": data_name,
            "duration_ms": round((time.monotonic() - started) * 1000, 3),
            "input_waiting_before": before,
            "input_waiting_after": input_waiting(bus),
        }
    )
    return result


def checkpoint(bus: Any, attempts: int = 3) -> dict[str, Any]:
    position_attempts: list[dict[str, Any]] = []
    for attempt in range(1, attempts + 1):
        item = raw_group_read(bus, "Present_Position")
        item["attempt"] = attempt
        position_attempts.append(item)
        if attempt < attempts:
            time.sleep(0.02)
    return {
        "at": now(),
        "position_attempts": position_attempts,
        "torque_enable": raw_group_read(bus, "Torque_Enable"),
        "voltage": raw_group_read(bus, "Present_Voltage"),
    }


def run_stage(
    trial: dict[str, Any],
    trial_started: float,
    name: str,
    operation: Callable[[], Any],
) -> bool:
    add_event(trial["events"], trial_started, kind="stage_start", stage=name)
    started = time.monotonic()
    try:
        operation()
    except Exception as exc:
        trial["fatal_error"] = {"stage": name, **error_record(exc)}
        add_event(
            trial["events"],
            trial_started,
            kind="stage_error",
            stage=name,
            duration_ms=round((time.monotonic() - started) * 1000, 3),
            error=error_record(exc),
        )
        return False
    add_event(
        trial["events"],
        trial_started,
        kind="stage_ok",
        stage=name,
        duration_ms=round((time.monotonic() - started) * 1000, 3),
    )
    return True


def run_trial(
    name: str,
    include_leader_configure: bool,
    args: argparse.Namespace,
    *,
    perform_prewrite_reads: bool = True,
    instrument_calls: bool = True,
) -> dict[str, Any]:
    from lerobot.robots.so_follower import SO101Follower, SO101FollowerConfig
    from lerobot.teleoperators.so_leader import SO101Leader, SO101LeaderConfig

    trial_started = time.monotonic()
    trial: dict[str, Any] = {
        "name": name,
        "started_at": now(),
        "include_leader_configure": include_leader_configure,
        "perform_prewrite_reads": perform_prewrite_reads,
        "instrument_calls": instrument_calls,
        "events": [],
        "checkpoints": {},
        "fatal_error": None,
        "teardown": [],
    }
    robot = SO101Follower(
        SO101FollowerConfig(port=args.follower_port, id=args.config_id, cameras={})
    )
    leader = SO101Leader(SO101LeaderConfig(port=args.leader_port, id=args.config_id))
    trial["calibration_entries"] = {
        "follower": len(robot.calibration),
        "leader": len(leader.calibration),
    }
    if trial["calibration_entries"] != {"follower": 6, "leader": 6}:
        trial["fatal_error"] = {
            "stage": "load_calibration",
            "type": "RuntimeError",
            "message": "expected six calibration entries for each device",
        }
        trial["finished_at"] = now()
        return trial

    follower_connected = leader_connected = False
    try:
        if instrument_calls:
            instrument_bus(robot.bus, "follower", trial["events"], trial_started)
            instrument_bus(leader.bus, "leader", trial["events"], trial_started)

        if not run_stage(trial, trial_started, "follower_connect", robot.bus.connect):
            return trial
        follower_connected = True
        if not run_stage(trial, trial_started, "leader_connect", leader.bus.connect):
            return trial
        leader_connected = True

        if perform_prewrite_reads:
            trial["checkpoints"]["before_writes_follower"] = checkpoint(robot.bus, attempts=1)
            trial["checkpoints"]["before_writes_leader"] = checkpoint(leader.bus, attempts=1)

        if not run_stage(
            trial,
            trial_started,
            "follower_write_calibration",
            lambda: robot.bus.write_calibration(robot.calibration),
        ):
            return trial
        if not run_stage(
            trial,
            trial_started,
            "leader_write_calibration",
            lambda: leader.bus.write_calibration(leader.calibration),
        ):
            return trial
        if not run_stage(trial, trial_started, "follower_configure", robot.configure):
            return trial

        if include_leader_configure:
            if not run_stage(trial, trial_started, "leader_configure", leader.configure):
                return trial
            checkpoint_name = "after_follower_and_leader_configure"
        else:
            checkpoint_name = "after_follower_configure_before_leader_configure"

        # This is deliberately the first follower read after the target
        # configure boundary. No RX clear or settle delay is inserted.
        trial["checkpoints"][checkpoint_name] = checkpoint(robot.bus, attempts=3)
        trial["checkpoints"][checkpoint_name + "_leader"] = checkpoint(leader.bus, attempts=1)
        trial["sequence_complete"] = True
        return trial
    finally:
        # Explicitly make both arms passive before closing. disconnect(False)
        # then avoids a second implicit torque write.
        for role, bus, connected in (
            ("leader", leader.bus, leader_connected),
            ("follower", robot.bus, follower_connected),
        ):
            if not connected:
                continue
            try:
                bus.disable_torque(num_retry=2)
                trial["teardown"].append({"role": role, "disable_torque": "ok"})
            except Exception as exc:
                trial["teardown"].append(
                    {"role": role, "disable_torque": "error", "error": error_record(exc)}
                )
            try:
                bus.disconnect(disable_torque=False)
                trial["teardown"].append({"role": role, "disconnect": "ok"})
            except Exception as exc:
                trial["teardown"].append(
                    {"role": role, "disconnect": "error", "error": error_record(exc)}
                )
        trial["finished_at"] = now()
        trial["duration_ms"] = round((time.monotonic() - trial_started) * 1000, 3)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--follower-port", default="/dev/ttyACM0")
    parser.add_argument("--leader-port", default="/dev/ttyACM1")
    parser.add_argument("--follower-serial", required=True)
    parser.add_argument("--leader-serial", required=True)
    parser.add_argument("--config-id", default="so-101")
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--mode",
        choices=("instrumented-two-stage", "cold-full-uninstrumented"),
        default="instrumented-two-stage",
    )
    args = parser.parse_args()

    report: dict[str, Any] = {
        "tool": "diagnose_dual_configure_lifecycle",
        "started_at": now(),
        "safety": {
            "explicit_onsite_approval_required": True,
            "calibration_and_configure_writes": True,
            "torque_toggles": True,
            "goal_position_writes": False,
            "baudrate_change": False,
            "return_delay_override": False,
            "usb_reconnect": False,
            "camera_access": False,
        },
        "ports": {
            "follower": {
                "path": args.follower_port,
                "serial": serial_number(args.follower_port),
            },
            "leader": {"path": args.leader_port, "serial": serial_number(args.leader_port)},
        },
        "trials": [],
    }
    if report["ports"]["follower"]["serial"] != args.follower_serial:
        raise RuntimeError("follower serial mismatch; no port opened")
    if report["ports"]["leader"]["serial"] != args.leader_serial:
        raise RuntimeError("leader serial mismatch; no port opened")

    if args.mode == "cold-full-uninstrumented":
        report["trials"].append(
            run_trial(
                "cold_full_record_configure_order",
                True,
                args,
                perform_prewrite_reads=False,
                instrument_calls=False,
            )
        )
        expected_trials = 1
    else:
        first = run_trial("follower_configure_boundary", False, args)
        report["trials"].append(first)
        if first.get("fatal_error") is None:
            time.sleep(1.0)
            report["trials"].append(run_trial("full_record_configure_order", True, args))
        expected_trials = 2

    register_writes = [
        event.get("args", [None])[0]
        for trial in report["trials"]
        for event in trial.get("events", [])
        if event.get("kind") == "call_start" and event.get("method") == "write"
    ]
    report["observed_goal_position_write"] = any(
        value in ("'Goal_Position'", '"Goal_Position"') for value in register_writes
    )
    report["ok"] = (
        len(report["trials"]) == expected_trials
        and all(trial.get("fatal_error") is None for trial in report["trials"])
        and not report["observed_goal_position_write"]
        and all(
            {
                item["role"]
                for item in trial["teardown"]
                if item.get("disable_torque") == "ok"
            }
            == {"follower", "leader"}
            and {
                item["role"]
                for item in trial["teardown"]
                if item.get("disconnect") == "ok"
            }
            == {"follower", "leader"}
            for trial in report["trials"]
        )
    )
    report["finished_at"] = now()
    Path(args.output).write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "ok": report["ok"],
                "trials": len(report["trials"]),
                "fatal_errors": [trial.get("fatal_error") for trial in report["trials"]],
                "goal_position_write": report["observed_goal_position_write"],
                "output": args.output,
            },
            ensure_ascii=False,
        )
    )
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
