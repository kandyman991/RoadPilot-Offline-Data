"""Shared Geofabrik PBF cache for independent routing and visual builds.

The published .osm.pbf.md5 sidecar is small and provides deterministic change
detection without downloading a large PBF again. MD5 is an upstream file
identity/integrity check, not a security signature. Routing/visual pack manifests
continue recording SHA-256 of actual source bytes.

Cache uses stable existing work/cache/<Geofabrik ID>.osm.pbf paths; replacing
a changed download is atomic, and an interrupted download never deletes old
bytes. A process lock protects concurrent Graph Studio builds on Linux.
"""
from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
import re
import shutil
import time
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_CHECK_INTERVAL_SECONDS = 24 * 60 * 60
USER_AGENT = "RoadPilot-Graph-Studio/shared-geofabrik-cache"
CHECKSUM_PATTERN = re.compile(r"^([0-9a-fA-F]{32})(?:\s|$)")


def _file_digest(path: Path, algorithm: str = "md5") -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024 * 2), b""):
            digest.update(block)
    return digest.hexdigest()


def _metadata_path(destination: Path) -> Path:
    return destination.with_name(destination.name + ".source.json")


def _read_metadata(destination: Path) -> dict:
    try:
        value = json.loads(_metadata_path(destination).read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _save_metadata(destination: Path, url: str, checksum: str | None) -> None:
    stat = destination.stat()
    metadata = {
        "schemaVersion": 1,
        "url": url,
        "upstreamMd5": checksum,
        "localBytes": stat.st_size,
        "localMtimeNs": stat.st_mtime_ns,
        "lastCheckedEpoch": time.time(),
    }
    path = _metadata_path(destination)
    temporary = path.with_name(path.name + ".part")
    try:
        temporary.write_text(json.dumps(metadata, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _matches_metadata(path: Path, url: str, metadata: dict) -> bool:
    if not path.is_file() or path.stat().st_size <= 0:
        return False
    stat = path.stat()
    return (metadata.get("url") == url
            and metadata.get("localBytes") == stat.st_size
            and metadata.get("localMtimeNs") == stat.st_mtime_ns)


def _upstream_md5(url: str) -> str:
    request = urllib.request.Request(url + ".md5", headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=25) as response:
        line = response.read(2048).decode("ascii", errors="replace").strip()
    match = CHECKSUM_PATTERN.match(line)
    if not match:
        raise ValueError(f"Geofabrik checksum sidecar is malformed: {url}.md5")
    return match.group(1).lower()


def _migrate_legacy(destination: Path, legacy_path: Path | None) -> None:
    if destination.exists() or legacy_path is None:
        return
    if not legacy_path.is_file() or legacy_path.stat().st_size == 0:
        return
    # Existing visual PBF bytes are reused in-place when both paths are on the
    # same filesystem. A failed hardlink falls back to a safe temporary copy.
    try:
        os.link(legacy_path, destination)
        print(f"shared source cache: linked old visual source {legacy_path}", flush=True)
    except OSError:
        temporary = destination.with_name(destination.name + ".migrating")
        try:
            with legacy_path.open("rb") as src, temporary.open("wb") as out:
                shutil.copyfileobj(src, out, length=1024 * 1024)
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)


def cached_geofabrik_pbf(
    url: str,
    destination: Path,
    *,
    refresh: bool = False,
    legacy_path: Path | None = None,
    check_interval_seconds: int = DEFAULT_CHECK_INTERVAL_SECONDS,
) -> Path:
    """Return a verified cached PBF, refreshing only if upstream MD5 changed.

    On offline reuse the existing bytes remain available and are explicitly
    reported as unverified freshness; a missing cache always fails closed.
    """
    if not url.startswith("https://") or not url.endswith(".osm.pbf"):
        raise ValueError("Geofabrik PBF URL must be HTTPS and end with .osm.pbf")
    if check_interval_seconds < 0:
        raise ValueError("Cache check interval must be non-negative")
    destination.parent.mkdir(parents=True, exist_ok=True)
    lock_path = destination.with_name(destination.name + ".lock")
    with lock_path.open("a+b") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        _migrate_legacy(destination, legacy_path)
        cached = destination.is_file() and destination.stat().st_size > 0
        metadata = _read_metadata(destination)
        trusted_local = _matches_metadata(destination, url, metadata)
        recent = (trusted_local and not refresh and
                  time.time() - float(metadata.get("lastCheckedEpoch", 0)) <
                  check_interval_seconds)
        if recent:
            print(f"shared source cache hit (recent): {destination}", flush=True)
            return destination

        try:
            checksum = _upstream_md5(url)
        except (OSError, ValueError, UnicodeError) as exc:
            if cached and not refresh:
                print(f"shared source cache: offline/unverified upstream freshness for "
                      f"{destination.name}: {exc}; using existing bytes", flush=True)
                return destination
            if refresh:
                raise RuntimeError(f"Cannot refresh {url} without its checksum: {exc}") from exc
            # Not all Geofabrik mirrors expose sidecars. A first-time source
            # can still be downloaded, but it cannot claim checksum validation.
            checksum = None
            print(f"shared source cache: no upstream checksum for {url}: {exc}", flush=True)

        if cached and not refresh and checksum is not None:
            old_checksum = metadata.get("upstreamMd5") if trusted_local else None
            if old_checksum == checksum or _file_digest(destination) == checksum:
                _save_metadata(destination, url, checksum)
                print(f"shared source cache hit (unchanged Geofabrik MD5): {destination}", flush=True)
                return destination

        temporary = destination.with_name(destination.name + ".part")
        temporary.unlink(missing_ok=True)
        print(f"shared source cache download: {url}", flush=True)
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            digest = hashlib.md5()
            count = 0
            with urllib.request.urlopen(request, timeout=120) as response, temporary.open("wb") as out:
                total_header = response.headers.get("Content-Length")
                total = int(total_header) if total_header and total_header.isdigit() else None
                next_report = 64 * 1024 * 1024
                for block in iter(lambda: response.read(1024 * 1024 * 2), b""):
                    out.write(block)
                    digest.update(block)
                    count += len(block)
                    if count >= next_report:
                        label = f"{count / (1024 * 1024):.0f} MiB"
                        if total:
                            label += f" / {total / (1024 * 1024):.0f} MiB"
                        print(f"shared source cache: {destination.name} {label}", flush=True)
                        next_report += 64 * 1024 * 1024
            if count <= 0:
                raise RuntimeError(f"Downloaded empty Geofabrik source: {url}")
            if checksum is not None and digest.hexdigest() != checksum:
                raise RuntimeError(
                    f"Geofabrik checksum mismatch for {url}; keeping prior cached source"
                )
            # Never remove/overwrite the old good copy until fully downloaded.
            temporary.replace(destination)
            _save_metadata(destination, url, checksum)
            print(f"shared source cache ready: {destination.name} ({count} bytes)", flush=True)
            return destination
        finally:
            temporary.unlink(missing_ok=True)
