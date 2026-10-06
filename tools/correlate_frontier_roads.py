#!/usr/bin/env python3
"""Correlate stable frontier-road anchors independently into two Valhalla graphs.

This stage is graph-bound evidence generation, not route proof. It retains every
usable Valhalla locate candidate, ranks same-OSM-way candidates first as evidence,
and never rejects a frontier anchor solely because heading/direction/access differ.
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
from typing import Any

SCHEMA = "roadpilot.frontier-road-correlations"
VERSION = 1
GENERATOR_NAME = "roadpilot-valhalla-frontier-correlator"
GENERATOR_VERSION = "1"


def fail(message: str) -> None:
    raise SystemExit(message)


def load_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"Could not read {label} {path}: {exc}")
    if not isinstance(value, dict):
        fail(f"{label} must be a JSON object: {path}")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_child(parent: Path, name: str, label: str) -> Path:
    root = parent.resolve()
    path = (parent / name).resolve()
    if path.parent != root:
        fail(f"{label} escapes its build directory: {name}")
    return path


def run_capture(command: list[str]) -> str:
    try:
        result = subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as exc:
        fail(f"Could not execute {command[0]}: {exc}")
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        fail(f"Command failed ({result.returncode}): {' '.join(command)}\n{detail}")
    return result.stdout


def required_string(value: Any, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        fail(f"{label} is required")
    return text


def load_inventory(path: Path) -> dict[str, Any]:
    inventory = load_object(path, "frontier inventory")
    if (
        inventory.get("schema") != "roadpilot.frontier-road-inventory"
        or inventory.get("version") != 1
    ):
        fail("Unsupported frontier-road inventory schema/version")
    for key in (
        "pairId",
        "fromRegionId",
        "toRegionId",
        "fromBoundaryFingerprint",
        "toBoundaryFingerprint",
    ):
        required_string(inventory.get(key), f"inventory.{key}")
    expected_pair = f"{inventory['fromRegionId']}__{inventory['toRegionId']}"
    if inventory["pairId"] != expected_pair:
        fail(f"inventory.pairId mismatch: expected {expected_pair}, got {inventory['pairId']}")
    roads = inventory.get("roads")
    if not isinstance(roads, list):
        fail("inventory.roads must be an array")
    return inventory


def graph_manifest_info(
    manifest_path: Path,
    expected_region: str,
    neighbor_primary_id: str,
    expected_boundary_fingerprint: str,
    temp_root: Path,
    label: str,
) -> tuple[dict[str, Any], Path]:
    manifest = load_object(manifest_path, f"{label} routing manifest")
    if (
        manifest.get("schema") != "roadpilot-routing-pack"
        or manifest.get("schemaVersion") != 1
    ):
        fail(f"{label} routing manifest has unsupported schema/version")

    region_id = required_string(manifest.get("regionId"), f"{label}.regionId")
    if region_id != expected_region:
        fail(
            f"{label} region mismatch: expected {expected_region}, got {region_id}"
        )

    package_version = required_string(
        manifest.get("packageVersion"), f"{label}.packageVersion"
    )
    graph_fingerprint = required_string(
        manifest.get("graphFingerprint"), f"{label}.graphFingerprint"
    )
    source = manifest.get("source")
    if not isinstance(source, dict):
        fail(f"{label}.source must be an object")
    primary_id = required_string(
        source.get("primaryGeofabrikId"), f"{label}.source.primaryGeofabrikId"
    )

    graph_index = manifest.get("graphIndex")
    if not isinstance(graph_index, dict):
        fail(f"{label}.graphIndex must be an object")
    boundary_fingerprints = graph_index.get("boundaryFingerprints")
    if not isinstance(boundary_fingerprints, dict):
        fail(f"{label}.graphIndex.boundaryFingerprints must be an object")
    actual_boundary = boundary_fingerprints.get(neighbor_primary_id)
    if actual_boundary != expected_boundary_fingerprint:
        fail(
            f"{label} boundary fingerprint for {neighbor_primary_id} is stale/mismatched: "
            f"inventory={expected_boundary_fingerprint} manifest={actual_boundary}"
        )

    artifact = manifest.get("artifact")
    if not isinstance(artifact, dict):
        fail(f"{label}.artifact must be an object")
    artifact_name = required_string(artifact.get("fileName"), f"{label}.artifact.fileName")
    artifact_path = safe_child(manifest_path.parent, artifact_name, f"{label} artifact")
    if not artifact_path.is_file():
        fail(f"{label} artifact does not exist: {artifact_path}")

    actual_sha = sha256_file(artifact_path)
    expected_sha = graph_fingerprint.removeprefix("sha256:")
    if graph_fingerprint != f"sha256:{actual_sha}" or expected_sha != actual_sha:
        fail(
            f"{label} graph fingerprint does not match retained routing artifact"
        )
    declared_sha = artifact.get("sha256")
    if declared_sha is not None and str(declared_sha) != actual_sha:
        fail(f"{label} artifact.sha256 does not match retained routing artifact")

    if shutil.which("valhalla_build_config") is None:
        fail("valhalla_build_config is required")
    if shutil.which("valhalla_service") is None:
        fail("valhalla_service is required")

    graph_root = temp_root / label
    tile_dir = graph_root / "tiles"
    graph_root.mkdir(parents=True, exist_ok=True)
    tile_dir.mkdir(parents=True, exist_ok=True)
    config_text = run_capture(
        [
            "valhalla_build_config",
            "--mjolnir-tile-dir",
            str(tile_dir),
            "--mjolnir-tile-extract",
            str(artifact_path),
        ]
    )
    try:
        config = json.loads(config_text)
    except json.JSONDecodeError as exc:
        fail(f"{label} valhalla_build_config returned invalid JSON: {exc}")
    if not isinstance(config, dict):
        fail(f"{label} Valhalla config must be an object")
    config_path = graph_root / "valhalla.json"
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

    return (
        {
            "regionId": region_id,
            "packageVersion": package_version,
            "graphFingerprint": graph_fingerprint,
            "primaryGeofabrikId": primary_id,
        },
        config_path,
    )


def haversine_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6371008.8
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = (
        math.sin(dp / 2.0) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dl / 2.0) ** 2
    )
    return radius * 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))


def numeric(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    return None


def positive_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str):
        try:
            parsed = int(value)
        except ValueError:
            return None
        return parsed if parsed > 0 else None
    return None


def candidate_way_id(edge: dict[str, Any]) -> int | None:
    info = edge.get("edge_info")
    if isinstance(info, dict):
        result = positive_int(info.get("way_id"))
        if result is not None:
            return result
    return positive_int(edge.get("way_id"))


def graph_id(edge: dict[str, Any]) -> int | None:
    value = edge.get("edge_id")
    if isinstance(value, dict):
        return positive_int(value.get("value"))
    return positive_int(value)


def edge_names(edge: dict[str, Any]) -> list[str]:
    info = edge.get("edge_info")
    if not isinstance(info, dict):
        return []
    names = info.get("names")
    if not isinstance(names, list):
        return []
    return sorted({str(name).strip() for name in names if str(name).strip()})


def edge_access(edge: dict[str, Any]) -> dict[str, bool]:
    value = edge.get("edge")
    if not isinstance(value, dict):
        return {}
    access = value.get("access")
    if not isinstance(access, dict):
        return {}
    return {
        str(key): bool(enabled)
        for key, enabled in sorted(access.items())
        if isinstance(enabled, bool)
    }


def road_class(edge: dict[str, Any]) -> str | None:
    value = edge.get("edge")
    if not isinstance(value, dict):
        return None
    classification = value.get("classification")
    if not isinstance(classification, dict):
        return None
    road_class_value = classification.get("classification")
    return (
        str(road_class_value)
        if isinstance(road_class_value, str) and road_class_value
        else None
    )


def edge_use(edge: dict[str, Any]) -> str | None:
    value = edge.get("edge")
    if not isinstance(value, dict):
        return None
    use = value.get("use")
    return str(use) if isinstance(use, str) and use else None


def locate_side(
    config_path: Path,
    lat: float,
    lng: float,
    stable_way_id: int,
) -> dict[str, Any]:
    request = json.dumps(
        {"locations": [{"lat": lat, "lon": lng}], "verbose": True},
        separators=(",", ":"),
    )
    try:
        result = subprocess.run(
            ["valhalla_service", str(config_path), "locate", request],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as exc:
        return {
            "status": "LOCATE_FAILED",
            "error": f"Could not execute valhalla_service: {exc}",
            "candidateCount": 0,
            "sameWayCandidateCount": 0,
            "candidates": [],
        }

    if result.returncode != 0:
        return {
            "status": "LOCATE_FAILED",
            "error": (result.stderr.strip() or result.stdout.strip() or "Valhalla locate failed"),
            "candidateCount": 0,
            "sameWayCandidateCount": 0,
            "candidates": [],
        }

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return {
            "status": "LOCATE_FAILED",
            "error": f"Valhalla locate returned invalid JSON: {exc}",
            "candidateCount": 0,
            "sameWayCandidateCount": 0,
            "candidates": [],
        }

    if not isinstance(payload, list) or not payload or not isinstance(payload[0], dict):
        return {
            "status": "NO_CANDIDATES",
            "candidateCount": 0,
            "sameWayCandidateCount": 0,
            "candidates": [],
        }
    edges = payload[0].get("edges")
    if not isinstance(edges, list):
        edges = []

    candidates = []
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        correlated_lat = numeric(edge.get("correlated_lat"))
        correlated_lng = numeric(edge.get("correlated_lon"))
        if correlated_lat is None or correlated_lng is None:
            continue
        way_id = candidate_way_id(edge)
        percent = numeric(edge.get("percent_along"))
        if percent is not None and not (0.0 <= percent <= 1.0):
            percent = None
        heading = numeric(edge.get("heading"))
        if heading is not None:
            heading %= 360.0
        linear_reference = edge.get("linear_reference")
        if not isinstance(linear_reference, str) or not linear_reference:
            linear_reference = None

        candidates.append(
            {
                "rank": 0,
                "wayMatch": way_id == stable_way_id,
                "correlatedCoordinate": {
                    "lat": correlated_lat,
                    "lng": correlated_lng,
                },
                "wayId": way_id,
                "percentAlong": percent,
                "distanceMeters": haversine_meters(
                    lat, lng, correlated_lat, correlated_lng
                ),
                "headingDegrees": heading,
                "linearReference": linear_reference,
                "graphId": graph_id(edge),
                "roadNames": edge_names(edge),
                "access": edge_access(edge),
                "roadClass": road_class(edge),
                "use": edge_use(edge),
            }
        )

    candidates.sort(
        key=lambda item: (
            not item["wayMatch"],
            item["distanceMeters"],
            item["graphId"] if item["graphId"] is not None else 2**63 - 1,
        )
    )
    for rank, item in enumerate(candidates):
        item["rank"] = rank
    same_way_count = sum(1 for item in candidates if item["wayMatch"])
    return {
        "status": "CORRELATED" if candidates else "NO_CANDIDATES",
        "candidateCount": len(candidates),
        "sameWayCandidateCount": same_way_count,
        "candidates": candidates,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--from-manifest", required=True, type=Path)
    parser.add_argument("--to-manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    for path in (args.inventory, args.from_manifest, args.to_manifest):
        if not path.is_file():
            fail(f"Input does not exist: {path}")

    inventory = load_inventory(args.inventory)
    from_region = required_string(inventory.get("fromRegionId"), "inventory.fromRegionId")
    to_region = required_string(inventory.get("toRegionId"), "inventory.toRegionId")

    from_manifest_preview = load_object(args.from_manifest, "from routing manifest")
    to_manifest_preview = load_object(args.to_manifest, "to routing manifest")
    from_source = from_manifest_preview.get("source")
    to_source = to_manifest_preview.get("source")
    if not isinstance(from_source, dict) or not isinstance(to_source, dict):
        fail("Both routing manifests must contain source objects")
    from_primary = required_string(
        from_source.get("primaryGeofabrikId"), "from source.primaryGeofabrikId"
    )
    to_primary = required_string(
        to_source.get("primaryGeofabrikId"), "to source.primaryGeofabrikId"
    )

    with tempfile.TemporaryDirectory(prefix="roadpilot-correlation-") as temp:
        temp_root = Path(temp)
        from_graph, from_config = graph_manifest_info(
            args.from_manifest,
            from_region,
            to_primary,
            required_string(
                inventory.get("fromBoundaryFingerprint"),
                "inventory.fromBoundaryFingerprint",
            ),
            temp_root,
            "from",
        )
        to_graph, to_config = graph_manifest_info(
            args.to_manifest,
            to_region,
            from_primary,
            required_string(
                inventory.get("toBoundaryFingerprint"),
                "inventory.toBoundaryFingerprint",
            ),
            temp_root,
            "to",
        )

        correlations = []
        roads = inventory.get("roads") or []
        for index, road in enumerate(roads):
            if not isinstance(road, dict):
                fail(f"inventory road[{index}] must be an object")
            road_id = required_string(road.get("id"), f"road[{index}].id")
            way_id = positive_int(road.get("wayId"))
            if way_id is None:
                fail(f"road[{index}].wayId must be a positive integer")
            coordinate = road.get("crossingCoordinate")
            if not isinstance(coordinate, dict):
                fail(f"road[{index}].crossingCoordinate must be an object")
            lat = numeric(coordinate.get("lat"))
            lng = numeric(coordinate.get("lng"))
            if lat is None or lng is None:
                fail(f"road[{index}] has invalid crossingCoordinate")
            frontier_heading = numeric(road.get("headingDegrees"))
            if frontier_heading is None or not (0.0 <= frontier_heading < 360.0):
                fail(f"road[{index}] has invalid headingDegrees")
            routing_tags = road.get("routingTags")
            if not isinstance(routing_tags, dict) or not all(
                isinstance(key, str) and isinstance(value, str)
                for key, value in routing_tags.items()
            ):
                fail(f"road[{index}] has invalid routingTags")

            correlations.append(
                {
                    "frontierRoadId": road_id,
                    "wayId": way_id,
                    "crossingIndex": int(road.get("crossingIndex") or 0),
                    "crossingKind": required_string(
                        road.get("crossingKind"), f"road[{index}].crossingKind"
                    ),
                    "frontierCoordinate": {"lat": lat, "lng": lng},
                    "frontierHeadingDegrees": frontier_heading,
                    "routingTags": {
                        str(key): str(value)
                        for key, value in sorted(routing_tags.items())
                        if isinstance(key, str) and isinstance(value, str)
                    },
                    "fromGraph": locate_side(from_config, lat, lng, way_id),
                    "toGraph": locate_side(to_config, lat, lng, way_id),
                }
            )

    artifact = {
        "schema": SCHEMA,
        "version": VERSION,
        "pairId": inventory["pairId"],
        "fromRegionId": from_region,
        "toRegionId": to_region,
        "fromBoundaryFingerprint": inventory["fromBoundaryFingerprint"],
        "toBoundaryFingerprint": inventory["toBoundaryFingerprint"],
        "fromGraph": from_graph,
        "toGraph": to_graph,
        "generator": {
            "name": GENERATOR_NAME,
            "version": GENERATOR_VERSION,
        },
        "correlations": correlations,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")

    correlated_from = sum(
        1 for item in correlations if item["fromGraph"]["status"] == "CORRELATED"
    )
    correlated_to = sum(
        1 for item in correlations if item["toGraph"]["status"] == "CORRELATED"
    )
    print(
        f"{artifact['pairId']}: {len(correlations)} frontier anchors; "
        f"Graph A correlated {correlated_from}; Graph B correlated {correlated_to}"
    )
    print(f"wrote: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
