"""Regression gates for the non-destructive P4-B legacy CLI audit."""
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.audit_legacy_validator_dependencies import CANDIDATES, audit, tracked_sources


class LegacyValidatorDependencyAuditTests(unittest.TestCase):
    def test_actual_repository_inventory_never_grants_deletion(self):
        root = Path(__file__).resolve().parent.parent
        report = audit(root)
        self.assertEqual(len(report["candidates"]), 11)
        self.assertTrue(report["tauri_tools_bundle_wildcard"])
        self.assertEqual(report["classification"],
                         "EVIDENCE_ONLY_NOT_DELETION_AUTHORIZATION")
        for item in report["candidates"]:
            self.assertEqual(item["retirement_decision"], "RETAIN")
            self.assertEqual(item["external_consumers"], "NOT_VERIFIED")
            self.assertEqual(item["historical_fixture_compatibility"], "NOT_VERIFIED")
            self.assertEqual(len(item["sha256"]), 64)
            self.assertNotIn("help_probe", item)
        self.assertEqual(report, audit(root), "Static audit must be deterministic")

    def test_only_tracked_literal_sources_are_scanned(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            subprocess.run(["git", "-C", str(root), "init", "-q"],
                           check=True, capture_output=True)
            (root / "tools").mkdir()
            (root / "src").mkdir()
            (root / "graph-studio" / "src-tauri").mkdir(parents=True)
            for name in CANDIDATES:
                (root / "tools" / name).write_text("print('trusted example')\n",
                                                    encoding="utf-8")
            config = root / "graph-studio/src-tauri/tauri.conf.json"
            config.write_text(json.dumps(
                {"bundle": {"resources": {"../../tools/": "pipeline/tools/"}}}),
                encoding="utf-8")
            (root / "src/consumer.py").write_text(
                "import validate_crossing_proofs\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "tools", "src", "graph-studio"],
                           check=True, capture_output=True)
            # This untracked text must not count as a dependency.
            (root / "src/untracked.py").write_text(
                "import validate_runtime_connectivity\n", encoding="utf-8")
            report = audit(root)
            indexed = {p["path"]: p for p in report["candidates"]}
            self.assertEqual(
                indexed["tools/validate_crossing_proofs.py"]["literal_tracked_callers_or_mentions"],
                ["src/consumer.py"])
            self.assertEqual(
                indexed["tools/validate_runtime_connectivity.py"]["literal_tracked_callers_or_mentions"],
                [])
            self.assertNotIn("src/untracked.py", tracked_sources(root))
            self.assertEqual(report, audit(root))

    def test_scan_ignores_symlink_targets_outside_repository(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "repo"
            root.mkdir()
            outside = Path(temp) / "outside.py"
            outside.write_text("import validate_crossing_proofs\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "init", "-q"],
                           check=True, capture_output=True)
            (root / "leak.py").symlink_to(outside)
            subprocess.run(["git", "-C", str(root), "add", "leak.py"],
                           check=True, capture_output=True)
            self.assertEqual(tracked_sources(root), {})


if __name__ == "__main__":
    unittest.main()
