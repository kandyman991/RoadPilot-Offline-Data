"""M6a graph-B split directed-chain evidence cannot certify a cross-graph seam."""
from __future__ import annotations

from pathlib import Path
import copy
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from probe_native_f8_directed_chain import (
    inspect, native_chain_observation, source_tail_on_b_chain,
    trace_selected_b_chain,
)

MASK = 1025


def edge(graph_id, points, *, mask=MASK, way=10):
    return {
        "sourceGraphId": graph_id,
        "endNodeGraphId": graph_id + 1000,
        "wayId": way,
        "endLat": points[-1][0],
        "endLon": points[-1][1],
        "forwardAccess": mask,
        "directedGeometry": points,
    }


A = edge(11, [[0, 0], [0, .0005]], way=100)
B = [
    edge(201, [[0, 0], [0, .00025]], way=999),
    edge(202, [[0, .00025], [0, .0005]], way=1000),
    edge(203, [[0, .0005], [0, .001]], way=1001),
]


def row(gid, end=None, mask=MASK):
    return {
        "graphId": gid, "endNodeGraphId": end if end is not None else gid + 1000,
        "forwardAccess": mask, "isRoad": True, "isShortcut": False,
        "autoBit": bool(mask & 1), "motorcycleBit": bool(mask & 1024),
    }


def adjacency(chain=B):
    result = []
    for i, e in enumerate(chain):
        opp = 901 + i
        outs = [row(opp)]
        if i + 1 < len(chain):
            nxt = chain[i + 1]
            outs.append(row(nxt["sourceGraphId"], nxt["endNodeGraphId"],
                            nxt["forwardAccess"]))
        if i == len(chain) - 1:
            outs.append(row(404))
        result.append({
            "sourceGraphId": e["sourceGraphId"],
            "endNodeGraphId": e["endNodeGraphId"],
            "wayId": e["wayId"],
            "forwardAccess": e["forwardAccess"],
            "opposingGraphId": opp,
            "nativeOutgoingDegree": len(outs),
            "outgoingDirectedEdges": outs,
        })
    return result


def route(_cfg, start, end, _mode):
    return {
        "status": "SUCCEEDED", "startOffsetMeters": 0, "endOffsetMeters": 0,
        "startActual": start, "endActual": end, "encodedShape": "fixture",
        "durationSeconds": 18, "distanceKm": .12,
    }


def trace(_cfg, _shape, _mode):
    return [201, 202, 203]


def probe(*, source=A, chain=B, adj=None, mode="auto",
          route_fn=route, trace_fn=trace):
    return inspect(
        source, chain, adjacency(chain) if adj is None else adj,
        Path("graph-B"), mode, route_fn, trace_fn,
    )


class M6DirectedChainTests(unittest.TestCase):
    def test_split_b_edges_are_native_connected_and_b_route_is_exact(self):
        r = probe()
        self.assertEqual(r["receiverTopology"]["selectedGraphLocalDirectedChain"],
                         [201, 202, 203])
        self.assertTrue(r["receiverTopology"]["allNativeOutgoingAlternativesRetained"])
        self.assertEqual(r["receivingGraphRouteObservation"]["status"],
                         "B_GRAPH_DIRECTED_CHAIN_TRACED_FOR_THIS_LOCAL_ROUTE")
        self.assertEqual(r["directedGeometryObservation"]["sampledDirectedOrder"],
                         "SELECTED_B_CHAIN_ALIGNED_SAMPLES_ONLY")
        self.assertEqual(r["directedGeometryObservation"]["tailSamplesWithinOneMetre"],
                         r["directedGeometryObservation"]["sourceTailSamples"])
        for key in ("crossGraphPhysicalContinuity", "crossSeamTurnLegality",
                    "androidF8Parity", "discoveryCoverage", "routeOptimality"):
            self.assertEqual(r[key], "NOT_VERIFIED")
        self.assertEqual(r["productionPublication"], "BLOCKED")
        self.assertNotEqual(A["wayId"], B[0]["wayId"])

    def test_preserve_all_native_unselected_outgoing_branches(self):
        r = probe()
        inv = r["receiverTopology"]["allBranchInventories"]
        self.assertEqual([r["selectedNextGraphId"] for r in inv], [202, 203, None])
        self.assertEqual([[e["graphId"] for e in b["allNativeOutgoingAlternatives"]]
                          for b in inv], [[901, 202], [902, 203], [903, 404]])
        self.assertEqual(inv[-1]["nativeOutgoingDegree"], 2)

    def test_native_cpp_extractor_reports_actual_node_degree(self):
        source = (Path(__file__).resolve().parents[1] /
                  "tools/native-f8-edge-scan/native_f8_directed_endpoints.cpp").read_text()
        self.assertIn('"nativeOutgoingDegree', source)
        self.assertIn('node->edge_count()', source)

    def test_wrong_or_partial_native_adjacency_is_rejected(self):
        base = adjacency()
        for mutated in (
            lambda x: x[0].update(nativeOutgoingDegree=1),
            lambda x: x[0]["outgoingDirectedEdges"].pop(),
            lambda x: x[0]["outgoingDirectedEdges"][1].update(graphId=901),
            lambda x: x[0].update(endNodeGraphId=456),
            lambda x: x[0]["outgoingDirectedEdges"][1].update(
                endNodeGraphId=999999),
            lambda x: x[0]["outgoingDirectedEdges"][1].update(autoBit=False),
            lambda x: x[0].update(opposingGraphId=999),
        ):
            bad = copy.deepcopy(base)
            mutated(bad)
            with self.assertRaises(ValueError):
                probe(adj=bad)

    def test_nonadjacent_b_graph_edge_is_not_accepted_by_shared_geometry(self):
        broken = adjacency()
        broken[1]["outgoingDirectedEdges"][1]["graphId"] = 450
        with self.assertRaisesRegex(ValueError, "not native-directed adjacent"):
            probe(adj=broken)

    def test_opposite_geometry_annotated_but_not_a_discovery_filter(self):
        opposite = [
            edge(501, [[0, .0005], [0, .00025]]),
            edge(502, [[0, .00025], [0, 0]]),
        ]
        result = probe(chain=opposite, trace_fn=lambda *_: [501, 502])
        self.assertEqual(result["directedGeometryObservation"]["sampledDirectedOrder"],
                         "SELECTED_B_CHAIN_OPPOSED_SAMPLES_ONLY")
        self.assertEqual(result["crossGraphPhysicalContinuity"], "NOT_VERIFIED")
        self.assertEqual(result["receiverTopology"]["selectedEdgeCount"], 2)

    def test_selected_chain_can_share_numeric_graph_id_with_a_without_identity_assumption(self):
        source = edge(201, [[0, 0], [0, .0005]])
        r = probe(source=source)
        self.assertEqual(r["sourceDirectedGraphId"], 201)
        self.assertEqual(r["receiverTopology"]["selectedGraphLocalDirectedChain"][0], 201)
        self.assertEqual(r["crossGraphPhysicalContinuity"], "NOT_VERIFIED")

    def test_alternative_b_valhalla_route_does_not_reject_handoff(self):
        r = probe(trace_fn=lambda *_: [201, 303, 203])
        self.assertEqual(r["receivingGraphRouteObservation"]["status"],
                         "UNPROVEN_FOR_THIS_ROUTE")
        self.assertEqual(r["discoveryCoverage"], "NOT_VERIFIED")

    def test_b_local_engine_inconclusive_preserves_geometry_and_branch_evidence(self):
        r = probe(route_fn=lambda *_: {"status": "FAILED"})
        self.assertEqual(r["receivingGraphRouteObservation"]["status"], "INCONCLUSIVE")
        self.assertEqual(r["receiverTopology"]["allBranchInventories"][0]
                         ["nativeOutgoingDegree"], 2)
        self.assertEqual(r["productionPublication"], "BLOCKED")

    def test_inaccessible_selected_b_edge_does_not_invalidate_other_modes(self):
        chain = copy.deepcopy(B)
        chain[1]["forwardAccess"] = 1  # car-only
        r = probe(chain=chain, mode="motorcycle")
        self.assertEqual(r["receivingGraphRouteObservation"]["status"],
                         "UNPROVEN_FOR_THIS_MODE")
        self.assertEqual(r["crossSeamTurnLegality"], "NOT_VERIFIED")
        car = probe(chain=chain, mode="auto")
        self.assertEqual(car["receivingGraphRouteObservation"]["status"],
                         "B_GRAPH_DIRECTED_CHAIN_TRACED_FOR_THIS_LOCAL_ROUTE")

    def test_discontinuous_b_geometry_fails_closed_without_global_negative(self):
        chain = copy.deepcopy(B)
        chain[1]["directedGeometry"][0] = [.0005, .00025]
        with self.assertRaisesRegex(ValueError, "inconsistent geometry"):
            probe(chain=chain)

    def test_duplicate_and_oversized_paths_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            native_chain_observation([B[0], B[0]], [adjacency()[0]] * 2)
        with self.assertRaisesRegex(ValueError, "2–16"):
            native_chain_observation(B[:1], adjacency()[:1])
        with self.assertRaisesRegex(ValueError, "2–16"):
            native_chain_observation(B * 6, adjacency() * 6)

    def test_invalid_mode_and_route_snapping_are_not_promoted(self):
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            trace_selected_b_chain(Path("graph-B"), B, "horse", route, trace)
        def snap(_cfg, a, b, mode):
            r = route(_cfg, a, b, mode)
            r["startOffsetMeters"] = 15
            return r
        r = probe(route_fn=snap)
        self.assertEqual(r["receivingGraphRouteObservation"]["status"],
                         "UNPROVEN_FOR_THIS_ROUTE")
        self.assertEqual(r["crossGraphPhysicalContinuity"], "NOT_VERIFIED")

    def test_b_route_trace_missing_or_nonconsecutive_remains_unproven(self):
        r = probe(trace_fn=lambda *_: None)
        self.assertEqual(r["receivingGraphRouteObservation"]["status"], "INCONCLUSIVE")
        r = probe(trace_fn=lambda *_: [201, 202, 77, 203])
        self.assertEqual(r["receivingGraphRouteObservation"]["status"],
                         "UNPROVEN_FOR_THIS_ROUTE")

    def test_malformed_source_native_geometry_fails_closed(self):
        bad = edge(11, [[0, 0], [float("nan"), .0005]])
        with self.assertRaises(ValueError):
            probe(source=bad)


if __name__ == "__main__":
    unittest.main()
