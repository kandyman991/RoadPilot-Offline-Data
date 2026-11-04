"""Actual original A-last/B-first GraphIds must appear in full independent
GraphStudio directed source scans; no road name/OSM way collapse or ID matching."""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from audit_native_f8_original_receiver_source_coverage import original_receiver_source_coverage


def valid():
    pair={"pairId":"italy-nord-est__austria",
          "fromGraphFingerprint":"sha256:"+"a"*64,
          "toGraphFingerprint":"sha256:"+"b"*64}
    point={"lat":47.2338644,"lng":11.392306}
    item={"direction":"from-to","mode":"auto",
          "sourceFinalDirectedGraphId":101,
          "originalSourceLastGraphId":101,
          "originalReceivingFirstGraphId":201,
          "bFirstGraphIdIdentifiedFromOriginalTripLeg":True,
          "originalGraphIdsNeverComparedAcrossRegions":True,
          "originalALeg":{"lastDirectedGraphId":101,"endActual":point,
             "edgeIdOrigin":"ORIGINAL_TRIPLEG_NODE_EDGE_PROTOBUF"},
          "originalBLeg":{"firstDirectedGraphId":201,
             "edgeIdOrigin":"ORIGINAL_TRIPLEG_NODE_EDGE_PROTOBUF"}}
    report={"schema":"roadpilot.f8-original-core-directed-branch-journey",
            "version":1,"productionPublication":"BLOCKED",
            "globallyUniqueFinalPhysicalRoadPerDirection":"NOT_VERIFIED",
            "pairId":pair["pairId"],
            "fromGraphFingerprint":pair["fromGraphFingerprint"],
            "toGraphFingerprint":pair["toGraphFingerprint"],
            "cases":[item]}
    a={"edges":[{"graphId":101,"forwardAccess":1025,
                 "lat":point["lat"],"lon":point["lng"],"wayId":1}]}
    b={"edges":[{"graphId":201,"forwardAccess":1025,
                 "lat":point["lat"],"lon":point["lng"],"wayId":2}]}
    return pair,report,a,b


class OriginalReceiverNativeSourceCoverageTests(unittest.TestCase):
    @staticmethod
    def checked(p,r,a,b):
        with patch("audit_native_f8_original_receiver_source_coverage.pair_identity"):
            return original_receiver_source_coverage(p,r,a,b)

    def test_real_original_receiver_id_present_independent_of_way_name_and_graphids(self):
        p,r,a,b=valid()
        result=self.checked(p,r,a,b)
        self.assertEqual(result["counts"]["originalAEdgePresentAndBReceiverGpsMatched"],1)
        self.assertEqual(result["counts"]["originalReceiverFirstPresentInBFullScan"],1)
        self.assertEqual(result["proofScope"],"SCOPED_ORIGINAL_TRIPLEG_DIRECTED_GPS_IDENTITIES_ONLY")
        self.assertEqual(result["realAndroidJNIParity"],"NOT_VERIFIED")
        self.assertEqual(result["productionPublication"],"BLOCKED")
        self.assertEqual(result["caseDetails"][0]["sourceAndReceiverRoadNameOrWayComparison"],"NONE")
        # A complete F8 native edge sample may be interior and nowhere near
        # the actual A final directed edge endpoint X: identity is the original
        # source GraphId, not a false 1m distance rule on its sample point.
        a["edges"][0]["lat"] += .00144  # ~160m away from X, same native GraphId.
        observed = self.checked(p,r,a,b)
        self.assertEqual(observed["counts"]["originalAEdgePresentAndBReceiverGpsMatched"],1)
        self.assertGreater(observed["caseDetails"][0][
            "sourceOriginalScannerGpsToTerminalMetersAnnotationOnly"],100)
        # Coincident numeric IDs on two independent graphs are legal and never
        # treated as a match or conflict: only region-local capture membership.
        r["cases"][0]["originalReceivingFirstGraphId"]=101
        r["cases"][0]["originalBLeg"]["firstDirectedGraphId"]=101
        b["edges"][0]["graphId"]=101
        independent=self.checked(p,r,a,b)
        self.assertEqual(independent["counts"]["originalAEdgePresentAndBReceiverGpsMatched"],1)

    def test_missing_real_receiver_original_graphid_is_reported_not_suppressed(self):
        p,r,a,b=valid()
        b["edges"][0]["graphId"]=202
        result=self.checked(p,r,a,b)
        self.assertEqual(result["counts"]["originalRouteAndNativeCandidateScannerGaps"],1)
        self.assertFalse(result["caseDetails"][0]["receiverFirstPresentInNativeOriginalScan"])
        self.assertEqual(result["originalValhallaReceiverIdentitiesInNativeGraphStudioScans"],
                         "SCOPED_NATIVE_A_EDGE_OR_RECEIVER_B_GAPS_PRESENT")

    def test_wrong_mode_mask_or_gps_distance_cannot_be_silently_counted_as_parity(self):
        p,r,a,b=valid()
        b["edges"][0]["forwardAccess"]=1
        r["cases"][0]["mode"]="motorcycle"
        self.assertFalse(self.checked(p,r,a,b)["caseDetails"][0][
            "originalAEdgeIdAndReceivingBFirstGpsMatched"])
        b["edges"][0]["forwardAccess"]=1025
        b["edges"][0]["lat"]+=.01
        self.assertEqual(self.checked(p,r,a,b)["counts"][
            "originalRouteAndNativeCandidateScannerGaps"],1)

    def test_original_tripleg_spoof_or_duplicate_native_ids_abort(self):
        p,r,a,b=valid()
        r["cases"][0]["originalBLeg"]["firstDirectedGraphId"]=999
        with self.assertRaisesRegex(ValueError,"TripLeg"):
            self.checked(p,r,a,b)
        p,r,a,b=valid()
        b["edges"].append(copy.deepcopy(b["edges"][0]))
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            self.checked(p,r,a,b)

    def test_falsely_globally_proven_or_stale_graph_is_rejected(self):
        p,r,a,b=valid()
        r["globallyUniqueFinalPhysicalRoadPerDirection"]="VERIFIED"
        with self.assertRaisesRegex(ValueError,"falsely complete"):
            self.checked(p,r,a,b)
        p,r,a,b=valid()
        r["toGraphFingerprint"]="sha256:"+"z"*64
        with self.assertRaisesRegex(ValueError,"falsely complete"):
            self.checked(p,r,a,b)


if __name__=="__main__":
    unittest.main()
