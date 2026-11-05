"""Exact original source terminal gate must exclude intermediate A edges.

These regression cases use source-local directed geometry; none assumes
same numeric GraphIds or matching way names across two region archives.
"""
import copy
import sys
from pathlib import Path
from unittest import TestCase

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from gate_f8_source_final_native_topology import (
    validate_mode, gate_catalog, FINAL, INTERMEDIATE, AMBIGUOUS,
)


def edge(gid, coords):
    return {"sourceGraphId":gid,"directedGeometry":coords,"wayId":99,
            "forwardAccess":1025}


class NativeSourceFinalGateTest(TestCase):
    def setUp(self):
        self.a=edge(101,[[47.232463,11.392792],[47.233864,11.392306]])
        self.forward=edge(202,[[47.233864,11.392306],[47.237243,11.391179]])
        self.reverse=edge(404,[[47.233864,11.392306],[47.232463,11.392792]])
        self.fork=edge(303,[[47.233864,11.392306],[47.236000,11.392700]])
        self.root={
            "sourceGraphId":101,"endNodeGraphId":345,"opposingGraphId":404,
            "nativeAllHierarchyContinuationNodes":[
                {"allOutgoingDirectedEdges":[
                   {"graphId":404,"forwardAccess":1025,"isRoad":True,"isShortcut":False},
                   {"graphId":202,"forwardAccess":1025,"isRoad":True,"isShortcut":False},
                   {"graphId":303,"forwardAccess":1025,"isRoad":True,"isShortcut":False}]}]}
        self.geometry={202:self.forward,303:self.fork}

    def test_forward_same_source_graph_is_not_final_and_preserves_both_branches(self):
        value=validate_mode(self.a,self.root,self.geometry,"auto")
        self.assertEqual(value["status"],INTERMEDIATE)
        self.assertEqual({x["graphId"] for x in value["nativeSourceForwardContinuations"]},
                         {202,303})

    def test_mode_restriction_is_per_mode_not_duplicate_physical_road(self):
        root=copy.deepcopy(self.root)
        root["nativeAllHierarchyContinuationNodes"][0]["allOutgoingDirectedEdges"][1]["forwardAccess"]=1
        root["nativeAllHierarchyContinuationNodes"][0]["allOutgoingDirectedEdges"][2]["forwardAccess"]=1
        self.assertEqual(validate_mode(self.a,root,self.geometry,"auto")["status"],INTERMEDIATE)
        self.assertEqual(validate_mode(self.a,root,self.geometry,"motorcycle")["status"],FINAL)

    def test_no_forward_branch_proves_native_local_terminal(self):
        root=copy.deepcopy(self.root)
        root["nativeAllHierarchyContinuationNodes"][0]["allOutgoingDirectedEdges"]=root[
            "nativeAllHierarchyContinuationNodes"][0]["allOutgoingDirectedEdges"][:1]
        self.assertEqual(validate_mode(self.a,root,{},"auto")["status"],FINAL)

    def test_invalid_missing_native_neighbor_fails_not_silently_accepts(self):
        with self.assertRaises(KeyError):
            validate_mode(self.a,self.root,{202:self.forward},"auto")

    def test_invalid_opposing_id_fails(self):
        broken=copy.deepcopy(self.root)
        broken["opposingGraphId"]=0
        with self.assertRaises(ValueError):
            validate_mode(self.a,broken,self.geometry,"auto")

    def test_both_mode_intermediate_never_exports_an_A_final_connection(self):
        inputdoc={
            "connections":[{"sourceRegionId":"italy-nord-est",
              "receiverRegionId":"austria","sourceFinalDirectedGraphId":101,
              "sourceFinalCoordinate":{"lat":47.233864,"lng":11.392306},
              "sourceValhallaProvedModes":["auto","motorcycle"],
              "receiverOptions":[{"receiverFirstDirectedGraphId":909,
                  "travelModes":["auto","motorcycle"]}],
              "unverifiedReceiverCandidateGraphIds":[]}],
            "unresolvedSourceFinalEdges":[],
            "sourceDiscoveryComplete":False,"productionPublication":"BLOCKED"
        }
        results=gate_catalog(inputdoc,{("italy-nord-est",101):self.root},
                             {("italy-nord-est",101):self.a},
                             {"italy-nord-est":self.geometry})
        self.assertEqual(results["connections"],[])
        self.assertEqual(len(results["unresolvedSourceFinalEdges"]),1)
        self.assertEqual(results["unresolvedSourceFinalEdges"][0]["status"],
                         "ORIGINAL_SOURCE_NOT_PROVED_FINAL")
        self.assertEqual(results["unresolvedSourceFinalEdges"][0][
            "deferredPreTerminalReceiverOptions"][0]["receiverFirstDirectedGraphId"],909)
        self.assertFalse(results["sourceDiscoveryComplete"])
        self.assertEqual(results["productionPublication"],"BLOCKED")

    def test_independent_branch_and_mode_preserved_after_final_gate(self):
        r=copy.deepcopy(self.root)
        for x in r["nativeAllHierarchyContinuationNodes"][0]["allOutgoingDirectedEdges"]:
            if x["graphId"] in (202,303):x["forwardAccess"]=1
        document={
          "connections":[{"sourceRegionId":"italy-nord-est",
             "receiverRegionId":"austria","sourceFinalDirectedGraphId":101,
             "sourceFinalCoordinate":{"lat":47.233864,"lng":11.392306},
             "sourceValhallaProvedModes":["auto","motorcycle"],
             "receiverOptions":[{"receiverFirstDirectedGraphId":909,
                "travelModes":["auto","motorcycle"]},{"receiverFirstDirectedGraphId":919,
                "travelModes":["motorcycle"]}],
             "unverifiedReceiverCandidateGraphIds":[]}],
          "unresolvedSourceFinalEdges":[],
          "sourceDiscoveryComplete":False,"productionPublication":"BLOCKED"}
        result=gate_catalog(document,{("italy-nord-est",101):r},
                   {("italy-nord-est",101):self.a},
                   {"italy-nord-est":self.geometry})
        self.assertEqual(len(result["connections"]),1)
        a=result["connections"][0]
        self.assertEqual(a["sourceValhallaProvedModes"],["motorcycle"])
        self.assertEqual({x["receiverFirstDirectedGraphId"] for x in a["receiverOptions"]},
                         {909,919})
        self.assertEqual([x["travelModes"] for x in a["receiverOptions"]],
                         [["motorcycle"],["motorcycle"]])
        self.assertEqual(result["additionalSourceFinalGateCounts"]["nativeVerifiedReceivingOptions"],2)
