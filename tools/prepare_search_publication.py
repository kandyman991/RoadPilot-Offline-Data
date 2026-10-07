#!/usr/bin/env python3
"""Prepare a credential-free RoadPilot SEARCH publication plan."""

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
ARTIFACT_KIND = "SEARCH"


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


def contained_file(manifest_path: Path, file_name: str, label: str) -> Path:
    safe_component(file_name, label)
    parent = manifest_path.parent.resolve()
    path = (parent / file_name).resolve()
    try:
        path.relative_to(parent)
    except ValueError:
        fail(f"{label} escapes the retained search build directory")
    return path


def source_object(*, role: str, path: Path, key: str, content_type: str, expected_sha: str | None = None) -> dict[str, Any]:
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
    parser.add_argument("--prefix", default="search")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    manifest_path = args.manifest.resolve()
    if not manifest_path.is_file():
        fail(f"Search manifest does not exist: {manifest_path}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"Could not read search manifest {manifest_path}: {exc}")
    if not isinstance(manifest, dict) or manifest.get("schema") != "roadpilot-search-pack" or manifest.get("schemaVersion") != 1:
        fail("Not a RoadPilot search-pack v1 manifest")
    if manifest.get("artifactKind") != ARTIFACT_KIND:
        fail("Search manifest artifactKind must be SEARCH")
    if manifest.get("validation", {}).get("passed") is not True:
        fail("Refusing publication because retained search validation did not pass")

    region_id = safe_component(str(manifest.get("regionId") or ""), "regionId")
    version = safe_component(str(manifest.get("packVersion") or ""), "packVersion")
    built_at = str(manifest.get("builtAtUtc") or "").strip()
    if not built_at:
        fail("builtAtUtc is required")

    database_name = safe_component(str(manifest.get("fileName") or ""), "fileName")
    database_path = contained_file(manifest_path, database_name, "fileName")
    expected_sha = "sha256:" + str(manifest.get("sha256") or "").lower()
    if len(expected_sha) != 71:
        fail("manifest sha256 must be a 64-character digest")
    if str(manifest.get("searchFingerprint") or "") != expected_sha:
        fail("searchFingerprint must equal the exact SQLite SHA-256")

    validator = Path(__file__).with_name("validate_search_pack.py")
    result = subprocess.run(
        [
            sys.executable,
            str(validator),
            "--manifest",
            str(manifest_path),
            "--database",
            str(database_path),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "search-pack validation failed"
        fail(f"Refusing publication of invalid search pack: {detail}")

    checksum_path = contained_file(manifest_path, f"{database_name}.sha256", "checksum")
    if not checksum_path.is_file():
        fail(f"Missing search checksum file: {checksum_path}")
    checksum_text = checksum_path.read_text(encoding="utf-8").strip()
    raw_sha = expected_sha.removeprefix("sha256:")
    if checksum_text != f"{raw_sha}  {database_name}":
        fail("Search checksum file does not exactly match manifest database SHA/name")

    prefix = clean_prefix(args.prefix)
    immutable_prefix = f"{prefix}/{region_id}/{version}"
    sources = [
        source_object(
            role="ARTIFACT",
            path=database_path,
            key=f"{immutable_prefix}/{database_name}",
            content_type="application/vnd.sqlite3",
            expected_sha=expected_sha,
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

    validation_report = manifest_path.parent / "search-validation.json"
    if validation_report.is_file():
        sources.append(
            source_object(
                role="AUXILIARY",
                path=validation_report,
                key=f"{immutable_prefix}/{validation_report.name}",
                content_type="application/json",
            )
        )
    sources.sort(key=lambda item: (item["role"], item["key"]))

    enrichment = manifest.get("enrichment") if isinstance(manifest.get("enrichment"), dict) else {}
    capabilities = manifest.get("capabilities") if isinstance(manifest.get("capabilities"), dict) else {}
    source = manifest.get("source") if isinstance(manifest.get("source"), dict) else {}
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
            "databaseSchema": manifest.get("databaseSchema"),
            "searchFingerprint": manifest.get("searchFingerprint"),
            "sourceFingerprint": manifest.get("sourceFingerprint"),
            "artifactSha256": expected_sha,
            "artifactSizeBytes": int(manifest.get("sizeBytes") or 0),
            "recordCount": int(manifest.get("recordCount") or 0),
            "categorizedRecordCount": int(enrichment.get("categorizedRecordCount") or 0),
            "sourceRelease": source.get("dataRelease"),
            "runtimeContracts": list(capabilities.get("runtimeContracts") or []),
            "validationTargetCount": int(manifest.get("validation", {}).get("targetCount") or 0),
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
    print(f"search publication plan: {region_id} {version}")
    print(f"immutable objects: {len(sources)}")
    print(f"release: {release_key} {release_sha}")
    print(f"latest: {latest_key}")
    print(f"wrote: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
