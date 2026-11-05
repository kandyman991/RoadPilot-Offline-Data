"""Behavior gates for the production A-final -> B-directed edge matcher.

Check the real failure: a B route can legally U-turn on A's last road,
but that is NOT forward physical continuation. Retain independent forks.
"""
import sys
from pathlib import Path
from unittest import TestCase, mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from build_f8_final_edge_connections import (
    directed_line, physical_forward_continuation, pair_connections,
    SCHEMA, MODES,
)


def edge(gid, coords, way=1):
    return {"sourceGraphId":gid,"directedGeometry":coords,
            "wayId":way,"forwardAccess":1257}


class F8FinalDirectedConnectionTest(TestCase):
    def setUp(self):
        self.a=edge(101,[[47.232463,11.392792],[47.233864,11.392306]],7)
        self.b=edge(909,[[47.233864,11.392306],[47.237243,11.391179]],8)
        self.reverse=edge(808,[[47.233864,11.392306],[47.232463,11.392792]],7)

    def test_forward_physical_continuation_different_osm_way_is_eligible(self):
        m=physical_forward_continuation(directed_line(self.a),directed_line(self.b))
        self.assertEqual(m["status"],"FORWARD_CONTINUOUS")
        self.assertLess(m["seamGapMeters"],.1)
        self.assertGreater(m["directionCosine"],.9)

    def test_true_original_route_reverse_is_not_a_physical_forward_connection(self):
        m=physical_forward_continuation(directed_line(self.a),
                                         directed_line(self.reverse))
        self.assertEqual(m["status"],"REVERSE_OR_AMBIGUOUS_PHYSICAL_DIRECTION")
        self.assertLess(m["directionCosine"],-.9)

    def test_graphid_edge_not_deduped_by_coordinate_way_or_vehicle_modes(self):
        other=edge(919,[[47.233864,11.392306],[47.236000,11.392700]],7)
        scanner={"edges":[
            {"lat":47.233864,"lon":11.392306,"graphId":909},
            {"lat":47.233864,"lon":11.392306,"graphId":919},
            {"lat":47.233864,"lon":11.392306,"graphId":808},
        ]}
        def prove(cfg, binary, position, target, gid, source_modes):
            self.assertEqual(source_modes,{"auto","motorcycle"})
            return {mode:{"verified":True,"status":"SUCCEEDED",
                          "actualFirstDirectedGraphId":gid}
                    for mode in sorted(source_modes)}
        with mock.patch(
            "build_f8_final_edge_connections.prove_receiver_modes",
            side_effect=prove,
        ):
            ok,unknown,stats=pair_connections(
                {101:self.a},{909:self.b,919:other,808:self.reverse},
                scanner,{101:{"auto","motorcycle"}},Path("not-needed.json"),
                Path("not-needed-route"),"austria","italy-nord-est",
                "sha256:"+"b"*64)
        self.assertEqual(len(ok),1)
        self.assertFalse(unknown)
        self.assertEqual(ok[0]["sourceFinalDirectedGraphId"],101)
        ids=[x["receiverFirstDirectedGraphId"] for x in ok[0]["receiverOptions"]]
        self.assertEqual(set(ids),{909,919})
        # A valid B branch must not hide another unresolved/reverse candidate.
        self.assertEqual(ok[0]["unverifiedReceiverCandidateGraphIds"],[808])
        self.assertEqual(ok[0]["receiverAnchorCandidatesInspected"],3)
        self.assertFalse(ok[0]["receiverCandidateCensusComplete"])
        self.assertEqual(stats["sourceWithBothModesVerifiedOnSamePeer"],1)

    def test_no_forward_edge_never_creates_fabricated_connection(self):
        scanner={"edges":[{"lat":47.233864,"lon":11.392306,"graphId":808}]}
        ok,not_ok,_=pair_connections(
            {101:self.a},{808:self.reverse},scanner,
            {101:{"auto","motorcycle"}},Path("not-needed"),
            Path("not-needed"),"austria","italy-nord-est","sha256:"+"a"*64)
        self.assertEqual(ok,[])
        self.assertEqual(not_ok[0]["sourceFinalDirectedGraphId"],101)
        self.assertEqual(not_ok[0]["status"],"NO_VALHALLA_VERIFIED_FORWARD_RECEIVING_ROAD")
        self.assertEqual(not_ok[0]["unverifiedReceiverCandidateGraphIds"],[808])

    def test_car_and_motorcycle_cannot_be_counted_as_two_source_final_roads(self):
        scanner={"edges":[{"lat":47.233864,"lon":11.392306,"graphId":909}]}
        def prove(cfg, binary, position, target, gid, source_modes):
            return {m:{"verified":m=="auto"} for m in source_modes}
        with mock.patch("build_f8_final_edge_connections.prove_receiver_modes",
                        side_effect=prove):
            ok,unresolved,_=pair_connections(
                {101:self.a},{909:self.b},scanner,{101:{"auto","motorcycle"}},
                Path("not-needed"),Path("not-needed"),
                "austria","italy-nord-est","sha256:"+"a"*64)
        self.assertEqual(len(ok),1)
        self.assertEqual(len(ok[0]["receiverOptions"]),1)
        self.assertEqual(ok[0]["receiverOptions"][0]["travelModes"],["auto"])
        self.assertEqual(unresolved,[])
