"""M6b F8-native actual two-leg trace is not a cross-region seam certificate."""
from __future__ import annotations

import gzip
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from probe_native_f8_actual_journey import (
    evaluate_candidate, observe_actual_handoff_geometry, selected_catalog,
    trace_actual_legs,
)

MODE_MASK = 1025
HANDOFF = {"lat": 46.500000, "lng": 13.500000}
ORIGIN = {"lat": 46.499000, "lng": 13.499000}
DEST = {"lat": 46.501000, "lng": 13.501000}
CANDIDATE = {
    "id": "nf8gps-test-12345678",
    "coordinate": HANDOFF, "receiverGraphId": 22, "direction": "from-to",
}


def native_edge(gid: int, mask: int = MODE_MASK, *, farther=False) -> dict:
    if gid == 11:
        geom = [[46.4998, 13.4998], [46.5, 13.5]]
    else:
        geom = [[46.5, 13.5], [46.5002, 13.5002]]
    if farther:
        geom = [[lat + 0.01, lng + 0.01] for lat, lng in geom]
    return {
        "sourceGraphId": gid, "endNodeGraphId": gid + 100,
        "wayId": gid + 1000, "forwardAccess": mask,
        "endLat": geom[-1][0], "endLon": geom[-1][1],
        "directedGeometry": geom,
    }


def fake_route(config, start, end, mode):
    return {
        "status": "SUCCEEDED",
        "startOffsetMeters": 0.0, "endOffsetMeters": 0.0,
        "startActual": start.copy(), "endActual": end.copy(),
        "encodedShape": ("graph-A" if str(config) == "A" else "graph-B"),
        "durationSeconds": 20.0, "distanceKm": 0.2,
    }


def fake_trace(config, shape, mode):
    return [10, 11] if str(config) == "A" else [22, 23]


def case(candidate=None, route_fn=fake_route, trace_fn=fake_trace,
         native_fn=None, mode="auto"):
    if native_fn is None:
        native_fn = lambda a, b: (native_edge(a), native_edge(b))
    return evaluate_candidate(
        CANDIDATE if candidate is None else candidate,
        Path("A"), Path("B"), ORIGIN, DEST, mode, native_fn,
        route_fn, trace_fn,
    )


class ActualJourneyTests(unittest.TestCase):
    def test_real_traces_and_native_edges_coincide_but_never_prove_cross_seam(self):
        j = case()
        self.assertEqual(j["status"],
                         "BOTH_ACTUAL_GRAPH_LOCAL_LEGS_TRACED_FOR_THIS_JOURNEY")
        self.assertEqual(j["aLastEdgeMeaning"],
                         "ACTUAL_LAST_DIRECTED_EDGE_OF_THIS_A_ROUTE_ONLY")
        self.assertEqual(j["actualALastDirectedGraphId"], 11)
        self.assertEqual(j["actualBFirstDirectedGraphId"], 22)
        self.assertTrue(j["proposedReceiverMatchesActualFirstEdge"])
        self.assertTrue(j["endpointArrivalAndHandoffWithinF8Tolerance"])
        self.assertEqual(j["totalDistanceKm"], .4)
        self.assertEqual(j["totalDurationSeconds"], 40)
        self.assertEqual(j["actualEdgeGeometry"]["graphLocalGeometryObservation"],
                         "BOTH_TRACED_EDGES_COLOCATED_AT_SELECTED_HANDOFF_ONLY")
        self.assertEqual(j["crossSeamTurnLegality"], "NOT_VERIFIED")
        self.assertEqual(j["crossGraphPhysicalContinuity"], "NOT_VERIFIED")

    def test_actual_routed_last_edge_cannot_be_inferred_as_last_retained_road_edge(self):
        def mid_edge(a, b):
            source = native_edge(a)
            source["directedGeometry"] = [
                [46.4998, 13.4998], [46.5, 13.5], [46.5005, 13.5005]]
            source["endLat"], source["endLon"] = 46.5005, 13.5005
            source["deadend"] = False
            return source, native_edge(b)
        j = case(native_fn=mid_edge)
        self.assertEqual(j["status"],
                         "BOTH_ACTUAL_GRAPH_LOCAL_LEGS_TRACED_FOR_THIS_JOURNEY")
        g = j["actualEdgeGeometry"]
        self.assertGreater(g["aRemainingDistanceToDirectedEdgeEndMeters"], 10)
        self.assertFalse(g["aHandoffIsAtEndOfActualLastEdgeWithinOneMetre"])
        self.assertIs(g["aNativeLastEdgeDeadendFlag"], False)
        self.assertEqual(g["sourceRoadFinalEdgeIdentity"],
                         "NOT_VERIFIED_BY_SELECTED_LEG")
        self.assertEqual(j["crossSeamTurnLegality"], "NOT_VERIFIED")

    def test_actual_last_a_edge_not_nominated_from_prior_report(self):
        j = case(trace_fn=lambda cfg,shape,mode:
                 [10, 43] if str(cfg) == "A" else [22, 23])
        self.assertEqual(j["actualALastDirectedGraphId"], 43)
        self.assertEqual(j["actualEdgeGeometry"]["sourceActualDirectedGraphId"], 43)
        self.assertEqual(j["aLastEdgeMeaning"],
                         "ACTUAL_LAST_DIRECTED_EDGE_OF_THIS_A_ROUTE_ONLY")

    def test_receiver_first_differs_from_original_selected_gps_proposal(self):
        j = case(trace_fn=lambda cfg,shape,mode:
                 [10, 11] if str(cfg) == "A" else [99, 23])
        self.assertEqual(j["status"], "UNPROVEN_FOR_THIS_JOURNEY")
        self.assertFalse(j["proposedReceiverMatchesActualFirstEdge"])
        self.assertEqual(j["actualBFirstDirectedGraphId"], 99)
        self.assertEqual(j["crossGraphPhysicalContinuity"], "NOT_VERIFIED")

    def test_large_b_start_snap_downgrades_selected_journey(self):
        def far_b(config,start,end,mode):
            leg = fake_route(config,start,end,mode)
            if str(config) == "B":
                leg["startOffsetMeters"] = 30.0
            return leg
        j = case(route_fn=far_b)
        self.assertEqual(j["status"], "UNPROVEN_FOR_THIS_JOURNEY")
        self.assertFalse(j["endpointArrivalAndHandoffWithinF8Tolerance"])

    def test_invalid_b_destination_arrival_downgrades(self):
        def far_end(config,start,end,mode):
            leg = fake_route(config,start,end,mode)
            if str(config) == "B":
                leg["endActual"] = {"lat": end["lat"] + 0.001, "lng":end["lng"]}
            return leg
        j = case(route_fn=far_end)
        self.assertEqual(j["status"], "UNPROVEN_FOR_THIS_JOURNEY")
        self.assertGreater(j["destinationArrivalErrorMeters"], 25)

    def test_b_request_uses_actual_a_handoff_not_proposed_coordinate(self):
        normalized = {"lat": 46.500001, "lng": 13.500001}
        called = []
        def changed_a(config,start,end,mode):
            called.append((str(config),start.copy(),end.copy()))
            leg = fake_route(config,start,end,mode)
            if str(config) == "A":
                leg["endActual"] = normalized
                leg["endOffsetMeters"] = 0.2
            return leg
        j = case(route_fn=changed_a)
        self.assertEqual(called[1][0], "B")
        self.assertEqual(called[1][1], normalized)
        self.assertEqual(j["status"],
                         "BOTH_ACTUAL_GRAPH_LOCAL_LEGS_TRACED_FOR_THIS_JOURNEY")

    def test_first_or_second_unavailable_is_inconclusive_not_global_rejection(self):
        def a_failed(config,start,end,mode):
            if str(config) == "A":
                return {"status": "FAILED"}
            return fake_route(config,start,end,mode)
        self.assertEqual(case(route_fn=a_failed)["status"], "INCONCLUSIVE")
        def b_failed(config,start,end,mode):
            if str(config) == "B":
                return {"status": "FAILED"}
            return fake_route(config,start,end,mode)
        j=case(route_fn=b_failed)
        self.assertEqual(j["status"], "INCONCLUSIVE")
        self.assertEqual(j["actualALastDirectedGraphId"],11)

    def test_invalid_traces_fail_closed_as_inconclusive(self):
        for bad in (None, [], ["bad"], [0, 22], [True, 22]):
            j=case(trace_fn=lambda cfg,shape,mode: bad)
            self.assertEqual(j["status"], "INCONCLUSIVE")

    def test_fraudulent_native_graph_local_ids_cannot_be_used(self):
        def swapped(a,b):
            return native_edge(b), native_edge(a)
        with self.assertRaisesRegex(ValueError, "not bound"):
            case(native_fn=swapped)

    def test_mismatched_native_geometry_is_observation_not_filter(self):
        j=case(native_fn=lambda a,b: (native_edge(a),native_edge(b,farther=True)))
        self.assertEqual(j["status"],
                         "BOTH_ACTUAL_GRAPH_LOCAL_LEGS_TRACED_FOR_THIS_JOURNEY")
        self.assertEqual(j["actualEdgeGeometry"]["graphLocalGeometryObservation"],
                         "NOT_COLOCATED_WITHIN_ONE_METRE_FOR_SELECTED_HANDOFF")
        self.assertEqual(j["crossGraphPhysicalContinuity"], "NOT_VERIFIED")

    def test_invalid_native_mode_access_downgrades_only_this_journey(self):
        j=case(native_fn=lambda a,b:(native_edge(a),native_edge(b,mask=1)),
               mode="motorcycle")
        self.assertEqual(j["status"], "UNPROVEN_FOR_THIS_JOURNEY")
        self.assertFalse(j["actualEdgeGeometry"]["receiverForwardModeAccess"])
        self.assertEqual(j["crossSeamTurnLegality"], "NOT_VERIFIED")

    def test_same_numeric_local_ids_are_not_cross_graph_equivalence(self):
        data={
            **trace_actual_legs(CANDIDATE, Path("A"),Path("B"),ORIGIN,DEST,"auto",
                                fake_route,
                                lambda cfg,shape,mode:[22]),
            "actualALastDirectedGraphId":22,
        }
        g=observe_actual_handoff_geometry(data,native_edge(22),native_edge(22),"auto")
        self.assertEqual(g["sourceActualDirectedGraphId"],22)
        self.assertEqual(g["receiverActualDirectedGraphId"],22)
        self.assertEqual(g["crossSeamDirectedLegality"],"NOT_VERIFIED")

    def test_catalog_preserves_all_unselected_native_proposals(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"native.jsonl.gz"
            items=[{
                "id":f"nf8gps-{i:08d}",
                "coordinate":HANDOFF,
                "receiverGraphId":i+10,
                "direction":"from-to",
            } for i in range(5)]
            with gzip.open(path,"wt",encoding="utf-8") as stream:
                for obj in items:
                    stream.write(json.dumps(obj)+"\n")
            chosen,total=selected_catalog(path,[items[3]["id"],items[1]["id"]],
                                          "from-to",5)
            self.assertEqual(total,5)
            self.assertEqual([x["id"] for x in chosen],
                             [items[3]["id"],items[1]["id"]])
            with self.assertRaisesRegex(ValueError,"Incomplete"):
                selected_catalog(path,[items[0]["id"]],"from-to",3)
            with self.assertRaisesRegex(ValueError,"Invalid explicit"):
                selected_catalog(path,[items[1]["id"],items[1]["id"]],"from-to",5)
            with self.assertRaises(ValueError):
                selected_catalog(path,["nf8gps-notfound"],"from-to",5)
            with self.assertRaises(ValueError):
                selected_catalog(path,[items[0]["id"]],"to-from",5)

    def test_unsafe_or_invalid_inputs_cannot_promote_evidence(self):
        with self.assertRaises(ValueError):
            case(mode="pedestrian")
        with self.assertRaises(ValueError):
            case(candidate={**CANDIDATE,"receiverGraphId":0})
        with self.assertRaises(ValueError):
            case(candidate={**CANDIDATE,"coordinate":
                            {"lat":float("nan"),"lng":12.0}})
        with self.assertRaisesRegex(ValueError,"not bound"):
            observe_actual_handoff_geometry(
                {"actualALastDirectedGraphId":11,
                 "actualBFirstDirectedGraphId":22,
                 "actualAHandoff":HANDOFF,"actualBHandoff":HANDOFF},
                native_edge(11),native_edge(23),"auto")

if __name__ == "__main__":
    unittest.main()
