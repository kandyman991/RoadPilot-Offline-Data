#!/usr/bin/env python3
"""Validate a stable RoadPilot frontier-road inventory."""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any

SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
ROAD_ID = re.compile(r"^fri1-[0-9a-f]{24}$")
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
    require(-90 <= lat <= 90, f"{label}.lat is invalid")
    require(-180 <= lng <= 180, f"{label}.lng is invalid")


def line_string(value: Any, label: str) -> None:
    require(isinstance(value, dict), f"{label} must be an object")
    require(value.get("type") == "LineString", f"{label}.type must be LineString")
    coordinates = value.get("coordinates")
    require(
        isinstance(coordinates, list) and len(coordinates) >= 2,
        f"{label}.coordinates must contain at least two points",
    )
    for index, point in enumerate(coordinates):
        require(
            isinstance(point, list) and len(point) == 2,
            f"{label}.coordinates[{index}] must contain lng/lat",
        )
        lng = finite(point[0], f"{label}.coordinates[{index}][0]")
        lat = finite(point[1], f"{label}.coordinates[{index}][1]")
        require(-180 <= lng <= 180, f"{label}.coordinates[{index}] lng invalid")
        require(-90 <= lat <= 90, f"{label}.coordinates[{index}] lat invalid")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", required=True, type=Path)
    args = parser.parse_args()

    data = json.loads(args.inventory.read_text(encoding="utf-8"))
    require(isinstance(data, dict), "inventory must be an object")
    require(data.get("schema") == "roadpilot.frontier-road-inventory", "unexpected schema")
    require(data.get("version") == 1, "version must be 1")

    from_region = str(data.get("fromRegionId") or "")
    to_region = str(data.get("toRegionId") or "")
    require(from_region and to_region and from_region != to_region, "invalid region pair")
    require(
        data.get("pairId") == f"{from_region}__{to_region}",
        "pairId must match directed region pair",
    )

    for key in ("fromBoundaryFingerprint", "toBoundaryFingerprint"):
        value = data.get(key)
        require(
            isinstance(value, str) and bool(SHA256.fullmatch(value)),
            f"{key} must be sha256:<64 lowercase hex>",
        )

    source = data.get("source")
    require(isinstance(source, dict), "source must be an object")
    require(
        set(source) == {"osmSha256", "fromPolygonSha256", "toPolygonSha256"},
        "source must contain only OSM/from/to hashes",
    )
    for key, value in source.items():
        require(
            isinstance(value, str) and bool(SHA256.fullmatch(value)),
            f"source.{key} must be sha256:<64 lowercase hex>",
        )

    generator = data.get("generator")
    require(isinstance(generator, dict), "generator must be an object")
    require(bool(str(generator.get("name") or "").strip()), "generator.name required")
    require(bool(str(generator.get("version") or "").strip()), "generator.version required")

    roads = data.get("roads")
    require(isinstance(roads, list), "roads must be an array")
    ids = set()
    index_by_way: dict[int, set[int]] = {}
    for index, road in enumerate(roads):
        label = f"road[{index}]"
        require(isinstance(road, dict), f"{label} must be an object")
        road_id = road.get("id")
        require(
            isinstance(road_id, str) and bool(ROAD_ID.fullmatch(road_id)),
            f"{label}.id is invalid",
        )
        require(road_id not in ids, f"{label}.id is duplicated")
        ids.add(road_id)

        way_id = road.get("wayId")
        require(
            isinstance(way_id, int) and not isinstance(way_id, bool) and way_id > 0,
            f"{label}.wayId must be positive",
        )
        crossing_index = road.get("crossingIndex")
        require(
            isinstance(crossing_index, int)
            and not isinstance(crossing_index, bool)
            and crossing_index >= 0,
            f"{label}.crossingIndex is invalid",
        )
        seen_indexes = index_by_way.setdefault(way_id, set())
        require(
            crossing_index not in seen_indexes,
            f"{label}.crossingIndex duplicates another crossing on the same way",
        )
        seen_indexes.add(crossing_index)

        kind = road.get("crossingKind")
        require(kind in KINDS, f"{label}.crossingKind is invalid")
        coordinate(road.get("crossingCoordinate"), f"{label}.crossingCoordinate")

        heading = finite(road.get("headingDegrees"), f"{label}.headingDegrees")
        require(0 <= heading < 360, f"{label}.headingDegrees is invalid")

        overlap = road.get("overlapLengthMeters")
        if kind == "FRONTIER_OVERLAP":
            overlap_value = finite(overlap, f"{label}.overlapLengthMeters")
            require(overlap_value > 0, f"{label}.overlapLengthMeters must be positive")
        else:
            require(overlap is None, f"{label} CROSSING must not contain overlapLengthMeters")

        tags = road.get("routingTags")
        require(isinstance(tags, dict), f"{label}.routingTags must be an object")
        require(bool(str(tags.get("highway") or "").strip()), f"{label} missing highway tag")
        require(
            all(isinstance(key, str) and isinstance(value, str) for key, value in tags.items()),
            f"{label}.routingTags must contain string values",
        )
        line_string(road.get("snippet"), f"{label}.snippet")

        forbidden = {
            "graphId",
            "opposingGraphId",
            "sourceNodeGraphId",
            "endNodeGraphId",
        }
        require(
            forbidden.isdisjoint(road),
            f"{label} contains graph-local identity in the stable inventory",
        )

    print(
        f"valid frontier road inventory: {data['pairId']} "
        f"({len(roads)} physical anchors)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
