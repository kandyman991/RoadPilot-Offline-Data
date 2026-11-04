"""Fail-closed full ORIGINAL GraphReader tile census; no physical road dedup."""
from __future__ import annotations

import json
import sys
from pathlib import Path
import unittest

from shapely.geometry import box, Polygon

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from probe_native_f8_clipped_terminal import CRS
from census_native_f8_original_archive_tiles import (
    audit_stream, original_geojson_polygon, rectangles_from_original_buffer,
    serialize_rectangles, source_cut_observation, MAX_NATIVE_ROW_CHARS,
)


def original_buffer():
    x, y = CRS.transform(11.0, 47.0)
    return {"polygon": box(x-50, y-50, x+50, y+50),
            "sha256": "sha256:" + "a"*64}


def edge(gid=802, *, start_lon=10.998, end_lon=11.002, auto=True,
         motorcycle=True, is_road=True):
    return {
        "type": "candidate", "tileGraphId": 802,
        "originalDirectedGraphId": gid,
        "originalEndNodeGraphId": 300001,
        "forwardAccess": (1 if auto else 0) | (1024 if motorcycle else 0),
        "reverseAccess": 1025,
        "isRoad": is_road, "isShortcut": not is_road, "deadend": False,
        "wayIdAnnotationOnly": 53,
        "directedGeometry": [[47.0, start_lon], [47.0, end_lon]],
    }


def tile(n=2):
    return {"type": "tile", "tileGraphId": 802,
            "level": 2, "tileId": 100, "nodeCount": 2,
            "originalDirectedCount": n, "bboxCandidateCount": n}


def summary(total=2, bbox=2):
    return {"type": "summary", "valhallaVersion": "3.6.3",
            "archiveTileCount": 1, "allOriginalDirectedCount": total,
            "bboxCandidateCount": bbox}


def native_lines(*records):
    return [json.dumps(x)+"\n" for x in records]


class ArchiveOriginalSourceCutTests(unittest.TestCase):
    def test_all_native_edges_preserved_even_same_way_and_mode_fork(self):
        rows = native_lines(edge(), edge(802+(1<<25), auto=False, motorcycle=True,
                                         is_road=False), tile(), summary())
        result = audit_stream(rows, original_buffer())
        self.assertEqual(result["allOriginalDirectedEdgesEnumerated"], 2)
        self.assertEqual(result["archiveTileCount"], 1)
        self.assertEqual(result["originalDirectedCutShapeCount"], 2)
        a, b = result["allOriginalDirectedCutObservations"]
        self.assertNotEqual(a["originalDirectedGraphId"], b["originalDirectedGraphId"])
        self.assertEqual(a["originalWayIdAnnotationOnly"], b["originalWayIdAnnotationOnly"])
        self.assertFalse(b["nativeIsRoad"])
        self.assertFalse(b["vehicleModes"]["auto"])
        self.assertTrue(b["vehicleModes"]["motorcycle"])
        self.assertEqual(result["physicalRoadDirectionFinalEdge"], "NOT_VERIFIED")
        self.assertEqual(result["crossGraphMatching"], "NOT_STARTED")

    def test_real_original_zero_length_graphid_is_preserved_unresolved(self):
        original = edge()
        original["directedGeometry"] = [[43.571571, 11.864707],
                                        [43.571571, 11.864707]]
        result = audit_stream(native_lines(
            original, tile(n=1), summary(total=1,bbox=1)), original_buffer())
        self.assertEqual(result["allOriginalDirectedEdgesEnumerated"],1)
        self.assertEqual(result["originalDirectedCutShapeCount"],0)
        self.assertEqual(result["unresolvedOriginalNativeZeroLengthGeometryCount"],1)
        self.assertEqual(result["unresolvedOriginalNativeZeroLengthGeometries"][0][
            "originalDirectedGraphId"],original["originalDirectedGraphId"])

    def test_scan_may_have_zero_cut_hits_but_must_keep_full_inventory(self):
        r = audit_stream(native_lines(
            edge(start_lon=10.8, end_lon=10.9), tile(n=1), summary(total=1, bbox=1)),
            original_buffer())
        self.assertEqual(r["originalDirectedCutShapeCount"], 0)
        self.assertEqual(r["allOriginalDirectedEdgesEnumerated"], 1)

    def test_missing_tile_or_summary_rejected(self):
        for rows in (
            native_lines(edge(), summary()),
            native_lines(edge(), tile()),
            native_lines(tile(n=0)),
        ):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                audit_stream(rows, original_buffer())

    def test_duplicate_or_wrong_tile_graphids_rejected(self):
        corrupt = edge(802)
        corrupt["tileGraphId"] = 803
        for rows in (
            native_lines(corrupt, tile(n=1), summary(total=1,bbox=1)),
            native_lines(edge(), edge(), tile(), summary()),
            native_lines(edge(802+(2<<25)),tile(n=1),summary(total=1,bbox=1)),
        ):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                audit_stream(rows,original_buffer())

    def test_source_records_cannot_erase_source_scoped_mode_or_change_identity(self):
        for field, value in [
            ("forwardAccess", True),
            ("isRoad", 1),
            ("originalDirectedGraphId", "802"),
            ("originalEndNodeGraphId", -1),
        ]:
            corrupted=edge()
            corrupted[field]=value
            with self.subTest(field=field), self.assertRaises(ValueError):
                audit_stream(native_lines(corrupted,tile(n=1),summary(total=1,bbox=1)),
                             original_buffer())

    def test_wrong_count_and_missing_census_tail_fails(self):
        for t, ending in [
            (tile(n=1), summary(total=2,bbox=2)),
            (tile(n=3),summary(total=3,bbox=2)),
        ]:
            with self.assertRaises(ValueError):
                audit_stream(native_lines(edge(),edge(802+(1<<25)),t,ending),
                             original_buffer())

    def test_extra_records_and_truncated_or_huge_native_lines_rejected(self):
        for rows in (
            native_lines(edge(),tile(n=1),summary(total=1,bbox=1),{"type":"summary"}),
            ["x"*(MAX_NATIVE_ROW_CHARS+1)+"\n"],
            [json.dumps(edge())],
        ):
            with self.assertRaises(ValueError):
                audit_stream(rows,original_buffer())

    def test_segment_envelopes_cover_every_original_source_boundary_segment(self):
        polygon=Polygon([(10.99,46.99),(11.01,46.99),
                         (11.01,47.01),(10.99,47.01)])
        rects=rectangles_from_original_buffer(polygon)
        self.assertEqual(len(rects),4)
        for boxv in rects:
            self.assertLess(boxv[0],boxv[2])
            self.assertLess(boxv[1],boxv[3])
        raw=serialize_rectangles(rects)
        self.assertEqual(len(raw.splitlines()),4)

    def test_directional_cut_orientation_kept_separate(self):
        outward=edge(start_lon=10.998,end_lon=11.002)
        inward=edge(start_lon=11.002,end_lon=10.998)
        self.assertEqual(source_cut_observation(outward,original_buffer())[
            "originalSourceBufferCutDirectedTravel"],
            "BOTH_ENDPOINTS_OUTSIDE_BUFFER_CUT_INTERSECTION")
        self.assertEqual(source_cut_observation(inward,original_buffer())[
            "originalSourceBufferCutDirectedTravel"],
            "BOTH_ENDPOINTS_OUTSIDE_BUFFER_CUT_INTERSECTION")


if __name__ == "__main__":
    unittest.main()
