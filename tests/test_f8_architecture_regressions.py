"""Behavioral F8 invariants and architectural PR-policy regression tests.

These deterministic tests are not a claim of real Legion graph-edge parity.
They catch the earlier first-success-only / same-road-name loss of alternatives
and verify that protected architecture changes cannot pass an empty checklist.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import check_architecture_contract as contract
import plan_multiregion_route as multiregion
import refresh_graph_connectivity as refresh


def edge(rank: int, graph_id: int, way_id: int, heading: float):
    return {
        "rank": rank, "wayMatch": False, "wayId": way_id,
        "correlatedCoordinate": {"lat": 47.0 + rank * 0.00001, "lng": 12.0},
        "distanceMeters": 0.3, "percentAlong": 0.5,
        "headingDegrees": heading, "linearReference": None, "graphId": graph_id,
        "roadNames": ["Shared motorway name"], "access": {},
        "roadClass": "motorway", "use": None,
    }


class F8ArchitectureBehaviorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_all_correlated_edges_and_both_same_name_roads_are_retained(self):
        # Two physical way IDs share a road name; each has 2 directed
        # correlates on each independent graph, including opposite headings.
        # The generator must not keep only the first "good" match.
        fp_a = "sha256:" + "a" * 64
        fp_b = "sha256:" + "b" * 64
        artifact = {
            "schema": "roadpilot.frontier-road-correlations", "version": 1,
            "pairId": "region-a__region-b",
            "fromRegionId": "region-a", "toRegionId": "region-b",
            "fromBoundaryFingerprint": fp_a, "toBoundaryFingerprint": fp_b,
            "fromGraph": {"graphFingerprint": fp_a},
            "toGraph": {"graphFingerprint": fp_b},
            "correlations": [],
        }
        for i, way in enumerate((101, 202)):
            artifact["correlations"].append({
                "frontierRoadId": "fri1-" + str(i+1) * 24,
                "wayId": way, "crossingIndex": 0, "crossingKind": "CROSSING",
                "frontierCoordinate": {"lat": 47.0, "lng": 12.0},
                "frontierHeadingDegrees": 90.0,
                "routingTags": {"highway": "motorway"},
                "fromGraph": {"status": "CORRELATED", "candidates": [
                    edge(0, 100 + i, way, 0.0),
                    edge(1, 110 + i, way, 180.0),
                ]},
                "toGraph": {"status": "CORRELATED", "candidates": [
                    edge(0, 200 + i, way, 180.0),
                    edge(1, 210 + i, way, 0.0),
                ]},
            })
        input_path = self.root / "correlations.json"
        output_path = self.root / "candidates.json"
        input_path.write_text(json.dumps(artifact))
        process = subprocess.run(
            [sys.executable, str(ROOT / "tools/build_crossing_candidates.py"),
             "--correlations", str(input_path), "--output", str(output_path)],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        candidates = json.loads(output_path.read_text())["candidates"]
        self.assertEqual(len(candidates), 8, "Generator may not keep only a first success")
        self.assertEqual({item["stableWayId"] for item in candidates}, {101, 202})
        self.assertEqual(len({item["id"] for item in candidates}), 8)
        # Even opposite-heading/no-shared-way-name evidence cannot be
        # dismissed before Valhalla route validation.
        self.assertTrue(any(
            item["fromEdge"]["headingDegrees"] == 0.0
            and item["toEdge"]["headingDegrees"] == 180.0
            for item in candidates
        ))

    def test_first_validated_crossing_does_not_preempt_better_second(self):
        graphs = {"region-a": SimpleNamespace(fingerprint="sha256:a"),
                  "region-b": SimpleNamespace(fingerprint="sha256:b")}
        results = [
            {"status": "ROUTE_SELECTED", "chainId": "known-first",
             "regions": ["region-a", "region-b"], "legs": [1, 2],
             "durationSeconds": 500, "distanceKm": 25},
            {"status": "ROUTE_SELECTED", "chainId": "better-new",
             "regions": ["region-a", "region-b"], "legs": [1, 2],
             "durationSeconds": 210, "distanceKm": 30},
        ]
        for style, expected in (("FASTER", "better-new"), ("SHORTER", "known-first")):
            with self.subTest(style=style):
                with mock.patch.multiple(
                    multiregion,
                    trusted_graphs=mock.DEFAULT,
                    regions_containing=mock.DEFAULT,
                    local_assets=mock.DEFAULT,
                    proposed_chains=mock.DEFAULT,
                    evaluate_chain=mock.DEFAULT,
                ) as patched:
                    patched["trusted_graphs"].return_value = graphs
                    patched["regions_containing"].side_effect = [["region-a"], ["region-b"]]
                    patched["local_assets"].return_value = (
                        [self.root / "current-runtime.json"],
                        [self.root / "a-inventory.json", self.root / "b-inventory.json"],
                        [], {"region-a": {}, "region-b": {}},
                    )
                    patched["proposed_chains"].return_value = [
                        {"id": "known-first"}, {"id": "better-new"}
                    ]
                    patched["evaluate_chain"].side_effect = results
                    chosen = multiregion.plan(
                        self.root, self.root, self.root, self.root, self.root,
                        Path("/valhalla"), {"lat": 47, "lng": 12},
                        {"lat": 48, "lng": 13}, "motorcycle", style, {},
                    )
                    self.assertEqual(chosen["chainId"], expected)
                    self.assertEqual(chosen["chainsAttempted"], 2)
                    self.assertEqual(chosen["successfulChains"], 2)
                    self.assertEqual(patched["evaluate_chain"].call_count, 2)

    def test_cached_runtime_cannot_outlive_either_graph_or_boundary(self):
        a = SimpleNamespace(region="a", primary="source-a",
                            fingerprint="sha256:a", boundaries={"source-b": "sha256:bound-a"})
        b = SimpleNamespace(region="b", primary="source-b",
                            fingerprint="sha256:b", boundaries={"source-a": "sha256:bound-b"})
        dest = self.root / "runtime.json"
        data = {
            "schema": "roadpilot.runtime-connectivity", "validationState": "VALIDATED",
            "pairId": "a__b", "fromGraph": {"graphFingerprint": a.fingerprint},
            "toGraph": {"graphFingerprint": b.fingerprint},
            "fromBoundaryFingerprint": a.boundaries["source-b"],
            "toBoundaryFingerprint": b.boundaries["source-a"],
        }
        dest.write_text(json.dumps(data))
        self.assertTrue(refresh.is_current_runtime(dest, a, b))
        newer_graph = SimpleNamespace(**{**vars(b), "fingerprint": "sha256:changed"})
        self.assertFalse(refresh.is_current_runtime(dest, a, newer_graph))
        newer_frontier = SimpleNamespace(**{**vars(a), "boundaries": {"source-b": "sha256:changed"}})
        self.assertFalse(refresh.is_current_runtime(dest, newer_frontier, b))


class F8ArchitecturePolicyTests(unittest.TestCase):
    def valid_pr(self):
        template = (ROOT / ".github/pull_request_template.md").read_text()
        body = template.replace("- [ ]", "- [x]")
        body = body.replace(
            "Explain what changes, which implementation actually runs, and what is NOT yet proven. Keep only relevant clauses.",
            "The production candidate generator still retains every correlated directed-edge combination. "
            "This adds regression protection and does not claim real-graph F8 parity.",
        )
        body = body.replace(
            "Explain test names and observed results, exact commit/graph versions if known, missing acceptance coverage, and any fallback. Do not confuse a successful build with actual F8 parity or Android consumption.",
            "The new synthetic first-vs-second handoff regression verifies that both valid alternatives "
            "are evaluated and the better choice wins for FASTER, while SHORTER chooses the shorter leg. "
            "Real Italy–Austria graph parity is not yet run and is tracked in issue #73.",
        )
        return body

    def test_complete_routing_pr_passes_contract_gate(self):
        self.assertEqual(contract.validate(
            self.valid_pr(), ["tools/build_frontier_road_inventory.py"]), [])

    def test_missing_or_unchecked_contract_acknowledgement_blocks_pr(self):
        body = self.valid_pr().replace(
            "- [x] First successful or cached crossing never hides alternative crossings",
            "- [ ] First successful or cached crossing never hides alternative crossings",
        )
        self.assertTrue(any("Unchecked F8 invariant" in e for e in contract.validate(
            body, ["tools/refresh_graph_connectivity.py"])))

    def test_unapproved_architecture_change_is_blocked(self):
        body = self.valid_pr().replace("Architecture decision: PRESERVES",
                                       "Architecture decision: CHANGE_REQUESTED")
        self.assertTrue(any("NOT automatically permitted" in e for e in contract.validate(
            body, ["tools/build_crossing_candidates.py"])))

    def test_unproven_parity_claim_requires_real_evidence(self):
        body = self.valid_pr().replace("Discovery coverage: NOT_VERIFIED",
                                       "Discovery coverage: GRAPH_EDGE_PARITY_VERIFIED")
        self.assertTrue(any("parity evidence" in e.lower() for e in contract.validate(
            body, ["tools/build_crossing_candidates.py"])))

    def test_empty_test_results_are_rejected(self):
        body = self.valid_pr()
        body = body.replace(
            "The new synthetic first-vs-second handoff regression verifies that both valid alternatives "
            "are evaluated and the better choice wins for FASTER, while SHORTER chooses the shorter leg. "
            "Real Italy–Austria graph parity is not yet run and is tracked in issue #73.",
            "Passed.",
        )
        self.assertTrue(any("actual test results" in e for e in contract.validate(
            body, ["tools/prove_crossing_candidates.py"])))

    def test_non_architecture_changes_do_not_require_routing_checklist(self):
        self.assertEqual(contract.validate(
            "", ["docs/usage.md", "search/build_search_pack.py"]), [])


if __name__ == "__main__":
    unittest.main()
