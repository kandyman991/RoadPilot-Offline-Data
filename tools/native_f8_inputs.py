#!/usr/bin/env python3
"""Shared read-only input helpers for the native, uncapped F8 graph scan.

No OSM frontier sampling, inferred graph equivalence or legacy correlations.
Retained routing-archive hashes and neighbor boundary fingerprints are checked
before opening any native Valhalla GraphReader.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any
from shapely.geometry import Polygon, shape
from shapely.ops import unary_union

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
