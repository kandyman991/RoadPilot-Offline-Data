#!/usr/bin/env python3
"""Bounded, read-only native terminal-handoff *journey* proof.

Every selected terminal hypothesis must survive actual route and trace checks
on BOTH immutable Valhalla 3.6.3 graphs, including source final directed edge.
This never publishes a connectivity artifact, changes graphs, or claims that
unprobed alternatives are exhausted. Android F8 parity is NOT_VERIFIED.
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
from probe_native_f8_journey import (
    ARRIVAL_TOLERANCE_METERS, distance, route,
    service_payload, verify_retained_graph_identity,
)
from audit_native_f8_terminal_evidence import load_jsonl
from verify_native_f8_receiver_adjacency import (
    AUTO_ACCESS, MOTORCYCLE_ACCESS, validate_capture,
)

MODES = {"auto": AUTO_ACCESS, "motorcycle": MOTORCYCLE_ACCESS}
DIRECTIONS = {"from-to": "fromTo", "to-from": "toFrom"}
MAX_PROBES = 16
# This is a positive proof requirement, not a candidate discovery filter.
# Preserve every inconclusive hypothesis rather than silently dropping it.
EXACT_HANDOFF_TOLERANCE_METRES = 1.0


def strict_point(item: object, label: str) -> dict:
    if (not isinstance(item, dict) or set(item) != {"lat", "lng"} or
            any(type(item[k]) not in (int, float) or not math.isfinite(item[k])
                for k in ("lat", "lng")) or
            not -90 <= item["lat"] <= 90 or not -180 <= item["lng"] <= 180):
        raise ValueError(f"Invalid {label} coordinate")
    return {"lat": float(item["lat"]), "lng": float(item["lng"])}


def valid_pair_audit(pair: dict, audit: dict) -> None:
    pair_identity(pair)
    if (audit.get("schema") != "roadpilot.native-f8-receiver-topology-audit"
            or audit.get("version") != 0 or audit.get("pairId") != pair["pairId"]
            or audit.get("state") != "INCOMPLETE"
            or audit.get("androidParity") != "NOT_VERIFIED"
            or audit.get("productionPublication") != "BLOCKED"):
        raise ValueError("Expected the unpublished, incomplete native receiver audit")
    identities = audit.get("graphFingerprints")
    if (not isinstance(identities, dict) or
            identities.get("from") != pair["fromGraphFingerprint"] or
            identities.get("to") != pair["toGraphFingerprint"]):
        raise ValueError("Receiver audit graph fingerprint mismatch")


def candidate_pool(audit: dict, direction: str, receiver_rows: list[dict]) -> list[dict]:
    if direction not in DIRECTIONS:
        raise ValueError("Unsupported terminal travel direction")
    observations = audit[DIRECTIONS[direction]]["observations"]
    actual_receiver = validate_capture(observations, receiver_rows)
    pool: list[dict] = []
    unique = set()
    for source in observations:
        source_id = source["sourceDirectedGraphId"]
        handoff = strict_point(
            {"lat": source["sourceEnd"][0], "lng": source["sourceEnd"][1]},
            "source terminal")
        for match in source["nearbyReceiverIncoming"]:
            # The predecessor's same-way/native-deadend subset is a
            # *provisional catalog*, not a declaration that other roads fail.
            if not match["sameWay"] or match["receiverDeadend"]:
                continue
            receiver_id = match["receiverDirectedGraphId"]
            identity = (source_id, receiver_id)
            if identity in unique:
                raise ValueError("Duplicate source/receiver directed hypothesis")
            unique.add(identity)
            receiver = actual_receiver[receiver_id]
            outgoing = [
                edge for edge in receiver["outgoingDirectedEdges"]
                if edge["graphId"] != receiver["opposingGraphId"]
                and edge["isRoad"] and not edge["isShortcut"]
            ]
            pool.append({
                "sourceDirectedGraphId": source_id,
                "receiverIncomingGraphId": receiver_id,
                "receiverEndNodeGraphId": receiver["endNodeGraphId"],
                "sourceEndNodeGraphId": source["sourceEndNodeGraphId"],
                "handoff": handoff,
                "receiverEnd": strict_point(
                    {"lat": receiver["endLat"], "lng": receiver["endLon"]},
                    "receiver terminal"),
                "sourceForwardAccess": source["sourceForwardAccess"],
                "receiverForwardAccess": match["receiverForwardAccess"],
                "outgoing": {
                    mode: sorted(edge["graphId"] for edge in outgoing
                                 if edge[mode + "Bit" if mode == "auto" else "motorcycleBit"])
                    for mode in MODES
                },
            })
    return sorted(pool, key=lambda row: (
        row["sourceDirectedGraphId"], row["receiverIncomingGraphId"]))


def trace_directed_ids(config: Path, shape: str, mode: str,
                       timeout: int = 45) -> list[int] | None:
    """Return the exact directed GraphIds of a Valhalla-routed leg."""
    request = {
        "encoded_polyline": shape, "costing": mode, "shape_match": "edge_walk",
        "filters": {"attributes": ["edge.id"], "action": "include"},
    }
    try:
        result = subprocess.run(
            ["valhalla_service", str(config), "trace_attributes",
             json.dumps(request, separators=(",", ":"))],
            text=True, capture_output=True, timeout=timeout, check=False)
        if result.returncode:
            return None
        edges = service_payload(result.stdout).get("edges")
        if not isinstance(edges, list) or not edges:
            return None
        values = [edge["id"] for edge in edges]
        if any(type(value) is not int or value <= 0 for value in values):
            return None
        return values
    except (ValueError, TypeError, KeyError, IndexError, OSError,
            subprocess.TimeoutExpired):
        return None


def check_terminal(
    candidate: dict, config_a: Path, config_b: Path,
    start: dict, destination: dict, mode: str,
    route_fn: Callable = route, trace_fn: Callable = trace_directed_ids,
) -> dict:
    """Check two graph-local traces; never assert physical cross-graph continuity."""
    if mode not in MODES:
        raise ValueError("Unsupported vehicle mode")
    base = {
        "sourceDirectedGraphId": candidate["sourceDirectedGraphId"],
        "receiverIncomingGraphId": candidate["receiverIncomingGraphId"],
        "mode": mode, "coordinate": candidate["handoff"],
        "exactCrossGraphDirectedHandoff": "NOT_VERIFIED",
        "crossGraphPhysicalContinuity": "NOT_VERIFIED",
        "graphLocalDirectedLegTrace": "NOT_VERIFIED",
    }
    point = candidate["handoff"]
    matched = distance(point, candidate["receiverEnd"])
    base["sourceReceiverNodeGapMeters"] = round(matched, 3)
    try:
        first = route_fn(config_a, start, point, mode)
        if first["status"] != "SUCCEEDED":
            status = "INCONCLUSIVE" if first["status"] == "INCONCLUSIVE" else "UNPROVEN"
            return {**base, "status": status, "reason": "Graph A route did not succeed"}
        if (first["startOffsetMeters"] > ARRIVAL_TOLERANCE_METERS
                or first["endOffsetMeters"] > EXACT_HANDOFF_TOLERANCE_METRES):
            return {**base, "status": "UNPROVEN",
                    "reason": "Graph A route does not reach the exact terminal"}
        a_edges = trace_fn(config_a, first["encodedShape"], mode)
        if not a_edges:
            return {**base, "status": "INCONCLUSIVE",
                    "reason": "Graph A directed route trace unavailable"}
        if a_edges[-1] != candidate["sourceDirectedGraphId"]:
            return {**base, "status": "UNPROVEN",
                    "reason": "Graph A actual final edge differs from nominated terminal",
                    "actualSourceLastGraphId": a_edges[-1]}

        second = route_fn(config_b, first["endActual"], destination, mode)
        if second["status"] != "SUCCEEDED":
            status = "INCONCLUSIVE" if second["status"] == "INCONCLUSIVE" else "UNPROVEN"
            return {**base, "status": status, "reason": "Graph B route did not succeed",
                    "actualSourceLastGraphId": a_edges[-1]}
        if (second["startOffsetMeters"] > EXACT_HANDOFF_TOLERANCE_METRES
                or second["endOffsetMeters"] > ARRIVAL_TOLERANCE_METERS
                or distance(first["endActual"], second["startActual"])
                > EXACT_HANDOFF_TOLERANCE_METRES):
            return {**base, "status": "UNPROVEN",
                    "reason": "Graph B start is not the exact source terminal",
                    "actualSourceLastGraphId": a_edges[-1]}
        b_edges = trace_fn(config_b, second["encodedShape"], mode)
        if not b_edges:
            return {**base, "status": "INCONCLUSIVE",
                    "reason": "Graph B directed route trace unavailable",
                    "actualSourceLastGraphId": a_edges[-1]}

        expected = set(candidate["outgoing"][mode])
        # A route can begin *at* the B node and immediately take a B outgoing
        # edge, or begin slightly earlier on the known receiver incoming edge
        # then continue onto an exact outgoing edge. Reverse-only is rejected.
        receiver_first = b_edges[0]
        continued = bool(
            (receiver_first in expected) or
            (receiver_first == candidate["receiverIncomingGraphId"]
             and len(b_edges) > 1 and b_edges[1] in expected))
        if not continued:
            return {**base, "status": "UNPROVEN",
                    "reason": "Graph B trace does not continue through nominated receiver node",
                    "actualSourceLastGraphId": a_edges[-1],
                    "actualReceiverFirstGraphId": receiver_first}
        if (not (candidate["sourceForwardAccess"] & MODES[mode])
                or not (candidate["receiverForwardAccess"] & MODES[mode])):
            return {**base, "status": "UNPROVEN",
                    "reason": "Source/receiver direction access is unsupported",
                    "actualSourceLastGraphId": a_edges[-1],
                    "actualReceiverFirstGraphId": receiver_first}
        if matched > EXACT_HANDOFF_TOLERANCE_METRES:
            return {**base, "status": "UNPROVEN",
                    "reason": "Graph A terminal and Graph B node are not co-located exactly",
                    "actualSourceLastGraphId": a_edges[-1],
                    "actualReceiverFirstGraphId": receiver_first}
        return {
            **base, "status": "GRAPH_LOCAL_TRACES_MATCHED_FOR_THIS_JOURNEY",
            "graphLocalDirectedLegTrace": "MATCHED_FOR_THIS_JOURNEY_ONLY",
            "actualSourceLastGraphId": a_edges[-1],
            "actualReceiverFirstGraphId": receiver_first,
            "durationSeconds": first["durationSeconds"] + second["durationSeconds"],
            "distanceKm": first["distanceKm"] + second["distanceKm"],
        }
    except (OSError, subprocess.TimeoutExpired, ValueError, TypeError, KeyError) as error:
        return {**base, "status": "INCONCLUSIVE", "reason": str(error)[:300]}


def inspect(
    pair: dict, audit: dict, receivers: list[dict], config_a: Path, config_b: Path,
    start: dict, destination: dict, direction: str, mode: str, max_probes: int,
    route_fn: Callable = route, trace_fn: Callable = trace_directed_ids,
    focused_identity: tuple[int, int] | None = None,
) -> dict:
    valid_pair_audit(pair, audit)
    if direction not in DIRECTIONS or mode not in MODES or not 1 <= max_probes <= MAX_PROBES:
        raise ValueError("Unsupported direction, vehicle, or diagnostic probe budget")
    start = strict_point(start, "origin")
    destination = strict_point(destination, "destination")
    pool = candidate_pool(audit, direction, receivers)
    # Distance ranks only the *bounded probe order*. All unprobed hypotheses
    # remain represented as unresolved, never treated as failed or absent.
    ordered = sorted(pool, key=lambda row: (
        distance(start, row["handoff"]) + distance(row["handoff"], destination),
        row["sourceDirectedGraphId"], row["receiverIncomingGraphId"]))
    if focused_identity is not None:
        if (len(focused_identity) != 2 or any(
                type(member) is not int or member <= 0 for member in focused_identity)):
            raise ValueError("Invalid explicit source/receiver directed identity")
        ordered = [
            row for row in ordered if (
                row["sourceDirectedGraphId"], row["receiverIncomingGraphId"]
            ) == focused_identity
        ]
        if len(ordered) != 1:
            raise ValueError("Explicit directed handoff is absent from provisional catalog")
    chosen = ordered[:max_probes]
    results = [
        check_terminal(candidate, config_a, config_b, start, destination, mode,
                       route_fn, trace_fn)
        for candidate in chosen
    ]
    passed = [r for r in results
              if r["status"] == "GRAPH_LOCAL_TRACES_MATCHED_FOR_THIS_JOURNEY"]
    return {
        "schema": "roadpilot.native-f8-terminal-route-probe", "version": 0,
        "pairId": pair["pairId"],
        "graphFingerprints": {"from": pair["fromGraphFingerprint"],
                              "to": pair["toGraphFingerprint"]},
        "direction": direction, "mode": mode, "origin": start, "destination": destination,
        "terminalHypothesesInProvisionalCatalog": len(pool),
        "selection": "EXPLICIT_DIRECTED_PAIR" if focused_identity else "JOURNEY_DISTANCE_RANKED",
        "probed": len(results), "unprobed": len(pool) - len(results),
        "matchedGraphLocalTracesForThisJourneyOnly": len(passed),
        "rankingScope": "MATCHED_GRAPH_LOCAL_TRACES_ONLY_NOT_A_PROVEN_CROSS_GRAPH_ROUTE",
        "results": results,
        "bestOfProbedOnly": {
            style: (
                (
                    lambda winner: {
                        "sourceDirectedGraphId": winner["sourceDirectedGraphId"],
                        "receiverIncomingGraphId": winner["receiverIncomingGraphId"],
                    }
                )(min(passed, key=lambda r: (
                    r["durationSeconds"] if style == "FASTER" else r["distanceKm"],
                    r["sourceDirectedGraphId"], r["receiverIncomingGraphId"]
                ))) if passed else None)
            for style in ("FASTER", "SHORTER")
        },
        "crossGraphPhysicalContinuity": "NOT_VERIFIED",
        "handoffTurnLegality": "NOT_VERIFIED",
        "coverage": "NOT_VERIFIED", "androidF8Parity": "NOT_VERIFIED",
        "routeOptimality": "NOT_VERIFIED",
        "productionPublication": "BLOCKED",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("pair", "receiver-audit", "from-manifest", "to-manifest",
                 "from-native-adjacency", "to-native-adjacency"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--direction", choices=sorted(DIRECTIONS), required=True)
    parser.add_argument("--mode", choices=sorted(MODES), required=True)
    for name in ("start-lat", "start-lng", "end-lat", "end-lng"):
        parser.add_argument("--" + name, type=float, required=True)
    parser.add_argument("--max-probes", type=int, default=6)
    parser.add_argument("--focus-source-graph-id", type=int)
    parser.add_argument("--focus-receiver-graph-id", type=int)
    args = parser.parse_args()
    if (args.focus_source_graph_id is None) != (args.focus_receiver_graph_id is None):
        raise ValueError("Explicit focus requires BOTH graph-local directed IDs")
    focused = (
        (args.focus_source_graph_id, args.focus_receiver_graph_id)
        if args.focus_source_graph_id is not None else None
    )

    pair = json.loads(args.pair.read_text(encoding="utf-8"))
    audit = json.loads(args.receiver_audit.read_text(encoding="utf-8"))
    valid_pair_audit(pair, audit)
    with tempfile.TemporaryDirectory(prefix="graph-studio-terminal-proof-") as tmp:
        from_manifest = json.loads(args.from_manifest.read_text(encoding="utf-8"))
        to_manifest = json.loads(args.to_manifest.read_text(encoding="utf-8"))
        identity_a, cfg_a = graph_manifest_info(
            args.from_manifest, pair["fromRegionId"],
            to_manifest["source"]["primaryGeofabrikId"],
            pair["fromBoundaryFingerprint"], Path(tmp), "A")
        identity_b, cfg_b = graph_manifest_info(
            args.to_manifest, pair["toRegionId"],
            from_manifest["source"]["primaryGeofabrikId"],
            pair["toBoundaryFingerprint"], Path(tmp), "B")
        verify_retained_graph_identity(pair, identity_a, identity_b)
        if args.direction == "to-from":
            cfg_a, cfg_b = cfg_b, cfg_a
        receivers = load_jsonl(
            args.to_native_adjacency if args.direction == "from-to"
            else args.from_native_adjacency)
        result = inspect(
            pair, audit, receivers, cfg_a, cfg_b,
            {"lat": args.start_lat, "lng": args.start_lng},
            {"lat": args.end_lat, "lng": args.end_lng},
            args.direction, args.mode, args.max_probes,
            focused_identity=focused)
    print(json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(f"NATIVE_F8_TERMINAL_PROBE_ERROR: {error}", file=sys.stderr)
        sys.exit(2)
