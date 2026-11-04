#!/usr/bin/env python3
"""Read-only M6b: F8's actual A-last/B-first directed legs for native GPS proposals.

Original GPS proposals are explicitly selected, never filtered or replaced.
The final directed edge of a *route leg* is NOT presumed the final retained
road edge in the 25-km overlap, nor does GPS handoff prove cross-graph legality.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
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
    ARRIVAL_TOLERANCE_METERS, distance, eligible_manifest, route,
    verify_retained_graph_identity,
)
from probe_native_f8_terminal_handoffs import strict_point, trace_directed_ids
from probe_native_f8_terminal_geometry import (
    GEOMETRY_OBSERVATION_METRES, MODES, checked_edge, native_rows, nearest,
)

MAX_EXPLICIT_PROPOSALS = 8
MAX_TRACE_EDGES = 100000
TRACE_SAMPLE_COUNT = 8
DIRECTIONS = ("from-to", "to-from")


def selected_catalog(file: Path, requested: list[str], direction: str,
                     expected_records: int) -> tuple[list[dict], int]:
    """Preserve full original, hash-bound stream; probe explicit IDs only."""
    if (direction not in DIRECTIONS or not isinstance(requested, list)
            or not 1 <= len(requested) <= MAX_EXPLICIT_PROPOSALS
            or any(not isinstance(x, str) or not x.startswith("nf8gps-")
                   or len(x) > 90 for x in requested)
            or len(requested) != len(set(requested))
            or type(expected_records) is not int or expected_records < 0):
        raise ValueError("Invalid explicit native GPS proposal selection")
    selected = {}
    identities = set()
    total = 0
    with gzip.open(file, "rt", encoding="utf-8") as stream:
        for line in stream:
            entry = json.loads(line)
            identity = entry.get("id")
            if (not isinstance(identity, str) or identity in identities
                    or entry.get("direction") != direction):
                raise ValueError("Native GPS stream has duplicate ID or wrong direction")
            identities.add(identity)
            total += 1
            if identity in requested:
                if type(entry.get("receiverGraphId")) is not int or entry["receiverGraphId"] <= 0:
                    raise ValueError("Selected native GPS receiver identity invalid")
                entry["coordinate"] = strict_point(
                    entry.get("coordinate"), "native GPS proposal")
                selected[identity] = entry
    if total != expected_records or len(selected) != len(requested):
        raise ValueError("Incomplete or stale native GPS candidate stream/selection")
    return [selected[x] for x in requested], total


def _valid_trace(trace: object) -> bool:
    return (isinstance(trace, list) and 1 <= len(trace) <= MAX_TRACE_EDGES
            and all(type(x) is int and x > 0 for x in trace))


def _trace_digest(trace: list[int]) -> str:
    return "sha256:" + hashlib.sha256(
        ",".join(str(n) for n in trace).encode("ascii")).hexdigest()


def trace_actual_legs(candidate: dict, config_a: Path, config_b: Path,
                      origin: dict, destination: dict, mode: str,
                      route_fn: Callable = route,
                      trace_fn: Callable = trace_directed_ids) -> dict:
    """Trace actual leg edges, F8 normalization and exact destination.

    An outcome is only a property of this explicit candidate/route/mode, not
    negative evidence about other crossing positions or roads.
    """
    if mode not in MODES:
        raise ValueError("Unsupported mode")
    origin = strict_point(origin, "origin")
    destination = strict_point(destination, "destination")
    point = strict_point(candidate["coordinate"], "candidate GPS")
    expected_b = candidate.get("receiverGraphId")
    if type(expected_b) is not int or expected_b <= 0:
        raise ValueError("Invalid selected receiver directed identity")
    base = {
        "candidateId": candidate["id"], "proposedReceiverGraphId": expected_b,
        "gpsProposal": point, "mode": mode,
        "aLastEdgeMeaning": "ACTUAL_LAST_DIRECTED_EDGE_OF_THIS_A_ROUTE_ONLY",
        "crossGraphPhysicalContinuity": "NOT_VERIFIED",
        "crossSeamTurnLegality": "NOT_VERIFIED",
    }
    try:
        first = route_fn(config_a, origin, point, mode)
        if first.get("status") != "SUCCEEDED":
            return {**base, "status": "INCONCLUSIVE",
                    "reason": "A origin-to-GPS route did not succeed",
                    "firstLegStatus": first.get("status")}
        a_trace = trace_fn(config_a, first["encodedShape"], mode)
        if not _valid_trace(a_trace):
            return {**base, "status": "INCONCLUSIVE",
                    "reason": "Missing/invalid actual A directed edge trace"}
        normalized = strict_point(first["endActual"], "actual A leg arrival")
        second = route_fn(config_b, normalized, destination, mode)
        if second.get("status") != "SUCCEEDED":
            return {**base, "status": "INCONCLUSIVE",
                    "reason": "B normalized-start-to-destination route did not succeed",
                    "actualALastDirectedGraphId": a_trace[-1]}
        b_trace = trace_fn(config_b, second["encodedShape"], mode)
        if not _valid_trace(b_trace):
            return {**base, "status": "INCONCLUSIVE",
                    "reason": "Missing/invalid actual B directed edge trace",
                    "actualALastDirectedGraphId": a_trace[-1]}
        offsets = {}
        for side, leg in (("A", first), ("B", second)):
            for name in ("startOffsetMeters", "endOffsetMeters"):
                v = leg.get(name)
                if type(v) not in (int, float) or not math.isfinite(v) or v < 0:
                    return {**base, "status": "INCONCLUSIVE",
                            "reason": "Malformed Valhalla snap evidence"}
                offsets[side + name] = v
        a_start = strict_point(first["startActual"], "A actual origin")
        b_start = strict_point(second["startActual"], "B actual handoff")
        b_final = strict_point(second["endActual"], "B actual destination")
        handoff_gap = distance(normalized, b_start)
        destination_gap = distance(destination, b_final)
        gps_to_a = distance(point, normalized)
        costs = {}
        for name in ("durationSeconds", "distanceKm"):
            values = [first.get(name), second.get(name)]
            if any(type(v) not in (int, float) or not math.isfinite(v) or v < 0
                   for v in values):
                return {**base, "status": "INCONCLUSIVE",
                        "reason": "Malformed Valhalla route metrics"}
            costs[name] = sum(values)
        arrived = (
            all(x <= ARRIVAL_TOLERANCE_METERS for x in offsets.values())
            and distance(origin, a_start) <= ARRIVAL_TOLERANCE_METERS
            and destination_gap <= ARRIVAL_TOLERANCE_METERS
            and gps_to_a <= ARRIVAL_TOLERANCE_METERS
            and handoff_gap <= ARRIVAL_TOLERANCE_METERS
        )
        matches = b_trace[0] == expected_b
        return {
            **base,
            "status": ("BOTH_ACTUAL_GRAPH_LOCAL_LEGS_TRACED_FOR_THIS_JOURNEY"
                       if arrived and matches else "UNPROVEN_FOR_THIS_JOURNEY"),
            "endpointArrivalAndHandoffWithinF8Tolerance": arrived,
            "proposedReceiverMatchesActualFirstEdge": matches,
            "actualALastDirectedGraphId": a_trace[-1],
            "actualBFirstDirectedGraphId": b_trace[0],
            "aTraceEdgeCount": len(a_trace), "bTraceEdgeCount": len(b_trace),
            "aTraceLastIds": a_trace[-TRACE_SAMPLE_COUNT:],
            "bTraceFirstIds": b_trace[:TRACE_SAMPLE_COUNT],
            "aTraceSha256": _trace_digest(a_trace),
            "bTraceSha256": _trace_digest(b_trace),
            "actualALegStart": a_start, "actualAHandoff": normalized,
            "actualBHandoff": b_start, "actualDestination": b_final,
            "handoffGapMeters": round(handoff_gap, 3),
            "originalGpsToActualHandoffMeters": round(gps_to_a, 3),
            "destinationArrivalErrorMeters": round(destination_gap, 3),
            "aDurationSeconds": first["durationSeconds"],
            "bDurationSeconds": second["durationSeconds"],
            "aDistanceKm": first["distanceKm"],
            "bDistanceKm": second["distanceKm"],
            "totalDurationSeconds": costs["durationSeconds"],
            "totalDistanceKm": costs["distanceKm"],
            "reason": None if arrived and matches else
                      ("F8 endpoint/handoff tolerance failed or selected "
                       "B incoming edge differs from actual first edge"),
        }
    except (OSError, ValueError, KeyError, TypeError, IndexError, AttributeError,
            subprocess.TimeoutExpired) as exc:
        return {**base, "status": "INCONCLUSIVE",
                "reason": str(exc)[:250]}


def observe_actual_handoff_geometry(
    observation: dict, source_edge: dict, receiver_edge: dict, mode: str,
) -> dict:
    """Native A/B edge geometry is observational, not a legal seam edge."""
    if mode not in MODES:
        raise ValueError("Unsupported mode")
    a, b = checked_edge(source_edge), checked_edge(receiver_edge)
    a_id = observation["actualALastDirectedGraphId"]
    b_id = observation["actualBFirstDirectedGraphId"]
    if a["sourceGraphId"] != a_id or b["sourceGraphId"] != b_id:
        raise ValueError("Native geometry is not bound to actual A-last/B-first trace")
    a_hand = strict_point(observation["actualAHandoff"], "A actual handoff")
    b_hand = strict_point(observation["actualBHandoff"], "B actual handoff")
    a_pos = nearest(a_hand, a["directedGeometry"])
    b_pos = nearest(b_hand, b["directedGeometry"])
    gap = distance(a_hand, b_hand)
    tangent_cos = sum(x * y for x, y in zip(
        a_pos["tangent"], b_pos["tangent"]))
    a_length = sum(distance(x, y) for x, y in zip(
        a["directedGeometry"], a["directedGeometry"][1:]))
    a_remaining = max(0.0, a_length - a_pos["distanceAlongDirectedEdgeMeters"])
    co_located = (
        a_pos["metres"] <= GEOMETRY_OBSERVATION_METRES
        and b_pos["metres"] <= GEOMETRY_OBSERVATION_METRES
        and gap <= GEOMETRY_OBSERVATION_METRES
    )
    return {
        "sourceActualDirectedGraphId": a_id,
        "receiverActualDirectedGraphId": b_id,
        "sourceWayIdAnnotation": a["wayId"],
        "receiverWayIdAnnotation": b["wayId"],
        "sourceForwardModeAccess": bool(a["forwardAccess"] & MODES[mode]),
        "receiverForwardModeAccess": bool(b["forwardAccess"] & MODES[mode]),
        "aNativeLastEdgeDeadendFlag": a.get("deadend")
        if type(a.get("deadend")) is bool else None,
        "aNativeLastEdgeNotThruFlag": a.get("notThru")
        if type(a.get("notThru")) is bool else None,
        "aRemainingDistanceToDirectedEdgeEndMeters": round(a_remaining, 3),
        "aHandoffIsAtEndOfActualLastEdgeWithinOneMetre": (
            a_remaining <= GEOMETRY_OBSERVATION_METRES
            and a_pos["metres"] <= GEOMETRY_OBSERVATION_METRES),
        "sourceRoadFinalEdgeIdentity": "NOT_VERIFIED_BY_SELECTED_LEG",
        "aActualHandoffOnALastDirectedEdgeMeters": round(a_pos["metres"], 3),
        "bActualStartOnBFirstDirectedEdgeMeters": round(b_pos["metres"], 3),
        "actualABEndpointGapMeters": round(gap, 3),
        "aHandoffDistanceAlongALastDirectedEdgeMeters": round(
            a_pos["distanceAlongDirectedEdgeMeters"], 3),
        "bStartDistanceAlongBFirstDirectedEdgeMeters": round(
            b_pos["distanceAlongDirectedEdgeMeters"], 3),
        "aVsBLocalDirectedTangentCosine": round(tangent_cos, 5),
        "graphLocalGeometryObservation": (
            "BOTH_TRACED_EDGES_COLOCATED_AT_SELECTED_HANDOFF_ONLY"
            if co_located
            else "NOT_COLOCATED_WITHIN_ONE_METRE_FOR_SELECTED_HANDOFF"),
        "physicalCrossGraphContinuity": "NOT_VERIFIED",
        "crossSeamDirectedLegality": "NOT_VERIFIED",
    }


def evaluate_candidate(
    candidate: dict, config_a: Path, config_b: Path,
    origin: dict, destination: dict, mode: str,
    native_geometry_fn: Callable[[int, int], tuple[dict, dict]],
    route_fn: Callable = route,
    trace_fn: Callable = trace_directed_ids,
) -> dict:
    journey = trace_actual_legs(candidate, config_a, config_b,
                                origin, destination, mode, route_fn, trace_fn)
    if not all(k in journey for k in (
            "actualALastDirectedGraphId", "actualBFirstDirectedGraphId")):
        return {**journey, "nativeGeometry": "NOT_RUN_NO_COMPLETE_TWO_LEG_TRACE"}
    a_edge, b_edge = native_geometry_fn(
        journey["actualALastDirectedGraphId"],
        journey["actualBFirstDirectedGraphId"])
    geom = observe_actual_handoff_geometry(journey, a_edge, b_edge, mode)
    result = {**journey, "actualEdgeGeometry": geom,
              "crossGraphPhysicalContinuity": "NOT_VERIFIED",
              "crossSeamTurnLegality": "NOT_VERIFIED"}
    if not geom["sourceForwardModeAccess"] or not geom["receiverForwardModeAccess"]:
        result["status"] = "UNPROVEN_FOR_THIS_JOURNEY"
        result["reason"] = ("Actual traced graph-local directed edge lacks "
                            "requested native forward mode access")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("pair", "proposal-dir", "from-manifest", "to-manifest",
                "native-endpoints-binary"):
        parser.add_argument("--" + key, required=True, type=Path)
    parser.add_argument("--direction", choices=DIRECTIONS, required=True)
    parser.add_argument("--mode", choices=sorted(MODES), required=True)
    parser.add_argument("--candidate-id", action="append", required=True)
    for key in ("start-lat", "start-lng", "end-lat", "end-lng"):
        parser.add_argument("--" + key, type=float, required=True)
    args = parser.parse_args()
    origin = strict_point({"lat": args.start_lat, "lng": args.start_lng},
                          "requested origin")
    destination = strict_point({"lat": args.end_lat, "lng": args.end_lng},
                               "requested destination")
    version = subprocess.run(
        [str(args.native_endpoints_binary), "--version"], capture_output=True,
        text=True, timeout=15, check=True)
    if version.stdout.strip() != "3.6.3":
        raise ValueError("Pinned Valhalla 3.6.3 GraphReader required")
    pair = json.loads(args.pair.read_text(encoding="utf-8"))
    pair_identity(pair)
    manifest = json.loads(
        (args.proposal_dir / "manifest.json").read_text(encoding="utf-8"))
    stream = eligible_manifest(pair, manifest, args.direction, args.proposal_dir)
    expected = manifest["files"][args.direction + ".jsonl.gz"]["records"]
    selected, total = selected_catalog(stream, args.candidate_id,
                                       args.direction, expected)
    with tempfile.TemporaryDirectory(prefix="roadpilot-m6b-journal-") as folder:
        temp = Path(folder)
        a_manifest = json.loads(args.from_manifest.read_text(encoding="utf-8"))
        b_manifest = json.loads(args.to_manifest.read_text(encoding="utf-8"))
        graph_a, cfg_a = graph_manifest_info(
            args.from_manifest, pair["fromRegionId"],
            b_manifest["source"]["primaryGeofabrikId"],
            pair["fromBoundaryFingerprint"], temp, "A")
        graph_b, cfg_b = graph_manifest_info(
            args.to_manifest, pair["toRegionId"],
            a_manifest["source"]["primaryGeofabrikId"],
            pair["toBoundaryFingerprint"], temp, "B")
        verify_retained_graph_identity(pair, graph_a, graph_b)
        if args.direction == "to-from":
            cfg_a, cfg_b = cfg_b, cfg_a

        def capture_actual_native_edges(a_id: int, b_id: int) -> tuple[dict, dict]:
            a = native_rows(args.native_endpoints_binary, cfg_a, [a_id], temp)[0]
            b = native_rows(args.native_endpoints_binary, cfg_b, [b_id], temp)[0]
            return a, b

        reports = [evaluate_candidate(
            cand, cfg_a, cfg_b, origin, destination, args.mode,
            capture_actual_native_edges) for cand in selected]

    result = {
        "schema": "roadpilot.native-f8-m6b-actual-two-graph-leg-witness",
        "version": 0, "pairId": pair["pairId"],
        "direction": args.direction, "mode": args.mode,
        "origin": origin, "destination": destination,
        "fromGraphFingerprint": pair["fromGraphFingerprint"],
        "toGraphFingerprint": pair["toGraphFingerprint"],
        "fromBoundaryFingerprint": pair["fromBoundaryFingerprint"],
        "toBoundaryFingerprint": pair["toBoundaryFingerprint"],
        "selection": "EXPLICIT_ORIGINAL_NATIVE_F8_GPS_PROPOSAL_IDS",
        "selectedProbeCount": len(reports),
        "totalOriginalNativeGpsProposals": total,
        "remainingUnprobedProposals": total - len(reports),
        "sourceAIdentity": "ACTUAL_LAST_EDGE_OF_REQUESTED_GRAPH_A_LEG_ONLY",
        "results": reports,
        "graphLocalEvidenceOnly": True,
        "crossGraphPhysicalContinuity": "NOT_VERIFIED",
        "crossSeamTurnLegality": "NOT_VERIFIED",
        "androidF8Parity": "NOT_VERIFIED",
        "sourceDiscoveryCoverage": "NOT_VERIFIED",
        "wholeJourneyOptimality": "NOT_VERIFIED",
        "productionPublication": "BLOCKED",
    }
    print(json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, TypeError, AttributeError,
            subprocess.TimeoutExpired, subprocess.CalledProcessError) as exc:
        print("NATIVE_F8_M6B_ACTUAL_JOURNEY_ERROR: " + str(exc)[:350],
              file=sys.stderr)
        sys.exit(2)
