#!/usr/bin/env python3
"""Validate a RoadPilot boundary-edge inventory produced from a finished Valhalla graph."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

AUTO_ACCESS_MASK = 1
MOTORCYCLE_ACCESS_MASK = 1024


def finite(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def expected_modes(forward_access: int, reverse_access: int) -> set[str]:
    access = int(forward_access) | int(reverse_access)
    result = set()
    if access & MOTORCYCLE_ACCESS_MASK:
        result.add("MOTORCYCLE")
    if access & AUTO_ACCESS_MASK:
        result.add("CAR")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", required=True, type=Path)
    args = parser.parse_args()

    data = json.loads(args.inventory.read_text(encoding="utf-8"))
    errors = []
    if (
        data.get("schema") != "roadpilot.boundary-edge-inventory"
        or data.get("version") != 1
    ):
        errors.append("unsupported schema/version")
    if not data.get("regionId") or not data.get("graphFingerprint"):
        errors.append("missing region/fingerprint")

    graph_ids = set()
    edges = data.get("edges", [])
    if not isinstance(edges, list):
        errors.append("edges must be an array")
        edges = []

    for index, edge in enumerate(edges):
        graph_id = edge.get("graphId")
        if not isinstance(graph_id, int) or graph_id <= 0:
            errors.append(f"edge[{index}] invalid graphId")
        elif graph_id in graph_ids:
            errors.append(f"edge[{index}] duplicate graphId")
        graph_ids.add(graph_id)

        for key in (
            "opposingGraphId",
            "sourceNodeGraphId",
            "endNodeGraphId",
            "wayId",
        ):
            if not isinstance(edge.get(key), int) or edge[key] <= 0:
                errors.append(f"edge[{index}] invalid {key}")

        for key in ("forwardAccess", "reverseAccess", "roadClass", "use"):
            if not isinstance(edge.get(key), int) or edge[key] < 0:
                errors.append(f"edge[{index}] invalid {key}")

        for key in ("anchorCoordinate", "innerCoordinate"):
            coordinate = edge.get(key, {})
            lat, lng = coordinate.get("lat"), coordinate.get("lng")
            if (
                not finite(lat)
                or not -90 <= lat <= 90
                or not finite(lng)
                or not -180 <= lng <= 180
            ):
                errors.append(f"edge[{index}] invalid {key}")

        heading = edge.get("headingDegrees")
        if not finite(heading) or not 0 <= heading < 360:
            errors.append(f"edge[{index}] invalid headingDegrees")

        modes = set(edge.get("allowedTravelModes", []))
        expected = expected_modes(
            edge.get("forwardAccess", 0), edge.get("reverseAccess", 0)
        )
        if modes != expected or not modes:
            errors.append(
                f"edge[{index}] allowedTravelModes does not match access masks"
            )

    if errors:
        raise SystemExit("\n".join(errors))

    print(
        f"valid boundary edge inventory: {args.inventory} "
        f"({len(edges)} edges)"
    )


if __name__ == "__main__":
    main()
