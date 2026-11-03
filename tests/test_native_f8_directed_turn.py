"""Selected final edge and exact B-graph native turn proof are distinct."""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from probe_native_f8_directed_turn import (
    point_along, probe_point, trace_turn, validate_adjacency, inspect_seam,
    direction_observation,
)

MODE_ACCESS = 1025


def edge(gid, points, *, mask=MODE_ACCESS, way=99):
    return {
        "sourceGraphId": gid, "endNodeGraphId": gid + 1000,
        "wayId": way, "endLat": points[-1][0], "endLon": points[-1][1],
        "forwardAccess": mask, "directedGeometry": points,
    }


SOURCE = edge(11, [[0, 0], [0, .0005]])
IN = edge(22, [[0, 0], [0, .0005]])
OUT_EAST = edge(31, [[0, .0005], [0, .001]])
OUT_NORTH = edge(32, [[0, .0005], [.0005, .0005]])
OUT_REVERSE = edge(33, [[0, .0005], [0, 0]])
OUTS = [OUT_EAST, OUT_NORTH, OUT_REVERSE]


def adjacency():
    return {
        "sourceGraphId": 22,
        "endNodeGraphId": 1022,
        "wayId": 99,
        "forwardAccess": MODE_ACCESS,
        "opposingGraphId": 33,
        "outgoingDirectedEdges": [
            {
                "graphId": row["sourceGraphId"],
                "endNodeGraphId": row["endNodeGraphId"],
                "forwardAccess": row["forwardAccess"],
                "isRoad": True, "isShortcut": False,
                "autoBit": True, "motorcycleBit": True,
            } for row in OUTS
        ],
    }


def fake_route(_config, start, end, mode):
    return {
        "status": "SUCCEEDED", "startOffsetMeters": 0, "endOffsetMeters": 0,
        "startActual": start, "endActual": end,
        "encodedShape": "north" if end["lat"] > .00001 else (
            "reverse" if end["lng"] < .0005 else "east"),
        "distanceKm": .12, "durationSeconds": 12,
    }


def fake_trace(_config, shape, _mode):
    return {
        "east": [22, 31], "north": [22, 32], "reverse": [22, 33],
    }[shape]


class DirectedTurnTests(unittest.TestCase):
    def test_matched_b_turn_does_not_claim_cross_graph_handoff(self):
        result = inspect_seam(SOURCE, IN, adjacency(), OUTS, Path("B"), "auto",
                              3, fake_route, fake_trace)
        self.assertEqual(result["outgoingNativeCount"], 3)
        self.assertEqual(result["bGraphTurnTracesMatchedForLocalRoute"], 3)
        self.assertEqual(result["crossGraphDirectedPhysicalContinuity"], "NOT_VERIFIED")
        self.assertEqual(result["crossSeamTurnLegality"], "NOT_VERIFIED")
        self.assertEqual(result["productionPublication"], "BLOCKED")
        self.assertTrue(result["selectedSourceFinalEdgeOnly"])
        self.assertEqual(result["receiverDirectedOrderObservation"]["state"],
                         "SAMPLED_DIRECTED_ORDER_ALIGNED_ONLY")

    def test_does_not_stop_at_first_success_and_budget_preserves_outgoing(self):
        result = inspect_seam(SOURCE, IN, adjacency(), OUTS, Path("B"), "auto",
                              2, fake_route, fake_trace)
        self.assertEqual(result["probed"], 2)
        self.assertEqual(result["unprobed"], 1)
        self.assertEqual(result["bGraphTurnTracesMatchedForLocalRoute"], 2)
        self.assertEqual([r["outgoingDirectedGraphId"] for r in
                          result["allNativeOutgoingAlternatives"]], [31, 32, 33])
        self.assertEqual(result["allNativeOutgoingAlternatives"][-1][
            "routeEvidence"]["status"], "NOT_PROBED_BUDGET")

    def test_positive_exact_turn_provenance_is_replayable(self):
        record = trace_turn(Path("B"), IN, OUT_EAST, "auto",
                            fake_route, fake_trace)
        self.assertEqual(record["status"],
                         "B_GRAPH_DIRECTED_TURN_TRACED_FOR_THIS_LOCAL_ROUTE")
        self.assertEqual(record["matchedIncomingEdgeTraceIndex"], 0)
        self.assertEqual(record["totalTracedEdgeCount"], 2)
        self.assertEqual(record["actualTracedGraphIds"], [22, 31])

    def test_alternative_traced_route_is_not_promoted(self):
        result = trace_turn(Path("B"), IN, OUT_EAST, "motorcycle",
                            fake_route, lambda *_: [22, 32])
        self.assertEqual(result["status"], "UNPROVEN")
        self.assertEqual(result["graphLocalTurnProof"], "NOT_VERIFIED")

    def test_nonconsecutive_turn_is_not_a_matched_turn(self):
        outcome = trace_turn(Path("B"), IN, OUT_EAST, "auto", fake_route,
                             lambda *_: [22, 44, 31])
        self.assertEqual(outcome["status"], "UNPROVEN")

    def test_trace_missing_and_route_inconclusive_fail_closed(self):
        outcome = trace_turn(Path("B"), IN, OUT_EAST, "auto",
                             fake_route, lambda *_: None)
        self.assertEqual(outcome["status"], "INCONCLUSIVE")
        outcome = trace_turn(Path("B"), IN, OUT_EAST, "auto",
                             lambda *_: {"status": "INCONCLUSIVE"},
                             fake_trace)
        self.assertEqual(outcome["status"], "INCONCLUSIVE")

    def test_snap_away_is_not_a_legal_turn_proof(self):
        def wrong_snap(_config, start, end, mode):
            result = fake_route(_config, start, end, mode)
            result["startOffsetMeters"] = 35
            return result
        self.assertEqual(trace_turn(Path("B"), IN, OUT_EAST, "auto",
                                    wrong_snap, fake_trace)["status"], "UNPROVEN")

    def test_incompatible_vehicle_access_is_not_a_turn_proof(self):
        no_bike = edge(31, [[0, .0005], [0, .001]], mask=1)
        result = trace_turn(Path("B"), IN, no_bike, "motorcycle", fake_route, fake_trace)
        self.assertEqual(result["status"], "UNPROVEN")
        self.assertEqual(result["graphLocalTurnProof"], "NOT_VERIFIED")

    def test_native_adjacency_missing_duplicate_and_forged_access_fail(self):
        good = adjacency()
        validate_adjacency(IN, good, OUTS)
        for corruption, match in [
            ({"endNodeGraphId": 0}, "identity mismatch"),
            ({"opposingGraphId": 44}, "absent native opposing"),
        ]:
            bad = copy.deepcopy(good)
            bad.update(corruption)
            with self.assertRaisesRegex(ValueError, match):
                validate_adjacency(IN, bad, OUTS)
        with self.assertRaisesRegex(ValueError, "Missing/reordered"):
            validate_adjacency(IN, good, OUTS[:-1])
        with self.assertRaisesRegex(ValueError, "vertex safety bound"):
            huge = copy.deepcopy(OUTS)
            huge[0]["directedGeometry"] = [[0., .0005]] * 250001
            validate_adjacency(IN, good, huge)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            d = copy.deepcopy(good)
            d["outgoingDirectedEdges"][1]["graphId"] = 31
            validate_adjacency(IN, d, OUTS)
        with self.assertRaisesRegex(ValueError, "contradict"):
            d = copy.deepcopy(good)
            d["outgoingDirectedEdges"][0]["motorcycleBit"] = False
            validate_adjacency(IN, d, OUTS)

    def test_short_edge_is_inconclusive_not_invalidated_as_crossing(self):
        short = edge(22, [[0, 0], [0, .000001]])
        result = trace_turn(Path("B"), short, OUT_EAST, "auto", fake_route, fake_trace)
        self.assertEqual(result["status"], "INCONCLUSIVE")
        self.assertEqual(result["graphLocalTurnProof"], "NOT_VERIFIED")

    def test_directional_sampler_never_leaves_edge(self):
        vertices = [{"lat": 0., "lng": 0.}, {"lat": 0., "lng": .0005}]
        start, total = probe_point(vertices, incoming=True)
        end, _ = probe_point(vertices, incoming=False)
        self.assertGreater(total, 50)
        self.assertLess(start["lng"], .0005)
        self.assertGreater(end["lng"], 0)
        with self.assertRaises(ValueError):
            point_along(vertices, -1.)
        with self.assertRaises(ValueError):
            point_along(vertices, float("nan"))

    def test_opposite_directed_segment_does_not_claim_legal_seam(self):
        reversed_receiver = edge(22, [[0, .0005], [0, 0]])
        d = adjacency()
        d["endNodeGraphId"] = reversed_receiver["endNodeGraphId"]
        result = inspect_seam(SOURCE, reversed_receiver, d, OUTS,
                              Path("B"), "auto", 2, fake_route, fake_trace)
        self.assertEqual(result["receiverGeometryObservation"][
            "receiverObservations"][0]["sourceVsReceiverDirectedTangentCosine"], -1.)
        self.assertEqual(result["crossGraphDirectedPhysicalContinuity"], "NOT_VERIFIED")
        self.assertEqual(result["receiverDirectedOrderObservation"]["state"],
                         "SAMPLED_DIRECTED_ORDER_OPPOSED_ONLY")

    def test_supplemental_direction_is_not_a_pre_valhalla_rejection(self):
        receiver = edge(22, [[.0002, .0005], [.0003, .0005]])
        d = direction_observation(SOURCE, receiver)
        self.assertEqual(d["state"], "INSUFFICIENT_SAMPLED_SEGMENT_OVERLAP")
        self.assertEqual(d["directionalSegmentEquivalence"], "NOT_VERIFIED")
        self.assertIs(d["discoveryEligibilityFiltered"], False)

    def test_different_native_segment_divisions_do_not_imply_missing_road(self):
        half = edge(22, [[0, .00035], [0, .0005]])
        d = direction_observation(SOURCE, half)
        self.assertEqual(d["directionalSegmentEquivalence"], "NOT_VERIFIED")
        self.assertGreater(d["matchedTailSamples"], 1)
        self.assertEqual(d["state"], "SAMPLED_DIRECTED_ORDER_ALIGNED_ONLY")


if __name__ == "__main__":
    unittest.main()
