#!/usr/bin/env python3
"""One human-gated recorded C-to-red phase after a separately verified predecessor.

Dry-run is the default. Live mode executes exactly one of grasp, transport or
place; it never advances to another phase and never runs retreat implicitly.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

from scripts.prepare_c_red_phases import audit_phase, load_phases
try:  # The deployed trial runs from its directory, with replay at its root.
    from replay_c_red_approach import read_stillness, run_timed_segment
except ModuleNotFoundError:
    from scripts.replay_c_red_approach import read_stillness, run_timed_segment
from scripts.so101_exclusive_bus import ExclusiveFollowerLease, SystemBusProbe
from scripts.so101_follower_transport import SO101FollowerTransport
from scripts.staged_cycle_execution import JOINT_UNITS


PHASE_CONFIRMATION = {
    "grasp": "C HELD",
    "transport": "ABOVE RED",
    "place": "C IN RED",
}


def run_one_phase(phase: str, candidate: Path, *, time_scale: float = 4.0,
                  live: bool = False, confirm_scope: str | None = None,
                  input_fn=input, transport_factory=None) -> int:
    if phase not in PHASE_CONFIRMATION:
        raise ValueError("phase_not_live_supported")
    points = load_phases(candidate)[phase]
    result = audit_phase(phase, points, time_scale=time_scale)
    print(json.dumps({"dry_run": result}, separators=(",", ":")), flush=True)
    if not live:
        print("DRY_RUN: no port opened; no send_action", flush=True)
        return 0
    if confirm_scope != phase:
        raise ValueError("live_phase_scope_mismatch")
    if input_fn(f"C/scene/site stop verified. Type RUN {phase.upper()}: ") != f"RUN {phase.upper()}":
        print("NOT_RUN", flush=True)
        return 2
    factory = transport_factory or (lambda: SO101FollowerTransport.open_live(
        ExclusiveFollowerLease(SystemBusProbe()), approval_confirmed=True))
    transport = factory()
    progress = {"sent": 0, "last_seq": points[0]["seq"]}
    outcome = 1
    try:
        def mark(count, seq):
            progress.update(sent=count, last_seq=seq)
            print(f"sent={count} last_seq={seq}", flush=True)

        sent = run_timed_segment(
            points, transport, time_scale=time_scale, progress=mark,
            on_feedback=lambda point, command, feedback: print(json.dumps({
                "seq": point["seq"], "command": command,
                "feedback": feedback.positions,
                "feedback_monotonic": feedback.received_monotonic,
                "command_feedback_abs_error": {
                    name: abs(command[name] - feedback.positions[name]) for name in JOINT_UNITS
                }, "guard_state": "PENDING_CHECK"}, separators=(",", ":")), flush=True),
            on_timing=lambda timing: print(json.dumps({"timing": timing},
                                                separators=(",", ":")), flush=True),
            on_sample_timing=lambda timing: print(json.dumps({"sample_timing": timing},
                                                       separators=(",", ":")), flush=True),
        )
        if sent != len(points) - 1:
            raise RuntimeError("phase_target_count_incomplete")
        print(f"PHASE_TRANSMISSION_ENDED phase={phase} goals={sent}", flush=True)
        outcome = 0
    except (KeyboardInterrupt, Exception) as error:
        print(f"ABORT phase={phase} last_target={progress['sent']} "
              f"last_seq={progress['last_seq']}: {type(error).__name__}: {error}",
              file=sys.stderr, flush=True)
    finally:
        transport.stop_commands()
        try:
            still = read_stillness(transport)
            print(f"encoder_stillness={'PASS' if still else 'NOT_VERIFIED'}", flush=True)
            physically_stopped = input_fn("Arm stopped and scene safe? Type STOPPED: ") == "STOPPED"
            if not still or not physically_stopped:
                outcome = 1
                print("physical_stop=NOT_VERIFIED", flush=True)
            else:
                print("physical_stop=FEEDBACK_AND_HUMAN_CONFIRMED", flush=True)
                if outcome == 0:
                    phrase = PHASE_CONFIRMATION[phase]
                    if input_fn(f"Site phase result confirmed? Type {phrase}: ") != phrase:
                        outcome = 1
                        print("physical_phase_result=NOT_VERIFIED", flush=True)
                    else:
                        print(f"physical_phase_result={phrase.replace(' ', '_')}", flush=True)
        except (KeyboardInterrupt, Exception) as error:
            outcome = 1
            print(f"physical_stop=NOT_VERIFIED ({type(error).__name__})",
                  file=sys.stderr, flush=True)
        finally:
            transport.robot.bus.disconnect(disable_torque=False)
            transport.lease.release()
    return outcome


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--phase", required=True, choices=list(PHASE_CONFIRMATION))
    parser.add_argument("--time-scale", type=float, default=4.0)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-scope", choices=list(PHASE_CONFIRMATION))
    args = parser.parse_args(argv)
    if not math.isfinite(args.time_scale) or args.time_scale < 2.0:
        parser.error("time scale must be at least 2")
    try:
        return run_one_phase(args.phase, args.candidate, time_scale=args.time_scale,
                             live=args.live, confirm_scope=args.confirm_scope)
    except (OSError, ValueError) as error:
        parser.exit(2, f"PHASE_NOT_STARTED: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
