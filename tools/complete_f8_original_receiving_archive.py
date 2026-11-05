#!/usr/bin/env python3
"""Reconcile every original receiving-archive directed road near A native finals.

Reads original receiver GraphReader GetTileSet() complete edge geometry scans,
NOT the earlier subset of window-scanned receiver start-node anchors. Each
eligible physical-forward peer is checked by original Valhalla 3.6.3 B-FIRST
TripLeg for both allowed vehicle modes. Preserve all distinct receiving
branches and never alter the source native final-edge proof.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

from build_f8_final_edge_connections import (
    fingerprint, native_lines, directed_line, physical_forward_continuation,
    local_receiver_probe, prove_receiver_modes, MODES
)

SCHEMA = "roadpilot.f8-original-native-all-receiver-directed-shapes"
EXPECTED_TILES = {"austria": 338, "italy-nord-est": 367}
SCAN_RADIUS = 4.0


def original_receiver_scan(native_binary: Path, config: Path,
                           points: dict[int, dict], work: Path) -> dict:
    if not points:
        raise ValueError("No original source final directed edges")
    source = work / "source-final-coordinates.csv"
    source.write_text("".join(
        f"{gid},{x['lat']:.10f},{x['lng']:.10f}\n"
        for gid,x in sorted(points.items())), encoding="ascii")
    completed = subprocess.run(
        [str(native_binary), str(config), str(source), str(SCAN_RADIUS)],
        capture_output=True, text=True, timeout=180, check=False)
    if completed.returncode:
        raise ValueError("Complete original receiver native scan failed: "
                         + completed.stderr[-300:])
    doc = json.loads(completed.stdout)
    if (doc.get("schema") != SCHEMA or doc.get("version") != 1 or
        doc.get("valhallaVersion") != "3.6.3" or
        doc.get("allGraphReaderTilesExhaustivelyRead") is not True or
        doc.get("sourcePointCount") != len(points) or
        doc.get("originalRoutableRoadShapesRead", 0) < 100 or
        doc.get("allDirectedEdgesVisited", 0) < 100 or
        doc.get("candidatePairs") != len(doc.get("nearbyOriginalDirectedShapes", []))):
        raise ValueError("Full original receiver graph census not complete")
    # No nearby receiving shape is a legitimate negative result for this
    # source finalist; preserve the original source ID with empty B candidates.
    pairs = {gid: set() for gid in points}
    for row in doc["nearbyOriginalDirectedShapes"]:
        a = row.get("sourceGraphId")
        b = row.get("receiverGraphId")
        meters = row.get("nativeSourceDistanceMetres")
        if (type(a) is not int or a not in points or
            type(b) is not int or b <= 0 or b in pairs[a] or
            type(meters) not in (int, float) or not 0 <= meters <= SCAN_RADIUS):
            raise ValueError("Complete original receiver native edge match malformed")
        pairs[a].add(b)
    if len(pairs) != len(points):
        raise ValueError("Missing all-original-tile receiver shape candidates")
    return {"summary": {key: value for key, value in doc.items()
                         if key != "nearbyOriginalDirectedShapes"},
            "pairs": pairs, "sourceCsvSha256": fingerprint(source)}


def add_verified_options(catalog: dict, source_binary: Path, native_binary: Path,
                         route_binary: Path, from_config: Path, to_config: Path,
                         work: Path) -> dict:
    source_records = catalog.get("connections")
    if not isinstance(source_records, list) or not source_records:
        raise ValueError("No verified original source-final directed GraphIds")
    if catalog.get("sourceDiscoveryComplete") is not False or catalog.get(
           "productionPublication") != "BLOCKED":
        raise ValueError("Cannot mutate a complete or publishable source catalog")
    sections = [
        ("italy-nord-est", "austria", from_config, to_config),
        ("austria", "italy-nord-est", to_config, from_config)]
    counts = Counter()
    provenance = {}
    for region, peer, config, peer_config in sections:
        current = [r for r in source_records if r["sourceRegionId"] == region]
        if not current:
            raise ValueError("Missing F8 direction from native source final ledger")
        by_gid = {r["sourceFinalDirectedGraphId"]: r for r in current}
        if len(by_gid) != len(current):
            raise ValueError("Duplicate original source final directed GraphId")
        coords = {gid: r["sourceFinalCoordinate"] for gid, r in by_gid.items()}
        native = original_receiver_scan(source_binary, peer_config, coords, work)
        native_meta = native["summary"]
        if native_meta["originalReceiverTileCount"] != EXPECTED_TILES[peer]:
            raise ValueError("Original receiving GraphReader tile archive count changed")
        all_receiver_ids = set.union(*(native["pairs"].values()))
        receiving = native_lines(native_binary, peer_config, all_receiver_ids, work)
        source = native_lines(native_binary, config, set(by_gid), work)
        peer_shapes = {gid: directed_line(edge) for gid, edge in receiving.items()}
        forwarded_count = 0
        retained = 0
        for gid, row in sorted(by_gid.items()):
            source_line = directed_line(source[gid])
            if (abs(source[gid]["directedGeometry"][-1][0] -
                    row["sourceFinalCoordinate"]["lat"]) > 0.000001 or
                abs(source[gid]["directedGeometry"][-1][1] -
                    row["sourceFinalCoordinate"]["lng"]) > 0.000001):
                raise ValueError("Original source native last endpoint differs from source proof")
            existing = {option["receiverFirstDirectedGraphId"]: option
                        for option in row["receiverOptions"]}
            if len(existing) != len(row["receiverOptions"]):
                raise ValueError("Duplicate prior original receiver directed edge")
            if not set(existing).issubset(native["pairs"][gid]):
                raise ValueError("Full original receiver archive scan missed a verified prior peer")
            for rec_id in sorted(native["pairs"][gid]):
                m = physical_forward_continuation(source_line, peer_shapes[rec_id])
                if m is None or m["status"] != "FORWARD_CONTINUOUS":
                    continue
                forwarded_count += 1
                if rec_id in existing:
                    retained += 1
                    continue
                test = local_receiver_probe(peer_shapes[rec_id],
                                            m["receiverProjectionMeters"])
                modes=set(row["sourceValhallaProvedModes"])
                proofs = prove_receiver_modes(peer_config, route_binary,
                    row["sourceFinalCoordinate"], test, rec_id, modes)
                counts["newOriginalReceiverValhallaModeProbes"] += len(proofs)
                for mode in modes:
                    proofs[mode]["originalReceiverProbeMethod"] = "INTERIOR_DIRECTED_EDGE"
                not_proved={m for m in modes if not proofs[m]["verified"]}
                # On very short genuine B segments, Valhalla can report
                # its ORIGINAL route's actual endpoint at the edge terminal
                # rather than a probe 65% into the edge. Re-test the exact
                # native terminal coordinate without relaxing snap tolerance
                # or directed-first TripLeg identity. Keep both original
                # mode-specific outcomes, even when only one can pass.
                if not_proved:
                    terminal = receiving[rec_id]["directedGeometry"][-1]
                    terminal_point={"lat":terminal[0],"lng":terminal[1]}
                    alternate=prove_receiver_modes(peer_config,route_binary,
                        row["sourceFinalCoordinate"],terminal_point,rec_id,
                        not_proved)
                    counts["receiverOriginalEdgeTerminalFallbackModeProbes"]+=len(alternate)
                    for mode, proof in alternate.items():
                        if proof["verified"]:
                            proof["originalReceiverProbeMethod"] = "NATIVE_DIRECTED_EDGE_TERMINAL"
                            proofs[mode]=proof
                            counts["receiverOriginalEdgeTerminalFallbackModesProved"]+=1
                good = [mode for mode in MODES
                        if mode in proofs and proofs[mode]["verified"]]
                if not good:
                    counts["forwardOriginalReceiverEdgesButRouteNotProved"] += 1
                    continue
                option = {
                    "receiverFirstDirectedGraphId": rec_id,
                    "receiverGraphFingerprint": catalog["graphFingerprints"][
                        "to" if region == "italy-nord-est" else "from"],
                    "sourceWayIdAnnotationOnly": source[gid]["wayId"],
                    "receiverWayIdAnnotationOnly": receiving[rec_id]["wayId"],
                    "travelModes": good,
                    "directedPhysicalGeometry": m,
                    "originalReceiverValhallaTripLeg": proofs,
                    "downstreamTestPoint": test
                }
                row["receiverOptions"].append(option)
                counts["additionalOriginalReceiverDirectedOptionsVerified"] += 1
            row["receiverOptions"].sort(key=lambda e: e["receiverFirstDirectedGraphId"])
            row["receiverAnchorCandidatesInspected"] = len(native["pairs"][gid])
            row["receiverCandidateCensusComplete"] = True
            row["originalReceiverAllTileGeometryScan"] = "EXHAUSTIVE_GETTILESET_FOR_SOURCE_END"
            counts["originalSourceFinalIDsWithFullReceiverScan"] += 1
            counts["totalDirectedPeerOptionsAfterFullScan"] += len(row["receiverOptions"])
        counts["previousVerifiedReceiverOptionsRetained"] += retained
        counts["originalNativeReceiverForwardGeometryMatches"] += forwarded_count
        counts["originalNativeReceiverArchiveDirectedEdgesVisited"] += native_meta[
            "allDirectedEdgesVisited"]
        counts["originalNativeReceiverArchiveRoadShapesRead"] += native_meta[
            "originalRoutableRoadShapesRead"]
        provenance[region] = {
            "receivingRegionId": peer,
            "nativeReceiverArchiveShapeCensus": native_meta,
            "sourceFinalQueryCsvSha256": native["sourceCsvSha256"],
            "matchingReceiverAllGraphReaderTiles": True
        }
    catalog["originalReceivingFullArchiveCensus"] = provenance
    catalog["originalReceivingFullArchiveCorrelationCounts"] = dict(counts)
    catalog["sourceDiscoveryComplete"] = False
    catalog["physicalRoadPerDirectionGlobalUniqueness"] = "NOT_VERIFIED"
    catalog["productionPublication"] = "BLOCKED"
    return catalog


def main():
    global args
    p = argparse.ArgumentParser(description=__doc__)
    for item in ("catalog", "from-config", "to-config", "from-graph", "to-graph",
                 "original-receiver-scanner", "original-endpoint-reader",
                 "original-route", "output"):
        p.add_argument("--" + item, type=Path, required=True)
    p.add_argument("--expected-native-full-receiver-sha256", required=True)
    p.add_argument("--expected-native-endpoint-sha256", required=True)
    p.add_argument("--expected-original-route-sha256", required=True)
    args = p.parse_args()
    if args.output.exists() or args.output.is_symlink():
        raise ValueError("Will not overwrite existing immutable original graph evidence")
    originals = {
        "originalReceiverScanner": args.original_receiver_scanner,
        "originalEndpointReader": args.original_endpoint_reader,
        "originalRoute": args.original_route,
        "sourceCatalog": args.catalog,
        "fromGraph": args.from_graph, "toGraph": args.to_graph
    }
    inputs = {name: fingerprint(path) for name,path in originals.items()}
    if (inputs["originalReceiverScanner"] != args.expected_native_full_receiver_sha256 or
        inputs["originalEndpointReader"] != args.expected_native_endpoint_sha256 or
        inputs["originalRoute"] != args.expected_original_route_sha256):
        raise ValueError("Native original Valhalla executable review SHA mismatch")
    document = json.loads(args.catalog.read_text())
    if document.get("schema") != "roadpilot.f8-final-directed-connections":
        raise ValueError("Input does not have source/receiving directed catalog schema")
    if document.get("graphFingerprints") != {
        "from": inputs["fromGraph"], "to": inputs["toGraph"]}:
        raise ValueError("Original graph archive hash mismatch")
    with tempfile.TemporaryDirectory(prefix="f8-original-full-receiver-") as directory:
        result = add_verified_options(document, args.original_receiver_scanner,
             args.original_endpoint_reader, args.original_route,
             args.from_config, args.to_config, Path(directory))
    result["originalReceivingFullArchiveInputSHA256"] = inputs
    for name,path in originals.items():
        if fingerprint(path) != inputs[name]:
            raise ValueError("Original immutable graph or native binary changed during run")
    keys = [(r["sourceRegionId"],r["sourceFinalDirectedGraphId"])
            for r in result["connections"] + result["unresolvedSourceFinalEdges"]]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicated source directed GraphId after receiver full scan")
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile("w",dir=args.output.parent,delete=False,
        prefix=".f8-original-full-receiver-", encoding="utf8") as stream:
        staged = Path(stream.name)
        json.dump(result,stream,separators=(",",":"),allow_nan=False)
        stream.write("\n")
    try:
        os.link(staged,args.output)
    finally:
        staged.unlink(missing_ok=True)
    print("F8_RECEIVER_FULL_ARCHIVE_COUNTS",
          result["originalReceivingFullArchiveCorrelationCounts"])
    print("F8_RECEIVER_FULL_ARCHIVE_OUTPUT",args.output,
          fingerprint(args.output),flush=True)

if __name__ == "__main__":
    try:
        main()
    except (OSError,KeyError,ValueError,TypeError,IndexError,AssertionError) as err:
        raise SystemExit("F8_RECEIVER_ARCHIVE_CENSUS_FAILED: " + str(err)[:380])
