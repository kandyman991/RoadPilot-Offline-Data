"""Regression gates for exhaustive, non-suppressing F8 native graph-local census."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from shapely.geometry import box

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from census_native_f8_final_directed_edges import (
    audit_rows, validate_row, verify_binary, verify_window_coverage,
)
from capture_native_f8_graph_windows import overlap_windows


def edge(gid: int, *, way: int = 17, access: int = 1025):
    return {"graphId": gid, "wayId": way, "forwardAccess": access,
            "reverseAccess": 0}


def outgoing(gid: int, mask: int, *, shortcut: bool = False,
             road: bool = True):
    return {"graphId": gid, "endNodeGraphId": 222, "forwardAccess": mask,
            "isRoad": road, "isShortcut": shortcut, "autoBit": bool(mask & 1),
            "motorcycleBit": bool(mask & 1024)}


def row(source, *, branch=None, deadend=True):
    edges = [outgoing(source["graphId"] + 5000, 0)]
    if branch is not None:
        edges.append(branch)
    return {"sourceGraphId": source["graphId"],
            "endNodeGraphId": 333, "endLat": 47.1, "endLon": 11.2,
            "deadend": deadend, "notThru": False, "forward": True,
            "wayId": source["wayId"], "forwardAccess": source["forwardAccess"],
            "reverseAccess": source["reverseAccess"],
            "opposingGraphId": edges[0]["graphId"],
            "nativeOutgoingDegree": len(edges), "outgoingDirectedEdges": edges}


def lines(*records):
    return iter(json.dumps(x) + "\n" for x in records)


def buffer(inside=True):
    return {"polygon": box(0, 0, 1e7, 1e7) if inside
            else box(0, 0, .000001, .000001)}


class NativeFullCensusTests(unittest.TestCase):
    def test_every_selected_native_graph_id_is_consumed_without_name_way_collapse(self):
        a, b = edge(100), edge(200)  # deliberately same way/road annotation
        report = audit_rows([a, b], lines(row(a), row(b)), buffer())
        self.assertEqual(report["counts"]["nativeDirectedEdgesAudited"], 2)
        self.assertEqual(report["counts"]["autoGraphLocalFinalDirectedEdges"], 2)
        self.assertEqual([x["graphId"] for x in
            report["allGraphLocalModeTerminals"]["auto"]], [100, 200])
        self.assertEqual(report["physicalRoadUniqueFinalEdge"], "NOT_VERIFIED")
        self.assertEqual(report["androidJNIParity"], "NOT_VERIFIED")
        self.assertEqual(report["productionPublication"], "BLOCKED")

    def test_native_shortcuts_and_nonroad_outgoing_block_terminal_only(self):
        a, b = edge(100), edge(200)
        report = audit_rows(
            [a, b],
            lines(row(a, branch=outgoing(800, 1025, shortcut=True)),
                  row(b, branch=outgoing(900, 1025, road=False))),
            buffer())
        self.assertEqual(report["counts"]["nativeDirectedEdgesAudited"], 2)
        self.assertNotIn("autoGraphLocalFinalDirectedEdges", report["counts"])
        self.assertNotIn("motorcycleGraphLocalFinalDirectedEdges", report["counts"])

    def test_non_deadend_mode_stranded_is_not_assumed_final(self):
        a = edge(100)
        report = audit_rows([a], lines(row(a, deadend=False)), buffer())
        self.assertEqual(report["counts"]["autoModeStrandedNondeadend"], 1)
        self.assertEqual(report["counts"]["motorcycleModeStrandedNondeadend"], 1)
        self.assertEqual(report["allGraphLocalModeTerminals"]["auto"], [])

    def test_outside_peer_polygon_is_never_source_edge_rejection(self):
        a = edge(100)
        report = audit_rows([a], lines(row(a)), buffer(False))
        self.assertEqual(report["counts"]["autoGraphLocalFinalDirectedEdges"], 1)
        self.assertNotIn("autoFinalInsidePeerBuffer", report["counts"])
        self.assertFalse(report["allGraphLocalModeTerminals"]["auto"][0]["insidePeerBuffer"])

    def test_missing_extra_reordered_and_duplicate_rows_fail_closed(self):
        a, b = edge(100), edge(200)
        for evidence in (
                lines(row(a)),
                lines(row(a), row(b), row(edge(300))),
                lines(row(b), row(a)),
                lines(row(a), row(a))):
            with self.subTest(evidence=evidence):
                with self.assertRaises(ValueError):
                    audit_rows([a, b], evidence, buffer())
        with self.assertRaisesRegex(ValueError, "Repeated"):
            audit_rows([a, a], lines(row(a), row(a)), buffer())

    def test_omitted_forward_shortcut_bad_degree_or_reverse_is_fatal(self):
        a = edge(100)
        for invalid in (
                {**row(a), "nativeOutgoingDegree": 2},
                {**row(a), "opposingGraphId": 999},
                {**row(a), "outgoingDirectedEdges": [outgoing(5100, 0), outgoing(5100, 0)],
                 "nativeOutgoingDegree": 2},
                {**row(a), "outgoingDirectedEdges": [outgoing(5100, 0),
                    {**outgoing(800, 1025), "autoBit": False}], "nativeOutgoingDegree": 2}):
            with self.assertRaises(ValueError):
                validate_row(a, invalid)

    def test_binary_hash_is_checked_before_any_execution(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "untrusted"
            path.write_text("not a native binary")
            with patch("census_native_f8_final_directed_edges.subprocess.run") as run:
                with self.assertRaisesRegex(ValueError, "hash mismatch"):
                    verify_binary(path, "sha256:" + "0"*64)
                run.assert_not_called()
            path2 = Path(d) / "link"
            path2.symlink_to(path)
            with self.assertRaisesRegex(ValueError, "symlink"):
                verify_binary(path2, "sha256:" + "0"*64)

    def test_exact_overlap_window_catalog_cannot_skip_shared_cells(self):
        from_shape = box(0, 0, .05, .05)
        to_shape = box(0, 0, .05, .05)
        expected = list(overlap_windows(from_shape, to_shape, .025))
        def scan(bounds):
            return {"windows": [dict(x, index=i) for i, x in enumerate(bounds)]}
        with patch("census_native_f8_final_directed_edges.load_polygon",
                   side_effect=[from_shape, to_shape]):
            self.assertEqual(verify_window_coverage(
                scan(expected), scan(expected), Path("A"), Path("B")), len(expected))
        with patch("census_native_f8_final_directed_edges.load_polygon",
                   side_effect=[from_shape, to_shape]):
            with self.assertRaisesRegex(ValueError, "complete verified overlap"):
                verify_window_coverage(
                    scan(expected[:-1]), scan(expected[:-1]), Path("A"), Path("B"))


if __name__ == "__main__":
    unittest.main()
