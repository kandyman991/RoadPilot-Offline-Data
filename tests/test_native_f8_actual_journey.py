"""M6b F8-native actual two-leg trace is not a cross-region seam certificate."""
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from probe_native_f8_actual_journey import (
    NativeEvidenceIntegrityError, evaluate_candidate,
    evaluate_selected_batch, observe_replayed_handoff_geometry,
    selected_catalog, replay_route_shapes, verify_native_extractor,
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
                         "BOTH_EDGE_WALK_REPLAYS_MATCH_SELECTED_JOURNEY_SHAPES_ONLY")
        self.assertEqual(j["replayALastEdgeMeaning"],
                         "EDGE_WALK_REPLAY_LAST_DIRECTED_EDGE_OF_A_ROUTE_SHAPE_ONLY")
        self.assertEqual(j["replayedALastDirectedGraphId"], 11)
        self.assertEqual(j["replayedBFirstDirectedGraphId"], 22)
        self.assertTrue(j["proposedReceiverMatchesReplayedFirstEdge"])
        self.assertTrue(j["endpointArrivalAndHandoffWithinF8Tolerance"])
        self.assertEqual(j["totalDistanceKm"], .4)
        self.assertEqual(j["totalDurationSeconds"], 40)
        self.assertEqual(j["replayedEdgeGeometry"]["graphLocalGeometryObservation"],
                         "BOTH_REPLAYED_EDGES_COLOCATED_AT_SELECTED_HANDOFF_ONLY")
        self.assertEqual(j["crossSeamTurnLegality"], "NOT_VERIFIED")
        self.assertEqual(j["crossGraphPhysicalContinuity"], "NOT_VERIFIED")
        self.assertEqual(j["routeEdgeIdentityFidelity"], "NOT_VERIFIED")
        self.assertEqual(j["ambiguousGeometryEdgeIdentity"], "NOT_VERIFIED")
        self.assertEqual(
            j["edgeWalkReplayMethod"],
            "VALHALLA_TRACE_ATTRIBUTES_EDGE_WALK_OF_ROUTE_SHAPE",
        )

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
                         "BOTH_EDGE_WALK_REPLAYS_MATCH_SELECTED_JOURNEY_SHAPES_ONLY")
        g = j["replayedEdgeGeometry"]
        self.assertGreater(g["aRemainingDistanceToDirectedEdgeEndMeters"], 10)
        self.assertFalse(g["aHandoffIsAtEndOfActualLastEdgeWithinOneMetre"])
        self.assertIs(g["aReplayedEdgeDeadendFlag"], False)
        self.assertEqual(g["sourceRoadFinalEdgeIdentity"],
                         "NOT_VERIFIED_BY_SELECTED_LEG")
        self.assertEqual(j["crossSeamTurnLegality"], "NOT_VERIFIED")

    def test_actual_last_a_edge_not_nominated_from_prior_report(self):
        j = case(trace_fn=lambda cfg,shape,mode:
                 [10, 43] if str(cfg) == "A" else [22, 23])
        self.assertEqual(j["replayedALastDirectedGraphId"], 43)
        self.assertEqual(j["replayedEdgeGeometry"]["sourceReplayedDirectedGraphId"], 43)
        self.assertEqual(j["replayALastEdgeMeaning"],
                         "EDGE_WALK_REPLAY_LAST_DIRECTED_EDGE_OF_A_ROUTE_SHAPE_ONLY")

    def test_receiver_first_differs_from_original_selected_gps_proposal(self):
        j = case(trace_fn=lambda cfg,shape,mode:
                 [10, 11] if str(cfg) == "A" else [99, 23])
        self.assertEqual(j["status"], "UNPROVEN_FOR_THIS_JOURNEY")
        self.assertFalse(j["proposedReceiverMatchesReplayedFirstEdge"])
        self.assertEqual(j["replayedBFirstDirectedGraphId"], 99)
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
                         "BOTH_EDGE_WALK_REPLAYS_MATCH_SELECTED_JOURNEY_SHAPES_ONLY")

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
        self.assertEqual(j["replayedALastDirectedGraphId"],11)

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
                         "BOTH_EDGE_WALK_REPLAYS_MATCH_SELECTED_JOURNEY_SHAPES_ONLY")
        self.assertEqual(j["replayedEdgeGeometry"]["graphLocalGeometryObservation"],
                         "NOT_COLOCATED_WITHIN_ONE_METRE_FOR_SELECTED_HANDOFF")
        self.assertEqual(j["crossGraphPhysicalContinuity"], "NOT_VERIFIED")

    def test_invalid_native_mode_access_downgrades_only_this_journey(self):
        j=case(native_fn=lambda a,b:(native_edge(a),native_edge(b,mask=1)),
               mode="motorcycle")
        self.assertEqual(j["status"], "UNPROVEN_FOR_THIS_JOURNEY")
        self.assertFalse(j["replayedEdgeGeometry"]["receiverForwardModeAccess"])
        self.assertEqual(j["crossSeamTurnLegality"], "NOT_VERIFIED")

    def test_source_native_mode_access_must_match_traced_direction(self):
        j = case(native_fn=lambda a,b: (native_edge(a, mask=1), native_edge(b)),
                 mode="motorcycle")
        self.assertEqual(j["status"], "UNPROVEN_FOR_THIS_JOURNEY")
        self.assertFalse(j["replayedEdgeGeometry"]["sourceForwardModeAccess"])
        self.assertTrue(j["replayedEdgeGeometry"]["receiverForwardModeAccess"])
        self.assertEqual(j["crossSeamTurnLegality"], "NOT_VERIFIED")
        self.assertEqual(j["replayedEdgeGeometry"]["sourceRoadFinalEdgeIdentity"],
                         "NOT_VERIFIED_BY_SELECTED_LEG")

    def test_same_numeric_local_ids_are_not_cross_graph_equivalence(self):
        data={
            **replay_route_shapes(CANDIDATE, Path("A"),Path("B"),ORIGIN,DEST,"auto",
                                fake_route,
                                lambda cfg,shape,mode:[22]),
            "replayedALastDirectedGraphId":22,
        }
        g=observe_replayed_handoff_geometry(data,native_edge(22),native_edge(22),"auto")
        self.assertEqual(g["sourceReplayedDirectedGraphId"],22)
        self.assertEqual(g["receiverReplayedDirectedGraphId"],22)
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

    def test_missing_native_edge_only_degrades_its_candidate_in_mixed_batch(self):
        second = {**CANDIDATE, "id": "nf8gps-another-valid-id"}
        counter = {"calls": 0}
        def sometimes_missing(a, b):
            counter["calls"] += 1
            if counter["calls"] == 1:
                raise ValueError("Native edge id absent")
            return native_edge(a), native_edge(b)
        rows = evaluate_selected_batch(
            [CANDIDATE, second], Path("A"), Path("B"),
            ORIGIN, DEST, "auto", sometimes_missing,
            fake_route, fake_trace,
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual(counter["calls"], 2)
        self.assertEqual(rows[0]["status"], "INCONCLUSIVE")
        self.assertEqual(rows[0]["nativeGeometry"],
                         "UNAVAILABLE_FOR_THIS_CANDIDATE")
        self.assertEqual(rows[0]["candidateId"], CANDIDATE["id"])
        self.assertEqual(rows[1]["status"],
                         "BOTH_EDGE_WALK_REPLAYS_MATCH_SELECTED_JOURNEY_SHAPES_ONLY")
        self.assertEqual(rows[1]["candidateId"], second["id"])
        for row in rows:
            self.assertEqual(row["routeEdgeIdentityFidelity"], "NOT_VERIFIED")
            self.assertEqual(row["crossSeamTurnLegality"], "NOT_VERIFIED")

    def test_malformed_native_geometry_is_scoped_inconclusive(self):
        def bad_geometry(a, b):
            edge = native_edge(a)
            edge["directedGeometry"] = [[float("nan"), 13.50], [46.5,13.5]]
            return edge, native_edge(b)
        row = case(native_fn=bad_geometry)
        self.assertEqual(row["status"], "INCONCLUSIVE")
        self.assertIn("geometry", row["reason"])
        self.assertEqual(row["nativeGeometry"],
                         "UNAVAILABLE_FOR_THIS_CANDIDATE")

    def test_native_identity_mismatch_still_aborts_entire_batch(self):
        def swapped(a, b):
            return native_edge(b), native_edge(a)
        with self.assertRaises(NativeEvidenceIntegrityError):
            evaluate_selected_batch(
                [CANDIDATE, {**CANDIDATE, "id":"nf8gps-second"}],
                Path("A"), Path("B"), ORIGIN, DEST, "auto",
                swapped, fake_route, fake_trace)

    def test_native_payload_missing_graph_id_is_fatal_integrity_failure(self):
        def missing_id(a,b):
            return {k:v for k,v in native_edge(a).items()
                    if k != "sourceGraphId"}, native_edge(b)
        with self.assertRaises(NativeEvidenceIntegrityError):
            case(native_fn=missing_id)

    def test_route_shape_replay_cannot_certify_ambiguous_route_edge_identity(self):
        def same_shape_route(config, start, end, mode):
            leg = fake_route(config, start, end, mode)
            # Conflicting purported route edge IDs are intentionally
            # not consumed: edge_walk replay over shape cannot certify them.
            leg["unverifiedRouteEdgeIds"] = (
                [900, 901] if str(config)=="A" else [900, 902]
            )
            return leg
        j = case(route_fn=same_shape_route,
                 trace_fn=lambda cfg, shape, mode:
                 [10, 11] if str(cfg) == "A" else [22, 23])
        self.assertEqual(j["status"],
                         "BOTH_EDGE_WALK_REPLAYS_MATCH_SELECTED_JOURNEY_SHAPES_ONLY")
        self.assertEqual(j["routeEdgeIdentityFidelity"], "NOT_VERIFIED")
        self.assertEqual(j["ambiguousGeometryEdgeIdentity"], "NOT_VERIFIED")
        self.assertEqual(j["replayedEdgeGeometry"]["routeEdgeIdentityFidelity"],
                         "NOT_VERIFIED")
        self.assertEqual(j["replayALastEdgeMeaning"],
                         "EDGE_WALK_REPLAY_LAST_DIRECTED_EDGE_OF_A_ROUTE_SHAPE_ONLY")

    def test_native_sha256_pin_and_version_are_required_not_just_version(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "native_extractor"
            path.write_text("#!/bin/sh\nprintf '3.6.3\n'\n", encoding="utf-8")
            path.chmod(0o700)
            digest = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
            with self.assertRaisesRegex(NativeEvidenceIntegrityError, "SHA-256"):
                verify_native_extractor(path)
            proven = verify_native_extractor(path, expected_sha256=digest)
            self.assertEqual(proven["nativeExtractorSha256"], digest)
            self.assertEqual(proven["nativeExtractorVersion"], "3.6.3")
            self.assertEqual(proven["nativeExtractorProvenance"],
                             "MATCHED_TEST_CALLER_SHA256_NOT_REVIEWED")
            path.write_text("#!/bin/sh\nprintf '3.6.3\n'\n# different bytes\n",
                            encoding="utf-8")
            with self.assertRaisesRegex(NativeEvidenceIntegrityError, "SHA-256"):
                verify_native_extractor(path, expected_sha256=digest)

    def test_unsafe_or_invalid_inputs_cannot_promote_evidence(self):
        with self.assertRaises(ValueError):
            case(mode="pedestrian")
        with self.assertRaises(ValueError):
            case(candidate={**CANDIDATE,"receiverGraphId":0})
        with self.assertRaises(ValueError):
            case(candidate={**CANDIDATE,"coordinate":
                            {"lat":float("nan"),"lng":12.0}})
        with self.assertRaisesRegex(ValueError,"not bound"):
            observe_replayed_handoff_geometry(
                {"replayedALastDirectedGraphId":11,
                 "replayedBFirstDirectedGraphId":22,
                 "actualAHandoff":HANDOFF,"actualBHandoff":HANDOFF},
                native_edge(11),native_edge(23),"auto")

if __name__ == "__main__":
    unittest.main()
