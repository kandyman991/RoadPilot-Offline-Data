"""Regression tests: catalog works without geometry/build dependencies or network."""
import json
import os
import tempfile
import time
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from tools import graph_studio_regions as catalog


def feature(region_id, parent, name, bbox, pbf=None, iso=None):
    x0, y0, x1, y1 = bbox
    properties = {"id": region_id, "parent": parent, "name": name}
    if pbf:
        properties["urls"] = {"pbf": pbf}
    if iso:
        properties["iso3166-1:alpha2"] = iso
    return {
        "type": "Feature",
        "properties": properties,
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]],
        },
    }


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.root = {
            "type": "FeatureCollection",
            "features": [
                feature("europe", "", "Europe", [0, 30, 30, 60]),
                feature("italy", "europe", "Italy", [6, 36, 19, 47],
                        "https://download.geofabrik.de/europe/italy-latest.osm.pbf", "IT"),
                feature("nord-est", "italy", "Nord-Est", [10, 44, 14, 47],
                        "https://download.geofabrik.de/europe/italy/nord-est-latest.osm.pbf"),
                feature("nord-ovest", "italy", "Nord-Ovest", [7, 44, 11, 47],
                        "https://download.geofabrik.de/europe/italy/nord-ovest-latest.osm.pbf"),
            ],
        }

    def test_catalog_uses_stdlib_and_resolves_leaf_extractions(self):
        # No Shapely, PyProj or build_routing_region import is needed for this call.
        items = catalog.catalog_payload(self.root)
        self.assertEqual({item["id"] for item in items},
                         {"italy/nord-est", "italy/nord-ovest"})
        nord_est = next(item for item in items if item["id"] == "italy/nord-est")
        self.assertEqual(nord_est["countryName"], "Italy")
        self.assertEqual(nord_est["bounds"],
                         {"minLat": 44.0, "maxLat": 47.0, "minLng": 10.0, "maxLng": 14.0})
        self.assertTrue(nord_est["polygonUrl"].endswith("/nord-est.poly"))

    def test_cached_index_remains_available_on_network_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            cached = Path(tmp) / "index-v1.json"
            cached.write_text(json.dumps(self.root), encoding="utf-8")
            old = time.time() - 2 * catalog.DEFAULT_CACHE_SECONDS
            os.utime(cached, (old, old))
            with patch("urllib.request.urlopen",
                       side_effect=urllib.error.URLError("offline")):
                result = catalog.load_index(Path(tmp), refresh=False)
                self.assertEqual(result, self.root)
                self.assertFalse((Path(tmp) / "index-v1.json.part").exists())

    def test_missing_index_has_actionable_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("urllib.request.urlopen",
                       side_effect=urllib.error.URLError("offline")):
                with self.assertRaises(SystemExit) as result:
                    catalog.load_index(Path(tmp), refresh=False)
                self.assertIn("Cannot download", str(result.exception))


if __name__ == "__main__":
    unittest.main()
