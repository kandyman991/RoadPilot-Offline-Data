"""Fresh F8 original full-source census contracts.

The native C++ scanner visits every original GraphReader tile and directed
index. Tests focus on false negatives: a legitimate original final that is
not is_road, a peer buffer overlap outside peer nominal territory, and a
real outbound cut direction. No OSM-way grouping, arbitrary continuation
walk, or unverified release is permitted.
"""
from __future__ import annotations
import math
from pathlib import Path
import sys
import tempfile
import unittest

from pyproj import Transformer
from shapely.geometry import box

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from census_f8_original_source_after_build import (
    classify_near_cut,buffered_seam_cells,METRIC,BAND_METRES
)


class OriginalSourceNativeCensusTests(unittest.TestCase):
    def setUp(self):
        self.lat,self.lon=46.0,11.0
        self.x,self.y=METRIC.transform(self.lon,self.lat)
        self.own={"polygon":box(self.x-1000,self.y-1000,self.x,self.y+1000)}
        self.peer={"polygon":box(self.x-100,self.y-1100,self.x+1500,self.y+1100)}
        self.receiver_nominal=box(self.x+800,self.y-1000,self.x+1200,self.y+1000)
        self.start=Transformer.from_crs("EPSG:3035","EPSG:4326",always_xy=True).transform(
            self.x-20,self.y)
        self.end=Transformer.from_crs("EPSG:3035","EPSG:4326",always_xy=True).transform(
            self.x+25,self.y)
        self.row={
            "originalDirectedGraphId":15001,
            "originalEndNodeGraphId":25002,
            "originalWayIdAnnotationOnly":335,
            "directedStart":[self.start[1],self.start[0]],
            "directedEnd":[self.end[1],self.end[0]],
            "nativeDeadend":True,
            "nativeIsRoad":False,
            "nativeUse":0,
            "forwardAccess":1|1024,
        }

    def test_actual_original_bilateral_overlap_not_peer_nominal_border(self):
        # A real graph-pair seam may be inside both 25-km buffers without
        # touching the second country's nominal core.
        row=classify_near_cut(self.row,self.own,self.peer,self.receiver_nominal)
        self.assertIsNotNone(row)
        self.assertEqual(row["originalDirectedGraphId"],15001)
        self.assertEqual(row["travelModes"],["auto","motorcycle"])
        self.assertEqual(row["outwardSourceCutClassification"],
                         "OUTWARD_CROSSING_OWN_SOURCE_25KM_CUT")
        self.assertFalse(row["nativeOriginalIsRoadAnnotationOnly"])
        self.assertFalse(row["insideReceivingNominalCoreAnnotationOnly"])
        self.assertTrue(row["insideReceivingOriginal25kmBuffer"])
        self.assertEqual(row["nativeSourceLastTripLeg"],"NOT_YET_PROVED")

    def test_other_region_native_road_is_never_accepted(self):
        other={"polygon":box(self.x+2000,self.y-1000,self.x+3000,self.y+1000)}
        self.assertIsNone(classify_near_cut(
            self.row,self.own,other,self.receiver_nominal))

    def test_unrelated_native_inside_continuation_not_development_requirement(self):
        row=dict(self.row)
        row["directedEnd"]=[self.start[1],self.start[0]]
        row["nativeDeadend"]=False
        self.assertIsNone(classify_near_cut(
            row,self.own,self.peer,self.receiver_nominal))
        # A real source-local deadend just before the cut is retained
        # separately, but never called an original A-LAST route proof.
        row["nativeDeadend"]=True
        terminal=classify_near_cut(row,self.own,self.peer,self.receiver_nominal)
        self.assertEqual(terminal["outwardSourceCutClassification"],
                         "NEAR_SOURCE_CUT_INSIDE_NATIVE_TERMINAL_UNPROVED")

    def test_seam_grid_does_not_truncate_nominally_outside_receiving_core(self):
        cells=buffered_seam_cells(self.own,self.peer)
        self.assertTrue(cells)
        self.assertLess(len(cells),200000)
        grid=(math.floor(self.end[1]/0.01),math.floor(self.end[0]/0.01))
        self.assertIn(grid,cells)

    def test_census_contract_source_code_keeps_all_mode_accessible_nonshortcuts(self):
        cpp=(Path(__file__).resolve().parents[1]/"tools"/
             "native-f8-full-receiver"/"native_f8_full_source_cut_edges.cpp").read_text()
        self.assertIn("const auto all=reader.GetTileSet();",cpp)
        self.assertIn("++all_directed;",cpp)
        self.assertIn("edge->is_shortcut()",cpp)
        self.assertNotIn("if (!edge->is_road() ||",cpp)
        self.assertIn("nativeIsRoad",cpp)
        self.assertIn("allGraphReaderTilesExhaustivelyRead",cpp)
        self.assertIn("PARTIAL_OUTPUT_INVALID",cpp)


if __name__=="__main__":
    unittest.main()
