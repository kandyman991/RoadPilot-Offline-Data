#!/usr/bin/env python3
"""Verify exact graph-local receiver-node adjacency without claiming a F8 handoff.

Input is a diagnostic-only receiver proximity catalog plus native GraphReader
outgoing-edge captures. All graph-local IDs, directions, ambiguities and
unresolved cases are preserved. No publication, route proof or pruning.
"""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import sys

from audit_native_f8_terminal_evidence import load_jsonl

SCHEMA = "roadpilot.native-f8-receiver-adjacency-audit"
MOTORCYCLE_ACCESS = 1024  # Valhalla 3.6.3 graphconstants.h
AUTO_ACCESS = 1


def candidates(observations: list[dict]) -> dict[int, dict]:
    expected = {}
    for obs in observations:
        for row in obs["nearbyReceiverIncoming"]:
            if not (row["sameWay"] and not row["receiverDeadend"]):
                continue
            graph_id = row["receiverDirectedGraphId"]
            reference = {
                "endNodeGraphId": row["receiverEndNodeGraphId"],
                "wayId": row["receiverWayId"],
                "forwardAccess": row["receiverForwardAccess"],
            }
            previous = expected.setdefault(graph_id, reference)
            if previous != reference:
                raise ValueError("Same receiver GraphId has conflicting physical evidence")
    return expected


def validate_capture(observations: list[dict], rows: list[dict]) -> dict[int, dict]:
    required = candidates(observations)
    captured = {}
    for row in rows:
        graph_id = row.get("sourceGraphId")
        if type(graph_id) is not int or graph_id not in required:
            raise ValueError("Unknown receiver incoming GraphId in native adjacency capture")
        if graph_id in captured:
            raise ValueError("Repeated native receiver incoming GraphId")
        if any(row.get(field) != expected for field, expected in required[graph_id].items()):
            raise ValueError(f"Receiver incoming native identity mismatch: {graph_id}")
        if row.get("deadend") is not False:
            raise ValueError("Native receiver continuation became a dead-end")
        reverse = row.get("opposingGraphId")
        if type(reverse) is not int or reverse <= 0:
            raise ValueError("Missing native opposing directed GraphId")
        edges = row.get("outgoingDirectedEdges")
        if not isinstance(edges, list) or not edges:
            raise ValueError("Native receiver end node has no outgoing edges")
        ids = set()
        for edge in edges:
            if not isinstance(edge, dict):
                raise ValueError("Invalid native outgoing directed edge")
            eid = edge.get("graphId")
            if type(eid) is not int or eid <= 0 or eid in ids:
                raise ValueError("Repeated or invalid outgoing directed GraphId")
            ids.add(eid)
            if type(edge.get("endNodeGraphId")) is not int or edge["endNodeGraphId"] <= 0:
                raise ValueError("Outgoing directed end-node GraphId missing")
            mask = edge.get("forwardAccess")
            if type(mask) is not int or not (0 <= mask < 2**32):
                raise ValueError("Invalid outgoing access mask")
            for field in ("isRoad", "isShortcut", "motorcycleBit", "autoBit"):
                if type(edge.get(field)) is not bool:
                    raise ValueError(f"Invalid outgoing {field}")
            if edge["motorcycleBit"] != bool(mask & MOTORCYCLE_ACCESS):
                raise ValueError("Motorcycle access flag disagrees with native mask")
            if edge["autoBit"] != bool(mask & AUTO_ACCESS):
                raise ValueError("Car access flag disagrees with native mask")
        if reverse not in ids:
            raise ValueError("Opposing edge is not an outgoing neighbour of receiver end node")
        captured[graph_id] = row
    if set(captured) != set(required):
        raise ValueError(f"Incomplete receiver-node adjacency capture: expected {len(required)}, got {len(captured)}")
    return captured


def inspect_direction(observations: list[dict], capture: dict[int, dict]) -> dict:
    counts: Counter = Counter()
    for obs in observations:
        counts["sourceDeadEndsAudited"] += 1
        matches = [r for r in obs["nearbyReceiverIncoming"]
                   if r["sameWay"] and not r["receiverDeadend"]]
        if not matches:
            counts["sourceWithoutProvisionalReceiverIncoming"] += 1
            continue
        counts["sourceWithProvisionalReceiverIncoming"] += 1
        modes_found = {"motorcycle": False, "auto": False}
        for match in matches:
            counts["receiverIncomingProvisionalRelationships"] += 1
            entry = capture[match["receiverDirectedGraphId"]]
            reverse = entry["opposingGraphId"]
            outgoing = [edge for edge in entry["outgoingDirectedEdges"]
                        if edge["graphId"] != reverse and edge["isRoad"]
                        and not edge["isShortcut"]]
            counts["nonOpposingOutgoingRoadOccurrences"] += len(outgoing)
            for mode, mask, flag in (
                ("motorcycle", MOTORCYCLE_ACCESS, "motorcycleBit"),
                ("auto", AUTO_ACCESS, "autoBit"),
            ):
                if not (obs["sourceForwardAccess"] & mask
                        and match["receiverForwardAccess"] & mask):
                    continue
                if any(edge[flag] for edge in outgoing):
                    modes_found[mode] = True
                    counts[f"{mode}ProvisionalIncomingWithForwardAccess"] += 1
        for mode, found in modes_found.items():
            counts[f"sourceWith{mode.title()}StructuralContinuation" if found
                   else f"sourceWithout{mode.title()}StructuralContinuation"] += 1
        if all(modes_found.values()):
            counts["sourceWithBothModeStructuralContinuation"] += 1
    return {
        "counts": dict(sorted(counts.items())),
        "receiverIdentityCoverage": "EXACT_NATIVE_GRAPH_LOCAL_DIRECTED_IDS_ONLY",
        "modeEvidence": "ACCESS_BITS_AND_NON_OPPOSING_NODE_ADJACENCY_ONLY",
        "turnRestrictionsValidated": False,
        "valhallaRouteLegs": "NOT_RUN",
        "allRelevantAlternativesExhausted": False,
    }


def hash_file(path: Path) -> str:
    h = sha256()
    with path.open("rb") as file:
        while chunk := file.read(1048576):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receiver-audit", type=Path, required=True)
    parser.add_argument("--italy-native-adjacency", type=Path, required=True)
    parser.add_argument("--austria-native-adjacency", type=Path, required=True)
    args = parser.parse_args()
    audit = json.loads(args.receiver_audit.read_text(encoding="utf-8"))
    if (audit.get("schema") != "roadpilot.native-f8-receiver-topology-audit" or
            audit.get("state") != "INCOMPLETE" or
            audit.get("androidParity") != "NOT_VERIFIED" or
            audit.get("productionPublication") != "BLOCKED"):
        raise ValueError("Only incomplete, unpublished Graph Studio receiver audits are accepted")
    forward_obs = audit["fromTo"]["observations"]
    reverse_obs = audit["toFrom"]["observations"]
    austria = validate_capture(forward_obs, load_jsonl(args.austria_native_adjacency))
    italy = validate_capture(reverse_obs, load_jsonl(args.italy_native_adjacency))
    output = {
        "schema": SCHEMA, "version": 0, "pairId": audit["pairId"],
        "graphFingerprints": audit["graphFingerprints"],
        "inputSha256": {
            "receiverAudit": hash_file(args.receiver_audit),
            "italyAdjacency": hash_file(args.italy_native_adjacency),
            "austriaAdjacency": hash_file(args.austria_native_adjacency),
        },
        "status": "INCOMPLETE",
        "productionPublication": "BLOCKED",
        "f8GraphEdgeParity": "NOT_VERIFIED",
        "fullJourneyOptimality": "NOT_RUN",
        "fromTo": inspect_direction(forward_obs, austria),
        "toFrom": inspect_direction(reverse_obs, italy),
    }
    print(json.dumps(output, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print(f"F8_ADJACENCY_AUDIT_ERROR: {exc}", file=sys.stderr)
        sys.exit(2)
