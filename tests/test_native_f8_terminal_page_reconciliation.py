"""Native F8 immutable route witness page reconciliation: no gaps or false proof."""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from reconcile_native_f8_terminal_proof_pages import reconcile_pages
from tests.test_native_f8_terminal_lineage_proof import spatial, edges, census
from compile_native_f8_terminal_lineage_proof import (
    build_side_ledger, select_for_original_route_proof
)


def page(offset: int) -> dict:
    own_buffer, peer_buffer, own_core, peer_core = spatial()
    sides = {}
    for direction in ("from-to", "to-from"):
        part = build_side_ledger(
            {"edges": edges()}, census(),
            own_buffer, peer_buffer, own_core, peer_core, direction)
        for mode, doc in part.items():
            chosen = select_for_original_route_proof(
                doc, band_metres=20, page_offset=offset, page_size=1)
            probes = []
            for row in chosen:
                good = row["sourceGraphId"] == 101
                status = (
                    "ORIGINAL_VALHALLA_LAST_EDGE_ON_THIS_ROUTE_PROVEN" if good else
                    "ORIGINAL_VALHALLA_LAST_EDGE_NOT_PROVEN"
                )
                row["originalRouteLastEdge"] = status
                probes.append({
                    "sourceGraphId": row["sourceGraphId"],
                    "originalLastGraphLocalEdgeMatchesTerminal": good,
                    "status": status,
                    "originalLastDirectedGraphId": row["sourceGraphId"] if good else None,
                    "originalGraphLocalRouteDirectedGraphIds":
                        [row["sourceGraphId"]] if good else [],
                    "nativeFailureReason": "Bad snap" if not good else None
                })
            doc["originalLastEdgesProven"] = sum(
                v["originalLastGraphLocalEdgeMatchesTerminal"] for v in probes)
            doc["originalRouteWitnessCount"] = len(probes)
            doc["selectedOriginalRouteWitnesses"] = probes
        sides[direction] = part
    return {
        "schema": "roadpilot.f8-original-terminal-lineage-ledger",
        "version": 1, "pairId": "a__b",
        "graphFingerprints": {"from": "fp-a", "to": "fp-b"},
        "boundaryFingerprints": {"from": "b-a", "to": "b-b"},
        "verified25kmBufferFingerprints": {"from": "buffer-a", "to": "buffer-b"},
        "fullNativeCensusSha256": "sha256:" + "0" * 64,
        "unbufferedCorePolygonProvenance": "ANNOTATION_ONLY",
        "unbufferedCorePolygonSha256": {"from": "core-a", "to": "core-b"},
        "originalNativeBinariesSha256": {"topology": "t", "originalRoute": "r"},
        "allSourceNativeDirectedScansReconciled": True,
        "oneFinalEdgePerPhysicalRoadAndDirection": "NOT_VERIFIED",
        "physicalRoadEquivalenceClasses": "NOT_ESTABLISHED",
        "independentReceivingGraphDirectionalHandoff": "NOT_VERIFIED",
        "productionPublication": "BLOCKED",
        "directions": sides
    }


class OriginalRoutePageReconciliationTests(unittest.TestCase):
    def test_exact_page_coverage_preserves_both_same_way_directed_ids(self):
        result = reconcile_pages([page(0), page(1)], band_metres=20)
        for direction in ("from-to", "to-from"):
            for mode in ("auto", "motorcycle"):
                row = result["directions"][direction][mode]
                self.assertEqual(row["fullSourceGraphLocalModeTerminalCount"], 2)
                self.assertEqual(row["prioritizedWitnessCount"], 2)
                self.assertEqual(row["originalValhallaWitnessesAttempted"], 2)
                self.assertEqual(row["originalLastDirectedGraphIdsProven"], 1)
                self.assertEqual([x["sourceGraphId"] for x in row["originalRoutesNotProven"]],
                                 [102])
                self.assertEqual(row["fullPrioritizedWitnessPageCoverage"],
                                 "PROVEN_NO_GAPS_OR_DUPLICATES")
        self.assertEqual(result["globalOneFinalPhysicalRoadEdgePerRoadAndDirection"],
                         "NOT_VERIFIED")
        self.assertEqual(result["productionPublication"], "BLOCKED")

    def test_missing_page_is_fatal(self):
        with self.assertRaisesRegex(ValueError, "Incomplete native directed witness"):
            reconcile_pages([page(0)], band_metres=20)

    def test_duplicate_page_is_fatal(self):
        with self.assertRaisesRegex(ValueError, "Repeated original route witness"):
            reconcile_pages([page(0), page(0), page(1)], band_metres=20)

    def test_page_reordering_route_identity_and_status_falsification_are_fatal(self):
        a = page(0)
        b = page(1)
        b["directions"]["from-to"]["auto"]["selectedOriginalRouteWitnesses"][0]["sourceGraphId"] = 101
        with self.assertRaisesRegex(ValueError, "omit/reorder"):
            reconcile_pages([a, b], band_metres=20)
        b = page(1)
        b["directions"]["from-to"]["auto"]["selectedOriginalRouteWitnesses"][0][
            "originalLastGraphLocalEdgeMatchesTerminal"] = True
        with self.assertRaisesRegex(ValueError, "status"):
            reconcile_pages([a, b], band_metres=20)

    def test_mixed_fingerprints_and_source_terminals_are_fatal(self):
        a, b = page(0), page(1)
        b["graphFingerprints"]["to"] = "stale"
        with self.assertRaisesRegex(ValueError, "provenance"):
            reconcile_pages([a, b], band_metres=20)
        b = page(1)
        b["directions"]["to-from"]["motorcycle"]["allTerminals"][0][
            "sourceRoadClass"] = 999
        with self.assertRaisesRegex(ValueError, "inventory changed"):
            reconcile_pages([a, b], band_metres=20)

    def test_coverage_never_claims_global_physical_uniqueness(self):
        a = page(0)
        a["oneFinalEdgePerPhysicalRoadAndDirection"] = "PROVEN"
        with self.assertRaisesRegex(ValueError, "Not a blocked"):
            reconcile_pages([a, page(1)], band_metres=20)
        a = page(0)
        b = page(1)
        b["directions"]["to-from"]["auto"]["globalOnePhysicalRoadEdgePerDirection"] = "VERIFIED"
        with self.assertRaisesRegex(ValueError, "global physical-road"):
            reconcile_pages([a, b], band_metres=20)


if __name__ == "__main__":
    unittest.main()
