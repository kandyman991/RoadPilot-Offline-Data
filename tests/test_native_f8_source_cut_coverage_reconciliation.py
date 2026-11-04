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
PROVED = "ORIGINAL_SOURCE_LAST_DIRECTED_TRIPLEG_GRAPHID_MATCHED"
MODES = {mode: {"sourceLastEdgeProof": PROVED,
                "originalRouteStatus": "SUCCEEDED",
                "originalNativeLastGraphId": 11,
                "originalNativeTripLegDirectedGraphIds": [11],
                "startSnapMeters": 0.02, "endSnapMeters": 0.03}
         for mode in ("auto", "motorcycle")}


def original_witness(path):
    final = path[-1]
    return {
        "originalDirectedCutEdge": path[0],
        "nativeForwardDirectedPathToFinal": path,
        "originalRouteModeProofs": {
            mode: {"sourceLastEdgeProof": PROVED,
                   "originalRouteStatus": "SUCCEEDED",
                   "originalSourceCutPathExactTripLegSequence": True,
                   "originalNativeLastGraphId": final,
                   "originalNativeTripLegDirectedGraphIds": path,
                   "startSnapMeters": 0.01, "endSnapMeters": 0.05}
            for mode in ("auto", "motorcycle")
        },
    }


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
    direct_side = {"originalSourceCutCandidateDirectedEdges": 1,
                   "noOriginalCandidateSuppression": True,
                   "cutCandidateOriginalTripLegProof": [
        {"originalNativeSourceDirectedGraphId": 11, "vehicleModes": copy.deepcopy(MODES),
         "originalNativeSourceCutGeometryIntersects": True, "candidateSuppressed": False}
    ]}
    beyond_side = {"originalDirectedFinalEdgesBeyondCutIdentified": 1,
                   "originalSourceCandidateSuppression": "NONE",
                   "beyondCutOriginalFinalEdgeProofs": [
        {"originalFinalDirectedGraphId": 40,
         "originalFinalDirectedEdgeEntirelyBeyondOriginalSource25kmCut": True,
         "noOriginalBranchesSuppressed": True,
         "anyOriginalCutCrossingPredecessorLocated": True,
         "completeness": "INCOMPLETE_BOUNDED",
         "truncations": [{"reason": "BOUNDED_HOP_DEPTH_REACHED"}],
         "originalSourceOriginalValhallaTripLeg": {
             "originalSourceCutCrossingPathCount": 2,
             "originalSourceCutRouteProofs": [original_witness([12, 40]),
                                              original_witness([14, 40])],
             "routeModeCounts": {PROVED: 4},
         },
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


    def test_valid_short_original_final_uses_proved_immediate_predecessor(self):
        source = reports()
        row = source[1]["directions"]["from-to"]["cutCandidateOriginalTripLegProof"][0]
        upstream = {"sourceLastEdgeProof": PROVED, "originalRouteStatus": "SUCCEEDED",
                    "originalNativeLastGraphId": 11,
                    "originalNativeTripLegDirectedGraphIds": [10, 11],
                    "startSnapMeters": 0.03, "endSnapMeters": 0.02}
        fallback = {"sourceLastEdgeProof": PROVED,
                    "originalRouteStatus":
                        "SUCCEEDED_WITH_ORIGINAL_SOURCE_IMMEDIATE_PREDECESSOR",
                    "proofMethod": "ORIGINAL_SOURCE_IMMEDIATE_PREDECESSOR_TRIPLEG",
                    "originalNativeLastGraphId": 11,
                    "originalNativeTripLegDirectedGraphIds": [10, 11],
                    "originalOneHopImmediateSourcePredecessorProof": {
                        "status": PROVED,
                        "allRootPredecessorAlternativesCaptured": True,
                        "exactOriginalOneHopProofCount": 1,
                        "firstExactOriginalNativeTripLegGraphIds": [10, 11],
                        "upstreamProbes": [{
                            "mode": "auto",
                            "incomingOriginalDirectedGraphId": 10,
                            "originalTripLegFirstIsExactPredecessor": True,
                            "originalTripLegResult": upstream,
                            "proof": PROVED,
                        }]
                    }}
        row["vehicleModes"]["auto"] = fallback
        self.assertEqual(reconcile(*source)["productionPublication"], "BLOCKED")
        fallback["originalOneHopImmediateSourcePredecessorProof"][
            "upstreamProbes"][0]["originalTripLegFirstIsExactPredecessor"] = False
        with self.assertRaisesRegex(ValueError, "TripLeg"):
            reconcile(*source)

    def test_forged_direct_success_without_actual_ordered_tripleg_is_rejected(self):
        source = reports()
        item = source[1]["directions"]["from-to"]["cutCandidateOriginalTripLegProof"][0]
        item["vehicleModes"]["auto"]["originalNativeTripLegDirectedGraphIds"] = [99]
        with self.assertRaisesRegex(ValueError, "TripLeg"):
            reconcile(*source)

    def test_beyond_original_valhalla_witness_requires_matching_actual_graphids(self):
        source = reports()
        witness = source[2]["directions"]["from-to"]["beyondCutOriginalFinalEdgeProofs"][0][
            "originalSourceOriginalValhallaTripLeg"]["originalSourceCutRouteProofs"][0]
        proof = witness["originalRouteModeProofs"]["auto"]
        proof["originalNativeTripLegDirectedGraphIds"] = [11, 40]
        with self.assertRaisesRegex(ValueError, "beyond-cut mode proof"):
            reconcile(*source)

    def test_beyond_original_witness_needs_both_modes(self):
        source = reports()
        item = source[2]["directions"]["from-to"]["beyondCutOriginalFinalEdgeProofs"][0]
        for witness in item["originalSourceOriginalValhallaTripLeg"]["originalSourceCutRouteProofs"]:
            witness["originalRouteModeProofs"]["motorcycle"]["sourceLastEdgeProof"] = "NOT_VERIFIED"
        item["originalSourceOriginalValhallaTripLeg"]["routeModeCounts"][PROVED] = 2
        with self.assertRaisesRegex(ValueError, "both modes"):
            reconcile(*source)

    def test_one_failed_branch_is_preserved_without_losing_other_valid_witness(self):
        source = reports()
        item = source[2]["directions"]["from-to"]["beyondCutOriginalFinalEdgeProofs"][0]
        witness = item["originalSourceOriginalValhallaTripLeg"]["originalSourceCutRouteProofs"][0]
        witness["originalRouteModeProofs"]["auto"] = {
            "sourceLastEdgeProof": "NOT_VERIFIED", "reason": "LOCAL_ROUTE_FAILED"
        }
        item["originalSourceOriginalValhallaTripLeg"]["routeModeCounts"][PROVED] = 3
        result = reconcile(*source)
        self.assertEqual(result["directions"]["from-to"]["provedBeyondCutOriginalLastEdges"], 1)
        self.assertEqual(result["directions"]["from-to"][
            "beyondCutCandidatesWithBoundedUnresolvedBranches"], [40])

    def test_cut_branch_missing_route_witness_fails_closed(self):
        source = reports()
        item = source[2]["directions"]["to-from"]["beyondCutOriginalFinalEdgeProofs"][0]
        item["originalSourceOriginalValhallaTripLeg"]["originalSourceCutRouteProofs"].pop()
        with self.assertRaisesRegex(ValueError, "witness coverage"):
            reconcile(*source)

    def test_fake_original_mode_proof_status_rejected(self):
        source = reports()
        item = source[2]["directions"]["from-to"]["beyondCutOriginalFinalEdgeProofs"][0]
        witness = item["originalSourceOriginalValhallaTripLeg"]["originalSourceCutRouteProofs"][0]
        witness["originalRouteModeProofs"]["motorcycle"]["sourceLastEdgeProof"] = "READY"
        with self.assertRaisesRegex(ValueError, "witness status"):
            reconcile(*source)

    def test_cut_alternative_suppression_not_accepted(self):
        source = reports()
        item = source[2]["directions"]["from-to"]["beyondCutOriginalFinalEdgeProofs"][0]
        item["noOriginalBranchesSuppressed"] = False
        with self.assertRaisesRegex(ValueError, "preservation"):
            reconcile(*source)

    def test_predecessor_cap_must_not_be_concealed(self):
        source = reports()
        item = source[2]["directions"]["to-from"]["beyondCutOriginalFinalEdgeProofs"][0]
        item["truncations"] = []
        with self.assertRaisesRegex(ValueError, "traversal cap"):
            reconcile(*source)

    def test_cut_direct_coverage_counter_must_match_actual_records(self):
        source = reports()
        source[1]["directions"]["to-from"]["originalSourceCutCandidateDirectedEdges"] = 2
        with self.assertRaisesRegex(ValueError, "inventory"):
            reconcile(*source)


if __name__ == "__main__":
    unittest.main()
