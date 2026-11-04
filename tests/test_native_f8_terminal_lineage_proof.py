"""GraphStudio F8 terminal lineage proof: strict no-loss and original-route gates."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from shapely.geometry import Point, box
from shapely.prepared import prep

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from compile_native_f8_terminal_lineage_proof import (
    UNRESOLVED, atomic_write, build_side_ledger, check_original_terminal_route,
    expect_digest, pair_guard, select_for_original_route_proof
)
from probe_native_f8_clipped_terminal import _at


def edges():
    return [
        {"graphId": 101, "wayId": 88, "lat": 46.59, "lon": 13.82,
         "forwardAccess": 1025, "roadClass": 2},
        {"graphId": 102, "wayId": 88, "lat": 46.59, "lon": 13.82,
         "forwardAccess": 1025, "roadClass": 2}
    ]


def census():
    rows = [
        {"graphId": id, "endNodeGraphId": 300 + id,
         "wayIdAnnotationOnly": 88, "endLat": 46.591, "endLon": 13.83,
         "insidePeerBuffer": True,
         "terminalStatus": "NATIVE_GRAPH_LOCAL_MODE_TERMINAL_ONLY"}
        for id in (101, 102)
    ]
    return {
        "counts": {
            "autoGraphLocalFinalDirectedEdges": 2,
            "motorcycleGraphLocalFinalDirectedEdges": 2},
        "allGraphLocalModeTerminals": {
            "auto": rows, "motorcycle": rows}
    }


def spatial():
    p = _at({"lat": 46.591, "lng": 13.83})
    own_buffer = {"polygon": box(p.x - 15, p.y - 15, p.x + 15, p.y + 15)}
    peer_buffer = {"polygon": box(p.x - 150, p.y - 150, p.x + 150, p.y + 150)}
    own_core = prep(box(p.x - 2000, p.y - 2000, p.x - 1000, p.y - 1000))
    peer_core = prep(box(p.x - 250, p.y - 250, p.x + 250, p.y + 250))
    return own_buffer, peer_buffer, own_core, peer_core


class TerminalLineageGateTests(unittest.TestCase):
    def test_same_way_same_coordinate_different_directed_graphids_are_all_retained(self):
        a, b, own, peer = spatial()
        result = build_side_ledger(
            {"edges": edges()}, census(), a, b, own, peer, "from-to")
        for mode in ("auto", "motorcycle"):
            self.assertEqual(result[mode]["allGraphLocalModeTerminalCount"], 2)
            self.assertEqual(
                [x["sourceGraphId"] for x in result[mode]["allTerminals"]],
                [101, 102])
            self.assertEqual({x["physicalRoadLineage"] for x in result[mode]["allTerminals"]},
                             {UNRESOLVED})
            self.assertTrue(all(x["unbufferedCoreClassification"] == "RECEIVER_CORE"
                                for x in result[mode]["allTerminals"]))
            self.assertFalse(any(x["candidateSuppressed"]
                                 for x in result[mode]["allTerminals"]))
            selected = select_for_original_route_proof(
                result[mode], band_metres=20, page_offset=0, page_size=16)
            self.assertEqual([x["sourceGraphId"] for x in selected], [101, 102])
            self.assertFalse(result[mode]["witnessPriorityIsEligibility"])

    def test_witness_selection_never_removes_nonselected_source_edges(self):
        a, b, own, peer = spatial()
        result = build_side_ledger(
            {"edges": edges()}, census(), a, b, own, peer, "to-from")
        doc = result["auto"]
        self.assertEqual(select_for_original_route_proof(
            doc, band_metres=5, page_offset=0, page_size=16), [])
        self.assertEqual(select_for_original_route_proof(
            doc, band_metres=20, page_offset=1, page_size=1)[0]["sourceGraphId"], 102)
        self.assertEqual(len(doc["allTerminals"]), 2)
        self.assertEqual(doc["globalOnePhysicalRoadEdgePerDirection"], "NOT_VERIFIED")

    def test_wrong_terminal_identity_and_wrong_polygon_evidence_are_fatal(self):
        a, b, own, peer = spatial()
        bad = census()
        bad["allGraphLocalModeTerminals"]["auto"] = [
            {**bad["allGraphLocalModeTerminals"]["auto"][0], "graphId": 999},
            bad["allGraphLocalModeTerminals"]["auto"][1]]
        with self.assertRaisesRegex(ValueError, "Missing/duplicate"):
            build_side_ledger({"edges": edges()}, bad, a, b, own, peer, "from-to")
        bad = census()
        bad["allGraphLocalModeTerminals"]["auto"] = [
            {**bad["allGraphLocalModeTerminals"]["auto"][0], "insidePeerBuffer": False},
            bad["allGraphLocalModeTerminals"]["auto"][1]]
        with self.assertRaisesRegex(ValueError, "Peer SHA-bound"):
            build_side_ledger({"edges": edges()}, bad, a, b, own, peer, "from-to")

    def test_original_tripleg_last_edge_can_only_prove_nominated_route(self):
        row = {
            "sourceGraphId": 101,
            "terminalEndpoint": {"lat": 46.591, "lng": 13.83}
        }
        valid = {
            "status": "SUCCEEDED",
            "originalRouteEdgeIdentity": "ORIGINAL_VALHALLA_ROUTE_PROTOBUF",
            "edgeIdOrigin": "ORIGINAL_TRIPLEG_NODE_EDGE_PROTOBUF",
            "lastDirectedGraphId": 101,
            "originalNativeDirectedGraphIds": [199, 101],
            "startOffsetMeters": .1, "endOffsetMeters": .07,
            "endActual": {"lat": 46.591, "lng": 13.83},
        }
        result = check_original_terminal_route(row, valid)
        self.assertTrue(result["originalLastGraphLocalEdgeMatchesTerminal"])
        self.assertEqual(result["originalGraphLocalRouteDirectedGraphIds"], [199, 101])
        self.assertEqual(result["status"], "ORIGINAL_VALHALLA_LAST_EDGE_ON_THIS_ROUTE_PROVEN")
        self.assertEqual(result["physicalRoadDirectionUniqueness"], "NOT_VERIFIED_GLOBALLY")
        self.assertIn("NOT_PROVEN", check_original_terminal_route(
            row, {"status": "FAILED", "reason": "No route"})["status"])
        self.assertEqual(check_original_terminal_route(
            row, {"status": "FAILED", "reason": "No route"})["nativeFailureReason"],
            "No route")
        for other in (
            {**valid, "lastDirectedGraphId": 102},
            {**valid, "endOffsetMeters": 4.0},
            {**valid, "edgeIdOrigin": "TRACE_ATTRIBUTES_EDGE_WALK"},
            {**valid, "status": "FAILED"},
            {**valid, "originalNativeDirectedGraphIds": [199, 102]}
        ):
            self.assertFalse(check_original_terminal_route(
                row, other)["originalLastGraphLocalEdgeMatchesTerminal"])

    def test_source_coverage_and_pair_fingerprint_gate(self):
        pair = {k: "sha256:" + "a" * 64 for k in (
            "fromGraphFingerprint", "toGraphFingerprint",
            "fromBoundaryFingerprint", "toBoundaryFingerprint")}
        pair["pairId"] = "italy-nord-est__austria"
        rows = {"counts": {"nativeDirectedEdgesAudited": 2},
                "edgeCoverage": "ALL_SOURCE_NATIVE_SCAN_IDS_RECONCILED"}
        scan = {"edges": edges()}
        doc = {**pair,
               "schema": "roadpilot.f8-native-full-graph-local-terminal-census",
               "version": 1,
               "nativeTopologyCoverage": "ALL_RETAINED_NATIVE_SCAN_EDGES",
               "globalOneFinalRetainedEdgePerPhysicalRoadDirection": "NOT_VERIFIED",
               "sourceScanSHA256": {"from": "sha256:" + "a"*64,
                                    "to": "sha256:" + "b"*64},
               "directions": {"from-to": rows, "to-from": rows}}
        with patch("compile_native_f8_terminal_lineage_proof.pair_identity"):
            pair_guard(pair, doc, {"from-to": scan, "to-from": scan})
            with self.assertRaisesRegex(ValueError, "Inconsistent"):
                pair_guard(pair, {**doc, "directions": {
                    "from-to": {**rows, "counts": {"nativeDirectedEdgesAudited": 1}},
                    "to-from": rows}},
                    {"from-to": scan, "to-from": scan})
            with self.assertRaisesRegex(ValueError, "graph identity"):
                pair_guard({**pair, "fromGraphFingerprint": "sha256:" + "b"*64},
                           doc, {"from-to": scan, "to-from": scan})

    def test_evidence_immutable_pin_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "proof.json"
            atomic_write(p, {"productionPublication": "BLOCKED"})
            with self.assertRaisesRegex(ValueError, "overwrite"):
                atomic_write(p, {"productionPublication": "VALIDATED"})
            with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
                expect_digest(p, "sha256:" + "0"*64)
            q = Path(d) / "symlink.json"
            q.symlink_to(p)
            with self.assertRaisesRegex(ValueError, "symlink"):
                expect_digest(q, "sha256:" + "0"*64)


if __name__ == "__main__":
    unittest.main()
