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


def iter_frontier_hits(
    geometry,
    forward_transform,
) -> Iterable[tuple[str, Point, float]]:
    """Yield metric-local frontier anchors from WGS84 topology.

    Topological intersection stays in the original OSM coordinate space so a
    road exactly following a nominal polygon boundary remains an overlap after
    projection. Projection is used only after the topology is established.
    """
    if geometry.is_empty:
        return
    if isinstance(geometry, Point):
        yield ("CROSSING", transform(forward_transform, geometry), 0.0)
        return
    if isinstance(geometry, MultiPoint):
        for item in geometry.geoms:
            yield ("CROSSING", transform(forward_transform, item), 0.0)
        return
    if isinstance(geometry, LineString):
        local = transform(forward_transform, geometry)
        if local.length > 0.01:
            yield (
                "FRONTIER_OVERLAP",
                local.interpolate(local.length * 0.5),
                local.length,
            )
        return
    if isinstance(geometry, MultiLineString):
        for item in geometry.geoms:
            yield from iter_frontier_hits(item, forward_transform)
        return
    if isinstance(geometry, GeometryCollection):
        for item in geometry.geoms:
            yield from iter_frontier_hits(item, forward_transform)


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
    heading = math.degrees(math.atan2(dx, dy)) % 360.0
    # Floating-point modulo can represent a tiny negative northward bearing
    # as 360.0. Canonicalize the circular endpoint to strict [0, 360).
    if heading >= 360.0 - 1e-9:
        return 0.0
    return heading


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
    work.mkdir(parents=True, exist_ok=True)
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



def iter_lines(geometry):
    """Preserve every separate line fragment inside shared buffered coverage."""
    if isinstance(geometry, LineString):
        if geometry.length > 1.0:
            yield geometry
    elif hasattr(geometry, "geoms"):
        for part in geometry.geoms:
            yield from iter_lines(part)


def overlap_road_anchors(
    pair: dict[str, Any],
    from_buffer: Path,
    to_buffer: Path,
    source_paths: list[Path],
    nominal_roads: list[dict[str, Any]],
    forward,
    backward,
) -> tuple[list[dict[str, Any]], int]:
    """F8-inspired non-nominal discovery: every OSM way in both graph buffers.

    No heading, route-class, name/ref or first-success pruning. Distinct positions
    along long roads are retained. Physical OSM coverage does not certify F8
    graph-edge parity; the resulting discovery record makes this explicit.
    """
    shared = load_polygon(from_buffer).intersection(load_polygon(to_buffer))
    if shared.is_empty:
        fail("No shared buffered coverage for neighboring graphs")
    shared_local = transform(forward, shared)
    output: list[dict[str, Any]] = []
    seen_geometry: set[tuple[int, bytes]] = set()
    previous = {(r["wayId"], round(r["crossingCoordinate"]["lat"], 5),
                 round(r["crossingCoordinate"]["lng"], 5)) for r in nominal_roads}
    indices = {}
    for road in nominal_roads:
        way = road["wayId"]
        indices[way] = max(indices.get(way, 0), road["crossingIndex"] + 1)
    examined = 0
    with tempfile.TemporaryDirectory(prefix="roadpilot-overlap-") as temp:
        for source_index, source in enumerate(source_paths):
            exported = export_highways(source, Path(temp) / str(source_index))
            with exported.open("r", encoding="utf-8") as handle:
                for raw in handle:
                    raw = raw.strip()
                    if not raw:
                        continue
                    feature = json.loads(raw)
                    way = parse_way_id(feature)
                    geometry = feature.get("geometry")
                    tags = feature.get("properties")
                    if (way is None or
                            not isinstance(geometry, dict) or
                            geometry.get("type") != "LineString" or
                            not isinstance(tags, dict) or not tags.get("highway")):
                        continue
                    examined += 1
                    line_wgs = shape(geometry)
                    if not isinstance(line_wgs, LineString) or line_wgs.length <= 0:
                        continue
                    if not line_wgs.intersects(shared):
                        continue
                    # The same way may be clipped differently in graph A's
                    # and graph B's retained PBF. Never discard a distinct
                    # segment merely because a way ID was seen in A.
                    identity = (way, hashlib.sha256(line_wgs.wkb).digest())
                    if identity in seen_geometry:
                        continue
                    seen_geometry.add(identity)
                    line = transform(forward, line_wgs)
                    for piece in iter_lines(line.intersection(shared_local)):
                        # Same spatial order as the F8 1500m corridor window;
                        # no opaque top-N or one-representative-per-road-ref limit.
                        count = max(1, math.ceil(piece.length / 1500.0))
                        for index in range(count):
                            point = piece.interpolate((index + .5) / count, normalized=True)
                            pos = line.project(point)
                            wgs = transform(backward, point)
                            lat, lng = float(wgs.y), float(wgs.x)
                            key = (way, round(lat, 5), round(lng, 5))
                            if key in previous:
                                continue
                            previous.add(key)
                            record = {
                                "id": inventory_id(str(pair["pairId"]), way, "OVERLAP_ROAD", lng, lat),
                                "wayId": way,
                                "crossingIndex": indices.get(way, 0),
                                "crossingKind": "OVERLAP_ROAD",
                                "crossingCoordinate": {"lat": lat, "lng": lng},
                                "headingDegrees": heading_degrees(line, pos),
                                "routingTags": selected_tags(tags),
                                "snippet": snippet_geometry(line, pos, backward),
                            }
                            indices[way] = record["crossingIndex"] + 1
                            output.append(record)
                            if len(output) + len(nominal_roads) > 250_000:
                                fail("More than 250000 candidate anchors: refusing incomplete inventory")
    return output, examined



def build_inventory(
    pair: dict[str, Any],
    from_polygon: Path,
    to_polygon: Path,
    osm_source: Path,
    from_buffer: Path | None = None,
    to_buffer: Path | None = None,
    to_osm_source: Path | None = None,
) -> dict[str, Any]:
    from_wgs = load_polygon(from_polygon)
    to_wgs = load_polygon(to_polygon)
    forward, backward = local_projection(from_wgs, to_wgs)
    from_local = transform(forward, from_wgs)
    to_local = transform(forward, to_wgs)

    # Determine the actual shared frontier in original OSM/WGS84 topology.
    # Projecting polygon edges before intersection can turn an exactly shared
    # curved/geodesic boundary into two slightly different straight chords.
    frontier_wgs = from_wgs.boundary.intersection(to_wgs.boundary)
    if frontier_wgs.is_empty or frontier_wgs.length <= 0:
        fail(
            "Nominal boundaries have no shared line frontier (possibly "
            "overlapping polygons with point-only intersections). "
            "OSM nominal anchors cannot establish exhaustive graph-native "
            "F8 crossings; refusing a false sourceExhausted result"
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
                    line_wgs.intersection(from_wgs).length <= 0.0
                    or line_wgs.intersection(to_wgs).length <= 0.0
                ):
                    continue

                hits = []
                seen = set()
                for kind, point, overlap_length in iter_frontier_hits(
                    line_wgs.intersection(frontier_wgs),
                    forward,
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

    overlap_count = 0
    overlap_examined = 0
    buffered = (from_buffer, to_buffer, to_osm_source)
    if any(x is not None for x in buffered) and not all(x is not None for x in buffered):
        fail("Buffered overlap discovery requires both buffer polygons and both PBF sources")
    if all(x is not None for x in buffered):
        more, overlap_examined = overlap_road_anchors(
            pair, from_buffer, to_buffer, [osm_source, to_osm_source],
            roads, forward, backward,
        )
        overlap_count = len(more)
        roads.extend(more)

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
            **({
                "toOsmSha256": "sha256:" + sha256_file(to_osm_source),
                "fromBufferSha256": "sha256:" + sha256_file(from_buffer),
                "toBufferSha256": "sha256:" + sha256_file(to_buffer),
            } if overlap_count or all(x is not None for x in buffered) else {}),
        },
        "discovery": {
            "scope": "OSM_BUFFER_OVERLAP" if all(x is not None for x in buffered) else "NOMINAL_ONLY",
            "sourceExhausted": True,
            "f8GraphEdgeParity": "NOT_VERIFIED",
            "nominalRoadAnchors": len(roads) - overlap_count,
            "overlapRoadAnchors": overlap_count,
            "overlapSourceRoadWaysExamined": overlap_examined,
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
    parser.add_argument("--to-osm-source", type=Path)
    parser.add_argument("--from-buffer-polygon", type=Path)
    parser.add_argument("--to-buffer-polygon", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    for path in (
        args.pair_manifest,
        args.from_polygon,
        args.to_polygon,
        args.osm_source,
        *[x for x in (args.to_osm_source, args.from_buffer_polygon, args.to_buffer_polygon)
          if x is not None],
    ):
        if not path.is_file():
            fail(f"Input does not exist: {path}")

    pair = load_pair_manifest(args.pair_manifest)
    inventory = build_inventory(
        pair,
        args.from_polygon,
        args.to_polygon,
        args.osm_source,
        args.from_buffer_polygon,
        args.to_buffer_polygon,
        args.to_osm_source,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
    print(f"wrote: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
