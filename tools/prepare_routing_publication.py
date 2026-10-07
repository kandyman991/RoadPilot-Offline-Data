#!/usr/bin/env python3
"""Prepare a credential-free RoadPilot routing publication plan.

This does not contact R2. It validates the retained routing pack, enumerates every
immutable publication object, creates a deterministic immutable release descriptor,
and creates the mutable latest-pointer payload that may be advanced only after all
immutable objects are confirmed by a publisher backend.
"""

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
ARTIFACT_KIND = "ROUTING"


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
    if not value or value in {".", ".."}:
        fail(f"{label} is empty/unsafe")
    if "/" in value or "\\" in value or ".." in value:
        fail(f"{label} contains an unsafe path component: {value}")
    return value


def clean_prefix(value: str) -> str:
    parts = [part for part in value.strip("/").split("/") if part]
    if not parts:
        fail("--prefix must contain at least one path component")
    return "/".join(safe_component(part, "prefix") for part in parts)


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"Could not read routing manifest {path}: {exc}")
    if not isinstance(value, dict):
        fail("Routing manifest must be a JSON object")
    if value.get("schema") != "roadpilot-routing-pack" or value.get("schemaVersion") != 1:
        fail("Not a RoadPilot routing-pack v1 manifest")
    return value


def run_existing_pack_validator(manifest_path: Path, package_path: Path) -> None:
    validator = Path(__file__).with_name("validate_routing_pack.py")
    if not validator.is_file():
        fail(f"Routing-pack validator is missing: {validator}")
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
        detail = result.stderr.strip() or result.stdout.strip() or "routing-pack validation failed"
        fail(f"Refusing publication of invalid routing pack: {detail}")


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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--prefix", default="routing")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    manifest_path = args.manifest.resolve()
    if not manifest_path.is_file():
        fail(f"Routing manifest does not exist: {manifest_path}")
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
    package_path = (manifest_path.parent / package_name).resolve()
    try:
        package_path.relative_to(manifest_path.parent.resolve())
    except ValueError:
        fail("artifact.fileName escapes the manifest directory")

    run_existing_pack_validator(manifest_path, package_path)

    package_sha_raw = str(artifact.get("sha256") or "").lower()
    if len(package_sha_raw) != 64:
        fail("artifact.sha256 must be a 64-character digest")
    package_sha = "sha256:" + package_sha_raw
    if str(manifest.get("graphFingerprint") or "") != package_sha:
        fail("graphFingerprint must equal the package SHA-256")

    checksum_path = manifest_path.parent / f"{package_name}.sha256"
    if not checksum_path.is_file():
        fail(f"Missing routing checksum file: {checksum_path}")
    checksum_text = checksum_path.read_text(encoding="utf-8").strip()
    if checksum_text != f"{package_sha_raw}  {package_name}":
        fail("Routing checksum file does not exactly match manifest artifact SHA/name")

    prefix = clean_prefix(args.prefix)
    immutable_prefix = f"{prefix}/{region_id}/{version}"

    sources = [
        source_object(
            role="ARTIFACT",
            path=package_path,
            key=f"{immutable_prefix}/{package_name}",
            content_type="application/x-tar",
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
    ]

    graph_index = manifest.get("graphIndex")
    if graph_index is not None:
        if not isinstance(graph_index, dict):
            fail("manifest.graphIndex must be an object when present")
        graph_index_name = safe_component(str(graph_index.get("fileName") or ""), "graphIndex.fileName")
        graph_index_sha_raw = str(graph_index.get("sha256") or "").lower()
        if len(graph_index_sha_raw) != 64:
            fail("graphIndex.sha256 must be a 64-character digest")
        graph_index_path = (manifest_path.parent / graph_index_name).resolve()
        try:
            graph_index_path.relative_to(manifest_path.parent.resolve())
        except ValueError:
            fail("graphIndex.fileName escapes the manifest directory")
        sources.append(
            source_object(
                role="GRAPH_INDEX",
                path=graph_index_path,
                key=f"{immutable_prefix}/{graph_index_name}",
                content_type="application/json",
                expected_sha="sha256:" + graph_index_sha_raw,
            )
        )

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
            "graphFingerprint": manifest.get("graphFingerprint"),
            "valhallaVersion": manifest.get("valhallaVersion"),
            "artifactSha256": package_sha,
            "artifactSizeBytes": int(artifact.get("sizeBytes") or 0),
            "tileCount": int(artifact.get("tileCount") or 0),
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
    print(f"publication plan: {region_id} {version}")
    print(f"immutable objects: {len(sources)}")
    print(f"release: {release_key} {release_sha}")
    print(f"latest: {latest_key}")
    print(f"wrote: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
