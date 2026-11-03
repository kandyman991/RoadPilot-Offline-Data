"""Full directed geometry observations must not imply legal graph handoffs."""
from __future__ import annotations

import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from probe_native_f8_terminal_geometry import (
    checked_edge, inspect_geometry, nearest, tail_points,
)


def edge(graph_id, vertices, *, way=42, access=1025):
    return {
        "sourceGraphId": graph_id, "wayId": way, "forwardAccess": access,
        "endLat": vertices[-1][0], "endLon": vertices[-1][1],
        "directedGeometry": vertices,
    }


A = edge(11, [[0, 0], [0, 0.0005]])


class FullDirectedGeometryTests(unittest.TestCase):
    def test_different_node_division_does_not_hide_same_physical_road(self):
        receiver = edge(22, [[0, 0.0001], [0, 0.001]])
        report = inspect_geometry(A, [receiver], "motorcycle")
        self.assertEqual(report["sourceTailRequestedMetres"], 20.)
        self.assertEqual(report["sourceTailActualMetres"], 20.)
        self.assertEqual(report["tailSampleCount"],
                         report["tailSamplesWithinOneMetreOfSelectedGeometry"])
        self.assertEqual(report["receiverObservations"][0]["sourceEndpointToReceiverPolylineMeters"], 0.)
        self.assertGreater(report["receiverObservations"][0][
            "sourceEndpointToReceiverEndNodeMeters"], 50.)
        self.assertEqual(report["crossGraphPhysicalContinuity"], "NOT_VERIFIED")
        self.assertEqual(report["crossSeamTurnLegality"], "NOT_VERIFIED")
        self.assertEqual(report["productionPublication"], "BLOCKED")

    def test_opposite_direction_is_observed_not_silently_rejected(self):
        receiver = edge(22, [[0, 0.001], [0, 0.0001]])
        report = inspect_geometry(A, [receiver], "auto")
        self.assertEqual(report["receiverObservations"][0][
            "sourceVsReceiverDirectedTangentCosine"], -1.)
        self.assertEqual(report["tailSampleCount"],
                         report["tailSamplesWithinOneMetreOfSelectedGeometry"])
        self.assertEqual(report["crossGraphPhysicalContinuity"], "NOT_VERIFIED")

    def test_all_parallel_and_split_edges_stay_in_report(self):
        rows = [
            edge(24, [[0.00018, 0.0001], [0.00018, 0.001]], way=99),
            edge(22, [[0, 0.0002], [0, 0.0004]], way=123),
            edge(23, [[0, 0.0004], [0, 0.001]], way=42),
        ]
        report = inspect_geometry(A, rows, "auto")
        self.assertEqual([r["receiverDirectedGraphId"] for r in report[
            "receiverObservations"]], [22, 23, 24])
        self.assertEqual(report["tailSampleCount"],
                         report["tailSamplesWithinOneMetreOfSelectedGeometry"])
        self.assertTrue(report["receiverObservations"][0][
            "sourceWayAndReceiverWayIdEqual"] is False)
        self.assertFalse(report["receiverObservations"][2][
            "terminalGeometryWithinOneMetre"])
        self.assertEqual(report["receiverSelection"], "EXPLICIT_GRAPH_LOCAL_IDS_NOT_EXHAUSTIVE")

    def test_distant_receiver_remains_unresolved(self):
        report = inspect_geometry(A, [edge(22, [[0.001, 0], [0.001, .001]])], "auto")
        self.assertEqual(report["tailSamplesWithinOneMetreOfSelectedGeometry"], 0)
        self.assertEqual(report["tailGeometryObservation"],
                         "UNRESOLVED_FOR_SELECTED_RECEIVER_EDGES")
        self.assertEqual(report["coverage"], "NOT_VERIFIED")

    def test_mode_access_not_equal_to_legality(self):
        report = inspect_geometry(A, [edge(22, [[0, 0], [0, .001]], access=1)], "motorcycle")
        self.assertFalse(report["receiverObservations"][0]["modeForwardAccess"])
        self.assertEqual(report["crossSeamTurnLegality"], "NOT_VERIFIED")

    def test_corrupted_native_geometry_fails_closed(self):
        for raw in (
            edge(22, [[0, 0.001], [0, float("nan")]]),
            {**edge(22, [[0, 0], [0, 0.001]]), "endLat": .001},
            edge(22, [[0, 0]]),
            {**edge(22, [[0, 0], [0, 0.001]]), "forwardAccess": True},
        ):
            with self.assertRaises(ValueError):
                checked_edge(raw)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            inspect_geometry(A, [edge(22, [[0, 0], [0, .001]])] * 2, "auto")

    def test_native_reader_full_geometry_opt_in_and_existing_modes_preserved(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "tools/native-f8-edge-scan/native_f8_directed_endpoints.cpp").read_text()
        self.assertIn('include_geometry', source)
        self.assertIn('"--geometry"', source)
        self.assertIn('"--continuations"', source)
        self.assertIn("if (!edge->forward()) std::reverse(shape.begin(), shape.end())", source)
        self.assertIn("PARTIAL_STDOUT_MUST_BE_DISCARDED", source)
        for retired in ("build_frontier_road_inventory", "build_region_connector_matrix",
                        "plan_multiregion_route"):
            self.assertNotIn(retired, source)

    def test_short_terminal_and_curved_polyline(self):
        source = edge(11, [[0, 0], [.00001, .00001], [.00002, .00002]])
        samples = tail_points(checked_edge(source)["directedGeometry"])
        self.assertGreater(len(samples), 1)
        self.assertLess(inspect_geometry(source, [
            edge(11, [[0, 0], [.00001, .00001], [.00003, .00003]])
        ], "auto")["sourceTailActualMetres"], 5.)
        match = checked_edge(edge(23, [[0, 0], [.00001, .00001], [.00003, .00003]]))
        p = nearest({"lat": .00002, "lng": .00002}, match["directedGeometry"])
        self.assertLess(p["metres"], .1)


if __name__ == "__main__":
    unittest.main()
