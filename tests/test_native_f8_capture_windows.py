"""Synthetic tests for the read-only uncapped native graph window producer."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from shapely.geometry import box

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from capture_native_f8_graph_windows import (
    make_capture, overlap_windows, positive_window_degrees, scan_window, PORT
)
from unittest.mock import patch
from types import SimpleNamespace


class NativeF8CaptureWindowsTests(unittest.TestCase):
    def test_entire_intersection_is_windowed_including_second_carriageway(self):
        a, b = box(10, 45, 10.08, 45.08), box(10.02, 45.02, 10.10, 45.10)
        windows = list(overlap_windows(a, b, 0.02))
        self.assertGreaterEqual(len(windows), 9)
        self.assertTrue(any(w["minLon"] <= 10.02 < w["maxLon"] for w in windows))
        self.assertTrue(any(w["minLon"] <= 10.06 < w["maxLon"] for w in windows))
        self.assertTrue(all(w["maxLat"] > w["minLat"] for w in windows))

    def test_disjoint_shared_graph_buffers_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "no area overlap"):
            list(overlap_windows(box(0, 0, 1, 1), box(2, 2, 3, 3), 0.02))

    def test_no_silent_f8_source_budget_or_nonfinite_window_degree(self):
        for value in (0, float("nan"), 0.5, float("inf"), -1):
            with self.assertRaises(ValueError):
                positive_window_degrees(value)

    def test_real_f8_reference_identity_never_claimed_from_port(self):
        graph_a = {"regionId": "a", "packageVersion": "1", "graphFingerprint": "g1",
                   "primaryGeofabrikId": "a"}
        graph_b = {"regionId": "b", "packageVersion": "1", "graphFingerprint": "g2",
                   "primaryGeofabrikId": "b"}
        correlations = {"schema": "roadpilot.frontier-road-correlations",
                        "pairId": "a__b", "fromGraph": graph_a, "toGraph": graph_b,
                        "fromBoundaryFingerprint": "x", "toBoundaryFingerprint": "y"}
        capture = make_capture(
            correlations=correlations, graph_identity_a=graph_a,
            graph_identity_b=graph_b, from_scan={"windows": [], "edges": []},
            to_scan={"windows": [], "edges": []}, window_degrees=0.02)
        self.assertEqual(capture["scanner"], PORT)
        self.assertFalse(capture["nativeF8ReferenceCaptured"])
        self.assertEqual(capture["f8GraphEdgeParity"], "NOT_VERIFIED")
        self.assertEqual(capture["provenHandoffs"], [])
        graph_a = {**graph_a, "graphFingerprint": "stale"}
        with self.assertRaisesRegex(ValueError, "Stale fromGraph.graphFingerprint"):
            make_capture(correlations=correlations, graph_identity_a=graph_a,
                         graph_identity_b=graph_b, from_scan={},
                         to_scan={}, window_degrees=0.02)

    def test_native_cli_must_report_uncapped_no_false_success(self):
        raw = ('{"schema":"roadpilot.graph-studio-native-edge-window","version":1,'
               '"scanner":"GraphStudio.nativeUncappedRoadEdges","complete":true,'
               '"truncated":false,"maxResults":null,"returned":2,"visitedTiles":1,'
               '"visitedNodes":2,"edges":[{"graphId":101},{"graphId":102}]}')
        with patch("capture_native_f8_graph_windows.subprocess.run",
                   return_value=SimpleNamespace(returncode=0, stdout=raw, stderr="")):
            value = scan_window(Path("/bin/native"), Path("/tmp/config"), {
                "minLat": 45., "maxLat": 45.01, "minLon": 10., "maxLon": 10.01})
        self.assertEqual(value["returned"], 2)
        self.assertEqual(value["edges"][1]["graphId"], 102)

        for changed in (raw.replace('"returned":2', '"returned":1'),
                        raw.replace('"truncated":false', '"truncated":true'),
                        raw.replace('"maxResults":null', '"maxResults":512'),
                        raw.replace('"graphId":102', '"graphId":101')):
            with patch("capture_native_f8_graph_windows.subprocess.run",
                       return_value=SimpleNamespace(returncode=0, stdout=changed, stderr="")):
                with self.assertRaises(ValueError):
                    scan_window(Path("/bin/native"), Path("/tmp/config"), {
                        "minLat": 45., "maxLat": 45.01, "minLon": 10., "maxLon": 10.01})


if __name__ == "__main__":
    unittest.main()
