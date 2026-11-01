"""Regression tests for the read-only, privacy-minimal P4-B3 fixture inventory."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from devtools.audit_historical_fixture_inventory import SCHEMAS, scan_root


class HistoricalFixtureInventoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def put(self, name: str, data: dict) -> Path:
        target = self.root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data), encoding="utf-8")
        return target

    def test_empty_and_populated_legacy_roads_have_distinct_coverage(self):
        a = self.put("one.json", {
            "schema": "roadpilot.frontier-road-inventory", "version": 1, "roads": [],
            "privateSecret": "SECRET_MUST_NOT_BE_PRINTED",
        })
        b = self.put("sub/two.json", {
            "schema": "roadpilot.frontier-road-inventory", "version": 1,
            "roads": [{"id": 123, "coord": [45.0, 12.0]}],
        })
        original_a, original_b = a.read_bytes(), b.read_bytes()
        report = scan_root(self.root)
        matches = report["matches"]
        self.assertEqual(len(matches), 2)
        self.assertEqual(
            sorted(m["payload_array_lengths"]["roads"] for m in matches), [0, 1])
        self.assertEqual(
            sorted(m["frontier_roads_populated"] for m in matches), [False, True])
        self.assertEqual(report, scan_root(self.root))
        serialized = json.dumps(report)
        self.assertNotIn(str(self.root), serialized)
        self.assertNotIn("SECRET_MUST_NOT_BE_PRINTED", serialized)
        self.assertNotIn('"coord"', serialized)
        self.assertEqual(a.read_bytes(), original_a)
        self.assertEqual(b.read_bytes(), original_b)
        self.assertIn(hashlib.sha256(original_a).hexdigest(), serialized)

    def test_11_schema_mapping_and_nonmatching_schema(self):
        self.assertEqual(len(SCHEMAS), 11)
        self.assertIn("roadpilot.region-connector-refresh-plan", SCHEMAS)
        self.put("not_a_legacy_type.json", {
            "schema": "roadpilot.boundary-edge-inventory", "version": 1,
            "edges": [{"id": 1}],
        })
        self.put("legacy.json", {
            "schema": "roadpilot.crossing-proofs", "version": 1, "proofs": [1, 2],
        })
        matches = scan_root(self.root)["matches"]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["schema"], "roadpilot.crossing-proofs")
        self.assertEqual(matches[0]["payload_array_lengths"]["proofs"], 2)

    def test_symlinks_are_not_followed(self):
        outer = self.root / "outside"
        outer.mkdir()
        nested = outer / "nested.json"
        nested.write_text(json.dumps({
            "schema": "roadpilot.crossing-proofs", "version": 1,
            "proofs": [1]}), encoding="utf-8")
        scoped = self.root / "scoped"
        scoped.mkdir()
        (scoped / "linked.json").symlink_to(nested)
        (scoped / "other").symlink_to(outer, target_is_directory=True)
        report = scan_root(scoped)
        self.assertEqual(report["matches"], [])
        self.assertEqual(report["symlinks_skipped"], 2)
        with self.assertRaisesRegex(ValueError, "not a symlink"):
            scan_root(scoped / "other")

    def test_bounded_scans_report_incomplete_evidence(self):
        self.put("a.json", {
            "schema": "roadpilot.crossing-candidates", "version": 1,
            "candidates": [1]})
        self.put("b.json", {
            "schema": "roadpilot.crossing-proofs", "version": 1,
            "proofs": [2]})
        limited = scan_root(self.root, max_files=1)
        self.assertTrue(limited["truncated"])
        self.assertEqual(limited["files_checked"], 1)
        small = scan_root(self.root, max_file_bytes=3)
        self.assertEqual(small["oversize"], 2)
        self.assertEqual(small["matches"], [])
        with self.assertRaisesRegex(ValueError, "positive"):
            scan_root(self.root, max_files=0)

    def test_depth_cap_is_disclosed(self):
        self.put("sub/deep.json", {
            "schema": "roadpilot.runtime-connectivity", "version": 1,
            "routes": [1]})
        report = scan_root(self.root, max_depth=0)
        self.assertTrue(report["truncated"])
        self.assertEqual(report["matches"], [])


if __name__ == "__main__":
    unittest.main()
