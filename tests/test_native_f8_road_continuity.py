"""M6c Phase B: selected native A terminal → B incoming → B outgoing witness."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "devtools"))
from probe_native_f8_clipped_terminal import SourceIntegrityError
from probe_native_f8_road_continuity import (
    inspect_source_and_b_continuations,
    inspect_one_source_with_recoverable_b_reads, locate_set,
)

MASK = 1257
A_END = {"lat": 46.5, "lng": 13.5}


def edge(gid: int, coords: list[list[float]], *,
         access: int = MASK, way: int = 1000) -> dict:
    return {
        "sourceGraphId": gid,
        "endNodeGraphId": gid + 1000,
        "wayId": way, "forwardAccess": access,
        "endLat": coords[-1][0], "endLon": coords[-1][1],
        "directedGeometry": coords, "deadend": gid == 10,
    }


def entries(ids=(21, 22)):
    return [
        {"graphId": gid, "endNodeGraphId": gid + 1000,
         "forwardAccess": MASK if gid == 21 else 0,
         "isRoad": True, "isShortcut": False,
         "autoBit": gid == 21, "motorcycleBit": gid == 21}
        for gid in ids
    ]


def source_and_b():
    a = edge(10, [[46.4996, 13.4996], [46.5, 13.5]])
    incoming = edge(20, [[46.4995, 13.4995], [46.5, 13.5]])
    advance = edge(21, [[46.5, 13.5], [46.5005, 13.5005]], way=2000)
    reverse = edge(
        22, [[46.5, 13.5], [46.4995, 13.4995]], access=0)
    return a, incoming, advance, reverse


def locator(gid):
    return {
        "receiverGraphId": gid, "locateDistanceMeters": 0.0,
        "locateNativeDeadend": False, "locateForward": True,
    }


def adjacency(row, *, out=None):
    out = entries() if out is None else out
    return {
        "sourceGraphId": row["sourceGraphId"],
        "endNodeGraphId": row["endNodeGraphId"],
        "wayId": row["wayId"],
        "forwardAccess": row["forwardAccess"],
        "nativeOutgoingDegree": len(out),
        "opposingGraphId": 22,
        "outgoingDirectedEdges": out,
    }


def good_route(cfg, start, end, mode):
    return {
        "status": "SUCCEEDED",
        "startActual": start, "endActual": end,
        "startOffsetMeters": 0.0, "endOffsetMeters": 0.0,
        "encodedShape": "opaque-graph-local-b-route",
        "durationSeconds": 6.5, "distanceKm": 0.1,
    }


def good_trace(cfg, encoded, mode):
    return [20, 21]


def check(*, budget=16, get_adj=None, get_rows=None,
          locators=None, native_b=None, trace_fn=good_trace):
    a, incoming, advance, reverse = source_and_b()
    if locators is None: locators = [locator(21), locator(20)]
    if native_b is None: native_b = [advance, incoming]
    if get_adj is None: get_adj = lambda gid: adjacency(incoming)
    if get_rows is None: get_rows = lambda ids: [
        {21:advance, 22:reverse}[gid] for gid in ids]
    return inspect_source_and_b_continuations(
        a,
        {"sourceGraphId":10, "sourceDirectedEndpoint":A_END,
         "graphLocalModeTerminalConfirmed":True},
        locators, native_b, "auto", Path("B"), get_adj, get_rows,
        max_route_probes=budget, route_fn=good_route, trace_fn=trace_fn)


class ContinuityTests(unittest.TestCase):
    def test_one_true_b_incoming_contains_a_tail_and_opposing_direction_kept(self):
        found = check()
        self.assertEqual(found["sourceGraphId"], 10)
        self.assertEqual(found["retainedReceiverIdentities"], [21, 20])
        self.assertEqual(found["locatedReceiverCount"], 2)
        self.assertEqual(found["nominatedBIncomingCount"], 1)
        self.assertEqual(found["verifiedNativeBOutgoingBranchCount"], 2)
        self.assertEqual(found["bOnlyRouteProbeCount"], 2)
        out, incoming = found["allBLocatedEdges"]
        self.assertFalse(out["selectedBIncomingForNativeTurnDiagnostic"])
        self.assertEqual(
            out["incomingToOutgoingEvidence"]["status"],
            "NOT_PROBED_UNSELECTED_B_INCOMING_GEOMETRY")
        self.assertTrue(incoming["selectedBIncomingForNativeTurnDiagnostic"])
        self.assertEqual(
            incoming["bIncomingTailObservation"]["state"],
            "SAMPLED_DIRECTED_ORDER_ALIGNED_ONLY")
        self.assertTrue(incoming[
            "nativeSourceWayIdEqualsBIncomingWayIdAnnotation"])
        self.assertLess(incoming["aTerminalToBIncomingEndMeters"], 1)
        self.assertEqual(incoming["incomingToOutgoingEvidence"][
            "graphBPhysicalNodeAdjacency"], "CONFIRMED_FOR_THIS_NODE_ONLY")
        self.assertEqual(found["crossGraphDirectedTurnLegality"], "NOT_VERIFIED")
        self.assertEqual(found["sourcePhysicalFinalRoadEdge"], "NOT_VERIFIED")
        self.assertEqual(found["sourceDiscoveryCoverage"], "NOT_VERIFIED")
        self.assertEqual(found["productionPublication"], "BLOCKED")

    def test_complete_b_branches_include_mode_inaccessible_reverse(self):
        record = check()["allBLocatedEdges"][1]["incomingToOutgoingEvidence"]
        branches = record["allNativeOutgoingAlternatives"]
        self.assertEqual([b["bOutgoingGraphId"] for b in branches], [21,22])
        self.assertEqual([b["bNativeOpposingReverse"] for b in branches],
                         [False, True])
        self.assertEqual([b["modeForwardAccess"] for b in branches],
                         [True, False])
        self.assertEqual(branches[0]["bOnlyRouteReplay"]["status"],
                         "B_ONLY_ROUTE_EDGE_WALK_REPLAY_MATCHED_SELECTED_TURN")
        self.assertEqual(branches[1]["bOnlyRouteReplay"]["status"],
                         "UNPROVEN_FOR_THIS_MODE")
        geom = branches[0]["sampledA20mToBConnectedChain"]
        self.assertEqual(geom["tailSamplesWithinOneMetre"],
                         geom["sourceTailSamples"])
        self.assertEqual(geom["nativeSelectedBGeometryJoinGapsMeters"], [0.0])
        self.assertEqual(geom["sampledDirectedOrder"],
                         "SELECTED_B_CHAIN_ALIGNED_SAMPLES_ONLY")
        self.assertEqual(branches[0]["bOnlyRouteReplay"][
            "edgeWalkReplayDirectedGraphIds"], [20,21])
        self.assertNotIn("actualTracedGraphIds", branches[0]["bOnlyRouteReplay"])
        self.assertEqual(branches[0]["bOnlyRouteReplay"][
            "originalRouteEdgeIdentity"], "NOT_VERIFIED")
        self.assertEqual(branches[0]["bOnlyRouteReplay"][
            "ambiguousGeometryRouteFidelity"], "NOT_VERIFIED")
        self.assertEqual(branches[0]["crossGraphLegalTransfer"], "NOT_VERIFIED")

    def test_b_graph_shorter_split_incoming_keeps_partial_tail_overlap(self):
        # Real B segmentation need not equal A's. An incoming B edge may
        # cover only its last 8 m of A's 20 m tail but still terminate at
        # the same native B node and connect into a forward B branch.
        a, incoming, advance, reverse = source_and_b()
        incoming["directedGeometry"] = [
            [46.499947, 13.499947], [46.5,13.5]]
        incoming["endLat"], incoming["endLon"] = 46.5, 13.5
        result = check(native_b=[advance, incoming])
        b = result["allBLocatedEdges"][1]
        self.assertTrue(b["selectedBIncomingForNativeTurnDiagnostic"])
        self.assertFalse(b["sourceTailFullyCoveredByThisBIncoming"])
        self.assertGreaterEqual(b["bIncomingTailObservation"][
            "matchedTailSamples"],2)
        matched = b["incomingToOutgoingEvidence"][
            "allNativeOutgoingAlternatives"][0]
        self.assertEqual(matched["bOnlyRouteReplay"]["status"],
                         "B_ONLY_ROUTE_EDGE_WALK_REPLAY_MATCHED_SELECTED_TURN")
        self.assertFalse(matched["sampledA20mToBConnectedChain"][
            "sampledGeometryCoversTail"])
        self.assertEqual(result["sourceDiscoveryCoverage"],"NOT_VERIFIED")

    def test_native_way_ids_are_annotation_not_a_same_road_filter(self):
        a, incoming, advance, reverse = source_and_b()
        incoming["wayId"] = 999999
        result = check(native_b=[advance, incoming],
                       get_adj=lambda gid:adjacency(incoming))
        b = result["allBLocatedEdges"][1]
        self.assertTrue(b["selectedBIncomingForNativeTurnDiagnostic"])
        self.assertFalse(b["nativeSourceWayIdEqualsBIncomingWayIdAnnotation"])
        self.assertEqual(result["sourcePhysicalFinalRoadEdge"],"NOT_VERIFIED")

    def test_bounded_budget_does_not_erase_unprobed_native_outgoings(self):
        found = check(budget=1)
        record = found["allBLocatedEdges"][1]["incomingToOutgoingEvidence"]
        branches = record["allNativeOutgoingAlternatives"]
        self.assertEqual(len(branches), 2)
        self.assertEqual(record["bOutgoingRouteProbes"], 1)
        self.assertEqual(record["bUnprobedOutgoingBranches"], 1)
        self.assertEqual(branches[1]["bOnlyRouteReplay"]["status"],
                         "NOT_PROBED_BUDGET")
        self.assertEqual(record["nativeBOutgoingDegree"], 2)

    def test_zero_route_budget_is_not_a_coverage_certificate(self):
        found = check(budget=0)
        self.assertEqual(found["bOnlyRouteProbeCount"],0)
        self.assertTrue(all(
            row["bOnlyRouteReplay"]["status"] == "NOT_PROBED_BUDGET"
            for row in found["allBLocatedEdges"][1][
                "incomingToOutgoingEvidence"]["allNativeOutgoingAlternatives"]))
        self.assertEqual(found["bLocateCompleteness"],"NOT_VERIFIED_RADIUS_ONLY")

    def test_no_b_overlap_is_not_global_crossing_rejection(self):
        a, _, advance, reverse = source_and_b()
        result = check(locators=[locator(21)],native_b=[advance])
        self.assertEqual(result["nominatedBIncomingCount"], 0)
        self.assertEqual(result["retainedReceiverIdentities"], [21])
        self.assertEqual(result["sourceDiscoveryCoverage"], "NOT_VERIFIED")

    def test_wrong_or_missing_b_locator_id_is_fatal_integrity_error(self):
        _, incoming, advance, _ = source_and_b()
        with self.assertRaises(SourceIntegrityError):
            check(native_b=[incoming, advance])
        with self.assertRaises(SourceIntegrityError):
            check(native_b=[advance])
        with self.assertRaises(SourceIntegrityError):
            check(locators=[locator(20),locator(20)],
                  native_b=[incoming,incoming])

    def test_incomplete_native_b_adjacency_aborts_instead_of_choosing_first(self):
        _, incoming, advance, reverse = source_and_b()
        for adj in (
            {**adjacency(incoming), "nativeOutgoingDegree": 3},
            {**adjacency(incoming), "sourceGraphId": 999},
            {**adjacency(incoming), "opposingGraphId": 999},
        ):
            with self.assertRaises(SourceIntegrityError):
                check(get_adj=lambda gid, a=adj:a)
        with self.assertRaises(SourceIntegrityError):
            check(get_rows=lambda ids: [advance])

    def test_no_route_edge_fidelity_promotion_even_if_replay_matches(self):
        good = check(trace_fn=lambda cfg, encoded, mode:[20,21])
        branch = good["allBLocatedEdges"][1][
            "incomingToOutgoingEvidence"]["allNativeOutgoingAlternatives"][0]
        self.assertEqual(branch["bOnlyRouteReplay"]["status"],
                         "B_ONLY_ROUTE_EDGE_WALK_REPLAY_MATCHED_SELECTED_TURN")
        self.assertEqual(branch["bOnlyRouteReplay"]["originalRouteEdgeIdentity"],
                         "NOT_VERIFIED")
        self.assertEqual(good["originalValhallaRouteEdgeIdentity"],"NOT_VERIFIED")

    def test_ambiguous_or_different_route_replay_remains_unproven(self):
        result = check(trace_fn=lambda cfg, encoded, mode:[500,600])
        branch=result["allBLocatedEdges"][1][
            "incomingToOutgoingEvidence"]["allNativeOutgoingAlternatives"][0]
        self.assertEqual(branch["bOnlyRouteReplay"]["status"],
                         "UNPROVEN_FOR_THIS_ROUTE")
        self.assertEqual(branch["crossGraphLegalTransfer"],"NOT_VERIFIED")

    def test_unavailable_b_locate_keeps_a_terminal_and_next_source_unblocked(self):
        a, incoming, advance, reverse = source_and_b()
        terminal={"sourceGraphId":10,"sourceDirectedEndpoint":A_END,
                  "graphLocalModeTerminalConfirmed":True}
        def timeout_locate(point, mode):
            raise OSError("Temporary B locate process unavailable")
        result=inspect_one_source_with_recoverable_b_reads(
            a,terminal,"auto",Path("B"),timeout_locate,
            lambda ids:[advance,incoming],lambda gid:adjacency(incoming),
            lambda ids:[advance,reverse],route_fn=good_route,
            trace_fn=good_trace)
        self.assertEqual(result["diagnosticStatus"],
                         "INCONCLUSIVE_B_READ_UNAVAILABLE")
        self.assertEqual(result["unavailableStage"],"B_LOCATE")
        self.assertIsNone(result["nominatedBIncomingCount"])
        self.assertEqual(result["sourceGraphId"],10)
        self.assertEqual(result["sourceDiscoveryCoverage"],"NOT_VERIFIED")
        another=inspect_one_source_with_recoverable_b_reads(
            a,terminal,"auto",Path("B"),
            lambda point,mode:[locator(21),locator(20)],
            lambda ids:[advance,incoming],
            lambda gid:adjacency(incoming),
            lambda ids:[{21:advance,22:reverse}[x] for x in ids],
            route_fn=good_route,trace_fn=good_trace)
        self.assertEqual(another["nominatedBIncomingCount"],1)
        self.assertEqual(another["bOnlyRouteProbeCount"],2)

    def test_unavailable_b_geometry_keeps_exact_b_locate_ids_unknown(self):
        a, incoming, advance, reverse = source_and_b()
        terminal={"sourceGraphId":10,"sourceDirectedEndpoint":A_END,
                  "graphLocalModeTerminalConfirmed":True}
        def unavailable_native(ids):
            raise ValueError("Native geometry capture failed; discard partial stdout")
        result=inspect_one_source_with_recoverable_b_reads(
            a,terminal,"auto",Path("B"),
            lambda point,mode:[locator(21),locator(20)],
            unavailable_native,lambda gid:adjacency(incoming),
            lambda ids:[advance,reverse],
            route_fn=good_route,trace_fn=good_trace)
        self.assertEqual(result["diagnosticStatus"],
                         "INCONCLUSIVE_B_READ_UNAVAILABLE")
        self.assertEqual(result["unavailableStage"],"B_GEOMETRY")
        self.assertEqual(result["retainedReceiverIdentities"],[21,20])
        self.assertEqual(len(result["allBLocatedEdges"]),2)
        self.assertTrue(all(x["evaluationStatus"] ==
            "NOT_EVALUATED_B_READ_UNAVAILABLE"
            for x in result["allBLocatedEdges"]))

    def test_b_native_identity_corruption_aborts_not_a_recoverable_road_miss(self):
        a, incoming, advance, reverse=source_and_b()
        terminal={"sourceGraphId":10,"sourceDirectedEndpoint":A_END,
                  "graphLocalModeTerminalConfirmed":True}
        def mismatched(_):
            raise ValueError("Native geometry identities/counts mismatch explicit selection")
        with self.assertRaisesRegex(ValueError,"identities/counts mismatch"):
            inspect_one_source_with_recoverable_b_reads(
                a,terminal,"auto",Path("B"),
                lambda pt,mode:[locator(21),locator(20)],
                mismatched,lambda gid:adjacency(incoming),
                lambda ids:[advance,reverse],route_fn=good_route,
                trace_fn=good_trace)

    def test_graph_id_numeric_reuse_is_not_a_cross_graph_id_match(self):
        a, incoming, advance, reverse = source_and_b()
        a["sourceGraphId"] = 20
        result=inspect_source_and_b_continuations(
            a,{"sourceGraphId":20,"sourceDirectedEndpoint":A_END,
               "graphLocalModeTerminalConfirmed":True},
            [locator(21),locator(20)],[advance,incoming],
            "auto",Path("B"),lambda gid:adjacency(incoming),
            lambda ids:[{21:advance,22:reverse}[x] for x in ids],
            route_fn=good_route,trace_fn=good_trace)
        self.assertEqual(result["sourceGraphId"],20)
        self.assertEqual(result["nominatedBIncomingCount"],1)
        self.assertEqual(result["crossGraphDirectedTurnLegality"],"NOT_VERIFIED")

if __name__=="__main__":
    unittest.main()
