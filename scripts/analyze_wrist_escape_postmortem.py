#!/usr/bin/env python3
"""Offline-only postmortem for a failed staged Wrist escape trial.

The analysis uses recorded before/after joint feedback and the pinned URDF to
separate exact single-joint FK contributions from nonlinear interaction.  It
also checks whether joints that have demonstrated at least 50% response can
overcome the observed passive Lift/Elbow drift under the existing two-degree
step bound.  This module has no robot transport or hardware command path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

if __package__:
    from scripts.plan_pick_grasp_tcp_ik import JOINTS, tcp_position_mm
    from scripts.plan_responsive_joint_escape import (
        fk_z_sensitivity_mm_per_deg,
    )
    from scripts.urdf_forward_kinematics import UrdfKinematics
else:
    from plan_pick_grasp_tcp_ik import JOINTS, tcp_position_mm
    from plan_responsive_joint_escape import fk_z_sensitivity_mm_per_deg
    from urdf_forward_kinematics import UrdfKinematics


def _vector(value: object, size: int, label: str) -> np.ndarray:
    result = np.asarray(value, dtype=float)
    if result.shape != (size,) or not np.isfinite(result).all():
        raise ValueError(f"{label} must contain {size} finite values")
    return result


def analyze(document: dict, kinematics: UrdfKinematics, urdf_sha256: str) -> dict:
    if document.get("urdf_sha256") != urdf_sha256:
        raise ValueError("URDF SHA mismatch")
    if document.get("motion_authorized") is not False:
        raise ValueError("postmortem must not authorize motion")
    before = _vector(document["present_before_deg"], len(JOINTS), "before")
    after = _vector(document["present_after_deg"], len(JOINTS), "after")
    offset = _vector(document["pick_grasp_tcp_offset_gripper_mm"], 3, "offset")
    response = _vector(
        document["measured_response_fraction"], len(JOINTS), "response",
    )
    maximum_step = float(document["maximum_joint_step_deg"])
    minimum_fraction = float(document["minimum_motion_fraction"])
    epsilon = float(document["finite_difference_step_deg"])
    table_z = float(document["table_contact_reference_z_mm"])
    if not 0 < maximum_step <= 2.0 or minimum_fraction != 0.5:
        raise ValueError("escape policy mismatch")

    before_xyz = tcp_position_mm(kinematics, before, offset)
    after_xyz = tcp_position_mm(kinematics, after, offset)
    sensitivity_before = fk_z_sensitivity_mm_per_deg(
        kinematics, before, offset, epsilon,
    )
    sensitivity_after = fk_z_sensitivity_mm_per_deg(
        kinematics, after, offset, epsilon,
    )

    single_axis = {}
    single_sum = 0.0
    for index, joint in enumerate(JOINTS):
        isolated = before.copy()
        isolated[index] = after[index]
        contribution = float(
            tcp_position_mm(kinematics, isolated, offset)[2] - before_xyz[2]
        )
        single_sum += contribution
        single_axis[joint] = {
            "actual_delta_deg": float(after[index] - before[index]),
            "exact_isolated_fk_z_contribution_mm": contribution,
        }
    actual_z_delta = float(after_xyz[2] - before_xyz[2])
    interaction = actual_z_delta - single_sum

    responsive = [
        joint for index, joint in enumerate(JOINTS)
        if response[index] + 1e-12 >= minimum_fraction
    ]
    if "shoulder_lift" in responsive or "elbow_flex" in responsive:
        raise ValueError("fixture contradicts unresponsive Lift/Elbow evidence")

    # Evidence-constrained best case for one more <=2 degree step.  Pan, Flex,
    # and Roll use their demonstrated response fractions.  Lift and Elbow use
    # the passive drift observed during the Wrist-only trial.  Since Pan has
    # negligible Z sensitivity, both bounds are evaluated explicitly.
    passive = after - before
    best = None
    for pan_command in (-maximum_step, maximum_step):
        modeled = after.copy()
        modeled[JOINTS.index("shoulder_lift")] += passive[
            JOINTS.index("shoulder_lift")]
        modeled[JOINTS.index("elbow_flex")] += passive[
            JOINTS.index("elbow_flex")]
        modeled[JOINTS.index("shoulder_pan")] += (
            pan_command * response[JOINTS.index("shoulder_pan")]
        )
        modeled[JOINTS.index("wrist_flex")] += (
            -maximum_step * response[JOINTS.index("wrist_flex")]
        )
        modeled[JOINTS.index("wrist_roll")] += (
            maximum_step * response[JOINTS.index("wrist_roll")]
        )
        xyz = tcp_position_mm(kinematics, modeled, offset)
        gain = float(xyz[2] - after_xyz[2])
        item = {
            "command_delta_deg": {
                "shoulder_pan": pan_command,
                "wrist_flex": -maximum_step,
                "wrist_roll": maximum_step,
            },
            "assumed_passive_drift_deg": {
                "shoulder_lift": float(passive[JOINTS.index("shoulder_lift")]),
                "elbow_flex": float(passive[JOINTS.index("elbow_flex")]),
            },
            "modeled_present_deg": {
                joint: float(modeled[index])
                for index, joint in enumerate(JOINTS)
            },
            "modeled_grasp_tcp_xyz_mm": [float(value) for value in xyz],
            "modeled_z_delta_mm": gain,
            "modeled_table_proxy_margin_mm": float(xyz[2] - table_z),
        }
        if best is None or gain > best["modeled_z_delta_mm"]:
            best = item

    assert best is not None
    candidate_found = best["modeled_z_delta_mm"] > 0.0
    return {
        "status": "OFFLINE_POSTMORTEM_ONLY",
        "trial": document.get("trial"),
        "present_before_deg": {
            joint: float(before[index]) for index, joint in enumerate(JOINTS)
        },
        "present_after_deg": {
            joint: float(after[index]) for index, joint in enumerate(JOINTS)
        },
        "grasp_tcp_before_mm": [float(value) for value in before_xyz],
        "grasp_tcp_after_mm": [float(value) for value in after_xyz],
        "actual_grasp_tcp_z_delta_mm": actual_z_delta,
        "fk_z_sensitivity_before_mm_per_deg": sensitivity_before,
        "fk_z_sensitivity_after_mm_per_deg": sensitivity_after,
        "exact_single_axis_contribution": single_axis,
        "exact_single_axis_sum_mm": single_sum,
        "nonlinear_interaction_mm": interaction,
        "responsive_joints_at_50_percent": responsive,
        "best_evidence_constrained_responsive_only_step": best,
        "responsive_only_candidate": (
            "FOUND_OFFLINE_ONLY" if candidate_found else "NOT_FOUND"
        ),
        "next_live_command": None,
        "reason": (
            "No <=2 degree combination of joints with measured >=50% response "
            "overcomes the observed passive Lift/Elbow drift."
        ),
        "actual_motor_command_count": 0,
        "follower_port_opened": False,
        "phase_c": "HOLD",
        "motion_authorized": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trial", required=True, type=Path)
    parser.add_argument("--urdf", required=True, type=Path)
    args = parser.parse_args()
    document = json.loads(args.trial.read_text(encoding="utf-8"))
    digest = hashlib.sha256(args.urdf.read_bytes()).hexdigest()
    print(json.dumps(
        analyze(document, UrdfKinematics.from_file(args.urdf), digest),
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
