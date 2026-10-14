"""Regression: F8-inspired discovery must not freeze at nominal-border or first road.

No PBF downloads or Valhalla runtime required for source-coverage tests.
These tests do NOT claim graph-edge completeness: they cover the OSM candidate
enumeration foundation and explicit provenance only.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_frontier_road_inventory as inv


def polygon(path: Path, left: float, right: float):
    path.write_text(json.dumps({
        "type": "Polygon",
        "coordinates": [[[left, 0], [right, 0], [right, 2],
                         [left, 2], [left, 0]]]
    }))


def way(way_id: int, coords, name: str = "Same road"):
    return {"type": "Feature", "id": f"w{way_id}",
            "properties": {"highway": "primary", "name": name, "ref": "B99"},
            "geometry": {"type": "LineString", "coordinates": coords}}


class F8OverlapDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.a = self.root / "a.pbf"
        self.b = self.root / "b.pbf"
        for src in (self.a, self.b):
            src.write_bytes(b"test")
        self.polygon_a = self.root / "a.geojson"
        self.polygon_b = self.root / "b.geojson"
        self.buffer_a = self.root / "buf_a.geojson"
        self.buffer_b = self.root / "buf_b.geojson"
        polygon(self.polygon_a, 0, 1)
        polygon(self.polygon_b, 1, 3)
        polygon(self.buffer_a, 0, 1.7)
        polygon(self.buffer_b, 0.6, 3)
        self.pair = {"pairId": "region-a__region-b",
                     "fromRegionId": "region-a",
                     "toRegionId": "region-b",
                     "fromBoundaryFingerprint": "sha256:" + "a" * 64,
                     "toBoundaryFingerprint": "sha256:" + "b" * 64}

    def inventory(self, samples):
        def exporter(src: Path, work: Path) -> Path:
            work.mkdir(parents=True, exist_ok=True)
            dest = work / "highways.geojsonseq"
            dest.write_text("\n".join(json.dumps(item) for item in samples[src]) + "\n")
            return dest
        with patch.object(inv, "export_highways", side_effect=exporter):
            return inv.build_inventory(
                self.pair, self.polygon_a, self.polygon_b,
                self.a, self.buffer_a, self.buffer_b, self.b)

    def test_both_source_packs_extend_beyond_nominal_crossing(self):
        # Neither way crosses the nominal border x=1.0; both physically
        # exist where Graph A and B buffers overlap.
        result = self.inventory({
            self.a: [way(101, [[1.2, 0.3], [1.3, 0.3]])],
            self.b: [way(102, [[1.35, 0.7], [1.45, 0.7]])],
        })
        self.assertEqual({road["wayId"] for road in result["roads"]}, {101, 102})
        self.assertEqual({road["crossingKind"] for road in result["roads"]},
                         {"OVERLAP_ROAD"})
        self.assertEqual(result["discovery"]["scope"], "OSM_BUFFER_OVERLAP")
        self.assertTrue(result["discovery"]["sourceExhausted"])
        self.assertEqual(result["discovery"]["f8GraphEdgeParity"], "NOT_VERIFIED")

    def test_same_name_ref_distinct_ways_and_multiple_locations_preserved(self):
        # Same highway/ref may have disconnected exits/carriageways.
        first = way(201, [[0.95, 0.3], [1.1, 0.3]])
        second = way(202, [[1.15, 0.3], [1.4, 0.3]])
        result = self.inventory({self.a: [first, second],
                                 self.b: [first, second]})
        self.assertEqual({item["wayId"] for item in result["roads"]}, {201, 202})
        self.assertEqual(len({item["id"] for item in result["roads"]}),
                         len(result["roads"]))
        self.assertTrue(any(x["crossingKind"] == "CROSSING" for x in result["roads"]))
        self.assertTrue(any(x["crossingKind"] == "OVERLAP_ROAD" for x in result["roads"]))

    def test_different_fragments_of_same_way_across_sources_are_not_discarded(self):
        result = self.inventory({
            self.a: [way(303, [[0.7, 1], [0.8, 1]])],
            self.b: [way(303, [[1.3, 1], [1.4, 1]])]
        })
        anchors = [item for item in result["roads"] if item["wayId"] == 303]
        self.assertGreaterEqual(len(anchors), 2)
        self.assertEqual(len({item["crossingIndex"] for item in anchors}), len(anchors))

    def test_exhaustive_source_marker_never_claims_f8_graph_edge_parity(self):
        result = self.inventory({self.a: [], self.b: []})
        self.assertEqual(result["discovery"]["scope"], "OSM_BUFFER_OVERLAP")
        self.assertEqual(result["roads"], [])
        self.assertEqual(result["discovery"]["f8GraphEdgeParity"], "NOT_VERIFIED")


if __name__ == "__main__":
    unittest.main()
