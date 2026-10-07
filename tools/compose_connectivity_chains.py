#!/usr/bin/env python3
"""Compose validated neighboring RoadPilot connectivity artifacts into ranked multi-hop chains.

Only runtime artifacts already marked VALIDATED are accepted. Adjacency is created
solely from mode/direction booleans proven by Valhalla. All simple region chains up
to max-hops are retained and ranked using proven route metrics for FASTER/SHORTER.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

SCHEMA = "roadpilot.connectivity-chain-plan"
VERSION = 1
GENERATOR_NAME = "roadpilot-connectivity-chain-composer"
GENERATOR_VERSION = "2"
MODES = ("MOTORCYCLE", "CAR")
ROUTE_STYLES = ("FASTER", "SHORTER")


def fail(message: str) -> None:
    raise SystemExit(message)


def load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"Could not read {path}: {exc}")
    if not isinstance(value, dict):
        fail(f"{path}: expected a JSON object")
    if value.get("schema") != "roadpilot.runtime-connectivity" or value.get("version") != 1:
        fail(f"{path}: unsupported runtime connectivity schema/version")
    if value.get("validationState") != "VALIDATED":
        fail(f"{path}: runtime connectivity must be VALIDATED")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def graph_identity(value: Any, label: str) -> dict[str, str]:
    if not isinstance(value, dict):
        fail(f"{label} must be an object")
    result: dict[str, str] = {}
    for key in ("regionId", "packageVersion", "graphFingerprint", "primaryGeofabrikId"):
        item = value.get(key)
        if not isinstance(item, str) or not item:
            fail(f"{label}.{key} is required")
        result[key] = item
    return result


def boundary(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.startswith("sha256:") or len(value) != 71:
        fail(f"{label} must be sha256:<64 hex>")
    return value


def anchor(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail(f"{label} must be an object")
    coordinate = value.get("coordinate")
    if not isinstance(coordinate, dict):
        fail(f"{label}.coordinate must be an object")
    return {
        "coordinate": {
            "lat": float(coordinate["lat"]),
            "lng": float(coordinate["lng"]),
        },
        "graphId": int(value["graphId"]),
        "wayId": value.get("wayId"),
        "percentAlong": value.get("percentAlong"),
    }


def road(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        value = {}
    return {
        "name": value.get("name") if isinstance(value.get("name"), str) else None,
        "ref": value.get("ref") if isinstance(value.get("ref"), str) else None,
        "highway": value.get("highway") if isinstance(value.get("highway"), str) else None,
    }


def route_metric(crossing: dict[str, Any], mode: str, direction_key: str) -> dict[str, float]:
    metrics = crossing.get("routeMetrics")
    if not isinstance(metrics, dict):
        fail(f"crossing {crossing.get('candidateId')} is missing routeMetrics")
    mode_metrics = metrics.get(mode)
    if not isinstance(mode_metrics, dict):
        fail(f"crossing {crossing.get('candidateId')} is missing {mode} routeMetrics")
    metric = mode_metrics.get(direction_key)
    if not isinstance(metric, dict):
        fail(
            f"crossing {crossing.get('candidateId')} claims {mode}.{direction_key} "
            "support without proven route metrics"
        )
    try:
        distance = float(metric["distanceKm"])
        route_time = float(metric["timeSeconds"])
    except (KeyError, TypeError, ValueError):
        fail(f"crossing {crossing.get('candidateId')} has invalid route metrics")
    if distance < 0 or route_time < 0:
        fail(f"crossing {crossing.get('candidateId')} has negative route metrics")
    return {"distanceKm": distance, "timeSeconds": route_time}


def option(
    crossing: dict[str, Any],
    reverse: bool,
    mode: str,
    direction_key: str,
) -> dict[str, Any]:
    from_anchor = anchor(crossing.get("fromAnchor"), "crossing.fromAnchor")
    to_anchor = anchor(crossing.get("toAnchor"), "crossing.toAnchor")
    if reverse:
        from_anchor, to_anchor = to_anchor, from_anchor
    metric = route_metric(crossing, mode, direction_key)
    return {
        "rank": 0,
        "candidateId": crossing["candidateId"],
        "frontierRoadId": crossing["frontierRoadId"],
        "stableWayId": crossing["stableWayId"],
        "evidenceTier": crossing["evidenceTier"],
        "sourceCandidateRank": crossing["sourceCandidateRank"],
        "distanceKm": metric["distanceKm"],
        "timeSeconds": metric["timeSeconds"],
        "road": road(crossing.get("road")),
        "fromAnchor": from_anchor,
        "toAnchor": to_anchor,
    }


def option_score(value: dict[str, Any], route_style: str) -> float:
    return float(value["timeSeconds"] if route_style == "FASTER" else value["distanceKm"])


def option_sort_key(value: dict[str, Any], route_style: str) -> tuple[Any, ...]:
    return (
        option_score(value, route_style),
        value["evidenceTier"],
        value["sourceCandidateRank"],
        value["stableWayId"],
        value["candidateId"],
    )


def chain_id(mode: str, route_style: str, regions: list[str]) -> str:
    raw = f"{mode}|{route_style}|{'->'.join(regions)}".encode("utf-8")
    return "xch1-" + hashlib.sha256(raw).hexdigest()[:24]


def enumerate_paths(
    adjacency: dict[str, list[str]],
    start: str,
    target: str,
    max_hops: int,
) -> list[list[str]]:
    paths: list[list[str]] = []

    def walk(current: str, path: list[str]) -> None:
        if len(path) - 1 >= max_hops:
            return
        for neighbor in adjacency.get(current, []):
            if neighbor in path:
                continue
            next_path = path + [neighbor]
            if neighbor == target:
                paths.append(next_path)
            else:
                walk(neighbor, next_path)

    walk(start, [start])
    paths.sort()
    return paths


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", action="append", required=True, type=Path)
    parser.add_argument("--from-region", required=True)
    parser.add_argument("--to-region", required=True)
    parser.add_argument("--mode", required=True, choices=MODES)
    parser.add_argument("--route-style", choices=ROUTE_STYLES, default="FASTER")
    parser.add_argument("--max-hops", type=int, default=8)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    if args.from_region == args.to_region:
        fail("from-region and to-region must be different")
    if args.max_hops < 1:
        fail("--max-hops must be at least 1")

    graph_registry: dict[str, dict[str, str]] = {}
    source_artifacts: list[dict[str, Any]] = []
    pair_keys: set[frozenset[str]] = set()
    transitions: dict[tuple[str, str], dict[str, Any]] = {}

    for path in sorted(args.artifact, key=lambda p: str(p)):
        if not path.is_file():
            fail(f"Input does not exist: {path}")
        data = load_object(path)
        pair_id = str(data.get("pairId") or "")
        from_region = str(data.get("fromRegionId") or "")
        to_region = str(data.get("toRegionId") or "")
        if pair_id != f"{from_region}__{to_region}" or not from_region or not to_region:
            fail(f"{path}: invalid directed pair identity")

        unordered = frozenset((from_region, to_region))
        if unordered in pair_keys:
            fail(f"Duplicate neighboring region pair supplied: {from_region} / {to_region}")
        pair_keys.add(unordered)

        from_graph = graph_identity(data.get("fromGraph"), f"{path}.fromGraph")
        to_graph = graph_identity(data.get("toGraph"), f"{path}.toGraph")
        for region, graph in ((from_region, from_graph), (to_region, to_graph)):
            existing = graph_registry.get(region)
            if existing is not None and existing != graph:
                fail(
                    f"Conflicting graph identity for intermediate region {region}: "
                    f"{existing['graphFingerprint']} vs {graph['graphFingerprint']}"
                )
            graph_registry[region] = graph

        from_boundary = boundary(data.get("fromBoundaryFingerprint"), f"{path}.fromBoundaryFingerprint")
        to_boundary = boundary(data.get("toBoundaryFingerprint"), f"{path}.toBoundaryFingerprint")
        source_artifacts.append({
            "pairId": pair_id,
            "sha256": sha256_file(path),
            "fromRegionId": from_region,
            "toRegionId": to_region,
            "fromBoundaryFingerprint": from_boundary,
            "toBoundaryFingerprint": to_boundary,
        })

        crossings = data.get("crossings")
        if not isinstance(crossings, list):
            fail(f"{path}: crossings must be an array")

        for reverse, source, target, direction_key, source_direction in (
            (False, from_region, to_region, "fromTo", "FROM_TO"),
            (True, to_region, from_region, "toFrom", "TO_FROM"),
        ):
            options: list[dict[str, Any]] = []
            for crossing in crossings:
                if not isinstance(crossing, dict):
                    fail(f"{path}: crossing entry must be an object")
                modes = crossing.get("modes")
                if not isinstance(modes, dict):
                    fail(f"{path}: crossing modes must be an object")
                mode = modes.get(args.mode)
                if not isinstance(mode, dict) or mode.get(direction_key) is not True:
                    continue
                options.append(option(crossing, reverse, args.mode, direction_key))
            if not options:
                continue
            options.sort(key=lambda value: option_sort_key(value, args.route_style))
            for rank, item in enumerate(options):
                item["rank"] = rank
            key = (source, target)
            if key in transitions:
                fail(f"Multiple runtime artifacts define transition {source}->{target}")
            transitions[key] = {
                "fromRegionId": source,
                "toRegionId": target,
                "sourcePairId": pair_id,
                "sourceDirection": source_direction,
                "fromGraph": to_graph if reverse else from_graph,
                "toGraph": from_graph if reverse else to_graph,
                "fromBoundaryFingerprint": to_boundary if reverse else from_boundary,
                "toBoundaryFingerprint": from_boundary if reverse else to_boundary,
                "crossingOptions": options,
            }

    source_artifacts.sort(key=lambda item: item["pairId"])
    region_graphs = [graph_registry[key] for key in sorted(graph_registry)]

    adjacency: dict[str, list[str]] = defaultdict(list)
    for source, target in transitions:
        adjacency[source].append(target)
    for source in adjacency:
        adjacency[source].sort()

    region_paths = enumerate_paths(
        adjacency,
        args.from_region,
        args.to_region,
        args.max_hops,
    )

    chains: list[dict[str, Any]] = []
    score_unit = "SECONDS" if args.route_style == "FASTER" else "KILOMETERS"
    for regions in region_paths:
        hops = [transitions[(regions[i], regions[i + 1])] for i in range(len(regions) - 1)]
        best_options = [hop["crossingOptions"][0] for hop in hops]
        total_distance = sum(float(option["distanceKm"]) for option in best_options)
        total_time = sum(float(option["timeSeconds"]) for option in best_options)
        score = total_time if args.route_style == "FASTER" else total_distance
        chains.append({
            "id": chain_id(args.mode, args.route_style, regions),
            "rank": 0,
            "score": score,
            "scoreUnit": score_unit,
            "estimatedDistanceKm": total_distance,
            "estimatedTimeSeconds": total_time,
            "regions": regions,
            "hops": hops,
        })

    chains.sort(
        key=lambda item: (
            item["score"],
            len(item["hops"]),
            item["regions"],
            item["id"],
        )
    )
    for rank, chain in enumerate(chains):
        chain["rank"] = rank

    found = bool(chains)
    output = {
        "schema": SCHEMA,
        "version": VERSION,
        "fromRegionId": args.from_region,
        "toRegionId": args.to_region,
        "mode": args.mode,
        "routeStyle": args.route_style,
        "maxHops": args.max_hops,
        "status": "FOUND" if found else "NO_CHAIN",
        "hopCount": len(chains[0]["hops"]) if found else None,
        "sourceArtifacts": source_artifacts,
        "regionGraphs": region_graphs,
        "chains": chains,
        "generator": {"name": GENERATOR_NAME, "version": GENERATOR_VERSION},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(
        f"{args.from_region}->{args.to_region} {args.mode} {args.route_style}: "
        f"{output['status']} chains={len(chains)} best_hops={output['hopCount']}"
    )
    print(f"wrote: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
