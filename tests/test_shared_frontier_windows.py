import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "frontier",
    ROOT / "tools" / "build_shared_frontier_windows.py",
)
frontier = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(frontier)


class SharedFrontierWindowsTest(unittest.TestCase):
    def setUp(self):
        self.index = json.loads(
            (ROOT / "tests/fixtures/geofabrik-adjacent-polygons.json").read_text()
        )
        self.config = {
            "schemaVersion": 1,
            "id": "a__b",
            "fromRegionId": "a",
            "toRegionId": "b",
            "fromPbfUrl": "https://example.test/a-latest.osm.pbf",
            "toPbfUrl": "https://example.test/b-latest.osm.pbf",
            "frontierSearch": {
                "sampleSpacingMeters": 5000.0,
                "neighborDistanceMeters": 6000.0,
                "windowRadiusMeters": 7000.0,
            },
            "candidateSearch": {"maxSeparationMeters": 80.0},
        }

    def test_builds_windows_along_the_entire_shared_edge(self):
        result = frontier.build_windows(self.index, self.config)
        self.assertGreater(len(result["windows"]), 5)
        self.assertGreater(result["sampling"]["pairedSamples"], 10)

        # The shared longitude is 11° from latitude 47° through 48°. Every quarter
        # of that boundary must fall inside at least one emitted scan window.
        for lat in (47.0, 47.25, 47.5, 47.75, 48.0):
            self.assertTrue(
                any(
                    window["minLat"] <= lat <= window["maxLat"]
                    and window["minLng"] <= 11.0 <= window["maxLng"]
                    for window in result["windows"]
                ),
                f"shared frontier point {lat},11.0 is not covered",
            )

    def test_non_neighboring_polygons_fail_closed(self):
        shifted = json.loads(json.dumps(self.index))
        coords = shifted["features"][1]["geometry"]["coordinates"][0]
        for coordinate in coords:
            coordinate[0] += 5.0
        with self.assertRaises(ValueError):
            frontier.build_windows(self.index | {"features": shifted["features"]}, self.config)


if __name__ == "__main__":
    unittest.main()
