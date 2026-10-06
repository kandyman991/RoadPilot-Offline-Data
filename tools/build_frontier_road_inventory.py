#!/usr/bin/env python3
"""Build a stable OSM frontier-road inventory for a RoadPilot region pair.

Discovery uses real OSM highway geometry crossing both nominal regional polygons.
It deliberately contains no Valhalla graph-local ids. A later stage correlates
these stable physical anchors independently into each exact regional graph.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Iterable

from pyproj import CRS, Transformer
from shapely.geometry import (
    GeometryCollection,
    LineString,
    MultiLineString,
    MultiPoint,
    Point,
    Polygon,
    shape,
)
from shapely.ops import substring, transform, unary_union

SCHEMA = "roadpilot.frontier-road-inventory"
VERSION = 1
GENERATOR_NAME = "roadpilot-osm-frontier-inventory"
GENERATOR_VERSION = "1"
ROUTING_TAGS = (
    "highway",
    "name",
    "ref",
    "oneway",
    "junction",
    "access",
    "vehicle",
    "motor_vehicle",
    "motorcycle",
    "surface",
    "tracktype",
    "smoothness",
    "maxspeed",
    "bridge",
    "tunnel",
    "layer",
    "toll",
)


def fail(message: str) -> None:
    raise SystemExit(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(command: list[str]) -> None:
    print("+", " ".join(command), flush=True)
    result = subprocess.run(command, text=True, capture_output=True)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        fail(f"Command failed ({result.returncode}): {' '.join(command)}\n{detail}")


def parse_poly(path: Path):
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    if len(lines) < 4:
        fail(f"Invalid .poly file: {path}")

    outers = []
    holes = []
    index = 1
    while index < len(lines):
        label = lines[index]
        index += 1
        if label == "END":
            break
        is_hole = label.startswith("!")
        coordinates = []
        while index < len(lines) and lines[index] != "END":
            parts = lines[index].split()
            if len(parts) >= 2:
                coordinates.append((float(parts[0]), float(parts[1])))
            index += 1
        if index >= len(lines):
            fail(f"Unterminated ring in {path}")
        index += 1
        if len(coordinates) < 3:
            continue
        if coordinates[0] != coordinates[-1]:
            coordinates.append(coordinates[0])
        polygon = Polygon(coordinates)
        if not polygon.is_valid:
            polygon = polygon.buffer(0)
        (holes if is_hole else outers).append(polygon)

    if not outers:
        fail(f"No outer geometry found in {path}")
    geometry = unary_union(outers)
    if holes:
        geometry = geometry.difference(unary_union(holes))
    if geometry.is_empty:
        fail(f"Empty geometry produced from {path}")
    return geometry


def load_polygon(path: Path):
    suffix = path.suffix.lower()
    if suffix == ".poly":
        return parse_poly(path)
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"Could not read polygon {path}: {exc}")
    if isinstance(document, dict) and document.get("type") == "Feature":
        document = document.get("geometry")
    try:
        geometry = shape(document)
    except Exception as exc:
        fail(f"Could not parse polygon geometry {path}: {exc}")
    if geometry.is_empty or geometry.geom_type not in {"Polygon", "MultiPolygon"}:
        fail(f"{path}: expected Polygon or MultiPolygon")
    if not geometry.is_valid:
        geometry = geometry.buffer(0)
    return geometry


def load_pair_manifest(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"Could not read pair manifest {path}: {exc}")
    if not isinstance(value, dict):
        fail("Pair manifest must be a JSON object")
    if (
        value.get("schema") != "roadpilot.cross-region-connectivity"
        or value.get("version") != 1
    ):
        fail("Unsupported cross-region connectivity pair manifest")
    if value.get("bindingState") != "STABLE_PHYSICAL":
        fail("Pair manifest must use STABLE_PHYSICAL binding state")
    for key in (
        "pairId",
        "fromRegionId",
        "toRegionId",
        "fromBoundaryFingerprint",
        "toBoundaryFingerprint",
    ):
        if not str(value.get(key) or "").strip():
            fail(f"Pair manifest is missing {key}")
    return value


def local_projection(from_geometry, to_geometry):
    combined = unary_union([from_geometry, to_geometry])
    center = combined.centroid
    local_crs = CRS.from_proj4(
        f"+proj=aeqd +lat_0={center.y} +lon_0={center.x} "
        "+datum=WGS84 +units=m +no_defs"
    )
    forward = Transformer.from_crs("EPSG:4326", local_crs, always_xy=True).transform
    backward = Transformer.from_crs(local_crs, "EPSG:4326", always_xy=True).transform
    return forward, backward


def iter_frontier_hits(geometry) -> Iterable[tuple[str, Point, float]]:
    if geometry.is_empty:
        return
    if isinstance(geometry, Point):
        yield ("CROSSING", geometry, 0.0)
        return
    if isinstance(geometry, MultiPoint):
        for item in geometry.geoms:
            yield ("CROSSING", item, 0.0)
        return
    if isinstance(geometry, LineString):
        if geometry.length > 0.01:
            yield (
                "FRONTIER_OVERLAP",
                geometry.interpolate(geometry.length * 0.5),
                geometry.length,
            )
        return
    if isinstance(geometry, MultiLineString):
        for item in geometry.geoms:
            yield from iter_frontier_hits(item)
        return
    if isinstance(geometry, GeometryCollection):
        for item in geometry.geoms:
            yield from iter_frontier_hits(item)


def heading_degrees(line: LineString, distance: float) -> float:
    before = max(0.0, distance - 10.0)
    after = min(line.length, distance + 10.0)
    if after - before < 0.5:
        before = 0.0
        after = line.length
    a = line.interpolate(before)
    b = line.interpolate(after)
    dx = b.x - a.x
    dy = b.y - a.y
    if abs(dx) + abs(dy) < 1e-9:
        return 0.0
    return math.degrees(math.atan2(dx, dy)) % 360.0


def snippet_geometry(line: LineString, distance: float, backward_transform):
    start = max(0.0, distance - 250.0)
    end = min(line.length, distance + 250.0)
    if end - start < 0.5:
        segment = line
    else:
        segment = substring(line, start, end)
    if isinstance(segment, Point):
        segment = LineString([line.coords[0], line.coords[-1]])
    wgs = transform(backward_transform, segment)
    return {
        "type": "LineString",
        "coordinates": [[float(x), float(y)] for x, y in wgs.coords],
    }


def inventory_id(
    pair_id: str,
    way_id: int,
    crossing_kind: str,
    lng: float,
    lat: float,
) -> str:
    identity = (
        f"{pair_id}|{way_id}|{crossing_kind}|{lng:.7f}|{lat:.7f}"
    ).encode("utf-8")
    return "fri1-" + hashlib.sha256(identity).hexdigest()[:24]


def export_highways(osm_source: Path, work: Path) -> Path:
    if shutil.which("osmium") is None:
        fail("osmium is required to build the frontier road inventory")
    filtered = work / "highways.osm.pbf"
    exported = work / "highways.geojsonseq"
    run(
        [
            "osmium",
            "tags-filter",
            str(osm_source),
            "w/highway",
            "-o",
            str(filtered),
            "-O",
        ]
    )
    run(
        [
            "osmium",
            "export",
            str(filtered),
            "-o",
            str(exported),
            "-f",
            "geojsonseq",
            "--geometry-types=linestring",
            "--add-unique-id=type_id",
            "-x",
            "print_record_separator=false",
            "-O",
        ]
    )
    return exported


def parse_way_id(feature: dict[str, Any]) -> int | None:
    value = feature.get("id")
    if not isinstance(value, str) or not value.startswith("w"):
        return None
    try:
        way_id = int(value[1:])
    except ValueError:
        return None
    return way_id if way_id > 0 else None


def selected_tags(properties: Any) -> dict[str, str]:
    if not isinstance(properties, dict):
        return {}
    result = {}
    for key in ROUTING_TAGS:
        value = properties.get(key)
        if value is not None and str(value).strip():
            result[key] = str(value)
    return result


def build_inventory(
    pair: dict[str, Any],
    from_polygon: Path,
    to_polygon: Path,
    osm_source: Path,
) -> dict[str, Any]:
    from_wgs = load_polygon(from_polygon)
    to_wgs = load_polygon(to_polygon)
    forward, backward = local_projection(from_wgs, to_wgs)
    from_local = transform(forward, from_wgs)
    to_local = transform(forward, to_wgs)
    frontier = from_local.boundary.intersection(to_local.boundary)
    if frontier.is_empty:
        fail(
            "Nominal region polygons do not share a frontier; "
            "refusing to invent a seam corridor"
        )

    roads: list[dict[str, Any]] = []
    examined = 0
    with tempfile.TemporaryDirectory(prefix="roadpilot-frontier-") as temp:
        exported = export_highways(osm_source, Path(temp))
        with exported.open("r", encoding="utf-8") as handle:
            for raw in handle:
                raw = raw.strip()
                if not raw:
                    continue
                feature = json.loads(raw)
                way_id = parse_way_id(feature)
                geometry_value = feature.get("geometry")
                if way_id is None or not isinstance(geometry_value, dict):
                    continue
                if geometry_value.get("type") != "LineString":
                    continue
                properties = feature.get("properties")
                if not isinstance(properties, dict) or not properties.get("highway"):
                    continue
                examined += 1
                line_wgs = shape(geometry_value)
                if not isinstance(line_wgs, LineString) or line_wgs.length <= 0:
                    continue
                line = transform(forward, line_wgs)

                # A stable physical frontier road must have real geometry in both
                # nominal regions. No heading, distance, road-class, or travel-mode
                # filter is applied here; Valhalla proves those in a later stage.
                if (
                    line.intersection(from_local).length <= 0.01
                    or line.intersection(to_local).length <= 0.01
                ):
                    continue

                hits = []
                seen = set()
                for kind, point, overlap_length in iter_frontier_hits(
                    line.intersection(frontier)
                ):
                    key = (kind, round(point.x, 3), round(point.y, 3))
                    if key in seen:
                        continue
                    seen.add(key)
                    hits.append((line.project(point), kind, point, overlap_length))
                hits.sort(key=lambda item: item[0])

                for crossing_index, (distance, kind, point, overlap_length) in enumerate(hits):
                    point_wgs = transform(backward, point)
                    lng = float(point_wgs.x)
                    lat = float(point_wgs.y)
                    record = {
                        "id": inventory_id(
                            str(pair["pairId"]), way_id, kind, lng, lat
                        ),
                        "wayId": way_id,
                        "crossingIndex": crossing_index,
                        "crossingKind": kind,
                        "crossingCoordinate": {"lat": lat, "lng": lng},
                        "headingDegrees": heading_degrees(line, distance),
                        "routingTags": selected_tags(properties),
                        "snippet": snippet_geometry(line, distance, backward),
                    }
                    if kind == "FRONTIER_OVERLAP":
                        record["overlapLengthMeters"] = float(overlap_length)
                    roads.append(record)

    roads.sort(
        key=lambda item: (
            item["wayId"],
            item["crossingIndex"],
            item["id"],
        )
    )
    print(
        f"examined {examined} highway ways; "
        f"found {len(roads)} stable frontier road anchors",
        flush=True,
    )
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "pairId": pair["pairId"],
        "fromRegionId": pair["fromRegionId"],
        "toRegionId": pair["toRegionId"],
        "fromBoundaryFingerprint": pair["fromBoundaryFingerprint"],
        "toBoundaryFingerprint": pair["toBoundaryFingerprint"],
        "source": {
            "osmSha256": "sha256:" + sha256_file(osm_source),
            "fromPolygonSha256": "sha256:" + sha256_file(from_polygon),
            "toPolygonSha256": "sha256:" + sha256_file(to_polygon),
        },
        "generator": {
            "name": GENERATOR_NAME,
            "version": GENERATOR_VERSION,
        },
        "roads": roads,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pair-manifest", required=True, type=Path)
    parser.add_argument("--from-polygon", required=True, type=Path)
    parser.add_argument("--to-polygon", required=True, type=Path)
    parser.add_argument("--osm-source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    for path in (
        args.pair_manifest,
        args.from_polygon,
        args.to_polygon,
        args.osm_source,
    ):
        if not path.is_file():
            fail(f"Input does not exist: {path}")

    pair = load_pair_manifest(args.pair_manifest)
    inventory = build_inventory(
        pair,
        args.from_polygon,
        args.to_polygon,
        args.osm_source,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
    print(f"wrote: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
