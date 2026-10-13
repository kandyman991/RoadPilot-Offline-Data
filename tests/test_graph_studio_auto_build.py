"""Offline tests for automatic region setup and Valhalla crossing proof."""
import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from shapely.geometry import box
from tools.auto_boundary_routes import (
    boundary_candidates, decode_polyline6, discover_border_route, prove_crossing,
)


def encode_polyline6(positions):
    values = []
    previous_lat = previous_lng = 0
    for lng, lat in positions:
        y, x = round(lat * 1_000_000), round(lng * 1_000_000)
        for diff in (y - previous_lat, x - previous_lng):
            n = (diff << 1) if diff >= 0 else (~diff << 1) | 1
            while n >= 32:
                values.append(chr((32 | (n & 31)) + 63))
                n >>= 5
            values.append(chr(n + 63))
        previous_lat, previous_lng = y, x
    return "".join(values)


class AutomaticBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.nominal = box(-1, -1, 1, 1)
        self.neighbor = box(1, -1, 2, 1)

    def test_real_geographic_pairs_straddle_nominal_border_and_neighbor(self):
        pairs = list(boundary_candidates(self.nominal, 25,
                                         neighbor_geometries=[self.neighbor], maximum=40))
        self.assertGreater(len(pairs), 0)
        for inside, outside in pairs:
            self.assertLess(inside["lng"], 1)
            self.assertGreater(outside["lng"], 1)

    def test_decode_polyline6_and_prove_crossing_from_actual_road_shape(self):
        vertices = [(0.99, 0.0), (1.01, 0.0)]
        encoded = encode_polyline6(vertices)
        self.assertEqual(decode_polyline6(encoded), vertices)
        response = {"trip": {"status": 0, "summary": {"length": 2.0},
                             "legs": [{"shape": encoded}]}}
        start = {"lat": 0, "lng": 0.99}
        end = {"lat": 0, "lng": 1.01}
        self.assertTrue(prove_crossing(response, self.nominal, start, end))
        self.assertFalse(prove_crossing(
            {"trip": {"status": 0, "legs": [{"shape": encode_polyline6(
                [(0.97, 0), (0.99, 0)])}]}}, self.nominal, start, end
        ))

    def test_automatic_discovery_only_accepts_valhalla_proven_road(self):
        def good_service(request):
            a, b = request["locations"]
            vertices = [(a["lon"], a["lat"]), (b["lon"], b["lat"])]
            return {"trip": {"status": 0, "summary": {"length": 4.0},
                             "legs": [{"shape": encode_polyline6(vertices)}]}}
        result = discover_border_route("mock", self.nominal, 25,
                                       neighbor_geometries=[self.neighbor],
                                       max_probes=50, run_service=good_service)
        self.assertEqual(result["source"], "automatic-valhalla-proof")
        self.assertTrue(result["passed"])
        self.assertEqual(result["kind"], "border")
        self.assertLess(result["start"]["lng"], 1)
        self.assertGreater(result["end"]["lng"], 1)

    def test_no_valhalla_proof_stops_publication(self):
        with self.assertRaisesRegex(RuntimeError, "No unvalidated routing package"):
            discover_border_route("mock", self.nominal, 25,
                                  neighbor_geometries=[self.neighbor],
                                  max_probes=2, run_service=lambda _: None)

    def test_only_auto_mode_may_omit_border_route(self):
        config_path = Path("config/regions/italy-nord-est.json")
        original = json.loads(config_path.read_text(encoding="utf-8"))
        auto = copy.deepcopy(original)
        auto["routing"]["validationMode"] = "auto"
        auto["routing"]["validationRoutes"] = []
        auto["visual"] = {"enabled": False}
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "region.json"
            target.write_text(json.dumps(auto), encoding="utf-8")
            validation = subprocess.run(
                ["python", "tools/validate_region_config.py", "--config", str(target)],
                text=True, capture_output=True,
            )
            self.assertEqual(validation.returncode, 0, validation.stderr)
            auto["routing"]["validationMode"] = "manual"
            target.write_text(json.dumps(auto), encoding="utf-8")
            validation = subprocess.run(
                ["python", "tools/validate_region_config.py", "--config", str(target)],
                text=True, capture_output=True,
            )
            self.assertNotEqual(validation.returncode, 0)


if __name__ == "__main__":
    unittest.main()
