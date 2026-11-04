"""Recorded Legion pinned native hierarchy evidence and source-checksum policy."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class OriginalGraphHierarchyBuildProvenanceTests(unittest.TestCase):
    @staticmethod
    def sha256(path: Path) -> str:
        return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()

    def test_exact_native_source_and_build_recipe_match_real_graph_proof(self):
        path = ROOT / "docs/F8_PR120_ORIGINAL_BRANCH_BUILD_PROVENANCE.json"
        doc = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(doc["schema"],
                         "roadpilot.f8-native-branch-hierarchy-build-provenance")
        self.assertEqual(doc["version"], 1)
        self.assertEqual(doc["valhallaVersion"],"3.6.3")
        self.assertEqual(self.sha256(ROOT / doc["nativeSourcePath"]),
                         doc["nativeSourceSha256"])
        self.assertEqual(self.sha256(ROOT / doc["cmakePath"]),
                         doc["cmakeSha256"])
        self.assertEqual(doc["realAcceptanceReportSha256"],
                         "sha256:5a570d50cf31abf4d2a8c331529aa8e84b1b7fcaf2db5a7e30feae0be8e031c0")
        self.assertEqual(doc["nativeExecutableSha256"],
                         "sha256:74ed43ecff2cbffbffeb737381646561615d764c1468153f36c9ee8fc1f5f372")
        self.assertEqual(doc["originalRouteBinarySha256"],
                         "sha256:e955677e56278b53cee0d39ca6d94efa1557e1439da81859f330ffb4b8dbe776")
        self.assertEqual(doc["nativeTopologyHopCounts"]["missing"],0)
        self.assertEqual(doc["nativeTopologyHopCounts"]["direct"],5404)
        self.assertEqual(doc["nativeTopologyHopCounts"]["hierarchyLevelTransitions"],52)
        self.assertEqual(doc["realCases"],8)
        self.assertEqual(doc["directionallyAlignedHandoffs"],2)
        self.assertEqual(doc["opposingOrUnprovenHandoffs"],6)
        for key in ("physicalRoadGlobalUnique", "crossGraphTurnLegality", "androidE2E"):
            self.assertEqual(doc[key],"NOT_VERIFIED")
        self.assertEqual(doc["productionPublication"],"BLOCKED")
        self.assertIn("independent",doc["reviewState"].lower().replace("_"," "))

    def test_opt_in_native_lineage_does_not_replace_existing_scan_paths(self):
        source=(ROOT/"tools/native-f8-edge-scan/native_f8_directed_endpoints.cpp").read_text()
        self.assertIn('std::string(argv[3]) == "--continuations"',source)
        self.assertIn('std::string(argv[3]) == "--geometry"',source)
        self.assertIn('std::string(argv[3]) == "--lineage"',source)
        self.assertIn('nativeAllHierarchyContinuationNodes',source)
        self.assertIn('GetNodeTransitions',source)
        self.assertIn('is_shortcut()',source)
        self.assertIn('endNodeGraphId',source)
        self.assertIn('PARTIAL_STDOUT_MUST_BE_DISCARDED',source)


if __name__ == "__main__":
    unittest.main()
