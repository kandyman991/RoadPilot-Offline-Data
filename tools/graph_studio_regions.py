#!/usr/bin/env python3
"""Geofabrik catalog/discovery helpers for RoadPilot Graph Studio."""

from __future__ import annotations

import argparse
import json
import math
import os
import time
import urllib.request
from pathlib import Path
from typing import Any

from pyproj import CRS, Transformer
from shapely.geometry import Point, mapping, shape
from shapely.ops import transform

from build_routing_region import parse_poly

INDEX_URL = "https://download.geofabrik.de/index-v1.json"
USER_AGENT = "RoadPilot-Graph-Studio/0.1"
DEFAULT_CACHE_SECONDS = 12 * 60 * 60


def fail(message: str) -> None:
    raise SystemExit(message)


def download(url: str, destination: Path, *, refresh: bool = False) -> Path:
    if (
        not refresh
        and destination.is_file()
        and destination.stat().st_size > 0
        and time.time() - destination.stat().st_mtime < DEFAULT_CACHE_SECONDS
    ):
        return destination

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    temporary.unlink(missing_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=90) as response, temporary.open("wb") as out:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)
    if temporary.stat().st_size <= 0:
        fail(f"Downloaded empty file: {url}")
    temporary.replace(destination)
    return destination


def load_index(cache_dir: Path, refresh: bool) -> dict[str, Any]:
    path = download(INDEX_URL, cache_dir / "index-v1.json", refresh=refresh)
    try:
        root = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"Could not read Geofabrik index: {exc}")
    if root.get("type") != "FeatureCollection" or not isinstance(root.get("features"), list):
        fail("Unexpected Geofabrik index format")
    return root


def feature_id(feature: dict[str, Any]) -> str:
    return str(feature.get("properties", {}).get("id") or "").strip()


ROOT_CONTAINERS = {
    "africa",
    "asia",
    "australia-oceania",
    "central-america",
    "europe",
    "north-america",
    "south-america",
}


def canonical_id(node_id: str, nodes: dict[str, dict[str, Any]]) -> str:
    parts: list[str] = []
    current_id = node_id
    seen: set[str] = set()
    while current_id and current_id not in seen:
        seen.add(current_id)
        parts.append(current_id)
        feature = nodes.get(current_id)
        if feature is None:
            break
        current_id = str(feature.get("properties", {}).get("parent") or "").strip()
    parts.reverse()
    if len(parts) > 1 and parts[0] in ROOT_CONTAINERS:
        parts = parts[1:]
    return "/".join(parts)


def canonical_lookup(nodes: dict[str, dict[str, Any]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw_id in nodes:
        canonical = canonical_id(raw_id, nodes)
        if canonical:
            if canonical in result and result[canonical] != raw_id:
                fail(f"Duplicate canonical Geofabrik id: {canonical}")
            result[canonical] = raw_id
    return result


def pbf_url(feature: dict[str, Any]) -> str | None:
    value = feature.get("properties", {}).get("urls", {}).get("pbf")
    return str(value).strip() if value else None


def poly_url_for_pbf(url: str) -> str:
    suffix = "-latest.osm.pbf"
    if not url.endswith(suffix):
        fail(f"Cannot derive Geofabrik .poly URL from {url}")
    return url[: -len(suffix)] + ".poly"


def nodes_by_id(root: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        feature_id(feature): feature
        for feature in root["features"]
        if feature_id(feature)
    }


def children_by_parent(nodes: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    children: dict[str, list[str]] = {}
    for node_id, feature in nodes.items():
        parent = str(feature.get("properties", {}).get("parent") or "").strip()
        if parent:
            children.setdefault(parent, []).append(node_id)
    return children


def downloadable_leaf_ids(
    nodes: dict[str, dict[str, Any]],
    children: dict[str, list[str]],
) -> list[str]:
    memo: dict[str, bool] = {}

    def has_downloadable_descendant(node_id: str) -> bool:
        if node_id in memo:
            return memo[node_id]
        result = False
        for child_id in children.get(node_id, []):
            child = nodes.get(child_id)
            if child is None:
                continue
            if pbf_url(child) or has_downloadable_descendant(child_id):
                result = True
                break
        memo[node_id] = result
        return result

    return sorted(
        node_id
        for node_id, feature in nodes.items()
        if pbf_url(feature) and not has_downloadable_descendant(node_id)
    )


def country_info(
    feature: dict[str, Any],
    nodes: dict[str, dict[str, Any]],
) -> tuple[str | None, str | None]:
    current: dict[str, Any] | None = feature
    seen: set[str] = set()
    while current is not None:
        props = current.get("properties", {})
        node_id = str(props.get("id") or "")
        if node_id in seen:
            break
        seen.add(node_id)
        iso = props.get("iso3166-1:alpha2")
        has_iso = (
            isinstance(iso, list) and len(iso) > 0
        ) or (isinstance(iso, str) and bool(iso.strip()))
        if has_iso:
            return node_id or None, str(props.get("name") or node_id) or None
        parent = str(props.get("parent") or "").strip()
        current = nodes.get(parent) if parent else None
    return None, None


def geometry_for(feature: dict[str, Any]):
    geometry = feature.get("geometry")
    if not geometry:
        fail(f"Geofabrik feature {feature_id(feature)} has no geometry")
    result = shape(geometry)
    if result.is_empty:
        fail(f"Geofabrik feature {feature_id(feature)} has empty geometry")
    if not result.is_valid:
        result = result.buffer(0)
    return result


def metric_buffer(geometry, buffer_km: float):
    if not math.isfinite(buffer_km) or buffer_km <= 0 or buffer_km > 100:
        fail("Border buffer must be greater than 0 and no more than 100 km")
    center = geometry.centroid
    local = CRS.from_proj4(
        f"+proj=aeqd +lat_0={center.y} +lon_0={center.x} +datum=WGS84 +units=m +no_defs"
    )
    forward = Transformer.from_crs("EPSG:4326", local, always_xy=True).transform
    backward = Transformer.from_crs(local, "EPSG:4326", always_xy=True).transform
    return transform(backward, transform(forward, geometry).buffer(buffer_km * 1000.0))


def bounds_dict(geometry) -> dict[str, float]:
    min_lng, min_lat, max_lng, max_lat = geometry.bounds
    return {
        "minLat": min_lat,
        "maxLat": max_lat,
        "minLng": min_lng,
        "maxLng": max_lng,
    }


def catalog_payload(root: dict[str, Any]) -> list[dict[str, Any]]:
    nodes = nodes_by_id(root)
    children = children_by_parent(nodes)
    result = []
    for node_id in downloadable_leaf_ids(nodes, children):
        feature = nodes[node_id]
        public_id = canonical_id(node_id, nodes)
        url = pbf_url(feature)
        if not url:
            continue
        geometry = geometry_for(feature)
        country_id, country_name = country_info(feature, nodes)
        props = feature.get("properties", {})
        result.append(
            {
                "id": public_id,
                "indexId": node_id,
                "name": str(props.get("name") or node_id),
                "parent": str(props.get("parent") or "") or None,
                "pbfUrl": url,
                "polygonUrl": poly_url_for_pbf(url),
                "countryId": country_id,
                "countryName": country_name,
                "bounds": bounds_dict(geometry),
            }
        )
    result.sort(key=lambda item: ((item.get("countryName") or ""), item["name"], item["id"]))
    return result


def exact_primary_geometry(
    primary: dict[str, Any],
    cache_dir: Path,
    refresh: bool,
):
    url = pbf_url(primary)
    if not url:
        fail(f"Geofabrik region {feature_id(primary)} has no PBF URL")
    poly_url = poly_url_for_pbf(url)
    safe_name = feature_id(primary).replace("/", "__")
    poly_path = download(poly_url, cache_dir / "polygons" / f"{safe_name}.poly", refresh=refresh)
    return parse_poly(poly_path), poly_url


def preview_payload(
    root: dict[str, Any],
    region_id: str,
    buffer_km: float,
    cache_dir: Path,
    refresh: bool,
) -> dict[str, Any]:
    nodes = nodes_by_id(root)
    children = children_by_parent(nodes)
    lookup = canonical_lookup(nodes)
    primary_raw_id = lookup.get(region_id)
    if primary_raw_id is None and region_id in nodes:
        primary_raw_id = region_id
        region_id = canonical_id(primary_raw_id, nodes)
    if primary_raw_id is None:
        fail(f"Unknown Geofabrik region: {region_id}")
    primary = nodes[primary_raw_id]
    if primary_raw_id not in set(downloadable_leaf_ids(nodes, children)):
        fail(
            f"{region_id} is not a smallest downloadable Geofabrik extract. "
            "Graph Studio only creates independent packs from leaf extracts."
        )

    exact_geometry, poly_url = exact_primary_geometry(primary, cache_dir, refresh)
    buffered = metric_buffer(exact_geometry, buffer_km)
    leaf_ids = downloadable_leaf_ids(nodes, children)

    sources = []
    for candidate_id in leaf_ids:
        feature = nodes[candidate_id]
        candidate_public_id = canonical_id(candidate_id, nodes)
        candidate_geometry = geometry_for(feature)
        if not candidate_geometry.intersects(buffered):
            continue
        url = pbf_url(feature)
        if not url:
            continue
        intersection = candidate_geometry.intersection(buffered)
        sources.append(
            {
                "id": candidate_public_id,
                "indexId": candidate_id,
                "name": str(feature.get("properties", {}).get("name") or candidate_id),
                "pbfUrl": url,
                "polygonUrl": poly_url_for_pbf(url),
                "primary": candidate_id == primary_raw_id,
                "intersectionArea": float(intersection.area) if not intersection.is_empty else 0.0,
                "geometry": mapping(candidate_geometry),
            }
        )

    sources.sort(key=lambda item: (not item["primary"], -item["intersectionArea"], item["id"]))
    primary_url = pbf_url(primary)
    country_id, country_name = country_info(primary, nodes)
    props = primary.get("properties", {})

    return {
        "geofabrikId": region_id,
        "name": str(props.get("name") or region_id),
        "countryId": country_id,
        "countryName": country_name,
        "pbfUrl": primary_url,
        "polygonUrl": poly_url,
        "borderBufferKm": buffer_km,
        "bounds": bounds_dict(exact_geometry),
        "primaryGeometry": mapping(exact_geometry),
        "bufferGeometry": mapping(buffered),
        "sources": sources,
    }


def validate_config_geometry(config_path: Path, cache_dir: Path, refresh: bool) -> dict[str, Any]:
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"Could not read region config: {exc}")
    routing = config.get("routing")
    if not isinstance(routing, dict) or routing.get("enabled") is not True:
        fail("routing.enabled must be true")

    source = routing.get("source")
    if not isinstance(source, dict):
        fail("routing.source is required")
    primary_id = str(source.get("primaryGeofabrikId") or "")
    polygon_url = str(source.get("polygonUrl") or "")
    if not primary_id or not polygon_url:
        fail("Routing source must declare primaryGeofabrikId and polygonUrl")

    safe_name = primary_id.replace("/", "__")
    poly_path = download(
        polygon_url,
        cache_dir / "polygons" / f"{safe_name}.poly",
        refresh=refresh,
    )
    nominal = parse_poly(poly_path)

    border_routes = [
        route
        for route in routing.get("validationRoutes", [])
        if isinstance(route, dict) and route.get("kind") == "border"
    ]
    if not border_routes:
        fail("At least one border validation route is required")

    checked = []
    for route in border_routes:
        name = str(route.get("name") or "border")
        start = route.get("start") or {}
        end = route.get("end") or {}
        try:
            start_point = Point(float(start["lng"]), float(start["lat"]))
            end_point = Point(float(end["lng"]), float(end["lat"]))
        except (KeyError, TypeError, ValueError):
            fail(f"Border validation route {name!r} has invalid coordinates")
        start_inside = nominal.covers(start_point)
        end_inside = nominal.covers(end_point)
        if start_inside == end_inside:
            fail(
                f"Border validation route {name!r} must have exactly one endpoint "
                "inside the nominal Geofabrik region"
            )
        checked.append(
            {
                "name": name,
                "startInside": start_inside,
                "endInside": end_inside,
            }
        )

    return {"valid": True, "borderRoutes": checked}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-dir", required=True)
    parser.add_argument("--refresh", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("catalog")

    preview = sub.add_parser("preview")
    preview.add_argument("--geofabrik-id", required=True)
    preview.add_argument("--buffer-km", type=float, required=True)

    validate = sub.add_parser("validate-config")
    validate.add_argument("--config", required=True)

    args = parser.parse_args()
    cache_dir = Path(args.cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    if args.command == "catalog":
        root = load_index(cache_dir, args.refresh)
        payload: Any = catalog_payload(root)
    elif args.command == "preview":
        root = load_index(cache_dir, args.refresh)
        payload = preview_payload(
            root,
            args.geofabrik_id,
            args.buffer_km,
            cache_dir,
            args.refresh,
        )
    elif args.command == "validate-config":
        payload = validate_config_geometry(
            Path(args.config),
            cache_dir,
            args.refresh,
        )
    else:
        fail("Unknown command")

    print(json.dumps(payload, separators=(",", ":")))


if __name__ == "__main__":
    main()
