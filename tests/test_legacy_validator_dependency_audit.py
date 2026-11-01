"""Regression gates for the non-destructive P4-B legacy CLI audit."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
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
        self.assertEqual(report["repository"], "git-checkout")
        self.assertTrue(report["git_head"])
        self.assertIn("tracked_worktree_dirty", report)
        with self.assertRaisesRegex(ValueError, "acknowledge"):
            audit(root, probe_help=True)
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
            self.assertEqual(report["git_head"], "UNBORN_HEAD")
            self.assertTrue(report["tracked_worktree_dirty"])
            with self.assertRaisesRegex(RuntimeError, "committed HEAD"):
                audit(root, probe_help=True, acknowledge_cli_execution=True)

    def test_all_legacy_validators_reject_wrong_schema_without_fixture_writes(self):
        """Synthetic negative-path contract only, NOT real historical acceptance."""
        root = Path(__file__).resolve().parent.parent
        with tempfile.TemporaryDirectory(prefix="p4b-invalid-schema-") as temp:
            directory = Path(temp)
            fixture = directory / "invalid.json"
            fixture.write_text(
                '{"schema":"roadpilot.intentionally-invalid","version":1}\n',
                encoding="utf-8",
            )
            before = hashlib.sha256(fixture.read_bytes()).hexdigest()
            environment = dict(os.environ)
            environment["PYTHONDONTWRITEBYTECODE"] = "1"
            environment["PYTHONNOUSERSITE"] = "1"
            for name in CANDIDATES:
                flag = "--inventory" if name == "validate_frontier_road_inventory.py" else "--artifact"
                completed = subprocess.run(
                    [sys.executable, str(root / "tools" / name), flag, str(fixture)],
                    cwd=directory, env=environment, capture_output=True,
                    timeout=10, check=False,
                )
                with self.subTest(name=name):
                    self.assertEqual(completed.returncode, 1)
                    self.assertIn(b"unexpected schema", completed.stderr)
                    self.assertEqual(
                        hashlib.sha256(fixture.read_bytes()).hexdigest(), before
                    )
                    self.assertEqual(
                        sorted(path.name for path in directory.iterdir()), ["invalid.json"]
                    )

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
