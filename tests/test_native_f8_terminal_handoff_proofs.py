"""Terminal-boundary journey proofs must trace the nominated edge on BOTH graphs."""
from __future__ import annotations

import copy
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from probe_native_f8_terminal_handoffs import (
    check_terminal, inspect, candidate_pool, valid_pair_audit,
    strict_point, EXACT_HANDOFF_TOLERANCE_METRES,
)
from test_native_f8_pair_evidence import identity

START = {"lat": 46.501885, "lng": 13.592668}
DEST = {"lat": 46.592234, "lng": 13.846448}
X = {"lat": 46.591066, "lng": 13.828377}


def candidate(source_id=11, receiver_id=22):
    return {
        "sourceDirectedGraphId": source_id,
        "sourceEndNodeGraphId": 150,
        "receiverIncomingGraphId": receiver_id,
        "receiverEndNodeGraphId": 250,
        "handoff": X,
        "receiverEnd": dict(X),
        "sourceForwardAccess": 1025,
        "receiverForwardAccess": 1025,
        "outgoing": {"auto": [33], "motorcycle": [33]},
    }


def leg(start, end):
    return {
        "status": "SUCCEEDED", "startActual": start, "endActual": end,
        "startOffsetMeters": 0, "endOffsetMeters": 0,
        "durationSeconds": 10.0, "distanceKm": 1.0,
        "encodedShape": "route-shape",
    }


def fake_route(_config, start, end, _mode):
    return leg(start, end)


def traces_for(first=(11,), second=(33,)):
    def trace(config, _shape, _mode):
        return list(first if str(config) == "A" else second)
    return trace


def pair_and_audit():
    pair = identity()
    obs = {
        "sourceDirectedGraphId": 11,
        "sourceEndNodeGraphId": 150,
        "sourceEnd": [X["lat"], X["lng"]],
        "sourceForwardAccess": 1025,
        "sourceWayId": 900,
        "nearbyReceiverIncoming": [
            {
                "receiverDirectedGraphId": 22,
                "receiverEndNodeGraphId": 250,
                "receiverWayId": 900,
                "receiverForwardAccess": 1025,
                "receiverDeadend": False,
                "sameWay": True, "distanceMetres": 0,
            }
        ]
    }
    audit = {
        "schema": "roadpilot.native-f8-receiver-topology-audit",
        "version": 0, "pairId": pair["pairId"],
        "state": "INCOMPLETE", "androidParity": "NOT_VERIFIED",
        "productionPublication": "BLOCKED",
        "graphFingerprints": {
            "from": pair["fromGraphFingerprint"],
            "to": pair["toGraphFingerprint"],
        },
        "fromTo": {"observations": [obs]},
        "toFrom": {"observations": [obs]},
    }
    receiver = [{
        "sourceGraphId": 22, "endNodeGraphId": 250,
        "endLat": X["lat"], "endLon": X["lng"],
        "wayId": 900, "forwardAccess": 1025, "deadend": False,
        "opposingGraphId": 44,
        "outgoingDirectedEdges": [
            {"graphId": 44, "endNodeGraphId": 55, "forwardAccess": 1025,
             "isRoad": True, "isShortcut": False,
             "motorcycleBit": True, "autoBit": True},
            {"graphId": 33, "endNodeGraphId": 66, "forwardAccess": 1025,
             "isRoad": True, "isShortcut": False,
             "motorcycleBit": True, "autoBit": True}
        ]
    }]
    return pair, audit, receiver


class TerminalJourneyProofTests(unittest.TestCase):
    def test_both_graph_directed_edges_and_continuation_required(self):
        result = check_terminal(candidate(), Path("A"), Path("B"),
                                START, DEST, "auto",
                                fake_route, traces_for())
        self.assertEqual(result["status"], "VALIDATED_FOR_THIS_JOURNEY")
        self.assertEqual(result["actualSourceLastGraphId"], 11)
        self.assertEqual(result["actualReceiverFirstGraphId"], 33)

    def test_same_coordinate_wrong_source_final_edge_rejected(self):
        result = check_terminal(candidate(), Path("A"), Path("B"),
                                START, DEST, "motorcycle",
                                fake_route, traces_for(first=(88,)))
        self.assertEqual(result["status"], "UNPROVEN")
        self.assertIn("actual final edge differs", result["reason"])
        self.assertEqual(result["actualSourceLastGraphId"], 88)

    def test_b_receiver_does_not_continue_on_nominated_graph_node(self):
        result = check_terminal(candidate(), Path("A"), Path("B"),
                                START, DEST, "auto",
                                fake_route, traces_for(second=(77,)))
        self.assertEqual(result["status"], "UNPROVEN")
        self.assertIn("Graph B trace", result["reason"])

    def test_b_receiver_incoming_followed_by_outgoing_is_supported(self):
        result = check_terminal(candidate(), Path("A"), Path("B"),
                                START, DEST, "auto",
                                fake_route, traces_for(second=(22, 33)))
        self.assertEqual(result["status"], "VALIDATED_FOR_THIS_JOURNEY")
        rejected = check_terminal(candidate(), Path("A"), Path("B"),
                                  START, DEST, "auto",
                                  fake_route, traces_for(second=(22,)))
        self.assertEqual(rejected["status"], "UNPROVEN")

    def test_coordinate_gap_does_not_disappear_or_claim_success(self):
        c = candidate()
        c["receiverEnd"] = {"lat": X["lat"] + .00006, "lng": X["lng"]}
        result = check_terminal(c, Path("A"), Path("B"),
                                START, DEST, "auto",
                                fake_route, traces_for())
        self.assertEqual(result["status"], "UNPROVEN")
        self.assertGreater(result["sourceReceiverNodeGapMeters"],
                           EXACT_HANDOFF_TOLERANCE_METRES)

    def test_unavailable_trace_is_not_success(self):
        result = check_terminal(candidate(), Path("A"), Path("B"),
                                START, DEST, "auto",
                                fake_route, lambda *args: None)
        self.assertEqual(result["status"], "INCONCLUSIVE")

    def test_denied_mode_direction_is_not_success(self):
        c = candidate()
        c["sourceForwardAccess"] = 1
        result = check_terminal(c, Path("A"), Path("B"),
                                START, DEST, "motorcycle",
                                fake_route, traces_for())
        self.assertEqual(result["status"], "UNPROVEN")

    def test_input_fingerprint_binding_is_required(self):
        pair, audit, receiver = pair_and_audit()
        valid_pair_audit(pair, audit)
        bad = copy.deepcopy(audit)
        bad["graphFingerprints"]["to"] = "sha256:" + "0" * 64
        with self.assertRaisesRegex(ValueError, "fingerprint mismatch"):
            valid_pair_audit(pair, bad)

    def test_explicit_incomplete_budget_and_no_first_success_lockin(self):
        pair, audit, receiver = pair_and_audit()
        second = copy.deepcopy(audit["fromTo"]["observations"][0])
        second["sourceDirectedGraphId"] = 12
        second["sourceEndNodeGraphId"] = 151
        audit["fromTo"]["observations"].append(second)
        pool = candidate_pool(audit, "from-to", receiver)
        self.assertEqual([p["sourceDirectedGraphId"] for p in pool], [11, 12])
        report = inspect(pair, audit, receiver, Path("A"), Path("B"),
                         START, DEST, "from-to", "auto", 2,
                         fake_route, traces_for(first=(11,)))
        self.assertEqual(report["probed"], 2)
        self.assertEqual(report["validatedForThisJourneyOnly"], 1)
        self.assertEqual(
            report["bestOfProbedOnly"]["FASTER"],
            {"sourceDirectedGraphId": 11, "receiverIncomingGraphId": 22},
        )
        self.assertEqual(report["coverage"], "NOT_VERIFIED")
        self.assertEqual(report["productionPublication"], "BLOCKED")
        one = inspect(pair, audit, receiver, Path("A"), Path("B"),
                      START, DEST, "from-to", "auto", 1,
                      fake_route, traces_for(first=(11,)))
        self.assertEqual(one["unprobed"], 1)

    def test_focused_directed_pair_stays_bounded_and_provenance_explicit(self):
        pair, audit, receiver = pair_and_audit()
        report = inspect(
            pair, audit, receiver, Path("A"), Path("B"),
            START, DEST, "from-to", "auto", 1,
            fake_route, traces_for(),
            focused_identity=(11, 22),
        )
        self.assertEqual(report["selection"], "EXPLICIT_DIRECTED_PAIR")
        self.assertEqual(report["probed"], 1)
        self.assertEqual(report["terminalHypothesesInProvisionalCatalog"], 1)
        self.assertEqual(report["handoffTurnLegality"], "NOT_VERIFIED")
        with self.assertRaisesRegex(ValueError, "absent"):
            inspect(pair, audit, receiver, Path("A"), Path("B"),
                    START, DEST, "from-to", "auto", 1,
                    fake_route, traces_for(), focused_identity=(11, 999))
        with self.assertRaisesRegex(ValueError, "Invalid explicit"):
            inspect(pair, audit, receiver, Path("A"), Path("B"),
                    START, DEST, "from-to", "auto", 1,
                    fake_route, traces_for(), focused_identity=(11, 0))

    def test_diagnostic_uses_no_retired_osm_or_connector_matrix_producer(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "tools/probe_native_f8_terminal_handoffs.py").read_text()
        for retired in ("build_frontier_road_inventory", "build_crossing_candidates",
                        "build_region_connector_matrix", "plan_multiregion_route",
                        "roadpilot.runtime-connectivity"):
            self.assertNotIn(retired, source)

    def test_invalid_coordinates_rejected(self):
        for coords in ({"lat": float("nan"), "lng": 13.7},
                       {"lat": 92, "lng": 13.7}, {"lat": 46, "lng": float("inf")}):
            with self.assertRaisesRegex(ValueError, "Invalid"):
                strict_point(coords, "test")


if __name__ == "__main__":
    unittest.main()
