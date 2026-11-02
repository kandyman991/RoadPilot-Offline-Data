"""Regression gate for ten historical-CI synthetic legacy v1 CLI fixtures.

These snapshots are NOT operational user data or F8 graph-edge parity evidence.
They were reconstructed by replaying committed pre-#84 CI in a disposable
environment, then checked against historical/current/installed validators.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "historical-legacy-v1-synthetic"
EXPECTED = {
    "roadpilot.connectivity-chain-plan": "validate_connectivity_chain_plan.py",
    "roadpilot.connectivity-refresh-plan": "validate_connectivity_refresh_plan.py",
    "roadpilot.crossing-candidates": "validate_crossing_candidates.py",
    "roadpilot.crossing-proofs": "validate_crossing_proofs.py",
    "roadpilot.frontier-road-correlations": "validate_frontier_road_correlations.py",
    "roadpilot.hierarchical-connectivity-plan": "validate_hierarchical_connectivity_plan.py",
    "roadpilot.region-connector-inventory": "validate_region_connector_inventory.py",
    "roadpilot.region-connector-matrix": "validate_region_connector_matrix.py",
    "roadpilot.region-connector-refresh-plan": "validate_region_connector_refresh_plan.py",
    "roadpilot.runtime-connectivity": "validate_runtime_connectivity.py",
}

# These are material historical-CI payloads, not merely schema-valid empty shells.
EXPECTED_NONEMPTY_COUNTS = {
    "roadpilot.connectivity-chain-plan": ("chains", 2),
    "roadpilot.connectivity-refresh-plan": ("pairs", 2),
    "roadpilot.crossing-candidates": ("candidates", 18),
    "roadpilot.crossing-proofs": ("proofs", 18),
    "roadpilot.frontier-road-correlations": ("correlations", 2),
    "roadpilot.hierarchical-connectivity-plan": ("chains", 2),
    "roadpilot.region-connector-inventory": ("anchors", 9),
    "roadpilot.runtime-connectivity": ("crossings", 8),
}
PINNED_MANIFEST_SHA256 = "595a2f49f31415f67ca0542cf0b4e74f2c77b5ab9f9424258245cca85f31e123"



class HistoricalLegacyPositiveFixturesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))
        cls.entries = cls.manifest["fixtures"]

    def test_provenance_and_exact_ten_schema_contracts(self) -> None:
        self.assertEqual(
            self.manifest["provenance"], "RECONSTRUCTED_SYNTHETIC_HISTORICAL_CI_NOT_PRODUCTION"
        )
        self.assertEqual(self.manifest["f8GraphEdgeParity"], "NOT_VERIFIED")
        self.assertEqual(
            self.manifest["historical_git_ref"],
            "9c95ca37ef763f3e3d123fb3c77f2c9b25ab0be3",
        )
        self.assertEqual(
            {entry["schema"]: entry["validator"] for entry in self.entries}, EXPECTED
        )
        self.assertEqual(len(self.entries), 10)
        self.assertEqual(
            hashlib.sha256((FIXTURES / "manifest.json").read_bytes()).hexdigest(),
            PINNED_MANIFEST_SHA256,
        )
        self.assertEqual(
            {p.name for p in FIXTURES.glob("*.json")},
            {"manifest.json", *[entry["file"] for entry in self.entries]},
        )
        for entry in self.entries:
            with self.subTest(schema=entry["schema"]):
                self.assertEqual(
                    entry["file"],
                    entry["validator"].removeprefix("validate_").removesuffix(".py") + ".json",
                )
                path = FIXTURES / entry["file"]
                self.assertFalse(path.is_symlink())
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), entry["sha256"])
                self.assertEqual(path.stat().st_size, entry["bytes"])
                obj = json.loads(path.read_bytes())
                self.assertEqual(obj["schema"], entry["schema"])
                self.assertEqual(obj["version"], 1)
                if entry["schema"] in EXPECTED_NONEMPTY_COUNTS:
                    field, count = EXPECTED_NONEMPTY_COUNTS[entry["schema"]]
                    self.assertEqual(len(obj[field]), count)
                elif entry["schema"] == "roadpilot.region-connector-matrix":
                    self.assertEqual(obj["sourceAnchorCount"], 3)
                    self.assertEqual(set(obj["modes"]), {"CAR", "MOTORCYCLE"})
                elif entry["schema"] == "roadpilot.region-connector-refresh-plan":
                    self.assertEqual(obj["status"], "STALE")
                    self.assertEqual(obj["refreshAction"], "REBUILD_INVENTORY_AND_MATRIX")
                else:
                    self.fail("No material-payload assertion for historical schema")
                raw = path.read_text(encoding="utf-8")
                self.assertNotIn("/home/", raw)
                self.assertNotIn("/tmp/", raw)

    @staticmethod
    def run_cli(validator: Path, artifact: Path, cwd: Path) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            [sys.executable, str(validator), "--artifact", str(artifact)],
            cwd=cwd, capture_output=True, timeout=15, check=False,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1"},
        )

    def test_positive_compatibility_is_read_only_for_all_ten(self) -> None:
        for entry in self.entries:
            with self.subTest(schema=entry["schema"]), tempfile.TemporaryDirectory() as tmp:
                directory = Path(tmp)
                copy = directory / "artifact.json"
                shutil.copyfile(FIXTURES / entry["file"], copy)
                before = hashlib.sha256(copy.read_bytes()).hexdigest()
                outcome = self.run_cli(ROOT / "tools" / entry["validator"], copy, directory)
                self.assertEqual(outcome.returncode, 0, outcome.stderr.decode(errors="replace"))
                self.assertEqual(outcome.stderr, b"")
                self.assertEqual(hashlib.sha256(outcome.stdout).hexdigest(), entry["positiveStdoutSha256"])
                self.assertEqual(hashlib.sha256(copy.read_bytes()).hexdigest(), before)
                self.assertEqual([p.name for p in directory.iterdir()], ["artifact.json"])

    def test_invalid_schema_is_rejected_without_mutation_for_all_ten(self) -> None:
        for entry in self.entries:
            with self.subTest(schema=entry["schema"]), tempfile.TemporaryDirectory() as tmp:
                directory = Path(tmp)
                copy = directory / "artifact.json"
                obj = json.loads((FIXTURES / entry["file"]).read_bytes())
                obj["schema"] = "invalid.legacy-test-schema"
                copy.write_text(json.dumps(obj), encoding="utf-8")
                before = hashlib.sha256(copy.read_bytes()).hexdigest()
                outcome = self.run_cli(ROOT / "tools" / entry["validator"], copy, directory)
                self.assertNotEqual(outcome.returncode, 0)
                self.assertEqual(outcome.returncode, entry["invalidSchemaExitCode"])
                self.assertEqual(hashlib.sha256(outcome.stdout).hexdigest(), entry["invalidSchemaStdoutSha256"])
                self.assertEqual(hashlib.sha256(outcome.stderr).hexdigest(), entry["invalidSchemaStderrSha256"])
                self.assertEqual(hashlib.sha256(copy.read_bytes()).hexdigest(), before)
                self.assertEqual([p.name for p in directory.iterdir()], ["artifact.json"])


if __name__ == "__main__":
    unittest.main()
