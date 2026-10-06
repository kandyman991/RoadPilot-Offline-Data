#!/usr/bin/env python3
"""Validate RoadPilot graph-bound frontier-road correlations."""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any

SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
ROAD_ID = re.compile(r"^fri1-[0-9a-f]{24}$")
STATUSES = {"CORRELATED", "NO_CANDIDATES", "LOCATE_FAILED"}
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
    fingerprint = value.get("graphFingerprint")
    require(
        isinstance(fingerprint, str) and bool(SHA256.fullmatch(fingerprint)),
        f"{label}.graphFingerprint invalid",
    )
    require(
        bool(str(value.get("primaryGeofabrikId") or "").strip()),
        f"{label}.primaryGeofabrikId required",
    )


def candidate(value: Any, stable_way_id: int, expected_rank: int, label: str) -> bool:
    require(isinstance(value, dict), f"{label} must be an object")
    require(value.get("rank") == expected_rank, f"{label}.rank must be contiguous")
    way_match = value.get("wayMatch")
    require(isinstance(way_match, bool), f"{label}.wayMatch must be boolean")
    coordinate(value.get("correlatedCoordinate"), f"{label}.correlatedCoordinate")

    way_id = value.get("wayId")
    if way_id is not None:
        require(
            isinstance(way_id, int) and not isinstance(way_id, bool) and way_id > 0,
            f"{label}.wayId invalid",
        )
    require(
        way_match == (way_id == stable_way_id),
        f"{label}.wayMatch does not match way identity",
    )

    percent = value.get("percentAlong")
    if percent is not None:
        p = finite(percent, f"{label}.percentAlong")
        require(0 <= p <= 1, f"{label}.percentAlong invalid")

    distance = finite(value.get("distanceMeters"), f"{label}.distanceMeters")
    require(distance >= 0, f"{label}.distanceMeters invalid")

    heading = value.get("headingDegrees")
    if heading is not None:
        h = finite(heading, f"{label}.headingDegrees")
        require(0 <= h < 360, f"{label}.headingDegrees invalid")

    linear_reference = value.get("linearReference")
    require(
        linear_reference is None or isinstance(linear_reference, str),
        f"{label}.linearReference invalid",
    )

    graph_id = value.get("graphId")
    if graph_id is not None:
        require(
            isinstance(graph_id, int) and not isinstance(graph_id, bool) and graph_id > 0,
            f"{label}.graphId invalid",
        )

    names = value.get("roadNames")
    require(isinstance(names, list), f"{label}.roadNames must be an array")
    require(
        all(isinstance(item, str) for item in names),
        f"{label}.roadNames invalid",
    )
    require(len(names) == len(set(names)), f"{label}.roadNames contains duplicates")

    access = value.get("access")
    require(isinstance(access, dict), f"{label}.access must be an object")
    require(
        all(isinstance(key, str) and isinstance(enabled, bool) for key, enabled in access.items()),
        f"{label}.access invalid",
    )

    for key in ("roadClass", "use"):
        item = value.get(key)
        require(item is None or isinstance(item, str), f"{label}.{key} invalid")
    return way_match


def side(value: Any, stable_way_id: int, label: str) -> None:
    require(isinstance(value, dict), f"{label} must be an object")
    status = value.get("status")
    require(status in STATUSES, f"{label}.status invalid")
    count = value.get("candidateCount")
    same_count = value.get("sameWayCandidateCount")
    require(
        isinstance(count, int) and not isinstance(count, bool) and count >= 0,
        f"{label}.candidateCount invalid",
    )
    require(
        isinstance(same_count, int) and not isinstance(same_count, bool) and same_count >= 0,
        f"{label}.sameWayCandidateCount invalid",
    )
    candidates = value.get("candidates")
    require(isinstance(candidates, list), f"{label}.candidates must be an array")
    require(len(candidates) == count, f"{label}.candidateCount mismatch")

    matches = 0
    encountered_non_match = False
    for index, item in enumerate(candidates):
        matched = candidate(item, stable_way_id, index, f"{label}.candidates[{index}]")
        if matched:
            require(
                not encountered_non_match,
                f"{label} same-way evidence must rank before non-matching edges",
            )
            matches += 1
        else:
            encountered_non_match = True
    require(matches == same_count, f"{label}.sameWayCandidateCount mismatch")

    if status == "CORRELATED":
        require(count > 0, f"{label} CORRELATED requires candidates")
        require("error" not in value, f"{label} CORRELATED must not contain error")
    elif status == "NO_CANDIDATES":
        require(count == 0, f"{label} NO_CANDIDATES must be empty")
        require("error" not in value, f"{label} NO_CANDIDATES must not contain error")
    else:
        require(count == 0, f"{label} LOCATE_FAILED must be empty")
        require(bool(str(value.get("error") or "").strip()), f"{label} LOCATE_FAILED requires error")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", required=True, type=Path)
    args = parser.parse_args()

    data = json.loads(args.artifact.read_text(encoding="utf-8"))
    require(isinstance(data, dict), "artifact must be an object")
    require(data.get("schema") == "roadpilot.frontier-road-correlations", "unexpected schema")
    require(data.get("version") == 1, "version must be 1")

    from_region = str(data.get("fromRegionId") or "")
    to_region = str(data.get("toRegionId") or "")
    require(from_region and to_region and from_region != to_region, "invalid region pair")
    require(data.get("pairId") == f"{from_region}__{to_region}", "pairId mismatch")

    for key in ("fromBoundaryFingerprint", "toBoundaryFingerprint"):
        value = data.get(key)
        require(
            isinstance(value, str) and bool(SHA256.fullmatch(value)),
            f"{key} invalid",
        )

    graph(data.get("fromGraph"), from_region, "fromGraph")
    graph(data.get("toGraph"), to_region, "toGraph")

    generator = data.get("generator")
    require(isinstance(generator, dict), "generator must be an object")
    require(bool(str(generator.get("name") or "").strip()), "generator.name required")
    require(bool(str(generator.get("version") or "").strip()), "generator.version required")

    correlations = data.get("correlations")
    require(isinstance(correlations, list), "correlations must be an array")
    ids = set()
    for index, item in enumerate(correlations):
        label = f"correlation[{index}]"
        require(isinstance(item, dict), f"{label} must be an object")
        road_id = item.get("frontierRoadId")
        require(
            isinstance(road_id, str) and bool(ROAD_ID.fullmatch(road_id)),
            f"{label}.frontierRoadId invalid",
        )
        require(road_id not in ids, f"{label}.frontierRoadId duplicated")
        ids.add(road_id)

        way_id = item.get("wayId")
        require(
            isinstance(way_id, int) and not isinstance(way_id, bool) and way_id > 0,
            f"{label}.wayId invalid",
        )
        crossing_index = item.get("crossingIndex")
        require(
            isinstance(crossing_index, int)
            and not isinstance(crossing_index, bool)
            and crossing_index >= 0,
            f"{label}.crossingIndex invalid",
        )
        require(item.get("crossingKind") in KINDS, f"{label}.crossingKind invalid")
        coordinate(item.get("frontierCoordinate"), f"{label}.frontierCoordinate")
        heading = finite(item.get("frontierHeadingDegrees"), f"{label}.frontierHeadingDegrees")
        require(0 <= heading < 360, f"{label}.frontierHeadingDegrees invalid")
        tags = item.get("routingTags")
        require(isinstance(tags, dict), f"{label}.routingTags must be an object")
        require(
            all(isinstance(key, str) and isinstance(value, str) for key, value in tags.items()),
            f"{label}.routingTags invalid",
        )
        side(item.get("fromGraph"), way_id, f"{label}.fromGraph")
        side(item.get("toGraph"), way_id, f"{label}.toGraph")

    print(
        f"valid frontier road correlations: {data['pairId']} "
        f"({len(correlations)} frontier anchors)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
