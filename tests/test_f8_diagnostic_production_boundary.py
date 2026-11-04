"""Regression gate: M6c forensic road-join must never become an F8 producer.

Native receiver-side GraphReader scan + GPS proposal inventory is authoritative.
A/B road geometry is an optional bounded *diagnostic*, not a filter or catalog.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "devtools"))

from discover_native_f8_crossings import candidate
from test_native_f8_road_continuity import check


class NoDiagnosticPromotionTests(unittest.TestCase):
    def test_continuity_experiment_is_not_in_shipped_pipeline_tools(self):
        self.assertTrue(
            (ROOT / "devtools/probe_native_f8_road_continuity.py").is_file()
        )
        self.assertFalse(
            (ROOT / "tools/probe_native_f8_road_continuity.py").exists()
        )
        config = json.loads(
            (ROOT / "graph-studio/src-tauri/tauri.conf.json").read_text()
        )
        resources = config["bundle"]["resources"]
        # Graph Studio packages the complete tools/ tree; devtools/ must
        # remain absent, even when the experiment produces positive evidence.
        self.assertIn("../../tools/", resources)
        self.assertNotIn("../../devtools/", resources)
        for key, value in resources.items():
            self.assertNotIn("devtools", key)
            self.assertNotIn("devtools", str(value))

    def test_no_runtime_or_production_tool_imports_forensic_road_join(self):
        forbidden = "probe_native_f8_road_continuity"
        # This is a guard on all shipping Python tools, even those executed
        # through Tauri's pipeline command interface.
        for file in (ROOT / "tools").rglob("*.py"):
            ast.parse(file.read_text(encoding="utf-8"))
            self.assertNotIn(forbidden, file.read_text(encoding="utf-8"),
                             f"Runtime tool must not depend on M6c forensic diagnostic: {file}")
        for code in (
            list((ROOT / "graph-studio/src-tauri/src").rglob("*.rs"))
            + list((ROOT / "graph-studio/src").rglob("*.ts"))
            + list((ROOT / "graph-studio/src").rglob("*.tsx"))
        ):
            self.assertNotIn(forbidden, code.read_text(encoding="utf-8"),
                             f"Installed Graph Studio must not invoke M6c diagnostic: {code}")

    def test_original_receiver_f8_proposals_are_independent_of_same_road_peers(self):
        # Same-way different directed edges and a no-peer edge must produce
        # distinct native F8 GPS proposals. Never gate them on M6c geometry.
        pair = {
            "pairId": "example-graph-pair",
            "fromGraphFingerprint": "sha256:" + "a" * 64,
            "toGraphFingerprint": "sha256:" + "b" * 64,
        }
        def receiver(graph_id, latitude):
            return {
                "graphId":graph_id, "wayId":8080,
                "innerLat":latitude, "innerLon":13.5,
                "lat":latitude-0.0001, "lon":13.4999,
                "forwardAccess":1025, "reverseAccess":1025,
            }
        first = candidate(pair,"from-to",receiver(101,46.5),[])
        second = candidate(pair,"from-to",receiver(102,46.6),[9001])
        reverse = candidate(pair,"to-from",receiver(101,46.5),[])
        self.assertNotEqual(first["id"],second["id"])
        self.assertNotEqual(first["id"],reverse["id"])
        self.assertEqual(first["gpsProposalState"],"UNPROVEN")
        self.assertEqual(first["receiverGraphId"],101)
        self.assertEqual(second["receiverGraphId"],102)
        self.assertEqual(first["physicalPeerOriginGraphIds"],[])
        self.assertEqual(second["physicalPeerOriginGraphIds"],[9001])
        self.assertEqual(first["originGraphCorrelation"],"NOT_RUN")
        self.assertEqual(first["receiverGraphCorrelation"],"NOT_RUN")

    def test_successful_b_road_geometry_does_not_create_any_f8_crossing_record(self):
        result = check()
        self.assertEqual(result["artifactRole"],
                         "NON_SHIPPING_FORENSIC_DIAGNOSTIC_ONLY")
        self.assertEqual(result["crossingCandidateExport"],"NONE")
        self.assertIs(result["geometryCannotExcludeF8Proposals"],True)
        self.assertEqual(result["productionPublication"],"BLOCKED")
        self.assertEqual(result["sourcePhysicalFinalRoadEdge"],"NOT_VERIFIED")
        self.assertEqual(result["originalValhallaRouteEdgeIdentity"],"NOT_VERIFIED")
        self.assertEqual(result["crossGraphDirectedTurnLegality"],"NOT_VERIFIED")
        self.assertNotIn("candidateId",result)
        self.assertNotIn("gpsProposal",result)
        self.assertNotIn("handoff",result)

    def test_unmatched_b_road_geometry_is_not_rejected_f8_proposal(self):
        # No geometry match to the specific A-terminal must be preserved
        # and cannot be treated as a negative native F8 receiver proposal.
        from test_native_f8_road_continuity import source_and_b, locator
        _, _, advance, _ = source_and_b()
        result = check(locators=[locator(21)],native_b=[advance])
        self.assertEqual(result["retainedReceiverIdentities"],[21])
        self.assertEqual(result["nominatedBIncomingCount"],0)
        self.assertEqual(result["sourceDiscoveryCoverage"],"NOT_VERIFIED")
        self.assertEqual(result["crossingCandidateExport"],"NONE")
        self.assertTrue(result["geometryCannotExcludeF8Proposals"])


if __name__ == "__main__":
    unittest.main()
