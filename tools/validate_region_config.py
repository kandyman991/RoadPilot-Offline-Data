#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path

SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")
SAFE_FILE = re.compile(r"^[A-Za-z0-9._{}-]+$")


def fail(message: str) -> None:
    raise SystemExit(message)


def validate_coordinate(value, label: str) -> None:
    if not isinstance(value, dict):
        fail(f"{label} must be an object")
    try:
        lat = float(value["lat"])
        lng = float(value["lng"])
    except (KeyError, TypeError, ValueError):
        fail(f"{label} must contain numeric lat/lng")
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        fail(f"{label} coordinate is invalid")


def validate_overture(overture) -> bool:
    if not isinstance(overture, dict) or overture.get("enabled") is not True:
        return False

    if overture.get("databaseSchema") != "roadpilot-overture-v1":
        fail("unexpected Overture database schema")

    file_name = str(overture.get("fileName") or "")
    manifest_name = str(overture.get("manifestFileName") or "")
    if not SAFE_FILE.fullmatch(file_name) or not file_name.endswith(".sqlite"):
        fail("invalid Overture SQLite file name")
    if not SAFE_FILE.fullmatch(manifest_name) or not manifest_name.endswith(".json"):
        fail("invalid Overture manifest file name")

    coverage = overture.get("coverage")
    if not isinstance(coverage, dict):
        fail("Overture coverage is required")

    try:
        min_lat = float(coverage["minLat"])
        max_lat = float(coverage["maxLat"])
        min_lng = float(coverage["minLng"])
        max_lng = float(coverage["maxLng"])
    except (KeyError, TypeError, ValueError):
        fail("Overture coverage must contain numeric min/max latitude/longitude")

    if not (-90 <= min_lat < max_lat <= 90):
        fail("invalid Overture latitude coverage")
    if not (-180 <= min_lng < max_lng <= 180):
        fail("invalid Overture longitude coverage")

    country = str(overture.get("country") or "")
    if len(country) != 2 or not country.isalpha():
        fail("Overture country must be a two-letter code")

    validations = overture.get("validation")
    if not isinstance(validations, list) or not validations:
        fail("at least one Overture validation target is required")
    return True


def validate_visual(visual, routing) -> bool:
    if not isinstance(visual, dict) or visual.get("enabled") is not True:
        return False

    source = visual.get("source")
    if not isinstance(source, dict):
        fail("visual.source is required")
    primary_id = str(source.get("primaryGeofabrikId") or "")
    url = str(source.get("url") or "")
    polygon_url = str(source.get("polygonUrl") or "")
    if not primary_id:
        fail("visual.source.primaryGeofabrikId is required")
    if not url.startswith("https://") or not url.endswith(".osm.pbf"):
        fail("visual.source.url must be an HTTPS .osm.pbf URL")
    if not polygon_url.startswith("https://") or not polygon_url.endswith(".poly"):
        fail("visual.source.polygonUrl must be an HTTPS .poly URL")

    threads = visual.get("buildThreads", 1)
    if not isinstance(threads, int) or not (1 <= threads <= 64):
        fail("visual.buildThreads must be an integer from 1 to 64")

    package = visual.get("package")
    if not isinstance(package, dict):
        fail("visual.package is required")
    templates = {
        "fileNameTemplate": ".pmtiles",
        "manifestFileNameTemplate": "-manifest.json",
        "roadIndexFileNameTemplate": "-road-index.json",
    }
    for key, suffix in templates.items():
        value = str(package.get(key) or "")
        if "{version}" not in value or not value.endswith(suffix):
            fail(f"visual.package.{key} must contain {{version}} and end in {suffix}")
        if not SAFE_FILE.fullmatch(value):
            fail(f"visual.package.{key} contains unsafe characters")

    validation = visual.get("validation")
    if not isinstance(validation, dict):
        fail("visual.validation is required")
    classes = validation.get("majorRoadClasses")
    allowed = {
        "motorway", "trunk", "primary", "secondary",
        "motorway_link", "trunk_link", "primary_link", "secondary_link",
    }
    if (
        not isinstance(classes, list)
        or not classes
        or any(not isinstance(item, str) or item not in allowed for item in classes)
        or len(classes) != len(set(classes))
    ):
        fail("visual.validation.majorRoadClasses must be a unique non-empty supported class list")
    try:
        tolerance = float(validation["borderToleranceMeters"])
    except (KeyError, TypeError, ValueError):
        fail("visual.validation.borderToleranceMeters must be numeric")
    if not (0 <= tolerance <= 1000):
        fail("visual.validation.borderToleranceMeters must be from 0 to 1000")

    if isinstance(routing, dict) and routing.get("enabled") is True:
        routing_source = routing.get("source")
        if not isinstance(routing_source, dict):
            fail("routing.source is required when visual is enabled")
        routing_primary = str(routing_source.get("primaryGeofabrikId") or "")
        if routing_primary != primary_id:
            fail("visual primary Geofabrik id must match routing primary Geofabrik id")
        pbfs = routing_source.get("pbfs")
        match = next(
            (
                item for item in (pbfs or [])
                if isinstance(item, dict) and str(item.get("id") or "") == primary_id
            ),
            None,
        )
        if match is None or str(match.get("url") or "") != url:
            fail("visual source URL must match the routing primary PBF URL")
        routing_polygon = str(routing_source.get("polygonUrl") or "")
        if routing_polygon and routing_polygon != polygon_url:
            fail("visual source polygonUrl must match the routing nominal polygon URL")
    return True


def validate_routing(routing) -> bool:
    if not isinstance(routing, dict) or routing.get("enabled") is not True:
        return False

    expected_valhalla = str(routing.get("expectedValhallaVersion") or "")
    if not re.fullmatch(r"\d+\.\d+\.\d+", expected_valhalla):
        fail("routing.expectedValhallaVersion must be a semantic version such as 3.6.3")

    try:
        buffer_km = float(routing["borderBufferKm"])
    except (KeyError, TypeError, ValueError):
        fail("routing.borderBufferKm must be numeric")
    if not (0 < buffer_km <= 100):
        fail("routing.borderBufferKm must be > 0 and <= 100")

    concurrency = routing.get("buildConcurrency", 1)
    if not isinstance(concurrency, int) or not (1 <= concurrency <= 64):
        fail("routing.buildConcurrency must be an integer from 1 to 64")

    source = routing.get("source")
    if not isinstance(source, dict):
        fail("routing.source is required")
    primary_id = str(source.get("primaryGeofabrikId") or "")
    polygon_url = str(source.get("polygonUrl") or "")
    if not primary_id:
        fail("routing.source.primaryGeofabrikId is required")
    if not polygon_url.startswith("https://") or not polygon_url.endswith(".poly"):
        fail("routing.source.polygonUrl must be an HTTPS .poly URL")

    pbfs = source.get("pbfs")
    if not isinstance(pbfs, list) or not pbfs:
        fail("routing.source.pbfs must be a non-empty array")
    ids = []
    for index, item in enumerate(pbfs):
        if not isinstance(item, dict):
            fail(f"routing.source.pbfs[{index}] must be an object")
        source_id = str(item.get("id") or "")
        url = str(item.get("url") or "")
        if not source_id or not url.startswith("https://") or not url.endswith(".osm.pbf"):
            fail(f"invalid routing source PBF at index {index}")
        ids.append(source_id)
    if len(ids) != len(set(ids)):
        fail("routing.source.pbfs contains duplicate ids")
    if primary_id not in ids:
        fail("routing primaryGeofabrikId must be present in routing.source.pbfs")

    package = routing.get("package")
    if not isinstance(package, dict):
        fail("routing.package is required")
    package_template = str(package.get("fileNameTemplate") or "")
    manifest_template = str(package.get("manifestFileNameTemplate") or "")
    if "{version}" not in package_template or not package_template.endswith(".tar"):
        fail("routing package fileNameTemplate must contain {version} and end in .tar")
    if "{version}" not in manifest_template or not manifest_template.endswith("-manifest.json"):
        fail("routing manifestFileNameTemplate must contain {version} and end in -manifest.json")
    if not SAFE_FILE.fullmatch(package_template) or not SAFE_FILE.fullmatch(manifest_template):
        fail("routing package file templates contain unsafe characters")

    routes = routing.get("validationRoutes")
    if not isinstance(routes, list) or not routes:
        fail("routing.validationRoutes must be non-empty")
    border_count = 0
    for index, route in enumerate(routes):
        if not isinstance(route, dict):
            fail(f"routing.validationRoutes[{index}] must be an object")
        if not str(route.get("name") or "").strip():
            fail(f"routing.validationRoutes[{index}].name is required")
        kind = route.get("kind", "interior")
        if kind not in {"interior", "border"}:
            fail(f"routing.validationRoutes[{index}].kind is invalid")
        if kind == "border":
            border_count += 1
        validate_coordinate(route.get("start"), f"routing.validationRoutes[{index}].start")
        validate_coordinate(route.get("end"), f"routing.validationRoutes[{index}].end")
    if border_count == 0:
        fail("at least one routing border validation route is required")
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    path = Path(args.config)
    config = json.loads(path.read_text(encoding="utf-8"))

    if config.get("schemaVersion") != 1:
        fail("region config schemaVersion must be 1")

    region_id = str(config.get("id") or "")
    if not SAFE_ID.fullmatch(region_id):
        fail("invalid region id")
    if not str(config.get("name") or "").strip():
        fail("region name is required")

    overture_enabled = validate_overture(config.get("overture"))
    routing_enabled = validate_routing(config.get("routing"))
    visual_enabled = validate_visual(config.get("visual"), config.get("routing"))
    if not overture_enabled and not routing_enabled and not visual_enabled:
        fail("region config must enable at least one supported dataset")

    enabled = []
    if overture_enabled:
        enabled.append("overture")
    if routing_enabled:
        enabled.append("routing")
    if visual_enabled:
        enabled.append("visual")
    print(f"{region_id}: region config is valid ({', '.join(enabled)})")


if __name__ == "__main__":
    main()
