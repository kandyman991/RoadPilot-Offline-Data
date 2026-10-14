"""Synthetic evidence-tier tests for the read-only native F8 coverage auditor."""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from audit_f8_graph_edge_parity import audit


PAIR = "italy-nord-est__geofabrik-austria"
GRAPH_A = "sha256:graph-a"
GRAPH_B = "sha256:graph-b"


def identity() -> dict:
    return {
        "pairId": PAIR,
        "fromGraph": {"graphFingerprint": GRAPH_A},
        "toGraph": {"graphFingerprint": GRAPH_B},
        "fromBoundaryFingerprint": "sha256:boundary-a",
        "toBoundaryFingerprint": "sha256:boundary-b",
    }


def fixtures():
    base = identity()
    reference = {
        **base,
        "schema": "roadpilot.native-f8-edge-scan",
        "version": 1,
        "scanner": "GraphEndpointNative.scanBoundaryRoadEdges",
        "scans": {
            side: {
                "complete": True,
                "windows": [{"complete": True, "truncated": False, "maxResults": 4096,
                             "returned": 2}],
                "edges": [{"graphId": value, "wayId": 55, "roadNames": ["A12"]} for value in values]
            }
            for side, values in (("from", [101, 102]), ("to", [201, 202]))
        },
        "provenHandoffs": [
            {"fromGraphId": 101, "toGraphId": 201, "mode": "motorcycle",
             "direction": "from-to"},
            {"fromGraphId": 102, "toGraphId": 202, "mode": "motorcycle",
             "direction": "from-to"},
        ],
    }
    correlations = {
        **base, "schema": "roadpilot.frontier-road-correlations",
        "correlations": [
            {"frontierRoadId": f"road-{i}", "fromGraph":
             {"candidates": [{"graphId": 100 + i}]},
             "toGraph": {"candidates": [{"graphId": 200 + i}]}}
            for i in (1, 2)
        ],
    }
    candidates = {
        **base, "schema": "roadpilot.crossing-candidates",
        "candidates": [
            {"fromEdge": {"graphId": 101}, "toEdge": {"graphId": 201}},
            {"fromEdge": {"graphId": 102}, "toEdge": {"graphId": 202}},
        ],
    }
    return reference, correlations, candidates


class F8GraphEdgeAuditTests(unittest.TestCase):
    def test_two_distinct_directed_edges_on_same_named_way_are_preserved(self):
        report = audit(*fixtures())
        self.assertEqual(report["scanStatus"], "OBSERVED_WINDOWS_COMPARED")
        self.assertEqual(report["f8GraphEdgeParity"], "NOT_VERIFIED")
        self.assertEqual(report["sides"]["to"]["nativeDistinctDirectedEdges"], 2)
        self.assertEqual(report["nativeProvenHandoffsMissingFromCandidates"], [])

    def test_second_successful_alternative_missing_is_not_hidden_by_first(self):
        reference, correlations, candidates = fixtures()
        del candidates["candidates"][1]
        report = audit(reference, correlations, candidates)
        self.assertEqual(report["scanStatus"], "INCOMPLETE")
        self.assertEqual(report["sides"]["from"]["nativeEdgesMissingFromCandidates"], ["102"])
        self.assertEqual(report["sides"]["to"]["nativeEdgesMissingFromCandidates"], ["202"])
        self.assertEqual(report["nativeProvenHandoffsMissingFromCandidates"][0]["toGraphId"], "202")

    def test_native_edge_not_generated_by_osm_seed_is_reported(self):
        reference, correlations, candidates = fixtures()
        correlations["correlations"].pop()
        candidates["candidates"].pop()
        report = audit(reference, correlations, candidates)
        self.assertEqual(report["sides"]["to"]["nativeEdgesMissingFromCorrelations"], ["202"])
        self.assertEqual(report["f8GraphEdgeParity"], "NOT_VERIFIED")

    def test_same_way_different_graph_id_is_not_counted_as_equivalent(self):
        reference, correlations, candidates = fixtures()
        candidates["candidates"][1]["toEdge"]["graphId"] = 203
        report = audit(reference, correlations, candidates)
        self.assertEqual(report["sides"]["to"]["nativeEdgesMissingFromCandidates"], ["202"])

    def test_graph_identity_mismatch_hard_fails(self):
        reference, correlations, candidates = fixtures()
        reference["toGraph"] = {"graphFingerprint": "sha256:other"}
        with self.assertRaisesRegex(ValueError, "fingerprints or pair identity"):
            audit(reference, correlations, candidates)

    def test_boundary_mismatch_hard_fails(self):
        reference, correlations, candidates = fixtures()
        candidates["fromBoundaryFingerprint"] = "sha256:stale"
        with self.assertRaisesRegex(ValueError, "fingerprints or pair identity"):
            audit(reference, correlations, candidates)

    def test_truncated_or_failed_native_window_cannot_establish_completeness(self):
        for change in ({"truncated": True}, {"returned": 4096}, {"complete": False}):
            reference, correlations, candidates = fixtures()
            reference["scans"]["from"]["windows"][0].update(change)
            report = audit(reference, correlations, candidates)
            self.assertEqual(report["scanStatus"], "INCOMPLETE")
            self.assertEqual(report["f8GraphEdgeParity"], "NOT_VERIFIED")


    def test_native_jni_512_hard_cap_even_when_4096_requested(self):
        reference, correlations, candidates = fixtures()
        window = reference["scans"]["from"]["windows"][0]
        window["maxResults"] = 4096
        window["returned"] = 512
        window["complete"] = True
        window["truncated"] = False
        report = audit(reference, correlations, candidates)
        self.assertEqual(report["scanStatus"], "INCOMPLETE")
        self.assertEqual(report["nativeScannerHardCapPerWindow"], 512)
        self.assertTrue(any("actualNativeCap=512" in item
                            for item in report["incompleteReasons"]))

    def test_native_requested_cap_less_than_512_must_also_detect_saturation(self):
        reference, correlations, candidates = fixtures()
        window = reference["scans"]["to"]["windows"][0]
        window["maxResults"] = 2
        window["returned"] = 2
        report = audit(reference, correlations, candidates)
        self.assertEqual(report["scanStatus"], "INCOMPLETE")

    def test_reject_unsupported_claim_of_more_than_512_native_results(self):
        reference, correlations, candidates = fixtures()
        window = reference["scans"]["from"]["windows"][0]
        window["returned"] = 513
        report = audit(reference, correlations, candidates)
        self.assertEqual(report["scanStatus"], "INCOMPLETE")
        self.assertTrue(any("invalid returned count" in item
                            for item in report["incompleteReasons"]))

    def test_empty_native_scan_cannot_prove_parity(self):
        reference, correlations, candidates = fixtures()
        reference["scans"]["from"]["windows"] = []
        reference["provenHandoffs"] = []
        report = audit(reference, correlations, candidates)
        self.assertEqual(report["scanStatus"], "INCOMPLETE")

    def test_unknown_graph_id_is_recorded_instead_of_crashing(self):
        reference, correlations, candidates = fixtures()
        candidates["candidates"].append(
            {"fromEdge": {"graphId": None}, "toEdge": {"graphId": 202}}
        )
        result = audit(reference, correlations, candidates)
        self.assertEqual(result["graphStudioCandidatePairsWithoutExactIds"], 1)
        self.assertEqual(result["scanStatus"], "INCOMPLETE")

    def test_proven_pairs_must_be_native_observations_with_valid_mode(self):
        reference, correlations, candidates = fixtures()
        reference["provenHandoffs"][0]["mode"] = "unknown"
        reference["scans"]["to"]["edges"].pop()
        result = audit(reference, correlations, candidates)
        self.assertEqual(result["scanStatus"], "INCOMPLETE")
        self.assertTrue(any("mode/direction" in s for s in result["incompleteReasons"]))
        self.assertTrue(any("not present in native" in s for s in result["incompleteReasons"]))

    def test_scanner_identity_required_not_simulated_candidates(self):
        reference, correlations, candidates = fixtures()
        reference["scanner"] = "SyntheticRoadSampler"
        with self.assertRaisesRegex(ValueError, "not identified as the native"):
            audit(reference, correlations, candidates)


if __name__ == "__main__":
    unittest.main()
