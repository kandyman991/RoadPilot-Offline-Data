#!/usr/bin/env python3
"""Verify selected original F8 road terminal edges against native graph topology.

Production *proof gate* only, not a crossing producer or filter. It reports
whether a nominated native edge truly ends a mode-accessible graph-local road
path inside the other region's SHA-verified 25-km buffer, and whether the
ORIGINAL Valhalla route to that endpoint ends on the SAME native GraphId.
This does NOT prove unique global physical-road identity or F8 completeness.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Callable

from build_native_f8_pair_evidence import pair_identity
from capture_native_f8_graph_windows import read, require_compatible_versions
from native_f8_inputs import graph_manifest_info
from native_f8_original_route import (
    route_with_original_ids, verify_native_route_binary
)
from probe_native_f8_clipped_terminal import (
    SourceIntegrityError, check_source_terminal, verified_buffer
)
from probe_native_f8_directed_turn import native_adjacency
from probe_native_f8_journey import distance, verify_retained_graph_identity
from probe_native_f8_terminal_geometry import checked_edge, native_rows
from probe_native_f8_actual_journey import verify_native_extractor

MAX_EXPLICIT_EDGES = 16
MAX_ENDPOINT_SNAP_METRES = 1.0
DIRECTIONS = ("from-to", "to-from")
MODES = ("auto", "motorcycle")


def certify_one(source: dict, adjacency: dict, mode: str,
                own_buffer: dict, peer_buffer: dict,
                route_fn: Callable[[dict, dict, str], dict]) -> dict:
    """Never suppress a candidate due to evidence that is inconclusive."""
    native = checked_edge(source)
    terminal = check_source_terminal(
        source, adjacency, mode, own_buffer, peer_buffer)
    start = native["directedGeometry"][0]
    end = {"lat": native["endLat"], "lng": native["endLon"]}
    result = route_fn(start, end, mode)
    if not isinstance(result, dict):
        raise SourceIntegrityError("Malformed original route result")
    original = (
        result.get("status") == "SUCCEEDED"
        and result.get("originalRouteEdgeIdentity")
        == "ORIGINAL_VALHALLA_ROUTE_PROTOBUF"
        and type(result.get("lastDirectedGraphId")) is int
    )
    actual_last = (result["lastDirectedGraphId"] if original else None)
    aligned = bool(
        original and result.get("startOffsetMeters", float("inf"))
        <= MAX_ENDPOINT_SNAP_METRES
        and result.get("endOffsetMeters", float("inf"))
        <= MAX_ENDPOINT_SNAP_METRES
        and distance(end, result["endActual"]) <= MAX_ENDPOINT_SNAP_METRES
    )
    local = bool(
        terminal["graphLocalModeTerminalConfirmed"]
        and terminal["sourceEndInsidePeerRetainedBuffer"]
        # The actual retained graph is authoritative for source existence.
        # Its last directed road edge may extend beyond the separately
        # retained own-buffer GeoJSON polygon (confirmed on Italy A13).
        # Own polygon membership is diagnostic, NEVER a pre-Valhalla gate.
        and terminal["shortcutAndNonroadContinuationsPreserved"]
        and not terminal["modeUsableNonreverseOutgoingGraphIds"]
    )
    identified = aligned and actual_last == native["sourceGraphId"] and local
    return {
        "sourceGraphId": native["sourceGraphId"],
        "sourceWayIdAnnotation": native["wayId"],
        "mode": mode,
        "originalRouteLastDirectedGraphId": actual_last,
        "originalRouteUsesThisFinalDirectedEdge": (
            original and actual_last == native["sourceGraphId"]
        ),
        "originalRouteStartAndTerminalSnapsWithinOneMetre": aligned,
        "sourceNativeTerminal": terminal,
        "originalGraphLocalRoute": result,
        "perEdgeStatus": (
            "NATIVE_GRAPH_LOCAL_FINAL_DIRECTED_EDGE_WITH_ORIGINAL_ROUTE_PROVEN"
            if identified else
            "NOT_VERIFIED_AS_THIS_NATIVE_GRAPH_LOCAL_TERMINAL"
        ),
        "physicalRoadUniqueFinalEdgeAcrossGraph": "NOT_VERIFIED",
        "graphPairHandoffLegalTransfer": "NOT_VERIFIED",
        "originalAndroidJNIParity": "NOT_VERIFIED",
        "discoveryCandidateExclusion": "NONE",
        "originalReceiverGPSProposalStream": "UNCHANGED",
        "productionPublication": "BLOCKED",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("pair", "from-manifest", "to-manifest",
                "from-buffer", "to-buffer",
                "native-endpoints-binary", "native-route-edges-binary",
                "output"):
        parser.add_argument("--" + key, required=True, type=Path)
    parser.add_argument("--expected-native-route-sha256",required=True,
                        help="Owner-reviewed sha256:<64-hex> for the exact native executable")
    parser.add_argument("--direction", choices=DIRECTIONS, required=True)
    parser.add_argument("--mode", choices=MODES, required=True)
    parser.add_argument("--source-graph-id", type=int, action="append",
                        required=True)
    args = parser.parse_args()
    selected = args.source_graph_id
    if (not 1 <= len(selected) <= MAX_EXPLICIT_EDGES
            or len(selected) != len(set(selected))
            or any(type(x) is not int or x <= 0 for x in selected)):
        raise ValueError("Invalid explicitly nominated native source GraphIds")
    pair = read(args.pair)
    pair_identity(pair)
    from_manifest = read(args.from_manifest)
    to_manifest = read(args.to_manifest)
    require_compatible_versions(from_manifest, to_manifest, "3.6.3")
    own = verified_buffer(args.from_buffer, from_manifest)
    peer = verified_buffer(args.to_buffer, to_manifest)
    version = verify_native_extractor(args.native_endpoints_binary)
    route_sha = verify_native_route_binary(
        args.native_route_edges_binary,
        expected_sha256=args.expected_native_route_sha256)
    with tempfile.TemporaryDirectory(prefix="f8-true-original-terminal-") as folder:
        tmp = Path(folder)
        a, ac = graph_manifest_info(
            args.from_manifest, pair["fromRegionId"],
            to_manifest["source"]["primaryGeofabrikId"],
            pair["fromBoundaryFingerprint"], tmp, "A")
        b, bc = graph_manifest_info(
            args.to_manifest, pair["toRegionId"],
            from_manifest["source"]["primaryGeofabrikId"],
            pair["toBoundaryFingerprint"], tmp, "B")
        verify_retained_graph_identity(pair, a, b)
        if args.direction == "to-from":
            ac, bc = bc, ac
            own, peer = peer, own
        rows = native_rows(
            args.native_endpoints_binary, ac, selected, tmp)
        if len(rows) != len(selected):
            raise SourceIntegrityError("Original source edges incomplete")
        proofs = []
        for gid, source in zip(selected, rows):
            if source.get("sourceGraphId") != gid:
                raise SourceIntegrityError("Native source GraphId differs from requested identity")
            topology = native_adjacency(
                args.native_endpoints_binary, ac, gid, tmp)
            proof = certify_one(
                source, topology, args.mode, own, peer,
                lambda start,end,mode: route_with_original_ids(
                    ac,start,end,mode,args.native_route_edges_binary))
            proofs.append(proof)
    proven = sum(
        p["perEdgeStatus"] ==
        "NATIVE_GRAPH_LOCAL_FINAL_DIRECTED_EDGE_WITH_ORIGINAL_ROUTE_PROVEN"
        for p in proofs)
    result = {
        "schema": "roadpilot.f8-original-native-last-retained-graph-edge",
        "version": 1,
        "pairId": pair["pairId"],
        "fromGraphFingerprint": pair["fromGraphFingerprint"],
        "toGraphFingerprint": pair["toGraphFingerprint"],
        "fromBoundaryFingerprint": pair["fromBoundaryFingerprint"],
        "toBoundaryFingerprint": pair["toBoundaryFingerprint"],
        "direction": args.direction, "mode": args.mode,
        "nativeEndpointsVersion": version["nativeExtractorVersion"],
        "nativeEndpointsBinarySha256": version["nativeExtractorSha256"],
        "originalRouteBinarySha256": route_sha,
        "sourceBufferSha256": own["sha256"],
        "receiverBufferSha256": peer["sha256"],
        "explicitlyNominatedSourceCount": len(selected),
        "provenGraphLocalTerminalRoutes": proven,
        "sourceEvidence": proofs,
        "roadNameOrWayBasedDeduplication": "NONE",
        "sourcePhysicalRoadFinalIdentity": "NOT_VERIFIED_GLOBALLY",
        "globalAllPhysicalRoadCoverage": "NOT_VERIFIED",
        "otherRegionCrossGraphTurnLegality": "NOT_VERIFIED",
        "androidJNIParity": "NOT_VERIFIED",
        "productionPublication": "BLOCKED",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        raise ValueError("Refusing to overwrite existing source terminal proof")
    import os
    with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=args.output.parent,
            prefix=".f8-native-original-terminal-", delete=False) as item:
        temporary = Path(item.name)
        json.dump(result,item,indent=2,allow_nan=False)
        item.write("\n")
    try:
        os.link(temporary,args.output)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"{proven}/{len(selected)} originally routed graph-local terminals "
          "proven on explicitly selected native edges; global physical-road "
          "coverage and JNI parity remain NOT_VERIFIED.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, TypeError,
            SourceIntegrityError, subprocess.TimeoutExpired) as error:
        print("F8_ORIGINAL_TERMINAL_ERROR: " + str(error)[:330],
              file=sys.stderr)
        sys.exit(2)
