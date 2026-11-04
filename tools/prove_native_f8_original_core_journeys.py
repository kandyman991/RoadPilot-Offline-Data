#!/usr/bin/env python3
"""Bounded, nonpublishing native F8 core-to-core original-route/branch evidence.

On unchanged region-local Valhalla graphs:
  source core -> true A final directed GraphId -> original A-end X
  X -> receiving core, with original receiving first directed GraphId.
Every original TripLeg edge is reconciled to actual GraphReader outgoing arcs,
including hierarchy-level transitions, shortcuts, ramps and reverse arcs.
A two-leg route and aligned geometry are NOT proof of a legal cross-graph turn,
complete physical road classes, Android parity, or an optimal FASTER/SHORTER path.
"""
from __future__ import annotations

import argparse
from collections import Counter, deque
import hashlib
import json
import math
from pathlib import Path
import subprocess
import tempfile

from shapely.geometry import Point

from build_native_f8_pair_evidence import pair_identity
from capture_native_f8_graph_windows import read
from census_native_f8_final_directed_edges import verify_binary
from compile_native_f8_terminal_lineage_proof import (
    digest, expect_digest, read_core, atomic_write,
)
from native_f8_inputs import graph_manifest_info, safe_child
from native_f8_original_route import (
    route_with_original_ids, verify_native_route_binary,
)
from probe_native_f8_clipped_terminal import _at, verified_buffer
from probe_native_f8_journey import distance, verify_retained_graph_identity
from probe_native_f8_terminal_geometry import (
    MODES, inspect_geometry, native_rows,
)

SCHEMA = "roadpilot.f8-original-core-directed-branch-journey"
CASES_SCHEMA = "roadpilot.f8-explicit-original-core-journey-cases"
MAX_CASES = 32
MAX_ROUTE_IDS = 6000
MAX_NATIVE_HIERARCHY = 32
MAX_ACCEPTED_START_SNAP_METRES = 25.0
MAX_EXACT_END_SNAP_METRES = 1.0
MAX_B_START_GAP_METRES = 1.0
MAX_DESTINATION_ARRIVAL_METRES = 25.0
MIN_DIRECTION_COSINE = 0.85


def valid_point(p: dict) -> dict:
    if (not isinstance(p, dict) or set(p) != {"lat", "lng"}
            or any(type(p.get(k)) not in (int, float)
                   or not math.isfinite(p[k]) for k in ("lat", "lng"))
            or not -90 <= p["lat"] <= 90 or not -180 <= p["lng"] <= 180):
        raise ValueError("Invalid explicit source/destination coordinates")
    return {"lat": float(p["lat"]), "lng": float(p["lng"])}


def parse_cases(doc: dict) -> list[dict]:
    if (not isinstance(doc, dict) or doc.get("schema") != CASES_SCHEMA
            or doc.get("version") != 1 or
            not isinstance(doc.get("cases"), list)
            or not 1 <= len(doc["cases"]) <= MAX_CASES):
        raise ValueError("Invalid, empty, or unbounded explicit route case manifest")
    checked, known = [], set()
    for case in doc["cases"]:
        if not isinstance(case, dict) or set(case) != {
                "direction", "mode", "sourceFinalDirectedGraphId",
                "originSourceCore", "destinationReceiverCore"}:
            raise ValueError("Invalid or ambiguous explicit journey case")
        dr, mode, source = (case["direction"], case["mode"],
                            case["sourceFinalDirectedGraphId"])
        if dr not in ("from-to", "to-from") or mode not in MODES:
            raise ValueError("Unsupported F8 graph direction or costing mode")
        if type(source) is not int or source <= 0:
            raise ValueError("Original source GraphId must be positive integer")
        start = valid_point(case["originSourceCore"])
        end = valid_point(case["destinationReceiverCore"])
        identity = (dr, mode, source, start["lat"], start["lng"],
                    end["lat"], end["lng"])
        if identity in known:
            raise ValueError("Duplicate explicit route proof case")
        known.add(identity)
        checked.append({**case, "originSourceCore": start,
                        "destinationReceiverCore": end})
    return checked


def route_terminal(ledger: dict, direction: str, mode: str,
                   graph_id: int) -> dict:
    if (ledger.get("schema") != "roadpilot.f8-original-terminal-lineage-ledger"
            or ledger.get("version") != 1
            or ledger.get("productionPublication") != "BLOCKED"
            or ledger.get("oneFinalEdgePerPhysicalRoadAndDirection") != "NOT_VERIFIED"):
        raise ValueError("Source proof page is not the original incomplete native ledger")
    mode_doc = ledger["directions"][direction][mode]
    if mode_doc.get("sourceCoverage") != "ALL_NATIVE_CENSUS_TERMINALS_RETAINED":
        raise ValueError("Original source GraphReader census incomplete")
    matches = [row for row in mode_doc["allTerminals"]
               if row.get("sourceGraphId") == graph_id]
    if len(matches) != 1:
        raise ValueError("Source directed edge absent or duplicated in full census")
    row = matches[0]
    if (row.get("candidateSuppressed") is not False
            or row.get("nativeGraphLocalTerminal") != "PROVEN_BY_FULL_TOPOLOGY_CENSUS"
            or row.get("physicalRoadLineage") !=
            "PHYSICAL_ROAD_DIRECTION_LINEAGE_NOT_ESTABLISHED"
            or type(row.get("insideVerifiedPeerBuffer")) is not bool):
        raise ValueError("Unbound, incomplete or suppressed source native terminal")
    return row


def capture_native_lineage(binary: Path, config: Path, ordered: list[int],
                           temporary: Path) -> tuple[list[dict], str]:
    if (not isinstance(ordered, list) or
            not 1 <= len(ordered) <= MAX_ROUTE_IDS
            or any(type(i) is not int or i <= 0 for i in ordered)):
        raise ValueError("Original native route edge count invalid/oversized")
    unique = list(dict.fromkeys(ordered))
    fd = temporary / "original-route-directed-ids.txt"
    fd.write_text("".join(str(gid) + "\n" for gid in unique), encoding="ascii")
    command = [str(binary), str(config), str(fd), "--lineage"]
    proc = subprocess.run(command, capture_output=True, text=True,
                          timeout=120, check=False)
    if proc.returncode:
        raise ValueError("Pinned native GraphReader branch/transition audit failed; "
                         "discard all partial stdout: " + proc.stderr[-250:])
    lines = proc.stdout.splitlines()
    if len(lines) != len(unique):
        raise ValueError("Native hierarchy stream truncated/contains extra rows")
    rows = [json.loads(line) for line in lines]
    if [item.get("sourceGraphId") for item in rows] != unique:
        raise ValueError("Native directed GraphId order changed in hierarchy audit")
    return rows, "sha256:" + hashlib.sha256(proc.stdout.encode("utf-8")).hexdigest()


def check_native_original_route_topology(ordered: list[int], rows: list[dict],
                                         mode: str) -> dict:
    """No road-grouping or mode-based branch rejection. Original hops only."""
    if mode not in MODES or not ordered or len(ordered) > MAX_ROUTE_IDS:
        raise ValueError("Invalid route/vehicle for native branch proof")
    unique = list(dict.fromkeys(ordered))
    if [x.get("sourceGraphId") for x in rows] != unique:
        raise ValueError("Native graph rows differ from original TripLeg edge identities")
    by_id = dict(zip(unique, rows))
    counts = Counter()
    hops = []
    all_branches = []
    for idx, gid in enumerate(ordered):
        current = by_id[gid]
        root = current.get("endNodeGraphId")
        hierarchy = current.get("nativeAllHierarchyContinuationNodes")
        outgoing = current.get("outgoingDirectedEdges")
        if (type(root) is not int or root <= 0
                or not isinstance(hierarchy, list)
                or not 1 <= len(hierarchy) <= MAX_NATIVE_HIERARCHY
                or not isinstance(outgoing, list)
                or type(current.get("forwardAccess")) is not int):
            raise ValueError("Missing or truncated native hierarchy / route source")
        if hierarchy[0].get("nodeGraphId") != root or hierarchy[0].get("transitionDepth") != 0:
            raise ValueError("Root native graph hierarchy end node identity mismatch")
        root_pos = {"lat": hierarchy[0].get("nodeLat"),
                    "lng": hierarchy[0].get("nodeLon")}
        valid_point(root_pos)
        if {x.get("graphId") for x in hierarchy[0].get("allOutgoingDirectedEdges", [])} != {
                x.get("graphId") for x in outgoing}:
            raise ValueError("Native direct outgoing edge and hierarchy inventory conflict")
        node_ids = [node.get("nodeGraphId") for node in hierarchy]
        if (any(type(node_id) is not int or node_id <= 0 for node_id in node_ids)
                or len(node_ids) != len(set(node_ids))):
            raise ValueError("Duplicate or invalid native transition node")
        for node in hierarchy:
            node_pos = {"lat": node.get("nodeLat"), "lng": node.get("nodeLon")}
            valid_point(node_pos)
            if distance(root_pos, node_pos) > 1.0:
                raise ValueError("Native hierarchy transition changes physical node location")
            if (type(node.get("nodeGraphId")) is not int
                    or type(node.get("transitionDepth")) is not int
                    or not 0 <= node["transitionDepth"] <= 4):
                raise ValueError("Malformed native hierarchy transition")
            actual = node.get("allOutgoingDirectedEdges")
            if not isinstance(actual, list) or len(actual) > 256:
                raise ValueError("Missing or oversized native alternative inventory")
            edge_ids = [e.get("graphId") for e in actual]
            if (len(edge_ids) != len(set(edge_ids))
                    or any(type(e.get("graphId")) is not int or e["graphId"] <= 0
                           or type(e.get("forwardAccess")) is not int
                           or any(type(e.get(k)) is not bool
                                  for k in ("isRoad", "isShortcut"))
                           for e in actual)):
                raise ValueError("Corrupt native per-hierarchy branch data")
            transitions = node.get("nativeHierarchyTransitions")
            if not isinstance(transitions, list):
                raise ValueError("Missing native transition adjacency")
            for item in transitions:
                if (type(item.get("nodeGraphId")) is not int
                        or item["nodeGraphId"] not in node_ids
                        or type(item.get("up")) is not bool):
                    raise ValueError("Hierarchy transition not represented by original nodes")
        # The mere appearance of an outgoing GraphId in an inventory cannot
        # prove an original route hop. Its owning node must be connected to
        # the *actual end node* by real Valhalla level transitions. Persist
        # the shortest original-node transition path for independent review.
        by_node = {node["nodeGraphId"]: node for node in hierarchy}
        paths = {root: [root]}
        pending = deque([root])
        while pending:
            node_id = pending.popleft()
            for arc in by_node[node_id]["nativeHierarchyTransitions"]:
                target = arc["nodeGraphId"]
                if target not in paths:
                    paths[target] = paths[node_id] + [target]
                    pending.append(target)
        if len(paths) != len(by_node):
            raise ValueError("Disconnected native hierarchy branch cannot prove an original hop")
        for node in hierarchy:
            node_id = node["nodeGraphId"]
            if node["transitionDepth"] != len(paths[node_id]) - 1:
                raise ValueError("Native hierarchy transition depth does not match reachable path")
        # Both C++ views describe the same root outgoing graph arcs. A change
        # in identity, accessibility or endpoint cannot be hidden by equal IDs.
        shared = ("graphId", "endNodeGraphId", "forwardAccess", "isRoad", "isShortcut")
        root_edges = sorted(
            (tuple(edge.get(k) for k in shared) for edge in outgoing),
            key=lambda item: item[0])
        hierarchy_root_edges = sorted(
            (tuple(edge.get(k) for k in shared)
             for edge in hierarchy[0]["allOutgoingDirectedEdges"]),
            key=lambda item: item[0])
        if root_edges != hierarchy_root_edges:
            raise ValueError("Native root outgoing and hierarchy edge attributes disagree")
        if not (current["forwardAccess"] & MODES[mode]):
            counts["originalRouteEdgesWithDifferentModeAccessMask"] += 1
        branches = []
        for node in hierarchy:
            for edge in node["allOutgoingDirectedEdges"]:
                branches.append({
                    "nodeGraphId": node["nodeGraphId"],
                    "hierarchyDepth": node["transitionDepth"],
                    "graphId": edge["graphId"],
                    "forwardAccess": edge["forwardAccess"],
                    "isRoad": edge["isRoad"],
                    "isShortcut": edge["isShortcut"],
                    "isImmediateOpposingReverse": (
                        edge["graphId"] == current.get("opposingGraphId")),
                    "requestedModeForwardBit": bool(
                        edge["forwardAccess"] & MODES[mode]),
                })
        if len([e for e in branches if e["requestedModeForwardBit"]]) > 1:
            counts["intersectionsWithMultipleNativeModeAccessibleChoices"] += 1
        counts["allOriginalNativeOutgoingOptions"] += len(branches)
        counts["nativeModeAccessibleOutgoingOptions"] += sum(
            e["requestedModeForwardBit"] for e in branches)
        counts["nativeHierarchyTransitionNodesVisited"] += len(hierarchy)-1
        if idx + 1 < len(ordered):
            successor = ordered[idx+1]
            match = [branch for branch in branches if branch["graphId"] == successor]
            transition_path = (paths[match[0]["nodeGraphId"]]
                               if len(match) == 1 else None)
            if len(match) != 1:
                counts["originalNextDirectedEdgesUnresolvedInNativeAdjacency"] += 1
                relation = "ORIGINAL_ROUTE_SUCCESSOR_NOT_IN_NATIVE_NODE_INVENTORY"
            elif not match[0]["requestedModeForwardBit"]:
                counts["originalNextDirectedEdgesInaccessibleByNativeModeBit"] += 1
                relation = "ORIGINAL_ROUTE_SUCCESSOR_MODE_MASK_DISAGREES"
            elif match[0]["hierarchyDepth"] == 0:
                counts["originalRouteDirectNativeHops"] += 1
                relation = "EXACT_NATIVE_DIRECT_HOP"
            else:
                counts["originalRouteHierarchyTransitionHops"] += 1
                relation = "EXACT_NATIVE_LEVEL_TRANSITION_HOP"
            hops.append({"sourceGraphId": gid, "nextOriginalGraphId": successor,
                         "nativeContinuation": relation,
                         "originalNativeTransitionNodePath": transition_path})
        all_branches.append({
            "incomingOriginalDirectedGraphId": gid,
            "sourceWayIdAnnotation": current.get("wayId"),
            "sourceEndNodeGraphId": root,
            "allNativeHierarchyAndModeBranchOptions": branches,
        })
    proven = (len(hops) == len(ordered)-1
              and not any(counts[k] for k in (
                  "originalNextDirectedEdgesUnresolvedInNativeAdjacency",
                  "originalNextDirectedEdgesInaccessibleByNativeModeBit",
                  "originalRouteEdgesWithDifferentModeAccessMask")))
    return {
        "originalDirectedGraphIds": ordered,
        "originalDirectedGraphIdCount": len(ordered),
        "originalFullGraphReaderSourceRows": rows,
        "allNativeBranchInventories": all_branches,
        "originalRouteDirectedHops": hops,
        "counts": dict(sorted(counts.items())),
        "originalRouteEveryHopSupportedByNativeDirectedTopology": proven,
        "branchCompletenessWithinVisitedNodes": "ALL_NATIVE_OUTGOING_HIERARCHY_LEVELS_EXPOSED",
        "branchesOffTheObservedRoute": "PRESERVED_BUT_NOT_VALHALLA_ROUTED",
        "fullPhysicalRoadDirectionLineage": "NOT_VERIFIED_GLOBALLY",
    }


def _geometry(native: dict, incoming: dict, mode: str) -> dict:
    comparison = inspect_geometry(native, [incoming], mode)
    row = comparison["receiverObservations"][0]
    aligned = (
        row["sourceEndpointToReceiverPolylineMeters"] <= 1.0
        and row["sourceVsReceiverDirectedTangentCosine"] >= MIN_DIRECTION_COSINE)
    return {
        "directedSourceAndReceiverGeometryObservation": comparison,
        "directedLocalTangentAlignedAtHandoff": aligned,
        "samePhysicalRoadContinuity": "NOT_VERIFIED_GLOBALLY",
    }


def prove_case(case: dict, source_row: dict, native_binary: Path,
               original_binary: Path, configs: tuple[Path, Path],
               source_core, receiver_core, temp: Path) -> dict:
    mode, direction = case["mode"], case["direction"]
    cfg_a, cfg_b = configs
    origin, destination = case["originSourceCore"], case["destinationReceiverCore"]
    if not source_core.covers(_at(origin)) or not receiver_core.covers(_at(destination)):
        raise ValueError("Journey waypoints are not inside their pinned source/receiver cores")
    first = route_with_original_ids(
        cfg_a, origin, source_row["terminalEndpoint"], mode, original_binary)
    identity = case["sourceFinalDirectedGraphId"]
    base = {
        "direction": direction, "mode": mode, "sourceFinalDirectedGraphId": identity,
        "originSourceCore": origin, "destinationReceiverCore": destination,
        "actualSourceTerminal": source_row["terminalEndpoint"],
        "sourceGraphLocalCensusTerminal": True,
        # Buffer membership is an observation, NEVER a reason to skip a
        # nominated original route or suppress an Android F8 alternative.
        "sourceTerminalInsidePeerBufferAnnotation": source_row["insideVerifiedPeerBuffer"],
        "globalPhysicalRoadUniqueFinalEdge": "NOT_VERIFIED",
        "crossGraphTurnLegality": "NOT_VERIFIED",
        "AndroidPhysicalDeviceParity": "NOT_VERIFIED",
        "fullAlternativeOptimality": "NOT_VERIFIED",
        "productionPublication": "BLOCKED",
        "originalALeg": first,
    }
    if first.get("status") != "SUCCEEDED":
        return {**base, "status": "A_ORIGINAL_CORE_ROUTE_UNPROVEN"}
    orig_ids = first["originalNativeDirectedGraphIds"]
    if (first["lastDirectedGraphId"] != identity
            or first.get("originalRouteEdgeIdentity") != "ORIGINAL_VALHALLA_ROUTE_PROTOBUF"
            or distance(first["endActual"], source_row["terminalEndpoint"]) >
                MAX_EXACT_END_SNAP_METRES
            or first["endOffsetMeters"] > MAX_EXACT_END_SNAP_METRES
            or first["startOffsetMeters"] > MAX_ACCEPTED_START_SNAP_METRES
            or not source_core.covers(_at(first["startActual"]))):
        return {**base, "status": "A_ORIGINAL_SOURCE_CORE_TO_FINAL_GRAPHID_NOT_PROVEN"}
    rows_a, sha_a = capture_native_lineage(native_binary, cfg_a, orig_ids, temp)
    lineage_a = check_native_original_route_topology(orig_ids, rows_a, mode)
    second = route_with_original_ids(
        cfg_b, first["endActual"], destination, mode, original_binary)
    if second.get("status") != "SUCCEEDED":
        return {**base, "status": "B_ORIGINAL_CORE_ARRIVAL_UNPROVEN",
                "firstOriginalLineage": lineage_a,
                "firstNativeBranchCaptureSHA256": sha_a,
                "originalBLeg": second}
    b_ids = second["originalNativeDirectedGraphIds"]
    rows_b, sha_b = capture_native_lineage(native_binary, cfg_b, b_ids, temp)
    lineage_b = check_native_original_route_topology(b_ids, rows_b, mode)
    n_a = native_rows(native_binary, cfg_a, [identity], temp)[0]
    original_b_first = second["firstDirectedGraphId"]
    n_b = native_rows(native_binary, cfg_b, [original_b_first], temp)[0]
    observed = _geometry(n_a, n_b, mode)
    exact_handoff_gap = distance(first["endActual"], second["startActual"])
    original_b_destination_error = distance(
        second["endActual"], destination)
    arrived = bool(
        second["startOffsetMeters"] <= MAX_B_START_GAP_METRES
        and second["endOffsetMeters"] <= MAX_DESTINATION_ARRIVAL_METRES
        and exact_handoff_gap <= MAX_B_START_GAP_METRES
        and original_b_destination_error <= MAX_DESTINATION_ARRIVAL_METRES
        and receiver_core.covers(_at(second["endActual"])))
    all_hops = bool(
        lineage_a["originalRouteEveryHopSupportedByNativeDirectedTopology"]
        and lineage_b["originalRouteEveryHopSupportedByNativeDirectedTopology"]
        and n_a["forwardAccess"] & MODES[mode]
        and n_b["forwardAccess"] & MODES[mode])
    aligned = bool(
        arrived and all_hops and observed["directedLocalTangentAlignedAtHandoff"])
    result = {
        **base,
        "status": (
            "TWO_ORIGINAL_GRAPH_LOCAL_LEGS_AND_DIRECTED_SEAM_GEOMETRY_ALIGNED_ONLY"
            if aligned else
            "TWO_ORIGINAL_GRAPH_LOCAL_LEGS_BUT_TRANSFER_UNPROVEN"),
        "firstOriginalLineage": lineage_a,
        "secondOriginalLineage": lineage_b,
        "firstNativeBranchCaptureSHA256": sha_a,
        "secondNativeBranchCaptureSHA256": sha_b,
        "originalBLeg": second,
        "originalSourceLastGraphId": first["lastDirectedGraphId"],
        "originalReceivingFirstGraphId": original_b_first,
        "originalGraphIdsNeverComparedAcrossRegions": True,
        "bFirstGraphIdIdentifiedFromOriginalTripLeg": True,
        "originalAAndBModeMasksPresent": all_hops,
        "normalizationGapMeters": round(exact_handoff_gap, 3),
        "destinationErrorMeters": round(original_b_destination_error, 3),
        "arrivalAndHandoffSnapsWithinTolerance": arrived,
        "directedSeamGeometry": observed,
        "scopedTwoLegDirectionallyAligned": aligned,
        "originalTotalDurationSeconds": round(
            first["durationSeconds"] + second["durationSeconds"], 3),
        "originalTotalDistanceKm": round(
            first["distanceKm"] + second["distanceKm"], 4),
        "fullJourneyRoutingScope": "ONE_EXPLICIT_A_TO_X_PLUS_B_TO_DESTINATION_HYPOTHESIS_ONLY",
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("pair", "from-manifest", "to-manifest", "from-buffer", "to-buffer",
                "from-core-poly", "to-core-poly", "original-terminal-ledger",
                "cases", "native-lineage-binary", "native-route-binary", "output"):
        parser.add_argument("--" + key, type=Path, required=True)
    for key in ("from-core-poly", "to-core-poly", "original-terminal-ledger",
                "native-lineage-binary", "native-route-binary"):
        parser.add_argument("--expected-" + key + "-sha256", required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        raise ValueError("Refusing to replace immutable original journey proof")
    source_paths = (args.pair, args.from_manifest, args.to_manifest,
                    args.from_buffer, args.to_buffer, args.from_core_poly,
                    args.to_core_poly, args.original_terminal_ledger, args.cases)
    inputs = {str(path): digest(path) for path in source_paths}
    for name in ("original-terminal-ledger", "from-core-poly", "to-core-poly"):
        path = getattr(args, name.replace("-", "_"))
        expected = getattr(args, "expected_" + name.replace("-", "_") + "_sha256")
        expect_digest(path, expected)
    lineage_sha = verify_binary(args.native_lineage_binary,
                                args.expected_native_lineage_binary_sha256)
    route_sha = verify_native_route_binary(
        args.native_route_binary,
        expected_sha256=args.expected_native_route_binary_sha256)
    pair = read(args.pair)
    pair_identity(pair)
    ledger = read(args.original_terminal_ledger)
    cases = parse_cases(read(args.cases))
    if (ledger.get("pairId") != pair["pairId"]
            or ledger.get("graphFingerprints") != {
                "from": pair["fromGraphFingerprint"],
                "to": pair["toGraphFingerprint"]}
            or ledger.get("boundaryFingerprints") != {
                "from": pair["fromBoundaryFingerprint"],
                "to": pair["toBoundaryFingerprint"]}):
        raise ValueError("Original complete native terminal page uses stale graph identities")
    from_manifest = read(args.from_manifest)
    to_manifest = read(args.to_manifest)
    # Prevent mutation of a graph archive during the multi-leg proof. The
    # existing graph_manifest_info verifies before opening, but this second
    # explicit pin additionally detects replacement after route execution.
    source_archives = {}
    for side, manifest, base in (("from", from_manifest, args.from_manifest),
                                 ("to", to_manifest, args.to_manifest)):
        value = manifest.get("artifact")
        if not isinstance(value, dict) or not isinstance(value.get("fileName"), str):
            raise ValueError("Missing bound original Valhalla routing artifact")
        graph_archive = safe_child(base.parent, value["fileName"], side + " archive")
        expected = pair[side + "GraphFingerprint"]
        if digest(graph_archive) != expected:
            raise ValueError("Original native routing archive fingerprint mismatch")
        source_archives[str(graph_archive)] = expected
    buf_a = verified_buffer(args.from_buffer, from_manifest)
    buf_b = verified_buffer(args.to_buffer, to_manifest)
    if ledger.get("verified25kmBufferFingerprints") != {
            "from": buf_a["sha256"], "to": buf_b["sha256"]}:
        raise ValueError("The original terminal witness ledger is bound to different buffers")
    cores = (
        read_core(args.from_core_poly, args.expected_from_core_poly_sha256),
        read_core(args.to_core_poly, args.expected_to_core_poly_sha256))
    results = []
    with tempfile.TemporaryDirectory(prefix="f8-original-core-full-journey-") as scratch:
        temp = Path(scratch)
        a, cfg_a = graph_manifest_info(
            args.from_manifest, pair["fromRegionId"],
            to_manifest["source"]["primaryGeofabrikId"],
            pair["fromBoundaryFingerprint"], temp, "A")
        b, cfg_b = graph_manifest_info(
            args.to_manifest, pair["toRegionId"],
            from_manifest["source"]["primaryGeofabrikId"],
            pair["toBoundaryFingerprint"], temp, "B")
        verify_retained_graph_identity(pair, a, b)
        for i, case in enumerate(cases):
            dr, mode = case["direction"], case["mode"]
            source = route_terminal(ledger, dr, mode,
                                    case["sourceFinalDirectedGraphId"])
            configs = (cfg_a, cfg_b) if dr == "from-to" else (cfg_b, cfg_a)
            own, peer = (cores[0], cores[1]) if dr == "from-to" else (cores[1], cores[0])
            evidence = prove_case(case, source, args.native_lineage_binary,
                                  args.native_route_binary, configs, own, peer, temp)
            results.append(evidence)
            print(f"Original two-graph F8 {i+1}/{len(cases)} {dr} {mode} "
                  f"source={case['sourceFinalDirectedGraphId']} -> {evidence['status']}",
                  flush=True)
    if (any(digest(Path(path)) != h for path, h in inputs.items())
            or any(digest(Path(path)) != h for path, h in source_archives.items())
            or digest(args.native_lineage_binary) != lineage_sha
            or digest(args.native_route_binary) != route_sha):
        raise ValueError("Source archives or pinned original native executables changed")
    summary = Counter(row["status"] for row in results)
    report = {
        "schema": SCHEMA, "version": 1,
        "pairId": pair["pairId"],
        "fromGraphFingerprint": pair["fromGraphFingerprint"],
        "toGraphFingerprint": pair["toGraphFingerprint"],
        "fromBoundaryFingerprint": pair["fromBoundaryFingerprint"],
        "toBoundaryFingerprint": pair["toBoundaryFingerprint"],
        "verified25kmBufferSha256": {"from": buf_a["sha256"],
                                     "to": buf_b["sha256"]},
        "originalNativeTerminalLedgerSha256": args.expected_original_terminal_ledger_sha256,
        "unbufferedCoreSha256": {
            "from": args.expected_from_core_poly_sha256,
            "to": args.expected_to_core_poly_sha256},
        "nativeGraphReaderLineageBinarySha256": lineage_sha,
        "originalValhallaTripLegRouteBinarySha256": route_sha,
        "sourceInputsSha256": inputs,
        "originalImmutableRoutingArchivesSha256": source_archives,
        "originalRouteCaseCount": len(results),
        "statusCounts": dict(sorted(summary.items())),
        "cases": results,
        "originalNativeRouteLineage": "PROVEN_ONLY_FOR_EXPLICIT_ROUTE_CASES",
        "globallyUniqueFinalPhysicalRoadPerDirection": "NOT_VERIFIED",
        "originalBGraphFirstEdge": "ORIGINAL_TRIPLEG_FOR_SCOPED_LEGS_ONLY",
        "actualLegalCrossGraphTurn": "NOT_VERIFIED",
        "allDirectionsAndRoadFamiliesExhausted": "NOT_VERIFIED",
        "allFASTER_SHORTESTAlternatives": "NOT_VERIFIED",
        "originalAndroidCompleteJourneyParity": "NOT_VERIFIED",
        "productionPublication": "BLOCKED",
    }
    atomic_write(args.output, report)
    print("Scoped original road-core-to-core GraphReader lineage and directed two-leg "
          "evidence written; all-road uniqueness and transfer legality NOT_VERIFIED.",
          flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError, IndexError,
            subprocess.TimeoutExpired) as error:
        raise SystemExit("F8_ORIGINAL_CORE_JOURNEY_ERROR: " + str(error)[:420])
