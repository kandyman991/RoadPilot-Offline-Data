"""Original source-only beyond-cut road-edge predecessor and TripLeg gates."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from shapely.geometry import box

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from probe_native_f8_clipped_terminal import CRS
from prove_native_f8_final_edge_beyond_cut import (
    enumerate_original_cut_predecessor_paths, prove_original_cut_predecessor_routes,
    SCHEMA,
)
from prove_native_f8_source_cut_last_tripleg import STATUS_PROVEN


def own_buffer():
    x,y=CRS.transform(11.,47.)
    return {"polygon":box(x-20,y-50,x+20,y+50)}


def candidate():
    return {
        "finalDirectedGraphId":300, "nativeEndNodeGraphId":999,
        "wayIdAnnotationOnly":100,
        "nativeTerminal":{"lat":47.,"lng":11.002},
        "vehicleModes":["auto","motorcycle"],
    }


NATIVE_ROWS={
    (300,"--continuations"):{
        "sourceGraphId":300,"endNodeGraphId":999,"wayId":100,"opposingGraphId":200},
    (200,"--continuations"):{
        "sourceGraphId":200,"endNodeGraphId":700,
        "outgoingDirectedEdges":[{"graphId":500},{"graphId":501},{"graphId":300}]},
    (500,"--continuations"):{
        "sourceGraphId":500,"opposingGraphId":510},
    (501,"--continuations"):{
        "sourceGraphId":501,"opposingGraphId":511},
    (510,"--geometry"):{
        "sourceGraphId":510,"endNodeGraphId":700,"wayId":101,
        "forwardAccess":1025,"endLat":47.,"endLon":11.001,
        "directedGeometry":[[47.,10.999],[47.,11.001]]},
    (511,"--geometry"):{
        "sourceGraphId":511,"endNodeGraphId":700,"wayId":102,
        "forwardAccess":1025,"endLat":47.,"endLon":11.001,
        "directedGeometry":[[47.,11.0006],[47.,11.001]]},
    (511,"--continuations"):{
        "sourceGraphId":511,"endNodeGraphId":700,"opposingGraphId":600},
    (600,"--continuations"):{
        "sourceGraphId":600,"endNodeGraphId":800,
        "outgoingDirectedEdges":[{"graphId":601},{"graphId":511}]},
    (601,"--continuations"):{
        "sourceGraphId":601,"opposingGraphId":610},
    (610,"--geometry"):{
        "sourceGraphId":610,"endNodeGraphId":800,"wayId":103,
        "forwardAccess":1025,"endLat":47.,"endLon":11.0006,
        "directedGeometry":[[47.,10.999],[47.,11.0006]]},
}


def native_rows(_binary,_config,ids,option,_work):
    try:
        return [NATIVE_ROWS[(id,option)] for id in ids]
    except KeyError as exc:
        raise AssertionError("Unexpected native GraphReader query "+str(exc))


class SourceBeyondCutTests(unittest.TestCase):
    def test_all_original_source_branches_one_and_two_hops_preserved(self):
        with patch("prove_native_f8_final_edge_beyond_cut.native_original_rows",
                   side_effect=native_rows):
            result=enumerate_original_cut_predecessor_paths(
                Path("native"),Path("original-config"),candidate(),
                own_buffer(),Path("/tmp"))
        self.assertTrue(result["anyOriginalCutCrossingPredecessorLocated"])
        paths=result["originalDirectedCutCrossingPredecessorPaths"]
        self.assertEqual(
            [p["nativeForwardDirectedPathToFinal"] for p in paths],
            [[510,300],[610,511,300]])
        self.assertEqual(result["nativeSourceSameLevelPredecessorEdgesVisited"],3)
        self.assertEqual(result["globalNativePhysicalRoadDirectionEquivalence"],"NOT_VERIFIED")
        self.assertTrue(result["noOriginalBranchesSuppressed"])

    def test_bound_exhaustion_is_explicit_not_misreported_complete(self):
        with patch("prove_native_f8_final_edge_beyond_cut.native_original_rows",
                   side_effect=native_rows):
            res=enumerate_original_cut_predecessor_paths(
                Path("native"),Path("cfg"),candidate(),
                own_buffer(),Path("/tmp"),depth_limit=1)
        self.assertTrue(res["anyOriginalCutCrossingPredecessorLocated"])
        self.assertEqual(res["completeness"],"INCOMPLETE_BOUNDED")
        self.assertTrue(res["truncations"])

    def test_cut_predecessor_original_route_must_match_entire_native_chain(self):
        p={"originalDirectedGraphId":510,
           "nativeForwardDirectedPathToFinal":[510,300]}
        branches={"originalDirectedCutCrossingPredecessorPaths":[p]}
        route={"status":"SUCCEEDED",
            "originalRouteEdgeIdentity":"ORIGINAL_VALHALLA_ROUTE_PROTOBUF",
            "edgeIdOrigin":"ORIGINAL_TRIPLEG_NODE_EDGE_PROTOBUF",
            "lastDirectedGraphId":300,
            "firstDirectedGraphId":510,
            "originalNativeDirectedGraphIds":[510,300],
            "startOffsetMeters":0.1,"endOffsetMeters":0.1,
            "endActual":{"lat":47.,"lng":11.002}}
        with patch("prove_native_f8_final_edge_beyond_cut.native_original_rows",
                   side_effect=native_rows),patch(
            "prove_native_f8_final_edge_beyond_cut.route_with_original_ids",
                   return_value=route) as probe:
            result=prove_original_cut_predecessor_routes(
                candidate(),branches,Path("native"),Path("route"),Path("cfg"),Path("/tmp"))
            probe.assert_called()
        self.assertEqual(result["routeModeCounts"][STATUS_PROVEN],2)
        self.assertTrue(result["originalSourceCutRouteProofs"][0][
            "originalRouteModeProofs"]["auto"]["originalSourceCutPathExactTripLegSequence"])
        self.assertEqual(result["physicalRoadEquivalence"],"NOT_VERIFIED")

    def test_missing_middle_native_edge_never_proves_route_path(self):
        p={"originalDirectedGraphId":510,
           "nativeForwardDirectedPathToFinal":[510,300]}
        branches={"originalDirectedCutCrossingPredecessorPaths":[p]}
        route={"status":"SUCCEEDED",
            "originalRouteEdgeIdentity":"ORIGINAL_VALHALLA_ROUTE_PROTOBUF",
            "edgeIdOrigin":"ORIGINAL_TRIPLEG_NODE_EDGE_PROTOBUF",
            "lastDirectedGraphId":300,
            "firstDirectedGraphId":510,
            "originalNativeDirectedGraphIds":[510,999,300],
            "startOffsetMeters":0.1,"endOffsetMeters":0.1,
            "endActual":{"lat":47.,"lng":11.002}}
        # This produces a first-and-last match but a different path; fail
        # closed unless exactly the original predecessor suffix is present.
        with patch("prove_native_f8_final_edge_beyond_cut.native_original_rows",
                   side_effect=native_rows),patch(
            "prove_native_f8_final_edge_beyond_cut.route_with_original_ids",
                   return_value=route):
            result=prove_original_cut_predecessor_routes(
                candidate(),branches,Path("native"),Path("route"),Path("cfg"),Path("/tmp"))
        self.assertEqual(result["routeModeCounts"]["NOT_VERIFIED"],2)

    def test_same_level_root_missing_final_edge_is_corrupt(self):
        corrupted=dict(NATIVE_ROWS)
        corrupted[(200,"--continuations")]={
            **NATIVE_ROWS[(200,"--continuations")],
            "outgoingDirectedEdges":[{"graphId":500},{"graphId":501}]}
        def fake(_b,_cfg,ids,option,_w):
            return [corrupted[(gid,option)] for gid in ids]
        with patch("prove_native_f8_final_edge_beyond_cut.native_original_rows",
                   side_effect=fake),self.assertRaisesRegex(ValueError,"missing"):
            enumerate_original_cut_predecessor_paths(
                Path("native"),Path("cfg"),candidate(),own_buffer(),Path("/tmp"))

    def test_input_invalid_is_rejected(self):
        with self.assertRaises(ValueError):
            enumerate_original_cut_predecessor_paths(
                Path("native"),Path("cfg"),{**candidate(),"finalDirectedGraphId":0},
                own_buffer(),Path("/tmp"))


if __name__=="__main__":
    unittest.main()
