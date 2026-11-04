"""Final graph-local road-edge evidence from ORIGINAL Valhalla native route IDs."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from probe_native_f8_clipped_terminal import SourceIntegrityError
from test_native_f8_clipped_terminal import (
    END, adjacency, buffers, edge, out, MASK
)
from verify_native_f8_original_road_terminal import certify_one


def routed(source:dict,mode:str,last_id:int|None=None,delta:float=0.0):
    start={"lat":source["directedGeometry"][0][0],
           "lng":source["directedGeometry"][0][1]}
    def fn(origin,end,travel_mode):
        assert travel_mode==mode
        return {
            "status":"SUCCEEDED",
            "originalRouteEdgeIdentity":"ORIGINAL_VALHALLA_ROUTE_PROTOBUF",
            "firstDirectedGraphId":source["sourceGraphId"],
            "lastDirectedGraphId": (
                source["sourceGraphId"] if last_id is None else last_id),
            "startOffsetMeters":0.0,
            "endOffsetMeters":0.0,
            "startActual":start,
            "endActual":{"lat":end["lat"]+delta,"lng":end["lng"]},
            "durationSeconds":8.0,"distanceKm":0.1,
        }
    return fn


class OriginalTerminalTests(unittest.TestCase):
    def test_true_original_last_edge_and_native_graph_terminal_proven_per_direction(self):
        own,peer=buffers()
        s=edge()
        for mode in ("auto","motorcycle"):
            got=certify_one(s,adjacency(source=s),mode,own,peer,routed(s,mode))
            self.assertEqual(got["perEdgeStatus"],
                "NATIVE_GRAPH_LOCAL_FINAL_DIRECTED_EDGE_WITH_ORIGINAL_ROUTE_PROVEN")
            self.assertTrue(got["originalRouteUsesThisFinalDirectedEdge"])
            self.assertTrue(got["originalRouteStartAndTerminalSnapsWithinOneMetre"])
            self.assertTrue(got["sourceNativeTerminal"]["graphLocalModeTerminalConfirmed"])
            self.assertEqual(got["sourceNativeTerminal"]["modeUsableNonreverseOutgoingGraphIds"],[])
            self.assertEqual(got["physicalRoadUniqueFinalEdgeAcrossGraph"],"NOT_VERIFIED")
            self.assertEqual(got["discoveryCandidateExclusion"],"NONE")
            self.assertEqual(got["originalAndroidJNIParity"],"NOT_VERIFIED")
            self.assertEqual(got["productionPublication"],"BLOCKED")

    def test_polygon_own_buffer_mismatch_cannot_reject_original_native_terminal(self):
        own,peer=buffers()
        s=edge()
        x=own["polygon"].bounds[2]
        own={**own,"polygon":own["polygon"].buffer(-200)}
        result=certify_one(s,adjacency(source=s),"auto",own,peer,routed(s,"auto"))
        self.assertFalse(result["sourceNativeTerminal"]["sourceEndInsideOwnRetainedBuffer"])
        self.assertTrue(result["sourceNativeTerminal"]["sourceEndInsidePeerRetainedBuffer"])
        self.assertIn("PROVEN",result["perEdgeStatus"])

    def test_original_route_not_reaching_exact_nominated_native_edge_is_not_certified(self):
        own,peer=buffers()
        s=edge()
        report=certify_one(s,adjacency(source=s),"auto",own,peer,
                           routed(s,"auto",last_id=s["sourceGraphId"]+99))
        self.assertFalse(report["originalRouteUsesThisFinalDirectedEdge"])
        self.assertEqual(report["perEdgeStatus"],
                         "NOT_VERIFIED_AS_THIS_NATIVE_GRAPH_LOCAL_TERMINAL")
        self.assertEqual(report["discoveryCandidateExclusion"],"NONE")

    def test_mode_forward_shortcut_and_nonroad_block_this_terminal_certificate_only(self):
        own,peer=buffers()
        s=edge()
        for branch in (out(888,road=False),out(888,road=True,shortcut=True)):
            result=certify_one(s,adjacency([out(777),branch],source=s),
                               "auto",own,peer,routed(s,"auto"))
            self.assertEqual(result["perEdgeStatus"],
                             "NOT_VERIFIED_AS_THIS_NATIVE_GRAPH_LOCAL_TERMINAL")
            self.assertTrue(result["sourceNativeTerminal"][
                "modeUsableNonreverseOutgoingGraphIds"])
            self.assertEqual(result["discoveryCandidateExclusion"],"NONE")

    def test_undocumented_full_physical_road_dedup_is_not_done_by_way_id(self):
        own,peer=buffers()
        edge1=edge(gid=100)
        edge2=edge(gid=200)
        edge2["wayId"]=edge1["wayId"]
        ids=[]
        for e in (edge1,edge2):
            r=certify_one(e,adjacency(source=e),"auto",own,peer,routed(e,"auto"))
            self.assertEqual(r["perEdgeStatus"],
                "NATIVE_GRAPH_LOCAL_FINAL_DIRECTED_EDGE_WITH_ORIGINAL_ROUTE_PROVEN")
            ids.append(r["sourceGraphId"])
        self.assertEqual(ids,[100,200])
        self.assertEqual(len(set(ids)),2)

    def test_route_snap_away_fails_terminal_certificate_without_global_rejection(self):
        own,peer=buffers()
        s=edge()
        report=certify_one(s,adjacency(source=s),"auto",own,peer,
                           routed(s,"auto",delta=0.002))
        self.assertFalse(report["originalRouteStartAndTerminalSnapsWithinOneMetre"])
        self.assertEqual(report["perEdgeStatus"],
                         "NOT_VERIFIED_AS_THIS_NATIVE_GRAPH_LOCAL_TERMINAL")

    def test_truncated_native_outgoing_degree_is_fatal_not_proven(self):
        own,peer=buffers()
        s=edge()
        invalid=adjacency(source=s)
        invalid["nativeOutgoingDegree"]=3
        with self.assertRaises(SourceIntegrityError):
            certify_one(s,invalid,"auto",own,peer,routed(s,"auto"))

    def test_peer_buffer_not_containing_terminal_keeps_unknown(self):
        own,peer=buffers()
        s=edge()
        peer={**peer,"polygon":peer["polygon"].buffer(-300)}
        r=certify_one(s,adjacency(source=s),"auto",own,peer,routed(s,"auto"))
        self.assertEqual(r["perEdgeStatus"],
                         "NOT_VERIFIED_AS_THIS_NATIVE_GRAPH_LOCAL_TERMINAL")
        self.assertEqual(r["discoveryCandidateExclusion"],"NONE")


if __name__=="__main__":
    unittest.main()
