#!/usr/bin/env python3
"""Audit receiver-directed native endpoints for D-017; NOT a handoff producer.

Nearby receiver incoming edges remain *observations*, not graph handoffs.
Road names and OSM way IDs are diagnostic annotations, never a pre-Valhalla
rejection rule. All source dead ends receive a complete classification.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
import math
from pathlib import Path
import sys

from audit_native_f8_terminal_evidence import (
    load_jsonl, native_endpoints_to_observations
)
from build_native_f8_pair_evidence import pair_identity, source_scans

SCHEMA = "roadpilot.native-f8-receiver-topology-audit"
TOLERANCE_METRES = 8.0
GRID_DEGREES = 0.0001
CLASSIFY_EXACT_METRES = 0.25  # Annotation only. Does not exclude candidates.


def metres(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    mid = math.radians((lat1 + lat2) / 2)
    return 111320.0 * math.hypot(lat2 - lat1, (lon2 - lon1) * math.cos(mid))


def make_receiver_index(receiver_rows: dict[int, dict]) -> dict:
    grid: dict[tuple[int, int], list[tuple[int, dict]]] = defaultdict(list)
    for graph_id, row in receiver_rows.items():
        key = (math.floor(row["endLat"] / GRID_DEGREES),
               math.floor(row["endLon"] / GRID_DEGREES))
        grid[key].append((graph_id, row))
    return grid


def incoming_near(
    grid: dict, lat: float, lon: float, *, tolerance_metres: float = TOLERANCE_METRES
) -> list[tuple[float, int, dict]]:
    # This observational search is deliberately bounded to Alps-scale latitudes.
    # Out-of-domain inputs fail rather than returning an incomplete empty set.
    if not (abs(lat) <= 80.0 and -180 <= lon <= 180):
        raise ValueError("Receiver proximity audit is not defined near the poles")
    latitude_cells = math.ceil(tolerance_metres / (111320 * GRID_DEGREES)) + 1
    longitude_cells = math.ceil(
        tolerance_metres / (111320 * GRID_DEGREES * math.cos(math.radians(abs(lat) + .001)))
    ) + 1
    x = math.floor(lat / GRID_DEGREES)
    y = math.floor(lon / GRID_DEGREES)
    found = []
    for i in range(x - latitude_cells, x + latitude_cells + 1):
        for j in range(y - longitude_cells, y + longitude_cells + 1):
            for graph_id, row in grid.get((i, j), ()):
                distance = metres(lat, lon, row["endLat"], row["endLon"])
                if distance <= tolerance_metres:
                    found.append((distance, graph_id, row))
    return sorted(found, key=lambda t: (t[0], t[1]))


def audit_direction(
    source_edges: list[dict], source_end_rows: list[dict],
    receiver_edges: list[dict], receiver_end_rows: list[dict],
    *, include_observations: bool = False
) -> dict:
    """Never claim completeness; preserve every candidate source GraphId."""
    source = {edge["graphId"]: edge for edge in source_edges}
    receiver = {edge["graphId"]: edge for edge in receiver_edges}
    src_end = {row["sourceGraphId"]: row for row in source_end_rows}
    recv_end = {row["sourceGraphId"]: row for row in receiver_end_rows}
    if (len(source) != len(source_edges) or len(receiver) != len(receiver_edges)
        or len(src_end) != len(source) or len(recv_end) != len(receiver)):
        raise ValueError("Directed edge/endpoint inventory is incomplete or duplicated")
    if set(src_end) != set(source) or set(recv_end) != set(receiver):
        raise ValueError("Directed edge/endpoint identity mismatch")

    grid = make_receiver_index(recv_end)
    counts: Counter = Counter()
    observations: list[dict] = []
    for graph_id, edge in sorted(source.items()):
        end = src_end[graph_id]
        if not end["deadend"]:
            continue
        counts["sourceNativeDeadends"] += 1
        nearby = incoming_near(grid, end["endLat"], end["endLon"])
        same_way = [(distance, peer_id, peer) for distance, peer_id, peer in nearby
                    if receiver[peer_id]["wayId"] == edge["wayId"]]
        continuing = [(distance, peer_id, peer) for distance, peer_id, peer in same_way
                      if not peer["deadend"]]
        counts["nearbyReceiverIncomingOccurrences"] += len(nearby)
        counts["sameWayIncomingOccurrences"] += len(same_way)
        counts["continuingSameWayIncomingOccurrences"] += len(continuing)
        if nearby:
            counts["sourceWithNearbyReceiverIncoming"] += 1
        if same_way:
            counts["sourceWithSameWayIncoming"] += 1
        if continuing:
            counts["sourceWithProvisionalReceiverContinuation"] += 1
            if len(continuing) > 1:
                counts["sourceWithAmbiguousMultipleContinuations"] += 1
            if any(distance <= CLASSIFY_EXACT_METRES for distance, _, _ in continuing):
                counts["sourceWithSubmetreColocatedContinuation"] += 1
            status = "PROVISIONAL_SAME_WAY_NON_DEADEND_RECEIVER"
        elif same_way:
            counts["sourceWithOnlyDeadEndReceiverIncoming"] += 1
            status = "UNRESOLVED_RECEIVER_ALSO_DEADEND"
        elif nearby:
            counts["sourceWithOnlyDifferentWayReceiverIncoming"] += 1
            status = "UNRESOLVED_DIFFERENT_WAY_NEARBY"
        else:
            counts["sourceWithNoNearbyReceiverIncoming"] += 1
            status = "UNRESOLVED_NO_NEARBY_RECEIVER_INCOMING"

        if include_observations:
            observations.append({
                "sourceDirectedGraphId": graph_id,
                "sourceEndNodeGraphId": end["endNodeGraphId"],
                "sourceEnd": [end["endLat"], end["endLon"]],
                "sourceWayId": edge["wayId"],
                "sourceForwardAccess": edge["forwardAccess"],
                "status": status,
                "nearbyReceiverIncoming": [
                    {"receiverDirectedGraphId": peer_id,
                     "receiverEndNodeGraphId": peer["endNodeGraphId"],
                     "receiverWayId": receiver[peer_id]["wayId"],
                     "receiverForwardAccess": receiver[peer_id]["forwardAccess"],
                     "receiverDeadend": peer["deadend"],
                     "sameWay": receiver[peer_id]["wayId"] == edge["wayId"],
                     "distanceMetres": round(distance, 4)}
                    for distance, peer_id, peer in nearby
                ],
            })

    return {
        "classification": dict(sorted(counts.items())),
        "sourceDirectedEdgeTotal": len(source),
        "receiverDirectedEdgeTotal": len(receiver),
        "evidence": "EXACT_GRAPH_LOCAL_ENDPOINTS_WITH_OBSERVATIONAL_SPATIAL_CORRELATION",
        "receiverContinuation": "PROVISIONAL_NOT_VALHALLA_PROVEN",
        "coverageClaim": "NOT_VERIFIED",
        **({"observations": observations} if include_observations else {}),
    }


def read_bytes_sha(path: Path) -> str:
    h = sha256()
    with path.open("rb") as file:
        while chunk := file.read(1024 * 1024):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def atomic_new_json(path: Path, doc: dict) -> None:
    # Explicit opt-in scratch evidence output; no overwrite or publication.
    import os
    import tempfile
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                     prefix=".native-f8-incomplete-", delete=False) as file:
        tmp = Path(file.name)
        json.dump(doc, file, separators=(",", ":"), allow_nan=False)
        file.write("\n")
    try:
        os.link(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("pair", "from-scan", "to-scan", "scan-summary",
                 "from-native-endpoints", "to-native-endpoints"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--observations-output", type=Path,
                        help="Optional NEW scratch file; refuses to overwrite existing evidence")
    args = parser.parse_args()

    pair = json.loads(args.pair.read_text(encoding="utf-8"))
    pair_identity(pair)
    scans = (json.loads(args.from_scan.read_text(encoding="utf-8")),
             json.loads(args.to_scan.read_text(encoding="utf-8")))
    from_scan, to_scan, provenance = source_scans(
        pair, from_scan=scans[0], to_scan=scans[1],
        scan_summary=json.loads(args.scan_summary.read_text(encoding="utf-8")))
    from_end = load_jsonl(args.from_native_endpoints)
    to_end = load_jsonl(args.to_native_endpoints)
    # Fail closed on missing endpoints and disagreement with source scan
    # way identity/access, not merely coincident numeric GraphIds.
    native_endpoints_to_observations(from_scan["edges"], from_end, "from")
    native_endpoints_to_observations(to_scan["edges"], to_end, "to")

    details = bool(args.observations_output)
    forward = audit_direction(from_scan["edges"], from_end,
                              to_scan["edges"], to_end, include_observations=details)
    reverse = audit_direction(to_scan["edges"], to_end,
                              from_scan["edges"], from_end, include_observations=details)
    sources = {
        "pair": args.pair,
        "fromScan": args.from_scan, "toScan": args.to_scan,
        "scanSummary": args.scan_summary,
        "fromNativeEndpoints": args.from_native_endpoints,
        "toNativeEndpoints": args.to_native_endpoints,
    }
    report = {
        "schema": SCHEMA, "version": 0, "pairId": pair["pairId"],
        "graphFingerprints": {
            "from": pair["fromGraphFingerprint"], "to": pair["toGraphFingerprint"]},
        "inputFileSha256": {role: read_bytes_sha(path) for role, path in sources.items()},
        "sourceBinding": provenance["sourceBindingLevel"],
        "coordinateToleranceMetres": TOLERANCE_METRES,
        "state": "INCOMPLETE",
        "exactReceivingGraphTopology": "NOT_VERIFIED",
        "modeSpecificValhallaLegs": "NOT_RUN",
        "androidParity": "NOT_VERIFIED",
        "productionPublication": "BLOCKED",
        "limits": [
            "Spatially coincident incoming receiver endpoints are not exact directed route continuity.",
            "Same OSM way is diagnostic evidence only: alternatives from other ways are not rejected.",
            "Source dead-end hypothesis is not a proof of exhaustive cross-graph transitions.",
            "Native extract and source historical scans are not independently archive-hash-attested.",
        ],
        "fromTo": forward, "toFrom": reverse,
    }
    if details:
        atomic_new_json(args.observations_output, report)
    for item in (forward, reverse):
        item.pop("observations", None)
    print(json.dumps(report, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, KeyError, ValueError, TypeError) as exc:
        print(f"NATIVE_F8_RECEIVER_AUDIT_ERROR: {exc}", file=sys.stderr)
        sys.exit(2)
