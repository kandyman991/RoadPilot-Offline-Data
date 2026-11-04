#!/usr/bin/env python3
"""Read-only source-complete native F8 terminal ledger with original route-edge probes.

This is a production *fail-closed proof gate*, NOT a physical-road deduper or
crossing sidecar. Every native graph-local terminal survives; an explicit,
bounded selection of cut-line witnesses receives original TripLeg GraphId
checks. No road labels, way IDs, GPS distance or cross-graph GraphIds are used
to exclude candidates, establish road identity, or publish a connection.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

import shapely
from shapely.prepared import prep

from build_native_f8_pair_evidence import pair_identity, source_scans
from capture_native_f8_graph_windows import read
from census_native_f8_final_directed_edges import verify_binary
from native_f8_inputs import graph_manifest_info, load_polygon
from native_f8_original_route import route_with_original_ids, verify_native_route_binary
from probe_native_f8_clipped_terminal import CRS, _at, verified_buffer
from probe_native_f8_journey import distance, verify_retained_graph_identity
from probe_native_f8_terminal_geometry import checked_edge, native_rows
from verify_native_f8_receiver_adjacency import AUTO_ACCESS, MOTORCYCLE_ACCESS

SCHEMA = "roadpilot.f8-original-terminal-lineage-ledger"
MODES = {"auto": AUTO_ACCESS, "motorcycle": MOTORCYCLE_ACCESS}
MAX_PROOFS_PER_MODE = 24
SNAP_TOLERANCE_METRES = 1.0
CORE_PROVENANCE = "EXPLICIT_SHA_PINNED_GEOFABRIK_CORE_ANNOTATION_NOT_GRAPH_BUILD_BOUND"
UNRESOLVED = "PHYSICAL_ROAD_DIRECTION_LINEAGE_NOT_ESTABLISHED"


def digest(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise ValueError("Input missing or symlink: " + str(path))
    with path.open("rb") as f:
        return "sha256:" + hashlib.file_digest(f, "sha256").hexdigest()


def expect_digest(path: Path, expected: str) -> str:
    if not isinstance(expected, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", expected):
        raise ValueError("Mandatory independent SHA256 pin missing")
    actual = digest(path)
    if actual != expected:
        raise ValueError("Immutable input SHA256 mismatch: " + str(path))
    return actual


def read_core(path: Path, expected_sha256: str):
    expect_digest(path, expected_sha256)
    poly = load_polygon(path)
    if poly.is_empty or not poly.is_valid or poly.geom_type not in ("Polygon", "MultiPolygon"):
        raise ValueError("Invalid Geofabrik source core polygon")
    # The project stores original source cores as lon/lat, buffers as EPSG:3035.
    return prep(shapely.transform(poly, CRS.transform, interleaved=False))


def pair_guard(pair: dict, census: dict, scans: dict[str, dict]) -> None:
    pair_identity(pair)
    if (census.get("schema") != "roadpilot.f8-native-full-graph-local-terminal-census"
            or census.get("version") != 1 or
            census.get("nativeTopologyCoverage") != "ALL_RETAINED_NATIVE_SCAN_EDGES"):
        raise ValueError("Exhaustive native terminal census is not certified")
    for key in ("pairId", "fromGraphFingerprint", "toGraphFingerprint",
                "fromBoundaryFingerprint", "toBoundaryFingerprint"):
        if census.get(key) != pair.get(key):
            raise ValueError("Pair/census immutable graph identity mismatch: " + key)
    if census.get("globalOneFinalRetainedEdgePerPhysicalRoadDirection") != "NOT_VERIFIED":
        raise ValueError("Upstream census illegally claims physical-road completeness")
    declared = census.get("sourceScanSHA256")
    if not isinstance(declared, dict):
        raise ValueError("Census lacks source scan provenance")
    for direction, side in (("from-to", "from"), ("to-from", "to")):
        expected = census.get("directions", {}).get(direction)
        actual = scans[direction]
        if not isinstance(expected, dict) or not isinstance(actual, dict):
            raise ValueError("Native side lacks source evidence")
        edges = actual.get("edges")
        counts = expected.get("counts", {})
        if not isinstance(edges, list) or counts.get("nativeDirectedEdgesAudited") != len(edges):
            raise ValueError("Inconsistent 1:1 original native scan edge coverage")
        if expected.get("edgeCoverage") != "ALL_SOURCE_NATIVE_SCAN_IDS_RECONCILED":
            raise ValueError("Upstream source coverage incomplete")
        if type(counts.get("nativeDirectedEdgesAudited")) is not int:
            raise ValueError("Invalid native census total")
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", declared.get(side, "")):
            raise ValueError("Missing source SHA256 binding")


def build_side_ledger(
    scan: dict, source_census: dict, own_buffer: dict, peer_buffer: dict,
    own_core, peer_core, direction: str,
) -> dict:
    """Emit EVERY native mode terminal; polygon labels never remove candidates."""
    source = {}
    for edge in scan["edges"]:
        gid = edge.get("graphId")
        if type(gid) is not int or gid <= 0 or gid in source:
            raise ValueError("Malformed/duplicate native source GraphId")
        source[gid] = edge

    result = {}
    for mode, bit in MODES.items():
        rows = source_census["allGraphLocalModeTerminals"][mode]
        expected = source_census["counts"][f"{mode}GraphLocalFinalDirectedEdges"]
        if not isinstance(rows, list) or len(rows) != expected:
            raise ValueError("Terminal census count mismatch for " + mode)
        identities = set()
        ledger = []
        classes = Counter()
        for row in rows:
            gid = row.get("graphId")
            if type(gid) is not int or gid in identities or gid not in source:
                raise ValueError("Missing/duplicate mode terminal GraphId")
            identities.add(gid)
            s = source[gid]
            if (s.get("wayId") != row.get("wayIdAnnotationOnly")
                    or not s.get("forwardAccess", 0) & bit
                    or not isinstance(row.get("endLat"), (int, float))
                    or not isinstance(row.get("endLon"), (int, float))
                    or row.get("terminalStatus") != "NATIVE_GRAPH_LOCAL_MODE_TERMINAL_ONLY"):
                raise ValueError("Census native identity and access mismatch")
            point = _at({"lat": row["endLat"], "lng": row["endLon"]})
            inside_own = own_core.covers(point)
            inside_peer = peer_core.covers(point)
            in_verified_peer_buffer = peer_buffer["polygon"].covers(point)
            if in_verified_peer_buffer != row.get("insidePeerBuffer"):
                raise ValueError("Peer SHA-bound polygon changed since native census")
            category = ("BOTH_CORES" if inside_own and inside_peer else
                        "SOURCE_CORE" if inside_own else
                        "RECEIVER_CORE" if inside_peer else
                        "OUTSIDE_BOTH_SOURCE_CORES")
            classes[category] += 1
            # Exact EPSG:3035 boundary distance, not a route/physical identity proof.
            edge_cut_distance = own_buffer["polygon"].boundary.distance(point)
            ledger.append({
                "sourceGraphId": gid,
                "nativeEndNodeGraphId": row["endNodeGraphId"],
                "nativeWayIdAnnotationOnly": row["wayIdAnnotationOnly"],
                "sourceEndpoint": {"lat": s["lat"], "lng": s["lon"]},
                "terminalEndpoint": {"lat": row["endLat"], "lng": row["endLon"]},
                "sourceForwardAccess": s["forwardAccess"],
                "sourceRoadClass": s.get("roadClass"),
                "insideVerifiedPeerBuffer": in_verified_peer_buffer,
                "unbufferedCoreClassification": category,
                "metresToOwnVerifiedBufferOuterBoundary": round(edge_cut_distance, 3),
                "physicalRoadLineage": UNRESOLVED,
                "nativeGraphLocalTerminal": "PROVEN_BY_FULL_TOPOLOGY_CENSUS",
                "originalRouteLastEdge": "NOT_PROBED",
                "candidateSuppressed": False,
                "publication": "BLOCKED",
            })
        result[mode] = {
            "sourceDirectedGraphIdsInNativeScan": len(scan["edges"]),
            "allGraphLocalModeTerminalCount": len(ledger),
            "terminalCoreAnnotations": dict(sorted(classes.items())),
            "allTerminals": ledger,
            "sourceCoverage": "ALL_NATIVE_CENSUS_TERMINALS_RETAINED",
            "globalOnePhysicalRoadEdgePerDirection": "NOT_VERIFIED",
            "originalRouteCoverage": "NOT_VERIFIED",
        }
    return result


def select_for_original_route_proof(mode_doc: dict, *, band_metres: float,
                                    page_offset: int, page_size: int) -> list[dict]:
    """Prioritization only: all other candidate rows remain in the complete ledger."""
    eligible = [row for row in mode_doc["allTerminals"]
                if row["unbufferedCoreClassification"] in ("RECEIVER_CORE", "BOTH_CORES")
                and row["metresToOwnVerifiedBufferOuterBoundary"] <= band_metres
                and row["insideVerifiedPeerBuffer"]]
    eligible.sort(key=lambda row: (
        row["metresToOwnVerifiedBufferOuterBoundary"], row["sourceGraphId"]))
    mode_doc["prioritizedWitnessCount"] = len(eligible)
    mode_doc["witnessPriorityIsEligibility"] = False
    mode_doc["witnessPageOffset"] = page_offset
    mode_doc["witnessPageSize"] = page_size
    return eligible[page_offset:page_offset + page_size]


def check_original_terminal_route(row: dict, original: dict) -> dict:
    """Only original TripLeg IDs can promote one nominated GraphId/route pair."""
    expected = row["sourceGraphId"]
    valid = bool(
        original.get("status") == "SUCCEEDED"
        and original.get("originalRouteEdgeIdentity") == "ORIGINAL_VALHALLA_ROUTE_PROTOBUF"
        and original.get("edgeIdOrigin") == "ORIGINAL_TRIPLEG_NODE_EDGE_PROTOBUF"
        and original.get("lastDirectedGraphId") == expected
        and isinstance(original.get("originalNativeDirectedGraphIds"), list)
        and original["originalNativeDirectedGraphIds"][-1] == expected
        and original.get("startOffsetMeters", 1e99) <= SNAP_TOLERANCE_METRES
        and original.get("endOffsetMeters", 1e99) <= SNAP_TOLERANCE_METRES
        and distance(original["endActual"], row["terminalEndpoint"]) <= SNAP_TOLERANCE_METRES
    )
    return {
        "sourceGraphId": expected,
        "originalRouteStatus": original.get("status", "INVALID"),
        "originalLastDirectedGraphId": original.get("lastDirectedGraphId"),
        "routeDirectedGraphIdCount": len(original.get("originalNativeDirectedGraphIds", [])),
        # Preserve original ordered Valhalla TripLeg IDs as per-route lineage
        # evidence; never infer a second graph's IDs from this sequence.
        "originalGraphLocalRouteDirectedGraphIds": (
            original.get("originalNativeDirectedGraphIds", [])
            if original.get("status") == "SUCCEEDED" else []),
        "startSnapOffsetMeters": original.get("startOffsetMeters"),
        "terminalSnapOffsetMeters": original.get("endOffsetMeters"),
        "nativeFailureReason": str(original.get("reason", ""))[:320]
            if original.get("status") != "SUCCEEDED" else None,
        "originalLastGraphLocalEdgeMatchesTerminal": valid,
        "status": ("ORIGINAL_VALHALLA_LAST_EDGE_ON_THIS_ROUTE_PROVEN" if valid
                   else "ORIGINAL_VALHALLA_LAST_EDGE_NOT_PROVEN"),
        "physicalRoadDirectionUniqueness": "NOT_VERIFIED_GLOBALLY",
        "crossGraphTransfer": "NOT_VERIFIED",
        "publication": "BLOCKED",
    }


def atomic_write(path: Path, document: dict) -> None:
    if path.exists() or path.is_symlink():
        raise ValueError("Refusing to overwrite existing proof evidence")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent,
        prefix=".roadpilot-terminal-lineage-", delete=False
    ) as stream:
        stage = Path(stream.name)
        json.dump(document, stream, indent=2, allow_nan=False)
        stream.write("\n")
    try:
        os.link(stage, path)
    finally:
        stage.unlink(missing_ok=True)


def main() -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    for label in ("pair", "from-manifest", "to-manifest",
                  "from-buffer", "to-buffer", "from-core-poly", "to-core-poly",
                  "from-native-scan", "to-native-scan", "native-summary",
                  "full-native-census", "native-endpoints-binary",
                  "native-route-edges-binary", "output"):
        cli.add_argument("--" + label, required=True, type=Path)
    for label in ("full-native-census", "from-core-poly", "to-core-poly",
                  "native-endpoints", "native-route"):
        cli.add_argument("--expected-" + label + "-sha256", required=True)
    cli.add_argument("--route-witness-band-metres", type=float, default=20.0)
    cli.add_argument("--route-page-offset", type=int, default=0)
    cli.add_argument("--route-page-size", type=int, default=0)
    args = cli.parse_args()
    if (not 0 < args.route_witness_band_metres <= 1000
            or not 0 <= args.route_page_offset < 1000000
            or not 0 <= args.route_page_size <= MAX_PROOFS_PER_MODE):
        raise ValueError("Invalid strictly bounded witness proof window")
    if args.output.exists() or args.output.is_symlink():
        raise ValueError("Immutable report path already exists")
    input_paths = (args.pair, args.from_manifest, args.to_manifest,
                   args.from_buffer, args.to_buffer, args.from_core_poly,
                   args.to_core_poly, args.from_native_scan, args.to_native_scan,
                   args.native_summary, args.full_native_census)
    before = {str(path): digest(path) for path in input_paths}
    expect_digest(args.full_native_census, args.expected_full_native_census_sha256)
    for side in ("from", "to"):
        expect_digest(getattr(args, side + "_core_poly"),
                      getattr(args, "expected_" + side + "_core_poly_sha256"))
    binary = verify_binary(args.native_endpoints_binary,
                           args.expected_native_endpoints_sha256)
    route_binary = verify_native_route_binary(
        args.native_route_edges_binary,
        expected_sha256=args.expected_native_route_sha256)
    pair = read(args.pair)
    census = read(args.full_native_census)
    scan_summary = read(args.native_summary)
    scan_from, scan_to, scan_provenance = source_scans(
        pair, from_scan=read(args.from_native_scan),
        to_scan=read(args.to_native_scan), scan_summary=scan_summary)
    scans = {"from-to": scan_from, "to-from": scan_to}
    pair_guard(pair, census, scans)
    if (before[str(args.from_native_scan)] != census["sourceScanSHA256"]["from"]
            or before[str(args.to_native_scan)] != census["sourceScanSHA256"]["to"]):
        raise ValueError("Native scan files do not match full census SHA256")
    first_manifest, second_manifest = read(args.from_manifest), read(args.to_manifest)
    from_buffer = verified_buffer(args.from_buffer, first_manifest)
    to_buffer = verified_buffer(args.to_buffer, second_manifest)
    if (from_buffer["sha256"] != census["fromBufferSha256"]
            or to_buffer["sha256"] != census["toBufferSha256"]):
        raise ValueError("Native census and verified 25km buffer mismatch")
    cores = (read_core(args.from_core_poly, args.expected_from_core_poly_sha256),
             read_core(args.to_core_poly, args.expected_to_core_poly_sha256))
    directions = {}
    with tempfile.TemporaryDirectory(prefix="roadpilot-f8-terminal-lineage-") as temp:
        working = Path(temp)
        first, first_cfg = graph_manifest_info(
            args.from_manifest, pair["fromRegionId"],
            second_manifest["source"]["primaryGeofabrikId"],
            pair["fromBoundaryFingerprint"], working, "A")
        second, second_cfg = graph_manifest_info(
            args.to_manifest, pair["toRegionId"],
            first_manifest["source"]["primaryGeofabrikId"],
            pair["toBoundaryFingerprint"], working, "B")
        verify_retained_graph_identity(pair, first, second)
        for direction, own, peer, own_core, peer_core, config in (
                ("from-to", from_buffer, to_buffer, cores[0], cores[1], first_cfg),
                ("to-from", to_buffer, from_buffer, cores[1], cores[0], second_cfg)):
            side = build_side_ledger(
                scans[direction], census["directions"][direction],
                own, peer, own_core, peer_core, direction)
            for mode in MODES:
                chosen = select_for_original_route_proof(
                    side[mode], band_metres=args.route_witness_band_metres,
                    page_offset=args.route_page_offset, page_size=args.route_page_size)
                proof = []
                if chosen:
                    native = native_rows(
                        args.native_endpoints_binary, config,
                        [c["sourceGraphId"] for c in chosen], working)
                    for row, native_edge in zip(chosen, native):
                        checked = checked_edge(native_edge)
                        if (checked["sourceGraphId"] != row["sourceGraphId"]
                                or checked["wayId"] != row["nativeWayIdAnnotationOnly"]
                                or checked["forwardAccess"] != row["sourceForwardAccess"]
                                or distance({"lat": checked["endLat"],
                                             "lng": checked["endLon"]},
                                            row["terminalEndpoint"]) > 1.0):
                            raise ValueError("Graph-native witness geometry disagrees with census")
                        origin = checked["directedGeometry"][0]
                        target = row["terminalEndpoint"]
                        original = route_with_original_ids(
                            config, origin, target, mode, args.native_route_edges_binary)
                        result = check_original_terminal_route(row, original)
                        proof.append(result)
                        row["originalRouteLastEdge"] = result["status"]
                side[mode]["selectedOriginalRouteWitnesses"] = proof
                side[mode]["originalRouteWitnessCount"] = len(proof)
                side[mode]["originalLastEdgesProven"] = sum(
                    p["originalLastGraphLocalEdgeMatchesTerminal"] for p in proof)
                side[mode]["originalRouteCoverage"] = (
                    "BOUNDED_SELECTED_WITNESSES_ONLY" if proof else "NOT_PROBED")
                print(direction, mode, "source terminals", len(side[mode]["allTerminals"]),
                      "prioritized", side[mode]["prioritizedWitnessCount"],
                      "original-route proven", side[mode]["originalLastEdgesProven"],
                      "/", len(proof), flush=True)
            directions[direction] = side

    if (any(digest(Path(p)) != expected for p, expected in before.items())
            or digest(args.native_endpoints_binary) != binary
            or digest(args.native_route_edges_binary) != route_binary):
        raise ValueError("Immutable input or original native binary changed mid-proof")

    result = {
        "schema": SCHEMA, "version": 1,
        "pairId": pair["pairId"],
        "graphFingerprints": {
            "from": pair["fromGraphFingerprint"], "to": pair["toGraphFingerprint"]},
        "boundaryFingerprints": {
            "from": pair["fromBoundaryFingerprint"], "to": pair["toBoundaryFingerprint"]},
        "verified25kmBufferFingerprints": {
            "from": from_buffer["sha256"], "to": to_buffer["sha256"]},
        "fullNativeCensusSha256": args.expected_full_native_census_sha256,
        "unbufferedCorePolygonProvenance": CORE_PROVENANCE,
        "unbufferedCorePolygonSha256": {
            "from": args.expected_from_core_poly_sha256,
            "to": args.expected_to_core_poly_sha256},
        "originalNativeBinariesSha256": {
            "topology": binary, "originalRoute": route_binary},
        "allSourceNativeDirectedScansReconciled": True,
        "sourceScanProvenance": scan_provenance,
        "inputFilesSHA256": before,
        "directions": directions,
        "oneFinalEdgePerPhysicalRoadAndDirection": "NOT_VERIFIED",
        "physicalRoadEquivalenceClasses": "NOT_ESTABLISHED",
        "originalValhallaAllRoadRouteIdentity": "BOUNDED_WITNESSES_ONLY",
        "independentReceivingGraphDirectionalHandoff": "NOT_VERIFIED",
        "sameGraphAndroidF8ScannerParity": "SEPARATE_ANDROID_EVIDENCE_ONLY",
        "originalRoadNameOrWayDeduplication": "NONE",
        "candidateExclusion": "NONE",
        "productionPublication": "BLOCKED",
    }
    atomic_write(args.output, result)
    print("Immutable F8 native terminal lineage ledger written. Global physical-road"
          " uniqueness and cross-graph journey legality are NOT_VERIFIED.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError, IndexError) as failure:
        raise SystemExit("F8_TERMINAL_LINEAGE_ERROR: " + str(failure)[:390])
