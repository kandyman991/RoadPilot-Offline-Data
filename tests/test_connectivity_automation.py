"""Offline contract tests for Graph Studio's automatic F8-derived connectivity stages."""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "refresh_graph_connectivity.py"
SPEC = importlib.util.spec_from_file_location("refresh_graph_connectivity", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ConnectivityAutomationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.work = self.root / "work"
        self.dist = self.root / "dist"
        self.public = self.root / "connectivity"
        self.matrix = self.root / "connector-matrices"
        for folder in (self.work, self.dist, self.public, self.matrix):
            folder.mkdir(parents=True)

    def graph(self, name, primary, neighbors, digest):
        folder = self.dist / name
        folder.mkdir()
        graph_fp = "sha256:" + digest * 64
        boundaries = {k: "sha256:" + c * 64 for k, c in neighbors.items()}
        doc = {
            "schema": "roadpilot-routing-pack",
            "regionId": name,
            "graphFingerprint": graph_fp,
            "source": {"primaryGeofabrikId": primary},
            "graphIndex": {
                "fileName": name + "-graph-index.json",
                "boundaryFingerprints": boundaries,
            },
        }
        path = folder / (name + "-2026-manifest.json")
        path.write_text(json.dumps(doc))
        (folder / (name + "-graph-index.json")).write_text("{}")
        return MODULE.Graph.from_manifest(path)

    def pair(self):
        a = self.graph("a", "source-a", {"source-b": "b"}, "a")
        b = self.graph("b", "source-b", {"source-a": "a"}, "b")
        return a, b

    def prepare_sources(self, a, b):
        cache = self.work / "cache"
        cache.mkdir(parents=True)
        for region in (a.region, b.region):
            (cache / (region + ".poly")).write_text("synthetic polygon")
        folder = self.work / a.region / "build"
        folder.mkdir(parents=True)
        (folder / "buffered.osm.pbf").write_bytes(b"synthetic, not real OSM")

    def test_only_mutually_covered_pairs_with_changed_region(self):
        a, b = self.pair()
        c = self.graph("c", "source-c", {}, "c")
        graphs = {x.region: x for x in (a, b, c)}
        self.assertEqual([(x.region, y.region)
                          for x, y in MODULE.discover_pairs(graphs)], [("a", "b")])
        self.assertEqual(MODULE.discover_pairs(graphs, {"c"}), [])
        self.assertEqual(len(MODULE.discover_pairs(graphs, {"b"})), 1)

    def test_latest_manifest_is_selected_instead_of_arbitrary_artifact(self):
        a, _ = self.pair()
        old = a.manifest_path
        newer = old.with_name("a-2027-manifest.json")
        newer.write_text(old.read_text().replace(a.fingerprint, "sha256:" + "f" * 64))
        self.assertEqual(MODULE.latest_graphs(self.dist)["a"].fingerprint,
                         "sha256:" + "f" * 64)

    def test_current_artifact_must_match_both_graphs_and_boundaries(self):
        a, b = self.pair()
        path = self.public / "a__b" / "runtime.json"
        path.parent.mkdir()
        data = {
            "schema": "roadpilot.runtime-connectivity",
            "validationState": "VALIDATED",
            "pairId": "a__b",
            "fromGraph": {"graphFingerprint": a.fingerprint},
            "toGraph": {"graphFingerprint": b.fingerprint},
            "fromBoundaryFingerprint": a.boundaries[b.primary],
            "toBoundaryFingerprint": b.boundaries[a.primary],
        }
        path.write_text(json.dumps(data))
        self.assertTrue(MODULE.is_current_runtime(path, a, b))
        for change in ("toBoundaryFingerprint", "validationState", "pairId"):
            bad = dict(data)
            bad[change] = "obsolete"
            path.write_text(json.dumps(bad))
            self.assertFalse(MODULE.is_current_runtime(path, a, b))

    def test_failure_preserves_existing_publication_and_graphs(self):
        a, b = self.pair()
        self.prepare_sources(a, b)
        existing = self.public / "a__b" / "runtime.json"
        existing.parent.mkdir()
        existing.write_text('{"old":"unchanged"}')
        original = a.manifest_path.read_bytes()
        with mock.patch.object(MODULE, "run_tool", side_effect=RuntimeError("Valhalla proof failed")):
            with self.assertRaisesRegex(RuntimeError, "Valhalla proof failed"):
                MODULE.build_pair(self.root / "tools", self.work, self.public, a, b,
                                  self.root / "staging")
        self.assertEqual(existing.read_text(), '{"old":"unchanged"}')
        self.assertEqual(a.manifest_path.read_bytes(), original)

    def test_full_stage_order_only_publishes_after_proofs_and_validation(self):
        a, b = self.pair()
        self.prepare_sources(a, b)
        calls = []
        def fake_run(tools, name, *args, **kwargs):
            calls.append(name)
            if "--output" not in args:
                return
            output = Path(args[args.index("--output") + 1])
            output.parent.mkdir(parents=True, exist_ok=True)
            result = {"stage": name}
            if name == "compile_runtime_connectivity":
                result.update({
                    "schema": "roadpilot.runtime-connectivity",
                    "validationState": "VALIDATED",
                    "pairId": "a__b",
                    "fromGraph": {"graphFingerprint": a.fingerprint},
                    "toGraph": {"graphFingerprint": b.fingerprint},
                    "fromBoundaryFingerprint": a.boundaries[b.primary],
                    "toBoundaryFingerprint": b.boundaries[a.primary],
                })
            output.write_text(json.dumps(result))
        with mock.patch.object(MODULE, "run_tool", side_effect=fake_run):
            output = MODULE.build_pair(self.root / "tools", self.work, self.public, a, b,
                                       self.root / "staging")
        self.assertEqual([name for name, _, _ in MODULE.STAGES],
                         [x.removeprefix("build_") for x in []] or
                         ["pair", "frontier", "correlations", "candidates", "proofs", "runtime"])
        self.assertEqual(len(calls), 12)
        self.assertEqual(calls[-2:], ["compile_runtime_connectivity",
                                     "validate_runtime_connectivity"])
        self.assertTrue(MODULE.is_current_runtime(output, a, b))
        for stage, _, _ in MODULE.STAGES:
            self.assertTrue((output.parent / (stage + ".json")).is_file())

    def test_no_graphs_means_no_downloads_or_graph_builds(self):
        self.assertEqual(MODULE.discover_pairs({}), [])
        self.assertEqual(MODULE.latest_graphs(self.dist), {})


if __name__ == "__main__":
    unittest.main()
