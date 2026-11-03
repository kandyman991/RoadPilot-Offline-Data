"""M5: selected-journey observations never promote cross-graph seam legality."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from probe_native_f8_selected_journey import evaluate_selected_journey

ACCESS_BOTH = 1025


def edge(graph_id, vertices, *, mask=ACCESS_BOTH, way=99):
    return {
        "sourceGraphId": graph_id,
        "endNodeGraphId": graph_id + 1000,
        "wayId": way,
        "endLat": vertices[-1][0],
        "endLon": vertices[-1][1],
        "forwardAccess": mask,
        "directedGeometry": vertices,
    }


SOURCE = edge(11, [[0, 0], [0, 0.0005]])
INCOMING = edge(22, [[0, 0], [0, 0.0005]])
EAST = edge(31, [[0, 0.0005], [0, 0.001]])
NORTH = edge(32, [[0, 0.0005], [0.0005, 0.0005]])
REVERSE = edge(33, [[0, 0.0005], [0, 0]])
OUTGOINGS = [EAST, NORTH, REVERSE]
ORIGIN = {"lat": 0, "lng": 0}
DESTINATION = {"lat": 0, "lng": 0.001}


def adjacency():
    return {
        "sourceGraphId": 22,
        "endNodeGraphId": 1022,
        "wayId": 99,
        "forwardAccess": ACCESS_BOTH,
        "opposingGraphId": 33,
        "outgoingDirectedEdges": [
            {
                "graphId": row["sourceGraphId"],
                "endNodeGraphId": row["endNodeGraphId"],
                "forwardAccess": row["forwardAccess"],
                "isRoad": True,
                "isShortcut": False,
                "autoBit": True,
                "motorcycleBit": True,
            }
            for row in OUTGOINGS
        ],
    }


def fake_route(config, start, destination, mode):
    if str(config) == "graph-A":
        code = "a-last"
    elif start["lng"] >= 0.00049:
        code = "b-journey"
    elif destination["lat"] > 0.00001:
        code = "b-north"
    elif destination["lng"] < 0.00049:
        code = "b-reverse"
    else:
        code = "b-east"
    return {
        "status": "SUCCEEDED",
        "startOffsetMeters": 0,
        "endOffsetMeters": 0,
        "startActual": start,
        "endActual": destination,
        "encodedShape": code,
        "durationSeconds": 15,
        "distanceKm": 0.13,
    }


def fake_trace(config, shape, mode):
    return {
        "a-last": [11],
        "b-journey": [31],
        "b-east": [22, 31],
        "b-north": [22, 32],
        "b-reverse": [22, 33],
    }[shape]


def evaluate(*, source=SOURCE, incoming=INCOMING, adj=None, outgoing=None,
             mode="auto", budget=3, route_fn=fake_route, trace_fn=fake_trace,
             origin=ORIGIN, destination=DESTINATION):
    return evaluate_selected_journey(
        source, incoming, adj if adj is not None else adjacency(),
        outgoing if outgoing is not None else OUTGOINGS,
        Path("graph-A"), Path("graph-B"), origin, destination,
        mode, budget, route_fn=route_fn, trace_fn=trace_fn,
    )


class SelectedJourneyTests(unittest.TestCase):
    def test_full_journey_and_three_b_turns_still_do_not_prove_cross_graph_seam(self):
        result = evaluate()
        self.assertEqual(result["bLocalTracedTurns"], 3)
        self.assertTrue(result["twoGraphLocalTracesMatched"])
        self.assertEqual(result["twoGraphJourneyObservation"]["status"],
                         "GRAPH_LOCAL_TRACES_MATCHED_FOR_THIS_JOURNEY")
        self.assertEqual(result["crossGraphPhysicalContinuity"], "NOT_VERIFIED")
        self.assertEqual(result["crossSeamTurnLegality"], "NOT_VERIFIED")
        self.assertEqual(result["androidF8Parity"], "NOT_VERIFIED")
        self.assertEqual(result["productionPublication"], "BLOCKED")
        self.assertEqual(result["terminalSourceIdentity"],
                         "NOMINATED_ONLY_NOT_A_GRAPH_WIDE_CENSUS")

    def test_actual_graph_a_last_edge_mismatch_is_not_promoted(self):
        def wrong_source(config, shape, mode):
            return [987] if str(config) == "graph-A" else fake_trace(config, shape, mode)
        result = evaluate(trace_fn=wrong_source)
        self.assertEqual(result["bLocalTracedTurns"], 3)
        self.assertFalse(result["twoGraphLocalTracesMatched"])
        self.assertEqual(result["twoGraphJourneyObservation"]["status"], "UNPROVEN")
        self.assertEqual(result["twoGraphJourneyObservation"]["actualSourceLastGraphId"], 987)
        self.assertEqual(result["crossGraphPhysicalContinuity"], "NOT_VERIFIED")

    def test_receiver_b_first_edge_mismatch_is_not_promoted(self):
        def wrong_receiver(config, shape, mode):
            if shape == "b-journey":
                return [456]
            return fake_trace(config, shape, mode)
        result = evaluate(trace_fn=wrong_receiver)
        self.assertEqual(result["twoGraphJourneyObservation"]["status"], "UNPROVEN")
        self.assertFalse(result["twoGraphLocalTracesMatched"])
        self.assertEqual(result["bLocalTracedTurns"], 3)

    def test_gap_and_snap_away_never_implicate_entire_frontier(self):
        displaced = edge(22, [[.0001, 0], [.0001, .0005]])
        adj = adjacency()
        result = evaluate(incoming=displaced, adj=adj)
        self.assertEqual(result["twoGraphJourneyObservation"]["status"], "UNPROVEN")
        self.assertEqual(result["discoveryCoverage"], "NOT_VERIFIED")
        self.assertEqual(result["journeyOptimality"], "NOT_VERIFIED")

        def snap_away(config, start, destination, mode):
            response = fake_route(config, start, destination, mode)
            if str(config) == "graph-B" and response["encodedShape"] == "b-journey":
                response["startOffsetMeters"] = 50
            return response
        result = evaluate(route_fn=snap_away)
        self.assertEqual(result["twoGraphJourneyObservation"]["status"], "UNPROVEN")
        self.assertEqual(result["crossSeamTurnLegality"], "NOT_VERIFIED")

    def test_budget_preserves_all_outgoing_native_alternatives(self):
        result = evaluate(budget=1)
        self.assertEqual(result["outgoingAlternativesEnumerated"], 3)
        self.assertEqual(result["outgoingAlternativesProbed"], 1)
        self.assertEqual(result["outgoingAlternativesUnprobed"], 2)
        self.assertEqual(
            [r["outgoingDirectedGraphId"] for r in result[
                "bLocalTurnObservation"]["allNativeOutgoingAlternatives"]],
            [31, 32, 33],
        )
        self.assertTrue(result["twoGraphLocalTracesMatched"])
        self.assertEqual(result["productionPublication"], "BLOCKED")

    def test_forward_access_rejection_cannot_establish_global_negative(self):
        car_only = edge(11, [[0, 0], [0, .0005]], mask=1)
        result = evaluate(source=car_only, mode="motorcycle")
        self.assertEqual(result["twoGraphJourneyObservation"]["status"], "UNPROVEN")
        self.assertFalse(result["twoGraphLocalTracesMatched"])
        self.assertEqual(result["discoveryCoverage"], "NOT_VERIFIED")

    def test_native_adjacency_corruption_fails_before_any_valhalla_call(self):
        tampered = adjacency()
        tampered["outgoingDirectedEdges"][0]["graphId"] = 999
        def no_route(*_args):
            self.fail("Should fail before any route is requested")
        with self.assertRaisesRegex(ValueError, "Missing/reordered"):
            evaluate(adj=tampered, route_fn=no_route)

    def test_unproven_b_turn_stays_distinct_from_journey(self):
        def nonconsecutive_b_turn(config, shape, mode):
            if shape.startswith("b-") and shape != "b-journey":
                return [22, 777, 31]
            return fake_trace(config, shape, mode)
        result = evaluate(trace_fn=nonconsecutive_b_turn)
        self.assertEqual(result["bLocalTracedTurns"], 0)
        self.assertTrue(result["twoGraphLocalTracesMatched"])
        self.assertEqual(result["crossSeamTurnLegality"], "NOT_VERIFIED")

    def test_inconclusive_b_journey_keeps_positive_local_turn_evidence(self):
        def unable_to_complete_b_leg(config, start, destination, mode):
            result = fake_route(config, start, destination, mode)
            if result["encodedShape"] == "b-journey":
                return {"status": "INCONCLUSIVE", "reason": "Routing engine unavailable"}
            return result
        result = evaluate(route_fn=unable_to_complete_b_leg)
        self.assertEqual(result["bLocalTracedTurns"], 3)
        self.assertEqual(result["twoGraphJourneyObservation"]["status"], "INCONCLUSIVE")
        self.assertFalse(result["twoGraphLocalTracesMatched"])
        self.assertEqual(result["outgoingAlternativesEnumerated"], 3)
        self.assertEqual(result["crossSeamTurnLegality"], "NOT_VERIFIED")

    def test_invalid_mode_budget_and_coordinates_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            evaluate(mode="foot")
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            evaluate(budget=0)
        with self.assertRaisesRegex(ValueError, "Invalid"):
            evaluate(origin={"lat": float("nan"), "lng": 0.0})

    def test_falsified_source_graph_id_cannot_count_as_cross_graph_identity(self):
        # Independent graphs can coincidentally contain the same numeric GraphId.
        spoofed_a = edge(22, [[0, 0], [0, .0005]])
        result = evaluate(source=spoofed_a)
        self.assertFalse(result["twoGraphLocalTracesMatched"])
        self.assertEqual(result["crossGraphPhysicalContinuity"], "NOT_VERIFIED")


if __name__ == "__main__":
    unittest.main()
