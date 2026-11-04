#!/usr/bin/env python3
"""Reconcile real original A-last/B-first TripLeg identities against Graph Studio's
COMPLETE native receiver directed candidate streams, no candidate reduction.

A native B first original TripLeg GraphId missing from the actual full scan is
a genuine candidate-coverage gap, never proof that the physical road is illegal.
The script NEVER compares an A numeric GraphId to a B numeric GraphId, produces
a crossing package, or claims Android JNI or legal A/B transfer parity.
"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from build_native_f8_pair_evidence import pair_identity, source_scans
from capture_native_f8_graph_windows import read
from compile_native_f8_terminal_lineage_proof import digest, expect_digest, atomic_write
from probe_native_f8_journey import distance

SCHEMA = "roadpilot.f8-original-journeys-native-receiver-source-coverage"
SCOPED = "SCOPED_ORIGINAL_TRIPLEG_DIRECTED_GPS_IDENTITIES_ONLY"
ACCESS = {"auto": 1, "motorcycle": 1024}


def original_receiver_source_coverage(pair: dict, original: dict,
                                      from_scan: dict, to_scan: dict) -> dict:
    pair_identity(pair)
    if (original.get("schema") != "roadpilot.f8-original-core-directed-branch-journey"
            or original.get("version") != 1
            or original.get("productionPublication") != "BLOCKED"
            or original.get("pairId") != pair["pairId"]
            or original.get("globallyUniqueFinalPhysicalRoadPerDirection") != "NOT_VERIFIED"
            or original.get("fromGraphFingerprint") != pair["fromGraphFingerprint"]
            or original.get("toGraphFingerprint") != pair["toGraphFingerprint"]):
        raise ValueError("Incompatible or falsely complete original native journey report")
    a = from_scan["edges"]
    b = to_scan["edges"]
    if not isinstance(a, list) or not isinstance(b, list):
        raise ValueError("Original complete native source scans missing")
    indexes = []
    for scan in (a, b):
        idx = {}
        for item in scan:
            gid = item.get("graphId")
            if (type(gid) is not int or gid <= 0 or gid in idx
                    or type(item.get("forwardAccess")) is not int
                    or not 0 <= item["forwardAccess"] < 2**32):
                raise ValueError("Duplicate, incomplete or invalid native source graph IDs")
            idx[gid] = item
        indexes.append(idx)

    detailed, counts = [], Counter()
    original_cases = original.get("cases")
    if not isinstance(original_cases, list) or not original_cases:
        raise ValueError("Original route proof missing nominated journeys")
    for case in original_cases:
        direction = case.get("direction")
        mode = case.get("mode")
        if direction not in ("from-to","to-from") or mode not in ACCESS:
            raise ValueError("Malformed original mode/direction proof")
        source_index, receiver_index = (
            (indexes[0], indexes[1]) if direction == "from-to"
            else (indexes[1], indexes[0]))
        source_gid = case.get("originalSourceLastGraphId")
        receiver_gid = case.get("originalReceivingFirstGraphId")
        expected_source = case.get("sourceFinalDirectedGraphId")
        if (type(source_gid) is not int or source_gid != expected_source
                or type(receiver_gid) is not int or receiver_gid <= 0
                or case.get("bFirstGraphIdIdentifiedFromOriginalTripLeg") is not True
                or case.get("originalGraphIdsNeverComparedAcrossRegions") is not True):
            raise ValueError("Original A/B first-last GraphId provenance incomplete")
        first = case.get("originalALeg")
        second = case.get("originalBLeg")
        if (not isinstance(first, dict) or not isinstance(second, dict)
                or first.get("lastDirectedGraphId") != source_gid
                or second.get("firstDirectedGraphId") != receiver_gid
                or first.get("edgeIdOrigin") != "ORIGINAL_TRIPLEG_NODE_EDGE_PROTOBUF"
                or second.get("edgeIdOrigin") != "ORIGINAL_TRIPLEG_NODE_EDGE_PROTOBUF"):
            raise ValueError("Original local legs lack genuine matching TripLeg IDs")
        entry_a = source_index.get(source_gid)
        entry_b = receiver_index.get(receiver_gid)
        source_active = bool(entry_a and entry_a["forwardAccess"] & ACCESS[mode])
        receiver_active = bool(entry_b and entry_b["forwardAccess"] & ACCESS[mode])
        normalized = first.get("endActual")
        if not isinstance(normalized, dict):
            raise ValueError("Missing original normalized A route terminal")
        distance_b = (round(distance(
            normalized, {"lat":entry_b["lat"],"lng":entry_b["lon"]}), 3)
            if entry_b is not None else None)
        distance_a = (round(distance(
            normalized, {"lat":entry_a["lat"],"lng":entry_a["lon"]}), 3)
            if entry_a is not None else None)
        # Graph A's source scanner samples the INTERIOR of its original
        # directed edge, which may be 160m from the true terminal X. Matching
        # original A GraphId is authoritative: requiring its GPS sample to
        # equal the end node would manufacture a false missing-road result.
        # B's first native directed candidate must still be geographically
        # at the actual normalized A handoff X to prove THIS receiver proposal.
        matched = bool(entry_a and entry_b and source_active and receiver_active
                       and distance_b <= 1.0)
        counts["allOriginalRoutePairs"] += 1
        if entry_a is not None:
            counts["originalSourceLastPresentInAFullScan"] += 1
        if entry_b is not None:
            counts["originalReceiverFirstPresentInBFullScan"] += 1
        if matched:
            counts["originalAEdgePresentAndBReceiverGpsMatched"] += 1
        else:
            counts["originalRouteAndNativeCandidateScannerGaps"] += 1
        detailed.append({
            "direction":direction, "mode":mode,
            "originalSourceLastGraphId":source_gid,
            "originalReceiverFirstGraphId":receiver_gid,
            "sourceLastPresentInNativeOriginalScan":entry_a is not None,
            "receiverFirstPresentInNativeOriginalScan":entry_b is not None,
            "sourceLastForwardModeBit":source_active,
            "receiverFirstForwardModeBit":receiver_active,
            "sourceOriginalScannerGpsToTerminalMetersAnnotationOnly":distance_a,
            "sourceScannerSampleMayBeInteriorToDirectedEdge": True,
            "originalReceiverFirstGpsToF8ScannerSampleMeters":distance_b,
            "originalAEdgeIdAndReceivingBFirstGpsMatched":matched,
            "sourceAndReceiverRoadNameOrWayComparison":"NONE",
            "physicalDirectedTransferLegal":"NOT_VERIFIED",
            "productionPublication":"BLOCKED",
        })
    return {
        "schema": SCHEMA, "version":1, "pairId":pair["pairId"],
        "graphFingerprints":{
            "from":pair["fromGraphFingerprint"],"to":pair["toGraphFingerprint"]},
        "nativeDirectedScanSourceCounts":{"from":len(a),"to":len(b)},
        "counts":dict(sorted(counts.items())),
        "originalValhallaReceiverIdentitiesInNativeGraphStudioScans":(
            "SCOPED_ORIGINAL_A_EDGE_ID_AND_B_RECEIVER_GPS_MATCHED" if
            counts["originalRouteAndNativeCandidateScannerGaps"] == 0 else
            "SCOPED_NATIVE_A_EDGE_OR_RECEIVER_B_GAPS_PRESENT"),
        "caseDetails":detailed,
        "proofScope":SCOPED,
        "allPhysicalRoadsAndDirectionsExhausted":"NOT_VERIFIED",
        "realAndroidJNIParity":"NOT_VERIFIED",
        "fullCrossGraphLegalTransfer":"NOT_VERIFIED",
        "productionPublication":"BLOCKED",
    }


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ("pair","from-native-scan","to-native-scan","native-summary",
                "full-native-census","original-core-route-report","output"):
        parser.add_argument("--"+key, type=Path, required=True)
    for key in ("full-native-census","original-core-route-report"):
        parser.add_argument("--expected-"+key+"-sha256", required=True)
    args=parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        raise ValueError("Refusing to overwrite existing immutable source coverage audit")
    original_paths=(args.pair,args.from_native_scan,args.to_native_scan,
                    args.native_summary,args.full_native_census,args.original_core_route_report)
    prior={str(path):digest(path) for path in original_paths}
    expect_digest(args.full_native_census,args.expected_full_native_census_sha256)
    expect_digest(args.original_core_route_report,
                  args.expected_original_core_route_report_sha256)
    pair=read(args.pair)
    pair_identity(pair)
    full=read(args.full_native_census)
    if (full.get("schema") != "roadpilot.f8-native-full-graph-local-terminal-census"
            or full.get("nativeTopologyCoverage") != "ALL_RETAINED_NATIVE_SCAN_EDGES"
            or full.get("pairId") != pair["pairId"]):
        raise ValueError("Source full-census GraphIds not bound to source pair")
    for member in ("fromGraphFingerprint","toGraphFingerprint",
                   "fromBoundaryFingerprint","toBoundaryFingerprint"):
        if full.get(member) != pair.get(member):
            raise ValueError("Source native census and actual graph versions differ")
    originals=full.get("sourceScanSHA256")
    if (not isinstance(originals,dict)
            or prior[str(args.from_native_scan)] != originals.get("from")
            or prior[str(args.to_native_scan)] != originals.get("to")):
        raise ValueError("Real original complete source scans differ from SHA-pinned full census")
    from_scan,to_scan,provenance=source_scans(
        pair,from_scan=read(args.from_native_scan),
        to_scan=read(args.to_native_scan),scan_summary=read(args.native_summary))
    report=original_receiver_source_coverage(
        pair,read(args.original_core_route_report),from_scan,to_scan)
    if any(digest(Path(path)) != sha for path,sha in prior.items()):
        raise ValueError("Original A/B route evidence or complete scanner data changed during audit")
    report["sourceInputsSha256"]=prior
    report["nativeScanProvenance"]=provenance
    atomic_write(args.output,report)
    print("Original TripLeg first-B/last-A source scanner reconciliation:",
          report["counts"],"No physical-road uniqueness or Android parity claimed.")
    return 0


if __name__=="__main__":
    try:
        raise SystemExit(main())
    except (OSError,ValueError,KeyError,TypeError,IndexError) as failure:
        raise SystemExit("F8_ORIGINAL_RECEIVER_COVERAGE_ERROR: "+str(failure)[:360])
