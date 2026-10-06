#!/usr/bin/env python3
"""Compile unproven cross-region crossing candidates from independent correlations.

Every usable Graph A x Graph B correlation pair is retained. Evidence only affects
ordering; heading/access/direction are never rejection criteria at this stage.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

SCHEMA = "roadpilot.crossing-candidates"
VERSION = 1
GENERATOR_NAME = "roadpilot-crossing-candidate-compiler"
GENERATOR_VERSION = "1"


def fail(message: str) -> None:
    raise SystemExit(message)


def load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"Could not read {path}: {exc}")
    if not isinstance(value, dict):
        fail("Correlation artifact must be an object")
    if value.get("schema") != "roadpilot.frontier-road-correlations" or value.get("version") != 1:
        fail("Unsupported frontier-road correlation artifact")
    return value


def finite(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        fail(f"{label} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        fail(f"{label} must be finite")
    return number


def heading_delta(a: Any, b: Any) -> float | None:
    if a is None or b is None:
        return None
    av = finite(a, "from heading")
    bv = finite(b, "to heading")
    delta = abs((av - bv) % 360.0)
    return min(delta, 360.0 - delta)


def haversine(a: dict[str, Any], b: dict[str, Any]) -> float:
    lat1 = finite(a.get("lat"), "from correlated lat")
    lng1 = finite(a.get("lng"), "from correlated lng")
    lat2 = finite(b.get("lat"), "to correlated lat")
    lng2 = finite(b.get("lng"), "to correlated lng")
    radius = 6371008.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    h = math.sin(dp / 2.0) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2.0) ** 2
    return radius * 2.0 * math.atan2(math.sqrt(h), math.sqrt(max(0.0, 1.0 - h)))


def normalized_names(edge: dict[str, Any]) -> dict[str, str]:
    names = edge.get("roadNames")
    if not isinstance(names, list):
        return {}
    result: dict[str, str] = {}
    for name in names:
        if not isinstance(name, str):
            continue
        clean = " ".join(name.split())
        if clean:
            result.setdefault(clean.casefold(), clean)
    return result


def shared_names(a: dict[str, Any], b: dict[str, Any]) -> list[str]:
    left = normalized_names(a)
    right = normalized_names(b)
    return sorted(
        [left[key] for key in left.keys() & right.keys()],
        key=str.casefold,
    )


def evidence_tier(
    both_match: bool,
    same_way: bool,
    one_match: bool,
    names: list[str],
) -> int:
    if both_match:
        return 0
    if same_way:
        return 1
    if one_match:
        return 2
    if names:
        return 3
    return 4


def edge_copy(edge: dict[str, Any]) -> dict[str, Any]:
    return {
        "correlationRank": int(edge.get("rank")),
        "wayMatch": bool(edge.get("wayMatch")),
        "correlatedCoordinate": dict(edge.get("correlatedCoordinate") or {}),
        "wayId": edge.get("wayId"),
        "percentAlong": edge.get("percentAlong"),
        "distanceMeters": finite(edge.get("distanceMeters"), "correlation distance"),
        "headingDegrees": edge.get("headingDegrees"),
        "linearReference": edge.get("linearReference"),
        "graphId": edge.get("graphId"),
        "roadNames": list(edge.get("roadNames") or []),
        "access": dict(edge.get("access") or {}),
        "roadClass": edge.get("roadClass"),
        "use": edge.get("use"),
    }


def candidate_id(
    pair_id: str,
    frontier_road_id: str,
    from_rank: int,
    to_rank: int,
    from_graph_fingerprint: str,
    to_graph_fingerprint: str,
) -> str:
    raw = (
        f"{pair_id}|{frontier_road_id}|{from_rank}|{to_rank}|"
        f"{from_graph_fingerprint}|{to_graph_fingerprint}"
    ).encode("utf-8")
    return "xpc1-" + hashlib.sha256(raw).hexdigest()[:24]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--correlations", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    data = load(args.correlations)
    pair_id = str(data.get("pairId") or "")
    from_region = str(data.get("fromRegionId") or "")
    to_region = str(data.get("toRegionId") or "")
    if pair_id != f"{from_region}__{to_region}":
        fail("Correlation pair identity is invalid")

    from_graph = data.get("fromGraph")
    to_graph = data.get("toGraph")
    if not isinstance(from_graph, dict) or not isinstance(to_graph, dict):
        fail("Correlation artifact is missing graph identity")
    from_fp = str(from_graph.get("graphFingerprint") or "")
    to_fp = str(to_graph.get("graphFingerprint") or "")
    if not from_fp or not to_fp:
        fail("Correlation artifact is missing graph fingerprints")

    correlations = data.get("correlations")
    if not isinstance(correlations, list):
        fail("correlations must be an array")

    all_candidates: list[dict[str, Any]] = []
    unresolved: list[str] = []

    for item_index, item in enumerate(correlations):
        if not isinstance(item, dict):
            fail(f"correlation[{item_index}] must be an object")
        frontier_id = str(item.get("frontierRoadId") or "")
        stable_way = item.get("wayId")
        if not frontier_id or not isinstance(stable_way, int) or stable_way <= 0:
            fail(f"correlation[{item_index}] has invalid frontier identity")

        from_side = item.get("fromGraph")
        to_side = item.get("toGraph")
        if not isinstance(from_side, dict) or not isinstance(to_side, dict):
            fail(f"correlation[{item_index}] missing side correlation")
        from_edges = from_side.get("candidates") if from_side.get("status") == "CORRELATED" else []
        to_edges = to_side.get("candidates") if to_side.get("status") == "CORRELATED" else []
        if not isinstance(from_edges, list) or not isinstance(to_edges, list) or not from_edges or not to_edges:
            unresolved.append(frontier_id)
            continue

        road_candidates: list[dict[str, Any]] = []
        for from_edge in from_edges:
            if not isinstance(from_edge, dict):
                continue
            for to_edge in to_edges:
                if not isinstance(to_edge, dict):
                    continue

                from_rank = int(from_edge.get("rank"))
                to_rank = int(to_edge.get("rank"))
                both_match = bool(from_edge.get("wayMatch")) and bool(to_edge.get("wayMatch"))
                one_match = bool(from_edge.get("wayMatch")) or bool(to_edge.get("wayMatch"))
                from_way = from_edge.get("wayId")
                to_way = to_edge.get("wayId")
                same_way = (
                    isinstance(from_way, int)
                    and isinstance(to_way, int)
                    and from_way > 0
                    and from_way == to_way
                )
                names = shared_names(from_edge, to_edge)
                separation = haversine(
                    dict(from_edge.get("correlatedCoordinate") or {}),
                    dict(to_edge.get("correlatedCoordinate") or {}),
                )
                combined_distance = finite(
                    from_edge.get("distanceMeters"), "from correlation distance"
                ) + finite(to_edge.get("distanceMeters"), "to correlation distance")
                delta = heading_delta(
                    from_edge.get("headingDegrees"),
                    to_edge.get("headingDegrees"),
                )
                tier = evidence_tier(both_match, same_way, one_match, names)

                road_candidates.append(
                    {
                        "id": candidate_id(
                            pair_id,
                            frontier_id,
                            from_rank,
                            to_rank,
                            from_fp,
                            to_fp,
                        ),
                        "candidateRank": 0,
                        "frontierRoadId": frontier_id,
                        "stableWayId": stable_way,
                        "crossingIndex": int(item.get("crossingIndex") or 0),
                        "crossingKind": str(item.get("crossingKind") or ""),
                        "frontierCoordinate": dict(item.get("frontierCoordinate") or {}),
                        "frontierHeadingDegrees": finite(
                            item.get("frontierHeadingDegrees"),
                            "frontier heading",
                        ),
                        "routingTags": dict(item.get("routingTags") or {}),
                        "fromEdge": edge_copy(from_edge),
                        "toEdge": edge_copy(to_edge),
                        "evidence": {
                            "tier": tier,
                            "bothMatchStableWay": both_match,
                            "sameCorrelatedWay": same_way,
                            "oneMatchesStableWay": one_match,
                            "sharedRoadNames": names,
                            "separationMeters": separation,
                            "combinedCorrelationDistanceMeters": combined_distance,
                            "headingDeltaDegrees": delta,
                        },
                    }
                )

        road_candidates.sort(
            key=lambda candidate: (
                candidate["evidence"]["tier"],
                candidate["evidence"]["combinedCorrelationDistanceMeters"],
                candidate["evidence"]["separationMeters"],
                candidate["fromEdge"]["correlationRank"],
                candidate["toEdge"]["correlationRank"],
            )
        )
        for rank, candidate in enumerate(road_candidates):
            candidate["candidateRank"] = rank
        all_candidates.extend(road_candidates)

    artifact = {
        "schema": SCHEMA,
        "version": VERSION,
        "pairId": pair_id,
        "fromRegionId": from_region,
        "toRegionId": to_region,
        "fromBoundaryFingerprint": data["fromBoundaryFingerprint"],
        "toBoundaryFingerprint": data["toBoundaryFingerprint"],
        "fromGraph": from_graph,
        "toGraph": to_graph,
        "generator": {"name": GENERATOR_NAME, "version": GENERATOR_VERSION},
        "validationState": "UNPROVEN",
        "frontierRoadCount": len(correlations),
        "candidateCount": len(all_candidates),
        "unresolvedFrontierRoadIds": sorted(set(unresolved)),
        "candidates": all_candidates,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(
        f"{pair_id}: {len(all_candidates)} unproven candidates from "
        f"{len(correlations)} frontier roads; unresolved={len(set(unresolved))}"
    )
    print(f"wrote: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
