"""Regressions for the read-only terminal evidence audit (NOT a handoff producer)."""
from __future__ import annotations

import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from audit_native_f8_terminal_evidence import audit_side, native_endpoints_to_observations


def edge(graph_id, way_id=99):
    return {"graphId": graph_id, "wayId": way_id, "forwardAccess": 2031, "reverseAccess": 2031}


def endpoint(graph_id, *, matched=True, dead_end=True):
    record = {"g": graph_id, "id": matched}
    if matched:
        record.update(e=[46.5, 13.7], d=dead_end, n=False)
    return record


def continuation(graph_id, *, found=True, continues=True):
    return {"g": graph_id, "found": found, "cont": continues}


class TerminalEvidenceAuditTests(unittest.TestCase):
    def test_unproven_terminal_observations_same_way_are_not_collapsed(self):
        result = audit_side(
            [edge(1), edge(2), edge(3)],
            [endpoint(1), endpoint(2), endpoint(3, dead_end=False)],
            [continuation(1), continuation(2)], "from", include_candidates=True)
        self.assertEqual(result["provisionalTerminalEdges"], 2)
        self.assertEqual([c["sourceGraphId"] for c in result["candidates"]], [1, 2])
        self.assertEqual([c["sourceWayId"] for c in result["candidates"]], [99, 99])
        self.assertTrue(all(c["receiverGraphId"] is None for c in result["candidates"]))
        self.assertEqual(result["terminalCompleteness"], "NOT_VERIFIED")

    def test_missing_source_and_unmatched_endpoints_are_counted(self):
        result = audit_side(
            [edge(1), edge(2), edge(3)],
            [endpoint(1, matched=False), endpoint(2, dead_end=False)],
            [], "from")
        self.assertEqual(result["unresolvedEndpoints"], 2)
        self.assertEqual(result["provisionalTerminalEdges"], 0)
        self.assertEqual(result["terminalCompleteness"], "NOT_VERIFIED")

    def test_missing_probe_does_not_disappear_as_rejection(self):
        result = audit_side(
            [edge(1), edge(2)], [endpoint(1), endpoint(2)], [continuation(1)], "to")
        self.assertEqual(result["deadEndObservations"], 2)
        self.assertEqual(result["unresolvedDeadEndProbes"], 1)
        self.assertEqual(result["provisionalTerminalEdges"], 1)

    def test_no_neighbour_and_neighbour_dead_end_are_not_proofs(self):
        result = audit_side(
            [edge(1), edge(2)], [endpoint(1), endpoint(2)],
            [continuation(1, found=False, continues=False),
             continuation(2, found=True, continues=False)], "from")
        self.assertEqual(result["noNeighbourMatchWithinTolerance"], 1)
        self.assertEqual(result["neighbourAlsoStops"], 1)
        self.assertEqual(result["provisionalTerminalEdges"], 0)

    def test_unknown_or_duplicate_graphid_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown/non-integer"):
            audit_side([edge(1)], [endpoint(2)], [], "from")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            audit_side([edge(1)], [endpoint(1), endpoint(1)], [], "from")
        with self.assertRaisesRegex(ValueError, "duplicate scan"):
            audit_side([edge(1), edge(1)], [], [], "from")

    def test_out_of_scope_or_malformed_receiver_proof_rejected(self):
        with self.assertRaisesRegex(ValueError, "does not correspond"):
            audit_side([edge(1)], [endpoint(1, dead_end=False)],
                       [continuation(1)], "to")
        with self.assertRaisesRegex(ValueError, "without neighbour match"):
            audit_side([edge(1)], [endpoint(1)],
                       [continuation(1, found=False, continues=True)], "to")
        with self.assertRaisesRegex(ValueError, "malformed"):
            audit_side([edge(1)], [endpoint(1)],
                       [{"g": 1, "found": 1, "cont": True}], "to")

    def test_invalid_coordinates_and_flags_rejected(self):
        with self.assertRaisesRegex(ValueError, "invalid directed endpoint"):
            audit_side([edge(1)], [{"g": 1, "id": True, "e": [float("nan"), 4], "d": True}], [], "from")
        with self.assertRaisesRegex(ValueError, "invalid endpoint match"):
            audit_side([edge(1)], [{"g": 1, "id": 1}], [], "from")


def native_row(graph_id, *, way_id=99):
    return {"sourceGraphId": graph_id, "endNodeGraphId": 123,
            "endLat": 46.5, "endLon": 13.7, "deadend": True,
            "notThru": False, "forward": True,
            "wayId": way_id, "forwardAccess": 2031, "reverseAccess": 2031}


class NativeGraphReaderEndpointTests(unittest.TestCase):
    def test_full_exact_source_resolution_does_not_infer_receiver_connection(self):
        observations = native_endpoints_to_observations(
            [edge(1), edge(2)], [native_row(1), native_row(2)], "from")
        result = audit_side([edge(1), edge(2)], observations,
                            [continuation(1)], "from")
        self.assertEqual(result["endpointMatched"], 2)
        self.assertEqual(result["unresolvedEndpoints"], 0)
        self.assertEqual(result["unresolvedDeadEndProbes"], 1)
        self.assertEqual(result["terminalCompleteness"], "NOT_VERIFIED")

    def test_exact_graph_reader_rows_fail_closed_on_incomplete_or_wrong_graph(self):
        with self.assertRaisesRegex(ValueError, "coverage incomplete"):
            native_endpoints_to_observations([edge(1), edge(2)], [native_row(1)], "from")
        with self.assertRaisesRegex(ValueError, "wayId mismatches scanner"):
            native_endpoints_to_observations([edge(1)], [native_row(1, way_id=400)], "from")
        bad = native_row(1)
        bad["forwardAccess"] = 99
        with self.assertRaisesRegex(ValueError, "forwardAccess mismatches"):
            native_endpoints_to_observations([edge(1)], [bad], "from")
        bad = native_row(1)
        bad["endNodeGraphId"] = -1
        with self.assertRaisesRegex(ValueError, "invalid native end-node"):
            native_endpoints_to_observations([edge(1)], [bad], "from")

    def test_compiled_native_extractor_registered_without_replacing_raw_scanner(self):
        root = Path(__file__).resolve().parents[1]
        cmake = (root / "tools/native-f8-edge-scan/CMakeLists.txt").read_text()
        cpp = (root / "tools/native-f8-edge-scan/native_f8_directed_endpoints.cpp").read_text()
        self.assertIn("add_executable(native_f8_directed_endpoints", cmake)
        self.assertIn("add_executable(native_f8_edge_scan", cmake)
        self.assertIn("GetGraphTile(end_id)", cpp)
        self.assertIn("endNodeGraphId", cpp)
        self.assertIn("deadend()", cpp)
        self.assertIn("PARTIAL_STDOUT_MUST_BE_DISCARDED", cpp)


if __name__ == "__main__":
    unittest.main()
