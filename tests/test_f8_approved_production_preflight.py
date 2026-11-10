"""Publication preflight must never manufacture a READY directed-road catalog."""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from preflight_f8_approved_directed_catalog import reconcile

HASH_A = "sha256:" + "a" * 64
HASH_B = "sha256:" + "b" * 64


def fixtures():
    catalog = {
        "schema": "roadpilot.f8-final-directed-connection-candidates",
        "version": 1,
        "pairId": "from__to",
        "fromRegionId": "from",
        "toRegionId": "to",
        "productionPublication": "BLOCKED",
        "physicalRoadIdentityAcceptance": "NOT_VERIFIED",
        "graphFingerprints": {"from": HASH_A, "to": HASH_B},
        "sourceBufferFingerprint": HASH_A,
        "receiverBufferFingerprint": HASH_B,
        "sourceGraphIndexFingerprint": HASH_A,
        "receiverGraphIndexFingerprint": HASH_B,
        "counts": {"eligibleSourceFinals": 2, "nativeBDirectedRoadMatchesAtX": 2},
        "nativeDirectedRoadMatchesAtX": [],
    }
    disposition = {
        "schema": "roadpilot.f8-pr127-bounded-physical-road-dispositions",
        "version": 1,
        "pairId": "from__to",
        "fromRegionId": "from",
        "toRegionId": "to",
        "productionPublication": "BLOCKED",
        "originalGraphArchiveSha256": {"from": HASH_A, "to": HASH_B},
        "nativeOriginalSourceTerminalCensus": "EXHAUSTIVE_WITHIN_PAIR_ENDPOINT_DOMAIN",
        "nativeLongEdgeOwningTileCoverage": "VERIFIED_WITHIN_PAIR_ENDPOINT_DOMAIN",
        "noAdditionalRoadTracingPerformed": True,
        "physicalRoadDirectionCompleteness": "NOT_VERIFIED",
        "androidProductionUIAcceptance": "NOT_VERIFIED",
        "sourceBufferFingerprint": HASH_A,
        "receiverBufferFingerprint": HASH_B,
        "sourceGraphIndexFingerprint": HASH_A,
        "receiverGraphIndexFingerprint": HASH_B,
        "counts": {
            "eligibleOriginalAExteriorTerminals": 2,
            "nativeBMatchedIncomingAApproaches": 2,
            "unlinkedOriginalSourceCutRootObservations": 1,
        },
        "nativeOriginalASourceFinalDispositions": [],
    }
    native_audit = {
        "pairId": "from__to",
        "productionPublication": "BLOCKED",
        "originalArchiveFingerprints": {"from": HASH_A, "to": HASH_B},
        "originalSourceFinalIdsCheckedAgainstIndependentNativeInventory": True,
        "originalBIncomingApproachReadbackVerified": True,
        "eligibleOriginalSourceFinals": 2,
        "verifiedNativeAOriginalBDirectedIncomingAtExactX": 2,
        "fullPhysicalRoadIdentityApproval": "NOT_VERIFIED",
    }
    for offset, mode_mask in ((0, 1025), (1, 1024)):
        aid, bid = 102 + offset, 202 + offset
        x = {"lat": 46.6 + offset / 10, "lng": 11.2 + offset / 10}
        catalog["nativeDirectedRoadMatchesAtX"].append({
            "sourceFinalDirectedGraphId": aid,
            "sourceFinalCoordinate": dict(x),
            "sourceValhallaProvedModes": (
                ["auto", "motorcycle"] if mode_mask == 1025 else ["motorcycle"]
            ),
            "status": "NATIVE_DIRECTED_ROAD_MATCH_AT_X",
            "productionRouteVerified": False,
            "receiverDirectedRoadsAtX": [{
                "receiverDirectedGraphId": bid,
                "receiverXPosition": "END_NODE" if offset == 0 else "INTERIOR",
                "productionRouteVerified": False,
                "distanceXMetres": 0.04,
                "directedApproachOverlapMetres": 25.0,
                "nativeCommonVehicleModes": mode_mask,
            }],
        })
        disposition["nativeOriginalASourceFinalDispositions"].append({
            "originalASourceFinalDirectedGraphId": aid,
            "exactX": dict(x),
            "originalAtoBIncomingDirectedApproach": "NATIVE_GEOMETRY_TOPOLOGY_VERIFIED",
            "originalSourceCarMotorcycleModeMask": mode_mask,
            "nativeBIncomingDirectedGraphIds": [bid],
            "nativeBIncomingDirectedOverlapMetres": {str(bid): 25.0},
            "nativeBIncomingAtXMaxDeviationMetres": 0.04,
            # Intentionally NO outgoing B legal branch in either source:
            # correspondence must NOT be gated on post-X continuation.
            "disposition": "NO_NATIVE_ALLOWED_B_BRANCH_AT_CHECKED_CONTEXT",
            "sourceRoadDirectionCensusCompleteness": "NOT_VERIFIED",
            "mustNotPublishAsReady": True,
        })
    return catalog, disposition, native_audit


def check(c, d, a):
    return reconcile(c, d, a, native_evidence_sha=HASH_A,
                     archive_from_sha=HASH_A, archive_to_sha=HASH_B)


class ApprovedCatalogPreflightTest(unittest.TestCase):
    def assert_denied(self, c, d, a, message):
        with self.assertRaisesRegex(ValueError, message):
            check(c, d, a)

    def test_outgoing_b_turn_cannot_become_match_gate(self):
        c, d, a = fixtures()
        report = check(c, d, a)
        self.assertEqual("BLOCKED", report["publication"])
        self.assertTrue(report["notForRoadPilotRuntime"])
        self.assertEqual(2, report["counts"]["independentlyReconciledOriginalASourceFinals"])
        self.assertEqual(2, report["counts"]["nativeDirectedBIncomingPhysicalRoadMatches"])
        self.assertEqual(2, len(report["nativeDirectedApproachesForReviewOnly"]))
        self.assertEqual(
            "NO_NATIVE_ALLOWED_B_BRANCH_AT_CHECKED_CONTEXT",
            next(iter(report["counts"]["outgoingBContextDispositionsNotRoadMatchGates"]))
        )
        self.assertEqual("INTERIOR",
            report["nativeDirectedApproachesForReviewOnly"][1]["receiverDirectedRoadsAtX"][0]["receiverXPosition"])
        self.assertNotIn("approval", report)
        self.assertNotIn("connections", report)
        self.assertNotIn("productionPublication", report)

    def test_original_a_source_removed_or_changed_fails(self):
        c, d, a = fixtures()
        c["nativeDirectedRoadMatchesAtX"].pop()
        self.assert_denied(c, d, a, "inventory incomplete")
        c, d, a = fixtures()
        c["nativeDirectedRoadMatchesAtX"][1]["sourceFinalDirectedGraphId"] = 102
        self.assert_denied(c, d, a, "inventory incomplete")
        c, d, a = fixtures()
        c["nativeDirectedRoadMatchesAtX"][0]["sourceFinalCoordinate"]["lat"] += 0.1
        self.assert_denied(c, d, a, "exact X disagrees")

    def test_receiver_missing_swapped_or_duplicated_fails(self):
        c, d, a = fixtures()
        c["nativeDirectedRoadMatchesAtX"][0]["receiverDirectedRoadsAtX"] = []
        self.assert_denied(c, d, a, "omitted or invented")
        c, d, a = fixtures()
        c["nativeDirectedRoadMatchesAtX"][1]["receiverDirectedRoadsAtX"][0]["receiverDirectedGraphId"] = 202
        self.assert_denied(c, d, a, "duplicated or invalid")
        c, d, a = fixtures()
        c["nativeDirectedRoadMatchesAtX"][0]["receiverDirectedRoadsAtX"][0]["distanceXMetres"] = .9
        self.assert_denied(c, d, a, "unsupported physical geometry")

    def test_original_mode_mutation_fails_even_with_matching_gps(self):
        c, d, a = fixtures()
        c["nativeDirectedRoadMatchesAtX"][1]["receiverDirectedRoadsAtX"][0]["nativeCommonVehicleModes"] = 1025
        self.assert_denied(c, d, a, "permissions wider")
        c, d, a = fixtures()
        c["nativeDirectedRoadMatchesAtX"][0]["sourceValhallaProvedModes"] = ["motorcycle"]
        self.assert_denied(c, d, a, "permissions differ")

    def test_unproven_semantic_lineage_cannot_be_set_verified(self):
        c, d, a = fixtures()
        c["productionPublication"] = "READY"
        self.assert_denied(c, d, a, "strictly BLOCKED")
        c, d, a = fixtures()
        d["nativeOriginalASourceFinalDispositions"][0]["sourceRoadDirectionCensusCompleteness"] = "VERIFIED"
        self.assert_denied(c, d, a, "Unexpected approval")
        c, d, a = fixtures()
        d["physicalRoadDirectionCompleteness"] = "VERIFIED"
        self.assert_denied(c, d, a, "Unexpected approval")
        c, d, a = fixtures()
        a["originalBIncomingApproachReadbackVerified"] = False
        self.assert_denied(c, d, a, "Independent original archive/native audit")

    def test_archive_hash_or_index_fingerprint_mutation_fails(self):
        c, d, a = fixtures()
        a["originalArchiveFingerprints"]["to"] = HASH_A
        self.assert_denied(c, d, a, "Independent original archive/native audit")
        c, d, a = fixtures()
        d["receiverGraphIndexFingerprint"] = HASH_A
        self.assert_denied(c, d, a, "fingerprint mismatch")


if __name__ == "__main__":
    unittest.main()
