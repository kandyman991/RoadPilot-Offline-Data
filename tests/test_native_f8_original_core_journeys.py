"""F8 original core-to-core route and all-native-branch topology proof gates."""
from __future__ import annotations

import copy
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

from shapely.geometry import box
from shapely.prepared import prep

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from probe_native_f8_clipped_terminal import _at
from prove_native_f8_original_core_journeys import (
    CASES_SCHEMA, _geometry, check_native_original_route_topology,
    parse_cases, prove_case, route_terminal,
)


def graph_row(gid, mask=1025, *, incoming_direct=None, incoming_via_transition=None):
    expected = gid + 9000
    outgoing = [{
        "graphId": expected, "forwardAccess": 0, "isRoad": True,
        "isShortcut": False, "endNodeGraphId": gid + 19900}]
    if incoming_direct is not None:
        outgoing.append({
            "graphId": incoming_direct, "forwardAccess": mask,
            "isRoad": True, "isShortcut": False,
            "endNodeGraphId": incoming_direct + 19900})
    # Two distinct active branches plus shortcut and opposing reverse are never dropped.
    outgoing += [
        {"graphId": gid+4000, "forwardAccess": mask,
         "isRoad": True, "isShortcut": False, "endNodeGraphId": gid+3000},
        {"graphId": gid+5000, "forwardAccess": mask,
         "isRoad": True, "isShortcut": True, "endNodeGraphId": gid+3001},
        {"graphId": gid+6000, "forwardAccess": 0,
         "isRoad": False, "isShortcut": False, "endNodeGraphId": gid+3002},
    ]
    node = {"nodeGraphId":gid+10000, "transitionDepth":0,
            "nodeLat":47.0, "nodeLon":11.0,
            "allOutgoingDirectedEdges":outgoing,
            "nativeHierarchyTransitions":[]}
    nodes = [node]
    if incoming_via_transition is not None:
        peer = gid+10001
        node["nativeHierarchyTransitions"] = [{"nodeGraphId":peer, "up":True}]
        nodes.append({
            "nodeGraphId":peer, "transitionDepth":1,
            "nodeLat":47.0, "nodeLon":11.0,
            "allOutgoingDirectedEdges":[{
                "graphId":incoming_via_transition, "forwardAccess":mask,
                "isRoad":True, "isShortcut":False,
                "endNodeGraphId":incoming_via_transition+19900}],
            "nativeHierarchyTransitions":[{"nodeGraphId":gid+10000, "up":False}],
        })
    return {
        "sourceGraphId":gid, "forwardAccess":mask, "wayId":33,
        "endNodeGraphId":gid+10000, "opposingGraphId":expected,
        "outgoingDirectedEdges":outgoing, "nativeAllHierarchyContinuationNodes":nodes,
    }


def case_payload(source=101, direction="from-to", mode="auto"):
    return {
        "direction":direction, "mode":mode,
        "sourceFinalDirectedGraphId":source,
        "originSourceCore":{"lat":47.0,"lng":11.0},
        "destinationReceiverCore":{"lat":47.03,"lng":11.0},
    }


def mock_edge(gid, reverse=False):
    shape = [[47.019,11.0],[47.02,11.0]]
    if reverse:
        shape.reverse()
    return {"sourceGraphId":gid, "wayId":88, "forwardAccess":1025,
            "endNodeGraphId":gid+5000,
            "endLat":shape[-1][0], "endLon":shape[-1][1],
            "directedGeometry":shape}


class OriginalF8CoreTopologyTests(unittest.TestCase):
    def test_complete_native_direct_and_hierarchy_hops_with_all_road_branches(self):
        path = [101,102,103]
        rows = [graph_row(101,incoming_direct=102),
                graph_row(102,incoming_via_transition=103),graph_row(103)]
        proof = check_native_original_route_topology(path,rows,"auto")
        self.assertTrue(proof["originalRouteEveryHopSupportedByNativeDirectedTopology"])
        self.assertEqual(proof["counts"]["originalRouteDirectNativeHops"],1)
        self.assertEqual(proof["counts"]["originalRouteHierarchyTransitionHops"],1)
        self.assertEqual(proof["originalDirectedGraphIdCount"],3)
        self.assertEqual(proof["branchCompletenessWithinVisitedNodes"],
                         "ALL_NATIVE_OUTGOING_HIERARCHY_LEVELS_EXPOSED")
        options = proof["allNativeBranchInventories"][0]["allNativeHierarchyAndModeBranchOptions"]
        self.assertTrue(any(x["isShortcut"] for x in options))
        self.assertTrue(any(x["isImmediateOpposingReverse"] for x in options))
        self.assertTrue(any(not x["isRoad"] for x in options))
        self.assertGreaterEqual(proof["counts"]["intersectionsWithMultipleNativeModeAccessibleChoices"],2)
        self.assertEqual(proof["fullPhysicalRoadDirectionLineage"],"NOT_VERIFIED_GLOBALLY")

    def test_wrong_graphid_missing_mode_bit_or_unproven_adjacency_never_pass(self):
        ids=[101,102]
        proof=check_native_original_route_topology(ids,[graph_row(101),graph_row(102)],"auto")
        self.assertFalse(proof["originalRouteEveryHopSupportedByNativeDirectedTopology"])
        self.assertEqual(proof["counts"]["originalNextDirectedEdgesUnresolvedInNativeAdjacency"],1)
        no_mask=graph_row(101,mask=1024,incoming_direct=102)
        proof=check_native_original_route_topology(ids,[no_mask,graph_row(102)],"auto")
        self.assertFalse(proof["originalRouteEveryHopSupportedByNativeDirectedTopology"])
        self.assertGreaterEqual(proof["counts"]["originalRouteEdgesWithDifferentModeAccessMask"],1)
        with self.assertRaisesRegex(ValueError,"rows differ"):
            check_native_original_route_topology(ids,[graph_row(101),graph_row(104)],"auto")

    def test_dropped_hierarchy_arc_and_duplicate_branch_ids_fail_closed(self):
        rows=[graph_row(101,incoming_via_transition=102),graph_row(102)]
        rows[0]["nativeAllHierarchyContinuationNodes"][0]["nativeHierarchyTransitions"][0]["nodeGraphId"]=99999
        with self.assertRaisesRegex(ValueError,"transition not represented"):
            check_native_original_route_topology([101,102],rows,"auto")
        rows=[graph_row(101,incoming_direct=102),graph_row(102)]
        e=rows[0]["nativeAllHierarchyContinuationNodes"][0]["allOutgoingDirectedEdges"]
        e.append(copy.copy(e[0]))
        with self.assertRaisesRegex(ValueError,"per-hierarchy branch"):
            check_native_original_route_topology([101,102],rows,"auto")
        rows=[graph_row(101,incoming_via_transition=102),graph_row(102)]
        rows[0]["nativeAllHierarchyContinuationNodes"][1]["nodeLat"] = 47.0001
        with self.assertRaisesRegex(ValueError,"changes physical node"):
            check_native_original_route_topology([101,102],rows,"auto")

    def test_hierarchy_successor_must_be_reachable_from_actual_original_end_node(self):
        rows=[graph_row(101,incoming_via_transition=102),graph_row(102)]
        proven=check_native_original_route_topology([101,102],rows,"auto")
        self.assertEqual(
            proven["originalRouteDirectedHops"][0]["originalNativeTransitionNodePath"],
            [101+10000,101+10001])
        # Removing the root->peer arc must fail even though the original
        # successor is still present inside a native outgoing inventory.
        bad=copy.deepcopy(rows)
        bad[0]["nativeAllHierarchyContinuationNodes"][0][
            "nativeHierarchyTransitions"]=[]
        with self.assertRaisesRegex(ValueError,"Disconnected native hierarchy"):
            check_native_original_route_topology([101,102],bad,"auto")
        bad=copy.deepcopy(rows)
        bad[0]["nativeAllHierarchyContinuationNodes"][1]["transitionDepth"]=0
        with self.assertRaisesRegex(ValueError,"depth does not match"):
            check_native_original_route_topology([101,102],bad,"auto")

    def test_root_outgoing_identity_access_and_endpoint_must_agree(self):
        for key, value in (("forwardAccess",7),("endNodeGraphId", 999999),
                           ("isShortcut",True)):
            with self.subTest(key=key):
                rows=[graph_row(101,incoming_direct=102),graph_row(102)]
                bad=copy.deepcopy(rows)
                # In synthetic fixtures, both native views intentionally
                # alias one list; detach so only one view is corrupted.
                bad[0]["outgoingDirectedEdges"] = copy.deepcopy(
                    bad[0]["outgoingDirectedEdges"])
                bad[0]["outgoingDirectedEdges"][-1][key]=value
                with self.assertRaisesRegex(ValueError,"edge attributes disagree"):
                    check_native_original_route_topology([101,102],bad,"auto")

    def test_tampered_source_native_terminal_or_missing_directed_edge_fails(self):
        record={"schema":"roadpilot.f8-original-terminal-lineage-ledger",
                "version":1,"productionPublication":"BLOCKED",
                "oneFinalEdgePerPhysicalRoadAndDirection":"NOT_VERIFIED",
                "directions":{"from-to":{"auto":{
                    "sourceCoverage":"ALL_NATIVE_CENSUS_TERMINALS_RETAINED",
                    "allTerminals":[{
                        "sourceGraphId":101,"candidateSuppressed":False,
                        "nativeGraphLocalTerminal":"PROVEN_BY_FULL_TOPOLOGY_CENSUS",
                        "physicalRoadLineage":
                            "PHYSICAL_ROAD_DIRECTION_LINEAGE_NOT_ESTABLISHED",
                        "insideVerifiedPeerBuffer":True}]}}}}
        self.assertEqual(route_terminal(record,"from-to","auto",101)["sourceGraphId"],101)
        # Geometry outside the separately saved buffer is not a source
        # candidate disqualifier; use original Valhalla routing as authority.
        record["directions"]["from-to"]["auto"]["allTerminals"][0][
            "insideVerifiedPeerBuffer"] = False
        self.assertEqual(route_terminal(record,"from-to","auto",101)["sourceGraphId"],101)
        with self.assertRaisesRegex(ValueError,"absent"):
            route_terminal(record,"from-to","auto",404)
        record["directions"]["from-to"]["auto"]["allTerminals"][0]["candidateSuppressed"]=True
        with self.assertRaisesRegex(ValueError,"suppressed"):
            route_terminal(record,"from-to","auto",101)

    def test_input_cases_reject_duplicate_ambiguous_invalid_and_unbounded(self):
        good={"schema":CASES_SCHEMA,"version":1,"cases":[case_payload()]}
        self.assertEqual(len(parse_cases(good)),1)
        for bad in (
            {**good,"cases":[case_payload(),case_payload()]},
            {**good,"cases":[{**case_payload(),"sourceFinalDirectedGraphId":True}]},
            {**good,"cases":[{**case_payload(),"mode":"truck"}]},
            {**good,"cases":[{**case_payload(),"originSourceCore":{"lat":float("nan"),"lng":0}}]},
            {**good,"cases":[case_payload(i+1) for i in range(33)]},
            {**good,"cases":[{**case_payload(),"legacyOSMWayId":8}]},
        ):
            with self.subTest(bad=str(bad)[:50]),self.assertRaises(ValueError):
                parse_cases(bad)

    def test_aligned_native_geometry_is_local_evidence_only_opposing_not_promoted(self):
        a=mock_edge(101)
        aligned=mock_edge(201)
        opposite=mock_edge(202,reverse=True)
        first=_geometry(a,aligned,"auto")
        second=_geometry(a,opposite,"motorcycle")
        self.assertTrue(first["directedLocalTangentAlignedAtHandoff"])
        self.assertFalse(second["directedLocalTangentAlignedAtHandoff"])
        self.assertEqual(first["samePhysicalRoadContinuity"],"NOT_VERIFIED_GLOBALLY")

    def test_original_two_legs_need_exact_a_last_and_actual_b_first(self):
        coreA=_at({"lat":47.0,"lng":11.0})
        coreB=_at({"lat":47.03,"lng":11.0})
        own=prep(box(coreA.x-1000,coreA.y-1000,coreA.x+1000,coreA.y+1000))
        peer=prep(box(coreB.x-1000,coreB.y-1000,coreB.x+1000,coreB.y+1000))
        x={"lat":47.02,"lng":11.0}
        source_row={"terminalEndpoint":x, "insideVerifiedPeerBuffer":True}
        first={"status":"SUCCEEDED",
               "originalRouteEdgeIdentity":"ORIGINAL_VALHALLA_ROUTE_PROTOBUF",
               "startActual":{"lat":47.0,"lng":11.0},
               "endActual":x,
               "startOffsetMeters":0.0,"endOffsetMeters":0.0,
               "firstDirectedGraphId":199,"lastDirectedGraphId":101,
               "originalNativeDirectedGraphIds":[199,101],
               "durationSeconds":200.0,"distanceKm":2.2}
        second={"status":"SUCCEEDED",
                "startActual":x,"endActual":{"lat":47.03,"lng":11.0},
                "startOffsetMeters":0.0,"endOffsetMeters":0.0,
                "firstDirectedGraphId":201,"lastDirectedGraphId":299,
                "originalNativeDirectedGraphIds":[201,299],
                "durationSeconds":100.0,"distanceKm":1.1}
        case=case_payload()
        with (patch("prove_native_f8_original_core_journeys.route_with_original_ids",
                    side_effect=[first,second]),
              patch("prove_native_f8_original_core_journeys.capture_native_lineage",
                    side_effect=[([], "sha256:a"),([], "sha256:b")]),
              patch("prove_native_f8_original_core_journeys.check_native_original_route_topology",
                    return_value={"originalRouteEveryHopSupportedByNativeDirectedTopology":True}),
              patch("prove_native_f8_original_core_journeys.native_rows",
                    side_effect=[[mock_edge(101)],[mock_edge(201)]])):
            proof=prove_case(case,source_row,Path("/safe-native"),Path("/safe-route"),
                             (Path("A"),Path("B")),own,peer,Path("/tmp"))
        self.assertEqual(proof["status"],
                         "TWO_ORIGINAL_GRAPH_LOCAL_LEGS_AND_DIRECTED_SEAM_GEOMETRY_ALIGNED_ONLY")
        self.assertEqual(proof["originalReceivingFirstGraphId"],201)
        self.assertEqual(proof["originalTotalDistanceKm"],3.3)
        self.assertEqual(proof["crossGraphTurnLegality"],"NOT_VERIFIED")
        self.assertTrue(proof["arrivalAndHandoffSnapsWithinTolerance"])
        bad=copy.deepcopy(first)
        bad["lastDirectedGraphId"]=102
        with (patch("prove_native_f8_original_core_journeys.route_with_original_ids",
                    return_value=bad) as routed,
              patch("prove_native_f8_original_core_journeys.capture_native_lineage") as native):
            failing=prove_case(case,source_row,Path("/native"),Path("/route"),
                               (Path("A"),Path("B")),own,peer,Path("/tmp"))
        self.assertEqual(failing["status"],
                         "A_ORIGINAL_SOURCE_CORE_TO_FINAL_GRAPHID_NOT_PROVEN")
        native.assert_not_called()
        routed.assert_called_once()


if __name__=="__main__":
    unittest.main()
