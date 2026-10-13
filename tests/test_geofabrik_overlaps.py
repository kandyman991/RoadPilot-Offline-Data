"""Austria regression: redundant Alps/DACH coverage + mixed OSM object versions."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from shapely.geometry import box
from tools.geofabrik_source_selection import choose_buffer_sources
from tools.osmium_source_merge import merge_current_osm_snapshot


class SourceCoverageTests(unittest.TestCase):
    def setUp(self):
        self.nominal = box(0, 0, 2, 2)
        self.buffer = box(-0.2, -0.2, 2.2, 2.2)
        self.polygons = {
            "west": box(-0.5, -0.5, 0, 2.5),
            "east": box(2, -0.5, 2.5, 2.5),
            "north": box(-0.5, 2, 2.5, 2.5),
            "south": box(-0.5, -0.5, 2.5, 0),
            "alps": box(-1, -1, 3, 3),
            "dach": box(-2, -2, 4, 4),
        }
        self.pbfs = [{"id": "austria", "url": "https://example.org/austria.osm.pbf"}] + [
            {"id": name, "url": f"https://example.org/{name}.osm.pbf"}
            for name in ("dach", "alps", "west", "east", "north", "south")
        ]

    def test_redundant_umbrella_extracts_not_downloaded(self):
        selected, skipped = choose_buffer_sources(
            self.pbfs, "austria", self.nominal, self.buffer, self.polygons,
        )
        self.assertEqual([p["id"] for p in selected],
                         ["austria", "east", "west", "north", "south"])
        self.assertEqual(set(skipped), {"dach", "alps"})

    def test_large_extract_kept_if_it_adds_unique_border_coverage(self):
        without_east = [p for p in self.pbfs if p["id"] != "east"]
        selected, _ = choose_buffer_sources(
            without_east, "austria", self.nominal, self.buffer, self.polygons,
        )
        self.assertIn("alps", [p["id"] for p in selected])

    def test_selection_requires_real_primary(self):
        with self.assertRaisesRegex(ValueError, "primary"):
            choose_buffer_sources(self.pbfs, "italy", self.nominal,
                                  self.buffer, self.polygons)


@unittest.skipUnless(shutil.which("osmium"), "Osmium installed in routing CI")
class OsmiumOverlapFixtureTests(unittest.TestCase):
    def test_different_osm_versions_do_not_break_extract(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pbfs = []
            for index, version in enumerate((1, 2)):
                xml = root / f"source{index}.osm"
                xml.write_text(
                    '<?xml version="1.0" encoding="UTF-8"?>\n'
                    '<osm version="0.6" generator="RoadPilot test">\n'
                    f'<node id="1" version="{version}" '
                    f'timestamp="2025-01-0{version}T12:00:00Z" '
                    f'lat="47.00" lon="13.00"/>\n'
                    f'<node id="2" version="{version}" '
                    f'timestamp="2025-01-0{version}T12:00:00Z" '
                    f'lat="47.01" lon="13.01"/>\n'
                    f'<way id="7" version="{version}" '
                    f'timestamp="2025-01-0{version}T12:00:00Z">'
                    '<nd ref="1"/><nd ref="2"/><tag k="highway" v="residential"/></way>\n'
                    '</osm>\n', encoding="utf-8",
                )
                pbf = root / f"source{index}.osm.pbf"
                subprocess.run(["osmium", "cat", str(xml), "-o", str(pbf)],
                               check=True, capture_output=True)
                pbfs.append(pbf)

            raw = root / "raw.osm.pbf"
            subprocess.run(["osmium", "merge", *map(str, pbfs), "-o", str(raw)],
                           check=True, capture_output=True)
            failed = subprocess.run(
                ["osmium", "extract", "--bbox", "12.99,46.99,13.02,47.02",
                 str(raw), "-o", str(root / "rawcut.osm.pbf")],
                capture_output=True, text=True,
            )
            self.assertNotEqual(failed.returncode, 0, failed.stderr)

            normalized = root / "normalized.osm.pbf"
            merge_current_osm_snapshot(pbfs, normalized)
            cut = root / "cut.osm.pbf"
            subprocess.run(
                ["osmium", "extract", "--bbox", "12.99,46.99,13.02,47.02",
                 "--strategy", "complete_ways", str(normalized),
                 "-o", str(cut)],
                check=True, capture_output=True, text=True,
            )
            subprocess.run(["osmium", "check-refs", str(cut)],
                           check=True, capture_output=True, text=True)


if __name__ == "__main__":
    unittest.main()
