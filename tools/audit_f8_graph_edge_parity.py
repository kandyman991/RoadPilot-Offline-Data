#!/usr/bin/env python3
"""Read-only F8 directed graph-edge coverage audit for exact retained graph pairs.

This compares a capture from RoadPilot's *native* edge scanner with Graph Studio's
correlations and crossing candidates. It never calls OSM-only evidence "F8 parity",
never edits graphs or existing artifacts, and never treats one successful handoff
as proof that other directed alternatives are absent.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SCHEMA = "roadpilot.f8-graph-edge-audit"
REFERENCE_SCHEMA = "roadpilot.native-f8-edge-scan"
SIDES = ("from", "to")
# RoadPilot native/on-device-valhalla/builder_jni.cpp::scan_boundary_road_edges
# clamps the caller's maxResults to 512, even when Android asks for 4096.
NATIVE_F8_MAX_RESULTS_PER_WINDOW = 512


def obj(value: Any, where: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{where} must be an object")
    return value


def items(value: Any, where: str) -> list:
    if not isinstance(value, list):
        raise ValueError(f"{where} must be an array")
    return value


def edge_id(value: Any, where: str) -> str:
    # Preserve the native GraphId; NEVER collapse by OSM way, name or location.
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError(f"{where}: graphId must be a nonempty integer/string")
    result = str(value).strip()
    if not result or result == "0" or (result.startswith("-") and result[1:].isdigit()):
        raise ValueError(f"{where}: invalid graphId")
    return result


def read(path: Path) -> dict:
    return obj(json.loads(path.read_text(encoding="utf-8")), str(path))


def identities(data: dict) -> tuple[str, str, str, str, str]:
    return (
        data.get("pairId"),
        obj(data.get("fromGraph"), "fromGraph").get("graphFingerprint"),
        obj(data.get("toGraph"), "toGraph").get("graphFingerprint"),
        data.get("fromBoundaryFingerprint"),
        data.get("toBoundaryFingerprint"),
    )


def audit(reference: dict, correlations: dict, candidates: dict) -> dict:
    if reference.get("schema") != REFERENCE_SCHEMA or reference.get("version") != 1:
        raise ValueError("Native F8 capture schema/version unsupported")
    if reference.get("scanner") != "GraphEndpointNative.scanBoundaryRoadEdges":
        raise ValueError("Capture is not identified as the native F8 graph-edge scanner")
    if correlations.get("schema") != "roadpilot.frontier-road-correlations":
        raise ValueError("Invalid Graph Studio correlations input")
    if candidates.get("schema") != "roadpilot.crossing-candidates":
        raise ValueError("Invalid Graph Studio candidate input")
    ids = identities(correlations)
    if identities(reference) != ids or identities(candidates) != ids:
        raise ValueError("Graph/boundary fingerprints or pair identity disagree")
    if not all(isinstance(x, str) and x for x in ids):
        raise ValueError("Graph/boundary identities must be nonempty")

    scans = obj(reference.get("scans"), "scans")
    correlated = {side: set() for side in SIDES}
    for index, row in enumerate(items(correlations.get("correlations"), "correlations")):
        row = obj(row, f"correlations[{index}]")
        for side in SIDES:
            block = obj(row.get(side + "Graph"), f"correlation {index}.{side}Graph")
            for edge in items(block.get("candidates"), f"correlation {index}.{side}.candidates"):
                edge = obj(edge, "correlated edge")
                if edge.get("graphId") is not None:
                    correlated[side].add(edge_id(edge["graphId"], "correlated edge"))

    candidate_ids = {side: set() for side in SIDES}
    known_pairs = set()
    unknown_candidate_graph_ids = 0
    for index, row in enumerate(items(candidates.get("candidates"), "candidates")):
        row = obj(row, f"candidate[{index}]")
        raw_a = obj(row.get("fromEdge"), "candidate.fromEdge").get("graphId")
        raw_b = obj(row.get("toEdge"), "candidate.toEdge").get("graphId")
        if raw_a is None or raw_b is None:
            # Valhalla locate may return candidates without exact directed IDs.
            # They cannot prove native F8 equivalence; retain an explicit gap.
            unknown_candidate_graph_ids += 1
            continue
        a = edge_id(raw_a, "candidate.fromEdge")
        b = edge_id(raw_b, "candidate.toEdge")
        candidate_ids["from"].add(a)
        candidate_ids["to"].add(b)
        known_pairs.add((a, b))

    report_sides = {}
    incomplete_reasons = []
    if unknown_candidate_graph_ids:
        incomplete_reasons.append("Graph Studio candidates lacking exact directed graph IDs")
    missing_count = 0
    native_ids = {}
    for side in SIDES:
        scan = obj(scans.get(side), f"scans.{side}")
        edges = items(scan.get("edges"), f"scans.{side}.edges")
        windows = items(scan.get("windows"), f"scans.{side}.windows")
        observed = set()
        for i, row in enumerate(edges):
            observed.add(edge_id(obj(row, f"{side}.edges[{i}]").get("graphId"), "native edge"))
        if not windows or scan.get("complete") is not True:
            incomplete_reasons.append(f"{side}: no demonstrated complete scan")
        for i, window in enumerate(windows):
            window = obj(window, f"{side}.windows[{i}]")
            requested = window.get("maxResults")
            returned = window.get("returned")
            if isinstance(requested, bool) or not isinstance(requested, int) or requested <= 0:
                incomplete_reasons.append(f"{side}: scan window {i} missing valid requested limit")
                continue
            actual_limit = min(requested, NATIVE_F8_MAX_RESULTS_PER_WINDOW)
            # The JNI scanner silently clamps to 512; a request for 4096
            # returning exactly 512 cannot be declared complete.
            if (isinstance(returned, bool) or not isinstance(returned, int)
                    or returned < 0 or returned > actual_limit):
                incomplete_reasons.append(f"{side}: scan window {i} invalid returned count")
                continue
            if (window.get("complete") is not True or
                    window.get("truncated") is not False or returned >= actual_limit):
                incomplete_reasons.append(
                    f"{side}: scan window {i} not proven complete "
                    f"(requested={requested}, actualNativeCap={actual_limit}, returned={returned})"
                )
        native_ids[side] = observed
        missing_correlation = sorted(observed - correlated[side])
        missing_candidates = sorted(observed - candidate_ids[side])
        missing_count += len(missing_correlation) + len(missing_candidates)
        report_sides[side] = {
            "nativeDistinctDirectedEdges": len(observed),
            "correlatedDistinctDirectedEdges": len(correlated[side]),
            "candidateDistinctDirectedEdges": len(candidate_ids[side]),
            "nativeEdgesMissingFromCorrelations": missing_correlation,
            "nativeEdgesMissingFromCandidates": missing_candidates,
        }

    proven = items(reference.get("provenHandoffs", []), "provenHandoffs")
    absent_pairs = []
    for i, row in enumerate(proven):
        row = obj(row, f"provenHandoffs[{i}]")
        pair = (edge_id(row.get("fromGraphId"), "handoff.fromGraphId"),
                edge_id(row.get("toGraphId"), "handoff.toGraphId"))
        if pair[0] not in native_ids["from"] or pair[1] not in native_ids["to"]:
            incomplete_reasons.append(f"proven handoff {i} not present in native edge scan")
        if row.get("mode") not in ("motorcycle", "auto") or row.get("direction") not in ("from-to", "to-from"):
            incomplete_reasons.append(f"proven handoff {i} missing valid mode/direction")
        if pair not in known_pairs:
            absent_pairs.append({
                "fromGraphId": pair[0],
                "toGraphId": pair[1],
                "mode": row.get("mode"),
                "direction": row.get("direction"),
            })
    missing_count += len(absent_pairs)
    if not proven:
        incomplete_reasons.append("no F8-proven handoff pairs supplied")
    if missing_count:
        incomplete_reasons.append("native F8 candidates or proven alternatives are missing")

    # Even a clean *sample* cannot establish full buffer/window coverage,
    # mode-specific Valhalla proof or route-time optimality.
    return {
        "schema": SCHEMA,
        "version": 1,
        "pairId": ids[0],
        "fromGraphFingerprint": ids[1],
        "toGraphFingerprint": ids[2],
        "fromBoundaryFingerprint": ids[3],
        "toBoundaryFingerprint": ids[4],
        "sides": report_sides,
        "nativeProvenHandoffCount": len(proven),
        "nativeScannerHardCapPerWindow": NATIVE_F8_MAX_RESULTS_PER_WINDOW,
        "graphStudioCandidatePairsWithoutExactIds": unknown_candidate_graph_ids,
        "nativeProvenHandoffsMissingFromCandidates": absent_pairs,
        "scanStatus": "INCOMPLETE" if incomplete_reasons else "OBSERVED_WINDOWS_COMPARED",
        "incompleteReasons": sorted(set(incomplete_reasons)),
        "f8GraphEdgeParity": "NOT_VERIFIED",
        "note": "Matching observed native edges is not an exhaustive graph-frontier parity proof.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-scan", required=True, type=Path)
    parser.add_argument("--correlations", required=True, type=Path)
    parser.add_argument("--candidates", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = audit(read(args.native_scan), read(args.correlations), read(args.candidates))
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error(str(error))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{result['pairId']}: {result['scanStatus']} / F8 parity NOT_VERIFIED")
    print("Missing native edges/candidate pairs:", sum(
        len(side["nativeEdgesMissingFromCandidates"]) for side in result["sides"].values()
    ) + len(result["nativeProvenHandoffsMissingFromCandidates"]))
    # Nonzero if incomplete evidence or missing candidates: safe for strict acceptance pipelines.
    return 0 if result["scanStatus"] == "OBSERVED_WINDOWS_COMPARED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
