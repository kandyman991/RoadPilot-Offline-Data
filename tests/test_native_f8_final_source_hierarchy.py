"""Native final-edge source hierarchy contract tests: no cross-region correlation."""
from __future__ import annotations

import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from verify_native_f8_final_source_hierarchy import (
    inspect_original_directed_cut, prove_original_end_hierarchy,
)
from probe_native_f8_clipped_terminal import CRS
from shapely.geometry import box


def source(mask=1025):
    return {"graphId": 111, "wayId": 30, "forwardAccess": mask}


def candidate(*, status="ORIGINAL_NATIVE_MODE_STRANDED_NODE_ONLY",
              modes=None):
    return {
        "finalDirectedGraphId": 111, "nativeEndNodeGraphId": 220,
        "wayIdAnnotationOnly": 30,
        "nativeTerminal": {"lat": 47., "lng": 11.},
        "vehicleModes": modes or ["auto", "motorcycle"],
        "candidateStatus": status,
    }


def edge(gid, mask=1025, *, road=True, shortcut=False):
    return {"graphId": gid, "endNodeGraphId": gid+3,
            "forwardAccess": mask, "isRoad": road, "isShortcut": shortcut}


def original_row(*, hierarchical=False, deadend=False):
    rev = {**edge(333), "autoBit": True, "motorcycleBit": True}
    node = {
        "nodeGraphId": 220, "transitionDepth": 0,
        "nodeLat": 47., "nodeLon": 11.,
        "allOutgoingDirectedEdges": [edge(333)],
        "nativeHierarchyTransitions": (
            [{"nodeGraphId": 990, "up": True}] if hierarchical else []),
    }
    hierarchy = [node]
    if hierarchical:
        hierarchy.append({
            "nodeGraphId": 990, "transitionDepth": 1,
            "nodeLat": 47., "nodeLon": 11.,
            "allOutgoingDirectedEdges": [edge(555)],
            "nativeHierarchyTransitions": [{"nodeGraphId": 220, "up": False}],
        })
    return {
        "sourceGraphId": 111, "endNodeGraphId": 220,
        "endLat": 47., "endLon": 11.,
        "wayId": 30, "forwardAccess": 1025,
        "deadend": deadend, "opposingGraphId": 333,
        "nativeOutgoingDegree": 1, "outgoingDirectedEdges": [rev],
        "nativeAllHierarchyContinuationNodes": hierarchy,
    }


class SourceOnlyFinalEdgeHierarchyTests(unittest.TestCase):
    def test_single_end_node_has_no_mode_alternative_but_no_physical_claim(self):
        result = prove_original_end_hierarchy(candidate(), source(), original_row())
        self.assertEqual(result["originalDirectedGraphId"], 111)
        self.assertEqual(result["originalModeEndStatus"]["auto"]["status"],
                         "NO_OTHER_NATIVE_MODE_ACCESSIBLE_HIERARCHY_OUTGOING")
        self.assertEqual(result["originalModeEndStatus"]["motorcycle"]["status"],
                         "NO_OTHER_NATIVE_MODE_ACCESSIBLE_HIERARCHY_OUTGOING")
        self.assertEqual(result["sourcePhysicalRoadDirectionEquivalence"],
                         "NOT_VERIFIED")
        self.assertFalse(result["candidateSuppressed"])

    def test_native_hierarchy_alternative_prevents_false_terminal_claim(self):
        result = prove_original_end_hierarchy(
            candidate(), source(), original_row(hierarchical=True))
        for mode in ("auto", "motorcycle"):
            self.assertEqual(result["originalModeEndStatus"][mode]["status"],
                             "HIERARCHY_MODE_ACCESSIBLE_ALTERNATIVES_UNRESOLVED")
            self.assertEqual(result["originalModeEndStatus"][mode][
                "originalOtherHierarchyDirectedEdges"][0]["directedGraphId"], 555)
        self.assertEqual(result["nativeHierarchyNodesAudited"], 2)

    def test_mode_specific_hierarchy_not_shared_between_vehicles(self):
        row = original_row(hierarchical=True)
        row["nativeAllHierarchyContinuationNodes"][1]["allOutgoingDirectedEdges"][0][
            "forwardAccess"] = 1
        result = prove_original_end_hierarchy(candidate(), source(), row)
        self.assertEqual(result["originalModeEndStatus"]["auto"]["status"],
                         "HIERARCHY_MODE_ACCESSIBLE_ALTERNATIVES_UNRESOLVED")
        self.assertEqual(result["originalModeEndStatus"]["motorcycle"]["status"],
                         "NO_OTHER_NATIVE_MODE_ACCESSIBLE_HIERARCHY_OUTGOING")

    def test_deadend_original_evidence_kept_distinct_from_stranded(self):
        c = candidate(status="ORIGINAL_NATIVE_GRAPH_LOCAL_TERMINAL_ONLY")
        r = original_row(deadend=True)
        self.assertTrue(prove_original_end_hierarchy(c, source(), r)[
            "originalModeEndStatus"]["auto"]["exactNativeEndNodeProved"])
        with self.assertRaisesRegex(ValueError, "classification"):
            prove_original_end_hierarchy(c, source(), original_row())

    def test_unreachable_and_spoofed_hierarchy_fail(self):
        for mutate in (
            lambda r: r["nativeAllHierarchyContinuationNodes"][0].update(
                nativeHierarchyTransitions=[]),
            lambda r: r["nativeAllHierarchyContinuationNodes"][1].update(
                transitionDepth=2),
            lambda r: r["nativeAllHierarchyContinuationNodes"][1].update(
                nodeGraphId=220),
            lambda r: r["nativeAllHierarchyContinuationNodes"][0].update(
                allOutgoingDirectedEdges=[edge(999)]),
            lambda r: r["nativeAllHierarchyContinuationNodes"][1].update(
                nativeHierarchyTransitions=[{"nodeGraphId": 888, "up": True}]),
        ):
            r = original_row(hierarchical=True)
            mutate(r)
            with self.subTest(r=r), self.assertRaises(ValueError):
                prove_original_end_hierarchy(candidate(), source(), r)

    def test_original_root_forward_branch_must_not_be_suppressed(self):
        r = original_row()
        r["outgoingDirectedEdges"].append({
            **edge(444), "autoBit": True, "motorcycleBit": True})
        r["nativeAllHierarchyContinuationNodes"][0][
            "allOutgoingDirectedEdges"].append(edge(444))
        r["nativeOutgoingDegree"] = 2
        with self.assertRaisesRegex(ValueError, "root continuation"):
            prove_original_end_hierarchy(candidate(), source(), r)

    def test_bad_mode_source_and_duplicate_modes_fatal(self):
        with self.assertRaisesRegex(ValueError, "source is not traversable"):
            prove_original_end_hierarchy(
                candidate(modes=["motorcycle"]),
                source(mask=1), {**original_row(), "forwardAccess": 1})
        with self.assertRaises(ValueError):
            prove_original_end_hierarchy(
                candidate(modes=["auto", "auto"]), source(), original_row())

    def test_opposing_edge_alone_is_not_forward_continuation(self):
        r = original_row()
        r["nativeAllHierarchyContinuationNodes"][0][
            "allOutgoingDirectedEdges"] = [edge(333)]
        self.assertEqual(
            prove_original_end_hierarchy(candidate(), source(), r)[
                "originalModeEndStatus"]["auto"]["status"],
            "NO_OTHER_NATIVE_MODE_ACCESSIBLE_HIERARCHY_OUTGOING")

    def test_missing_or_malformed_node_inventory_aborts(self):
        for field, value in (
            ("nativeAllHierarchyContinuationNodes", []),
            ("nativeAllHierarchyContinuationNodes", "truncated"),
            ("sourceGraphId", 0),
            ("opposingGraphId", 999),
            ("nativeOutgoingDegree", 0),
        ):
            r = original_row()
            r[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                prove_original_end_hierarchy(candidate(), source(), r)

    def test_source_cut_must_intersect_real_native_directed_geometry(self):
        x, y = CRS.transform(11., 47.)
        own = {"polygon": box(x-20, y-50, x+20, y+50)}
        c = candidate()
        original = original_row()
        original["directedGeometry"] = [[47., 10.998], [47., 11.]]
        obs = inspect_original_directed_cut(c, original, own)
        self.assertTrue(obs["originalDirectedEdgeIntersects25kmSourceCut"])
        self.assertGreater(obs["originalDirectedShapeMetresOutsideSourceBuffer"], 0)
        self.assertEqual(
            obs["geometryClaim"],
            "SOURCE_SIDE_ONLY_PHYSICAL_ROAD_UNIQUENESS_NOT_VERIFIED")
        original["directedGeometry"] = [[47., 10.99999], [47., 11.]]
        obs2 = inspect_original_directed_cut(c, original, own)
        self.assertFalse(obs2["originalDirectedEdgeIntersects25kmSourceCut"])
        self.assertEqual(obs2["originalDirectedShapeMetresOutsideSourceBuffer"], 0.)

    def test_original_geometry_never_forges_end_point_or_cut_intersection(self):
        x, y = CRS.transform(11., 47.)
        own = {"polygon": box(x-20, y-20, x+20, y+20)}
        c = candidate()
        for vertices in (
            [], [[47., 11.]], [[47., 11.], [47., 11.]],
            [[47., 10.999], [48., 12.]],
            [[47., 10.999], [float("nan"), 11.]],
            [[47., 10.999], [47., 181.]],
        ):
            row = original_row()
            row["directedGeometry"] = vertices
            with self.subTest(vertices=vertices), self.assertRaises(ValueError):
                inspect_original_directed_cut(c, row, own)

    def test_native_extractor_is_only_original_end_node_hierarchy(self):
        root = Path(__file__).resolve().parents[1]
        cpp = (root / "tools/native-f8-edge-scan/native_f8_directed_endpoints.cpp").read_text()
        self.assertIn("--terminal-hierarchy", cpp)
        self.assertIn("GetNodeTransitions", cpp)
        self.assertIn("nativeAllHierarchyContinuationNodes", cpp)
        self.assertIn("PARTIAL_STDOUT_MUST_BE_DISCARDED", cpp)
        for retired in ("build_frontier_road_inventory", "build_region_connector_matrix",
                        "plan_multiregion_route"):
            self.assertNotIn(retired, cpp)


if __name__ == "__main__":
    unittest.main()
