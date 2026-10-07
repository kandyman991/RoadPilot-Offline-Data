#!/usr/bin/env python3
"""Validate a RoadPilot visual-map manifest and its exact PMTiles artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from visual_pack import VisualPackError, inspect_pmtiles, load_json_object

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "visual-pack-manifest.schema.json"
ROAD_INDEX_SCHEMA = REPO_ROOT / "schemas" / "visual-road-index.schema.json"
PROFILE_DIR = REPO_ROOT / "visual" / "tilemaker"
FORBIDDEN_LAYERS = {"building", "poi", "poi_detail"}


def fail(message: str) -> None:
    raise SystemExit(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def source_fingerprint(source: dict[str, Any]) -> str:
    payload = {
        "primaryGeofabrikId": source["primaryGeofabrikId"],
        "url": source["url"],
        "sizeBytes": source["sizeBytes"],
        "sha256": source["sha256"],
    }
    return "sha256:" + hashlib.sha256(canonical_bytes(payload)).hexdigest()


def profile_fingerprint() -> str:
    digest = hashlib.sha256()
    for path in (
        PROFILE_DIR / "config.json",
        PROFILE_DIR / "process.lua",
        PROFILE_DIR / "toolchain.json",
    ):
        if not path.is_file():
            fail(f"Current visual profile file is missing: {path}")
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def validate_schema(manifest: dict[str, Any], schema_path: Path) -> None:
    schema = load_json_object(schema_path, "visual manifest schema")
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(manifest), key=lambda err: list(err.path))
    if errors:
        detail = "\n".join(
            f"- {'.'.join(str(part) for part in error.path) or '<root>'}: {error.message}"
            for error in errors[:20]
        )
        fail(f"Visual manifest schema validation failed:\n{detail}")


def validate_road_index(manifest: dict[str, Any], manifest_path: Path) -> None:
    descriptor = manifest.get("roadIndex")
    if descriptor is None:
        return
    if not isinstance(descriptor, dict):
        fail("roadIndex must be an object")
    path = manifest_path.parent / str(descriptor.get("fileName") or "")
    if not path.is_file():
        fail(f"Visual road index does not exist: {path}")
    actual_sha = sha256_file(path)
    if actual_sha != descriptor.get("sha256"):
        fail(
            f"Visual road index SHA mismatch: manifest={descriptor.get('sha256')} actual={actual_sha}"
        )
    value = load_json_object(path, "visual road index")
    schema = load_json_object(ROAD_INDEX_SCHEMA, "visual road index schema")
    errors = sorted(
        Draft202012Validator(schema).iter_errors(value),
        key=lambda err: list(err.path),
    )
    if errors:
        detail = "\n".join(
            f"- {'.'.join(str(part) for part in error.path) or '<root>'}: {error.message}"
            for error in errors[:20]
        )
        fail(f"Visual road index schema validation failed:\n{detail}")
    for key in ("regionId", "packageVersion", "sourceFingerprint", "visualFingerprint"):
        if value.get(key) != manifest.get(key):
            fail(f"Visual road index {key} does not match manifest")
    for key in ("sourceRoadCount", "majorRoadCount", "borderRoadCount", "missingRoadCount"):
        if value.get(key) != descriptor.get(key):
            fail(f"Visual road index {key} summary does not match manifest")
    if value.get("missingRoadCount") != 0:
        fail("Visual road index reports missing required roads")


def approx_equal(a: float, b: float, tolerance: float = 1e-7) -> bool:
    return abs(float(a) - float(b)) <= tolerance


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--package", type=Path)
    parser.add_argument("--schema", default=DEFAULT_SCHEMA, type=Path)
    parser.add_argument(
        "--expect-current-profile",
        action="store_true",
        help="Require profileFingerprint to match the visual profile currently in this checkout.",
    )
    args = parser.parse_args()

    for path, label in ((args.manifest, "manifest"), (args.schema, "schema")):
        if not path.is_file():
            fail(f"{label} does not exist: {path}")

    manifest = load_json_object(args.manifest, "visual manifest")
    validate_schema(manifest, args.schema)

    artifact = manifest["artifact"]
    package_path = args.package or (args.manifest.parent / artifact["fileName"])
    package_path = package_path.resolve()
    if not package_path.is_file():
        fail(f"Visual PMTiles package does not exist: {package_path}")

    actual_size = package_path.stat().st_size
    actual_sha = sha256_file(package_path)
    if actual_size != artifact["sizeBytes"]:
        fail(
            f"Visual PMTiles size mismatch: manifest={artifact['sizeBytes']} actual={actual_size}"
        )
    if actual_sha != artifact["sha256"]:
        fail(
            f"Visual PMTiles SHA mismatch: manifest={artifact['sha256']} actual={actual_sha}"
        )
    if manifest["visualFingerprint"] != f"sha256:{actual_sha}":
        fail("visualFingerprint must equal the exact PMTiles SHA-256")

    expected_source_fp = source_fingerprint(manifest["source"])
    if manifest["sourceFingerprint"] != expected_source_fp:
        fail(
            "sourceFingerprint does not match the manifest source descriptor: "
            f"expected {expected_source_fp}, got {manifest['sourceFingerprint']}"
        )

    if args.expect_current_profile:
        expected_profile_fp = profile_fingerprint()
        if manifest["profileFingerprint"] != expected_profile_fp:
            fail(
                "profileFingerprint does not match this checkout's visual profile: "
                f"expected {expected_profile_fp}, got {manifest['profileFingerprint']}"
            )

    checksum_path = package_path.with_name(package_path.name + ".sha256")
    if checksum_path.is_file():
        expected_line = f"{actual_sha}  {package_path.name}"
        actual_line = checksum_path.read_text(encoding="utf-8").strip()
        if actual_line != expected_line:
            fail(
                f"Visual checksum file mismatch: expected {expected_line!r}, got {actual_line!r}"
            )

    required_layers = set(manifest["validation"]["requiredLayers"])
    manifest_layers = set(manifest["layers"])
    if not required_layers <= manifest_layers:
        fail(
            "Manifest requiredLayers are not all declared in layers: "
            + ", ".join(sorted(required_layers - manifest_layers))
        )
    forbidden = sorted(FORBIDDEN_LAYERS & manifest_layers)
    if forbidden:
        fail("Visual manifest contains forbidden dense layers: " + ", ".join(forbidden))

    try:
        inspection = inspect_pmtiles(
            package_path,
            required_layers=required_layers,
            max_tiles_to_decode=5000,
        )
    except VisualPackError as exc:
        fail(str(exc))

    if inspection["tileType"] != "MVT":
        fail("Visual PMTiles does not contain MVT tiles")
    if inspection["tileCount"] != artifact["tileCount"]:
        fail(
            f"PMTiles tile count mismatch: manifest={artifact['tileCount']} "
            f"actual={inspection['tileCount']}"
        )
    if inspection["minZoom"] != artifact["minZoom"] or inspection["maxZoom"] != artifact["maxZoom"]:
        fail(
            "PMTiles zoom range mismatch: "
            f"manifest={artifact['minZoom']}..{artifact['maxZoom']} "
            f"actual={inspection['minZoom']}..{inspection['maxZoom']}"
        )

    for key in ("minLat", "maxLat", "minLng", "maxLng"):
        if not approx_equal(inspection["bounds"][key], artifact["bounds"][key]):
            fail(
                f"PMTiles bound {key} mismatch: "
                f"manifest={artifact['bounds'][key]} actual={inspection['bounds'][key]}"
            )

    archive_layers = set(inspection["metadataLayers"]) | set(inspection["observedLayers"])
    missing_declared = sorted(archive_layers - manifest_layers)
    if missing_declared:
        fail(
            "PMTiles exposes layers not recorded in the visual manifest: "
            + ", ".join(missing_declared)
        )
    forbidden_archive = sorted(FORBIDDEN_LAYERS & archive_layers)
    if forbidden_archive:
        fail(
            "Generated PMTiles contains forbidden dense layers: "
            + ", ".join(forbidden_archive)
        )

    validate_road_index(manifest, args.manifest.resolve())

    print(
        f"valid visual pack: {manifest['regionId']} {manifest['packageVersion']} "
        f"tiles={inspection['tileCount']} zoom={inspection['minZoom']}..{inspection['maxZoom']} "
        f"decoded={inspection['decodedTileCount']}"
    )
    print("layers:", ", ".join(sorted(manifest_layers)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
