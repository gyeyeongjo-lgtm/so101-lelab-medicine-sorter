import json
import unittest

from scripts.medicine_fixed_slot_command import DEFAULT_SLOTS, validate_slots
from scripts.simulate_fixed_slot_plan import prepare_plan, simulate_events


COMMAND = "A, B를 빨강에 넣고 C는 파랑에 넣어라."


class FixedSlotPlanSimulationTests(unittest.TestCase):
    def setUp(self):
        self.slots = validate_slots(json.loads(DEFAULT_SLOTS.read_text(encoding="utf-8")))
        self.snapshot = {
            "ok": True, "robot_enabled": False, "frame_age_s": 0.1,
            "sequence": 42, "layout_id": "mock_fixed_layout",
            "table": {
                "ready": True, "detected_ids": [0, 1, 2, 3, 4, 5, 6],
                "basket_mapping": {"4": "red", "5": "green", "6": "blue"},
                "basket_markers": {"4": {"color": "red"}, "5": {"color": "green"},
                                   "6": {"color": "blue"}},
            },
            "detections": [
                {"confidence": 0.9, "xyxy": [300, 221, 340, 258]},
                {"confidence": 0.9, "xyxy": [361, 216, 391, 255]},
                {"confidence": 0.9, "xyxy": [422, 203, 458, 255]},
            ],
        }
        self.occupancy = {"red": 0, "green": 0, "blue": 0}
        self.catalog = {"schema_version": 1, "layout_id": "mock_fixed_layout", "routes": []}

    def add_mock_route(self, label, color, before):
        self.catalog["routes"].append({
            "bottle_label": label, "target_color": color,
            "route_id": f"mock_{label}_{color}_{before}",
            "evidence_ref": "synthetic_test_only",
            "validated_full_cycle": True,
            "occupancy_conditions": [{
                "occupancy_before": before,
                "clearance_verified": True,
                "capacity_verified": True,
                "evidence_ref": "synthetic_occupancy_test_only",
            }],
        })

    def complete_mock_catalog(self):
        self.add_mock_route("A", "red", 0)
        self.add_mock_route("B", "red", 1)
        self.add_mock_route("C", "blue", 0)

    def plan(self, command=COMMAND):
        return prepare_plan(command, self.snapshot, self.slots,
                            self.catalog, self.occupancy)

    def test_example_blocks_all_execution_when_no_verified_routes_exist(self):
        plan = self.plan()
        self.assertEqual(plan["status"], "BLOCKED")
        self.assertEqual([(task["bottle_label"], task["target_color"],
                           task["basket_occupancy_before"]) for task in plan["tasks"]],
                         [("A", "red", 0), ("B", "red", 1), ("C", "blue", 0)])
        self.assertTrue(all(task["status"] == "BLOCKED_UNVERIFIED_ROUTE"
                            for task in plan["tasks"]))
        self.assertEqual(simulate_events(plan, [{"outcome": "completed"}])["events_consumed"], 0)
        self.assertFalse(plan["motion_authorized"])

    def test_second_bottle_requires_occupied_basket_route(self):
        self.add_mock_route("A", "red", 0)
        self.add_mock_route("B", "red", 0)  # Wrong occupancy: cannot substitute.
        self.add_mock_route("C", "blue", 0)
        plan = self.plan()
        self.assertEqual(plan["status"], "BLOCKED")
        self.assertEqual(plan["tasks"][1]["status"], "BLOCKED_UNVERIFIED_ROUTE")

    def test_unvalidated_route_or_duplicate_catalog_key_is_rejected(self):
        self.complete_mock_catalog()
        self.catalog["routes"][0]["validated_full_cycle"] = False
        self.assertEqual(self.plan()["tasks"][0]["status"],
                         "BLOCKED_UNVERIFIED_ROUTE")
        self.catalog["routes"][0]["validated_full_cycle"] = True
        self.catalog["routes"].append(self.catalog["routes"][0].copy())
        self.assertEqual(self.plan()["reason"], "duplicate_route_key")

    def test_same_route_can_cover_empty_and_occupied_basket_if_both_are_verified(self):
        self.add_mock_route("C", "red", 0)
        route = self.catalog["routes"][0]
        route["occupancy_conditions"].append({
            "occupancy_before": 1,
            "clearance_verified": True,
            "capacity_verified": True,
            "evidence_ref": "synthetic_second_bottle_clearance",
        })
        empty = self.plan("C를 빨강에 넣어라")
        self.assertEqual(empty["status"], "READY")
        self.occupancy["red"] = 1
        occupied = self.plan("C를 빨강에 넣어라")
        self.assertEqual(occupied["status"], "READY")
        self.assertEqual(empty["tasks"][0]["route_id"], occupied["tasks"][0]["route_id"])
        route["occupancy_conditions"][1]["capacity_verified"] = False
        self.assertEqual(self.plan("C를 빨강에 넣어라")["status"], "BLOCKED")

    def test_unmentioned_bottles_are_not_planned(self):
        self.add_mock_route("C", "blue", 0)
        plan = self.plan("C는 파랑에 넣어라")
        self.assertEqual(plan["status"], "READY")
        self.assertEqual([task["bottle_label"] for task in plan["tasks"]], ["C"])

    def test_missing_bottle_and_target_marker_block(self):
        self.snapshot["detections"] = self.snapshot["detections"][:2]
        self.assertEqual(self.plan()["reason"], "requested_bottle_missing")
        self.snapshot["detections"] = [
            {"confidence": 0.9, "xyxy": [300, 221, 340, 258]},
            {"confidence": 0.9, "xyxy": [361, 216, 391, 255]},
            {"confidence": 0.9, "xyxy": [422, 203, 458, 255]},
        ]
        self.snapshot["table"]["detected_ids"].remove(6)
        self.assertEqual(self.plan()["reason"], "reference_or_target_marker_missing")

    def test_timeout_failure_or_stop_never_advances_to_second_task(self):
        self.complete_mock_catalog()
        for outcome, status in (("timeout", "FAILED"), ("failure", "FAILED"),
                                ("stop", "STOPPED")):
            with self.subTest(outcome=outcome):
                result = simulate_events(self.plan(), [{"outcome": outcome},
                                                       {"outcome": "completed"}])
                self.assertEqual(result["status"], status)
                self.assertEqual(result["events_consumed"], 1)
                self.assertEqual(result["tasks"][1]["status"], "READY")

    def test_running_state_can_be_observed_before_result_and_then_stopped(self):
        self.complete_mock_catalog()
        started = simulate_events(self.plan(), [{"outcome": "start"}])
        self.assertEqual(started["status"], "RUNNING")
        self.assertEqual(started["tasks"][0]["status"], "RUNNING")
        stopped = simulate_events(started, [{"outcome": "stop"}])
        self.assertEqual(stopped["status"], "STOPPED")
        self.assertEqual(stopped["tasks"][1]["status"], "READY")

    def test_missing_pick_or_place_or_retreat_proof_requires_confirmation(self):
        self.complete_mock_catalog()
        result = simulate_events(self.plan(), [
            {"outcome": "completed", "grasp_verified": True,
             "placement_verified": True, "retreat_verified": False},
            {"outcome": "completed", "grasp_verified": True,
             "placement_verified": True, "retreat_verified": True},
        ])
        self.assertEqual(result["status"], "USER_CONFIRMATION_REQUIRED")
        self.assertEqual(result["tasks"][0]["status"], "UNVERIFIED")
        self.assertEqual(result["tasks"][1]["status"], "READY")
        self.assertEqual(result["events_consumed"], 1)

    def test_mock_proofs_complete_ordered_simulation_without_motion_authority(self):
        self.complete_mock_catalog()
        event = {"outcome": "completed", "grasp_verified": True,
                 "placement_verified": True, "retreat_verified": True}
        result = simulate_events(self.plan(), [event, event, event])
        self.assertEqual(result["status"], "SUCCEEDED")
        self.assertEqual([task["bottle_label"] for task in result["tasks"]],
                         ["A", "B", "C"])
        self.assertTrue(result["simulation_only"])
        self.assertFalse(result["robot_enabled"])
        self.assertFalse(result["motion_authorized"])

    def test_layout_and_occupancy_must_be_supplied(self):
        self.complete_mock_catalog()
        self.snapshot.pop("layout_id")
        self.assertEqual(self.plan()["reason"], "layout_id_unverified")
        self.snapshot["layout_id"] = "mock_fixed_layout"
        self.occupancy = {"red": 0, "blue": 0}
        self.assertEqual(self.plan()["reason"], "basket_occupancy_unverified")


if __name__ == "__main__":
    unittest.main()
