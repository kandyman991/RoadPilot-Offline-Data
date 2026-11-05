import sys
from copy import deepcopy
from pathlib import Path
from unittest import TestCase

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from trace_f8_original_source_to_last_edge import is_ordered_subsequence
from emit_f8_verified_android_test_catalog import make_partial_cache


def valid_source_catalog():
    return {
        "schema":"roadpilot.f8-final-directed-connections","version":1,
        "productionPublication":"BLOCKED","sourceDiscoveryComplete":False,
        "physicalRoadPerDirectionGlobalUniqueness":"NOT_VERIFIED",
        "connections":[{
           "sourceRegionId":"italy-nord-est",
           "receiverRegionId":"austria",
           "sourceFinalDirectedGraphId":125,
           "sourceValhallaProvedModes":["auto","motorcycle"],
           "originalSourceFinalTopologyProof":{
                "auto":{"status":"NO_OTHER_NATIVE_PHYSICAL_FORWARD_CONTINUATION"},
                "motorcycle":{"status":"NO_OTHER_NATIVE_PHYSICAL_FORWARD_CONTINUATION"}},
           "receiverOptions":[
               {"receiverFirstDirectedGraphId":400,
                "travelModes":["auto","motorcycle"],
                "directedPhysicalGeometry":{"status":"FORWARD_CONTINUOUS"},
                "originalReceiverValhallaTripLeg":{
                    "auto":{"verified":True,"actualFirstDirectedGraphId":400,
                           "originalTripLegDirectedGraphIds":[400,405]},
                    "motorcycle":{"verified":True,"actualFirstDirectedGraphId":400,
                           "originalTripLegDirectedGraphIds":[400,405]}},
                },
               {"receiverFirstDirectedGraphId":420,
                "travelModes":["motorcycle"],
                "directedPhysicalGeometry":{"status":"FORWARD_CONTINUOUS"},
                "originalReceiverValhallaTripLeg":{
                    "motorcycle":{"verified":True,"actualFirstDirectedGraphId":420,
                                  "originalTripLegDirectedGraphIds":[420,425]}}}]}],
        "unresolvedSourceFinalEdges":[
            {"sourceRegionId":"italy-nord-est",
             "sourceFinalDirectedGraphId":123,
             "mustNotCreateConnection":True,
             "status":"ORIGINAL_SOURCE_HAS_FORWARD_CONTINUATION"}]}


class F8NativeLastEdgeDeliveryTest(TestCase):
    def test_ordered_original_a_chain_accepts_extra_valhalla_edges(self):
        self.assertTrue(is_ordered_subsequence([1,20,30,40,50],[1,30,50]))
        self.assertTrue(is_ordered_subsequence([1,20,30,40,50],[1,20,30,40,50]))

    def test_original_a_route_must_visit_source_branches_in_order(self):
        self.assertFalse(is_ordered_subsequence([1,20,30,40,50],[1,40,20,50]))
        self.assertFalse(is_ordered_subsequence([1,20,30,40,50],[1,22,50]))
        self.assertFalse(is_ordered_subsequence([1,20,30,40,50],[1,20,51]))

    def test_partial_android_cache_delivers_every_verified_receiver_branch(self):
        result=make_partial_cache(valid_source_catalog(),"d"*64)
        self.assertEqual(len(result["connections"]),1)
        self.assertEqual({x["receiverFirstDirectedGraphId"] for x in
                          result["connections"][0]["receiverOptions"]},{400,420})
        self.assertEqual(result["unresolvedSourceFinalEdges"],[])
        self.assertEqual(result["originalUnpublishedFullNativeUnresolvedCount"],1)
        self.assertFalse(result["sourceDiscoveryComplete"])
        self.assertEqual(result["productionPublication"],"BLOCKED")

    def test_non_final_source_cannot_enter_android_cache(self):
        p=valid_source_catalog()
        p["connections"][0]["originalSourceFinalTopologyProof"]["auto"][
            "status"]="ORIGINAL_SOURCE_GRAPH_HAS_FORWARD_ROAD_CONTINUATION"
        with self.assertRaisesRegex(ValueError,"[Nn]ot an actual native terminal"):
            make_partial_cache(p,"d"*64)

    def test_wrong_first_b_native_graphid_is_rejected(self):
        p=valid_source_catalog()
        p["connections"][0]["receiverOptions"][1][
             "originalReceiverValhallaTripLeg"]["motorcycle"]["actualFirstDirectedGraphId"]=421
        with self.assertRaisesRegex(ValueError,"not proved"):
            make_partial_cache(p,"d"*64)

    def test_duplicate_receiving_branch_is_rejected(self):
        p=valid_source_catalog()
        p["connections"][0]["receiverOptions"].append(deepcopy(
            p["connections"][0]["receiverOptions"][0]))
        with self.assertRaisesRegex(ValueError,"Repeated native receiver branch"):
            make_partial_cache(p,"d"*64)

    def test_complete_catalog_claim_is_rejected(self):
        p=valid_source_catalog()
        p["sourceDiscoveryComplete"]=True
        with self.assertRaises(ValueError):
            make_partial_cache(p,"d"*64)
