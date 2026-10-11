#!/usr/bin/env python3
"""Read-only C→red vision/IK preview; never opens robot ports or sends motion.

The old rejected World→Base/TCP transforms are never used. Robot XY and IK are
computed only after a new 4+ point fit passes an independent hold-out gate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from urllib.request import urlopen
import xml.etree.ElementTree as ET

import cv2
import numpy as np

from detect_medicine_onnx import decode_detections, letterbox
from medicine_fixed_slot_command import parse_command
from medicine_yolo_web import TableMapper, project_table_xy
from stable_aruco_table import StableTableReference
from urdf_forward_kinematics import UrdfKinematics
from vision_guided_geometry import (
    basket_opening_table_xy, fit_table_to_robot_xy, nearest_table_slot,
    table_to_robot_xy,
)


ARM_JOINTS = ("Rotation", "Pitch", "Elbow", "Wrist_Pitch", "Wrist_Roll")
URDF_SHA256 = "443d38d756e01bac7d3455b24430047ddc6427105e0d3454b2003116f5f67236"
FOLLOWER_CALIBRATION_SHA256 = "2f74c1303b2fce03576eff539329e1185a652e2d551caa1ec82b026dafe29c2e"
FOLLOWER_ARM_RAW_RANGES = ((755, 3448), (796, 3113), (880, 3087),
                           (936, 3225), (86, 3643))
MIN_OPERATIONAL_SERVO_MARGIN_DEG = 2.0
DEFAULT_TABLE_SLOTS = Path(__file__).resolve().parents[1] / "configs/medicine_table_slots.provisional.json"
DEFAULT_TABLE_ROBOT = Path(__file__).resolve().parents[1] / "configs/c_red_table_robot_xy.pending.json"
DEFAULT_RED_BASKET = Path(__file__).resolve().parents[1] / "configs/c_red_basket_opening.provisional.json"


def joint_bounds_rad(urdf: Path, *, reserve_deg: float = 2.0) -> np.ndarray:
    root = ET.parse(urdf).getroot()
    by_name = {joint.get("name"): joint for joint in root.findall("joint")}
    bounds = []
    for name in ARM_JOINTS:
        joint = by_name.get(name)
        if joint is None or joint.get("type") != "revolute":
            raise ValueError(f"missing revolute URDF joint: {name}")
        limit = joint.find("limit")
        if limit is None:
            raise ValueError(f"missing URDF limit: {name}")
        lower = float(limit.get("lower")) + math.radians(reserve_deg)
        upper = float(limit.get("upper")) - math.radians(reserve_deg)
        if not math.isfinite(lower + upper) or lower >= upper:
            raise ValueError(f"invalid URDF limits: {name}")
        bounds.append((lower, upper))
    return np.asarray(bounds, dtype=float)


def operational_bounds_rad(config: dict) -> np.ndarray:
    """Separate, explicitly certified autonomous limits; never infer from URDF."""
    if (config.get("status") != "VERIFIED_FOR_AUTONOMOUS_PLANNING" or
            config.get("physical_clearance_verified") is not True or
            config.get("follower_calibration_sha256") != FOLLOWER_CALIBRATION_SHA256 or
            config.get("unit") != "deg" or
            set(config.get("joint_bounds_deg", {})) != set(ARM_JOINTS)):
        raise ValueError("operational joint limits are not independently verified")
    bounds = np.asarray([config["joint_bounds_deg"][name] for name in ARM_JOINTS], dtype=float)
    if (bounds.shape != (5, 2) or not np.isfinite(bounds).all() or
            np.any(bounds[:, 0] >= bounds[:, 1])):
        raise ValueError("invalid operational joint limits")
    for index, (raw_lower, raw_upper) in enumerate(FOLLOWER_ARM_RAW_RANGES):
        half_range = (raw_upper - raw_lower) * 180 / 4095
        if (bounds[index, 0] < -half_range + MIN_OPERATIONAL_SERVO_MARGIN_DEG - 1e-6 or
                bounds[index, 1] > half_range - MIN_OPERATIONAL_SERVO_MARGIN_DEG + 1e-6):
            raise ValueError("operational limits exceed servo calibration with 2 degree reserve")
    return np.deg2rad(bounds)


def tcp_position_mm(kinematics: UrdfKinematics, q_rad: np.ndarray,
                    tcp_offset_mm: np.ndarray) -> np.ndarray:
    transform = kinematics.forward(dict(zip(ARM_JOINTS, q_rad)), "base", "gripper")
    return transform[:3, 3] * 1000.0 + transform[:3, :3] @ tcp_offset_mm


def solve_position_ik(
    kinematics: UrdfKinematics,
    target_base_mm: np.ndarray,
    seed_deg: np.ndarray,
    tcp_offset_mm: np.ndarray,
    bounds_rad: np.ndarray,
    *,
    tolerance_mm: float = 1.0,
    max_iterations: int = 160,
) -> dict:
    """Bounded position-only DLS IK, validated by independent FK residual.

    This is a numerical dry-run, not orientation, collision, path or physical
    calibration validation. A seed already outside the URDF is rejected.
    """
    target = np.asarray(target_base_mm, dtype=float)
    offset = np.asarray(tcp_offset_mm, dtype=float)
    q = np.deg2rad(np.asarray(seed_deg, dtype=float))
    if target.shape != (3,) or offset.shape != (3,) or q.shape != (5,):
        raise ValueError("IK target, TCP offset and seed must have 3/3/5 elements")
    if not np.isfinite(target).all() or not np.isfinite(offset).all() or not np.isfinite(q).all():
        raise ValueError("IK input must be finite")
    if np.any(q < bounds_rad[:, 0]) or np.any(q > bounds_rad[:, 1]):
        raise ValueError("IK seed outside reserved URDF limits")
    damping = 10.0
    iterations = 0
    for iterations in range(1, max_iterations + 1):
        actual = tcp_position_mm(kinematics, q, offset)
        error = target - actual
        error_norm = float(np.linalg.norm(error))
        if error_norm <= tolerance_mm:
            break
        epsilon = 1e-4
        jacobian = np.column_stack([
            (tcp_position_mm(kinematics, q + np.eye(5)[axis] * epsilon, offset) - actual) / epsilon
            for axis in range(5)
        ])
        step = jacobian.T @ np.linalg.solve(
            jacobian @ jacobian.T + damping * damping * np.eye(3), error
        )
        step = np.clip(step, -math.radians(5), math.radians(5))
        improved = False
        for scale in (1.0, 0.5, 0.25, 0.125, 0.0625):
            candidate = np.clip(q + scale * step, bounds_rad[:, 0], bounds_rad[:, 1])
            if float(np.linalg.norm(target - tcp_position_mm(kinematics, candidate, offset))) < error_norm:
                q = candidate
                improved = True
                break
        if not improved:
            damping *= 3.0
            if damping > 1e5:
                break
        else:
            damping = max(1.0, damping / 1.5)
    actual = tcp_position_mm(kinematics, q, offset)
    residual = float(np.linalg.norm(target - actual))
    lower_margin = np.rad2deg(q - bounds_rad[:, 0])
    upper_margin = np.rad2deg(bounds_rad[:, 1] - q)
    return {
        "status": "NUMERIC_POSITION_IK_PASS" if residual <= tolerance_mm else "IK_UNREACHABLE_OR_UNCONVERGED",
        "joint_target_deg": {name: round(float(value), 6) for name, value in zip(ARM_JOINTS, np.rad2deg(q))},
        "fk_tcp_base_mm": [round(float(value), 3) for value in actual],
        "position_residual_mm": round(residual, 6),
        "minimum_reserved_urdf_margin_deg": round(float(min(lower_margin.min(), upper_margin.min())), 6),
        "iterations": iterations,
        "orientation_solved": False,
        "collision_checked": False,
    }


def classify_bottle_detections(detections: list[dict], table: dict,
                               table_slots: dict) -> list[dict]:
    if (table.get("ready") is not True or
            not {0, 1, 2, 3, 4}.issubset(set(table.get("detected_ids", []))) or
            table.get("basket_markers", {}).get("4", {}).get("color") != "red"):
        raise ValueError("reference or red basket marker missing")
    classified = []
    identities = set()
    for detection in detections:
        if detection["confidence"] < 0.5:
            continue
        point = detection.get("image_center_table_mm")
        if (not isinstance(point, list) or len(point) != 2 or
                any(not isinstance(value, (int, float)) or not math.isfinite(value) for value in point)):
            raise ValueError("bottle table projection missing or invalid")
        identity = nearest_table_slot(point, table_slots)
        if identity["identity"] is None:
            raise ValueError("bottle outside or ambiguous between table slots")
        label = identity["identity"]
        if label in identities:
            raise ValueError("multiple bottle boxes assigned to one table slot")
        identities.add(label)
        box = detection["xyxy"]
        classified.append({
            "yolo_class": detection["class_name"],
            "confidence": detection["confidence"],
            "bbox_xyxy_px": box,
            "bbox_center_px": [round((box[0] + box[2]) / 2, 3),
                               round((box[1] + box[3]) / 2, 3)],
            "table_xy_mm": point,
            "identity_source": "NEAREST_ARUCO_TABLE_SLOT_NOT_YOLO_CLASS",
            **identity,
            "inside_existing_pickup_roi": detection["inside_pickup_roi"],
        })
    if not classified:
        raise ValueError("no confident bottle detection")
    return classified


def validate_c_metadata(metadata: dict, image_sha256: str) -> None:
    if metadata.get("raw_jpeg_sha256") != image_sha256:
        raise ValueError("saved metadata does not match this exact image")


def read_ceiling_frame(image: Path | None, image_url: str | None) -> tuple[np.ndarray, bytes, str]:
    if image is not None:
        raw = image.read_bytes()
        source = str(image)
    elif image_url is not None:
        if not image_url.startswith("http://"):
            raise ValueError("live frame URL must use an explicit local HTTP endpoint")
        with urlopen(image_url, timeout=5) as response:
            raw = bytearray()
            while len(raw) < 2_000_000:
                chunk = response.read(65536)
                if not chunk:
                    raise ValueError("live JPEG stream ended without a frame")
                raw.extend(chunk)
                start = raw.find(b"\xff\xd8")
                end = raw.find(b"\xff\xd9", start + 2) if start >= 0 else -1
                if end >= 0:
                    raw = bytes(raw[start:end + 2])
                    break
            else:
                raise ValueError("live JPEG not found within 2 MB")
        source = image_url
    else:
        raise ValueError("image or image URL required")
    frame = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
    if frame is None or frame.shape[:2] != (480, 640):
        raise ValueError("C preview needs one decoded 640x480 ceiling frame")
    return frame, bytes(raw), source


def detect_and_project(image: Path | None, image_url: str | None, model: Path,
                       workspace_config: Path, table_slots_config: Path,
                       reference_image: Path) -> dict:
    frame, raw, source = read_ceiling_frame(image, image_url)
    net = cv2.dnn.readNetFromONNX(str(model))
    prepared, scale, pad_x, pad_y = letterbox(frame, 640, cv2, np)
    net.setInput(cv2.dnn.blobFromImage(prepared, 1 / 255, (640, 640), swapRB=True))
    detections = decode_detections(
        net.forward(), 640, 480, scale, pad_x, pad_y, 0.25, 0.7, cv2, np
    )
    mapper = TableMapper(workspace_config, cv2, np)
    table = mapper.analyze(frame, frame.copy(), detections)
    stable = StableTableReference(cv2, np, mapper, reference_image).analyze(frame)
    for detection in detections:
        box = detection["xyxy"]
        center = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
        detection["image_center_table_mm"] = [
            round(v, 3) for v in project_table_xy(np, stable["homography"], *center)]
        roi = json.loads(workspace_config.read_text(encoding="utf-8"))["pickup_roi_table_mm"]
        x, y = detection["image_center_table_mm"]
        detection["inside_pickup_roi"] = roi["x"][0] <= x <= roi["x"][1] and roi["y"][0] <= y <= roi["y"][1]
    table_slots = json.loads(table_slots_config.read_text(encoding="utf-8"))
    bottles = classify_bottle_detections(detections, table, table_slots)
    selected = next((bottle for bottle in bottles if bottle["identity"] == "C"), None)
    if selected is None:
        raise ValueError("C not detected at its ArUco table slot")
    return {
        "source_image": source,
        "source_image_sha256": hashlib.sha256(raw).hexdigest(),
        "detected_bottles": bottles,
        "c_detection": selected,
        "c_table_xy_mm": selected["table_xy_mm"],
        "inside_existing_pickup_roi": selected["inside_existing_pickup_roi"],
        "aruco_ids": stable["aruco_ids"],
        "aruco_quality": stable["quality"],
        "table_reference_status": json.loads(workspace_config.read_text(encoding="utf-8"))["markers"].get("reference_center_status", "UNSPECIFIED"),
        "red_id4_marker_table_xy_mm": [round(v, 3) for v in stable["id4_marker_table_xy_mm"]],
        "red_basket_center_verified": False,
    }


def solve_phase_targets(kinematics: UrdfKinematics, bounds: np.ndarray,
                        grasp_tcp_offset: np.ndarray, c_xy: list[float],
                        basket_xy: list[float], heights: dict,
                        start_joints_deg: np.ndarray) -> dict:
    """Solve five discrete waypoints; never interpret them as a safe path."""
    targets = {}
    q_seed = np.asarray(start_joints_deg, dtype=float).copy()
    if q_seed.shape != (5,) or not np.isfinite(q_seed).all():
        raise ValueError("five finite observed follower start joints required")
    if np.any(np.deg2rad(q_seed) < bounds[:, 0]) or np.any(np.deg2rad(q_seed) > bounds[:, 1]):
        raise ValueError("observed follower start outside selected planning limits")
    for phase, z_key, xy in (
        ("approach", "Z_APPROACH", c_xy),
        ("grasp", "Z_GRASP", c_xy),
        ("lift", "Z_LIFT", c_xy),
        ("red_basket_hover", "Z_SAFE", basket_xy),
        ("place", "Z_PLACE", basket_xy),
    ):
        target = np.array([xy[0], xy[1], heights[z_key]], dtype=float)
        solution = solve_position_ik(
            kinematics, target, q_seed, grasp_tcp_offset, bounds
        )
        targets[phase] = {
            "candidate_robot_base_xyz_mm": [round(float(value), 3) for value in target],
            "tcp_reference": "pick_grasp_tcp_offset_gripper_mm_not_calibration_pin_tip",
            **solution,
        }
        if solution["status"] != "NUMERIC_POSITION_IK_PASS":
            break
        q_seed = np.array(list(solution["joint_target_deg"].values()))
    return targets


def diagnostic_preview(args: argparse.Namespace) -> dict:
    command = parse_command(args.command)
    if command != {"C": "red"}:
        raise ValueError("this diagnostic is restricted to C to red")
    vision = detect_and_project(args.image, args.image_url, args.model,
                                args.workspace_config, args.table_slots_config,
                                args.reference_image)
    if args.metadata is not None:
        metadata = json.loads(args.metadata.read_text(encoding="utf-8"))
        validate_c_metadata(metadata, vision["source_image_sha256"])
        vision["saved_frame_label_used_for_runtime_identity"] = False
    if hashlib.sha256(args.urdf.read_bytes()).hexdigest() != URDF_SHA256:
        raise ValueError("installed URDF SHA mismatch")
    calibration = json.loads(args.table_robot_calibration.read_text(encoding="utf-8"))
    basket_config = json.loads(args.red_basket_offset.read_text(encoding="utf-8"))
    try:
        fit = fit_table_to_robot_xy(calibration)
    except ValueError as error:
        fit = {"status": "BLOCKED_CALIBRATION_INPUT", "reason": str(error),
               "motion_geometry_eligible": False}
    workspace_sha = hashlib.sha256(args.workspace_config.read_bytes()).hexdigest()
    if (fit["status"] == "ACCEPTED_HOLDOUT_PASS" and
            calibration.get("workspace_config_sha256") != workspace_sha):
        fit = {**fit, "status": "BLOCKED_REFERENCE_FRAME_MISMATCH",
               "reason": "calibration not bound to this ArUco reference configuration",
               "motion_geometry_eligible": False}
    if (fit["status"] == "ACCEPTED_HOLDOUT_PASS" and
            calibration.get("table_reference_image_sha256") !=
            hashlib.sha256(args.reference_image.read_bytes()).hexdigest()):
        fit = {**fit, "status": "BLOCKED_TABLE_TEMPLATE_MISMATCH",
               "reason": "calibration used a different saved ArUco reference image",
               "motion_geometry_eligible": False}
    basket = basket_opening_table_xy(vision["red_id4_marker_table_xy_mm"], basket_config)
    heights = {
        "Z_SAFE": args.z_safe_mm, "Z_APPROACH": args.z_approach_mm,
        "Z_GRASP": args.z_grasp_mm, "Z_LIFT": args.z_lift_mm,
        "Z_PLACE": args.z_place_mm,
    }
    if not all(math.isfinite(value) for value in heights.values()):
        raise ValueError("fixed Z values must be finite")
    blocked = ["fixed robot-base Z and grasp orientation not physically verified",
               "collision/swept path not checked", "current follower feedback not freshly verified for motion"]
    if args.operational_limits is None:
        blocked.append("verified autonomous operational joint limits not supplied")
    if args.start_joints_deg is None:
        blocked.append("observed follower start joints not supplied; safe_start is not an IK seed")
    if fit["status"] != "ACCEPTED_HOLDOUT_PASS":
        blocked.insert(0, "table-to-robot TCP XY fit and independent hold-out not accepted")
    if not basket["offset_verified"]:
        blocked.append("red basket opening offset is image-estimated, not measured")
    if not vision["inside_existing_pickup_roi"]:
        blocked.append("C center outside existing pickup ROI")
    grasp_tcp_values = getattr(args, "grasp_tcp_offset_mm", None)
    if grasp_tcp_values is None:
        blocked.append("PICK grasp TCP offset not explicitly supplied; calibration PIN TCP cannot be reused")
    result = {
        "status": "DIAGNOSTIC_ONLY_MOTION_BLOCKED",
        "command": command,
        "vision": vision,
        "z_levels_robot_base_mm": heights,
        "z_levels_verified": False,
        "table_to_robot_xy_calibration": fit,
        "tcp_frames": {
            "calibration_pin_tip_offset_gripper_mm": (
                fit.get("tcp_offset_gripper_link_mm")
                if fit.get("status") == "ACCEPTED_HOLDOUT_PASS" else None
            ),
            "pick_grasp_tcp_offset_gripper_mm": grasp_tcp_values,
            "frames_explicitly_separated": grasp_tcp_values is not None,
        },
        "basket_opening": basket,
        "c_robot_xy_mm": None,
        "red_basket_robot_xy_mm": None,
        "blocking_reasons": blocked,
        "joint_targets": {},
        "numeric_dry_run": "NOT_RUN",
        "urdf_check": "NOT_RUN",
        "robot_enabled": False,
        "motion_authorized": False,
    }
    if (fit["status"] != "ACCEPTED_HOLDOUT_PASS" or args.start_joints_deg is None or
            args.operational_limits is None or grasp_tcp_values is None):
        return result
    result["c_robot_xy_mm"] = table_to_robot_xy(vision["c_table_xy_mm"], fit)
    result["red_basket_robot_xy_mm"] = table_to_robot_xy(basket["opening_table_xy_mm"], fit)
    kinematics = UrdfKinematics.from_file(args.urdf)
    bounds = operational_bounds_rad(json.loads(args.operational_limits.read_text(encoding="utf-8")))
    grasp_tcp_offset = np.asarray(grasp_tcp_values, dtype=float)
    if grasp_tcp_offset.shape != (3,) or not np.isfinite(grasp_tcp_offset).all():
        raise ValueError("PICK grasp TCP offset must contain three finite millimetre values")
    result["joint_targets"] = solve_phase_targets(
        kinematics, bounds, grasp_tcp_offset, result["c_robot_xy_mm"],
        result["red_basket_robot_xy_mm"], heights,
        np.asarray(args.start_joints_deg, dtype=float),
    )
    for phase, solution in result["joint_targets"].items():
        if solution["status"] != "NUMERIC_POSITION_IK_PASS":
            blocked.append(f"{phase} numerical IK failed")
    result["numeric_dry_run"] = (
        "ALL_FIVE_POSITION_IK_PASS" if len(result["joint_targets"]) == 5 and
        all(item["status"] == "NUMERIC_POSITION_IK_PASS" for item in result["joint_targets"].values())
        else "IK_BLOCKED"
    )
    result["urdf_check"] = "PASS" if result["numeric_dry_run"] == "ALL_FIVE_POSITION_IK_PASS" else "FAIL"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--image", type=Path)
    source.add_argument("--image-url", type=str)
    parser.add_argument("--metadata", type=Path)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--workspace-config", type=Path, required=True)
    parser.add_argument("--reference-image", type=Path, required=True,
                        help="saved pre-drift ceiling JPEG with ID0–3")
    parser.add_argument("--table-slots-config", type=Path, default=DEFAULT_TABLE_SLOTS)
    parser.add_argument("--table-robot-calibration", type=Path, default=DEFAULT_TABLE_ROBOT)
    parser.add_argument("--red-basket-offset", type=Path, default=DEFAULT_RED_BASKET)
    parser.add_argument("--command", default="C를 빨강 바구니에 넣어")
    parser.add_argument("--urdf", type=Path, required=True)
    parser.add_argument("--operational-limits", type=Path,
                        help="separately verified autonomous planning limits; pending candidates are rejected")
    parser.add_argument("--start-joints-deg", type=float, nargs=5,
                        help="observed follower Rotation Pitch Elbow Wrist_Pitch Wrist_Roll; "
                             "dry-run only, not proof of fresh live feedback")
    parser.add_argument(
        "--grasp-tcp-offset-mm", type=float, nargs=3,
        help="required PICK-only gripper-origin to opening-center XYZ; the calibration PIN TCP is never substituted",
    )
    for name in ("safe", "approach", "grasp", "lift", "place"):
        parser.add_argument(f"--z-{name}-mm", type=float, required=True)
    try:
        result = diagnostic_preview(parser.parse_args())
    except (OSError, ValueError, TimeoutError, cv2.error) as error:
        print(json.dumps({"status": "BLOCKED_INPUT_OR_CAMERA", "reason": str(error),
                          "robot_enabled": False, "motion_authorized": False},
                         ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["numeric_dry_run"] == "ALL_FIVE_POSITION_IK_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
