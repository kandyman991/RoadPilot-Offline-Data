"""Exact receiver-node adjacency is evidence, never route proof."""
from __future__ import annotations
import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from verify_native_f8_receiver_adjacency import (
    candidates, validate_capture, inspect_direction, AUTO_ACCESS, MOTORCYCLE_ACCESS
)


def observation(source_id=1, receiver_id=11, *, same_way=True, deadend=False):
    return {"sourceDirectedGraphId": source_id, "sourceForwardAccess": 1025,
            "nearbyReceiverIncoming": [{
                "receiverDirectedGraphId": receiver_id,
                "receiverEndNodeGraphId": 5011,
                "receiverWayId": 900, "receiverForwardAccess": 1025,
                "receiverDeadend": deadend, "sameWay": same_way,
                "distanceMetres": 0.0
            }]}


def native(receiver_id=11, *, mode_mask=1025):
    return {
        "sourceGraphId": receiver_id, "endNodeGraphId": 5011,
        "wayId": 900, "forwardAccess": 1025, "deadend": False,
        "opposingGraphId": 44,
        "outgoingDirectedEdges": [
            {"graphId": 44, "endNodeGraphId": 32, "forwardAccess": 1025,
             "isRoad": True, "isShortcut": False, "autoBit": True,
             "motorcycleBit": True},
            {"graphId": 55, "endNodeGraphId": 76, "forwardAccess": mode_mask,
             "isRoad": True, "isShortcut": False,
             "autoBit": bool(mode_mask & AUTO_ACCESS),
             "motorcycleBit": bool(mode_mask & MOTORCYCLE_ACCESS)},
        ]
    }


class NativeReceiverAdjacencyTests(unittest.TestCase):
    def test_exact_receiver_node_access_is_structural_only(self):
        obs = [observation()]
        captured = validate_capture(obs, [native()])
        result = inspect_direction(obs, captured)
        self.assertEqual(result["counts"]["sourceWithBothModeStructuralContinuation"], 1)
        self.assertEqual(result["valhallaRouteLegs"], "NOT_RUN")
        self.assertFalse(result["allRelevantAlternativesExhausted"])

    def test_motorcycle_and_auto_separated_by_forward_access(self):
        obs = [observation()]
        motorcycle_only = inspect_direction(obs, validate_capture(obs, [native(mode_mask=1024)]))
        counts = motorcycle_only["counts"]
        self.assertEqual(counts["sourceWithMotorcycleStructuralContinuation"], 1)
        self.assertEqual(counts["sourceWithoutAutoStructuralContinuation"], 1)

    def test_reverse_only_is_not_forward_continuation(self):
        obs = [observation()]
        record = native()
        record["outgoingDirectedEdges"] = record["outgoingDirectedEdges"][:1]
        result = inspect_direction(obs, validate_capture(obs, [record]))
        self.assertEqual(result["counts"]["sourceWithoutAutoStructuralContinuation"], 1)
        self.assertEqual(result["counts"]["sourceWithoutMotorcycleStructuralContinuation"], 1)

    def test_same_named_road_source_alternatives_stay_distinct(self):
        obs = [observation(1, 11), observation(2, 12)]
        peer = native(receiver_id=12)
        report = inspect_direction(obs, validate_capture(obs, [native(), peer]))
        self.assertEqual(report["counts"]["sourceWithProvisionalReceiverIncoming"], 2)
        self.assertEqual(report["counts"]["sourceWithBothModeStructuralContinuation"], 2)

    def test_other_way_nearby_not_treated_as_rejected_road(self):
        obs = [observation(same_way=False)]
        self.assertEqual(candidates(obs), {})
        result = inspect_direction(obs, validate_capture(obs, []))
        self.assertEqual(result["counts"]["sourceWithoutProvisionalReceiverIncoming"], 1)
        self.assertFalse(result["allRelevantAlternativesExhausted"])

    def test_missing_extra_and_duplicate_receiver_ids_rejected(self):
        obs = [observation()]
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            validate_capture(obs, [])
        with self.assertRaisesRegex(ValueError, "Unknown"):
            validate_capture(obs, [native(receiver_id=12)])
        with self.assertRaisesRegex(ValueError, "Repeated native"):
            validate_capture(obs, [native(), native()])

    def test_spoofed_access_identity_and_opposing_id_rejected(self):
        obs = [observation()]
        record = native()
        record["forwardAccess"] = 123
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            validate_capture(obs, [record])
        record = native()
        record["outgoingDirectedEdges"][1]["motorcycleBit"] = False
        with self.assertRaisesRegex(ValueError, "Motorcycle access"):
            validate_capture(obs, [record])
        record = native()
        record["opposingGraphId"] = 9999
        with self.assertRaisesRegex(ValueError, "Opposing edge"):
            validate_capture(obs, [record])
        record = native()
        record["deadend"] = True
        with self.assertRaisesRegex(ValueError, "became a dead-end"):
            validate_capture(obs, [record])


if __name__ == "__main__":
    unittest.main()
