#!/usr/bin/env python3
"""Observe one exact F8 source terminal against B's real directed turn choices.

No production handoff, no pre-Valhalla eligibility filter, no Android parity.
The proof is strictly of the *receiving graph's* traced native turn, never of a
cross-graph turn. All native outgoing alternatives are retained in the report.
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
    MODES, GEOMETRY_OBSERVATION_METRES, checked_edge, inspect_geometry,
    native_rows, nearest, tail_points,
)

MAX_NATIVE_OUTGOING = 256  # Fail closed, never represent a truncated capture as complete.
MAX_NATIVE_GEOMETRY_VERTICES = 250000  # Aggregate allocation safety; explicit abort only.
MAX_TURN_PROBES = 32
NEAR_END_MAX_METRES = 20.0


def point_along(vertices: list[dict], metres_from_start: float) -> dict:
    if type(metres_from_start) not in (int, float) or not math.isfinite(metres_from_start):
        raise ValueError("Invalid directed distance")
    lengths = [distance(a, b) for a, b in zip(vertices, vertices[1:])]
    total = sum(lengths)
    if not 0 <= metres_from_start <= total or total <= 0:
        raise ValueError("Point lies outside directed edge")
    remaining = metres_from_start
    for i, length in enumerate(lengths):
        if remaining <= length and length > 0.001:
            f = remaining / length
            a, b = vertices[i:i + 2]
            return {"lat": a["lat"] + (b["lat"] - a["lat"]) * f,
                    "lng": a["lng"] + (b["lng"] - a["lng"]) * f}
        remaining -= length
    return dict(vertices[-1])


def probe_point(vertices: list[dict], *, incoming: bool) -> tuple[dict, float]:
    total = sum(distance(a, b) for a, b in zip(vertices, vertices[1:]))
    if total < 2.0:
        raise ValueError("Native directed edge too short for local turn probe")
    # Retain margin from both ends; arbitrary travel distance is a diagnostic
    # and never an eligibility gate or evidence of route optimality.
    offset = min(NEAR_END_MAX_METRES, total * .5)
    position = total - offset if incoming else offset
    return point_along(vertices, position), round(total, 3)


def native_adjacency(binary: Path, config: Path, receiver_id: int,
                     temporary: Path) -> dict:
    ids = temporary / "selected-incoming-id.txt"
    ids.write_text(str(receiver_id) + "\n", encoding="ascii")
    completed = subprocess.run(
        [str(binary), str(config), str(ids), "--continuations"],
        capture_output=True, text=True, timeout=90, check=False)
    if completed.returncode:
        raise ValueError("Native receiver adjacency failed; discard partial stdout: "
                         + completed.stderr[-200:])
    lines = completed.stdout.splitlines()
    if len(lines) != 1:
        raise ValueError("Unexpected native receiver adjacency row count")
    row = json.loads(lines[0])
    if row.get("sourceGraphId") != receiver_id:
        raise ValueError("Native receiver adjacency identity changed")
    return row


def validate_adjacency(receiver: dict, adjacency: dict,
                       outgoings: list[dict]) -> list[dict]:
    """Require exact native end-node provenance and all outgoing edge identities."""
    receiver = checked_edge(receiver)
    if (adjacency.get("sourceGraphId") != receiver["sourceGraphId"]
            or adjacency.get("endNodeGraphId") != receiver["endNodeGraphId"]
            or adjacency.get("wayId") != receiver["wayId"]
            or adjacency.get("forwardAccess") != receiver["forwardAccess"]):
        raise ValueError("Native incoming edge or end-node identity mismatch")
    reverse = adjacency.get("opposingGraphId")
    edges = adjacency.get("outgoingDirectedEdges")
    if type(reverse) is not int or reverse <= 0:
        raise ValueError("No native opposing edge identity")
    if not isinstance(edges, list) or not 1 <= len(edges) <= MAX_NATIVE_OUTGOING:
        raise ValueError("Invalid or excessive native outgoing edge count")
    raw_ids = []
    for entry in edges:
        if not isinstance(entry, dict):
            raise ValueError("Invalid outgoing adjacency record")
        gid = entry.get("graphId")
        mask = entry.get("forwardAccess")
        if (type(gid) is not int or gid <= 0 or
                type(mask) is not int or not 0 <= mask < 2**32 or
                type(entry.get("endNodeGraphId")) is not int or
                entry["endNodeGraphId"] <= 0):
            raise ValueError("Invalid native outgoing edge identity/access")
        if any(type(entry.get(key)) is not bool for key in (
                "isRoad", "isShortcut", "autoBit", "motorcycleBit")):
            raise ValueError("Invalid native outgoing edge metadata")
        if entry["autoBit"] != bool(mask & MODES["auto"]) or (
                entry["motorcycleBit"] != bool(mask & MODES["motorcycle"])):
            raise ValueError("Native mode bits contradict access mask")
        raw_ids.append(gid)
    if len(set(raw_ids)) != len(raw_ids) or reverse not in raw_ids:
        raise ValueError("Duplicate outgoing directed ID or absent native opposing edge")
    if len(outgoings) != len(raw_ids) or [r.get("sourceGraphId") for r in outgoings] != raw_ids:
        raise ValueError("Missing/reordered/extra native outgoing geometry")
    if sum(len(row.get("directedGeometry", ())) if isinstance(
            row.get("directedGeometry"), list) else 0 for row in outgoings
           ) > MAX_NATIVE_GEOMETRY_VERTICES:
        raise ValueError("Native outgoing geometry exceeds diagnostic vertex safety bound")
    for entry, raw in zip(edges, outgoings):
        out = checked_edge(raw)
        if (out["sourceGraphId"] != entry["graphId"]
                or out["endNodeGraphId"] != entry["endNodeGraphId"]
                or out["forwardAccess"] != entry["forwardAccess"]):
            raise ValueError("Native outgoing edge mismatch between geometry and adjacency")
    return edges


def trace_turn(config: Path, incoming: dict, outgoing: dict, mode: str,
               route_fn: Callable = route,
               trace_fn: Callable = trace_directed_ids) -> dict:
    """Prove only that B's actual Valhalla route traces the nominated B turn."""
    incoming = checked_edge(incoming)
    outgoing = checked_edge(outgoing)
    base = {
        "incomingGraphId": incoming["sourceGraphId"],
        "outgoingGraphId": outgoing["sourceGraphId"],
        "costing": mode,
        "graphLocalTurnProof": "NOT_VERIFIED",
    }
    if mode not in MODES:
        raise ValueError("Unsupported mode")
    if (not incoming["forwardAccess"] & MODES[mode] or
            not outgoing["forwardAccess"] & MODES[mode]):
        return {**base, "status": "UNPROVEN",
                "reason": "Native forward-access bits do not support the mode"}
    try:
        start, in_length = probe_point(incoming["directedGeometry"], incoming=True)
        end, out_length = probe_point(outgoing["directedGeometry"], incoming=False)
        result = route_fn(config, start, end, mode)
        if result.get("status") != "SUCCEEDED":
            return {**base,
                    "status": "INCONCLUSIVE" if result.get("status") == "INCONCLUSIVE"
                    else "UNPROVEN",
                    "reason": "Valhalla local B turn route did not succeed"}
        if (result["startOffsetMeters"] > 2.0 or
                result["endOffsetMeters"] > 2.0 or
                distance(result["startActual"], start) > 2.0 or
                distance(result["endActual"], end) > 2.0):
            return {**base, "status": "UNPROVEN",
                    "reason": "Valhalla snapped away from requested B turn probe points"}
        actual_ids = trace_fn(config, result["encodedShape"], mode)
        if not actual_ids:
            return {**base, "status": "INCONCLUSIVE",
                    "reason": "Directed Valhalla trace unavailable"}
        expected = [incoming["sourceGraphId"], outgoing["sourceGraphId"]]
        consecutive = any(actual_ids[i:i + 2] == expected
                          for i in range(len(actual_ids) - 1))
        if not consecutive:
            return {**base, "status": "UNPROVEN",
                    "reason": "Valhalla routed an alternative turn",
                    "actualTracedGraphIds": actual_ids[:64],
                    "totalTracedEdgeCount": len(actual_ids),
                    "traceTruncatedForReport": len(actual_ids) > 64}
        matched_index = next(i for i in range(len(actual_ids) - 1)
                             if actual_ids[i:i + 2] == expected)
        return {**base, "status": "B_GRAPH_DIRECTED_TURN_TRACED_FOR_THIS_LOCAL_ROUTE",
                "graphLocalTurnProof": "TRACED_FOR_THIS_LOCAL_ROUTE_ONLY",
                "actualTracedGraphIds": actual_ids[:64],
                "totalTracedEdgeCount": len(actual_ids),
                "matchedIncomingEdgeTraceIndex": matched_index,
                "traceTruncatedForReport": len(actual_ids) > 64,
                "incomingLengthMeters": in_length,
                "outgoingLengthMeters": out_length,
                "durationSeconds": result["durationSeconds"],
                "distanceKm": result["distanceKm"]}
    except (OSError, subprocess.TimeoutExpired, ValueError, TypeError, KeyError) as error:
        return {**base, "status": "INCONCLUSIVE", "reason": str(error)[:250]}



def direction_observation(source: dict, receiver: dict) -> dict:
    """Monotone native directed order for the final A edge samples in one B edge.

    A direction observation is not a producer filter and does not prove the
    receiving graph continues after the terminal. If the B graph split an A
    road edge, missing tail samples remain unresolved, not rejected.
    """
    a = checked_edge(source)
    b = checked_edge(receiver)
    samples = tail_points(a["directedGeometry"])  # from terminal back upstream
    projected = [nearest(sample, b["directedGeometry"]) for sample in samples]
    matches = [r for r in projected if r["metres"] <= GEOMETRY_OBSERVATION_METRES]
    distances = [r["distanceAlongDirectedEdgeMeters"] for r in matches]
    if len(distances) < 2:
        state = "INSUFFICIENT_SAMPLED_SEGMENT_OVERLAP"
    elif all(left > right + .25 for left, right in zip(distances, distances[1:])):
        state = "SAMPLED_DIRECTED_ORDER_ALIGNED_ONLY"
    elif all(left + .25 < right for left, right in zip(distances, distances[1:])):
        state = "SAMPLED_DIRECTED_ORDER_OPPOSED_ONLY"
    else:
        state = "AMBIGUOUS_SAMPLED_DIRECTED_ORDER"
    return {
        "state": state,
        "matchedTailSamples": len(matches),
        "totalTailSamples": len(samples),
        "maxObservedTailGapMeters": round(
            max(r["metres"] for r in projected), 3),
        "directionalSegmentEquivalence": "NOT_VERIFIED",
        "discoveryEligibilityFiltered": False,
    }


def inspect_seam(source: dict, receiver: dict, adjacency: dict,
                 outgoings: list[dict], config_b: Path, mode: str,
                 max_probes: int,
                 route_fn: Callable = route,
                 trace_fn: Callable = trace_directed_ids) -> dict:
    if type(max_probes) is not int or not 1 <= max_probes <= MAX_TURN_PROBES:
        raise ValueError("Unsupported explicit turn probe budget")
    if mode not in MODES:
        raise ValueError("Unsupported mode")
    edges = validate_adjacency(receiver, adjacency, outgoings)
    geometry = inspect_geometry(source, [receiver], mode)
    all_results = []
    for i, (edge, shape) in enumerate(zip(edges, outgoings)):
        record = {
            "outgoingDirectedGraphId": edge["graphId"],
            "nativeOpposingEdge": edge["graphId"] == adjacency["opposingGraphId"],
            "isRoad": edge["isRoad"],
            "isShortcut": edge["isShortcut"],
            "modeForwardAccess": bool(edge["forwardAccess"] & MODES[mode]),
        }
        if i >= max_probes:
            result = {"status": "NOT_PROBED_BUDGET"}
        else:
            result = trace_turn(config_b, receiver, shape, mode, route_fn, trace_fn)
        all_results.append({**record, "routeEvidence": result})
    proved = sum(row["routeEvidence"]["status"] ==
                 "B_GRAPH_DIRECTED_TURN_TRACED_FOR_THIS_LOCAL_ROUTE"
                 for row in all_results)
    return {
        "schema": "roadpilot.native-f8-directed-seam-turn-diagnostic",
        "version": 0,
        "mode": mode,
        "sourceDirectedGraphId": source["sourceGraphId"],
        "receiverIncomingGraphId": receiver["sourceGraphId"],
        "receiverEndNodeGraphId": receiver["endNodeGraphId"],
        "selectedSourceFinalEdgeOnly": True,
        "receiverGeometryObservation": geometry,
        "receiverDirectedOrderObservation": direction_observation(source, receiver),
        "outgoingNativeCount": len(all_results),
        "probed": min(max_probes, len(all_results)),
        "unprobed": max(0, len(all_results) - max_probes),
        "bGraphTurnTracesMatchedForLocalRoute": proved,
        "allNativeOutgoingAlternatives": all_results,
        "crossGraphDirectedPhysicalContinuity": "NOT_VERIFIED",
        "crossSeamTurnLegality": "NOT_VERIFIED",
        "androidF8Parity": "NOT_VERIFIED",
        "discoveryCoverage": "NOT_VERIFIED",
        "routeOptimality": "NOT_VERIFIED",
        "productionPublication": "BLOCKED",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("pair", "from-manifest", "to-manifest", "native-endpoints-binary"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--direction", required=True, choices=["from-to", "to-from"])
    parser.add_argument("--mode", required=True, choices=sorted(MODES))
    parser.add_argument("--source-graph-id", required=True, type=int)
    parser.add_argument("--receiver-incoming-graph-id", required=True, type=int)
    parser.add_argument("--max-turn-probes", type=int, default=16)
    args = parser.parse_args()
    if (args.source_graph_id <= 0 or args.receiver_incoming_graph_id <= 0 or
            not 1 <= args.max_turn_probes <= MAX_TURN_PROBES):
        raise ValueError("Invalid directed identities or turn probe budget")
    version = subprocess.run([str(args.native_endpoints_binary), "--version"],
                             text=True, capture_output=True, timeout=15, check=True)
    if version.stdout.strip() != "3.6.3":
        raise ValueError("Valhalla native endpoint extractor must be 3.6.3")
    pair = json.loads(args.pair.read_text(encoding="utf-8"))
    pair_identity(pair)
    with tempfile.TemporaryDirectory(prefix="roadpilot-f8-directed-turn-") as folder:
        temporary = Path(folder)
        manifest_a = json.loads(args.from_manifest.read_text(encoding="utf-8"))
        manifest_b = json.loads(args.to_manifest.read_text(encoding="utf-8"))
        graph_a, cfg_a = graph_manifest_info(
            args.from_manifest, pair["fromRegionId"],
            manifest_b["source"]["primaryGeofabrikId"],
            pair["fromBoundaryFingerprint"], temporary, "A")
        graph_b, cfg_b = graph_manifest_info(
            args.to_manifest, pair["toRegionId"],
            manifest_a["source"]["primaryGeofabrikId"],
            pair["toBoundaryFingerprint"], temporary, "B")
        verify_retained_graph_identity(pair, graph_a, graph_b)
        if args.direction == "to-from":
            cfg_a, cfg_b = cfg_b, cfg_a
        binary = args.native_endpoints_binary
        source = native_rows(binary, cfg_a, [args.source_graph_id], temporary)[0]
        incoming = native_rows(binary, cfg_b,
                               [args.receiver_incoming_graph_id], temporary)[0]
        adjacency = native_adjacency(binary, cfg_b, args.receiver_incoming_graph_id,
                                     temporary)
        edges = adjacency["outgoingDirectedEdges"]
        if (not isinstance(edges, list) or not 1 <= len(edges) <= MAX_NATIVE_OUTGOING
                or any(type(r.get("graphId")) is not int for r in edges)):
            raise ValueError("Invalid/oversized native receiver adjacency; no truncated output")
        outgoing_rows = native_rows(binary, cfg_b,
                                    [row["graphId"] for row in edges], temporary)
        report = inspect_seam(
            source, incoming, adjacency, outgoing_rows,
            cfg_b, args.mode, args.max_turn_probes)
        report.update({
            "pairId": pair["pairId"], "direction": args.direction,
            "graphFingerprints": {"from": pair["fromGraphFingerprint"],
                                  "to": pair["toGraphFingerprint"]},
        })
    print(json.dumps(report, separators=(",", ":"), sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, TypeError, KeyError, subprocess.TimeoutExpired,
            subprocess.CalledProcessError) as error:
        print("NATIVE_F8_DIRECTED_TURN_DIAGNOSTIC_ERROR: " + str(error)[:350],
              file=sys.stderr)
        sys.exit(2)
