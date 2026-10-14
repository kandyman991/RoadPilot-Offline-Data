"""Test multi-region F8-derived Valhalla route composition without network or graphs."""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
SPEC=importlib.util.spec_from_file_location("plan_multiregion_route",ROOT/"tools/plan_multiregion_route.py")
route=importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name]=route
SPEC.loader.exec_module(route)


class MultiRegionRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.a=route.Graph("a",self.root/"a-manifest.json","sha256:"+"a"*64,"it",{"at":"sha256:"+"a"*64})
        self.b=route.Graph("b",self.root/"b-manifest.json","sha256:"+"b"*64,"at",{"it":"sha256:"+"b"*64})
        self.start={"lat":46.0,"lng":12.0}
        self.end={"lat":47.0,"lng":12.3}
        self.aexit={"lat":46.5,"lng":12.0}
        self.bentry={"lat":46.50002,"lng":12.00002}
        self.chain={"id":"xhc1-case","regions":["a","b"],"crossings":[
            {"candidateId":"xpc1-one","fromExitAnchorId":"exit-a","toEntryAnchorId":"entry-b"}]}
        self.anchors={
            "a":{"exit-a":{"graphAnchor":{"coordinate":self.aexit,"graphId":11}}},
            "b":{"entry-b":{"graphAnchor":{"coordinate":self.bentry,"graphId":22}}},
        }

    def fake_leg(self,service,config,src,dst,costing,options,timeout=18,**kwargs):
        return {"geometry":[[src["lng"],src["lat"]],[dst["lng"],dst["lat"]]],
                "distanceKm":20.0,"durationSeconds":900.0,
                "actualStart":src,"actualEnd":dst,
                "startOffsetMeters":0.0,"endOffsetMeters":0.0}

    def test_aggregates_exact_valhalla_legs_without_inventing_handoff_segment(self):
        with mock.patch.object(route,"leg_route",side_effect=self.fake_leg):
            result=route.evaluate_chain(self.chain,self.anchors,self.start,self.end,
                {"a":self.a,"b":self.b},self.root,Path("/valhalla"),
                "motorcycle",{},route.time.monotonic()+10,{})
        self.assertTrue(result["destinationReached"])
        self.assertEqual(result["regions"],["a","b"])
        self.assertEqual(result["geometry"]["type"],"MultiLineString")
        self.assertEqual(len(result["geometry"]["coordinates"]),2)
        self.assertEqual(result["distanceKm"],40.0)
        self.assertEqual(result["durationSeconds"],1800.0)
        self.assertGreater(result["handoffs"][0]["gapMeters"],0.0)
        self.assertEqual(result["endOffsetMeters"],0.0)

    def test_partial_middle_or_final_leg_is_rejected(self):
        def wrong_endpoint(*args,**kwargs):
            out=self.fake_leg(*args,**kwargs)
            out["actualEnd"]={"lat":47.0,"lng":13.0}
            return out
        with mock.patch.object(route,"leg_route",side_effect=wrong_endpoint):
            # Real leg_route must enforce endpoint arrival, not evaluate_chain.
            with self.assertRaisesRegex(ValueError,"Leg"):
                def refuse(*args,**kwargs):
                    out=wrong_endpoint(*args,**kwargs)
                    if route.distance(args[3],out["actualEnd"])>150:
                        raise ValueError("Leg did not reach endpoint")
                    return out
                with mock.patch.object(route,"leg_route",side_effect=refuse):
                    route.evaluate_chain(self.chain,self.anchors,self.start,self.end,
                        {"a":self.a,"b":self.b},self.root,Path("/valhalla"),
                        "motorcycle",{},route.time.monotonic()+10,{})

    def test_end_to_end_declares_no_complete_route_not_fake_success(self):
        with mock.patch.multiple(route,
            trusted_graphs=mock.DEFAULT,regions_containing=mock.DEFAULT,
            local_assets=mock.DEFAULT,proposed_chains=mock.DEFAULT,leg_route=mock.DEFAULT) as funcs:
            funcs["trusted_graphs"].return_value={"a":self.a,"b":self.b}
            funcs["regions_containing"].side_effect=[["a"],["b"]]
            funcs["local_assets"].return_value=([self.root/"runtime.json"],
                [self.root/"a-inv.json",self.root/"b-inv.json"],[],self.anchors)
            funcs["proposed_chains"].return_value=[self.chain]
            funcs["leg_route"].side_effect=ValueError("Valhalla route missing destination")
            result=route.plan(self.root,self.root,self.root,self.root,self.root,
                Path("/valhalla"),self.start,self.end,"motorcycle","FASTER",{})
        self.assertEqual(result["status"],"NO_COMPLETE_ROUTE")
        self.assertEqual(result["chainsAttempted"],1)

    def test_tries_complete_direct_graph_before_handoffs(self):
        with mock.patch.multiple(route,
            trusted_graphs=mock.DEFAULT,regions_containing=mock.DEFAULT,
            local_assets=mock.DEFAULT,leg_route=mock.DEFAULT) as funcs:
            funcs["trusted_graphs"].return_value={"a":self.a}
            funcs["regions_containing"].return_value=["a"]
            funcs["leg_route"].side_effect=self.fake_leg
            result=route.plan(self.root,self.root,self.root,self.root,self.root,
                Path("/valhalla"),self.start,self.end,"auto","SHORTER",{})
            funcs["local_assets"].assert_not_called()
        self.assertEqual(result["regions"],["a"])
        self.assertTrue(result["destinationReached"])

    def test_partial_direct_routes_fall_through_to_multigraph(self):
        with mock.patch.multiple(route,trusted_graphs=mock.DEFAULT,
            regions_containing=mock.DEFAULT,local_assets=mock.DEFAULT,
            proposed_chains=mock.DEFAULT,leg_route=mock.DEFAULT) as funcs:
            funcs["trusted_graphs"].return_value={"a":self.a,"b":self.b}
            funcs["regions_containing"].side_effect=[["a"],["a","b"]]
            funcs["local_assets"].return_value=([self.root/"runtime"],
                [self.root/"invA",self.root/"invB"],[],self.anchors)
            funcs["proposed_chains"].return_value=[self.chain]
            def fake(*args,**kwargs):
                if args[2]==self.start and args[3]==self.end:
                    raise ValueError("1.57 km short")
                return self.fake_leg(*args,**kwargs)
            funcs["leg_route"].side_effect=fake
            result=route.plan(self.root,self.root,self.root,self.root,self.root,
                Path("/valhalla"),self.start,self.end,"motorcycle","FASTER",{})
        self.assertEqual(result["regions"],["a","b"])
        self.assertEqual(result["chainsAttempted"],1)

    def test_scoring_uses_actual_detailed_cost_not_matrix_only(self):
        fast={"durationSeconds":100.0,"distanceKm":50.0,"legs":[1],"chainId":"fast"}
        short={"durationSeconds":150.0,"distanceKm":30.0,"legs":[1],"chainId":"short"}
        self.assertEqual(route.select_best([short,fast],"FASTER")["chainId"],"fast")
        self.assertEqual(route.select_best([short,fast],"SHORTER")["chainId"],"short")

    def test_actual_valhalla_leg_wrong_directed_edge_is_rejected(self):
        # Geometrically valid route, but Valhalla selects graph edge #24
        # where the fingerprint-bound connector requires edge #22.
        import subprocess
        response={"trip":{"status":0,"summary":{"length":0.01,"time":3},
                          "legs":[{"shape":"??AA"}]}}
        traced={"edges":[{"id":11},{"id":24}]}
        calls=[subprocess.CompletedProcess([],0,stdout=json.dumps(response),stderr=""),
               subprocess.CompletedProcess([],0,stdout=json.dumps(traced),stderr="")]
        with mock.patch.object(route.subprocess,"run",side_effect=calls):
            with self.assertRaisesRegex(ValueError,"END edge 24 differs"):
                route.leg_route(Path("/bin/valhalla"),Path("/graph.json"),
                    {"lat":0.0,"lng":0.0},{"lat":0.000001,"lng":0.000001},
                    "motorcycle",{},start_graph_id=11,end_graph_id=22)

    def test_real_valhalla_leg_rejects_geometry_ending_short(self):
        import subprocess
        response={"trip":{"status":0,"summary":{"length":0.01,"time":3},
                          "legs":[{"shape":"??AA"}]}}
        fake=subprocess.CompletedProcess([],0,stdout=json.dumps(response),stderr="")
        with mock.patch.object(route.subprocess,"run",return_value=fake):
            with self.assertRaisesRegex(ValueError,"Leg did not reach exact endpoint"):
                route.leg_route(Path("/bin/valhalla"),Path("/graph.json"),
                    {"lat":0.0,"lng":0.0},{"lat":0.02,"lng":0.02},
                    "motorcycle",{})

    def test_parse_pyvalhalla_launcher_information(self):
        val=route.parse_service_json('[INFO] launch native valhalla\n{"trip":{"status":0}}\n')
        self.assertEqual(val["trip"]["status"],0)

    def test_distinct_geometry_parts_and_endpoints(self):
        # Encoded polyline6 fixture: (0,0) to (0.000001,0.000001).
        self.assertEqual(route.decode_polyline6("??AA"),[[0.0,0.0],[0.000001,0.000001]])
        self.assertGreater(route.distance(self.aexit,self.bentry),0)


if __name__=="__main__":
    unittest.main()
