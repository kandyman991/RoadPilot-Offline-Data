"""Source native original directed full cut-first completeness regression gates."""
from __future__ import annotations

import sys
from pathlib import Path
import unittest

from shapely.geometry import box

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from probe_native_f8_clipped_terminal import CRS
from census_native_f8_original_source_cut_edges import check_native_directed_shape


def original(gid=111, way=30):
    return {"graphId":gid,"wayId":way,"forwardAccess":1025,
            "reverseAccess":0}


def native(gid=111, way=30, vertices=None):
    return {
        "sourceGraphId":gid,"wayId":way,
        "forwardAccess":1025,"reverseAccess":0,
        "endNodeGraphId":333,"forward":True,"deadend":False,
        "directedGeometry":vertices if vertices is not None
        else [[47.,11.],[47.,11.002]],
    }


def own():
    x,y=CRS.transform(11.,47.)
    return {"polygon":box(x-20,y-50,x+20,y+50)}


class OriginalNativeSourceCutTests(unittest.TestCase):
    def test_actual_full_original_directed_geometry_reports_outward(self):
        row=check_native_directed_shape(original(),native(),own())
        self.assertEqual(row["originalSourceBufferCutDirectedTravel"],
                         "OUTWARD_FROM_ORIGINAL_SOURCE_BUFFER")
        self.assertEqual(row["originalDirectedGraphId"],111)
        self.assertTrue(row["nativeDirectedStartInsideOwn25kmBuffer"])
        self.assertFalse(row["nativeDirectedEndInsideOwn25kmBuffer"])
        self.assertFalse(row["candidateSuppressed"])
        self.assertEqual(row["physicalRoadDirectionEquivalence"],"NOT_VERIFIED")

    def test_reverse_original_directed_shape_is_inward_not_outward(self):
        row=check_native_directed_shape(
            original(),native(vertices=[[47.,11.002],[47.,11.]]),own())
        self.assertEqual(row["originalSourceBufferCutDirectedTravel"],
                         "INWARD_TOWARD_ORIGINAL_SOURCE_BUFFER")
        self.assertFalse(row["nativeDirectedStartInsideOwn25kmBuffer"])
        self.assertTrue(row["nativeDirectedEndInsideOwn25kmBuffer"])

    def test_two_cut_intersections_are_explicitly_ambiguous(self):
        row=check_native_directed_shape(original(),native(vertices=[
            [47.,11.],[47.,11.002],[47.,11.]]),own())
        self.assertEqual(row["originalSourceBufferCutDirectedTravel"],
                         "BOTH_ENDPOINTS_WITHIN_BUFFER_CUT_INTERSECTION")
        row=check_native_directed_shape(original(),native(vertices=[
            [47.,10.997],[47.,11.],[47.,11.003]]),own())
        self.assertEqual(row["originalSourceBufferCutDirectedTravel"],
                         "BOTH_ENDPOINTS_OUTSIDE_BUFFER_CUT_INTERSECTION")

    def test_no_crossing_is_none_not_claimed_retained_final(self):
        self.assertIsNone(check_native_directed_shape(
            original(),native(vertices=[[47.,11.],[47.,11.0001]]),own()))

    def test_same_way_distinct_native_graphids_not_merged(self):
        x=check_native_directed_shape(original(111),native(111),own())
        y=check_native_directed_shape(original(222),native(222),own())
        self.assertNotEqual(x["originalDirectedGraphId"],y["originalDirectedGraphId"])
        self.assertEqual(x["originalWayIdAnnotationOnly"],y["originalWayIdAnnotationOnly"])

    def test_invalid_geometry_identity_and_access_fail_closed(self):
        variants=(
            {**native(),"sourceGraphId":999},
            {**native(),"wayId":31},
            {**native(),"forwardAccess":1},
            {**native(),"reverseAccess":1025},
            {**native(),"forward":"true"},
            {**native(),"endNodeGraphId":0},
            {**native(),"directedGeometry":[]},
            {**native(),"directedGeometry":[[47.,11.]]},
            {**native(),"directedGeometry":[[47.,11.],[float("nan"),11.]]},
            {**native(),"directedGeometry":[[47.,11.],[47.,200.]]},
            {**native(),"directedGeometry":[[47.,11.],[47.,11.]]},
        )
        for row in variants:
            with self.subTest(row=row),self.assertRaises(ValueError):
                check_native_directed_shape(original(),row,own())


if __name__=="__main__":
    unittest.main()
