#!/usr/bin/env python3
"""Validate RoadPilot multi-hop connectivity chain plans."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
CHAIN_ID = re.compile(r"^xch1-[0-9a-f]{24}$")
CANDIDATE_ID = re.compile(r"^xpc1-[0-9a-f]{24}$")


def fail(message: str) -> None:
    raise SystemExit(message)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def graph(value: Any, label: str) -> str:
    require(isinstance(value, dict), f"{label} must be an object")
    region = value.get("regionId")
    require(isinstance(region, str) and region, f"{label}.regionId required")
    for key in ("packageVersion", "primaryGeofabrikId"):
        require(isinstance(value.get(key), str) and value[key], f"{label}.{key} required")
    fp = value.get("graphFingerprint")
    require(isinstance(fp, str) and bool(SHA256.fullmatch(fp)), f"{label}.graphFingerprint invalid")
    return region


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", required=True, type=Path)
    args = parser.parse_args()

    data = json.loads(args.artifact.read_text(encoding="utf-8"))
    require(isinstance(data, dict), "artifact must be an object")
    require(data.get("schema") == "roadpilot.connectivity-chain-plan", "unexpected schema")
    require(data.get("version") == 1, "version must be 1")
    require(data.get("mode") in {"MOTORCYCLE", "CAR"}, "invalid mode")
    require(data.get("status") in {"FOUND", "NO_CHAIN"}, "invalid status")
    max_hops = data.get("maxHops")
    require(isinstance(max_hops, int) and not isinstance(max_hops, bool) and max_hops >= 1, "invalid maxHops")

    sources = data.get("sourceArtifacts")
    require(isinstance(sources, list), "sourceArtifacts must be an array")
    pair_ids = set()
    for i, source in enumerate(sources):
        require(isinstance(source, dict), f"sourceArtifacts[{i}] must be an object")
        pair_id = source.get("pairId")
        require(isinstance(pair_id, str) and pair_id and pair_id not in pair_ids, f"sourceArtifacts[{i}].pairId invalid/duplicate")
        pair_ids.add(pair_id)
        require(isinstance(source.get("sha256"), str) and bool(SHA256.fullmatch(source["sha256"])), f"sourceArtifacts[{i}].sha256 invalid")
        for key in ("fromBoundaryFingerprint", "toBoundaryFingerprint"):
            require(isinstance(source.get(key), str) and bool(SHA256.fullmatch(source[key])), f"sourceArtifacts[{i}].{key} invalid")

    graph_values = data.get("regionGraphs")
    require(isinstance(graph_values, list), "regionGraphs must be an array")
    graph_by_region = {}
    for i, item in enumerate(graph_values):
        region = graph(item, f"regionGraphs[{i}]")
        require(region not in graph_by_region, f"duplicate graph identity for {region}")
        graph_by_region[region] = item

    chains = data.get("chains")
    require(isinstance(chains, list), "chains must be an array")
    if data["status"] == "NO_CHAIN":
        require(data.get("hopCount") is None, "NO_CHAIN hopCount must be null")
        require(chains == [], "NO_CHAIN chains must be empty")
    else:
        hop_count = data.get("hopCount")
        require(isinstance(hop_count, int) and hop_count >= 1, "FOUND hopCount invalid")
        require(chains, "FOUND requires at least one chain")

    seen_chain_ids = set()
    previous_regions = None
    for ci, chain in enumerate(chains):
        require(isinstance(chain, dict), f"chain[{ci}] must be an object")
        chain_id = chain.get("id")
        require(isinstance(chain_id, str) and bool(CHAIN_ID.fullmatch(chain_id)) and chain_id not in seen_chain_ids, f"chain[{ci}].id invalid/duplicate")
        seen_chain_ids.add(chain_id)
        regions = chain.get("regions")
        hops = chain.get("hops")
        require(isinstance(regions, list) and len(regions) >= 2 and all(isinstance(r, str) and r for r in regions), f"chain[{ci}].regions invalid")
        require(len(regions) == len(set(regions)), f"chain[{ci}] contains a region cycle")
        require(isinstance(hops, list) and len(hops) == len(regions) - 1, f"chain[{ci}].hops mismatch")
        require(len(hops) == data["hopCount"], f"chain[{ci}] is not shortest-hop length")
        require(regions[0] == data["fromRegionId"] and regions[-1] == data["toRegionId"], f"chain[{ci}] endpoints mismatch")
        if previous_regions is not None:
            require(previous_regions <= regions, "chains are not deterministically ordered")
        previous_regions = regions

        for hi, hop in enumerate(hops):
            label = f"chain[{ci}].hop[{hi}]"
            require(isinstance(hop, dict), f"{label} must be an object")
            require(hop.get("fromRegionId") == regions[hi] and hop.get("toRegionId") == regions[hi+1], f"{label} region sequence mismatch")
            require(hop.get("sourceDirection") in {"FROM_TO", "TO_FROM"}, f"{label}.sourceDirection invalid")
            require(hop.get("sourcePairId") in pair_ids, f"{label}.sourcePairId unknown")
            from_graph = hop.get("fromGraph")
            to_graph = hop.get("toGraph")
            fr = graph(from_graph, f"{label}.fromGraph")
            tr = graph(to_graph, f"{label}.toGraph")
            require(fr == regions[hi] and tr == regions[hi+1], f"{label} graph orientation mismatch")
            require(graph_by_region.get(fr) == from_graph and graph_by_region.get(tr) == to_graph, f"{label} graph identity conflicts with registry")
            for key in ("fromBoundaryFingerprint", "toBoundaryFingerprint"):
                require(isinstance(hop.get(key), str) and bool(SHA256.fullmatch(hop[key])), f"{label}.{key} invalid")

            options = hop.get("crossingOptions")
            require(isinstance(options, list) and options, f"{label}.crossingOptions must be non-empty")
            previous_option = None
            option_ids = set()
            for oi, option in enumerate(options):
                require(isinstance(option, dict), f"{label}.option[{oi}] must be an object")
                cid = option.get("candidateId")
                require(isinstance(cid, str) and bool(CANDIDATE_ID.fullmatch(cid)) and cid not in option_ids, f"{label}.option[{oi}].candidateId invalid/duplicate")
                option_ids.add(cid)
                key = (option.get("evidenceTier"), option.get("sourceCandidateRank"), option.get("stableWayId"), cid)
                require(all(isinstance(x, int) and not isinstance(x, bool) and x >= 0 for x in key[:3]), f"{label}.option[{oi}] ranking invalid")
                if previous_option is not None:
                    require(previous_option <= key, f"{label} options are not deterministically ordered")
                previous_option = key
                for anchor_name, expected_region in (("fromAnchor", fr), ("toAnchor", tr)):
                    anchor = option.get(anchor_name)
                    require(isinstance(anchor, dict), f"{label}.option[{oi}].{anchor_name} missing")
                    coord = anchor.get("coordinate")
                    require(isinstance(coord, dict) and isinstance(coord.get("lat"), (int,float)) and isinstance(coord.get("lng"), (int,float)), f"{label}.option[{oi}].{anchor_name}.coordinate invalid")
                    graph_id = anchor.get("graphId")
                    require(isinstance(graph_id, int) and not isinstance(graph_id, bool) and graph_id > 0, f"{label}.option[{oi}].{anchor_name}.graphId invalid")

    print(f"valid connectivity chain plan: {data['fromRegionId']}->{data['toRegionId']} {data['mode']} status={data['status']} chains={len(chains)}")


if __name__ == "__main__":
    main()
