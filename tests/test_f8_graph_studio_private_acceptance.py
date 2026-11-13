"""Owner-only Graph Studio readiness is native-audited, NOT Android-gated.

RoadPilot consumer READY remains a separate future release contract.
"""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from build_f8_native_auto_catalog import build
from preflight_f8_approved_directed_catalog import reconcile
from test_f8_approved_production_preflight import fixtures, HASH_A, HASH_B


class GraphStudioPrivateAcceptanceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads((ROOT / "schemas" /
            "f8-graph-studio-native-private-catalog.schema.json").read_text())
        Draft202012Validator.check_schema(cls.schema)
        cls.validator = Draft202012Validator(cls.schema)

    def preflight(self, android_status="NOT_VERIFIED"):
        c, d, a = fixtures()
        d["androidProductionUIAcceptance"] = android_status
        return reconcile(c, d, a,
                         native_evidence_sha=HASH_A,
                         archive_from_sha=HASH_A,
                         archive_to_sha=HASH_B)

    def test_actual_native_preflight_no_longer_reads_android_acceptance(self):
        baseline = self.preflight(android_status="NOT_VERIFIED")
        for status in ("PASSED", "FAILED", "NOT_RUN", "UNKNOWN"):
            with self.subTest(android_status=status):
                self.assertEqual(baseline, self.preflight(status))
        self.assertEqual(baseline["graphStudioNativeCoverageScope"],
                         "VERIFIED_WITHIN_ORIGINAL_PAIR_ENDPOINT_DOMAIN")
        self.assertTrue(baseline["graphStudioPrivateTestingReady"])
        self.assertFalse(any("ANDROID" in k or "APK" in k
                             for k in baseline["blockingEvidence"]))

    def test_native_pass_generates_private_ready_without_android_or_owner_release(self):
        output = build(self.preflight(), HASH_A, graph_studio_private_ready=True)
        self.validator.validate(output)
        self.assertEqual("GRAPH_STUDIO_PRIVATE_READY", output["publication"])
        self.assertEqual("OWNER_ONLY_GRAPH_STUDIO_TESTING", output["intendedUse"])
        self.assertTrue(output["notForRoadPilotRuntime"])
        self.assertEqual(2, output["counts"]["sourceConnections"])
        self.assertEqual(2, output["counts"]["receiverIncomingRoads"])
        self.assertEqual("NOT_VERIFIED", output["sourcePhysicalRoadDirectionCompleteness"])
        self.assertEqual(2, output["unverifiedSourcePhysicalRoadLineages"])
        self.assertNotIn("approval", output)
        self.assertNotIn("producerEvidence", output)
        self.assertNotIn("android", json.dumps(output).lower())
        self.assertNotIn("signed", json.dumps(output).lower())
        default = build(self.preflight(), HASH_A)
        self.assertEqual("BLOCKED_TEST_ONLY", default["publication"])
        self.assertNotEqual(output["schema"], default["schema"])

    def test_private_ready_fails_closed_if_native_scope_missing_or_unproved(self):
        original = self.preflight()
        for key,value in (("graphStudioPrivateTestingReady", False),
                          ("graphStudioNativeCoverageScope", "INCOMPLETE")):
            changed = dict(original, **{key:value})
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "private acceptance proof"):
                build(changed, HASH_A, graph_studio_private_ready=True)
        for bad in ("", "sha256:"+"f"*63, "sha256:"+"z"*64):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                build(original, bad, graph_studio_private_ready=True)

    def test_private_ready_never_omits_b_road_or_escalates_mode(self):
        original = self.preflight()
        for mutate in (
            lambda r: r["nativeDirectedApproachesForReviewOnly"].pop(),
            lambda r: r["nativeDirectedApproachesForReviewOnly"][0]["receiverDirectedRoadsAtX"].clear(),
            lambda r: r["nativeDirectedApproachesForReviewOnly"][1]["receiverDirectedRoadsAtX"][0].update(
                {"travelModes":["car","motorcycle"]}),
        ):
            r = copy.deepcopy(original)
            mutate(r)
            with self.assertRaises(ValueError):
                build(r, HASH_A, graph_studio_private_ready=True)

    def test_short_edges_and_distinct_b_branches_preserved_in_private_wire(self):
        r = self.preflight()
        first = r["nativeDirectedApproachesForReviewOnly"][0]
        one = first["receiverDirectedRoadsAtX"][0]
        one["directedApproachOverlapMeters"] = .933
        one["nativeXGapMeters"] = .045
        two = dict(one, receiverDirectedGraphId=999)
        first["receiverDirectedRoadsAtX"].append(two)
        r["counts"]["nativeDirectedBIncomingPhysicalRoadMatches"] += 1
        output = build(r, HASH_A, graph_studio_private_ready=True)
        self.validator.validate(output)
        self.assertEqual(2, output["counts"]["sourceConnections"])
        self.assertEqual(3, output["counts"]["receiverIncomingRoads"])
        self.assertEqual([202, 999], [b["receiverDirectedGraphId"] for b in
                         output["connections"][0]["receiverDirectedRoadsAtX"]])
        corrupt = copy.deepcopy(output)
        corrupt["connections"][0]["receiverDirectedRoadsAtX"][0]["nativeXGapMeters"] = .15
        self.assertFalse(self.validator.is_valid(corrupt))
        corrupt = copy.deepcopy(output)
        corrupt["publication"] = "READY"
        self.assertFalse(self.validator.is_valid(corrupt))
        corrupt = copy.deepcopy(output)
        corrupt["notForRoadPilotRuntime"] = False
        self.assertFalse(self.validator.is_valid(corrupt))
        corrupt = copy.deepcopy(output)
        corrupt["sourcePhysicalRoadDirectionCompleteness"] = "VERIFIED"
        self.assertFalse(self.validator.is_valid(corrupt))


if __name__ == "__main__":
    unittest.main()
