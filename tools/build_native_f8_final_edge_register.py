#!/usr/bin/env python3
"""Produce ONE graph-local terminal candidate record per original directed GraphId.

This is the first, nonpublishing final-edge-focused F8 production stage.
Two vehicle modes on the same original directed edge are not two handoffs.
Neither shared OSM way/name, nearby GPS, nor a successful sample route may
collapse distinct directed GraphIds or establish a physical-road class.

The native complete source scan remains authoritative and unchanged. These
terminal candidates are NOT YET proved one final edge per physical road and
direction; mode-stranded and nonterminal source edges remain explicitly
unclassified, never discarded from F8 discovery.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile

from build_native_f8_pair_evidence import pair_identity, source_scans
from capture_native_f8_graph_windows import read

SCHEMA = "roadpilot.f8-one-final-directed-edge-candidate-register"
CENSUS_SCHEMA = "roadpilot.f8-native-full-graph-local-terminal-census"
MODE_BITS = {"auto": 1, "motorcycle": 1024}
_SHA = re.compile(r"sha256:[0-9a-f]{64}")


def digest(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise ValueError("Source evidence is missing or symlinked")
    with path.open("rb") as stream:
        return "sha256:" + hashlib.file_digest(stream, "sha256").hexdigest()


def pinned(path: Path, expected: str) -> str:
    if not isinstance(expected, str) or not _SHA.fullmatch(expected):
        raise ValueError("Missing explicit original evidence SHA-256 pin")
    actual = digest(path)
    if actual != expected:
        raise ValueError("Original evidence SHA-256 mismatch")
    return actual


def _number(value: object, bound: float) -> float:
    if (type(value) not in (int, float) or not math.isfinite(value)
            or not -bound <= value <= bound):
        raise ValueError("Malformed original native endpoint coordinate")
    return float(value)


def make_register(pair: dict, census: dict, from_scan: dict, to_scan: dict) -> dict:
    """Consolidate mode repetitions only; preserve every distinct native ID."""
    pair_identity(pair)
    if (census.get("schema") != CENSUS_SCHEMA or census.get("version") != 1
            or census.get("pairId") != pair["pairId"]
            or census.get("nativeTopologyCoverage") != "ALL_RETAINED_NATIVE_SCAN_EDGES"
            or census.get("globalOneFinalRetainedEdgePerPhysicalRoadDirection") != "NOT_VERIFIED"
            or census.get("productionPublication") != "BLOCKED"):
        raise ValueError("Source census is incomplete, stale or falsely certified")
    for key in ("fromGraphFingerprint", "toGraphFingerprint",
                "fromBoundaryFingerprint", "toBoundaryFingerprint"):
        if census.get(key) != pair[key]:
            raise ValueError("Graph or boundary fingerprint mismatch: " + key)
    results = {}
    for direction, scan, side in (
            ("from-to", from_scan, "from"), ("to-from", to_scan, "to")):
        edges = scan.get("edges")
        original = census.get("directions", {}).get(direction)
        if not isinstance(edges, list) or not isinstance(original, dict):
            raise ValueError("Missing full original native directed source evidence")
        counts = original.get("counts", {})
        if (original.get("edgeCoverage") != "ALL_SOURCE_NATIVE_SCAN_IDS_RECONCILED"
                or type(counts.get("nativeDirectedEdgesAudited")) is not int
                or counts["nativeDirectedEdgesAudited"] != len(edges)
                or not len(edges)):
            raise ValueError("Full native source-to-terminal coverage not established")
        original_by_id = {}
        for item in edges:
            gid = item.get("graphId")
            mask = item.get("forwardAccess")
            if (type(gid) is not int or gid <= 0 or gid in original_by_id
                    or type(mask) is not int or not 0 <= mask < 2**32
                    or type(item.get("wayId")) is not int
                    or item["wayId"] <= 0):
                raise ValueError("Duplicate or invalid original directed source GraphId")
            original_by_id[gid] = item
        candidates = {}
        mode_ids = {}
        original_terminals = original.get("allGraphLocalModeTerminals")
        if not isinstance(original_terminals, dict):
            raise ValueError("Original full-census terminal rows missing")
        for mode, bit in MODE_BITS.items():
            rows = original_terminals.get(mode)
            expected = counts.get(f"{mode}GraphLocalFinalDirectedEdges", 0)
            if (not isinstance(rows, list) or type(expected) is not int
                    or expected < 0 or len(rows) != expected):
                raise ValueError("Native directed terminal count disagreement")
            seen = set()
            for item in rows:
                gid = item.get("graphId")
                source = original_by_id.get(gid)
                if type(gid) is not int or gid in seen or source is None:
                    raise ValueError("Repeated terminal or terminal not in complete scan")
                seen.add(gid)
                if (item.get("terminalStatus") != "NATIVE_GRAPH_LOCAL_MODE_TERMINAL_ONLY"
                        or item.get("wayIdAnnotationOnly") != source["wayId"]
                        or type(item.get("endNodeGraphId")) is not int
                        or item["endNodeGraphId"] <= 0
                        or type(item.get("insidePeerBuffer")) is not bool
                        or not source["forwardAccess"] & bit):
                    raise ValueError("Original directed terminal identity or access mismatch")
                lat = _number(item.get("endLat"), 90)
                lon = _number(item.get("endLon"), 180)
                row = candidates.get(gid)
                if row is None:
                    row = {
                        "finalDirectedGraphId": gid,
                        "nativeEndNodeGraphId": item["endNodeGraphId"],
                        "nativeTerminal": {"lat": lat, "lng": lon},
                        # The original scanner has TWO different GPS
                        # concepts: lat/lon is the source NODE; innerLat/
                        # innerLon is the sample INSIDE the directed edge.
                        # Neither is the authoritative final endpoint.
                        "sourceStartNodeAnnotationOnly": {
                            "lat": _number(source.get("lat"), 90),
                            "lng": _number(source.get("lon"), 180)},
                        "sourceInteriorSampleAnnotationOnly": {
                            "lat": _number(source.get("innerLat"), 90),
                            "lng": _number(source.get("innerLon"), 180)},
                        "wayIdAnnotationOnly": source["wayId"],
                        "insidePeerBufferAnnotationOnly": item["insidePeerBuffer"],
                        "vehicleModes": [],
                        "physicalRoadDirectionClass": "NOT_YET_ESTABLISHED",
                        "finalPhysicalRoadEdgeUniqueness": "NOT_VERIFIED",
                        "candidateStatus": "ORIGINAL_NATIVE_GRAPH_LOCAL_TERMINAL_ONLY",
                        "candidateSuppressed": False,
                    }
                    candidates[gid] = row
                elif (row["nativeEndNodeGraphId"] != item["endNodeGraphId"]
                      or row["nativeTerminal"] != {"lat": lat, "lng": lon}
                      or row["insidePeerBufferAnnotationOnly"] != item["insidePeerBuffer"]):
                    raise ValueError("Two mode views disagree about one original final edge")
                row["vehicleModes"].append(mode)
            mode_ids[mode] = len(seen)
        stranded = {}
        for mode in MODE_BITS:
            count = counts.get(f"{mode}ModeStrandedNondeadend", 0)
            if type(count) is not int or not 0 <= count <= len(edges):
                raise ValueError("Invalid unresolved mode-stranded source count")
            stranded[mode] = count
        if any(x["candidateSuppressed"] for x in candidates.values()):
            raise ValueError("Native original candidate suppression is prohibited")
        results[direction] = {
            "originalRegion": pair[side + "RegionId"],
            "originalDirectedSourceCount": len(edges),
            "oneCandidateRecordPerOriginalDirectedGraphId": True,
            "uniqueOriginalTerminalCandidateGraphIds": len(candidates),
            "modeCounts": mode_ids,
            "unresolvedModeStrandedNondeadendCounts": stranded,
            "originalSourceIDsOutsideTerminalRegisterStillInFullScan": len(edges) - len(candidates),
            "terminalCandidates": [candidates[gid] for gid in sorted(candidates)],
            "physicalRoadDirectionEquivalence": "NOT_VERIFIED",
            "noRoadsOrBranchesDiscardedFromFullSourceScan": True,
        }
    return {
        "schema": SCHEMA, "version": 1, "pairId": pair["pairId"],
        "graphFingerprints": {"from": pair["fromGraphFingerprint"],
                              "to": pair["toGraphFingerprint"]},
        "boundaryFingerprints": {"from": pair["fromBoundaryFingerprint"],
                                 "to": pair["toBoundaryFingerprint"]},
        "directions": results,
        "model": "ONE_FINAL_DIRECTED_EDGE_PER_PHYSICAL_ROAD_DIRECTION",
        "roadDirectionClasses": "NOT_VERIFIED",
        "allPhysicalRoadsAndDirectionsExhausted": "NOT_VERIFIED",
        "androidSameGraphJNIParity": "NOT_VERIFIED",
        "crossGraphOriginalValhallaTransfer": "NOT_VERIFIED",
        "productionPublication": "BLOCKED",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ("pair", "census", "from-scan", "to-scan", "native-summary", "output"):
        ap.add_argument("--" + name, type=Path, required=True)
    for name in ("census", "from-scan", "to-scan", "native-summary"):
        ap.add_argument("--expected-" + name + "-sha256", required=True)
    args = ap.parse_args()
    if args.output.exists() or args.output.is_symlink():
        raise ValueError("Refusing to replace an immutable final-edge register")
    paths = {
        "pair": args.pair, "census": args.census, "fromScan": args.from_scan,
        "toScan": args.to_scan, "nativeSummary": args.native_summary,
    }
    hashes = {key: digest(path) for key, path in paths.items()}
    for name in ("census", "from-scan", "to-scan", "native-summary"):
        pinned(getattr(args, name.replace("-", "_")),
               getattr(args, "expected_" + name.replace("-", "_") + "_sha256"))
    pair, census = read(args.pair), read(args.census)
    a, b, provenance = source_scans(
        pair, from_scan=read(args.from_scan), to_scan=read(args.to_scan),
        scan_summary=read(args.native_summary))
    if (census.get("sourceScanSHA256") != {
            "from": hashes["fromScan"], "to": hashes["toScan"]}
            or census.get("sourceScanProvenance") != provenance
            or type(census.get("verifiedCompleteOverlapWindows")) is not int
            or census["verifiedCompleteOverlapWindows"] <= 0
            or any(len(s.get("windows", [])) != census["verifiedCompleteOverlapWindows"]
                   for s in (a, b))):
        raise ValueError("Original census SHA/window source scan binding changed")
    report = make_register(pair, census, a, b)
    report["immutableSourceSHA256"] = hashes
    if any(digest(path) != hashes[key] for key, path in paths.items()):
        raise ValueError("Original immutable input changed during register compilation")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    stage = None
    try:
        with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=args.output.parent, delete=False,
                prefix=".f8-final-edge-register-") as stream:
            stage = Path(stream.name)
            json.dump(report, stream, indent=2, allow_nan=False)
            stream.write("\n")
        if args.output.exists() or args.output.is_symlink():
            raise ValueError("Refusing to overwrite a concurrent immutable output")
        os.link(stage, args.output)
    finally:
        if stage is not None:
            stage.unlink(missing_ok=True)
    print("One native directed-edge record per GraphId; physical-road uniqueness",
          "NOT_VERIFIED, publication BLOCKED.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        raise SystemExit("F8_FINAL_EDGE_REGISTER_ERROR: " + str(exc)[:350])
