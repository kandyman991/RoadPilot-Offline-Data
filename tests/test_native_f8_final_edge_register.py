"""Contract gates for the native F8 one-final-directed-edge candidate register."""
from __future__ import annotations

import copy
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from build_native_f8_final_edge_register import make_register

SHA = "sha256:" + "a" * 64


def pair():
    return {
        "schema": "roadpilot.cross-region-connectivity", "version": 1,
        "pairId": "alpha__beta", "fromRegionId": "alpha", "toRegionId": "beta",
        "fromPackageVersion": "1", "toPackageVersion": "1",
        "validationState": "UNPROVEN",
        "fromGraphFingerprint": SHA, "toGraphFingerprint": "sha256:" + "b" * 64,
        "fromBoundaryFingerprint": "sha256:" + "c" * 64,
        "toBoundaryFingerprint": "sha256:" + "d" * 64,
    }


def edge(gid, way=25, modes=1025):
    return {"graphId": gid, "wayId": way, "forwardAccess": modes,
            "lat": 47.0, "lon": 11.0,
            "innerLat": 47.001, "innerLon": 11.001}


def terminal(gid, *, way=25, inside=True):
    return {
        "graphId": gid, "wayIdAnnotationOnly": way,
        "endNodeGraphId": gid + 1000, "endLat": 47.01,
        "endLon": 11.01, "insidePeerBuffer": inside,
        "terminalStatus": "NATIVE_GRAPH_LOCAL_MODE_TERMINAL_ONLY",
    }


def census(a, b, *, ma, mb):
    p = pair()
    def side(src, modes):
        return {
            "edgeCoverage": "ALL_SOURCE_NATIVE_SCAN_IDS_RECONCILED",
            "counts": {
                "nativeDirectedEdgesAudited": len(src),
                "autoGraphLocalFinalDirectedEdges": len(modes["auto"]),
                "motorcycleGraphLocalFinalDirectedEdges": len(modes["motorcycle"]),
                "autoModeStrandedNondeadend": 2,
                "motorcycleModeStrandedNondeadend": 1},
            "allGraphLocalModeTerminals": modes,
        }
    return {
        "schema": "roadpilot.f8-native-full-graph-local-terminal-census",
        "version": 1, "pairId": p["pairId"],
        "nativeTopologyCoverage": "ALL_RETAINED_NATIVE_SCAN_EDGES",
        "globalOneFinalRetainedEdgePerPhysicalRoadDirection": "NOT_VERIFIED",
        "productionPublication": "BLOCKED",
        **{k: p[k] for k in ("fromGraphFingerprint", "toGraphFingerprint",
                            "fromBoundaryFingerprint", "toBoundaryFingerprint")},
        "directions": {"from-to": side(a, ma), "to-from": side(b, mb)},
    }


class OneFinalEdgeRegisterTests(unittest.TestCase):
    def setUp(self):
        # Same physical OSM way annotation on two separate directed IDs must
        # NEVER cause one to be silently discarded.
        self.a = {"edges": [edge(101), edge(102), edge(103, modes=1)]}
        self.b = {"edges": [edge(201)]}
        self.ca = {"auto": [terminal(101), terminal(102), terminal(103)],
                   "motorcycle": [terminal(101), terminal(102)]}
        self.cb = {"auto": [terminal(201)], "motorcycle": [terminal(201)]}
        self.c = census(self.a["edges"], self.b["edges"], ma=self.ca, mb=self.cb)

    def compile(self):
        return make_register(pair(), self.c, self.a, self.b)

    def test_one_record_per_native_directed_edge_across_two_modes(self):
        x = self.compile()
        rows = x["directions"]["from-to"]["terminalCandidates"]
        self.assertEqual([r["finalDirectedGraphId"] for r in rows], [101, 102, 103])
        self.assertEqual(rows[0]["vehicleModes"], ["auto", "motorcycle"])
        self.assertEqual(rows[0]["sourceStartNodeAnnotationOnly"],
                         {"lat": 47.0, "lng": 11.0})
        self.assertEqual(rows[0]["sourceInteriorSampleAnnotationOnly"],
                         {"lat": 47.001, "lng": 11.001})
        self.assertEqual(rows[0]["nativeTerminal"],
                         {"lat": 47.01, "lng": 11.01})
        self.assertEqual(rows[2]["vehicleModes"], ["auto"])
        self.assertEqual(x["directions"]["from-to"]["modeCounts"],
                         {"auto": 3, "motorcycle": 2})
        self.assertTrue(x["directions"]["from-to"]["oneCandidateRecordPerOriginalDirectedGraphId"])
        self.assertEqual(x["roadDirectionClasses"], "NOT_VERIFIED")
        self.assertEqual(x["productionPublication"], "BLOCKED")

    def test_same_way_different_edges_and_buffer_labels_cannot_filter(self):
        self.ca["auto"][1]["insidePeerBuffer"] = False
        self.ca["motorcycle"][1]["insidePeerBuffer"] = False
        rows = self.compile()["directions"]["from-to"]["terminalCandidates"]
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["wayIdAnnotationOnly"], rows[1]["wayIdAnnotationOnly"])
        self.assertFalse(rows[1]["insidePeerBufferAnnotationOnly"])
        self.assertTrue(all(not r["candidateSuppressed"] for r in rows))

    def test_original_scan_contains_nonterminal_and_mode_stranded_cases(self):
        self.a["edges"].append(edge(104))
        self.c["directions"]["from-to"]["counts"]["nativeDirectedEdgesAudited"] = 4
        side = self.compile()["directions"]["from-to"]
        self.assertEqual(side["originalSourceIDsOutsideTerminalRegisterStillInFullScan"], 1)
        self.assertEqual(side["unresolvedModeStrandedNondeadendCounts"]["auto"], 2)
        self.assertTrue(side["noRoadsOrBranchesDiscardedFromFullSourceScan"])

    def test_duplicate_mode_terminal_aborts_not_deduplicated(self):
        self.ca["auto"].append(copy.deepcopy(self.ca["auto"][0]))
        self.c["directions"]["from-to"]["counts"]["autoGraphLocalFinalDirectedEdges"] += 1
        with self.assertRaisesRegex(ValueError, "Repeated terminal"):
            self.compile()

    def test_shared_id_must_agree_on_end_node_buffer_and_geometry(self):
        for field, bad in (("endNodeGraphId", 999),
                           ("endLon", 11.5), ("insidePeerBuffer", False)):
            with self.subTest(field=field):
                self.ca["motorcycle"][0][field] = bad
                with self.assertRaisesRegex(ValueError, "mode views disagree"):
                    self.compile()
                self.ca["motorcycle"][0] = terminal(101)

    def test_wrong_mode_access_or_source_identity_aborts(self):
        self.a["edges"][0]["forwardAccess"] = 1
        with self.assertRaisesRegex(ValueError, "access mismatch"):
            self.compile()
        self.a["edges"][0]["forwardAccess"] = 1025
        self.ca["auto"][0]["wayIdAnnotationOnly"] = 29
        with self.assertRaisesRegex(ValueError, "identity or access mismatch"):
            self.compile()

    def test_incomplete_census_false_completeness_or_stale_pair_aborts(self):
        for field, value in (
            ("nativeTopologyCoverage", "PARTIAL"),
            ("productionPublication", "READY"),
            ("globalOneFinalRetainedEdgePerPhysicalRoadDirection", "VERIFIED"),
            ("fromGraphFingerprint", "sha256:" + "f" * 64)):
            old = self.c[field]
            self.c[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.compile()
            self.c[field] = old

    def test_duplicate_source_id_or_missing_terminal_aborts(self):
        self.a["edges"].append(edge(101))
        self.c["directions"]["from-to"]["counts"]["nativeDirectedEdgesAudited"] = 4
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.compile()
        self.a["edges"].pop()
        self.c["directions"]["from-to"]["counts"]["nativeDirectedEdgesAudited"] = 3
        self.ca["auto"][0]["graphId"] = 999
        with self.assertRaisesRegex(ValueError, "not in complete scan"):
            self.compile()

    def test_independent_regions_may_reuse_same_numeric_graphid(self):
        self.b["edges"][0]["graphId"] = 101
        for mode in self.cb:
            self.cb[mode][0] = terminal(101)
        results = self.compile()["directions"]
        self.assertEqual(
            results["from-to"]["terminalCandidates"][0]["finalDirectedGraphId"],
            results["to-from"]["terminalCandidates"][0]["finalDirectedGraphId"])
        self.assertEqual(results["from-to"]["originalRegion"], "alpha")
        self.assertEqual(results["to-from"]["originalRegion"], "beta")
        # Numeric GraphId equality between independent graphs is not a road
        # equivalence relation and must never produce a cross-region collapse.

    def test_missing_interior_source_sample_must_fail_not_be_mislabelled(self):
        del self.a["edges"][0]["innerLat"]
        with self.assertRaisesRegex(ValueError, "coordinate"):
            self.compile()

    def test_incorrect_census_terminal_counts_do_not_silently_shrink(self):
        self.ca["auto"].pop()
        with self.assertRaisesRegex(ValueError, "terminal count disagreement"):
            self.compile()
        self.ca["auto"].append(terminal(103))
        self.c["directions"]["from-to"]["counts"]["autoModeStrandedNondeadend"] = -1
        with self.assertRaisesRegex(ValueError, "stranded"):
            self.compile()


if __name__ == "__main__":
    unittest.main()
