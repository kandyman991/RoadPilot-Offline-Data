#!/usr/bin/env python3
"""Validate RoadPilot matrix-backed hierarchical connectivity plans."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
CHAIN_ID = re.compile(r"^xhc1-[0-9a-f]{24}$")
CANDIDATE_ID = re.compile(r"^xpc1-[0-9a-f]{24}$")
ANCHOR_ID = re.compile(r"^rca1-[0-9a-f]{24}$")


def fail(message: str) -> None:
    raise SystemExit(message)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def nonnegative_number(value: Any, label: str) -> float:
    require(
        isinstance(value, (int, float)) and not isinstance(value, bool),
        f"{label} must be numeric",
    )
    number = float(value)
    require(number >= 0, f"{label} must be non-negative")
    return number


def graph(value: Any, label: str) -> str:
    require(isinstance(value, dict), f"{label} must be an object")
    region = value.get("regionId")
    require(isinstance(region, str) and region, f"{label}.regionId required")
    for key in ("packageVersion", "primaryGeofabrikId"):
        require(isinstance(value.get(key), str) and value[key], f"{label}.{key} required")
    fingerprint = value.get("graphFingerprint")
    require(
        isinstance(fingerprint, str) and bool(SHA256.fullmatch(fingerprint)),
        f"{label}.graphFingerprint invalid",
    )
    return region


def source_hash(value: Any, label: str) -> None:
    require(
        isinstance(value, str) and bool(SHA256.fullmatch(value)),
        f"{label} invalid",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", required=True, type=Path)
    args = parser.parse_args()

    data = json.loads(args.artifact.read_text(encoding="utf-8"))
    require(isinstance(data, dict), "artifact must be an object")
    require(data.get("schema") == "roadpilot.hierarchical-connectivity-plan", "unexpected schema")
    require(data.get("version") == 1, "version must be 1")
    require(data.get("mode") in {"MOTORCYCLE", "CAR"}, "invalid mode")
    require(data.get("routeStyle") in {"FASTER", "SHORTER"}, "invalid routeStyle")
    require(data.get("scoreScope") == "INTERMEDIATE_REGIONS_ONLY", "invalid scoreScope")
    require(data.get("status") in {"FOUND", "NO_CHAIN"}, "invalid status")

    from_region = data.get("fromRegionId")
    to_region = data.get("toRegionId")
    require(
        isinstance(from_region, str) and from_region
        and isinstance(to_region, str) and to_region
        and from_region != to_region,
        "invalid endpoints",
    )
    max_hops = data.get("maxHops")
    max_candidates = data.get("maxCandidates")
    require(
        isinstance(max_hops, int) and not isinstance(max_hops, bool) and max_hops >= 1,
        "maxHops invalid",
    )
    require(
        isinstance(max_candidates, int)
        and not isinstance(max_candidates, bool)
        and max_candidates >= 1,
        "maxCandidates invalid",
    )

    missing = data.get("missingMatrixRegions")
    require(isinstance(missing, list), "missingMatrixRegions must be an array")
    require(
        missing == sorted(set(missing))
        and all(isinstance(item, str) and item for item in missing),
        "missingMatrixRegions must be unique/sorted strings",
    )

    connectivity = data.get("sourceConnectivity")
    require(isinstance(connectivity, list), "sourceConnectivity must be an array")
    previous_pair = None
    seen_pairs = set()
    for index, item in enumerate(connectivity):
        label = f"sourceConnectivity[{index}]"
        require(isinstance(item, dict), f"{label} must be an object")
        pair_id = item.get("pairId")
        require(isinstance(pair_id, str) and pair_id, f"{label}.pairId required")
        require(pair_id not in seen_pairs, f"{label}.pairId duplicated")
        seen_pairs.add(pair_id)
        if previous_pair is not None:
            require(previous_pair <= pair_id, "sourceConnectivity not sorted")
        previous_pair = pair_id
        source_hash(item.get("sha256"), f"{label}.sha256")

    inventory_sources = data.get("sourceInventories")
    require(isinstance(inventory_sources, list), "sourceInventories must be an array")
    inventory_hashes: dict[str, str] = {}
    graph_registry: dict[str, dict[str, Any]] = {}
    previous_region = None
    for index, item in enumerate(inventory_sources):
        label = f"sourceInventories[{index}]"
        require(isinstance(item, dict), f"{label} must be an object")
        region = item.get("regionId")
        require(isinstance(region, str) and region, f"{label}.regionId required")
        require(region not in inventory_hashes, f"{label}.regionId duplicated")
        if previous_region is not None:
            require(previous_region <= region, "sourceInventories not sorted")
        previous_region = region
        source_hash(item.get("sha256"), f"{label}.sha256")
        graph_region = graph(item.get("graph"), f"{label}.graph")
        require(graph_region == region, f"{label}.graph.regionId mismatch")
        inventory_hashes[region] = item["sha256"]
        graph_registry[region] = item["graph"]

    matrix_sources = data.get("sourceMatrices")
    require(isinstance(matrix_sources, list), "sourceMatrices must be an array")
    matrix_regions = set()
    previous_region = None
    for index, item in enumerate(matrix_sources):
        label = f"sourceMatrices[{index}]"
        require(isinstance(item, dict), f"{label} must be an object")
        region = item.get("regionId")
        require(isinstance(region, str) and region, f"{label}.regionId required")
        require(region not in matrix_regions, f"{label}.regionId duplicated")
        matrix_regions.add(region)
        if previous_region is not None:
            require(previous_region <= region, "sourceMatrices not sorted")
        previous_region = region
        source_hash(item.get("sha256"), f"{label}.sha256")
        source_hash(item.get("sourceInventorySha256"), f"{label}.sourceInventorySha256")
        require(
            inventory_hashes.get(region) == item.get("sourceInventorySha256"),
            f"{label} source inventory hash mismatch",
        )
        matrix_graph_region = graph(item.get("graph"), f"{label}.graph")
        require(matrix_graph_region == region, f"{label}.graph.regionId mismatch")
        require(
            graph_registry.get(region) == item.get("graph"),
            f"{label}.graph conflicts with inventory graph",
        )

    chains = data.get("chains")
    require(isinstance(chains, list), "chains must be an array")
    require(len(chains) <= max_candidates, "chains exceed maxCandidates")
    if data["status"] == "FOUND":
        require(chains, "FOUND requires at least one chain")
    else:
        require(not chains, "NO_CHAIN must have no chains")

    expected_score_unit = "SECONDS" if data["routeStyle"] == "FASTER" else "KILOMETERS"
    previous_key = None
    seen_chain_ids = set()
    for ci, chain in enumerate(chains):
        label = f"chains[{ci}]"
        require(isinstance(chain, dict), f"{label} must be an object")
        chain_id = chain.get("id")
        require(
            isinstance(chain_id, str) and bool(CHAIN_ID.fullmatch(chain_id)),
            f"{label}.id invalid",
        )
        require(chain_id not in seen_chain_ids, f"{label}.id duplicated")
        seen_chain_ids.add(chain_id)
        require(chain.get("rank") == ci, f"{label}.rank must equal sorted position")

        regions = chain.get("regions")
        crossings = chain.get("crossings")
        traversals = chain.get("internalTraversals")
        require(
            isinstance(regions, list)
            and len(regions) >= 2
            and all(isinstance(region, str) and region for region in regions),
            f"{label}.regions invalid",
        )
        require(len(regions) == len(set(regions)), f"{label}.regions must be simple/no cycles")
        require(regions[0] == from_region and regions[-1] == to_region, f"{label} endpoints mismatch")
        require(isinstance(crossings, list) and crossings, f"{label}.crossings invalid")
        require(len(crossings) == len(regions) - 1, f"{label}.crossings count mismatch")
        require(chain.get("hopCount") == len(crossings), f"{label}.hopCount mismatch")
        require(len(crossings) <= max_hops, f"{label} exceeds maxHops")
        require(
            isinstance(traversals, list) and len(traversals) == max(0, len(crossings) - 1),
            f"{label}.internalTraversals count mismatch",
        )

        candidate_sequence = []
        for xi, crossing in enumerate(crossings):
            c_label = f"{label}.crossings[{xi}]"
            require(isinstance(crossing, dict), f"{c_label} must be an object")
            candidate_id = crossing.get("candidateId")
            require(
                isinstance(candidate_id, str) and bool(CANDIDATE_ID.fullmatch(candidate_id)),
                f"{c_label}.candidateId invalid",
            )
            candidate_sequence.append(candidate_id)
            require(crossing.get("sourcePairId") in seen_pairs, f"{c_label}.sourcePairId unknown")
            require(crossing.get("fromRegionId") == regions[xi], f"{c_label}.fromRegionId mismatch")
            require(crossing.get("toRegionId") == regions[xi + 1], f"{c_label}.toRegionId mismatch")
            for anchor_key in ("fromExitAnchorId", "toEntryAnchorId"):
                anchor_id = crossing.get(anchor_key)
                require(
                    isinstance(anchor_id, str) and bool(ANCHOR_ID.fullmatch(anchor_id)),
                    f"{c_label}.{anchor_key} invalid",
                )
            stable_way = crossing.get("stableWayId")
            require(
                isinstance(stable_way, int) and not isinstance(stable_way, bool) and stable_way > 0,
                f"{c_label}.stableWayId invalid",
            )
            for key in ("evidenceTier", "sourceCandidateRank"):
                value = crossing.get(key)
                require(
                    isinstance(value, int) and not isinstance(value, bool) and value >= 0,
                    f"{c_label}.{key} invalid",
                )

        total_distance = 0.0
        total_time = 0.0
        for ti, traversal in enumerate(traversals):
            t_label = f"{label}.internalTraversals[{ti}]"
            require(isinstance(traversal, dict), f"{t_label} must be an object")
            intermediate_region = regions[ti + 1]
            require(traversal.get("regionId") == intermediate_region, f"{t_label}.regionId mismatch")
            require(intermediate_region in matrix_regions, f"{t_label} uses region without matrix")
            require(
                traversal.get("fromEntryAnchorId") == crossings[ti]["toEntryAnchorId"],
                f"{t_label}.fromEntryAnchorId mismatch",
            )
            require(
                traversal.get("toExitAnchorId") == crossings[ti + 1]["fromExitAnchorId"],
                f"{t_label}.toExitAnchorId mismatch",
            )
            total_distance += nonnegative_number(traversal.get("distanceKm"), f"{t_label}.distanceKm")
            total_time += nonnegative_number(traversal.get("timeSeconds"), f"{t_label}.timeSeconds")

        declared_distance = nonnegative_number(
            chain.get("estimatedIntermediateDistanceKm"),
            f"{label}.estimatedIntermediateDistanceKm",
        )
        declared_time = nonnegative_number(
            chain.get("estimatedIntermediateTimeSeconds"),
            f"{label}.estimatedIntermediateTimeSeconds",
        )
        require(abs(declared_distance - total_distance) < 1e-6, f"{label} intermediate distance mismatch")
        require(abs(declared_time - total_time) < 1e-6, f"{label} intermediate time mismatch")
        require(chain.get("scoreUnit") == expected_score_unit, f"{label}.scoreUnit invalid")
        declared_score = nonnegative_number(chain.get("score"), f"{label}.score")
        expected_score = total_time if data["routeStyle"] == "FASTER" else total_distance
        require(abs(declared_score - expected_score) < 1e-6, f"{label}.score mismatch")

        secondary = total_distance if data["routeStyle"] == "FASTER" else total_time
        key = (declared_score, secondary, len(crossings), tuple(candidate_sequence), chain_id)
        if previous_key is not None:
            require(previous_key <= key, "chains are not deterministically ranked")
        previous_key = key

    generator = data.get("generator")
    require(isinstance(generator, dict), "generator required")
    require(isinstance(generator.get("name"), str) and generator["name"], "generator.name required")
    require(isinstance(generator.get("version"), str) and generator["version"], "generator.version required")

    print(
        f"valid hierarchical connectivity plan: {from_region}->{to_region} "
        f"{data['mode']} {data['routeStyle']} status={data['status']} chains={len(chains)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
