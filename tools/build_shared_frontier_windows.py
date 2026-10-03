#!/usr/bin/env python3
"""Create continuous graph-scan windows along the shared frontier of two Geofabrik extracts.

Unlike the old journey-scoped F8 seeds, this build-time tool covers the entire neighboring frontier.
It densifies both exact Geofabrik polygon boundaries, pairs nearby samples, and emits overlapping
bounding boxes large enough that no point on a retained frontier segment falls outside all windows.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Iterable

EARTH_RADIUS_M = 6_371_008.8


def normalize_url(url: str) -> str:
    return url.strip().rstrip("/").replace("http://", "https://")


def distance_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2.0) ** 2
    )
    return 2.0 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(h)))


def interpolate(
    a: tuple[float, float],
    b: tuple[float, float],
    fraction: float,
) -> tuple[float, float]:
    return (
        a[0] + (b[0] - a[0]) * fraction,
        a[1] + (b[1] - a[1]) * fraction,
    )


def feature_geometry(index: dict[str, Any], pbf_url: str) -> dict[str, Any]:
    target = normalize_url(pbf_url)
    for feature in index.get("features", []):
        properties = feature.get("properties") or {}
        urls = properties.get("urls") or {}
        if normalize_url(str(urls.get("pbf", ""))) == target:
            geometry = feature.get("geometry")
            if isinstance(geometry, dict):
                return geometry
    raise ValueError(f"Geofabrik index has no geometry for {pbf_url}")


def rings_from_geometry(geometry: dict[str, Any]) -> list[list[tuple[float, float]]]:
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")
    rings: list[list[tuple[float, float]]] = []

    def convert_ring(raw: Iterable[Any]) -> list[tuple[float, float]]:
        result: list[tuple[float, float]] = []
        for item in raw:
            if (
                isinstance(item, list)
                and len(item) >= 2
                and isinstance(item[0], (int, float))
                and isinstance(item[1], (int, float))
            ):
                # GeoJSON order is longitude, latitude.
                result.append((float(item[1]), float(item[0])))
        return result

    if geometry_type == "Polygon" and isinstance(coordinates, list):
        # Every ring matters. An extract can use holes around another regional extract.
        rings.extend(
            ring
            for raw in coordinates
            if isinstance(raw, list) and len((ring := convert_ring(raw))) >= 2
        )
    elif geometry_type == "MultiPolygon" and isinstance(coordinates, list):
        for polygon in coordinates:
            if not isinstance(polygon, list):
                continue
            rings.extend(
                ring
                for raw in polygon
                if isinstance(raw, list) and len((ring := convert_ring(raw))) >= 2
            )
    else:
        raise ValueError(f"Unsupported Geofabrik geometry type: {geometry_type!r}")

    if not rings:
        raise ValueError("Geofabrik geometry has no usable boundary rings")
    return rings


def densify_ring(
    ring: list[tuple[float, float]],
    spacing_m: float,
) -> list[tuple[float, float]]:
    if spacing_m <= 0:
        raise ValueError("sample spacing must be positive")
    if len(ring) < 2:
        return ring[:]

    points: list[tuple[float, float]] = []
    for index in range(1, len(ring)):
        a, b = ring[index - 1], ring[index]
        segment_m = distance_m(a, b)
        divisions = max(1, math.ceil(segment_m / spacing_m))
        if not points:
            points.append(a)
        for step in range(1, divisions + 1):
            points.append(interpolate(a, b, step / divisions))
    return points


def densified_geometry_points(
    geometry: dict[str, Any],
    spacing_m: float,
) -> list[tuple[float, float]]:
    return [
        point
        for ring in rings_from_geometry(geometry)
        for point in densify_ring(ring, spacing_m)
    ]


def build_spatial_index(
    points: list[tuple[float, float]],
    cell_m: float,
) -> tuple[dict[tuple[int, int], list[tuple[float, float]]], float, float]:
    if not points:
        raise ValueError("cannot index an empty boundary")
    reference_lat = sum(point[0] for point in points) / len(points)
    lat_cell = cell_m / 111_320.0
    lon_scale = max(0.1, math.cos(math.radians(reference_lat)))
    lon_cell = cell_m / (111_320.0 * lon_scale)
    index: dict[tuple[int, int], list[tuple[float, float]]] = {}
    for point in points:
        key = (
            math.floor(point[0] / lat_cell),
            math.floor(point[1] / lon_cell),
        )
        index.setdefault(key, []).append(point)
    return index, lat_cell, lon_cell


def nearest_within(
    point: tuple[float, float],
    index: dict[tuple[int, int], list[tuple[float, float]]],
    lat_cell: float,
    lon_cell: float,
    max_distance_m: float,
) -> tuple[tuple[float, float], float] | None:
    base = (
        math.floor(point[0] / lat_cell),
        math.floor(point[1] / lon_cell),
    )
    best: tuple[float, float] | None = None
    best_distance = float("inf")
    # cell size equals max distance, so adjacent cells are sufficient.
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            for candidate in index.get((base[0] + dy, base[1] + dx), ()):
                d = distance_m(point, candidate)
                if d < best_distance:
                    best_distance = d
                    best = candidate
    if best is None or best_distance > max_distance_m:
        return None
    return best, best_distance


def paired_frontier_samples(
    a_points: list[tuple[float, float]],
    b_points: list[tuple[float, float]],
    neighbor_distance_m: float,
) -> list[tuple[tuple[float, float], tuple[float, float], float]]:
    b_index, b_lat_cell, b_lon_cell = build_spatial_index(
        b_points, neighbor_distance_m
    )
    a_index, a_lat_cell, a_lon_cell = build_spatial_index(
        a_points, neighbor_distance_m
    )

    pairs: list[tuple[tuple[float, float], tuple[float, float], float]] = []
    for point in a_points:
        found = nearest_within(
            point,
            b_index,
            b_lat_cell,
            b_lon_cell,
            neighbor_distance_m,
        )
        if found is not None:
            pairs.append((point, found[0], found[1]))

    # Also walk B -> A. This catches short frontier fragments that happen to be sparsely
    # represented on one polygon but densely represented on the other.
    for point in b_points:
        found = nearest_within(
            point,
            a_index,
            a_lat_cell,
            a_lon_cell,
            neighbor_distance_m,
        )
        if found is not None:
            pairs.append((found[0], point, found[1]))

    return pairs


def make_window(
    a: tuple[float, float],
    b: tuple[float, float],
    radius_m: float,
) -> dict[str, float]:
    center_lat = (a[0] + b[0]) * 0.5
    lat_pad = radius_m / 111_320.0
    lon_pad = radius_m / (
        111_320.0 * max(0.1, math.cos(math.radians(center_lat)))
    )
    return {
        "minLat": min(a[0], b[0]) - lat_pad,
        "maxLat": max(a[0], b[0]) + lat_pad,
        "minLng": min(a[1], b[1]) - lon_pad,
        "maxLng": max(a[1], b[1]) + lon_pad,
    }


def dedupe_windows(
    pairs: list[tuple[tuple[float, float], tuple[float, float], float]],
    radius_m: float,
) -> list[dict[str, float]]:
    # Quantize by approximately one scan radius. Neighboring dense samples then collapse into a
    # compact set of overlapping windows while retaining continuous frontier coverage.
    buckets: dict[tuple[int, int], dict[str, float]] = {}
    for a, b, _ in pairs:
        center_lat = (a[0] + b[0]) * 0.5
        center_lon = (a[1] + b[1]) * 0.5
        lat_step = radius_m / 111_320.0
        lon_step = radius_m / (
            111_320.0 * max(0.1, math.cos(math.radians(center_lat)))
        )
        key = (
            round(center_lat / lat_step),
            round(center_lon / lon_step),
        )
        window = make_window(a, b, radius_m)
        previous = buckets.get(key)
        if previous is None:
            buckets[key] = window
        else:
            previous["minLat"] = min(previous["minLat"], window["minLat"])
            previous["maxLat"] = max(previous["maxLat"], window["maxLat"])
            previous["minLng"] = min(previous["minLng"], window["minLng"])
            previous["maxLng"] = max(previous["maxLng"], window["maxLng"])

    return sorted(
        buckets.values(),
        key=lambda item: (
            item["minLat"],
            item["minLng"],
            item["maxLat"],
            item["maxLng"],
        ),
    )


def build_windows(
    index: dict[str, Any],
    pair_config: dict[str, Any],
) -> dict[str, Any]:
    frontier = pair_config["frontierSearch"]
    spacing = float(frontier["sampleSpacingMeters"])
    neighbor_distance = float(frontier["neighborDistanceMeters"])
    radius = float(frontier["windowRadiusMeters"])
    if min(spacing, neighbor_distance, radius) <= 0:
        raise ValueError("frontier search distances must be positive")

    a_geometry = feature_geometry(index, pair_config["fromPbfUrl"])
    b_geometry = feature_geometry(index, pair_config["toPbfUrl"])
    a_points = densified_geometry_points(a_geometry, spacing)
    b_points = densified_geometry_points(b_geometry, spacing)
    pairs = paired_frontier_samples(a_points, b_points, neighbor_distance)
    if not pairs:
        raise ValueError("Geofabrik polygons do not expose a neighboring frontier")

    windows = dedupe_windows(pairs, radius)
    if not windows:
        raise ValueError("frontier pairing produced no scan windows")

    return {
        "schema": "roadpilot.shared-frontier-windows",
        "version": 1,
        "pairId": pair_config["id"],
        "fromRegionId": pair_config["fromRegionId"],
        "toRegionId": pair_config["toRegionId"],
        "source": {
            "index": "geofabrik-index-v1",
            "fromPbfUrl": pair_config["fromPbfUrl"],
            "toPbfUrl": pair_config["toPbfUrl"],
        },
        "sampling": {
            "sampleSpacingMeters": spacing,
            "neighborDistanceMeters": neighbor_distance,
            "windowRadiusMeters": radius,
            "pairedSamples": len(pairs),
        },
        "windows": windows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--geofabrik-index", required=True, type=Path)
    parser.add_argument("--pair-config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    index = json.loads(args.geofabrik_index.read_text(encoding="utf-8"))
    pair_config = json.loads(args.pair_config.read_text(encoding="utf-8"))
    output = build_windows(index, pair_config)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(
        f"{output['pairId']}: {len(output['windows'])} continuous scan windows "
        f"from {output['sampling']['pairedSamples']} paired boundary samples"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
