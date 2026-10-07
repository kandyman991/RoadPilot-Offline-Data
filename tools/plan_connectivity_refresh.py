#!/usr/bin/env python3
"""Plan surgical refreshes for fingerprint-bound RoadPilot runtime connectivity."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SCHEMA = "roadpilot.connectivity-refresh-plan"
VERSION = 1
GENERATOR_NAME = "roadpilot-connectivity-refresh-planner"
GENERATOR_VERSION = "1"


def fail(message: str) -> None:
    raise SystemExit(message)


def load(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"Could not read {label} {path}: {exc}")
    if not isinstance(value, dict):
        fail(f"{label} must be a JSON object")
    return value


def manifest_identity(value: dict[str, Any], label: str) -> dict[str, Any]:
    if value.get("schema") != "roadpilot-routing-pack" or value.get("schemaVersion") != 1:
        fail(f"{label}: unsupported routing manifest")
    region = str(value.get("regionId") or "")
    graph = str(value.get("graphFingerprint") or "")
    source = value.get("source")
    graph_index = value.get("graphIndex")
    if not region or not graph:
        fail(f"{label}: regionId/graphFingerprint required")
    if not isinstance(source, dict) or not isinstance(graph_index, dict):
        fail(f"{label}: source/graphIndex required")
    primary = str(source.get("primaryGeofabrikId") or "")
    boundaries = graph_index.get("boundaryFingerprints")
    if not primary or not isinstance(boundaries, dict):
        fail(f"{label}: primaryGeofabrikId/boundaryFingerprints required")
    return {
        "regionId": region,
        "graphFingerprint": graph,
        "primaryGeofabrikId": primary,
        "boundaryFingerprints": {
            str(key): str(value)
            for key, value in boundaries.items()
            if isinstance(key, str) and isinstance(value, str)
        },
    }


def runtime_pair(value: dict[str, Any], label: str) -> dict[str, Any]:
    if value.get("schema") != "roadpilot.runtime-connectivity" or value.get("version") != 1:
        fail(f"{label}: unsupported runtime connectivity artifact")
    if value.get("validationState") != "VALIDATED":
        fail(f"{label}: runtime connectivity must be VALIDATED")
    pair_id = str(value.get("pairId") or "")
    from_region = str(value.get("fromRegionId") or "")
    to_region = str(value.get("toRegionId") or "")
    if pair_id != f"{from_region}__{to_region}" or not from_region or not to_region:
        fail(f"{label}: invalid pair identity")
    from_graph = value.get("fromGraph")
    to_graph = value.get("toGraph")
    if not isinstance(from_graph, dict) or not isinstance(to_graph, dict):
        fail(f"{label}: fromGraph/toGraph required")
    return {
        "pairId": pair_id,
        "fromRegionId": from_region,
        "toRegionId": to_region,
        "fromGraph": from_graph,
        "toGraph": to_graph,
        "fromBoundaryFingerprint": str(value.get("fromBoundaryFingerprint") or ""),
        "toBoundaryFingerprint": str(value.get("toBoundaryFingerprint") or ""),
    }


def inspect_side(
    *,
    region_id: str,
    bound_graph: dict[str, Any],
    bound_boundary: str,
    neighbor_primary_id: str,
    current: dict[str, Any] | None,
    prefix: str,
) -> tuple[dict[str, Any], list[str]]:
    bound_graph_fp = str(bound_graph.get("graphFingerprint") or "")
    reasons: list[str] = []
    current_graph_fp = None
    current_boundary_fp = None
    graph_matches: bool | None = None
    boundary_matches: bool | None = None

    if current is None:
        reasons.append(f"{prefix}_GRAPH_MISSING")
    else:
        current_graph_fp = str(current["graphFingerprint"])
        graph_matches = current_graph_fp == bound_graph_fp
        if not graph_matches:
            reasons.append(f"{prefix}_GRAPH_CHANGED")
        current_boundary_fp = current["boundaryFingerprints"].get(neighbor_primary_id)
        if current_boundary_fp is None:
            reasons.append(f"{prefix}_BOUNDARY_MISSING")
        else:
            boundary_matches = current_boundary_fp == bound_boundary
            if not boundary_matches:
                reasons.append(f"{prefix}_BOUNDARY_CHANGED")

    return (
        {
            "regionId": region_id,
            "neighborPrimaryGeofabrikId": neighbor_primary_id,
            "boundGraphFingerprint": bound_graph_fp,
            "currentGraphFingerprint": current_graph_fp,
            "graphMatches": graph_matches,
            "boundBoundaryFingerprint": bound_boundary,
            "currentBoundaryFingerprint": current_boundary_fp,
            "boundaryMatches": boundary_matches,
        },
        reasons,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", action="append", required=True, type=Path)
    parser.add_argument("--manifest", action="append", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    manifests: dict[str, dict[str, Any]] = {}
    for path in args.manifest:
        if not path.is_file():
            fail(f"Manifest does not exist: {path}")
        identity = manifest_identity(load(path, "routing manifest"), str(path))
        region = identity["regionId"]
        if region in manifests:
            fail(f"Duplicate current routing manifest for {region}")
        manifests[region] = identity

    pairs = []
    seen_pairs = set()
    for path in args.artifact:
        if not path.is_file():
            fail(f"Artifact does not exist: {path}")
        pair = runtime_pair(load(path, "runtime connectivity"), str(path))
        if pair["pairId"] in seen_pairs:
            fail(f"Duplicate runtime connectivity pair: {pair['pairId']}")
        seen_pairs.add(pair["pairId"])

        from_neighbor_primary = str(pair["toGraph"].get("primaryGeofabrikId") or "")
        to_neighbor_primary = str(pair["fromGraph"].get("primaryGeofabrikId") or "")
        if not from_neighbor_primary or not to_neighbor_primary:
            fail(f"{pair['pairId']}: graph primaryGeofabrikId required")

        from_side, from_reasons = inspect_side(
            region_id=pair["fromRegionId"],
            bound_graph=pair["fromGraph"],
            bound_boundary=pair["fromBoundaryFingerprint"],
            neighbor_primary_id=from_neighbor_primary,
            current=manifests.get(pair["fromRegionId"]),
            prefix="FROM",
        )
        to_side, to_reasons = inspect_side(
            region_id=pair["toRegionId"],
            bound_graph=pair["toGraph"],
            bound_boundary=pair["toBoundaryFingerprint"],
            neighbor_primary_id=to_neighbor_primary,
            current=manifests.get(pair["toRegionId"]),
            prefix="TO",
        )
        reasons = from_reasons + to_reasons

        missing_graph = any(reason.endswith("_GRAPH_MISSING") for reason in reasons)
        boundary_changed = any(
            reason.endswith("_BOUNDARY_CHANGED") or reason.endswith("_BOUNDARY_MISSING")
            for reason in reasons
        )
        graph_changed = any(reason.endswith("_GRAPH_CHANGED") for reason in reasons)

        if missing_graph:
            status = "UNRESOLVED"
            action = "WAIT_FOR_GRAPH"
        elif boundary_changed:
            status = "STALE"
            action = "REDISCOVER_BOUNDARY"
        elif graph_changed:
            status = "STALE"
            action = "REBIND_GRAPH"
        else:
            status = "CURRENT"
            action = "NONE"

        pairs.append({
            "pairId": pair["pairId"],
            "status": status,
            "refreshAction": action,
            "reasons": reasons,
            "fromSide": from_side,
            "toSide": to_side,
        })

    pairs.sort(key=lambda item: item["pairId"])
    affected = [item["pairId"] for item in pairs if item["status"] == "STALE"]
    output = {
        "schema": SCHEMA,
        "version": VERSION,
        "currentPairCount": sum(item["status"] == "CURRENT" for item in pairs),
        "stalePairCount": sum(item["status"] == "STALE" for item in pairs),
        "unresolvedPairCount": sum(item["status"] == "UNRESOLVED" for item in pairs),
        "affectedPairs": affected,
        "pairs": pairs,
        "generator": {"name": GENERATOR_NAME, "version": GENERATOR_VERSION},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(
        f"refresh plan: current={output['currentPairCount']} "
        f"stale={output['stalePairCount']} unresolved={output['unresolvedPairCount']}"
    )
    print(f"affected pairs: {', '.join(affected) if affected else 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
