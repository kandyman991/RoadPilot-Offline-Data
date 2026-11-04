"""M6c native clip terminal: graph-local evidence, never a seam certificate."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace

from shapely.geometry import Point, box

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from probe_native_f8_clipped_terminal import (
    CRS, SourceIntegrityError, _at,
    check_source_terminal, inspect_receivers, local_journey_sample,
    locate_receiver_edges, verified_buffer,
)

MASK = 1025
END = {"lat": 46.5, "lng": 13.5}


def edge(gid=100, *, mask=MASK, deadend=True):
    return {
        "sourceGraphId": gid, "endNodeGraphId": gid + 100,
        "wayId": gid + 1000, "forwardAccess": mask,
        "endLat": END["lat"], "endLon": END["lng"],
        "deadend": deadend,
        "directedGeometry": [[46.499, 13.499], [46.5, 13.5]],
    }


def out(gid, mask=MASK, road=True, shortcut=False):
    return {
        "graphId": gid, "endNodeGraphId": gid + 400,
        "forwardAccess": mask, "isRoad": road, "isShortcut": shortcut,
        "autoBit": bool(mask & 1),
        "motorcycleBit": bool(mask & 1024),
    }


def adjacency(entries=None, *, source=None):
    source = source or edge()
    if entries is None:
        entries = [out(777), out(888, mask=0)]
    return {
        "sourceGraphId": source["sourceGraphId"],
        "endNodeGraphId": source["endNodeGraphId"],
        "wayId": source["wayId"],
        "forwardAccess": source["forwardAccess"],
        "nativeOutgoingDegree": len(entries),
        "opposingGraphId": 777,
        "outgoingDirectedEdges": entries,
    }


def buffers():
    x, y = CRS.transform(END["lng"], END["lat"])
    # The point lies on the true outer boundary of its source buffer.
    own = {
        "polygon": box(x-250, y-100, x, y+100),
        "sha256": "sha256:" + "a"*64,
    }
    peer = {
        "polygon": box(x-300, y-200, x+300, y+200),
        "sha256": "sha256:" + "b"*64,
    }
    return own, peer


class ClippedTerminalTests(unittest.TestCase):
    def test_terminal_is_mode_local_only_without_reverse_or_road_filter(self):
        own, peer = buffers()
        source = edge()
        native = adjacency()
        result = check_source_terminal(source, native, "auto", own, peer)
        self.assertTrue(result["graphLocalClippedTerminalCandidate"])
        self.assertEqual(result["graphLocalTerminalStatus"],
                         "NATIVE_MODE_LOCAL_TERMINAL_IN_PEER_BUFFER_NEAR_OWN_OUTLINE")
        self.assertEqual(result["modeLegalNonreverseOutgoingRoadGraphIds"], [])
        self.assertEqual([x["graphId"] for x in result["allNativeOutgoingAlternatives"]],
                         [777, 888])
        self.assertEqual(result["nativeOutgoingDegree"], 2)
        self.assertTrue(result["sourceEndInsidePeerRetainedBuffer"])
        self.assertEqual(result["bufferProvenance"],
                         "BOTH_SHA_BOUND_TO_RESPECTIVE_GRAPH_MANIFESTS")
        self.assertEqual(result["physicalRoadFinalEdgeIdentity"], "NOT_VERIFIED")
        self.assertEqual(result["crossGraphDirectedTransfer"], "NOT_VERIFIED")

    def test_real_forward_mode_edge_disables_this_terminal_status_only(self):
        own, peer = buffers()
        result = check_source_terminal(
            edge(), adjacency([out(777), out(888, MASK)]),
            "auto", own, peer)
        self.assertFalse(result["graphLocalClippedTerminalCandidate"])
        self.assertEqual(result["modeLegalNonreverseOutgoingRoadGraphIds"], [888])
        self.assertEqual(result["physicalRoadFinalEdgeIdentity"], "NOT_VERIFIED")

    def test_road_clipping_requires_deadend_and_boundary_and_peer_coverage(self):
        own, peer = buffers()
        no_deadend = check_source_terminal(
            edge(deadend=False), adjacency(), "auto", own, peer)
        self.assertFalse(no_deadend["graphLocalClippedTerminalCandidate"])
        far_own = {**own, "polygon": own["polygon"].buffer(10000)}
        off_clip = check_source_terminal(
            edge(), adjacency(), "auto", far_own, peer)
        self.assertTrue(off_clip["graphLocalClippedTerminalCandidate"])
        self.assertFalse(off_clip["nearSampledOwnBufferOutline"])
        self.assertEqual(off_clip["boundaryProximityEligibility"], "NOT_A_FILTER")
        self.assertEqual(off_clip["graphLocalTerminalStatus"],
                         "NATIVE_MODE_LOCAL_TERMINAL_IN_PEER_BUFFER_OUTLINE_FARTHER")
        x, y = CRS.transform(END["lng"], END["lat"])
        far_peer = {**peer, "polygon": box(x+1000, y+1000, x+1200, y+1200)}
        no_overlap = check_source_terminal(
            edge(), adjacency(), "auto", own, far_peer)
        self.assertFalse(no_overlap["graphLocalClippedTerminalCandidate"])

    def test_forward_mode_access_is_required_and_not_a_global_negative(self):
        own, peer = buffers()
        s = edge(mask=1)
        adj = adjacency(source=s)
        motorcycle = check_source_terminal(s, adj, "motorcycle", own, peer)
        self.assertFalse(motorcycle["graphLocalClippedTerminalCandidate"])
        car = check_source_terminal(s, adj, "auto", own, peer)
        self.assertTrue(car["graphLocalClippedTerminalCandidate"])

    def test_incomplete_or_false_outgoing_inventory_fails_closed(self):
        own, peer = buffers()
        for mutate in (
            lambda a: a.update(nativeOutgoingDegree=3),
            lambda a: a.update(opposingGraphId=999),
            lambda a: a["outgoingDirectedEdges"][1].update(graphId=777),
            lambda a: a.update(endNodeGraphId=112233),
            lambda a: a["outgoingDirectedEdges"][1].update(autoBit=True),
        ):
            a = adjacency()
            mutate(a)
            with self.assertRaises(SourceIntegrityError):
                check_source_terminal(edge(), a, "auto", own, peer)

    def test_manifest_buffer_hash_and_25km_are_not_optional(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)/"buffer.geojson"
            raw = {"type":"Feature", "geometry":{
                "type":"Polygon",
                "coordinates":[[[13.4,46.4],[13.6,46.4],
                                [13.6,46.6],[13.4,46.6],[13.4,46.4]]]
            }}
            p.write_text(json.dumps(raw), encoding="utf-8")
            digest = hashlib.sha256(p.read_bytes()).hexdigest()
            m = {"source":{"borderBufferKm":25.0,"bufferGeoJsonSha256":digest}}
            verified = verified_buffer(p,m)
            self.assertEqual(verified["sha256"],"sha256:"+digest)
            self.assertEqual(verified["bufferKm"],25.0)
            with self.assertRaises(SourceIntegrityError):
                verified_buffer(p,{"source":{**m["source"],"borderBufferKm":24.9}})
            p.write_text(p.read_text()+" ",encoding="utf-8")
            with self.assertRaisesRegex(SourceIntegrityError,"SHA-256"):
                verified_buffer(p,m)

    def test_locate_preserves_both_b_edges_including_opposing_direction(self):
        raw = [{"edges":[
            {"edge_id":{"value":1001},"distance":0.1,
             "edge":{"deadend":False,"forward":True}},
            {"edge_id":{"value":1002},"distance":0.2,
             "edge":{"deadend":False,"forward":False}},
        ]}]
        def runner(*args, **kwargs):
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps(raw)+"\n[INFO] Running valhalla",
            )
        observed = locate_receiver_edges(Path("B"),END,"auto",runner=runner)
        self.assertEqual([x["receiverGraphId"] for x in observed],[1001,1002])
        self.assertEqual([x["locateForward"] for x in observed],[True,False])
        self.assertTrue(all(x["locateDistanceMeters"] <= .2 for x in observed))

    def test_receiver_identity_mismatch_is_fatal(self):
        located=[{"receiverGraphId":1001,"locateDistanceMeters":0.0}]
        with self.assertRaises(SourceIntegrityError):
            inspect_receivers(END,located,[edge(gid=1002)],"auto")

    def test_receiver_alternatives_include_reverse_and_inaccessible(self):
        rows=[edge(gid=1001),edge(gid=1002,mask=0)]
        found=[
            {"receiverGraphId":1001,"locateDistanceMeters":0.0},
            {"receiverGraphId":1002,"locateDistanceMeters":0.1},
        ]
        result=inspect_receivers(END,found,rows,"auto")
        self.assertEqual([x["receiverGraphId"] for x in result],[1001,1002])
        self.assertEqual([x["modeForwardAccess"] for x in result],[True,False])
        self.assertTrue(all(x["crossGraphLegalTransfer"]=="NOT_VERIFIED" for x in result))

    def test_local_both_legs_are_not_proof_of_cross_graph_seam(self):
        source=edge(100)
        receiver={
            **edge(1001),
            "directedGeometry":[[46.5,13.5],[46.5006,13.5006]],
            "endLat":46.5006,"endLon":13.5006,
        }
        calls=[]
        def route_fn(config, start, dest, mode):
            calls.append((str(config),start,dest,mode))
            return {
                "status":"SUCCEEDED","startActual":start,
                "endActual":dest,"durationSeconds":5.0,"distanceKm":.025,
            }
        result=local_journey_sample(source,receiver,Path("A"),
                                    Path("B"),"auto",route_fn=route_fn)
        self.assertEqual(result["status"],
            "TWO_GRAPH_LOCAL_ROUTE_LEGS_SUCCEEDED_FOR_TERMINAL_SAMPLE")
        self.assertEqual([x[0] for x in calls],["A","B"])
        self.assertEqual(result["sourcePhysicalRoadFinalEdgeIdentity"],"NOT_VERIFIED")
        self.assertEqual(result["routeEdgeIdentityFidelity"],"NOT_VERIFIED")
        self.assertEqual(result["crossGraphDirectedTransfer"],"NOT_VERIFIED")

    def test_limited_receiver_length_records_unattempted_not_dropped(self):
        source=edge()
        receiver={
            **edge(1001),
            "directedGeometry":[[46.5,13.5],[46.50001,13.50001]],
            "endLat":46.50001,"endLon":13.50001,
        }
        result=local_journey_sample(source,receiver,Path("A"),Path("B"),"auto")
        self.assertEqual(result["status"],
                         "NOT_ATTEMPTED_SHORT_OR_INACCESSIBLE_LOCAL_LEG")


if __name__ == "__main__":
    unittest.main()
