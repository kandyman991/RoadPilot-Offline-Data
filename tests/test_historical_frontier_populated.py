"""Reconstructed *synthetic* pre-#84 two-road frontier fixture compatibility gate.

The fixture is generated from committed historic CI sources, NOT recovered
operational/private data and NOT evidence of native F8 graph-edge parity.
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
FIXTURE = ROOT / "tests/fixtures/historical-frontier-v1-populated-synthetic.json"
VALIDATOR = ROOT / "tools/validate_frontier_road_inventory.py"


class ReconstructedPopulatedFrontierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="legacy-frontier-v1-")
        self.addCleanup(self.temp.cleanup)
        self.input = Path(self.temp.name) / "inventory.json"
        shutil.copyfile(FIXTURE, self.input)
        self.original_hash = hashlib.sha256(self.input.read_bytes()).hexdigest()

    def validate(self) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            [sys.executable, str(VALIDATOR), "--inventory", str(self.input)],
            cwd=self.temp.name,
            capture_output=True, timeout=10, check=False,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1"},
        )

    def test_historical_two_road_reconstruction_is_positive(self) -> None:
        obj = json.loads(self.input.read_bytes())
        self.assertEqual(obj["schema"], "roadpilot.frontier-road-inventory")
        self.assertEqual(obj["version"], 1)
        self.assertEqual(obj["generator"], {"name": "roadpilot-osm-frontier-inventory", "version": "1"})
        self.assertEqual(len(obj["roads"]), 2)
        self.assertEqual(
            {r["wayId"]: r["crossingKind"] for r in obj["roads"]},
            {100: "CROSSING", 102: "FRONTIER_OVERLAP"},
        )
        self.assertEqual(obj["roads"][0]["routingTags"]["ref"], "A1")
        self.assertEqual(obj["discovery"]["f8GraphEdgeParity"], "NOT_VERIFIED")
        result = self.validate()
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        self.assertEqual(result.stderr, b"")
        self.assertEqual(hashlib.sha256(self.input.read_bytes()).hexdigest(), self.original_hash)
        self.assertEqual(sorted(p.name for p in Path(self.temp.name).iterdir()), ["inventory.json"])

    def test_modified_road_coordinate_must_be_rejected(self) -> None:
        obj = json.loads(self.input.read_bytes())
        obj["roads"][0]["crossingCoordinate"]["lat"] = 91
        self.input.write_text(json.dumps(obj), encoding="utf-8")
        modified_hash = hashlib.sha256(self.input.read_bytes()).hexdigest()
        result = self.validate()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(hashlib.sha256(self.input.read_bytes()).hexdigest(), modified_hash)
        self.assertEqual(sorted(p.name for p in Path(self.temp.name).iterdir()), ["inventory.json"])

    def test_modified_frontier_kind_must_be_rejected(self) -> None:
        obj = json.loads(self.input.read_bytes())
        obj["roads"][1]["crossingKind"] = "NOT_A_REAL_KIND"
        self.input.write_text(json.dumps(obj), encoding="utf-8")
        result = self.validate()
        self.assertNotEqual(result.returncode, 0)

    def test_this_fixture_is_explicitly_synthetic_not_production(self) -> None:
        obj = json.loads(FIXTURE.read_bytes())
        self.assertEqual([r["wayId"] for r in obj["roads"]], [100, 102])
        self.assertEqual([obj["fromRegionId"], obj["toRegionId"]], ["region-a", "region-b"])
        self.assertEqual(obj["discovery"]["scope"], "NOMINAL_ONLY")
        self.assertEqual(obj["discovery"]["f8GraphEdgeParity"], "NOT_VERIFIED")


if __name__ == "__main__":
    unittest.main()
