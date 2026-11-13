from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from test_f8_approved_production_preflight import fixtures, check
from build_f8_native_auto_catalog import build

PRE_SHA = "sha256:" + "b" * 64


class NativeAutoCatalogTest(unittest.TestCase):
    def sample(self):
        catalog, disposition, audit = fixtures()
        return check(catalog, disposition, audit)

    def test_complete_original_directed_inputs_build_exact_auto_catalog_without_ready(self):
        r = build(self.sample(), PRE_SHA)
        self.assertEqual("BLOCKED_TEST_ONLY", r["publication"])
        self.assertEqual(2, r["counts"]["sourceConnections"])
        self.assertEqual(2, r["counts"]["receiverIncomingRoads"])
        self.assertEqual([], r["excludedSourceFinals"])
        self.assertEqual([102, 103],
            [x["sourceFinalDirectedGraphId"] for x in r["connections"]])
        self.assertIn("SEMANTIC_ORIGINAL_SOURCE_PHYSICAL_ROAD_LINEAGE_NOT_VERIFIED",
                      r["remainingProductionReview"])
        self.assertNotIn("approval", r)
        self.assertNotIn("producerEvidence", r)
        self.assertEqual("END_NODE", r["connections"][0]["receiverDirectedRoadsAtX"][0]["receiverXPosition"])

    def test_multiple_receiver_branches_survive_into_auto_catalog(self):
        preflight = self.sample()
        extra = copy.deepcopy(
            preflight["nativeDirectedApproachesForReviewOnly"][0]["receiverDirectedRoadsAtX"][0]
        )
        extra["receiverDirectedGraphId"] = 204
        preflight["nativeDirectedApproachesForReviewOnly"][0]["receiverDirectedRoadsAtX"].append(extra)
        preflight["counts"]["nativeDirectedBIncomingPhysicalRoadMatches"] = 3
        result = build(preflight, PRE_SHA)
        self.assertEqual(2, result["counts"]["sourceConnections"])
        self.assertEqual(3, result["counts"]["receiverIncomingRoads"])
        self.assertEqual([202, 204], [road["receiverDirectedGraphId"]
            for road in result["connections"][0]["receiverDirectedRoadsAtX"]])
        self.assertEqual("BLOCKED_TEST_ONLY", result["publication"])

    def test_native_submetre_receiving_road_is_retained_only_when_x_is_exact(self):
        preflight = self.sample()
        road = preflight['nativeDirectedApproachesForReviewOnly'][0][
            'receiverDirectedRoadsAtX'][0]
        road['directedApproachOverlapMeters'] = 0.884
        road['nativeXGapMeters'] = 0.023
        result = build(preflight, PRE_SHA)
        self.assertEqual(0.884, result['connections'][0][
            'receiverDirectedRoadsAtX'][0]['directedApproachOverlapMeters'])
        road['nativeXGapMeters'] = 0.15
        with self.assertRaisesRegex(ValueError, 'projection or directed overlap'):
            build(preflight, PRE_SHA)

    def test_untrusted_or_malformed_preflight_sha_cannot_be_provenance(self):
        for invalid in (
            "sha256:" + "Z" * 64,
            "sha256:" + "f" * 63,
            "sha256:" + "f" * 65,
        ):
            with self.assertRaisesRegex(ValueError, "Preflight proof SHA-256"):
                build(self.sample(), invalid)

    def test_missing_original_a_or_b_road_never_generates_a_partial_catalog(self):
        r = self.sample()
        r["nativeDirectedApproachesForReviewOnly"].pop()
        with self.assertRaisesRegex(ValueError, "Incomplete original A"):
            build(r, PRE_SHA)
        r = self.sample()
        r["nativeDirectedApproachesForReviewOnly"][0]["receiverDirectedRoadsAtX"] = []
        with self.assertRaisesRegex(ValueError, "Incomplete original A"):
            build(r, PRE_SHA)

    def test_invented_approval_and_mode_escalation_rejected(self):
        r = self.sample()
        r["publication"] = "READY"
        with self.assertRaisesRegex(ValueError, "BLOCKED"):
            build(r, PRE_SHA)
        r = self.sample()
        r["nativeDirectedApproachesForReviewOnly"][1]["receiverDirectedRoadsAtX"][0]["travelModes"] = ["car", "motorcycle"]
        with self.assertRaisesRegex(ValueError, "permissions exceed"):
            build(r, PRE_SHA)


if __name__ == "__main__":
    unittest.main()
