#!/usr/bin/env python3
"""Read-only S1 diagnostic: audit provisional terminal-edge hypotheses.

This is NOT an F8-native handoff producer. It consumes independently captured
GraphReader inventory and Valhalla locate observations; neither an 8 m spatial
match nor a 'deadend' flag proves exact, directed graph continuity. Incomplete
observations and unknown receiver GraphIds remain explicit.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

from build_native_f8_pair_evidence import pair_identity, source_scans

SCHEMA = "roadpilot.f8-terminal-evidence-audit"
VERSION = 0


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                raise ValueError(f"{path.name}:{line_number}: empty evidence row")
            try:
                row = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"{path.name}:{line_number}: malformed JSON") from error
            if not isinstance(row, dict):
                raise ValueError(f"{path.name}:{line_number}: expected object")
            rows.append(row)
    return rows


def keyed_rows(rows: list[dict], valid_ids: set[int], label: str) -> dict[int, dict]:
    out = {}
    for row in rows:
        key = row.get("g")
        if type(key) is not int or key not in valid_ids:
            raise ValueError(f"{label}: unknown/non-integer directed GraphId")
        if key in out:
            raise ValueError(f"{label}: duplicate directed GraphId {key}")
        out[key] = row
    return out


def audit_side(edges: list[dict], ends: list[dict], probes: list[dict],
               side: str, *, include_candidates: bool = False) -> dict:
    """Classify evidence, never infer proof from road name or approximate location."""
    ids = {e["graphId"] for e in edges}
    if len(ids) != len(edges):
        raise ValueError(f"{side}: duplicate scan graph IDs")
    end_index = keyed_rows(ends, ids, f"{side} endpoints")
    probe_index = keyed_rows(probes, ids, f"{side} neighbour probes")
    expected_probes = set()

    for graph_id, row in end_index.items():
        if type(row.get("id")) is not bool:
            raise ValueError(f"{side}: invalid endpoint match flag")
        if row["id"]:
            point = row.get("e")
            if (not isinstance(point, list) or len(point) != 2 or
                any(type(v) not in (int, float) or not math.isfinite(v)
                    for v in point) or abs(point[0]) > 90 or abs(point[1]) > 180):
                raise ValueError(f"{side}: invalid directed endpoint coordinates")
            if type(row.get("d")) is not bool:
                raise ValueError(f"{side}: invalid directed dead-end flag")
            if row["d"]:
                expected_probes.add(graph_id)

    for graph_id, row in probe_index.items():
        if graph_id not in expected_probes:
            raise ValueError(f"{side}: neighbour probe does not correspond to a confirmed local dead-end")
        if type(row.get("found")) is not bool or type(row.get("cont")) is not bool:
            raise ValueError(f"{side}: malformed neighbour observation")
        if row["cont"] and not row["found"]:
            raise ValueError(f"{side}: neighbour continuation without neighbour match")

    successes = sorted(graph_id for graph_id, row in probe_index.items() if row["cont"])
    unresolved_source = len(ids - end_index.keys()) + sum(
        not row["id"] for row in end_index.values())
    unresolved_deadends = len(expected_probes - probe_index.keys())
    no_neighbour = sum(not row["found"] for row in probe_index.values())
    neighbour_stops = sum(row["found"] and not row["cont"] for row in probe_index.values())
    result = {
        "sourceSide": side,
        "directedEdges": len(edges),
        "endpointObservations": len(end_index),
        "endpointMatched": len(end_index) - sum(not row["id"] for row in end_index.values()),
        "unresolvedEndpoints": unresolved_source,
        "deadEndObservations": len(expected_probes),
        "neighbourProbes": len(probe_index),
        "unresolvedDeadEndProbes": unresolved_deadends,
        "noNeighbourMatchWithinTolerance": no_neighbour,
        "neighbourAlsoStops": neighbour_stops,
        "provisionalTerminalEdges": len(successes),
        "terminalCompleteness": "NOT_VERIFIED",
        "exactDirectedReceiverMatch": "NOT_RUN",
        "vehicleValhallaLegProof": "NOT_RUN",
    }
    if include_candidates:
        lookup = {e["graphId"]: e for e in edges}
        result["candidates"] = [
            {"sourceGraphId": graph_id,
             "sourceWayId": lookup[graph_id]["wayId"],
             "sourceDirectedEndpoint": end_index[graph_id]["e"],
             "receiverGraphId": None,
             "evidence": "APPROXIMATE_SPATIAL_CONTINUATION_ONLY"}
            for graph_id in successes
        ]
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pair", type=Path, required=True)
    parser.add_argument("--from-scan", type=Path, required=True)
    parser.add_argument("--to-scan", type=Path, required=True)
    parser.add_argument("--scan-summary", type=Path, required=True)
    parser.add_argument("--from-ends", type=Path, required=True)
    parser.add_argument("--to-ends", type=Path, required=True)
    parser.add_argument("--from-neighbour-probes", type=Path, required=True)
    parser.add_argument("--to-neighbour-probes", type=Path, required=True)
    parser.add_argument("--include-candidates", action="store_true")
    args = parser.parse_args()

    pair = json.loads(args.pair.read_text(encoding="utf-8"))
    pair_identity(pair)
    from_scan, to_scan, provenance = source_scans(
        pair, from_scan=json.loads(args.from_scan.read_text(encoding="utf-8")),
        to_scan=json.loads(args.to_scan.read_text(encoding="utf-8")),
        scan_summary=json.loads(args.scan_summary.read_text(encoding="utf-8")))
    from_side = audit_side(from_scan["edges"], load_jsonl(args.from_ends),
                           load_jsonl(args.from_neighbour_probes), "from",
                           include_candidates=args.include_candidates)
    to_side = audit_side(to_scan["edges"], load_jsonl(args.to_ends),
                         load_jsonl(args.to_neighbour_probes), "to",
                         include_candidates=args.include_candidates)
    report = {
        "schema": SCHEMA, "version": VERSION, "pairId": pair["pairId"],
        "graphFingerprints": {"from": pair["fromGraphFingerprint"],
                              "to": pair["toGraphFingerprint"]},
        "sourceBinding": provenance["sourceBindingLevel"],
        "endpointObservationBinding": "UNBOUND_S1_SCRATCH_LOGS",
        "spatialMatchToleranceMetres": 8,
        "source": "S1_RETROACTIVE_VALHALLA_LOCATE_OBSERVATIONS",
        "status": "INCOMPLETE",
        "reason": "8m locate matches are not exact directed cross-graph continuity proofs; "
                  "unmatched scanner edges and endpoint probes must be resolved.",
        "from": from_side, "to": to_side,
        "androidF8Parity": "NOT_VERIFIED",
        "productionPublication": "BLOCKED",
    }
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, KeyError, OSError, TypeError) as error:
        print(f"F8_TERMINAL_AUDIT_ERROR: {error}", file=sys.stderr)
        sys.exit(2)
