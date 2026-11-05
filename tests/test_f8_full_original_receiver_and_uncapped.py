"""Native full-original-receiver census and uncapped original same-road paths.

No mode is declared eligible merely from proximity or OSM-way identity:
full original graph shape census and exact Valhalla first/last TripLeg remain
the independent, explicit acceptance gates.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from shapely.geometry import Polygon
from shapely.prepared import prep

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from complete_f8_original_receiving_archive import original_receiver_scan
from resolve_f8_source_native_capped_paths import discover_uncapped_from_capped
from gate_f8_source_final_native_topology import FINAL, INTERMEDIATE


def receiver_scan_response(source_count=2, *, complete=True, candidates=None):
    if candidates is None:
        candidates = [{"sourceGraphId": 100,
                       "receiverGraphId": 900,
                       "nativeSourceDistanceMetres": 0.5}]
    return {
        "schema": "roadpilot.f8-original-native-all-receiver-directed-shapes",
        "version": 1, "valhallaVersion": "3.6.3",
        "allGraphReaderTilesExhaustivelyRead": complete,
        "sourcePointCount": source_count,
        "originalReceiverTileCount": 338,
        "allDirectedEdgesVisited": 13790726,
        "originalRoutableRoadShapesRead": 5505266,
        "nearbyOriginalDirectedShapes": candidates,
        "candidatePairs": len(candidates)
    }


class OriginalReceiverCompleteArchiveTests(unittest.TestCase):
    def run_scan(self, response):
        from subprocess import CompletedProcess
        points = {
            100: {"lat": 47.03, "lng": 11.5},
            200: {"lat": 47.04, "lng": 11.6},
        }
        with tempfile.TemporaryDirectory() as directory:
            with patch("complete_f8_original_receiving_archive.subprocess.run",
                       return_value=CompletedProcess(
                         args=[], returncode=0, stdout=json.dumps(response),
                         stderr="")):
                return original_receiver_scan(Path("/fake/native"), Path("/fake/config"),
                                              points, Path(directory))

    def test_complete_native_tiles_preserve_source_with_no_peer(self):
        result = self.run_scan(receiver_scan_response())
        self.assertEqual(result["pairs"][100], {900})
        self.assertEqual(result["pairs"][200], set())
        self.assertTrue(result["summary"]["allGraphReaderTilesExhaustivelyRead"])
        self.assertEqual(result["summary"]["originalReceiverTileCount"], 338)

    def test_missing_all_tiles_never_claims_receiver_coverage(self):
        with self.assertRaises(ValueError):
            self.run_scan(receiver_scan_response(complete=False))

    def test_duplicate_native_receiver_directed_id_fails(self):
        fake = receiver_scan_response(candidates=[
            {"sourceGraphId":100,"receiverGraphId":900,"nativeSourceDistanceMetres":0.1},
            {"sourceGraphId":100,"receiverGraphId":900,"nativeSourceDistanceMetres":0.2}
        ])
        with self.assertRaises(ValueError):
            self.run_scan(fake)

    def test_wrong_original_graphid_fails(self):
        fake = receiver_scan_response(candidates=[
            {"sourceGraphId":300,"receiverGraphId":900,"nativeSourceDistanceMetres":0.1}])
        with self.assertRaises(ValueError):
            self.run_scan(fake)


class OriginalSourceUncappedLineageTests(unittest.TestCase):
    def test_original_same_way_reaches_terminal_and_retains_different_way_branch(self):
        # Source seed 100; 101 -> 102 -> 104 are one physical OSM-way
        # candidate. The genuinely distinct directed branch 103 (another
        # way) is retained unresolved; it is never silently deleted or
        # classified as if the source road necessarily ended at 101.
        rows = [
            {"reason":"SOURCE_NATIVE_CHAIN_MAX_DEPTH_NOT_A_PROOF",
             "seedOriginalSourceGraphId":100,"mode":"auto",
             "pathOriginalDirectedGraphIds":[100,101]}
        ]
        forward = {
            101: [102,103], 102: [104], 103: [], 104: []
        }
        raw = {
            gid: {"sourceGraphId":gid, "wayId":11 if gid==103 else 10,
                  "directedGeometry":[[47.0,11.0],[47.0001,11.0001]]}
            for gid in (100,101,102,103,104)
        }

        def mock_lines(binary, config, ids, work):
            return {gid: raw[gid] for gid in ids}

        def mock_hierarchy(binary, config, ids, work):
            return {gid: {
                "sourceGraphId":gid, "opposingGraphId":999,
                "nativeAllHierarchyContinuationNodes":[{
                    "allOutgoingDirectedEdges":[{
                        "graphId":other,"forwardAccess":1}
                        for other in forward[gid]]}]
            } for gid in ids}

        def mock_status(shape, hierarchy, all_shapes, mode):
            gid = shape["sourceGraphId"]
            if forward[gid]:
                return {
                    "status": INTERMEDIATE,
                    "nativeSourceForwardContinuations":[{
                        "graphId":x} for x in forward[gid]],
                    "otherUnresolvedOriginalSourceBranches":[]}
            return {"status": FINAL, "nativeSourceForwardContinuations":[],
                    "otherUnresolvedOriginalSourceBranches":[]}

        overlap = (
            prep(Polygon([(10,46),(12,46),(12,48),(10,48)])),
            prep(Polygon([(10,46),(12,46),(12,48),(10,48)])))
        with tempfile.TemporaryDirectory() as directory,              patch("resolve_f8_source_native_capped_paths.native_lines",
                   side_effect=mock_lines),              patch("resolve_f8_source_native_capped_paths.hierarchy_rows",
                   side_effect=mock_hierarchy),              patch("resolve_f8_source_native_capped_paths.validate_mode",
                   side_effect=mock_status):
            finals, shapes, roots, deferred, counts = discover_uncapped_from_capped(
                rows, Path("/fake/native"), Path("/fake/config"), overlap,
                Path(directory))
        self.assertIn((104,"auto"),finals)
        self.assertEqual(finals[(104,"auto")][0]["pathOriginalDirectedGraphIds"],
                         [100,101,102,104])
        self.assertEqual(counts["originalDirectedSourceStatesExhaustivelyProcessed"],3)
        self.assertEqual(counts["nativeOtherWayForwardBranchesPreservedUnverified"],1)
        self.assertEqual(counts["unfinishedDepthLimitedSourcePaths"],0)
        self.assertTrue(any(r.get("otherForwardOriginalDirectedGraphId")==103
                            for r in deferred))
        self.assertNotIn(103,roots)

if __name__ == "__main__":
    unittest.main()
