#!/usr/bin/env python3
"""Move a local RoadPilot latest pointer to an existing immutable release.

Rollback never deletes or mutates immutable version objects.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any


def fail(message: str) -> None:
    raise SystemExit(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def store_path(root: Path, key: str) -> Path:
    if not key or key.startswith("/"):
        fail(f"Unsafe object key: {key!r}")
    parts = key.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        fail(f"Unsafe object key: {key}")
    target = (root / key).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError:
        fail(f"Object key escapes store root: {key}")
    return target


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--store-root", required=True, type=Path)
    parser.add_argument("--release-key", required=True)
    args = parser.parse_args()

    root = args.store_root.resolve()
    release_path = store_path(root, args.release_key)
    if not release_path.is_file():
        fail(f"Release does not exist: {args.release_key}")

    try:
        release = json.loads(release_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"Release JSON is invalid: {exc}")
    if not isinstance(release, dict):
        fail("Release must be a JSON object")
    if release.get("schema") != "roadpilot.publication-release" or release.get("version") != 1:
        fail("Unsupported publication release")

    immutable_prefix = str(release.get("immutablePrefix") or "")
    expected_release_key = f"{immutable_prefix}/release.json"
    if args.release_key != expected_release_key:
        fail(
            f"release-key does not match release immutablePrefix: "
            f"expected {expected_release_key}"
        )

    for index, item in enumerate(release.get("objects") or []):
        if not isinstance(item, dict):
            fail(f"release.objects[{index}] must be an object")
        key = str(item.get("key") or "")
        path = store_path(root, key)
        if not path.is_file():
            fail(f"Rollback target is incomplete; missing immutable object: {key}")
        if path.stat().st_size != int(item.get("sizeBytes") or -1):
            fail(f"Rollback target object size mismatch: {key}")
        if sha256_file(path) != str(item.get("sha256") or ""):
            fail(f"Rollback target object SHA mismatch: {key}")

    release_sha = sha256_file(release_path)
    parts = immutable_prefix.split("/")
    if len(parts) < 3:
        fail("immutablePrefix must contain artifact namespace, region and version")
    latest_key = "/".join(parts[:-1]) + "/latest.json"
    latest = {
        "schema": "roadpilot.publication-latest",
        "version": 1,
        "artifactKind": release["artifactKind"],
        "regionId": release["regionId"],
        "packageVersion": release["packageVersion"],
        "releaseKey": args.release_key,
        "releaseSha256": release_sha,
        "builtAtUtc": release["builtAtUtc"],
    }

    latest_path = store_path(root, latest_key)
    latest_path.parent.mkdir(parents=True, exist_ok=True)
    temp = latest_path.with_name(f".{latest_path.name}.tmp-{os.getpid()}")
    try:
        temp.write_bytes(canonical_json_bytes(latest))
        os.replace(temp, latest_path)
    finally:
        temp.unlink(missing_ok=True)

    print(
        f"activated existing release: {release['artifactKind']} "
        f"{release['regionId']} {release['packageVersion']}"
    )
    print(f"latest: {latest_key} -> {args.release_key}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
