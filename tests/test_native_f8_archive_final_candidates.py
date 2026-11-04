"""All known original Valhalla final-edge witnesses must exist in full archive."""
from __future__ import annotations

import copy
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from reconcile_native_f8_archive_final_candidates import reconcile, present_in_native_archive

SHA="sha256:"+"a"*64
GRAPH={"from":SHA,"to":"sha256:"+"b"*64}
FILES={"pair":SHA,"from-manifest":SHA,"to-manifest":SHA,
       "from-buffer":SHA,"to-buffer":SHA}
BASE=802
DIRECT=BASE
FINAL=BASE+(1<<25)
PRED=BASE+(2<<25)
PROVED="ORIGINAL_SOURCE_LAST_DIRECTED_TRIPLEG_GRAPHID_MATCHED"


def mode(gid, seq):
    return {"sourceLastEdgeProof": PROVED,
            "originalRouteStatus":"SUCCEEDED",
            "originalNativeLastGraphId":gid,
            "originalNativeTripLegDirectedGraphIds":list(seq),
            "startSnapMeters":0.03,"endSnapMeters":0.04}


def reports():
    archive_side={
        "originalArchiveTiles":[{"tileGraphId":BASE,"originalDirectedCount":3}],
        "archiveTileCount":1,
        "originalDirectedCutShapeCount":2,
        "unresolvedOriginalNativeZeroLengthGeometryCount":0,
        "unresolvedOriginalNativeZeroLengthGeometries":[],
        "allOriginalDirectedCutObservations":[
            {"originalDirectedGraphId":DIRECT},
            {"originalDirectedGraphId":PRED}],
    }
    direct_side={
        "cutCandidateOriginalTripLegProof":[{
            "originalNativeSourceDirectedGraphId":DIRECT,
            "candidateSuppressed":False,
            "vehicleModes":{x:mode(DIRECT,[DIRECT]) for x in ("auto","motorcycle")},
        }]
    }
    beyond_side={
        "beyondCutOriginalFinalEdgeProofs":[{
            "originalFinalDirectedGraphId":FINAL,
            "noOriginalBranchesSuppressed":True,
            "originalFinalDirectedEdgeEntirelyBeyondOriginalSource25kmCut":True,
            "originalDirectedCutCrossingPredecessorPaths":[{
                "originalDirectedGraphId":PRED,
                "intersectsOriginalSource25kmCut":True,
                "nativeForwardDirectedPathToFinal":[PRED,FINAL],
            }],
            "originalSourceOriginalValhallaTripLeg":{
                "originalSourceCutRouteProofs":[{
                    "originalDirectedCutEdge":PRED,
                    "nativeForwardDirectedPathToFinal":[PRED,FINAL],
                    "originalRouteModeProofs":{
                        x:{**mode(FINAL,[PRED,FINAL]),
                           "originalSourceCutPathExactTripLegSequence":True}
                        for x in ("auto","motorcycle")},
                }]
            }
        }]
    }
    archive={"schema":"roadpilot.f8-all-original-source-archive-tile-cut-census",
             "version":1,"pairId":"it-at",
             "productionPublication":"BLOCKED",
             "sourceGraphFingerprints":dict(GRAPH),
             "originalGraphArchiveTileInventory":
                "ALL_GRAPHREADER_GETTILESET_TILES_ENUMERATED",
             "immutableOriginalSourceSHA256":dict(FILES),
             "directions":{s:copy.deepcopy(archive_side) for s in ("from-to","to-from")}}
    direct={"schema":"roadpilot.f8-original-source-cut-last-tripleg",
            "pairId":"it-at","productionPublication":"BLOCKED",
            "sourceGraphFingerprints":dict(GRAPH),
            "immutableSourceSHA256":dict(FILES),
            "directions":{s:copy.deepcopy(direct_side) for s in ("from-to","to-from")}}
    beyond={"schema":"roadpilot.f8-original-source-beyond-cut-last-edge",
            "pairId":"it-at","productionPublication":"BLOCKED",
            "immutableSourceSHA256":dict(FILES),
            "directions":{s:copy.deepcopy(beyond_side) for s in ("from-to","to-from")}}
    return archive,direct,beyond


class KnownOriginalFinalCandidateTests(unittest.TestCase):
    def test_tiled_original_graphids_validate_same_source_level_and_index(self):
        self.assertTrue(present_in_native_archive(DIRECT,{BASE:3}))
        self.assertTrue(present_in_native_archive(FINAL,{BASE:3}))
        self.assertFalse(present_in_native_archive(BASE+(3<<25),{BASE:3}))
        self.assertFalse(present_in_native_archive(True,{BASE:3}))

    def test_car_motorcycle_original_final_proofs_and_predecessor_all_retained(self):
        r=reconcile(*reports())
        self.assertEqual(r["productionPublication"],"BLOCKED")
        for side in ("from-to","to-from"):
            row=r["directions"][side]
            self.assertEqual(row["allPreviouslyProvedFinalDirectedGraphIdsPresentInOriginalArchive"],2)
            self.assertEqual(row["allBeyondCutOriginalPredecessorRoutes"],1)
            self.assertEqual(row["valhallaExactBeyondCutRouteModeWitnesses"],2)
            self.assertEqual(row["globalPhysicalRoadDirectionUniqueness"],"NOT_VERIFIED")

    def test_missing_original_final_graphid_fails_closed(self):
        source=reports()
        source[0]["directions"]["from-to"]["originalArchiveTiles"][0][
            "originalDirectedCount"]=1
        with self.assertRaisesRegex(ValueError,"absent from native archive"):
            reconcile(*source)

    def test_native_cut_predecessor_missing_fails_closed(self):
        source=reports()
        source[0]["directions"]["to-from"]["allOriginalDirectedCutObservations"].pop()
        source[0]["directions"]["to-from"]["originalDirectedCutShapeCount"]=1
        with self.assertRaisesRegex(ValueError,"chain missing"):
            reconcile(*source)

    def test_beyond_cut_final_cannot_be_its_own_source_cut_observation(self):
        source=reports()
        a=source[0]["directions"]["to-from"]
        a["allOriginalDirectedCutObservations"].append({"originalDirectedGraphId":FINAL})
        a["originalDirectedCutShapeCount"]+=1
        with self.assertRaisesRegex(ValueError,"intersects cut"):
            reconcile(*source)

    def test_zero_length_native_edge_cannot_be_promoted_as_proved_final(self):
        source=reports()
        a=source[0]["directions"]["to-from"]
        a["unresolvedOriginalNativeZeroLengthGeometries"].append(
            {"originalDirectedGraphId":FINAL})
        a["unresolvedOriginalNativeZeroLengthGeometryCount"]=1
        with self.assertRaisesRegex(ValueError,"zero-length"):
            reconcile(*source)

    def test_original_valhalla_route_sequence_change_rejected(self):
        source=reports()
        witness=source[2]["directions"]["from-to"]["beyondCutOriginalFinalEdgeProofs"][0][
            "originalSourceOriginalValhallaTripLeg"]["originalSourceCutRouteProofs"][0]
        witness["originalRouteModeProofs"]["auto"]["originalNativeTripLegDirectedGraphIds"]=[DIRECT,FINAL]
        with self.assertRaisesRegex(ValueError,"TripLeg"):
            reconcile(*source)

    def test_missing_motorcycle_original_route_proof_rejected(self):
        source=reports()
        p=source[2]["directions"]["from-to"]["beyondCutOriginalFinalEdgeProofs"][0][
            "originalSourceOriginalValhallaTripLeg"]["originalSourceCutRouteProofs"][0][
            "originalRouteModeProofs"]
        p["motorcycle"]={"sourceLastEdgeProof":"NOT_VERIFIED"}
        with self.assertRaisesRegex(ValueError,"all-mode"):
            reconcile(*source)

    def test_no_cross_graph_numeric_equality_required(self):
        r=reconcile(*reports())
        self.assertEqual(r["directions"]["from-to"]["originalDirectFinalGraphIdsAtCut"],
                         r["directions"]["to-from"]["originalDirectFinalGraphIdsAtCut"])
        self.assertEqual(r["receivingGraphCorrelation"],"NOT_STARTED")

    def test_mutated_original_source_manifest_sha_rejected(self):
        source=reports()
        source[1]["immutableSourceSHA256"]["from-manifest"]="sha256:"+"c"*64
        with self.assertRaisesRegex(ValueError,"manifest SHA differs"):
            reconcile(*source)


if __name__=="__main__":
    unittest.main()
