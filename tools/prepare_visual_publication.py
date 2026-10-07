#!/usr/bin/env python3
"""Prepare a credential-free RoadPilot visual publication plan."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

SCHEMA = "roadpilot.publication-plan"
VERSION = 1
CONTRACT = "IMMUTABLE_OBJECTS_THEN_RELEASE_THEN_LATEST"
ARTIFACT_KIND = "VISUAL"


def fail(message: str) -> None:
    raise SystemExit(message)


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def safe_component(value: str, label: str) -> str:
    value = value.strip()
    if not value or value in {".", ".."} or "/" in value or "\\" in value or ".." in value:
        fail(f"{label} contains an unsafe path component: {value!r}")
    return value


def clean_prefix(value: str) -> str:
    parts = [part for part in value.strip("/").split("/") if part]
    if not parts:
        fail("--prefix must contain at least one path component")
    return "/".join(safe_component(part, "prefix") for part in parts)


def raw_sha(value: Any, label: str) -> str:
    text = str(value or "").lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        fail(f"{label} must be a 64-character lowercase SHA-256 digest")
    return text


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"Could not read visual manifest {path}: {exc}")
    if not isinstance(value, dict):
        fail("Visual manifest must be a JSON object")
    if value.get("schema") != "roadpilot-visual-pack" or value.get("schemaVersion") != 1:
        fail("Not a RoadPilot visual-pack v1 manifest")
    return value


def run_existing_pack_validator(manifest_path: Path, package_path: Path) -> None:
    validator = Path(__file__).with_name("validate_visual_pack.py")
    if not validator.is_file():
        fail(f"Visual-pack validator is missing: {validator}")
    result = subprocess.run(
        [
            sys.executable,
            str(validator),
            "--manifest",
            str(manifest_path),
            "--package",
            str(package_path),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "visual-pack validation failed"
        fail(f"Refusing publication of invalid visual pack: {detail}")


def source_object(
    *,
    role: str,
    path: Path,
    key: str,
    content_type: str,
    expected_sha: str | None = None,
) -> dict[str, Any]:
    if not path.is_file():
        fail(f"Missing publication input: {path}")
    actual_sha = sha256_file(path)
    if expected_sha is not None and actual_sha != expected_sha:
        fail(f"SHA-256 mismatch for {path.name}: expected {expected_sha}, got {actual_sha}")
    size = path.stat().st_size
    if size <= 0:
        fail(f"Publication input is empty: {path}")
    return {
        "role": role,
        "sourcePath": str(path.resolve()),
        "key": key,
        "sizeBytes": size,
        "sha256": actual_sha,
        "contentType": content_type,
    }


def published_object(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "role": source["role"],
        "key": source["key"],
        "fileName": Path(source["sourcePath"]).name,
        "sizeBytes": source["sizeBytes"],
        "sha256": source["sha256"],
        "contentType": source["contentType"],
    }


def contained_file(manifest_path: Path, file_name: str, label: str) -> Path:
    safe_component(file_name, label)
    parent = manifest_path.parent.resolve()
    path = (parent / file_name).resolve()
    try:
        path.relative_to(parent)
    except ValueError:
        fail(f"{label} escapes the visual build directory")
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--prefix", default="visual")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    manifest_path = args.manifest.resolve()
    if not manifest_path.is_file():
        fail(f"Visual manifest does not exist: {manifest_path}")
    manifest = load_manifest(manifest_path)

    region_id = safe_component(str(manifest.get("regionId") or ""), "regionId")
    version = safe_component(str(manifest.get("packageVersion") or ""), "packageVersion")
    built_at = str(manifest.get("builtAtUtc") or "").strip()
    if not built_at:
        fail("builtAtUtc is required")

    artifact = manifest.get("artifact")
    if not isinstance(artifact, dict):
        fail("manifest.artifact is required")
    package_name = safe_component(str(artifact.get("fileName") or ""), "artifact.fileName")
    package_path = contained_file(manifest_path, package_name, "artifact.fileName")

    run_existing_pack_validator(manifest_path, package_path)

    package_sha_raw = raw_sha(artifact.get("sha256"), "artifact.sha256")
    package_sha = "sha256:" + package_sha_raw
    if str(manifest.get("visualFingerprint") or "") != package_sha:
        fail("visualFingerprint must equal the exact PMTiles SHA-256")

    checksum_path = contained_file(
        manifest_path,
        f"{package_name}.sha256",
        "artifact checksum file",
    )
    if not checksum_path.is_file():
        fail(f"Missing visual checksum file: {checksum_path}")
    checksum_text = checksum_path.read_text(encoding="utf-8").strip()
    if checksum_text != f"{package_sha_raw}  {package_name}":
        fail("Visual checksum file does not exactly match manifest artifact SHA/name")

    road_index = manifest.get("roadIndex")
    if not isinstance(road_index, dict):
        fail("Production visual publication requires a validated roadIndex")
    if int(road_index.get("missingRoadCount") or 0) != 0:
        fail("Production visual publication requires roadIndex.missingRoadCount=0")
    road_index_name = safe_component(
        str(road_index.get("fileName") or ""),
        "roadIndex.fileName",
    )
    road_index_path = contained_file(manifest_path, road_index_name, "roadIndex.fileName")
    road_index_sha = "sha256:" + raw_sha(road_index.get("sha256"), "roadIndex.sha256")

    prefix = clean_prefix(args.prefix)
    immutable_prefix = f"{prefix}/{region_id}/{version}"

    sources = [
        source_object(
            role="ARTIFACT",
            path=package_path,
            key=f"{immutable_prefix}/{package_name}",
            content_type="application/vnd.pmtiles",
            expected_sha=package_sha,
        ),
        source_object(
            role="MANIFEST",
            path=manifest_path,
            key=f"{immutable_prefix}/{manifest_path.name}",
            content_type="application/json",
        ),
        source_object(
            role="CHECKSUM",
            path=checksum_path,
            key=f"{immutable_prefix}/{checksum_path.name}",
            content_type="text/plain; charset=utf-8",
        ),
        source_object(
            role="AUXILIARY",
            path=road_index_path,
            key=f"{immutable_prefix}/{road_index_name}",
            content_type="application/json",
            expected_sha=road_index_sha,
        ),
    ]
    sources.sort(key=lambda item: (item["role"], item["key"]))

    release = {
        "schema": "roadpilot.publication-release",
        "version": 1,
        "artifactKind": ARTIFACT_KIND,
        "regionId": region_id,
        "packageVersion": version,
        "builtAtUtc": built_at,
        "immutablePrefix": immutable_prefix,
        "objects": [published_object(item) for item in sources],
        "metadata": {
            "visualFingerprint": manifest.get("visualFingerprint"),
            "profileFingerprint": manifest.get("profileFingerprint"),
            "sourceFingerprint": manifest.get("sourceFingerprint"),
            "tilemakerVersion": manifest.get("tilemakerVersion"),
            "artifactSha256": package_sha,
            "artifactSizeBytes": int(artifact.get("sizeBytes") or 0),
            "tileCount": int(artifact.get("tileCount") or 0),
            "minZoom": int(artifact.get("minZoom") or 0),
            "maxZoom": int(artifact.get("maxZoom") or 0),
            "layers": list(manifest.get("layers") or []),
            "roadIndex": {
                "sha256": road_index_sha,
                "sourceRoadCount": int(road_index.get("sourceRoadCount") or 0),
                "majorRoadCount": int(road_index.get("majorRoadCount") or 0),
                "borderRoadCount": int(road_index.get("borderRoadCount") or 0),
                "missingRoadCount": int(road_index.get("missingRoadCount") or 0),
            },
        },
    }
    release_body = canonical_json_bytes(release)
    release_sha = sha256_bytes(release_body)
    release_key = f"{immutable_prefix}/release.json"
    latest_key = f"{prefix}/{region_id}/latest.json"
    latest = {
        "schema": "roadpilot.publication-latest",
        "version": 1,
        "artifactKind": ARTIFACT_KIND,
        "regionId": region_id,
        "packageVersion": version,
        "releaseKey": release_key,
        "releaseSha256": release_sha,
        "builtAtUtc": built_at,
    }

    plan = {
        "schema": SCHEMA,
        "version": VERSION,
        "contract": CONTRACT,
        "releaseKey": release_key,
        "releaseSha256": release_sha,
        "release": release,
        "latestKey": latest_key,
        "latest": latest,
        "sourceObjects": sources,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical_json_bytes(plan))
    print(f"visual publication plan: {region_id} {version}")
    print(f"immutable objects: {len(sources)}")
    print(f"release: {release_key} {release_sha}")
    print(f"latest: {latest_key}")
    print(f"wrote: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
