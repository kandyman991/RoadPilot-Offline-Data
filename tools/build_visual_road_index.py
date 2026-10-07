#!/usr/bin/env python3
"""Build RoadPilot visual major/border road coverage evidence from OSM + PMTiles."""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from pyproj import CRS, Transformer
from shapely.geometry import LineString, Polygon, shape
from shapely.ops import transform, unary_union

from visual_pack import VisualPackError, collect_layer_feature_ids, load_json_object

SUPPORTED_ROADS = {
    "motorway", "trunk", "primary", "secondary",
    "motorway_link", "trunk_link", "primary_link", "secondary_link",
    "tertiary", "tertiary_link", "unclassified", "residential", "road",
    "living_street", "service", "track",
}


def fail(message: str) -> None:
    raise SystemExit(message)


def run(command: list[str], label: str) -> None:
    try:
        result = subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as exc:
        fail(f"Could not run {label}: {exc}")
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        fail(f"{label} failed ({result.returncode}): {detail}")


def parse_poly(path: Path):
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    if len(lines) < 4:
        fail(f"Invalid Geofabrik poly file: {path}")
    outers = []
    holes = []
    index = 1
    while index < len(lines):
        label = lines[index]
        index += 1
        if label == "END":
            break
        is_hole = label.startswith("!")
        coords = []
        while index < len(lines) and lines[index] != "END":
            parts = lines[index].split()
            if len(parts) >= 2:
                coords.append((float(parts[0]), float(parts[1])))
            index += 1
        if index >= len(lines):
            fail(f"Unterminated polygon ring in {path}")
        index += 1
        if len(coords) < 3:
            continue
        if coords[0] != coords[-1]:
            coords.append(coords[0])
        polygon = Polygon(coords)
        if not polygon.is_valid:
            polygon = polygon.buffer(0)
        (holes if is_hole else outers).append(polygon)
    if not outers:
        fail(f"No outer polygon found in {path}")
    geometry = unary_union(outers)
    if holes:
        geometry = geometry.difference(unary_union(holes))
    if geometry.is_empty:
        fail(f"Empty polygon geometry from {path}")
    return geometry


def feature_way_id(feature: dict[str, Any]) -> int | None:
    value = feature.get("id")
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    if isinstance(value, str):
        if value.startswith("w") and value[1:].isdigit():
            result = int(value[1:])
            return result if result > 0 else None
        if value.isdigit():
            result = int(value)
            return result if result > 0 else None
    props = feature.get("properties")
    if isinstance(props, dict):
        attr = props.get("@id") or props.get("id")
        if isinstance(attr, int) and not isinstance(attr, bool) and attr > 0:
            return attr
        if isinstance(attr, str):
            attr = attr.removeprefix("w")
            if attr.isdigit() and int(attr) > 0:
                return int(attr)
    return None


def exported_highways(pbf: Path, work: Path):
    filtered = work / "highways.osm.pbf"
    exported = work / "highways.geojsonseq"
    run(
        ["osmium", "tags-filter", str(pbf), "w/highway", "-o", str(filtered), "-O"],
        "osmium highway filter",
    )
    run(
        [
            "osmium", "export", str(filtered),
            "--geometry-types=linestring",
            "--add-unique-id=type_id",
            "-f", "geojsonseq",
            "-o", str(exported),
            "-O",
        ],
        "osmium highway export",
    )
    with exported.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.lstrip("\x1e").strip()
            if not line:
                continue
            value = json.loads(line)
            if isinstance(value, dict):
                yield value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pbf", required=True, type=Path)
    parser.add_argument("--polygon", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--major-road-class", action="append", required=True)
    parser.add_argument("--border-tolerance-meters", type=float, default=75.0)
    args = parser.parse_args()

    for path, label in (
        (args.pbf, "OSM PBF"),
        (args.polygon, "region polygon"),
        (args.manifest, "visual manifest"),
        (args.package, "visual PMTiles"),
    ):
        if not path.is_file():
            fail(f"{label} does not exist: {path}")
    major_classes = set(args.major_road_class)
    if not major_classes or not major_classes <= SUPPORTED_ROADS:
        fail("major road classes must be supported RoadPilot visual road classes")
    if not (0 <= args.border_tolerance_meters <= 1000):
        fail("border tolerance must be from 0 to 1000 metres")

    manifest = load_json_object(args.manifest, "visual manifest")
    nominal = parse_poly(args.polygon)
    center = nominal.centroid
    local_crs = CRS.from_proj4(
        f"+proj=aeqd +lat_0={center.y} +lon_0={center.x} +datum=WGS84 +units=m +no_defs"
    )
    project = Transformer.from_crs("EPSG:4326", local_crs, always_xy=True).transform
    projected_boundary_corridor = transform(project, nominal.boundary).buffer(
        args.border_tolerance_meters
    )

    try:
        visual_way_ids = collect_layer_feature_ids(args.package, "transportation")
    except VisualPackError as exc:
        fail(str(exc))

    roads: dict[int, dict[str, Any]] = {}
    with tempfile.TemporaryDirectory(prefix="roadpilot-visual-road-index-") as tmp:
        for feature in exported_highways(args.pbf, Path(tmp)):
            props = feature.get("properties")
            geometry = feature.get("geometry")
            if not isinstance(props, dict) or not isinstance(geometry, dict):
                continue
            highway = str(props.get("highway") or "")
            if highway not in SUPPORTED_ROADS:
                continue
            way_id = feature_way_id(feature)
            if way_id is None:
                continue
            try:
                line = shape(geometry)
            except Exception:
                continue
            if not isinstance(line, LineString) or line.is_empty:
                continue

            categories = []
            if highway in major_classes:
                categories.append("MAJOR")
            projected_line = transform(project, line)
            if projected_line.intersects(projected_boundary_corridor):
                categories.append("BORDER")
            if not categories:
                continue

            existing = roads.get(way_id)
            record = {
                "osmWayId": way_id,
                "highway": highway,
                "name": str(props.get("name")) if props.get("name") not in (None, "") else None,
                "ref": str(props.get("ref")) if props.get("ref") not in (None, "") else None,
                "categories": sorted(set(categories)),
                "presentInVisual": way_id in visual_way_ids,
            }
            if existing is None:
                roads[way_id] = record
            else:
                existing["categories"] = sorted(set(existing["categories"]) | set(categories))
                existing["presentInVisual"] = existing["presentInVisual"] or record["presentInVisual"]

    ordered = [roads[key] for key in sorted(roads)]
    missing = [road for road in ordered if not road["presentInVisual"]]
    output = {
        "schema": "roadpilot-visual-road-index",
        "schemaVersion": 1,
        "regionId": manifest["regionId"],
        "packageVersion": manifest["packageVersion"],
        "sourceFingerprint": manifest["sourceFingerprint"],
        "visualFingerprint": manifest["visualFingerprint"],
        "majorRoadClasses": sorted(major_classes),
        "borderToleranceMeters": args.border_tolerance_meters,
        "sourceRoadCount": len(ordered),
        "majorRoadCount": sum("MAJOR" in road["categories"] for road in ordered),
        "borderRoadCount": sum("BORDER" in road["categories"] for road in ordered),
        "observedRoadCount": sum(road["presentInVisual"] for road in ordered),
        "missingRoadCount": len(missing),
        "roads": ordered,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")

    print(
        f"visual road index: source={len(ordered)} major={output['majorRoadCount']} "
        f"border={output['borderRoadCount']} observed={output['observedRoadCount']} "
        f"missing={len(missing)}"
    )
    if missing:
        sample = ", ".join(str(road["osmWayId"]) for road in missing[:20])
        fail(f"Visual PMTiles is missing required source roads (sample way IDs): {sample}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
