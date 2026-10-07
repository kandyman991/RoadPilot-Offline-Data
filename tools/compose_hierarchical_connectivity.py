#!/usr/bin/env python3
"""Compose RoadPilot multi-region candidates using exact regional connector matrices.

The query graph is sparse:
- cross-border edges come only from VALIDATED runtime connectivity;
- intermediate-region edges come only from REACHABLE exact-edge matrix cells.

Border proof probe metrics are intentionally not used as journey costs. Scores cover
only precomputed traversal through intermediate regions; live origin/destination legs
remain the responsibility of detailed RoadPilot/Valhalla routing.
"""

from __future__ import annotations

import argparse
import hashlib
import heapq
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

SCHEMA = "roadpilot.hierarchical-connectivity-plan"
VERSION = 1
GENERATOR_NAME = "roadpilot-hierarchical-connectivity-composer"
GENERATOR_VERSION = "1"
MODES = ("MOTORCYCLE", "CAR")
ROUTE_STYLES = ("FASTER", "SHORTER")


def fail(message: str) -> None:
    raise SystemExit(message)


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"Could not read {label} {path}: {exc}")
    if not isinstance(value, dict):
        fail(f"{label} {path} must be a JSON object")
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


def register_graph(registry: dict[str, dict[str, str]], graph: dict[str, str], label: str) -> None:
    region = graph["regionId"]
    existing = registry.get(region)
    if existing is not None and existing != graph:
        fail(
            f"Conflicting graph identity for {region} at {label}: "
            f"{existing['graphFingerprint']} vs {graph['graphFingerprint']}"
        )
    registry[region] = graph


def anchor_role(anchor: dict[str, Any], mode: str, role: str, label: str) -> None:
    roles = anchor.get("roles")
    if not isinstance(roles, dict):
        fail(f"{label}.roles missing")
    mode_roles = roles.get(mode)
    if not isinstance(mode_roles, list) or role not in mode_roles:
        fail(f"{label} does not declare {mode} {role}")


def load_runtime_artifacts(
    paths: list[Path],
    mode: str,
) -> tuple[
    dict[str, dict[str, str]],
    list[dict[str, str]],
    list[dict[str, Any]],
]:
    graph_registry: dict[str, dict[str, str]] = {}
    source_artifacts: list[dict[str, str]] = []
    raw_directed: list[dict[str, Any]] = []
    seen_pairs: set[frozenset[str]] = set()

    for path in sorted(paths, key=lambda item: str(item)):
        if not path.is_file():
            fail(f"Runtime connectivity artifact does not exist: {path}")
        data = load_json(path, "runtime connectivity")
        if data.get("schema") != "roadpilot.runtime-connectivity" or data.get("version") != 1:
            fail(f"{path}: unsupported runtime connectivity schema/version")
        if data.get("validationState") != "VALIDATED":
            fail(f"{path}: runtime connectivity must be VALIDATED")

        pair_id = str(data.get("pairId") or "")
        from_region = str(data.get("fromRegionId") or "")
        to_region = str(data.get("toRegionId") or "")
        if pair_id != f"{from_region}__{to_region}" or not from_region or not to_region:
            fail(f"{path}: invalid directed pair identity")
        unordered = frozenset((from_region, to_region))
        if unordered in seen_pairs:
            fail(f"Duplicate neighboring region pair: {from_region} / {to_region}")
        seen_pairs.add(unordered)

        from_graph = graph_identity(data.get("fromGraph"), f"{path}.fromGraph")
        to_graph = graph_identity(data.get("toGraph"), f"{path}.toGraph")
        register_graph(graph_registry, from_graph, str(path))
        register_graph(graph_registry, to_graph, str(path))
        source_artifacts.append({"pairId": pair_id, "sha256": sha256_file(path)})

        crossings = data.get("crossings")
        if not isinstance(crossings, list):
            fail(f"{path}: crossings must be an array")
        for reverse, source, target, direction_key in (
            (False, from_region, to_region, "fromTo"),
            (True, to_region, from_region, "toFrom"),
        ):
            for crossing in crossings:
                if not isinstance(crossing, dict):
                    fail(f"{path}: crossing must be an object")
                modes = crossing.get("modes")
                mode_value = modes.get(mode) if isinstance(modes, dict) else None
                if not isinstance(mode_value, dict) or mode_value.get(direction_key) is not True:
                    continue
                candidate_id = crossing.get("candidateId")
                frontier_id = crossing.get("frontierRoadId")
                stable_way_id = crossing.get("stableWayId")
                evidence_tier = crossing.get("evidenceTier")
                source_rank = crossing.get("sourceCandidateRank")
                if not isinstance(candidate_id, str) or not candidate_id:
                    fail(f"{path}: crossing candidateId required")
                if not isinstance(frontier_id, str) or not frontier_id:
                    fail(f"{path}: crossing frontierRoadId required")
                for value, label in (
                    (stable_way_id, "stableWayId"),
                    (evidence_tier, "evidenceTier"),
                    (source_rank, "sourceCandidateRank"),
                ):
                    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                        fail(f"{path}: crossing {candidate_id} {label} invalid")
                if stable_way_id <= 0:
                    fail(f"{path}: crossing {candidate_id} stableWayId invalid")
                raw_directed.append({
                    "candidateId": candidate_id,
                    "frontierRoadId": frontier_id,
                    "sourcePairId": pair_id,
                    "fromRegionId": source,
                    "toRegionId": target,
                    "stableWayId": stable_way_id,
                    "evidenceTier": evidence_tier,
                    "sourceCandidateRank": source_rank,
                    "reverse": reverse,
                })

    source_artifacts.sort(key=lambda item: item["pairId"])
    raw_directed.sort(
        key=lambda item: (
            item["fromRegionId"],
            item["toRegionId"],
            item["evidenceTier"],
            item["sourceCandidateRank"],
            item["stableWayId"],
            item["candidateId"],
        )
    )
    return graph_registry, source_artifacts, raw_directed


def load_inventories(
    paths: list[Path],
    graph_registry: dict[str, dict[str, str]],
) -> tuple[
    dict[str, dict[str, Any]],
    dict[str, str],
    list[dict[str, Any]],
]:
    inventories: dict[str, dict[str, Any]] = {}
    inventory_hashes: dict[str, str] = {}
    sources: list[dict[str, Any]] = []

    for path in sorted(paths, key=lambda item: str(item)):
        if not path.is_file():
            fail(f"Connector inventory does not exist: {path}")
        data = load_json(path, "connector inventory")
        if data.get("schema") != "roadpilot.region-connector-inventory" or data.get("version") != 1:
            fail(f"{path}: unsupported connector inventory schema/version")
        region = str(data.get("regionId") or "")
        if not region or region in inventories:
            fail(f"{path}: missing or duplicate inventory regionId {region!r}")
        graph = graph_identity(data.get("graph"), f"{path}.graph")
        if graph["regionId"] != region:
            fail(f"{path}: graph.regionId mismatch")
        register_graph(graph_registry, graph, str(path))
        anchors = data.get("anchors")
        if not isinstance(anchors, list) or data.get("anchorCount") != len(anchors):
            fail(f"{path}: anchors/anchorCount invalid")
        anchor_index: dict[tuple[str, str], dict[str, Any]] = {}
        ids: set[str] = set()
        for index, anchor in enumerate(anchors):
            if not isinstance(anchor, dict):
                fail(f"{path}: anchor[{index}] must be an object")
            anchor_id = anchor.get("id")
            candidate_id = anchor.get("candidateId")
            neighbor = anchor.get("neighborRegionId")
            if not all(isinstance(value, str) and value for value in (anchor_id, candidate_id, neighbor)):
                fail(f"{path}: anchor[{index}] identity invalid")
            if anchor_id in ids:
                fail(f"{path}: duplicate anchor id {anchor_id}")
            ids.add(anchor_id)
            key = (neighbor, candidate_id)
            if key in anchor_index:
                fail(f"{path}: duplicate anchor mapping {neighbor}/{candidate_id}")
            anchor_index[key] = anchor
        data["_anchor_index"] = anchor_index
        inventories[region] = data
        digest = sha256_file(path)
        inventory_hashes[region] = digest
        sources.append({"regionId": region, "sha256": digest, "graph": graph})

    sources.sort(key=lambda item: item["regionId"])
    return inventories, inventory_hashes, sources


def bind_crossings(
    raw_directed: list[dict[str, Any]],
    inventories: dict[str, dict[str, Any]],
    mode: str,
) -> dict[str, list[dict[str, Any]]]:
    outgoing: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for raw in raw_directed:
        source = raw["fromRegionId"]
        target = raw["toRegionId"]
        source_inventory = inventories.get(source)
        target_inventory = inventories.get(target)
        if source_inventory is None or target_inventory is None:
            continue
        source_anchor = source_inventory["_anchor_index"].get((target, raw["candidateId"]))
        target_anchor = target_inventory["_anchor_index"].get((source, raw["candidateId"]))
        if source_anchor is None or target_anchor is None:
            fail(
                f"Validated crossing {raw['candidateId']} lacks matching inventories "
                f"for {source}->{target}"
            )
        anchor_role(source_anchor, mode, "EXIT", f"{source}/{raw['candidateId']}")
        anchor_role(target_anchor, mode, "ENTRY", f"{target}/{raw['candidateId']}")
        option = {
            "candidateId": raw["candidateId"],
            "sourcePairId": raw["sourcePairId"],
            "fromRegionId": source,
            "toRegionId": target,
            "fromExitAnchorId": source_anchor["id"],
            "toEntryAnchorId": target_anchor["id"],
            "stableWayId": raw["stableWayId"],
            "evidenceTier": raw["evidenceTier"],
            "sourceCandidateRank": raw["sourceCandidateRank"],
        }
        outgoing[source].append(option)

    for source in outgoing:
        outgoing[source].sort(
            key=lambda item: (
                item["toRegionId"],
                item["evidenceTier"],
                item["sourceCandidateRank"],
                item["stableWayId"],
                item["candidateId"],
            )
        )
    return outgoing


def load_matrices(
    paths: list[Path],
    graph_registry: dict[str, dict[str, str]],
    inventory_hashes: dict[str, str],
    mode: str,
) -> tuple[
    dict[str, dict[tuple[str, str], dict[str, float]]],
    list[dict[str, Any]],
]:
    matrices: dict[str, dict[tuple[str, str], dict[str, float]]] = {}
    sources: list[dict[str, Any]] = []

    for path in sorted(paths, key=lambda item: str(item)):
        if not path.is_file():
            fail(f"Connector matrix does not exist: {path}")
        data = load_json(path, "connector matrix")
        if data.get("schema") != "roadpilot.region-connector-matrix" or data.get("version") != 1:
            fail(f"{path}: unsupported connector matrix schema/version")
        region = str(data.get("regionId") or "")
        if not region or region in matrices:
            fail(f"{path}: missing or duplicate matrix regionId {region!r}")
        graph = graph_identity(data.get("graph"), f"{path}.graph")
        if graph["regionId"] != region:
            fail(f"{path}: graph.regionId mismatch")
        register_graph(graph_registry, graph, str(path))
        inventory_hash = inventory_hashes.get(region)
        if inventory_hash is None:
            fail(f"{path}: no source inventory supplied for region {region}")
        if data.get("sourceInventorySha256") != inventory_hash:
            fail(
                f"{path}: matrix source inventory is stale for {region}: "
                f"matrix={data.get('sourceInventorySha256')} current={inventory_hash}"
            )
        modes = data.get("modes")
        mode_matrix = modes.get(mode) if isinstance(modes, dict) else None
        if not isinstance(mode_matrix, dict):
            fail(f"{path}: matrix has no {mode} data")
        cells = mode_matrix.get("cells")
        if not isinstance(cells, list):
            fail(f"{path}: {mode} cells must be an array")
        reachable: dict[tuple[str, str], dict[str, float]] = {}
        for index, cell in enumerate(cells):
            if not isinstance(cell, dict):
                fail(f"{path}: cell[{index}] must be an object")
            if cell.get("status") != "REACHABLE":
                continue
            from_anchor = cell.get("fromAnchorId")
            to_anchor = cell.get("toAnchorId")
            if not isinstance(from_anchor, str) or not isinstance(to_anchor, str):
                fail(f"{path}: reachable cell[{index}] anchor ids invalid")
            try:
                distance = float(cell["distanceKm"])
                route_time = float(cell["timeSeconds"])
            except (KeyError, TypeError, ValueError):
                fail(f"{path}: reachable cell[{index}] metrics invalid")
            if distance < 0 or route_time < 0:
                fail(f"{path}: reachable cell[{index}] metrics negative")
            key = (from_anchor, to_anchor)
            if key in reachable:
                fail(f"{path}: duplicate reachable cell {key}")
            reachable[key] = {"distanceKm": distance, "timeSeconds": route_time}
        matrices[region] = reachable
        sources.append({
            "regionId": region,
            "sha256": sha256_file(path),
            "sourceInventorySha256": inventory_hash,
            "graph": graph,
        })

    sources.sort(key=lambda item: item["regionId"])
    return matrices, sources


def score(distance_km: float, time_seconds: float, route_style: str) -> float:
    return time_seconds if route_style == "FASTER" else distance_km


def crossing_tie(crossing: dict[str, Any]) -> tuple[Any, ...]:
    return (
        crossing["evidenceTier"],
        crossing["sourceCandidateRank"],
        crossing["stableWayId"],
        crossing["candidateId"],
    )


def chain_id(mode: str, route_style: str, crossings: list[dict[str, Any]]) -> str:
    raw = "|".join(
        [mode, route_style] + [crossing["candidateId"] for crossing in crossings]
    ).encode("utf-8")
    return "xhc1-" + hashlib.sha256(raw).hexdigest()[:24]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", action="append", required=True, type=Path)
    parser.add_argument("--inventory", action="append", required=True, type=Path)
    parser.add_argument("--matrix", action="append", default=[], type=Path)
    parser.add_argument("--from-region", required=True)
    parser.add_argument("--to-region", required=True)
    parser.add_argument("--mode", required=True, choices=MODES)
    parser.add_argument("--route-style", choices=ROUTE_STYLES, default="FASTER")
    parser.add_argument("--max-hops", type=int, default=8)
    parser.add_argument("--max-candidates", type=int, default=32)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    if args.from_region == args.to_region:
        fail("from-region and to-region must be different")
    if args.max_hops < 1:
        fail("--max-hops must be at least 1")
    if args.max_candidates < 1:
        fail("--max-candidates must be at least 1")

    graph_registry, connectivity_sources, raw_directed = load_runtime_artifacts(
        args.artifact,
        args.mode,
    )
    inventories, inventory_hashes, inventory_sources = load_inventories(
        args.inventory,
        graph_registry,
    )
    outgoing = bind_crossings(raw_directed, inventories, args.mode)
    matrices, matrix_sources = load_matrices(
        args.matrix,
        graph_registry,
        inventory_hashes,
        args.mode,
    )

    if args.from_region not in graph_registry or args.to_region not in graph_registry:
        fail("from-region and to-region must be present in runtime connectivity inputs")

    missing_matrix_regions = sorted(
        region
        for region in graph_registry
        if region not in (args.from_region, args.to_region) and region not in matrices
    )

    # Heap items are ordered by the requested intermediate-region score, then the
    # other metric, hop count, candidate id sequence, and an insertion counter.
    heap: list[tuple[Any, ...]] = []
    counter = 0
    for crossing in outgoing.get(args.from_region, []):
        target = crossing["toRegionId"]
        state = {
            "regions": [args.from_region, target],
            "crossings": [crossing],
            "internalTraversals": [],
            "distanceKm": 0.0,
            "timeSeconds": 0.0,
        }
        sequence = (crossing["candidateId"],)
        heapq.heappush(
            heap,
            (
                score(0.0, 0.0, args.route_style),
                0.0,
                1,
                sequence,
                counter,
                state,
            ),
        )
        counter += 1

    results: list[dict[str, Any]] = []
    result_keys: set[tuple[str, ...]] = set()
    while heap and len(results) < args.max_candidates:
        _, _, hops, sequence, _, state = heapq.heappop(heap)
        current = state["regions"][-1]
        if current == args.to_region:
            if sequence in result_keys:
                continue
            result_keys.add(sequence)
            crossings = state["crossings"]
            regions = state["regions"]
            distance_km = float(state["distanceKm"])
            time_seconds = float(state["timeSeconds"])
            results.append({
                "id": chain_id(args.mode, args.route_style, crossings),
                "rank": 0,
                "regions": regions,
                "hopCount": len(crossings),
                "crossings": crossings,
                "internalTraversals": state["internalTraversals"],
                "score": score(distance_km, time_seconds, args.route_style),
                "scoreUnit": "SECONDS" if args.route_style == "FASTER" else "KILOMETERS",
                "estimatedIntermediateDistanceKm": distance_km,
                "estimatedIntermediateTimeSeconds": time_seconds,
            })
            continue

        if hops >= args.max_hops:
            continue
        matrix = matrices.get(current)
        if matrix is None:
            continue

        entry_anchor = state["crossings"][-1]["toEntryAnchorId"]
        visited_regions = set(state["regions"])
        for crossing in outgoing.get(current, []):
            target = crossing["toRegionId"]
            if target in visited_regions:
                continue
            exit_anchor = crossing["fromExitAnchorId"]
            metric = matrix.get((entry_anchor, exit_anchor))
            if metric is None:
                continue
            new_distance = float(state["distanceKm"]) + metric["distanceKm"]
            new_time = float(state["timeSeconds"]) + metric["timeSeconds"]
            traversal = {
                "regionId": current,
                "fromEntryAnchorId": entry_anchor,
                "toExitAnchorId": exit_anchor,
                "distanceKm": metric["distanceKm"],
                "timeSeconds": metric["timeSeconds"],
            }
            new_crossings = state["crossings"] + [crossing]
            new_state = {
                "regions": state["regions"] + [target],
                "crossings": new_crossings,
                "internalTraversals": state["internalTraversals"] + [traversal],
                "distanceKm": new_distance,
                "timeSeconds": new_time,
            }
            new_sequence = sequence + (crossing["candidateId"],)
            secondary = new_distance if args.route_style == "FASTER" else new_time
            heapq.heappush(
                heap,
                (
                    score(new_distance, new_time, args.route_style),
                    secondary,
                    hops + 1,
                    new_sequence,
                    counter,
                    new_state,
                ),
            )
            counter += 1

    results.sort(
        key=lambda item: (
            item["score"],
            item["estimatedIntermediateDistanceKm"]
            if args.route_style == "FASTER"
            else item["estimatedIntermediateTimeSeconds"],
            item["hopCount"],
            tuple(crossing_tie(crossing) for crossing in item["crossings"]),
            item["id"],
        )
    )
    for rank, item in enumerate(results):
        item["rank"] = rank

    output = {
        "schema": SCHEMA,
        "version": VERSION,
        "fromRegionId": args.from_region,
        "toRegionId": args.to_region,
        "mode": args.mode,
        "routeStyle": args.route_style,
        "maxHops": args.max_hops,
        "maxCandidates": args.max_candidates,
        "scoreScope": "INTERMEDIATE_REGIONS_ONLY",
        "status": "FOUND" if results else "NO_CHAIN",
        "missingMatrixRegions": missing_matrix_regions,
        "sourceConnectivity": connectivity_sources,
        "sourceInventories": inventory_sources,
        "sourceMatrices": matrix_sources,
        "chains": results,
        "generator": {"name": GENERATOR_NAME, "version": GENERATOR_VERSION},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(
        f"{args.from_region}->{args.to_region} {args.mode} {args.route_style}: "
        f"{output['status']} candidates={len(results)} "
        f"missing_matrices={len(missing_matrix_regions)}"
    )
    print(f"wrote: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
