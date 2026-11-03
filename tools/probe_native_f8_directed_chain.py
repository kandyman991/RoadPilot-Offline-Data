#!/usr/bin/env python3
"""M6a read-only witness: compare one A final edge with a nominated B edge chain.

A shared position/road name is not cross-graph continuity, and a B-local
Valhalla route is not a legal graph-A-to-graph-B turn. This opt-in diagnostic
does not filter candidates or emit a production connectivity artifact.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Callable

from build_native_f8_pair_evidence import pair_identity
from native_f8_inputs import graph_manifest_info
from probe_native_f8_journey import distance, route, verify_retained_graph_identity
from probe_native_f8_terminal_handoffs import trace_directed_ids
from probe_native_f8_terminal_geometry import (
    GEOMETRY_OBSERVATION_METRES, checked_edge, native_rows, nearest,
    tail_points,
)
from probe_native_f8_directed_turn import (
    MODES, MAX_NATIVE_OUTGOING, native_adjacency, probe_point,
)

MAX_SELECTED_B_EDGES = 16
MAX_NATIVE_VERTICES = 250000
MAX_GEOMETRY_JOIN_GAP_METRES = 2.0
ROUTE_SNAP_TOLERANCE_METRES = 2.0


def native_chain_observation(
    receiver_edges: list[dict], adjacencies: list[dict],
) -> dict:
    """Verify native B adjacency for every nominated edge and retain all branches.

    Only graph-B directed IDs are compared to graph-B IDs. All native
    continuations, including unselected, nonroad, reverse and inaccessible
    directions, are preserved as evidence; no branch is declared impossible.
    """
    if (not isinstance(receiver_edges, list) or
            not 2 <= len(receiver_edges) <= MAX_SELECTED_B_EDGES or
            not isinstance(adjacencies, list) or
            len(adjacencies) != len(receiver_edges)):
        raise ValueError("Require 2–16 selected B edges and one native adjacency per edge")
    rows = [checked_edge(edge) for edge in receiver_edges]
    ids = [row["sourceGraphId"] for row in rows]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate directed B GraphId in selected chain")
    if sum(len(row["directedGeometry"]) for row in rows) > MAX_NATIVE_VERTICES:
        raise ValueError("Selected B chain exceeds native geometry vertex bound")

    observed = []
    for i, (row, adjacency) in enumerate(zip(rows, adjacencies)):
        if (not isinstance(adjacency, dict) or
                adjacency.get("sourceGraphId") != row["sourceGraphId"] or
                adjacency.get("endNodeGraphId") != row["endNodeGraphId"] or
                adjacency.get("wayId") != row["wayId"] or
                adjacency.get("forwardAccess") != row["forwardAccess"]):
            raise ValueError("B adjacency source identity does not match geometry")
        edges = adjacency.get("outgoingDirectedEdges")
        degree = adjacency.get("nativeOutgoingDegree")
        if (type(degree) is not int or not 1 <= degree <= MAX_NATIVE_OUTGOING or
                not isinstance(edges, list) or len(edges) != degree):
            raise ValueError("Incomplete or excessive native B outgoing degree")
        opposing = adjacency.get("opposingGraphId")
        if type(opposing) is not int or opposing <= 0:
            raise ValueError("Missing native opposing directed identity")
        seen = set()
        for edge in edges:
            if not isinstance(edge, dict):
                raise ValueError("Malformed native B outgoing edge")
            gid, end, mask = (
                edge.get("graphId"), edge.get("endNodeGraphId"),
                edge.get("forwardAccess"),
            )
            if (type(gid) is not int or gid <= 0 or gid in seen or
                    type(end) is not int or end <= 0 or
                    type(mask) is not int or not 0 <= mask < 2**32):
                raise ValueError("Duplicate or malformed B outgoing edge identity")
            seen.add(gid)
            if any(type(edge.get(k)) is not bool for k in
                   ("isRoad", "isShortcut", "autoBit", "motorcycleBit")):
                raise ValueError("Incomplete native B outgoing edge metadata")
            if (edge["autoBit"] != bool(mask & MODES["auto"]) or
                    edge["motorcycleBit"] != bool(mask & MODES["motorcycle"])):
                raise ValueError("B outgoing mode flags contradict native mask")
        if opposing not in seen:
            raise ValueError("Native opposing edge missing from B outgoing inventory")
        selected_next = ids[i + 1] if i + 1 < len(rows) else None
        if selected_next is not None:
            match = [edge for edge in edges if edge["graphId"] == selected_next]
            if len(match) != 1:
                raise ValueError("Selected B chain is not native-directed adjacent")
            if (match[0]["endNodeGraphId"] != rows[i + 1]["endNodeGraphId"] or
                    match[0]["forwardAccess"] != rows[i + 1]["forwardAccess"]):
                raise ValueError("Selected B successor metadata mismatch")
        observed.append({
            "incomingGraphId": row["sourceGraphId"],
            "endNodeGraphId": row["endNodeGraphId"],
            "nativeOutgoingDegree": degree,
            "selectedNextGraphId": selected_next,
            "nativeOpposingGraphId": opposing,
            "allNativeOutgoingAlternatives": edges,
        })

    return {
        "selectedGraphLocalDirectedChain": ids,
        "graphBNativeAdjacency": "CONFIRMED_FOR_SELECTED_EDGES_ONLY",
        "selectedEdgeCount": len(ids),
        "allBranchInventories": observed,
        "allNativeOutgoingAlternativesRetained": True,
        "globalFrontierCoverage": "NOT_VERIFIED",
    }


def source_tail_on_b_chain(source: dict, receiver_edges: list[dict]) -> dict:
    """Measure A's last 20m against a topologically checked B directed chain.

    The observation admits different graph edge subdivisions. Geometric
    co-location and a monotone projection NEVER validate a cross-graph turn.
    """
    a = checked_edge(source)
    rows = [checked_edge(edge) for edge in receiver_edges]
    geometry = list(rows[0]["directedGeometry"])
    join_gaps = []
    for row in rows[1:]:
        segment = row["directedGeometry"]
        gap = distance(geometry[-1], segment[0])
        join_gaps.append(round(gap, 3))
        if gap > MAX_GEOMETRY_JOIN_GAP_METRES:
            raise ValueError("Graph B native adjacent edges have inconsistent geometry")
        geometry.extend(segment[1:])
    samples = tail_points(a["directedGeometry"])
    projections = [nearest(sample, geometry) for sample in samples]
    close = [p for p in projections if p["metres"] <= GEOMETRY_OBSERVATION_METRES]
    directed = [p["distanceAlongDirectedEdgeMeters"] for p in close]
    if len(directed) < 2:
        order = "INSUFFICIENT_DIRECTED_OVERLAP_SAMPLES"
    elif all(x > y + 0.25 for x, y in zip(directed, directed[1:])):
        order = "SELECTED_B_CHAIN_ALIGNED_SAMPLES_ONLY"
    elif all(x + 0.25 < y for x, y in zip(directed, directed[1:])):
        order = "SELECTED_B_CHAIN_OPPOSED_SAMPLES_ONLY"
    else:
        order = "SELECTED_B_CHAIN_DIRECTION_AMBIGUOUS"
    return {
        "sourceTerminalToSelectedBGeometryMeters": round(projections[0]["metres"], 3),
        "sourceTailSamples": len(samples),
        "tailSamplesWithinOneMetre": len(close),
        "maximumSampleGapMeters": round(max(p["metres"] for p in projections), 3),
        "selectedReceiverGraphEdgeCount": len(rows),
        "nativeSelectedBGeometryJoinGapsMeters": join_gaps,
        "sampledDirectedOrder": order,
        "sampledGeometryCoversTail": len(close) == len(samples),
        "scope": "NOMINATED_CHAIN_SAMPLED_OBSERVATION_ONLY",
        "crossGraphPhysicalContinuity": "NOT_VERIFIED",
    }


def trace_selected_b_chain(
    config_b: Path, receiver_edges: list[dict], mode: str,
    route_fn: Callable = route,
    trace_fn: Callable = trace_directed_ids,
) -> dict:
    """Observe a B-only route that uses all nominated directed edges in order."""
    if mode not in MODES:
        raise ValueError("Unsupported vehicle mode")
    rows = [checked_edge(edge) for edge in receiver_edges]
    identities = [r["sourceGraphId"] for r in rows]
    base = {
        "selectedBGraphLocalDirectedIds": identities,
        "mode": mode,
        "graphBLocalTrace": "NOT_VERIFIED",
        "crossGraphTurnLegality": "NOT_VERIFIED",
    }
    if any(not row["forwardAccess"] & MODES[mode] for row in rows):
        return {**base, "status": "UNPROVEN_FOR_THIS_MODE",
                "reason": "A selected B native edge lacks the requested mode access"}
    try:
        origin, _ = probe_point(rows[0]["directedGeometry"], incoming=False)
        endpoint, _ = probe_point(rows[-1]["directedGeometry"], incoming=True)
        leg = route_fn(config_b, origin, endpoint, mode)
        if leg.get("status") != "SUCCEEDED":
            return {**base, "status": "INCONCLUSIVE",
                    "reason": "Graph B local Valhalla route was unavailable or failed"}
        for name in ("startOffsetMeters", "endOffsetMeters"):
            value = leg.get(name)
            if (type(value) not in (int, float) or not math.isfinite(value)
                    or value < 0 or value > ROUTE_SNAP_TOLERANCE_METRES):
                return {**base, "status": "UNPROVEN_FOR_THIS_ROUTE",
                        "reason": "B-local Valhalla endpoint snapped away"}
        if (distance(leg["startActual"], origin) > ROUTE_SNAP_TOLERANCE_METRES
                or distance(leg["endActual"], endpoint) > ROUTE_SNAP_TOLERANCE_METRES):
            return {**base, "status": "UNPROVEN_FOR_THIS_ROUTE",
                    "reason": "B-local route does not reach selected edge points"}
        actual = trace_fn(config_b, leg["encodedShape"], mode)
        if not actual:
            return {**base, "status": "INCONCLUSIVE",
                    "reason": "B-local directed edge trace unavailable"}
        if not isinstance(actual, list) or any(type(x) is not int or x <= 0 for x in actual):
            return {**base, "status": "INCONCLUSIVE",
                    "reason": "Malformed B-local directed edge trace"}
        matches = [i for i in range(len(actual) - len(identities) + 1)
                   if actual[i:i + len(identities)] == identities]
        if not matches:
            return {**base, "status": "UNPROVEN_FOR_THIS_ROUTE",
                    "reason": "Valhalla used another B-local directed path",
                    "actualTracedGraphIds": actual[:64],
                    "traceTruncatedForReport": len(actual) > 64,
                    "totalTracedEdgeCount": len(actual)}
        return {
            **base, "status": "B_GRAPH_DIRECTED_CHAIN_TRACED_FOR_THIS_LOCAL_ROUTE",
            "graphBLocalTrace": "MATCHED_THIS_LOCAL_ROUTE_ONLY",
            "matchedTraceIndex": matches[0],
            "actualTracedGraphIds": actual[:64],
            "traceTruncatedForReport": len(actual) > 64,
            "totalTracedEdgeCount": len(actual),
            "durationSeconds": leg["durationSeconds"],
            "distanceKm": leg["distanceKm"],
        }
    except (ValueError, OSError, TypeError, KeyError, subprocess.TimeoutExpired) as error:
        return {**base, "status": "INCONCLUSIVE", "reason": str(error)[:240]}


def inspect(
    source: dict, receiver_edges: list[dict], adjacencies: list[dict],
    config_b: Path, mode: str, route_fn: Callable = route,
    trace_fn: Callable = trace_directed_ids,
) -> dict:
    a = checked_edge(source)
    native = native_chain_observation(receiver_edges, adjacencies)
    geometry = source_tail_on_b_chain(source, receiver_edges)
    local = trace_selected_b_chain(config_b, receiver_edges, mode, route_fn, trace_fn)
    return {
        "schema": "roadpilot.native-f8-directed-chain-geometry-witness",
        "version": 0, "mode": mode,
        "selection": "ONE_NOMINATED_A_FINAL_EDGE_AND_EXPLICIT_B_DIRECTED_CHAIN",
        "sourceDirectedGraphId": a["sourceGraphId"],
        "sourceModeForwardAccess": bool(a["forwardAccess"] & MODES[mode]),
        "receiverTopology": native,
        "directedGeometryObservation": geometry,
        "receivingGraphRouteObservation": local,
        "crossGraphPhysicalContinuity": "NOT_VERIFIED",
        "crossSeamTurnLegality": "NOT_VERIFIED",
        "androidF8Parity": "NOT_VERIFIED",
        "discoveryCoverage": "NOT_VERIFIED",
        "routeOptimality": "NOT_VERIFIED",
        "productionPublication": "BLOCKED",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("pair", "from-manifest", "to-manifest", "native-endpoints-binary"):
        parser.add_argument("--" + field, type=Path, required=True)
    parser.add_argument("--direction", choices=("from-to", "to-from"), required=True)
    parser.add_argument("--mode", choices=sorted(MODES), required=True)
    parser.add_argument("--source-graph-id", type=int, required=True)
    parser.add_argument("--receiver-edge-id", type=int, action="append", required=True)
    args = parser.parse_args()
    ids = args.receiver_edge_id
    if (args.source_graph_id <= 0 or not 2 <= len(ids) <= MAX_SELECTED_B_EDGES
            or any(type(x) is not int or x <= 0 for x in ids)
            or len(set(ids)) != len(ids)):
        raise ValueError("Invalid or duplicate explicitly nominated graph-local edges")
    binary = args.native_endpoints_binary
    v = subprocess.run([str(binary), "--version"], capture_output=True,
                       text=True, timeout=15, check=True)
    if v.stdout.strip() != "3.6.3":
        raise ValueError("M6 requires the pinned Valhalla 3.6.3 GraphReader")
    pair = json.loads(args.pair.read_text(encoding="utf-8"))
    pair_identity(pair)

    with tempfile.TemporaryDirectory(prefix="roadpilot-f8-m6-directed-chain-") as folder:
        temporary = Path(folder)
        from_manifest = json.loads(args.from_manifest.read_text(encoding="utf-8"))
        to_manifest = json.loads(args.to_manifest.read_text(encoding="utf-8"))
        from_graph, cfg_a = graph_manifest_info(
            args.from_manifest, pair["fromRegionId"],
            to_manifest["source"]["primaryGeofabrikId"],
            pair["fromBoundaryFingerprint"], temporary, "A",
        )
        to_graph, cfg_b = graph_manifest_info(
            args.to_manifest, pair["toRegionId"],
            from_manifest["source"]["primaryGeofabrikId"],
            pair["toBoundaryFingerprint"], temporary, "B",
        )
        verify_retained_graph_identity(pair, from_graph, to_graph)
        if args.direction == "to-from":
            cfg_a, cfg_b = cfg_b, cfg_a
        source = native_rows(binary, cfg_a, [args.source_graph_id], temporary)[0]
        receiver = native_rows(binary, cfg_b, ids, temporary)
        adjacency = [native_adjacency(binary, cfg_b, edge, temporary)
                     for edge in ids]
        report = inspect(source, receiver, adjacency, cfg_b, args.mode)
        report.update({
            "pairId": pair["pairId"], "direction": args.direction,
            "graphFingerprints": {
                "from": pair["fromGraphFingerprint"],
                "to": pair["toGraphFingerprint"],
            },
            "boundaryFingerprints": {
                "from": pair["fromBoundaryFingerprint"],
                "to": pair["toBoundaryFingerprint"],
            },
        })
    print(json.dumps(report, separators=(",", ":"), sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired,
            subprocess.CalledProcessError) as error:
        print("NATIVE_F8_M6_DIRECTED_CHAIN_ERROR: " + str(error)[:350], file=sys.stderr)
        sys.exit(2)
