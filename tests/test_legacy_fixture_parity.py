"""Unit tests for opt-in, isolated-copy legacy artifact parity verification."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from devtools.verify_legacy_fixture_parity import verify

VALIDATOR = "validate_frontier_road_inventory.py"


class HistoricalFixtureParityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.tools = self.repo / "tools"
        self.installed = self.root / "installed"
        self.tools.mkdir(parents=True)
        self.installed.mkdir()
        self.fixture = self.root / "legacy.json"
        self.fixture.write_text(
            json.dumps({"schema": "roadpilot.frontier-road-inventory",
                        "version": 1, "roads": []}),
            encoding="utf-8",
        )
        self.script = (
            "import argparse\n"
            "p=argparse.ArgumentParser()\n"
            "p.add_argument('--inventory',required=True)\n"
            "args=p.parse_args()\n"
            "print('schema accepted')\n"
        )
        (self.tools / VALIDATOR).write_text(self.script, encoding="utf-8")
        (self.installed / VALIDATOR).write_text(self.script, encoding="utf-8")

    def _verify(self, **kwargs):
        return verify(
            VALIDATOR, self.fixture, self.installed,
            repo_root=self.repo, acknowledge_execution=True, **kwargs,
        )

    def test_positive_real_file_copy_parity_never_writes_input(self):
        original = self.fixture.read_bytes()
        result = self._verify()
        self.assertTrue(result["positive_parity"])
        self.assertEqual(result["classification"],
                         "REAL_INPUT_PARITY_ONLY_NOT_RETIREMENT_AUTHORIZATION")
        self.assertTrue(result["original_unchanged"])
        self.assertEqual(result["source"]["exit_code"], 0)
        self.assertEqual(result["installed"]["exit_code"], 0)
        self.assertFalse(result["source"]["new_files_created"])
        self.assertEqual(self.fixture.read_bytes(), original)
        self.assertEqual(result["external_consumers"], "NOT_VERIFIED")
        self.assertNotIn(str(self.root), json.dumps(result))

    def test_unacknowledged_or_wrong_schema_rejected(self):
        with self.assertRaisesRegex(ValueError, "acknowledge-execution"):
            verify(VALIDATOR, self.fixture, self.installed, repo_root=self.repo)
        self.fixture.write_text('{"schema":"roadpilot.fake","version":1}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "schema/version"):
            self._verify()

    def test_different_output_or_temp_write_rejected(self):
        (self.installed / VALIDATOR).write_text(
            self.script.replace("schema accepted", "different output"),
            encoding="utf-8",
        )
        self.assertFalse(self._verify()["positive_parity"])
        (self.installed / VALIDATOR).write_text(
            self.script + "from pathlib import Path\nPath('side_effect.txt').write_text('x')\n",
            encoding="utf-8",
        )
        result = self._verify()
        self.assertFalse(result["positive_parity"])
        self.assertTrue(result["installed"]["new_files_created"])
        self.assertFalse((self.root / "side_effect.txt").exists())

    def test_symlink_and_oversized_input_rejected(self):
        alias = self.root / "link.json"
        alias.symlink_to(self.fixture)
        with self.assertRaisesRegex(ValueError, "non-symlink"):
            verify(VALIDATOR, alias, self.installed, repo_root=self.repo,
                   acknowledge_execution=True)
        with self.assertRaisesRegex(ValueError, "maximum permitted"):
            self._verify(max_bytes=8)


if __name__ == "__main__":
    unittest.main()
