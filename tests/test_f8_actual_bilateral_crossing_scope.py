"""F8 coverage regression: count only genuine bilateral outward road candidates.

No native intersection branching, name/way grouping, or broad-source graph walk.
The physical A-cut eligibility is a candidate inventory only; ORIGINAL A-last,
B-first TripLeg identities are separate fail-closed validation gates.
"""
import sys
import unittest
from pathlib import Path
from shapely.geometry import box
from shapely.prepared import prep
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from audit_f8_actual_bilateral_crossings import in_scope,classification
from reconcile_f8_only_real_outward_missing_crossings import positive_receiver_proof

def original(gid=100, direction="OUTWARD_FROM_ORIGINAL_SOURCE_BUFFER",
             road=True, shortcut=False, auto=True, moto=True):
    return {
        "originalDirectedGraphId":gid,
        "originalWayIdAnnotationOnly":450,
        "originalSourceBufferCutDirectedTravel":direction,
        "nativeIsRoad":road,"nativeIsShortcut":shortcut,
        "vehicleModes":{"auto":auto,"motorcycle":moto}
    }

def receive_proof(verified, graphid=900):
    return {"auto":{
        "verified":verified,
        "actualFirstDirectedGraphId":graphid,
        "originalTripLegDirectedGraphIds":[graphid] if verified else [],
        "status":"SUCCEEDED" if verified else "FAILED",
        "startSnapMeters":0.0 if verified else None,
        "endSnapMeters":0.0 if verified else None}}

class ActualBilateralCrossingAuditTests(unittest.TestCase):
    def setUp(self):
        self.core=prep(box(11,46,12,48))

    def test_only_outward_true_road_is_in_source_scope(self):
        self.assertTrue(in_scope(original()))
        self.assertFalse(in_scope(original(direction="INWARD_TOWARD_ORIGINAL_SOURCE_BUFFER")))
        self.assertFalse(in_scope(original(road=False)))
        self.assertFalse(in_scope(original(shortcut=True)))
        self.assertFalse(in_scope(original(auto=False,moto=False)))
        self.assertTrue(in_scope(original(auto=False,moto=True)))

    def test_road_exiting_other_country_cannot_be_missing_peer_crossing(self):
        # A valid outward original source directed road, but it never touches B.
        a=classification(original(),[[45.1,10.0],[45.2,10.2]],self.core,{}, {})
        self.assertIsNone(a)

    def test_receiver_core_geometry_not_way_name_is_bilateral_filter(self):
        out=classification(original(),[[47.0,10.5],[47.0,11.5]],self.core,
                           {},{100:{"status":"NO_VALHALLA_VERIFIED_FORWARD_RECEIVING_ROAD"}})
        self.assertEqual(out["status"],"ORIGINAL_SOURCE_CUT_GRAPHID_PREVIOUSLY_UNRESOLVED")
        self.assertEqual(out["originalOutwardSourceCutDirectedGraphId"],100)
        self.assertEqual(out["nativeOriginalSourceLastTripLeg"],"NOT_PROVED_BY_CUT_GEOMETRY")
        self.assertEqual(out["originalReceivingFirstTripLeg"],"NOT_PROVED_BY_CUT_GEOMETRY")

    def test_proved_original_source_and_receiver_are_not_recounted_missing(self):
        opt={"receiverFirstDirectedGraphId":900}
        item=classification(original(),[[47.0,10.5],[47.0,11.5]],self.core,
                            {100:{"receiverOptions":[opt]}},{})
        self.assertEqual(item["status"],
            "EXACT_ORIGINAL_FINAL_SOURCE_GRAPHID_HAS_VALHALLA_B_PEER")
        self.assertEqual(item["verifiedReceiverOriginalDirectedOptions"],[900])

    def test_reverse_direction_candidate_preserves_both_modes(self):
        out=classification(original(101,auto=False,moto=True),
                [[47.0,10.5],[47.0,11.5]],self.core,{}, {})
        self.assertFalse(out["carMode"])
        self.assertTrue(out["motorcycleMode"])

    def test_receiver_geometry_not_legally_forward_is_rejected(self):
        from shapely.geometry import LineString
        source={"directedGeometry":[[47.0,11.0],[47.01,11.01]],"wayId":1}
        receiving={"directedGeometry":[[47.01,11.01],[47.0,11.0]],"wayId":2}
        self.assertIsNone(positive_receiver_proof(receiving,source,
            {"lat":47.01,"lng":11.01},900,Path('/tmp/graph'),
            Path('/tmp/route'),{'auto'}))

    def test_b_first_mode_cannot_be_created_from_failed_route(self):
        # A physically forward match alone is not enough for Android.
        source={"directedGeometry":[[47.0,11.0],[47.001,11.001]],"wayId":1}
        receiving={"directedGeometry":[[47.001,11.001],[47.002,11.002]],"wayId":2}
        with patch("reconcile_f8_only_real_outward_missing_crossings.prove_receiver_modes",
                   return_value=receive_proof(False)):
            result=positive_receiver_proof(receiving,source,
                {"lat":47.001,"lng":11.001},900,Path('/tmp/graph'),
                Path('/tmp/route'),{'auto'})
        self.assertIsNone(result)

if __name__=='__main__':
    unittest.main()
