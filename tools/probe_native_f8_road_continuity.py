#!/usr/bin/env python3
"""M6c Phase B — read-only native directed A-tail/B-incoming/B-outgoing witness.

This observes the final directed edge of a *graph-local* road and the
receiving graph's native incoming→outgoing topology on exact immutable
regional graphs. No OSM sampler, sidecar, matrix, publication, Android
change or cross-graph GraphId match. A matched B-only trace_attributes
edge_walk replay does NOT prove original route-service edge identity.
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
from probe_native_f8_actual_journey import verify_native_extractor
from probe_native_f8_clipped_terminal import (
    SourceIntegrityError, check_source_terminal, inspect_receivers,
    locate_receiver_edges, verified_buffer,
)
from probe_native_f8_directed_chain import (
    source_tail_on_b_chain,
    trace_selected_b_chain,
)
from probe_native_f8_directed_turn import (
    direction_observation, native_adjacency, validate_adjacency,
)
from probe_native_f8_journey import (
    distance, route, verify_retained_graph_identity,
)
from probe_native_f8_terminal_geometry import (
    MODES, checked_edge, native_rows,
)
from probe_native_f8_terminal_handoffs import trace_directed_ids

MAX_SELECTED_SOURCE = 8
MAX_B_LOCATE = 64
MAX_TURN_PROBES_PER_SOURCE = 16
MAX_B_NATIVE_BRANCHES = 256
GEOMETRY_TERMINAL_OBSERVATION_METRES = 2.0
DIRECTIONS = ("from-to", "to-from")


def locate_set(
    endpoint: dict, locators: list[dict], b_edges: list[dict], mode: str,
) -> list[dict]:
    """Validate every B locate ID before drawing any identity conclusion."""
    if not isinstance(locators, list) or len(locators) > MAX_B_LOCATE:
        raise SourceIntegrityError("Unsupported/truncated B locate collection")
    if not isinstance(b_edges, list) or len(locators) != len(b_edges):
        raise SourceIntegrityError("B located IDs and native geometry count mismatch")
    identities = [row.get("receiverGraphId") if isinstance(row, dict) else None
                  for row in locators]
    if (any(type(x) is not int or x <= 0 for x in identities)
            or len(set(identities)) != len(identities)):
        raise SourceIntegrityError("Duplicate/malformed B locate directed identity")
    try:
        return inspect_receivers(endpoint, locators, b_edges, mode)
    except (ValueError, TypeError, KeyError, IndexError) as error:
        raise SourceIntegrityError(
            "B locate/native geometry identities or coordinates invalid"
        ) from error


def inspect_source_and_b_continuations(
    source: dict, source_terminal: dict,
    b_locators: list[dict], b_rows: list[dict], mode: str,
    cfg_b: Path,
    native_adj_fn: Callable[[int], dict],
    native_rows_fn: Callable[[list[int]], list[dict]],
    *, max_route_probes: int = MAX_TURN_PROBES_PER_SOURCE,
    route_fn: Callable = route,
    trace_fn: Callable = trace_directed_ids,
) -> dict:
    """Preserve every B native edge and all branches; probe selected B turns.

    Nomination uses only observed native segment overlap and adjacency,
    NOT a new road eligibility rule. Non-nominated candidates are retained
    with explicit "not probed" and cannot become negative route evidence.
    """
    if mode not in MODES or type(max_route_probes) is not int or not (
            0 <= max_route_probes <= MAX_TURN_PROBES_PER_SOURCE):
        raise ValueError("Invalid explicit diagnostic mode/budget")
    a = checked_edge(source)
    if source_terminal.get("sourceGraphId") != a["sourceGraphId"]:
        raise SourceIntegrityError("Graph A terminal/native geometry mismatch")
    original = locate_set(
        source_terminal["sourceDirectedEndpoint"], b_locators, b_rows, mode)
    examined = []
    route_count = 0
    matching_b_incoming = 0
    total_native_outgoing = 0
    for locator, row, b_local in zip(b_locators, b_rows, original):
        b = checked_edge(row)
        directed = direction_observation(source, row)
        if directed.get("discoveryEligibilityFiltered") is not False:
            raise SourceIntegrityError("Unexpected B direction filtering")
        point_b_end = b["directedGeometry"][-1]
        a_end = source_terminal["sourceDirectedEndpoint"]
        ending_gap = distance(a_end, point_b_end)
        terminal_overlap = (
            directed["state"] == "SAMPLED_DIRECTED_ORDER_ALIGNED_ONLY"
            # Graph B may segment one physical road differently from A.
            # A B-incoming ending at the same node can share only PART
            # of A's last 20 m. Do not require whole-tail co-location.
            # Missing samples remain explicit, never a global rejection.
            and directed["matchedTailSamples"] >= 2
            and ending_gap <= GEOMETRY_TERMINAL_OBSERVATION_METRES
            and b_local["modeForwardAccess"]
        )
        record = {
            **b_local,
            "nativeGeometryOfLocatedEdge": "VERIFIED_IDENTITY",
            "bIncomingTailObservation": directed,
            "nativeSourceWayIdEqualsBIncomingWayIdAnnotation": (
                a["wayId"] == b["wayId"]),
            "aTerminalToBIncomingEndMeters": round(ending_gap, 3),
            "selectedBIncomingForNativeTurnDiagnostic": terminal_overlap,
            "selectedBy": "SAMPLED_B_INCOMING_END_AND_PARTIAL_OR_FULL_DIRECTED_OVERLAP_ONLY",
            "sourceTailFullyCoveredByThisBIncoming": (
                directed["matchedTailSamples"] == directed["totalTailSamples"]),
            "discoveryEligibility": "NOT_A_FILTER_ALL_B_LOCATE_IDS_RETAINED",
            "originalRouteEdgeIdentity": "NOT_VERIFIED",
            "physicalRoadLineage": "NOT_VERIFIED",
            "crossGraphTurnLegality": "NOT_VERIFIED",
        }
        if not terminal_overlap:
            record["incomingToOutgoingEvidence"] = {
                "status": "NOT_PROBED_UNSELECTED_B_INCOMING_GEOMETRY",
                "crossGraphTurnLegality": "NOT_VERIFIED",
            }
            examined.append(record)
            continue
        matching_b_incoming += 1
        adjacency = native_adj_fn(b["sourceGraphId"])
        if not isinstance(adjacency, dict):
            raise SourceIntegrityError("Missing native B incoming adjacency")
        edges = adjacency.get("outgoingDirectedEdges")
        if (not isinstance(edges, list) or not 1 <= len(edges) <= MAX_B_NATIVE_BRANCHES
                or type(adjacency.get("nativeOutgoingDegree")) is not int
                or len(edges) != adjacency["nativeOutgoingDegree"]):
            raise SourceIntegrityError("Incomplete B incoming native outgoing degree")
        branch_ids = [entry.get("graphId") if isinstance(entry, dict) else None
                      for entry in edges]
        if any(type(x) is not int or x <= 0 for x in branch_ids):
            raise SourceIntegrityError("Malformed B incoming outgoing GraphId")
        outgoing = native_rows_fn(branch_ids)
        # Full-degree/access/GraphId checks before scoring a single outgoing.
        try:
            validated = validate_adjacency(row, adjacency, outgoing)
        except ValueError as error:
            raise SourceIntegrityError(
                "B node inventory identity/degree/access does not match extractor"
            ) from error
        if len(validated) != len(outgoing):
            raise SourceIntegrityError("Incomplete B outgoing branch preservation")
        total_native_outgoing += len(validated)
        candidates = []
        for descriptor, next_raw in zip(validated, outgoing):
            nxt = checked_edge(next_raw)
            opposing = descriptor["graphId"] == adjacency["opposingGraphId"]
            # Compare A final-edge tail with this actual connected B
            # incoming→outgoing chain, not a nominated OSM portal or
            # cross-graph GraphId correspondence.
            continuous_geometry = source_tail_on_b_chain(
                source, [row, next_raw])
            branch = {
                "bIncomingGraphId": b["sourceGraphId"],
                "bOutgoingGraphId": nxt["sourceGraphId"],
                "bIncomingEndNodeGraphId": b["endNodeGraphId"],
                "bNativeOpposingReverse": opposing,
                "isRoad": descriptor["isRoad"],
                "isShortcut": descriptor["isShortcut"],
                "modeForwardAccess": bool(nxt["forwardAccess"] & MODES[mode]),
                "bNativeWayIdAnnotation": nxt["wayId"],
                "nativeBOutgoingStartGapFromAEndMeters": round(
                    distance(a_end, nxt["directedGeometry"][0]), 3),
                "sampledA20mToBConnectedChain": continuous_geometry,
                "originalRouteEdgeIdentity": "NOT_VERIFIED",
                "crossGraphLegalTransfer": "NOT_VERIFIED",
            }
            # Probing bounded and explicit; all unprobed branches remain
            # present in this diagnostic as unknown, not eliminated.
            if route_count >= max_route_probes:
                branch["bOnlyRouteReplay"] = {"status": "NOT_PROBED_BUDGET"}
            else:
                route_count += 1
                # Exact Graph B-native adjacency already verified above.
                # A → B physical road lineage still cannot follow from
                # the route shape being independently re-matched by edge_walk.
                try:
                    evidence = trace_selected_b_chain(
                        cfg_b, [row, next_raw], mode, route_fn, trace_fn)
                except (OSError, ValueError, TypeError, KeyError,
                        subprocess.TimeoutExpired) as error:
                    evidence = {"status": "INCONCLUSIVE_B_ONLY_ROUTE_PROBE",
                                "reason": str(error)[:220]}
                status = evidence["status"]
                if status == "B_GRAPH_DIRECTED_CHAIN_TRACED_FOR_THIS_LOCAL_ROUTE":
                    status = "B_ONLY_ROUTE_EDGE_WALK_REPLAY_MATCHED_SELECTED_TURN"
                # Previous diagnostic names misleadingly called the
                # independent trace_attributes edge_walk IDs "actual".
                # They are a replay of a route shape, not the route
                # service's authoritative directed-edge trace.
                for old, new in (
                    ("actualTracedGraphIds", "edgeWalkReplayDirectedGraphIds"),
                    ("graphBLocalTrace", "edgeWalkReplayMatch"),
                    ("matchedTraceIndex", "matchedReplayIndex"),
                    ("totalTracedEdgeCount", "edgeWalkReplayEdgeCount"),
                    ("traceTruncatedForReport", "edgeWalkReplayTruncated"),
                ):
                    if old in evidence:
                        evidence[new] = evidence.pop(old)
                branch["bOnlyRouteReplay"] = {
                    **evidence,
                    "status": status,
                    "routeEdgeIdsComeFrom": (
                        "SEPARATE_TRACE_ATTRIBUTES_EDGE_WALK_SHAPE_REPLAY"
                    ),
                    "originalRouteEdgeIdentity": "NOT_VERIFIED",
                    "ambiguousGeometryRouteFidelity": "NOT_VERIFIED",
                    "crossGraphLegalTransfer": "NOT_VERIFIED",
                }
            candidates.append(branch)
        record["incomingToOutgoingEvidence"] = {
            "status": "FULL_B_INCOMING_NODE_ADJACENCY_VERIFIED",
            "bIncomingEndNodeGraphId": adjacency["endNodeGraphId"],
            "nativeBOutgoingDegree": adjacency["nativeOutgoingDegree"],
            "allNativeOutgoingAlternatives": candidates,
            "bOutgoingRouteProbes": sum(
                x["bOnlyRouteReplay"]["status"] != "NOT_PROBED_BUDGET"
                for x in candidates),
            "bUnprobedOutgoingBranches": sum(
                x["bOnlyRouteReplay"]["status"] == "NOT_PROBED_BUDGET"
                for x in candidates),
            "graphBPhysicalNodeAdjacency": "CONFIRMED_FOR_THIS_NODE_ONLY",
            "crossGraphTurnLegality": "NOT_VERIFIED",
        }
        examined.append(record)
    return {
        "sourceGraphId": a["sourceGraphId"],
        "sourceGraphLocalTerminal": source_terminal,
        "locatedReceiverCount": len(b_locators),
        "retainedReceiverIdentities": [r["receiverGraphId"] for r in b_locators],
        "allBLocatedEdges": examined,
        "nominatedBIncomingCount": matching_b_incoming,
        "verifiedNativeBOutgoingBranchCount": total_native_outgoing,
        "bOnlyRouteProbeCount": route_count,
        "bLocateCompleteness": "NOT_VERIFIED_RADIUS_ONLY",
        "sourcePhysicalFinalRoadEdge": "NOT_VERIFIED",
        "sourceEdgeProvedLastInThisNativeGraphMode": bool(
            source_terminal["graphLocalModeTerminalConfirmed"]
        ),
        "originalValhallaRouteEdgeIdentity": "NOT_VERIFIED",
        "crossGraphDirectedTurnLegality": "NOT_VERIFIED",
        "sourceDiscoveryCoverage": "NOT_VERIFIED",
        "productionPublication": "BLOCKED",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("pair", "from-manifest", "to-manifest", "from-buffer",
                 "to-buffer", "native-endpoints-binary"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--direction", choices=DIRECTIONS, required=True)
    parser.add_argument("--mode", choices=sorted(MODES), required=True)
    parser.add_argument("--source-graph-id", action="append", type=int, required=True)
    parser.add_argument("--locate-radius", type=int, default=25)
    parser.add_argument("--max-route-probes-per-source", type=int, default=16)
    args = parser.parse_args()
    selected = args.source_graph_id
    if (not 1 <= len(selected) <= MAX_SELECTED_SOURCE
            or any(type(x) is not int or x <= 0 for x in selected)
            or len(selected) != len(set(selected))):
        raise ValueError("Invalid explicit source native GraphId selection")
    native = verify_native_extractor(args.native_endpoints_binary)
    pair = json.loads(args.pair.read_text(encoding="utf-8"))
    pair_identity(pair)
    ma = json.loads(args.from_manifest.read_text(encoding="utf-8"))
    mb = json.loads(args.to_manifest.read_text(encoding="utf-8"))
    buffers = (
        verified_buffer(args.from_buffer, ma),
        verified_buffer(args.to_buffer, mb),
    )
    with tempfile.TemporaryDirectory(prefix="roadpilot-f8-m6c-continuity-") as folder:
        tmp = Path(folder)
        ga, ca = graph_manifest_info(
            args.from_manifest, pair["fromRegionId"],
            mb["source"]["primaryGeofabrikId"],
            pair["fromBoundaryFingerprint"], tmp, "A")
        gb, cb = graph_manifest_info(
            args.to_manifest, pair["toRegionId"],
            ma["source"]["primaryGeofabrikId"],
            pair["toBoundaryFingerprint"], tmp, "B")
        verify_retained_graph_identity(pair, ga, gb)
        if args.direction == "to-from":
            ca, cb = cb, ca
            buffers = buffers[::-1]
        reports = []
        for source_id in selected:
            a = native_rows(args.native_endpoints_binary, ca, [source_id], tmp)[0]
            a_adj = native_adjacency(
                args.native_endpoints_binary, ca, source_id, tmp)
            terminal = check_source_terminal(
                a, a_adj, args.mode, *buffers)
            endpoint = terminal["sourceDirectedEndpoint"]
            # B locate is explicit bounded diagnostic, not the full native
            # directed edge inventory or a coverage certificate.
            b_located = locate_receiver_edges(
                cb, endpoint, args.mode, radius=args.locate_radius)
            ids = [item["receiverGraphId"] for item in b_located]
            b_shapes = (
                native_rows(args.native_endpoints_binary, cb, ids, tmp)
                if ids else [])
            def get_b_adj(id: int) -> dict:
                return native_adjacency(
                    args.native_endpoints_binary, cb, id, tmp)
            def get_b_rows(ids: list[int]) -> list[dict]:
                return native_rows(args.native_endpoints_binary, cb, ids, tmp)
            report = inspect_source_and_b_continuations(
                a, terminal, b_located, b_shapes, args.mode, cb,
                get_b_adj, get_b_rows,
                max_route_probes=args.max_route_probes_per_source)
            reports.append(report)
    print(json.dumps({
        "schema": "roadpilot.f8-native-m6c-selected-road-overlap-continuity",
        "version": 0, "pairId": pair["pairId"],
        "direction": args.direction, "mode": args.mode,
        "fromGraphFingerprint": pair["fromGraphFingerprint"],
        "toGraphFingerprint": pair["toGraphFingerprint"],
        "fromBoundaryFingerprint": pair["fromBoundaryFingerprint"],
        "toBoundaryFingerprint": pair["toBoundaryFingerprint"],
        "sourceBufferSha256": buffers[0]["sha256"],
        "receiverBufferSha256": buffers[1]["sha256"],
        **native,
        "selection": "EXPLICIT_SELECTED_A_NATIVE_TERMINALS_ONLY",
        "selectedSourceCount": len(reports),
        "sourceEvidence": reports,
        "discoveryCompleteness": "NOT_VERIFIED",
        "androidJNIParity": "NOT_VERIFIED",
        "physicalRoadFinalEdgeLineage": "NOT_VERIFIED",
        "routeEdgeIdentityFidelity": "NOT_VERIFIED",
        "crossGraphLegalTransfer": "NOT_VERIFIED",
        "fastestShortestOptimality": "NOT_VERIFIED",
        "productionPublication": "BLOCKED",
    }, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, TypeError,
            json.JSONDecodeError, subprocess.TimeoutExpired,
            subprocess.CalledProcessError) as error:
        print("NATIVE_F8_M6C_CONTINUITY_ERROR: " + str(error)[:360],
              file=sys.stderr)
        sys.exit(2)
