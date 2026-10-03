import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "candidate_builder",
    ROOT / "tools" / "build_routing_transition_candidates.py",
)
builder = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(builder)


class TransitionCandidateBuilderTest(unittest.TestCase):
    def setUp(self):
        self.a = json.loads(
            (ROOT / "tests/fixtures/austria-boundary-inventory.json").read_text()
        )
        self.b = json.loads(
            (ROOT / "tests/fixtures/oberbayern-boundary-inventory.json").read_text()
        )
        self.cfg = json.loads(
            (
                ROOT
                / "config/routing-pairs/geofabrik-austria__geofabrik-oberbayern.json"
            ).read_text()
        )

    def test_keeps_motorway_when_refs_and_way_ids_change_at_border(self):
        catalog = builder.build_candidates(self.a, self.b, self.cfg)
        motorway = [
            candidate
            for candidate in catalog["candidates"]
            if "A12" in candidate["fromEdge"]["roadRefs"]
            and "A93" in candidate["toEdge"]["roadRefs"]
        ]
        self.assertEqual(1, len(motorway))
        self.assertIn("SPATIAL_PROXIMITY", motorway[0]["matchEvidence"])
        self.assertNotIn("SAME_OSM_WAY", motorway[0]["matchEvidence"])
        builder.verify_regression_anchors(catalog, self.cfg)

    def test_same_osm_way_is_strong_evidence_but_not_required(self):
        catalog = builder.build_candidates(self.a, self.b, self.cfg)
        b171 = [
            candidate
            for candidate in catalog["candidates"]
            if candidate["fromEdge"]["wayId"] == 9101
            and candidate["toEdge"]["wayId"] == 9101
        ]
        self.assertEqual(1, len(b171))
        self.assertIn("SAME_OSM_WAY", b171[0]["matchEvidence"])

    def test_heading_never_hard_rejects_candidate(self):
        self.b["edges"][0]["headingDegrees"] = 185.0
        catalog = builder.build_candidates(self.a, self.b, self.cfg)
        self.assertTrue(
            any(
                "A12" in candidate["fromEdge"]["roadRefs"]
                for candidate in catalog["candidates"]
            )
        )

    def test_no_common_motorized_mode_rejects_candidate(self):
        self.b["edges"][0]["allowedTravelModes"] = []
        catalog = builder.build_candidates(self.a, self.b, self.cfg)
        self.assertFalse(
            any(
                "A12" in candidate["fromEdge"]["roadRefs"]
                for candidate in catalog["candidates"]
            )
        )

    def test_directional_pair_has_distinct_candidate_identity(self):
        forward = builder.build_candidates(self.a, self.b, self.cfg)
        reverse_cfg = json.loads(
            (
                ROOT
                / "config/routing-pairs/geofabrik-oberbayern__geofabrik-austria.json"
            ).read_text()
        )
        reverse = builder.build_candidates(self.b, self.a, reverse_cfg)
        forward_motorway = next(
            candidate
            for candidate in forward["candidates"]
            if "A12" in candidate["fromEdge"]["roadRefs"]
            and "A93" in candidate["toEdge"]["roadRefs"]
        )
        reverse_motorway = next(
            candidate
            for candidate in reverse["candidates"]
            if "A93" in candidate["fromEdge"]["roadRefs"]
            and "A12" in candidate["toEdge"]["roadRefs"]
        )
        self.assertNotEqual(forward_motorway["id"], reverse_motorway["id"])
        builder.verify_regression_anchors(reverse, reverse_cfg)


if __name__ == "__main__":
    unittest.main()
