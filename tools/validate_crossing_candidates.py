#!/usr/bin/env python3
"""Validate RoadPilot unproven cross-region crossing candidates."""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
CANDIDATE_ID = re.compile(r"^xpc1-[0-9a-f]{24}$")
FRONTIER_ID = re.compile(r"^fri1-[0-9a-f]{24}$")
KINDS = {"CROSSING", "FRONTIER_OVERLAP"}


def fail(message: str) -> None:
    raise SystemExit(message)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def finite(value: Any, label: str) -> float:
    require(
        isinstance(value, (int, float)) and not isinstance(value, bool),
        f"{label} must be numeric",
    )
    number = float(value)
    require(math.isfinite(number), f"{label} must be finite")
    return number


def coordinate(value: Any, label: str) -> None:
    require(isinstance(value, dict), f"{label} must be an object")
    require(set(value) == {"lat", "lng"}, f"{label} must contain only lat/lng")
    lat = finite(value.get("lat"), f"{label}.lat")
    lng = finite(value.get("lng"), f"{label}.lng")
    require(-90 <= lat <= 90, f"{label}.lat invalid")
    require(-180 <= lng <= 180, f"{label}.lng invalid")


def graph(value: Any, expected_region: str, label: str) -> None:
    require(isinstance(value, dict), f"{label} must be an object")
    require(value.get("regionId") == expected_region, f"{label}.regionId mismatch")
    require(bool(str(value.get("packageVersion") or "").strip()), f"{label}.packageVersion required")
    fp = value.get("graphFingerprint")
    require(isinstance(fp, str) and bool(SHA256.fullmatch(fp)), f"{label}.graphFingerprint invalid")
    require(bool(str(value.get("primaryGeofabrikId") or "").strip()), f"{label}.primaryGeofabrikId required")


def edge(value: Any, label: str) -> None:
    require(isinstance(value, dict), f"{label} must be an object")
    rank = value.get("correlationRank")
    require(isinstance(rank, int) and not isinstance(rank, bool) and rank >= 0, f"{label}.correlationRank invalid")
    require(isinstance(value.get("wayMatch"), bool), f"{label}.wayMatch invalid")
    coordinate(value.get("correlatedCoordinate"), f"{label}.correlatedCoordinate")
    way_id = value.get("wayId")
    require(way_id is None or (isinstance(way_id, int) and not isinstance(way_id, bool) and way_id > 0), f"{label}.wayId invalid")
    percent = value.get("percentAlong")
    if percent is not None:
        p = finite(percent, f"{label}.percentAlong")
        require(0 <= p <= 1, f"{label}.percentAlong invalid")
    require(finite(value.get("distanceMeters"), f"{label}.distanceMeters") >= 0, f"{label}.distanceMeters invalid")
    heading = value.get("headingDegrees")
    if heading is not None:
        h = finite(heading, f"{label}.headingDegrees")
        require(0 <= h < 360, f"{label}.headingDegrees invalid")
    require(value.get("linearReference") is None or isinstance(value.get("linearReference"), str), f"{label}.linearReference invalid")
    graph_id = value.get("graphId")
    require(graph_id is None or (isinstance(graph_id, int) and not isinstance(graph_id, bool) and graph_id > 0), f"{label}.graphId invalid")
    names = value.get("roadNames")
    require(isinstance(names, list) and all(isinstance(x, str) for x in names), f"{label}.roadNames invalid")
    require(len(names) == len(set(names)), f"{label}.roadNames duplicates")
    access = value.get("access")
    require(isinstance(access, dict) and all(isinstance(k, str) and isinstance(v, bool) for k, v in access.items()), f"{label}.access invalid")
    require(value.get("roadClass") is None or isinstance(value.get("roadClass"), str), f"{label}.roadClass invalid")
    require(value.get("use") is None or isinstance(value.get("use"), str), f"{label}.use invalid")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", required=True, type=Path)
    args = parser.parse_args()

    data = json.loads(args.artifact.read_text(encoding="utf-8"))
    require(isinstance(data, dict), "artifact must be an object")
    require(data.get("schema") == "roadpilot.crossing-candidates", "unexpected schema")
    require(data.get("version") == 1, "version must be 1")

    from_region = str(data.get("fromRegionId") or "")
    to_region = str(data.get("toRegionId") or "")
    require(from_region and to_region and from_region != to_region, "invalid region pair")
    require(data.get("pairId") == f"{from_region}__{to_region}", "pairId mismatch")
    for key in ("fromBoundaryFingerprint", "toBoundaryFingerprint"):
        fp = data.get(key)
        require(isinstance(fp, str) and bool(SHA256.fullmatch(fp)), f"{key} invalid")
    graph(data.get("fromGraph"), from_region, "fromGraph")
    graph(data.get("toGraph"), to_region, "toGraph")

    require(data.get("validationState") == "UNPROVEN", "validationState must be UNPROVEN")

    generator = data.get("generator")
    require(isinstance(generator, dict), "generator must be an object")
    require(bool(str(generator.get("name") or "").strip()), "generator.name required")
    require(bool(str(generator.get("version") or "").strip()), "generator.version required")

    frontier_count = data.get("frontierRoadCount")
    candidate_count = data.get("candidateCount")
    require(isinstance(frontier_count, int) and frontier_count >= 0, "frontierRoadCount invalid")
    require(isinstance(candidate_count, int) and candidate_count >= 0, "candidateCount invalid")

    unresolved = data.get("unresolvedFrontierRoadIds")
    require(isinstance(unresolved, list), "unresolvedFrontierRoadIds must be an array")
    require(all(isinstance(x, str) and FRONTIER_ID.fullmatch(x) for x in unresolved), "unresolvedFrontierRoadIds invalid")
    require(len(unresolved) == len(set(unresolved)), "unresolvedFrontierRoadIds duplicates")

    candidates = data.get("candidates")
    require(isinstance(candidates, list), "candidates must be an array")
    require(len(candidates) == candidate_count, "candidateCount mismatch")
    ids = set()
    ranks_by_frontier: dict[str, list[int]] = defaultdict(list)

    for index, candidate in enumerate(candidates):
        label = f"candidate[{index}]"
        require(isinstance(candidate, dict), f"{label} must be an object")
        cid = candidate.get("id")
        require(isinstance(cid, str) and bool(CANDIDATE_ID.fullmatch(cid)), f"{label}.id invalid")
        require(cid not in ids, f"{label}.id duplicated")
        ids.add(cid)

        rank = candidate.get("candidateRank")
        require(isinstance(rank, int) and not isinstance(rank, bool) and rank >= 0, f"{label}.candidateRank invalid")
        frontier_id = candidate.get("frontierRoadId")
        require(isinstance(frontier_id, str) and bool(FRONTIER_ID.fullmatch(frontier_id)), f"{label}.frontierRoadId invalid")
        ranks_by_frontier[frontier_id].append(rank)

        stable_way = candidate.get("stableWayId")
        require(isinstance(stable_way, int) and stable_way > 0, f"{label}.stableWayId invalid")
        require(isinstance(candidate.get("crossingIndex"), int) and candidate["crossingIndex"] >= 0, f"{label}.crossingIndex invalid")
        require(candidate.get("crossingKind") in KINDS, f"{label}.crossingKind invalid")
        coordinate(candidate.get("frontierCoordinate"), f"{label}.frontierCoordinate")
        heading = finite(candidate.get("frontierHeadingDegrees"), f"{label}.frontierHeadingDegrees")
        require(0 <= heading < 360, f"{label}.frontierHeadingDegrees invalid")
        tags = candidate.get("routingTags")
        require(isinstance(tags, dict) and all(isinstance(k, str) and isinstance(v, str) for k, v in tags.items()), f"{label}.routingTags invalid")
        edge(candidate.get("fromEdge"), f"{label}.fromEdge")
        edge(candidate.get("toEdge"), f"{label}.toEdge")

        evidence = candidate.get("evidence")
        require(isinstance(evidence, dict), f"{label}.evidence must be an object")
        tier = evidence.get("tier")
        require(isinstance(tier, int) and 0 <= tier <= 4, f"{label}.evidence.tier invalid")
        for key in ("bothMatchStableWay", "sameCorrelatedWay", "oneMatchesStableWay"):
            require(isinstance(evidence.get(key), bool), f"{label}.evidence.{key} invalid")
        names = evidence.get("sharedRoadNames")
        require(isinstance(names, list) and all(isinstance(x, str) for x in names), f"{label}.evidence.sharedRoadNames invalid")
        require(len(names) == len(set(names)), f"{label}.evidence.sharedRoadNames duplicates")
        require(finite(evidence.get("separationMeters"), f"{label}.evidence.separationMeters") >= 0, f"{label}.evidence.separationMeters invalid")
        require(finite(evidence.get("combinedCorrelationDistanceMeters"), f"{label}.evidence.combinedCorrelationDistanceMeters") >= 0, f"{label}.evidence.combinedCorrelationDistanceMeters invalid")
        delta = evidence.get("headingDeltaDegrees")
        if delta is not None:
            d = finite(delta, f"{label}.evidence.headingDeltaDegrees")
            require(0 <= d <= 180, f"{label}.evidence.headingDeltaDegrees invalid")

        from_edge = candidate["fromEdge"]
        to_edge = candidate["toEdge"]
        both = bool(from_edge["wayMatch"]) and bool(to_edge["wayMatch"])
        one = bool(from_edge["wayMatch"]) or bool(to_edge["wayMatch"])
        same = (
            isinstance(from_edge["wayId"], int)
            and isinstance(to_edge["wayId"], int)
            and from_edge["wayId"] == to_edge["wayId"]
        )
        require(evidence["bothMatchStableWay"] == both, f"{label}.evidence both-match mismatch")
        require(evidence["oneMatchesStableWay"] == one, f"{label}.evidence one-match mismatch")
        require(evidence["sameCorrelatedWay"] == same, f"{label}.evidence same-way mismatch")

    for frontier_id, ranks in ranks_by_frontier.items():
        require(sorted(ranks) == list(range(len(ranks))), f"{frontier_id} candidate ranks are not contiguous")
        require(frontier_id not in unresolved, f"{frontier_id} cannot be both resolved and unresolved")

    resolved_count = len(ranks_by_frontier)
    require(resolved_count + len(unresolved) == frontier_count, "frontierRoadCount does not match resolved+unresolved roads")

    print(
        f"valid crossing candidates: {data['pairId']} "
        f"({candidate_count} candidates across {frontier_count} frontier roads)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
