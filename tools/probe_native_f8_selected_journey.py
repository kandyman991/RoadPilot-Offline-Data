#!/usr/bin/env python3
"""Read-only M5: correlate A's selected terminal route with all B-local turn evidence.

One explicit A final directed edge and one explicitly nominated B incoming
directed edge only. Every B outgoing edge is reported; no native F8 proposal is
removed or rejected from discovery. Even a matched pair of graph-local routes
does NOT prove cross-graph physical continuity or legal seam transfer.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Callable

from build_native_f8_pair_evidence import pair_identity
from native_f8_inputs import graph_manifest_info
from probe_native_f8_journey import route, verify_retained_graph_identity
from probe_native_f8_terminal_handoffs import (
    check_terminal, strict_point, trace_directed_ids,
)
from probe_native_f8_terminal_geometry import checked_edge, native_rows
from probe_native_f8_directed_turn import (
    MAX_NATIVE_OUTGOING, MAX_TURN_PROBES, MODES, inspect_seam,
    native_adjacency, validate_adjacency,
)


def evaluate_selected_journey(
    source: dict, receiver: dict, adjacency: dict, outgoing: list[dict],
    config_a: Path, config_b: Path, origin: dict, destination: dict,
    mode: str, max_turn_probes: int = 16,
    route_fn: Callable = route,
    trace_fn: Callable = trace_directed_ids,
) -> dict:
    """Correlate independent proofs for one nominated hypothesis, never merge them.

    The B-local probe proves a B turn only; the A/B journey probe proves
    requested graph-local traces only. Neither is an Android F8 parity capture
    or a cross-seam turn legality check.
    """
    if mode not in MODES or type(max_turn_probes) is not int or not 1 <= max_turn_probes <= MAX_TURN_PROBES:
        raise ValueError("Unsupported mode or turn diagnostic budget")
    origin = strict_point(origin, "journey origin")
    destination = strict_point(destination, "journey destination")
    a = checked_edge(source)
    b = checked_edge(receiver)
    edges = validate_adjacency(receiver, adjacency, outgoing)

    # No same-way, heading, proximity or numerical cross-graph ID eligibility gate.
    local = inspect_seam(
        source, receiver, adjacency, outgoing, config_b, mode, max_turn_probes,
        route_fn=route_fn, trace_fn=trace_fn,
    )
    mode_outgoing = {
        vehicle: sorted(row["graphId"] for row in edges
                        if row["isRoad"] and not row["isShortcut"]
                        and row["graphId"] != adjacency["opposingGraphId"]
                        and row["forwardAccess"] & mask)
        for vehicle, mask in MODES.items()
    }
    selected = {
        "sourceDirectedGraphId": a["sourceGraphId"],
        "receiverIncomingGraphId": b["sourceGraphId"],
        "handoff": a["directedGeometry"][-1],
        "receiverEnd": b["directedGeometry"][-1],
        "sourceForwardAccess": a["forwardAccess"],
        "receiverForwardAccess": b["forwardAccess"],
        "outgoing": mode_outgoing,
    }
    journey = check_terminal(
        selected, config_a, config_b, origin, destination, mode,
        route_fn=route_fn, trace_fn=trace_fn,
    )

    return {
        "schema": "roadpilot.native-f8-selected-terminal-journey-diagnostic",
        "version": 0,
        "mode": mode,
        "selection": "EXPLICIT_SOURCE_AND_RECEIVER_DIRECTED_IDS",
        "terminalSourceIdentity": "NOMINATED_ONLY_NOT_A_GRAPH_WIDE_CENSUS",
        "sourceDirectedGraphId": a["sourceGraphId"],
        "receiverIncomingGraphId": b["sourceGraphId"],
        "origin": origin,
        "destination": destination,
        "bLocalTurnObservation": local,
        "twoGraphJourneyObservation": journey,
        "bLocalTracedTurns": local["bGraphTurnTracesMatchedForLocalRoute"],
        "twoGraphLocalTracesMatched": (
            journey["status"] == "GRAPH_LOCAL_TRACES_MATCHED_FOR_THIS_JOURNEY"
        ),
        "outgoingAlternativesEnumerated": len(edges),
        "outgoingAlternativesProbed": local["probed"],
        "outgoingAlternativesUnprobed": local["unprobed"],
        "crossGraphPhysicalContinuity": "NOT_VERIFIED",
        "crossSeamTurnLegality": "NOT_VERIFIED",
        "androidF8Parity": "NOT_VERIFIED",
        "discoveryCoverage": "NOT_VERIFIED",
        "journeyOptimality": "NOT_VERIFIED",
        "productionPublication": "BLOCKED",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("pair", "from-manifest", "to-manifest", "native-endpoints-binary"):
        parser.add_argument("--" + field, required=True, type=Path)
    parser.add_argument("--direction", choices=("from-to", "to-from"), required=True)
    parser.add_argument("--mode", choices=sorted(MODES), required=True)
    parser.add_argument("--source-graph-id", required=True, type=int)
    parser.add_argument("--receiver-incoming-graph-id", required=True, type=int)
    for field in ("start-lat", "start-lng", "end-lat", "end-lng"):
        parser.add_argument("--" + field, required=True, type=float)
    parser.add_argument("--max-turn-probes", type=int, default=16)
    args = parser.parse_args()

    if args.source_graph_id <= 0 or args.receiver_incoming_graph_id <= 0:
        raise ValueError("Invalid native graph-local directed edge identity")
    if not 1 <= args.max_turn_probes <= MAX_TURN_PROBES:
        raise ValueError("Invalid explicit B turn probe budget")
    version = subprocess.run(
        [str(args.native_endpoints_binary), "--version"],
        capture_output=True, text=True, timeout=15, check=True,
    )
    if version.stdout.strip() != "3.6.3":
        raise ValueError("Exact Valhalla 3.6.3 native geometry extractor required")
    pair = json.loads(args.pair.read_text(encoding="utf-8"))
    pair_identity(pair)

    with tempfile.TemporaryDirectory(prefix="roadpilot-f8-selected-journey-") as scratch:
        temporary = Path(scratch)
        manifest_a = json.loads(args.from_manifest.read_text(encoding="utf-8"))
        manifest_b = json.loads(args.to_manifest.read_text(encoding="utf-8"))
        graph_a, config_a = graph_manifest_info(
            args.from_manifest, pair["fromRegionId"],
            manifest_b["source"]["primaryGeofabrikId"],
            pair["fromBoundaryFingerprint"], temporary, "A",
        )
        graph_b, config_b = graph_manifest_info(
            args.to_manifest, pair["toRegionId"],
            manifest_a["source"]["primaryGeofabrikId"],
            pair["toBoundaryFingerprint"], temporary, "B",
        )
        verify_retained_graph_identity(pair, graph_a, graph_b)
        if args.direction == "to-from":
            config_a, config_b = config_b, config_a

        source = native_rows(
            args.native_endpoints_binary, config_a,
            [args.source_graph_id], temporary,
        )[0]
        receiver = native_rows(
            args.native_endpoints_binary, config_b,
            [args.receiver_incoming_graph_id], temporary,
        )[0]
        adjacency = native_adjacency(
            args.native_endpoints_binary, config_b,
            args.receiver_incoming_graph_id, temporary,
        )
        entries = adjacency.get("outgoingDirectedEdges")
        if (not isinstance(entries, list) or not 1 <= len(entries) <= MAX_NATIVE_OUTGOING
                or any(not isinstance(entry, dict) or
                       type(entry.get("graphId")) is not int for entry in entries)):
            raise ValueError("Incomplete or excessive B native adjacency; abort")
        outgoings = native_rows(
            args.native_endpoints_binary, config_b,
            [entry["graphId"] for entry in entries], temporary,
        )
        report = evaluate_selected_journey(
            source, receiver, adjacency, outgoings,
            config_a, config_b,
            {"lat": args.start_lat, "lng": args.start_lng},
            {"lat": args.end_lat, "lng": args.end_lng},
            args.mode, args.max_turn_probes,
        )
        report.update({
            "direction": args.direction,
            "pairId": pair["pairId"],
            "graphFingerprints": {
                "from": pair["fromGraphFingerprint"],
                "to": pair["toGraphFingerprint"],
            },
            "boundaryFingerprints": {
                "from": pair["fromBoundaryFingerprint"],
                "to": pair["toBoundaryFingerprint"],
            },
        })
    print(json.dumps(report, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired,
            subprocess.CalledProcessError) as error:
        print("NATIVE_F8_SELECTED_JOURNEY_DIAGNOSTIC_ERROR: " + str(error)[:350],
              file=sys.stderr)
        sys.exit(2)
