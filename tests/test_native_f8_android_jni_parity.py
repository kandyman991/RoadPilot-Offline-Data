"""Android raw JNI cap + receiverRoadKey grouping are not F8 graph parity."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from test_native_f8_pair_evidence import identity,scan,edge
from audit_native_f8_android_jni_parity import audit, inspect_window, MAX_JNI_RESULTS


def example_capture(pair, ids, grouped=None, *, direction="from-to", n=4096):
    side="to" if direction=="from-to" else "from"
    return {
        "schema":"roadpilot.android-actual-f8-jni-scan-capture",
        "version":1,
        "regionId":pair[side+"RegionId"],
        "graphFingerprint":pair[side+"GraphFingerprint"],
        "boundaryFingerprint":pair[side+"BoundaryFingerprint"],
        "direction":direction,
        "captureSource":"SELF_REPORTED_ACTUAL_ANDROID_JNI",
        "androidBuildCommit":"0"*40,
        "device":"self-reported-android",
        "windows":[{
            "bounds":{"minLat":46.0,"maxLat":46.1,
                      "minLon":12.0,"maxLon":12.1},
            "requestedMaxResults":n,
            "returned":len(ids),
            "rawGraphIds":ids,
            "afterKotlinRoadKeyGroupingGraphIds":ids if grouped is None else grouped,
        }],
    }


class JNIParityTests(unittest.TestCase):
    def setUp(self):
        self.pair=identity()
        self.native=scan([
            edge(1001,5000,46.01,12.01),
            edge(1002,5000,46.02,12.02),
            edge(1003,5001,46.03,12.03),
        ])

    def test_matching_scoped_window_still_requires_authenticated_device_provenance(self):
        result=audit(self.pair,self.native,
                     example_capture(self.pair,[1001,1002,1003]),"from-to")
        self.assertEqual(result["scopedWindowsExamined"],1)
        self.assertTrue(result["exactOriginalWindowCatalogMatches"])
        self.assertEqual(result["lossCounters"]["nativeDirectedIdsNotReturnedByJNI"],0)
        self.assertEqual(result["lossCounters"]["receiverRoadKeyLostDistinctEdges"],0)
        self.assertEqual(result["lossCounters"]["losslessScopedWindows"],1)
        self.assertEqual(result["f8GraphEdgeParity"],"NOT_VERIFIED")
        self.assertEqual(result["productionPublication"],"BLOCKED")
        self.assertIn("NOT_VERIFIED_REQUIRES_INDEPENDENT_ON_DEVICE",
                      result["actualAndroidDeviceEvidenceAuthentication"])

    def test_kotlin_road_key_grouping_drops_distinct_same_way_directions(self):
        jni=example_capture(self.pair,[1001,1002,1003],grouped=[1001,1003])
        result=audit(self.pair,self.native,jni,"from-to")
        self.assertEqual(result["lossCounters"]["receiverRoadKeyLostDistinctEdges"],1)
        self.assertEqual(result["perWindow"][0]["receiverRoadKeyGroupedAwayGraphIds"],[1002])
        self.assertFalse(result["perWindow"][0]["allDirectedAlternativesPreservedThroughKotlin"])
        self.assertEqual(result["f8GraphEdgeParity"],"NOT_VERIFIED")

    def test_android_hard_512_jni_cap_suppresses_native_edges(self):
        edges=[
            edge(10000+i,5000+i%3,46.001+i*.0001,12.03)
            for i in range(MAX_JNI_RESULTS+3)
        ]
        native=scan(edges)
        ids=[r["graphId"] for r in edges[:MAX_JNI_RESULTS]]
        captured=example_capture(self.pair,ids,n=4096)
        j=audit(self.pair,native,captured,"from-to")
        self.assertEqual(j["lossCounters"]["jniSaturatedWindows"],1)
        self.assertEqual(j["lossCounters"]["nativeDirectedIdsNotReturnedByJNI"],3)
        self.assertEqual(j["perWindow"][0]["nativeDirectedIdsMissingFromJNI"],
                         [10000+MAX_JNI_RESULTS+i for i in range(3)])
        self.assertEqual(j["f8GraphEdgeParity"],"NOT_VERIFIED")
        self.assertEqual(j["perWindow"][0]["actualJNIHardCap"],512)

    def test_unknown_or_duplicate_android_graph_ids_fail_closed(self):
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            inspect_window(self.native["edges"],example_capture(
                self.pair,[1001,1001])["windows"][0])
        wrong=example_capture(self.pair,[55555])
        report=audit(self.pair,self.native,wrong,"from-to")
        self.assertEqual(report["lossCounters"]["androidEmittedIdsAbsentFromNative"],1)
        self.assertEqual(report["f8GraphEdgeParity"],"NOT_VERIFIED")

    def test_stale_graph_fingerprint_rejected_before_any_comparison(self):
        jni=example_capture(self.pair,[1001])
        jni["graphFingerprint"]="sha256:"+"f"*64
        with self.assertRaisesRegex(ValueError,"fingerprints mismatch"):
            audit(self.pair,self.native,jni,"from-to")

    def test_window_catalog_gap_remains_unverified(self):
        one=example_capture(self.pair,[1001,1002,1003])
        one["windows"][0]["bounds"]["minLat"]=46.001
        result=audit(self.pair,self.native,one,"from-to")
        self.assertFalse(result["exactOriginalWindowCatalogMatches"])
        self.assertEqual(result["f8GraphEdgeParity"],"NOT_VERIFIED")

    def test_wrong_direction_and_post_kotlin_forgery_cannot_validate(self):
        jni=example_capture(self.pair,[1001,1002,1003],direction="from-to")
        with self.assertRaisesRegex(ValueError,"fingerprints mismatch"):
            audit(self.pair,self.native,jni,"to-from")
        jni["windows"][0]["afterKotlinRoadKeyGroupingGraphIds"]=[99999]
        with self.assertRaisesRegex(ValueError,"Malformed Android Kotlin"):
            audit(self.pair,self.native,jni,"from-to")


if __name__=="__main__":
    unittest.main()
