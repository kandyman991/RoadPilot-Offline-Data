"""Original Valhalla route-edge identities are NOT shape replay nor crossings."""
from __future__ import annotations

import json
import hashlib
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from native_f8_original_route import (
    route_with_original_ids, validate_original_route, verify_native_route_binary
)
from probe_native_f8_journey import check_one


def poly6(points: list[tuple[float, float]]) -> str:
    oldlat=oldlng=0
    parts=[]
    for lat,lng in points:
        for value,prev in ((round(lat*1_000_000),oldlat),
                           (round(lng*1_000_000),oldlng)):
            diff=value-prev
            v=(diff<<1) if diff>=0 else ((~diff)<<1)|1
            while v>=32:
                parts.append(chr((32|(v&31))+63))
                v>>=5
            parts.append(chr(v+63))
        oldlat,oldlng=round(lat*1_000_000),round(lng*1_000_000)
    return ''.join(parts)


ORIGIN={"lat":46.5,"lng":13.5}
END={"lat":46.5001,"lng":13.5001}
GPS={"lat":46.50005,"lng":13.50005}


def valid_native(start=ORIGIN,end=END,first=5,last=6):
    return {
        "schema":"roadpilot.f8-original-valhalla-route-edges",
        "version":1,"valhallaVersion":"3.6.3",
        "edgeIdOrigin":"ORIGINAL_TRIPLEG_NODE_EDGE_PROTOBUF",
        "routeCalculationCount":1,"graphLocalOnly":True,
        "legCount":1,"nodeCount":3,
        "durationSeconds":25.5,"distanceKm":0.5,
        "encodedShape":poly6([
            (start["lat"],start["lng"]),(end["lat"],end["lng"])]),
        "directedEdges":[{"graphId":first,"wayId":123},
                         {"graphId":last,"wayId":456}],
        "firstDirectedGraphId":first,"lastDirectedGraphId":last,
        "routeEdgeIdentity":"ORIGINAL_VALHALLA_ROUTE_PROTOBUF",
        "crossGraphLegalTransfer":"NOT_VERIFIED",
        "physicalRoadFinalEdge":"NOT_VERIFIED",
        "productionPublication":"BLOCKED",
    }


class OriginalRouteEdgeTests(unittest.TestCase):
    def test_native_route_proto_verifies_original_full_edge_list_and_endpoints(self):
        doc=validate_original_route(valid_native(),ORIGIN,END)
        self.assertEqual(doc["status"],"SUCCEEDED")
        self.assertEqual(doc["originalNativeDirectedGraphIds"],[5,6])
        self.assertEqual(doc["firstDirectedGraphId"],5)
        self.assertEqual(doc["lastDirectedGraphId"],6)
        self.assertEqual(doc["startOffsetMeters"],0)
        self.assertEqual(doc["endOffsetMeters"],0)
        self.assertEqual(doc["durationSeconds"],25.5)
        self.assertEqual(doc["originalRouteEdgeIdentity"],
                         "ORIGINAL_VALHALLA_ROUTE_PROTOBUF")
        self.assertEqual(doc["crossGraphLegalTransfer"],"NOT_VERIFIED")
        self.assertEqual(doc["physicalLastRetainedRoadEdge"],"NOT_VERIFIED")

    def test_wrong_version_first_edge_way_id_or_provenance_aborts(self):
        overrides=(
            ("schema","other"),
            ("version",2),
            ("valhallaVersion","3.7.0"),
            ("routeCalculationCount",2),
            ("edgeIdOrigin","REPLAY_SHAPE_MATCH"),
            ("crossGraphLegalTransfer","VERIFIED"),
            ("productionPublication","PUBLISHED"),
            ("firstDirectedGraphId",100),
            ("nodeCount",4),
            ("nodeCount",2),
            ("durationSeconds",0),
            ("distanceKm",float('nan')),
            ("directedEdges",[{"graphId":5,"wayId":0}]),
        )
        for name,value in overrides:
            with self.subTest(field=name), self.assertRaises(ValueError):
                validate_original_route({**valid_native(),name:value},ORIGIN,END)

    def test_original_first_B_edge_match_without_trace_attributes(self):
        def original(cfg,start,end,mode):
            value=valid_native(start,end,first=8 if str(cfg)=="A" else 44,
                               last=9 if str(cfg)=="A" else 45)
            return validate_original_route(value,start,end)
        candidate={"id":"nativeGPS1","receiverGraphId":44,"coordinate":GPS}
        def forbidden_replay(*args):
            raise AssertionError("No independent trace_attributes replay allowed")
        answer=check_one(candidate,Path("A"),Path("B"),
                         ORIGIN,END,"motorcycle",original,forbidden_replay)
        self.assertEqual(answer["status"],
                         "TWO_GRAPH_LOCAL_LEGS_ORIGINAL_ROUTE_EDGE_MATCH_ONLY")
        self.assertEqual(answer["receiverOriginalFirstDirectedGraphId"],44)
        self.assertEqual(answer["sourceOriginalLastDirectedGraphId"],9)
        self.assertEqual(answer["originalRouteEdgeIdentity"],
                         "VERIFIED_FOR_THESE_TWO_GRAPH_LOCAL_LEGS")
        self.assertEqual(answer["receiverTraceOrigin"],
                         "ORIGINAL_VALHALLA_ROUTE_TRIP_PROTOBUF")
        self.assertEqual(answer["crossGraphLegalTransfer"],"NOT_VERIFIED")
        self.assertEqual(answer["physicalLastRetainedRoadEdge"],"NOT_VERIFIED")

    def test_wrong_original_B_route_edge_remains_unproven_even_if_route_succeeds(self):
        candidate={"id":"nativeGPS2","receiverGraphId":44,"coordinate":GPS}
        def original(cfg,start,end,mode):
            return validate_original_route(
                valid_native(start,end,first=8 if str(cfg)=="A" else 999,
                             last=9 if str(cfg)=="A" else 1000),
                start,end)
        answer=check_one(candidate,Path("A"),Path("B"),ORIGIN,END,
                         "auto",original,
                         lambda *args: (_ for _ in ()).throw(
                             AssertionError("Trace replay must not be executed")))
        self.assertEqual(answer["status"],"UNPROVEN")
        self.assertFalse(answer["receiverEdgeMatches"])
        self.assertEqual(answer["receiverOriginalFirstDirectedGraphId"],999)
        self.assertEqual(answer["originalRouteEdgeIdentity"],
                         "VERIFIED_FOR_THESE_TWO_GRAPH_LOCAL_LEGS")

    def test_native_binary_return_error_discards_partial_stdout(self):
        with tempfile.TemporaryDirectory() as td:
            binary=Path(td)/"native_f8_route_edges"
            binary.write_bytes(b"not a real binary")
            calls=[]
            def fake_run(command, **kwargs):
                calls.append(command)
                return SimpleNamespace(
                    returncode=2,stdout='{"some":"partial"}',
                    stderr="PARTIAL_STDOUT_MUST_BE_DISCARDED")
            result=route_with_original_ids(
                Path("graph.json"),ORIGIN,END,"auto",binary,
                runner=fake_run)
            self.assertEqual(len(calls),1)
            self.assertEqual(result["status"],"FAILED")
            self.assertNotIn("directedEdges",result)
            self.assertEqual(result["originalRouteEdgeIdentity"],"NOT_VERIFIED")

    def test_native_binary_version_and_content_hash(self):
        with tempfile.TemporaryDirectory() as td:
            binary=Path(td)/"native_f8_route_edges"
            binary.write_bytes(b"test binary content")
            def version(cmd,**kwargs):
                self.assertEqual(cmd,[str(binary),"--version"])
                return SimpleNamespace(returncode=0,stdout="3.6.3\n")
            pin="sha256:"+hashlib.sha256(binary.read_bytes()).hexdigest()
            self.assertEqual(
                verify_native_route_binary(
                    binary,version,expected_sha256=pin),pin)
            def stale(*args,**kwargs):
                return SimpleNamespace(returncode=0,stdout="3.7.0\n")
            with self.assertRaisesRegex(ValueError,"version mismatch"):
                verify_native_route_binary(binary,stale,expected_sha256=pin)

    def test_binary_hash_pin_is_mandatory_before_any_native_code_runs(self):
        with tempfile.TemporaryDirectory() as td:
            binary=Path(td)/"native_f8_route_edges"
            binary.write_bytes(b"known owner artifact")
            verified="sha256:"+hashlib.sha256(binary.read_bytes()).hexdigest()
            executed=[]
            def fake_run(*args,**kwargs):
                executed.append(args)
                return SimpleNamespace(returncode=0,stdout="3.6.3\n")
            with self.assertRaisesRegex(ValueError,"mandatory"):
                verify_native_route_binary(binary,fake_run)
            with self.assertRaisesRegex(ValueError,"SHA-256 does not match"):
                verify_native_route_binary(
                    binary,fake_run,expected_sha256="sha256:"+"0"*64)
            with self.assertRaisesRegex(ValueError,"mandatory"):
                verify_native_route_binary(
                    binary,fake_run,expected_sha256="not-a-sha")
            self.assertEqual(executed,[])
            self.assertEqual(
                verify_native_route_binary(
                    binary,fake_run,expected_sha256=verified),verified)
            self.assertEqual(len(executed),1)
            binary.write_bytes(b"substituted executable")
            with self.assertRaisesRegex(ValueError,"SHA-256 does not match"):
                verify_native_route_binary(
                    binary,fake_run,expected_sha256=verified)
            self.assertEqual(len(executed),1)


if __name__=="__main__":
    unittest.main()
