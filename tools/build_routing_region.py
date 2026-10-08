#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from pyproj import CRS, Transformer
from shapely.geometry import Point, Polygon, box, mapping
from shapely.ops import transform, unary_union


USER_AGENT = "RoadPilot-Offline-Data/1"
VALHALLA_TILE_SIZE_DEGREES = {0: 4.0, 1: 1.0, 2: 0.25}


def fail(message: str) -> None:
    raise SystemExit(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_lines(lines) -> str:
    digest = hashlib.sha256()
    for line in sorted(lines):
        digest.update(line.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def geofabrik_polygon_url(pbf_url: str) -> str:
    suffix = "-latest.osm.pbf"
    if not pbf_url.endswith(suffix):
        fail(f"Cannot derive Geofabrik polygon URL from {pbf_url}")
    return pbf_url[: -len(suffix)] + ".poly"


def valhalla_tile_metadata(tile_path: Path, tile_dir: Path):
    relative = tile_path.relative_to(tile_dir)
    parts = relative.parts
    if len(parts) < 2 or not parts[-1].endswith(".gph"):
        fail(f"Unexpected Valhalla graph tile path: {relative}")
    try:
        level = int(parts[0])
        tile_index = int("".join([*parts[1:-1], Path(parts[-1]).stem]))
        size = VALHALLA_TILE_SIZE_DEGREES[level]
    except (KeyError, ValueError):
        fail(f"Unsupported Valhalla graph tile path: {relative}")
    width = int(360.0 / size)
    row = tile_index // width
    column = tile_index % width
    min_lat = row * size - 90.0
    min_lng = column * size - 180.0
    return {
        "path": relative.as_posix(),
        "level": level,
        "tileIndex": tile_index,
        "bounds": {
            "minLat": min_lat,
            "maxLat": min_lat + size,
            "minLng": min_lng,
            "maxLng": min_lng + size,
        },
    }


def build_graph_index(
    *,
    tile_dir: Path,
    nominal_geometry,
    buffered_geometry,
    source: dict,
    cache_root: Path,
    refresh_sources: bool,
    region_id: str,
    package_version: str,
):
    border_ring = buffered_geometry.difference(nominal_geometry)
    primary_id = str(source["primaryGeofabrikId"])
    boundary_geometries = {}
    for item in source.get("pbfs") or []:
        source_id = str(item.get("id") or "")
        if not source_id or source_id == primary_id:
            continue
        polygon_url = geofabrik_polygon_url(str(item["url"]))
        polygon_path = download(
            polygon_url,
            cache_root / f"graph-index__{source_id.replace('/', '__')}.poly",
            refresh=refresh_sources,
        )
        overlap = parse_poly(polygon_path).intersection(border_ring)
        if not overlap.is_empty:
            boundary_geometries[source_id] = overlap

    tiles = []
    graph_lines = []
    internal_lines = []
    boundary_lines = {source_id: [] for source_id in boundary_geometries}
    for tile_path in sorted(tile_dir.rglob("*.gph")):
        metadata = valhalla_tile_metadata(tile_path, tile_dir)
        tile_sha = sha256(tile_path)
        bounds = metadata["bounds"]
        tile_geometry = box(
            bounds["minLng"], bounds["minLat"], bounds["maxLng"], bounds["maxLat"]
        )
        boundaries = sorted(
            source_id
            for source_id, geometry in boundary_geometries.items()
            if geometry.intersection(tile_geometry).area > 0.0
        )
        metadata["sha256"] = tile_sha
        metadata["boundaries"] = boundaries
        tiles.append(metadata)
        identity = f'{metadata["path"]}:{tile_sha}'
        graph_lines.append(identity)
        if boundaries:
            for source_id in boundaries:
                boundary_lines[source_id].append(identity)
        else:
            internal_lines.append(identity)

    if not tiles:
        fail("Cannot create graph index without Valhalla .gph tiles")

    boundaries = [
        {
            "sourceId": source_id,
            "fingerprint": f"sha256:{sha256_lines(lines)}",
            "tileCount": len(lines),
        }
        for source_id, lines in sorted(boundary_lines.items())
        if lines
    ]
    return {
        "schema": "roadpilot-graph-index",
        "schemaVersion": 1,
        "regionId": region_id,
        "packageVersion": package_version,
        "graphTileFingerprint": f"sha256:{sha256_lines(graph_lines)}",
        "internalFingerprint": f"sha256:{sha256_lines(internal_lines)}",
        "tileCount": len(tiles),
        "boundaries": boundaries,
        "tiles": tiles,
    }


def run(command, *, stdout=None, capture=False):
    print("+", " ".join(str(part) for part in command), flush=True)
    result = subprocess.run(
        [str(part) for part in command],
        check=True,
        stdout=subprocess.PIPE if capture else stdout,
        stderr=subprocess.PIPE if capture else None,
        text=capture,
    )
    return result.stdout if capture else None


def require_tools(names):
    missing = [name for name in names if shutil.which(name) is None]
    if missing:
        fail("Missing required build tools: " + ", ".join(missing))


def download(url: str, destination: Path, *, refresh: bool = False) -> Path:
    if refresh:
        destination.unlink(missing_ok=True)
    if destination.is_file() and destination.stat().st_size > 0:
        print(f"cache hit: {destination}")
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    temporary.unlink(missing_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    print(f"download: {url}")
    with urllib.request.urlopen(request) as response, temporary.open("wb") as output:
        shutil.copyfileobj(response, output, length=1024 * 1024)
    if temporary.stat().st_size <= 0:
        fail(f"Downloaded empty file: {url}")
    temporary.replace(destination)
    return destination


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


def make_buffered_geojson(poly_path: Path, buffer_km: float, output_path: Path):
    geometry = parse_poly(poly_path)
    center = geometry.centroid
    local_crs = CRS.from_proj4(
        f"+proj=aeqd +lat_0={center.y} +lon_0={center.x} +datum=WGS84 +units=m +no_defs"
    )
    forward = Transformer.from_crs("EPSG:4326", local_crs, always_xy=True).transform
    backward = Transformer.from_crs(local_crs, "EPSG:4326", always_xy=True).transform
    buffered = transform(backward, transform(forward, geometry).buffer(buffer_km * 1000.0))
    feature = {
        "type": "Feature",
        "properties": {"borderBufferKm": buffer_km},
        "geometry": mapping(buffered),
    }
    output_path.write_text(json.dumps(feature, separators=(",", ":")), encoding="utf-8")
    return geometry


def valhalla_version() -> str:
    for command in (["valhalla_build_tiles", "--version"], ["valhalla_service", "--version"]):
        try:
            output = run(command, capture=True).strip()
            match = re.search(r"(?<!\d)(\d+\.\d+\.\d+)(?!\d)", output)
            if match:
                return match.group(1)
        except subprocess.CalledProcessError:
            pass
    return "unknown"


def validate_routes(config_path: Path, nominal_geometry, routes):
    results = []
    for route in routes:
        name = route["name"]
        kind = route.get("kind", "interior")
        start = route["start"]
        end = route["end"]

        if kind == "border":
            start_inside = nominal_geometry.covers(Point(float(start["lng"]), float(start["lat"])))
            end_inside = nominal_geometry.covers(Point(float(end["lng"]), float(end["lat"])))
            if start_inside == end_inside:
                fail(
                    f"Border validation route '{name}' must have exactly one endpoint "
                    "inside the nominal region"
                )

        request = {
            "locations": [
                {"lat": float(start["lat"]), "lon": float(start["lng"])},
                {"lat": float(end["lat"]), "lon": float(end["lng"])},
            ],
            "costing": route.get("costing", "motorcycle"),
            "directions_options": {"units": "kilometers"},
        }
        output = run(
            ["valhalla_service", config_path, "route", json.dumps(request, separators=(",", ":"))],
            capture=True,
        )
        try:
            response = json.loads(output)
        except json.JSONDecodeError as exc:
            fail(f"Validation route '{name}' returned invalid JSON: {exc}")

        trip = response.get("trip")
        if not isinstance(trip, dict):
            fail(f"Validation route '{name}' did not return a trip")
        status = trip.get("status", 0)
        if status not in (0, None):
            fail(f"Validation route '{name}' failed with Valhalla status {status}")

        results.append(
            {
                "name": name,
                "kind": kind,
                "passed": True,
                "summary": trip.get("summary") if isinstance(trip.get("summary"), dict) else {},
            }
        )
        print(f"validation passed: {name}")

    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--package-version", required=True)
    parser.add_argument("--work-dir", default=".routing-work")
    parser.add_argument("--dist-dir", default="dist/routing")
    parser.add_argument(
        "--refresh-sources",
        action="store_true",
        help="Redownload Geofabrik polygon/PBF inputs instead of reusing the local cache.",
    )
    args = parser.parse_args()

    require_tools(
        [
            "osmium",
            "valhalla_build_config",
            "valhalla_build_timezones",
            "valhalla_build_admins",
            "valhalla_build_tiles",
            "valhalla_build_extract",
            "valhalla_service",
        ]
    )

    config_path = Path(args.config)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    routing = config.get("routing")
    if not isinstance(routing, dict) or routing.get("enabled") is not True:
        fail("routing.enabled must be true")

    region_id = str(config["id"])
    region_name = str(config["name"])
    border_buffer_km = float(routing["borderBufferKm"])
    expected_valhalla_version = str(routing["expectedValhallaVersion"])
    actual_valhalla_version = valhalla_version()
    if actual_valhalla_version != expected_valhalla_version:
        fail(
            "Valhalla build/runtime version mismatch: "
            f"expected {expected_valhalla_version}, found {actual_valhalla_version}. "
            "Refusing to publish graph tiles that may be incompatible with RoadPilot."
        )

    source = routing["source"]
    pbfs = source["pbfs"]
    if not pbfs:
        fail("routing.source.pbfs must not be empty")

    work_root = Path(args.work_dir) / region_id
    cache_root = Path(args.work_dir) / "cache"
    build_root = work_root / "build"
    dist_root = Path(args.dist_dir) / region_id
    build_root.mkdir(parents=True, exist_ok=True)
    dist_root.mkdir(parents=True, exist_ok=True)

    polygon_path = download(
        source["polygonUrl"],
        cache_root / f"{region_id}.poly",
        refresh=args.refresh_sources,
    )
    nominal_geometry = parse_poly(polygon_path)
    center = nominal_geometry.centroid
    local_crs = CRS.from_proj4(
        f"+proj=aeqd +lat_0={center.y} +lon_0={center.x} +datum=WGS84 +units=m +no_defs"
    )
    forward = Transformer.from_crs("EPSG:4326", local_crs, always_xy=True).transform
    backward = Transformer.from_crs(local_crs, "EPSG:4326", always_xy=True).transform
    buffered_geometry = transform(
        backward, transform(forward, nominal_geometry).buffer(border_buffer_km * 1000.0)
    )
    feature = {
        "type": "Feature",
        "properties": {"borderBufferKm": border_buffer_km},
        "geometry": mapping(buffered_geometry),
    }
    (build_root / "buffer.geojson").write_text(
        json.dumps(feature, separators=(",", ":")), encoding="utf-8"
    )

    source_records = []
    source_paths = []
    for item in pbfs:
        source_id = str(item["id"])
        file_name = source_id.replace("/", "__") + ".osm.pbf"
        path = download(item["url"], cache_root / file_name, refresh=args.refresh_sources)
        source_paths.append(path)
        source_records.append(
            {
                "id": source_id,
                "url": item["url"],
                "sizeBytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )

    merged = build_root / "merged.osm.pbf"
    buffered = build_root / "buffered.osm.pbf"
    run(["osmium", "merge", *source_paths, "-o", merged, "-O"])
    run(
        [
            "osmium",
            "extract",
            "--polygon",
            build_root / "buffer.geojson",
            "--strategy",
            "complete_ways",
            merged,
            "-o",
            buffered,
            "-O",
        ]
    )
    run(["osmium", "check-refs", buffered])

    tile_dir = build_root / "tiles"
    tile_extract = build_root / "tiles.tar"
    admin_db = build_root / "admins.sqlite"
    timezone_db = build_root / "timezones.sqlite"
    if tile_dir.exists():
        shutil.rmtree(tile_dir)
    tile_dir.mkdir(parents=True, exist_ok=True)
    tile_extract.unlink(missing_ok=True)
    admin_db.unlink(missing_ok=True)
    timezone_db.unlink(missing_ok=True)

    generated_config = run(
        [
            "valhalla_build_config",
            "--mjolnir-tile-dir",
            tile_dir,
            "--mjolnir-tile-extract",
            tile_extract,
            "--mjolnir-timezone",
            timezone_db,
            "--mjolnir-admin",
            admin_db,
        ],
        capture=True,
    )
    valhalla_config = json.loads(generated_config)
    valhalla_config.setdefault("mjolnir", {})["concurrency"] = int(
        routing.get("buildConcurrency") or max(1, min(12, os.cpu_count() or 1))
    )
    valhalla_config_path = build_root / "valhalla.json"
    valhalla_config_path.write_text(json.dumps(valhalla_config, indent=2), encoding="utf-8")

    with timezone_db.open("wb") as output:
        run(["valhalla_build_timezones"], stdout=output)
    # Build admin polygons from the broader merged source. The graph itself stays clipped
    # to the buffered regional geometry, but admin context must not be truncated at that edge.
    run(["valhalla_build_admins", "-c", valhalla_config_path, merged])
    run(["valhalla_build_tiles", "-c", valhalla_config_path, buffered])
    run(["valhalla_build_extract", "-c", valhalla_config_path, "-O"])

    if not tile_extract.is_file() or tile_extract.stat().st_size <= 0:
        fail("Valhalla tile extract was not created")

    with tarfile.open(tile_extract, "r") as archive:
        names = archive.getnames()
    tile_count = sum(1 for name in names if name.endswith(".gph"))
    if "index.bin" not in names or tile_count <= 0:
        fail("Tile extract is missing index.bin or graph tiles")

    route_results = validate_routes(
        valhalla_config_path,
        nominal_geometry,
        routing.get("validationRoutes") or [],
    )
    if not route_results:
        fail("At least one routing validation route is required")

    package_template = routing["package"]["fileNameTemplate"]
    manifest_template = routing["package"]["manifestFileNameTemplate"]
    package_name = package_template.replace("{version}", args.package_version)
    manifest_name = manifest_template.replace("{version}", args.package_version)
    package_path = dist_root / package_name
    manifest_path = dist_root / manifest_name
    if manifest_name.endswith("-manifest.json"):
        graph_index_name = manifest_name[: -len("-manifest.json")] + "-graph-index.json"
    else:
        graph_index_name = manifest_name.removesuffix(".json") + "-graph-index.json"
    graph_index_path = dist_root / graph_index_name

    graph_index = build_graph_index(
        tile_dir=tile_dir,
        nominal_geometry=nominal_geometry,
        buffered_geometry=buffered_geometry,
        source=source,
        cache_root=cache_root,
        refresh_sources=args.refresh_sources,
        region_id=region_id,
        package_version=args.package_version,
    )
    graph_index_path.write_text(json.dumps(graph_index, indent=2) + "\n", encoding="utf-8")
    graph_index_sha = sha256(graph_index_path)

    shutil.copy2(tile_extract, package_path)

    package_sha = sha256(package_path)
    manifest = {
        "schema": "roadpilot-routing-pack",
        "schemaVersion": 1,
        "regionId": region_id,
        "regionName": region_name,
        "packageVersion": args.package_version,
        "builtAtUtc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "valhallaVersion": actual_valhalla_version,
        "graphFingerprint": f"sha256:{package_sha}",
        "source": {
            "primaryGeofabrikId": source["primaryGeofabrikId"],
            "polygonUrl": source["polygonUrl"],
            "borderBufferKm": border_buffer_km,
            "bufferGeoJsonSha256": sha256(build_root / "buffer.geojson"),
            "pbfs": source_records,
        },
        "artifact": {
            "fileName": package_name,
            "sizeBytes": package_path.stat().st_size,
            "sha256": package_sha,
            "tileCount": tile_count,
        },
        "graphIndex": {
            "fileName": graph_index_name,
            "sha256": graph_index_sha,
            "graphTileFingerprint": graph_index["graphTileFingerprint"],
            "internalFingerprint": graph_index["internalFingerprint"],
            "boundaryFingerprints": {
                item["sourceId"]: item["fingerprint"] for item in graph_index["boundaries"]
            },
        },
        "validation": {"routes": route_results},
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    checksum_path = dist_root / f"{package_name}.sha256"
    checksum_path.write_text(f"{package_sha}  {package_name}\n", encoding="utf-8")

    print(f"built: {package_path}")
    print(f"manifest: {manifest_path}")
    print(f"sha256: {package_sha}")
    print(f"tiles: {tile_count}")
    print(f"graph-index: {graph_index_path}")
    print(f"graph-tile-fingerprint: {graph_index['graphTileFingerprint']}")


if __name__ == "__main__":
    main()
