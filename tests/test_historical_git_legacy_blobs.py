"""P4-B6: bounded read-only historical Git blob compatibility audit tests."""
from __future__ import annotations

import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from devtools.audit_historical_git_legacy_blobs import inventory, main


class HistoricalGitLegacyBlobAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        workspace = tempfile.TemporaryDirectory()
        self.addCleanup(workspace.cleanup)
        self.root = Path(workspace.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.git("init", "-q")
        self.git("config", "user.name", "Unit Tester")
        self.git("config", "user.email", "unit-tester@example.invalid")

    def git(self, *args: str) -> None:
        subprocess.run(["git", "-C", str(self.repo), *args], check=True,
                       capture_output=True, timeout=15)

    def put(self, name: str, data: object) -> None:
        file = self.repo / name
        file.parent.mkdir(exist_ok=True, parents=True)
        file.write_text(json.dumps(data), encoding="utf-8")

    def commit(self) -> None:
        self.git("add", "-A")
        self.git("commit", "-qm", "audit fixture")

    def test_history_is_read_only_and_never_discloses_paths_or_secrets(self) -> None:
        self.put("tests/fixtures/historical-test.json", {
            "schema": "roadpilot.frontier-road-inventory", "version": 1,
            "roads": [{"PRIVATE_GPS_COORDINATES": "SECRET_NEVER_PRINT"}],
        })
        self.commit()
        self.put("work/real-looking.json", {
            "schema": "roadpilot.crossing-candidates", "version": 1,
            "candidates": [{"privateOperator": "SECRET_NEVER_PRINT"}],
        })
        self.commit()
        before = subprocess.check_output(
            ["git", "-C", str(self.repo), "status", "--porcelain"]
        )
        result = inventory(self.repo)
        self.assertEqual(result["json_objects_parsed"], 2)
        self.assertEqual(len(result["legacy_by_schema_and_path_class"]), 2)
        self.assertEqual(
            {item["path_class"] for item in result["legacy_by_schema_and_path_class"]},
            {"known_historical_test_fixture_path", "other_path_not_production_proof"},
        )
        output = json.dumps(result)
        self.assertNotIn("SECRET_NEVER_PRINT", output)
        self.assertNotIn(str(self.repo), output)
        self.assertNotIn("real-looking.json", output)
        self.assertEqual(
            subprocess.check_output(["git", "-C", str(self.repo), "status", "--porcelain"]),
            before,
        )

    def test_historical_versions_are_examined_and_uncommitted_not_claimed(self) -> None:
        self.put("tests/fixtures/historical-test.json", {
            "schema": "roadpilot.frontier-road-inventory", "version": 1, "roads": [],
        })
        self.commit()
        self.put("tests/fixtures/historical-test.json", {
            "schema": "roadpilot.frontier-road-inventory", "version": 1,
            "roads": [{"id": "synthetic"}],
        })
        self.commit()
        self.put("work/uncommitted.json", {
            "schema": "roadpilot.crossing-proofs", "version": 1, "proofs": [1],
        })
        result = inventory(self.repo)
        self.assertEqual(result["unique_json_objects_considered"], 2)
        self.assertEqual(
            {x["observed_top_level_arrays"] for x in result["legacy_by_schema_and_path_class"]},
            {"no_nonempty_named_array", "nonempty_top_level_array"},
        )
        self.assertEqual(result["historical_operational_artifacts"], "NOT_PROVEN")

    def test_only_version_one_counts_as_a_v1_legacy_artifact(self) -> None:
        self.put("tests/fixtures/historical-wrong-version.json", {
            "schema": "roadpilot.crossing-candidates", "version": 2,
            "candidates": [1],
        })
        self.commit()
        report = inventory(self.repo)
        self.assertEqual(report["json_objects_parsed"], 1)
        self.assertEqual(report["legacy_schema_wrong_or_missing_version"], 1)
        self.assertEqual(report["legacy_by_schema_and_path_class"], [])

    def test_bounded_limits_report_truncation_and_oversize(self) -> None:
        self.put("tests/fixtures/historical-one.json", {
            "schema": "roadpilot.frontier-road-inventory", "version": 1, "roads": [1],
        })
        self.put("tests/fixtures/historical-two.json", {
            "schema": "roadpilot.crossing-proofs", "version": 1, "proofs": [1],
        })
        self.commit()
        capped = inventory(self.repo, max_json_blobs=1)
        self.assertTrue(capped["truncated"])
        self.assertEqual(capped["unique_json_objects_considered"], 1)
        small = inventory(self.repo, max_blob_bytes=3)
        self.assertEqual(small["oversize_skipped"], 2)
        self.assertEqual(small["json_objects_parsed"], 0)
        for args in ({"max_json_blobs": 0}, {"max_blob_bytes": 0}):
            with self.assertRaisesRegex(ValueError, "positive"):
                inventory(self.repo, **args)

    def test_bad_roots_refused_and_cli_has_privacy_flags(self) -> None:
        self.put("tests/fixtures/historical-test.json", {
            "schema": "roadpilot.frontier-road-inventory", "roads": [],
        })
        self.commit()
        (self.root / "linked").symlink_to(self.repo, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "real directory"):
            inventory(self.root / "linked")
        with self.assertRaisesRegex(ValueError, "repository toplevel"):
            inventory(self.repo / "tests")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(["--repo-root", str(self.repo)]), 0)
        parsed = json.loads(output.getvalue())
        self.assertTrue(parsed["missing_artifacts_do_not_prove_global_absence"])
        self.assertEqual(parsed["external_manual_consumers"], "NOT_VERIFIED")


if __name__ == "__main__":
    unittest.main()
