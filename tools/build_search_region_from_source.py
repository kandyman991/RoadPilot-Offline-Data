#!/usr/bin/env python3
"""Build one retained RoadPilot search pack directly from current Overture Places.

This is the source-aware entry point used by Graph Studio. It keeps source
retrieval/cache concerns out of the retained-pack builder so a retained build
can still be reproduced from a previously bounded GeoJSONSeq input.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLCHAIN = REPO_ROOT / "search" / "overture" / "toolchain.json"


def fail(message: str) -> None:
    raise SystemExit(message)


def load_object(path: Path, label: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"Could not read {label} {path}: {exc}")
    if not isinstance(value, dict):
        fail(f"{label} must be a JSON object")
    return value


def latest_release() -> str:
    request = urllib.request.Request(
        "https://stac.overturemaps.org/catalog.json",
        headers={"User-Agent": "RoadPilot-Graph-Studio/search-builder"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            value = json.load(response)
    except Exception as exc:
        fail(f"Could not resolve current Overture release: {exc}")
    release = str(value.get("latest") or "").strip().strip("/")
    if not release:
        fail("Overture STAC catalog did not expose latest release")
    return release


def source_key(region_id: str, release: str, coverage: dict) -> str:
    payload = json.dumps(coverage, sort_keys=True, separators=(",", ":")).encode("utf-8")
    suffix = hashlib.sha256(payload).hexdigest()[:12]
    return f"{region_id}-{release}-{suffix}"


def run_download(executable: Path, bbox: str, output: Path, no_stac: bool) -> bool:
    command = [
        str(executable),
        "download",
        f"--bbox={bbox}",
        "--type=place",
        "-f",
        "geojsonseq",
        "-o",
        str(output),
    ]
    if no_stac:
        command.insert(2, "--no-stac")
    print("+", " ".join(command), flush=True)
    result = subprocess.run(command, check=False)
    return result.returncode == 0 and output.is_file() and output.stat().st_size > 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--package-version", required=True)
    parser.add_argument("--work-dir", default=".search-source-work", type=Path)
    parser.add_argument("--dist-dir", default="dist/search", type=Path)
    parser.add_argument("--refresh-source", action="store_true")
    args = parser.parse_args()

    config = load_object(args.config, "region config")
    overture = config.get("overture")
    if not isinstance(overture, dict) or overture.get("enabled") is not True:
        fail("overture.enabled must be true")

    toolchain = load_object(TOOLCHAIN, "search toolchain")
    expected_client = str(toolchain.get("overturemapsVersion") or "").strip()
    if not expected_client:
        fail("Search toolchain is missing overturemapsVersion")
    try:
        installed_client = importlib.metadata.version("overturemaps")
    except importlib.metadata.PackageNotFoundError:
        fail("The pinned overturemaps client is not installed")
    if installed_client != expected_client:
        fail(
            f"Overture client mismatch: expected {expected_client}, "
            f"installed {installed_client}"
        )

    region_id = str(config.get("id") or "").strip()
    if not region_id:
        fail("Region id is missing")
    coverage = overture.get("coverage")
    if not isinstance(coverage, dict):
        fail("overture.coverage is missing")
    try:
        min_lat = float(coverage["minLat"])
        max_lat = float(coverage["maxLat"])
        min_lng = float(coverage["minLng"])
        max_lng = float(coverage["maxLng"])
    except (KeyError, TypeError, ValueError):
        fail("overture.coverage is invalid")
    bbox = f"{min_lng},{min_lat},{max_lng},{max_lat}"

    release = latest_release()
    cache_dir = args.work_dir / "source-cache" / region_id
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = source_key(region_id, release, coverage)
    source_path = cache_dir / f"{key}.geojsonseq"

    if args.refresh_source or not source_path.is_file() or source_path.stat().st_size <= 0:
        partial = source_path.with_suffix(".geojsonseq.downloading")
        partial.unlink(missing_ok=True)
        executable = Path(sys.executable).with_name("overturemaps")
        if not executable.is_file():
            found = shutil.which("overturemaps")
            if not found:
                fail("Could not locate the overturemaps CLI in the Graph Studio environment")
            executable = Path(found)

        print(f"search source: downloading Overture {release} for {region_id}", flush=True)
        success = run_download(executable, bbox, partial, no_stac=False)
        if not success:
            print("search source: STAC query returned no usable data; retrying without STAC", flush=True)
            partial.unlink(missing_ok=True)
            success = run_download(executable, bbox, partial, no_stac=True)
        if not success:
            partial.unlink(missing_ok=True)
            fail("Overture Places download failed")
        partial.replace(source_path)
    else:
        print(f"search source: reusing cached Overture {release} for {region_id}", flush=True)

    print(
        f"search source: release={release} bytes={source_path.stat().st_size} "
        f"path={source_path}",
        flush=True,
    )
    builder = REPO_ROOT / "tools" / "build_search_region_pack.py"
    command = [
        sys.executable,
        str(builder),
        "--config",
        str(args.config),
        "--input",
        str(source_path),
        "--source-release",
        release,
        "--pack-version",
        args.package_version,
        "--dist-dir",
        str(args.dist_dir),
        "--work-dir",
        str(args.work_dir / "build"),
    ]
    print("+", " ".join(command), flush=True)
    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        fail(f"Retained search-pack build failed with exit code {result.returncode}")

    final_dir = args.dist_dir / region_id / args.package_version
    print(f"retained search build: {final_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
