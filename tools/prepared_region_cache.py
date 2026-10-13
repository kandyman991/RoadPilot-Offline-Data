"""Provenance-controlled reuse of extracted region source and Valhalla context.

The broad OSM merge is only needed to create a reference-complete regional clip
and untruncated Valhalla admin context. Keep their *much smaller* products
between builds and remove the huge temporary merged PBF after successful prep.

A changed input SHA, nominal buffer polygon, engine version or edited output
invalidates the cache, so no stale graph inputs can be silently reused.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

CACHE_FORMAT = 1
RETAINED_FILES = ("buffered.osm.pbf", "admins.sqlite", "timezones.sqlite")


def prepare_key(source_records: list[dict], buffer_sha256: str, valhalla_version: str) -> str:
    canonical = {
        "format": CACHE_FORMAT,
        "sources": [{"id": p["id"], "url": p["url"], "sha256": p["sha256"]}
                    for p in source_records],
        "bufferSha256": buffer_sha256,
        "valhallaVersion": valhalla_version,
    }
    raw = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def checksum(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(2 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def source_preparation_ready(directory: Path, key: str) -> bool:
    metadata = directory / "source-preparation.json"
    try:
        record = json.loads(metadata.read_text(encoding="utf-8"))
        if record.get("format") != CACHE_FORMAT or record.get("key") != key:
            return False
        for name in RETAINED_FILES:
            path = directory / name
            if not path.is_file() or path.stat().st_size <= 0:
                return False
            recorded = record["files"][name]
            if recorded["size"] != path.stat().st_size or recorded["sha256"] != checksum(path):
                return False
        return True
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return False


def record_source_preparation(directory: Path, key: str) -> None:
    record = {"format": CACHE_FORMAT, "key": key, "files": {}}
    for name in RETAINED_FILES:
        path = directory / name
        if not path.is_file() or path.stat().st_size <= 0:
            raise RuntimeError(f"Cannot retain incomplete regional source: {path}")
        record["files"][name] = {"size": path.stat().st_size, "sha256": checksum(path)}
    destination = directory / "source-preparation.json"
    temporary = destination.with_name(destination.name + ".part")
    try:
        temporary.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n",
                             encoding="utf-8")
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
