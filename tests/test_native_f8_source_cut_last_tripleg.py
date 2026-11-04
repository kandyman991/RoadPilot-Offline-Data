"""Original A-side final edge TripLeg proofs require exact native identities."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from prove_native_f8_source_cut_last_tripleg import (
    STATUS_PROVEN, classify_source_last_edge, verify_one_side,
    prove_one_hop_local_source_predecessors,
)


def candidate(gid=111):
    return {
        "finalDirectedGraphId": gid,
        "nativeEndNodeGraphId": 222,
        "sourceInteriorSampleAnnotationOnly": {"lat": 47.0, "lng": 11.0},
        "nativeTerminal": {"lat": 47.0001, "lng": 11.0},
        "vehicleModes": ["auto"],
        "sourceStartNodeAnnotationOnly": {"lat": 47.0, "lng": 11.0},
    }


def valid_route(gid=111):
    return {
        "status": "SUCCEEDED",
        "originalRouteEdgeIdentity": "ORIGINAL_VALHALLA_ROUTE_PROTOBUF",
        "edgeIdOrigin": "ORIGINAL_TRIPLEG_NODE_EDGE_PROTOBUF",
        "firstDirectedGraphId": 555,
        "lastDirectedGraphId": gid,
        "originalNativeDirectedGraphIds": [gid],
        "startOffsetMeters": 0.03, "endOffsetMeters": 0.04,
        "endActual": {"lat": 47.0001, "lng": 11.0},
    }


def evidence(gid=111, crossing=True, mode_status="NO_OTHER_NATIVE_MODE_ACCESSIBLE_HIERARCHY_OUTGOING"):
    return {
        "originalDirectedGraphId": gid,
        "nativeEndNodeGraphId": 222,
        "candidateSuppressed": False,
        "originalDirectedEdgeIntersects25kmSourceCut": crossing,
        "originalModeEndStatus": {"auto": {"status": mode_status}},
    }


class NativeFinalSourceCutRouteTests(unittest.TestCase):
    def test_only_original_last_tripleg_directed_id_proves_edge(self):
        result = classify_source_last_edge(valid_route(), candidate())
        self.assertEqual(result["sourceLastEdgeProof"], STATUS_PROVEN)
        self.assertEqual(result["originalNativeTripLegDirectedGraphIds"], [111])
        self.assertNotIn("physicalRoadUniqueness", result)

    def test_route_success_without_correct_last_id_is_not_proven(self):
        for attr, wrong in (
            ("lastDirectedGraphId", 999),
            ("originalNativeDirectedGraphIds", [999]),
            ("edgeIdOrigin", "GRAPH_MATCHED_TRACE_NOT_ORIGINAL"),
            ("endOffsetMeters", 5.),
            ("startOffsetMeters", 5.),
            ("endActual", {"lat": 47.01, "lng": 11.0}),
        ):
            item = valid_route()
            item[attr] = wrong
            with self.subTest(attr=attr):
                self.assertEqual(
                    classify_source_last_edge(item, candidate())["sourceLastEdgeProof"],
                    "NOT_VERIFIED")

    def test_failed_or_inconclusive_original_valhalla_route_retained(self):
        for status in ("FAILED", "INCONCLUSIVE", "NOT_RUN"):
            res = classify_source_last_edge(
                {"status": status, "reason": "Valhalla couldn't route"}, candidate())
            self.assertEqual(res["sourceLastEdgeProof"], "NOT_VERIFIED")
            self.assertEqual(res["originalRouteStatus"], status)

    def test_geometric_source_cut_not_validated_as_transfer(self):
        a = candidate()
        h = evidence()
        side = {"terminalCandidates": [a], "uniqueOriginalTerminalCandidateGraphIds": 1}
        hist = {"allOriginalSourceFinalEdgeCandidateProofs": [h],
                "modeStopNativeGraphIdsReconciled": 1}
        with patch("prove_native_f8_source_cut_last_tripleg.route_with_original_ids",
                   return_value=valid_route()) as route:
            result = verify_one_side(Path("src.json"), side, hist, Path("binary"), "source")
            route.assert_called_once()
        self.assertEqual(result["classifications"][STATUS_PROVEN], 1)
        self.assertEqual(result["physicalRoadUniqueLastDirectedEdge"], "NOT_VERIFIED")
        self.assertEqual(result["cutCandidateOriginalTripLegProof"][0][
            "originalReceiverRoad"], "NOT_STARTED")

    def test_uncrossed_candidate_is_not_removed_from_original_source(self):
        a = candidate()
        side = {"terminalCandidates": [a], "uniqueOriginalTerminalCandidateGraphIds": 1}
        hist = {"allOriginalSourceFinalEdgeCandidateProofs": [evidence(crossing=False)],
                "modeStopNativeGraphIdsReconciled": 1}
        with patch("prove_native_f8_source_cut_last_tripleg.route_with_original_ids") as route:
            result = verify_one_side(Path("src.json"), side, hist, Path("binary"), "source")
            route.assert_not_called()
        self.assertEqual(result["classifications"][
            "nativeCandidatesNotOnCutStillPreservedUpstream"], 1)
        self.assertTrue(result["noOriginalCandidateSuppression"])

    def test_hierarchy_alternative_never_prevents_original_route_probe(self):
        a = candidate()
        h = evidence(mode_status="HIERARCHY_MODE_ACCESSIBLE_ALTERNATIVES_UNRESOLVED")
        side = {"terminalCandidates": [a], "uniqueOriginalTerminalCandidateGraphIds": 1}
        hist = {"allOriginalSourceFinalEdgeCandidateProofs": [h],
                "modeStopNativeGraphIdsReconciled": 1}
        with patch("prove_native_f8_source_cut_last_tripleg.route_with_original_ids",
                   return_value=valid_route()) as route:
            result = verify_one_side(Path("src.json"), side, hist, Path("binary"), "source")
            route.assert_called_once()
        self.assertEqual(result["classifications"][
            "unresolvedNativeHierarchyModeAlternatives"], 1)
        mode = result["cutCandidateOriginalTripLegProof"][0]["vehicleModes"]["auto"]
        self.assertEqual(mode["sourceLastEdgeProof"], STATUS_PROVEN)
        self.assertEqual(mode["uniqueFinalPhysicalRoadEdgeStatus"], "NOT_VERIFIED")
        self.assertEqual(mode["nativeSourceHierarchyModeStatus"],
                         "HIERARCHY_MODE_ACCESSIBLE_ALTERNATIVES_UNRESOLVED")

    def test_short_terminal_fallback_proves_both_exact_original_tripleg_ids(self):
        fake_rows = [
            [{"sourceGraphId": 111, "endNodeGraphId": 222,
              "opposingGraphId": 50}],
            [{"sourceGraphId": 50, "endNodeGraphId": 333,
              "endLat": 47., "endLon": 11.,
              "outgoingDirectedEdges": [{"graphId": 444}, {"graphId": 111}]}],
            [{"sourceGraphId": 444, "opposingGraphId": 555}],
            [{"sourceGraphId": 555, "endNodeGraphId": 333,
              "forwardAccess": 1025, "wayId": 20,
              "directedGeometry": [[47., 10.999], [47., 11.]]}],
        ]
        with patch("prove_native_f8_source_cut_last_tripleg.native_original_rows",
                   side_effect=fake_rows) as rows, patch(
            "prove_native_f8_source_cut_last_tripleg.route_with_original_ids",
                   return_value=valid_route()) as route:
            result = prove_one_hop_local_source_predecessors(
                Path("A"), candidate(), "auto", Path("route"), Path("native"))
            self.assertEqual(rows.call_count, 4)
            route.assert_called_once()
        self.assertEqual(result["status"], STATUS_PROVEN)
        self.assertEqual(result["exactOriginalOneHopProofCount"], 1)
        self.assertTrue(result["allRootPredecessorAlternativesCaptured"])
        self.assertEqual(result["upstreamProbes"][0]["incomingOriginalDirectedGraphId"], 555)
        self.assertEqual(result["physicalRoadDirectionClass"], "NOT_VERIFIED")

    def test_fallback_never_stops_at_first_success_or_suppresses_branches(self):
        fake_rows = [
            [{"sourceGraphId": 111, "endNodeGraphId": 222, "opposingGraphId": 50}],
            [{"sourceGraphId": 50, "endNodeGraphId": 333, "endLat": 47.,
              "endLon": 11., "outgoingDirectedEdges": [
                {"graphId": 444}, {"graphId": 666}, {"graphId": 111}]}],
            [{"sourceGraphId": 444, "opposingGraphId": 555},
             {"sourceGraphId": 666, "opposingGraphId": 777}],
            [{"sourceGraphId": 555, "endNodeGraphId": 333, "forwardAccess": 1025,
              "wayId": 20, "directedGeometry": [[47., 10.999], [47., 11.]]},
             {"sourceGraphId": 777, "endNodeGraphId": 333, "forwardAccess": 1025,
              "wayId": 21, "directedGeometry": [[47., 10.998], [47., 11.]]}],
        ]
        second = {**valid_route(), "firstDirectedGraphId": 777}
        with patch("prove_native_f8_source_cut_last_tripleg.native_original_rows",
                   side_effect=fake_rows), patch(
            "prove_native_f8_source_cut_last_tripleg.route_with_original_ids",
                   side_effect=[valid_route(), second]) as route:
            proof = prove_one_hop_local_source_predecessors(
                Path("A"), candidate(), "auto", Path("route"), Path("native"))
            self.assertEqual(route.call_count, 2)
        self.assertEqual(proof["exactOriginalOneHopProofCount"], 2)
        self.assertEqual(len(proof["upstreamProbes"]), 2)

    def test_missing_or_repeated_native_cut_graphids_abort(self):
        side = {"terminalCandidates": [candidate(), candidate()],
                "uniqueOriginalTerminalCandidateGraphIds": 2}
        hist = {"allOriginalSourceFinalEdgeCandidateProofs": [evidence(), evidence()],
                "modeStopNativeGraphIdsReconciled": 2}
        with self.assertRaisesRegex(ValueError, "Repeated"):
            verify_one_side(Path("src.json"), side, hist, Path("binary"), "source")


if __name__ == "__main__":
    unittest.main()
