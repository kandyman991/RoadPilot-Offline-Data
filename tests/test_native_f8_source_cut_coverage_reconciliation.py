"""Fail-closed overlap-window vs original source-cut predecessor coverage gates."""
from __future__ import annotations

import copy
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from reconcile_native_f8_source_cut_coverage import reconcile

SHA = "sha256:" + "a" * 64
GRAPH = {"from": SHA, "to": "sha256:" + "b" * 64}
INPUT = {"pair": SHA, "from-manifest": SHA, "to-manifest": SHA}
MODES = {mode: {"sourceLastEdgeProof":
                "ORIGINAL_SOURCE_LAST_DIRECTED_TRIPLEG_GRAPHID_MATCHED",
                "originalNativeLastGraphId": 11}
         for mode in ("auto", "motorcycle")}


def reports():
    observations = [
        {"originalDirectedGraphId": 11, "originalSourceBufferCutDirectedTravel":
         "OUTWARD_FROM_ORIGINAL_SOURCE_BUFFER"},
        {"originalDirectedGraphId": 12, "originalSourceBufferCutDirectedTravel":
         "OUTWARD_FROM_ORIGINAL_SOURCE_BUFFER"},
        {"originalDirectedGraphId": 13, "originalSourceBufferCutDirectedTravel":
         "INWARD_TOWARD_ORIGINAL_SOURCE_BUFFER"},
    ]
    cut_side = {
        "allOriginalDirectedCutObservations": observations,
        "originalSourceDirectedCutShapeCount": 3,
        "originalSourceDirectedGraphIdsAudited": 9,
    }
    direct_side = {"cutCandidateOriginalTripLegProof": [
        {"originalNativeSourceDirectedGraphId": 11, "vehicleModes": MODES}
    ]}
    beyond_side = {"beyondCutOriginalFinalEdgeProofs": [
        {"originalFinalDirectedGraphId": 40,
         "originalFinalDirectedEdgeEntirelyBeyondOriginalSource25kmCut": True,
         "completeness": "INCOMPLETE_BOUNDED",
         "originalDirectedCutCrossingPredecessorPaths": [
             {"originalDirectedGraphId": 12, "intersectsOriginalSource25kmCut": True,
              "nativeForwardDirectedPathToFinal": [12, 40]},
             {"originalDirectedGraphId": 14, "intersectsOriginalSource25kmCut": True,
              "nativeForwardDirectedPathToFinal": [14, 40]},
         ]}]}
    cut = {
        "schema": "roadpilot.f8-original-all-source-native-directed-cut-census",
        "version": 1, "pairId": "it-at", "productionPublication": "BLOCKED",
        "sourceCutCompleteness": "ALL_RETAINED_SOURCE_SCAN_ORIGINAL_DIRECTED_GRAPHIDS",
        "sourceGraphFingerprints": GRAPH,
        "originalSourceInputSHA256": {**INPUT, "native-binary": SHA},
        "directions": {side: copy.deepcopy(cut_side) for side in ("from-to", "to-from")}
    }
    direct = {
        "schema": "roadpilot.f8-original-source-cut-last-tripleg",
        "pairId": "it-at", "productionPublication": "BLOCKED",
        "sourceGraphFingerprints": GRAPH,
        "immutableSourceSHA256": {**INPUT, "native-endpoint-binary": SHA},
        "directions": {side: copy.deepcopy(direct_side) for side in ("from-to", "to-from")}
    }
    beyond = {
        "schema": "roadpilot.f8-original-source-beyond-cut-last-edge",
        "pairId": "it-at", "productionPublication": "BLOCKED",
        "immutableSourceSHA256": {**INPUT, "native-binary": SHA},
        "directions": {side: copy.deepcopy(beyond_side) for side in ("from-to", "to-from")}
    }
    return cut, direct, beyond


class SourceCutReconciliationTests(unittest.TestCase):
    def test_keep_all_original_cut_observations_and_missing_predecessor(self):
        result = reconcile(*reports())
        self.assertEqual(result["productionPublication"], "BLOCKED")
        self.assertEqual(result["completeOriginalGraphArchiveTileInventory"], "NOT_VERIFIED")
        for side in ("from-to", "to-from"):
            item = result["directions"][side]
            self.assertEqual(item["windowCapturedDirectedCutObservations"], 3)
            self.assertEqual(item["directOrPredecessorLinkedWindowCutGraphIds"], 2)
            self.assertEqual(item["unlinkedWindowCutGraphIds"], [13])
            self.assertEqual(item["beyondCutPredecessorsMissingFromWindowScan"], [14])
            self.assertEqual(item["beyondCutCandidatesWithBoundedUnresolvedBranches"], [40])
            self.assertTrue(item["noCutObservationSuppressed"])

    def test_independent_source_graphids_with_same_numeric_id_are_not_merged(self):
        result = reconcile(*reports())
        self.assertEqual(result["directions"]["from-to"]["unlinkedWindowCutGraphIds"], [13])
        self.assertEqual(result["directions"]["to-from"]["unlinkedWindowCutGraphIds"], [13])

    def test_missing_previously_verified_direct_edge_fails_closed(self):
        source = reports()
        source[0]["directions"]["from-to"]["allOriginalDirectedCutObservations"][0][
            "originalDirectedGraphId"] = 999
        with self.assertRaisesRegex(ValueError, "absent"):
            reconcile(*source)

    def test_duplicate_same_source_original_cut_id_rejected(self):
        source = reports()
        source[0]["directions"]["from-to"]["allOriginalDirectedCutObservations"][1][
            "originalDirectedGraphId"] = 11
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            reconcile(*source)

    def test_false_tripleg_identity_fails(self):
        source = reports()
        source[1]["directions"]["from-to"]["cutCandidateOriginalTripLegProof"][0][
            "vehicleModes"]["motorcycle"]["originalNativeLastGraphId"] = 99
        with self.assertRaisesRegex(ValueError, "TripLeg"):
            reconcile(*source)

    def test_wrong_predecessor_to_last_path_fails(self):
        source = reports()
        source[2]["directions"]["from-to"]["beyondCutOriginalFinalEdgeProofs"][0][
            "originalDirectedCutCrossingPredecessorPaths"][0][
            "nativeForwardDirectedPathToFinal"] = [12, 999]
        with self.assertRaisesRegex(ValueError, "path endpoints"):
            reconcile(*source)

    def test_input_sha_mismatch_fails(self):
        source = reports()
        source[2]["immutableSourceSHA256"]["from-manifest"] = "sha256:" + "c" * 64
        with self.assertRaisesRegex(ValueError, "SHA mismatch"):
            reconcile(*source)

    def test_wrong_native_executable_fails(self):
        source = reports()
        source[1]["immutableSourceSHA256"]["native-endpoint-binary"] = "sha256:" + "c" * 64
        with self.assertRaisesRegex(ValueError, "executable"):
            reconcile(*source)

    def test_published_claim_fails(self):
        source = reports()
        source[0]["productionPublication"] = "READY"
        with self.assertRaisesRegex(ValueError, "published"):
            reconcile(*source)

    def test_source_only_scope_never_claims_whole_graph(self):
        source = reports()
        source[0]["sourceCutCompleteness"] = "ALL_GRAPH_ARCHIVE_EDGES"
        with self.assertRaisesRegex(ValueError, "window-scanned"):
            reconcile(*source)


if __name__ == "__main__":
    unittest.main()
