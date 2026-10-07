#!/usr/bin/env python3
"""Validate a RoadPilot publication plan and all of its local source objects."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

CONTRACT = "IMMUTABLE_OBJECTS_THEN_RELEASE_THEN_LATEST"


def fail(message: str) -> None:
    raise SystemExit(message)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def safe_key(value: Any, label: str) -> str:
    require(isinstance(value, str) and value and not value.startswith("/"), f"{label} invalid")
    parts = value.split("/")
    require(all(part not in {"", ".", ".."} for part in parts), f"{label} contains unsafe path components")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True, type=Path)
    args = parser.parse_args()

    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    require(isinstance(plan, dict), "plan must be an object")
    require(plan.get("schema") == "roadpilot.publication-plan", "unexpected plan schema")
    require(plan.get("version") == 1, "plan version must be 1")
    require(plan.get("contract") == CONTRACT, "unexpected publication contract")

    release = plan.get("release")
    latest = plan.get("latest")
    sources = plan.get("sourceObjects")
    require(isinstance(release, dict), "release required")
    require(isinstance(latest, dict), "latest required")
    require(isinstance(sources, list) and sources, "sourceObjects must be non-empty")

    require(release.get("schema") == "roadpilot.publication-release", "unexpected release schema")
    require(release.get("version") == 1, "release version must be 1")
    require(latest.get("schema") == "roadpilot.publication-latest", "unexpected latest schema")
    require(latest.get("version") == 1, "latest version must be 1")

    immutable_prefix = safe_key(release.get("immutablePrefix"), "release.immutablePrefix")
    release_key = safe_key(plan.get("releaseKey"), "releaseKey")
    latest_key = safe_key(plan.get("latestKey"), "latestKey")
    require(release_key == f"{immutable_prefix}/release.json", "releaseKey must live at immutablePrefix/release.json")
    require(not latest_key.startswith(immutable_prefix + "/"), "latestKey must be outside immutable version prefix")

    release_sha = plan.get("releaseSha256")
    require(
        isinstance(release_sha, str) and release_sha == sha256_bytes(canonical_json_bytes(release)),
        "releaseSha256 does not match canonical release body",
    )

    for key in ("artifactKind", "regionId", "packageVersion", "builtAtUtc"):
        require(latest.get(key) == release.get(key), f"latest.{key} must match release")
    require(latest.get("releaseKey") == release_key, "latest.releaseKey mismatch")
    require(latest.get("releaseSha256") == release_sha, "latest.releaseSha256 mismatch")

    release_objects = release.get("objects")
    require(isinstance(release_objects, list) and release_objects, "release.objects must be non-empty")
    require(len(release_objects) == len(sources), "sourceObjects/release.objects length mismatch")

    published_by_key: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(release_objects):
        label = f"release.objects[{index}]"
        require(isinstance(item, dict), f"{label} must be an object")
        key = safe_key(item.get("key"), f"{label}.key")
        require(key.startswith(immutable_prefix + "/"), f"{label}.key must be under immutablePrefix")
        require(key not in published_by_key, f"duplicate immutable key: {key}")
        published_by_key[key] = item

    seen_source_keys = set()
    for index, source in enumerate(sources):
        label = f"sourceObjects[{index}]"
        require(isinstance(source, dict), f"{label} must be an object")
        key = safe_key(source.get("key"), f"{label}.key")
        require(key not in seen_source_keys, f"duplicate source key: {key}")
        seen_source_keys.add(key)
        published = published_by_key.get(key)
        require(published is not None, f"{label}.key missing from release.objects")

        source_path = Path(str(source.get("sourcePath") or ""))
        require(source_path.is_file(), f"{label}.sourcePath missing: {source_path}")
        size = source_path.stat().st_size
        digest = sha256_file(source_path)
        require(source.get("sizeBytes") == size, f"{label}.sizeBytes mismatch")
        require(source.get("sha256") == digest, f"{label}.sha256 mismatch")
        require(published.get("role") == source.get("role"), f"{label}.role mismatch")
        require(published.get("fileName") == source_path.name, f"{label}.fileName mismatch")
        require(published.get("sizeBytes") == size, f"{label} release size mismatch")
        require(published.get("sha256") == digest, f"{label} release SHA mismatch")
        require(published.get("contentType") == source.get("contentType"), f"{label}.contentType mismatch")

    print(
        f"valid publication plan: {release['artifactKind']} "
        f"{release['regionId']} {release['packageVersion']} "
        f"objects={len(sources)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
