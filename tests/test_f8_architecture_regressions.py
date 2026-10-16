"""Behavioral F8 invariants and architectural PR-policy regression tests.

These deterministic tests are not a claim of real Legion graph-edge parity.
They catch the earlier first-success-only / same-road-name loss of alternatives
and verify that protected architecture changes cannot pass an empty checklist.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import check_architecture_contract as contract


class F8RetirementBehaviorTests(unittest.TestCase):
    def test_desktop_build_does_not_invoke_osm_frontier_production(self):
        rust = (ROOT / "graph-studio/src-tauri/src/lib.rs").read_text()
        ui = (ROOT / "graph-studio/src/main.ts").read_text()
        for forbidden in ("refresh_graph_connectivity.py", "plan_multi_region_route",
                          "connectivity_only"):
            self.assertNotIn(forbidden, rust)
        for forbidden in ("refreshConnectivityBtn", "runMultiRegionRoute",
                          "Multi-region (validated F8 connectivity)"):
            self.assertNotIn(forbidden, ui)

    def test_native_graph_scan_is_independent_of_retired_osm_sources(self):
        scanner = (ROOT / "tools/capture_native_f8_graph_windows.py").read_text()
        self.assertIn("from native_f8_inputs import", scanner)
        self.assertIn("--pair-manifest", scanner)
        for forbidden in ("build_frontier_road_inventory", "correlate_frontier_roads",
                          "--correlations"):
            self.assertNotIn(forbidden, scanner)

    def test_retired_production_stages_are_absent(self):
        retired = ("build_frontier_road_inventory.py", "correlate_frontier_roads.py",
                   "build_crossing_candidates.py", "prove_crossing_candidates.py",
                   "refresh_graph_connectivity.py", "plan_multiregion_route.py")
        for name in retired:
            self.assertFalse((ROOT / "tools" / name).exists(), name)


class F8ArchitecturePolicyTests(unittest.TestCase):
    def valid_pr(self):
        template = (ROOT / ".github/pull_request_template.md").read_text()
        body = template.replace("- [ ]", "- [x]")
        body = body.replace(
            "Explain what changes, which implementation actually runs, and what is NOT yet proven. Keep only relevant clauses.",
            "The native scanner retains distinct directed-edge identities and does not write runtime crossings. "
            "This adds regression protection and does not claim real-graph F8 parity.",
        )
        body = body.replace(
            "Explain test names and observed results, exact commit/graph versions if known, missing acceptance coverage, and any fallback. Do not confuse a successful build with actual F8 parity or Android consumption.",
            "The native retirement tests confirm that graph builds no longer call the OSM producer and both alternatives "
            "remain a required future parity check; both route styles still require real Valhalla proof. "
            "Real Italy–Austria graph parity is not yet run and is tracked in issue #73.",
        )
        return body

    def test_complete_routing_pr_passes_contract_gate(self):
        self.assertEqual(contract.validate(
            self.valid_pr(), ["tools/capture_native_f8_graph_windows.py"]), [])

    def test_missing_or_unchecked_contract_acknowledgement_blocks_pr(self):
        body = self.valid_pr().replace(
            "- [x] First successful or cached crossing never hides alternative crossings",
            "- [ ] First successful or cached crossing never hides alternative crossings",
        )
        self.assertTrue(any("Unchecked F8 invariant" in e for e in contract.validate(
            body, ["tools/capture_native_f8_graph_windows.py"])))

    def test_unapproved_architecture_change_is_blocked(self):
        body = self.valid_pr().replace("Architecture decision: PRESERVES",
                                       "Architecture decision: CHANGE_REQUESTED")
        self.assertTrue(any("NOT automatically permitted" in e for e in contract.validate(
            body, ["tools/native_f8_inputs.py"])))

    def test_unproven_parity_claim_requires_real_evidence(self):
        body = self.valid_pr().replace("Discovery coverage: NOT_VERIFIED",
                                       "Discovery coverage: GRAPH_EDGE_PARITY_VERIFIED")
        self.assertTrue(any("parity evidence" in e.lower() for e in contract.validate(
            body, ["tools/native_f8_inputs.py"])))

    def test_empty_test_results_are_rejected(self):
        body = self.valid_pr()
        body = body.replace(
            "The native retirement tests confirm that graph builds no longer call the OSM producer and both alternatives "
            "remain a required future parity check; both route styles still require real Valhalla proof. "
            "Real Italy–Austria graph parity is not yet run and is tracked in issue #73.",
            "Passed.",
        )
        self.assertTrue(any("actual test results" in e for e in contract.validate(
            body, ["tools/capture_native_f8_graph_windows.py"])))

    def test_non_architecture_changes_do_not_require_routing_checklist(self):
        self.assertEqual(contract.validate(
            "", ["docs/usage.md", "search/build_search_pack.py"]), [])


if __name__ == "__main__":
    unittest.main()
