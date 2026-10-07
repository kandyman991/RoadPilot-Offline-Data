#!/usr/bin/env python3
"""Build and retain one complete RoadPilot regional visual package."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any

USER_AGENT = "RoadPilot-Offline-Data/visual-builder"
REPO_ROOT = Path(__file__).resolve().parents[1]


def fail(message: str) -> None:
    raise SystemExit(message)


def run(command: list[str], label: str) -> None:
    print("+", " ".join(command), flush=True)
    result = subprocess.run(command, text=True, check=False)
    if result.returncode != 0:
        fail(f"{label} failed with exit code {result.returncode}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_component(value: str, label: str) -> str:
    value = value.strip()
    if not value or value in {".", ".."} or "/" in value or "\\" in value or ".." in value:
        fail(f"Unsafe {label}: {value!r}")
    return value


def load(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"Could not read {label} {path}: {exc}")
    if not isinstance(value, dict):
        fail(f"{label} must be a JSON object")
    return value


def download(url: str, destination: Path, *, refresh: bool) -> Path:
    if refresh:
        destination.unlink(missing_ok=True)
    if destination.is_file() and destination.stat().st_size > 0:
        print(f"cache hit: {destination}")
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".part")
    temporary.unlink(missing_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    print(f"download: {url}")
    try:
        with urllib.request.urlopen(request) as response, temporary.open("wb") as output:
            shutil.copyfileobj(response, output, length=1024 * 1024)
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        fail(f"Could not download {url}: {exc}")
    if not temporary.is_file() or temporary.stat().st_size <= 0:
        temporary.unlink(missing_ok=True)
        fail(f"Downloaded empty source: {url}")
    temporary.replace(destination)
    return destination


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--package-version", required=True)
    parser.add_argument("--work-dir", default=".visual-work", type=Path)
    parser.add_argument("--dist-dir", default="dist/visual", type=Path)
    parser.add_argument("--tilemaker-bin")
    parser.add_argument("--refresh-sources", action="store_true")
    args = parser.parse_args()

    if not args.config.is_file():
        fail(f"Region config does not exist: {args.config}")
    run(
        [sys.executable, str(REPO_ROOT / "tools/validate_region_config.py"), "--config", str(args.config)],
        "region config validation",
    )
    config = load(args.config, "region config")
    region_id = safe_component(str(config.get("id") or ""), "region id")
    package_version = safe_component(args.package_version, "package version")
    visual = config.get("visual")
    if not isinstance(visual, dict) or visual.get("enabled") is not True:
        fail("visual.enabled must be true")
    source = visual.get("source")
    package = visual.get("package")
    validation = visual.get("validation")
    if not isinstance(source, dict) or not isinstance(package, dict) or not isinstance(validation, dict):
        fail("visual source/package/validation configuration is required")

    source_id = str(source.get("primaryGeofabrikId") or "")
    pbf_url = str(source.get("url") or "")
    polygon_url = str(source.get("polygonUrl") or "")
    if not source_id or not pbf_url.startswith("https://") or not polygon_url.startswith("https://"):
        fail("visual source identity, PBF URL and polygon URL are required")

    cache_root = args.work_dir / "cache" / "visual"
    cache_stem = source_id.replace("/", "__")
    pbf_path = download(
        pbf_url,
        cache_root / f"{cache_stem}.osm.pbf",
        refresh=args.refresh_sources,
    )
    polygon_path = download(
        polygon_url,
        cache_root / f"{cache_stem}.poly",
        refresh=args.refresh_sources,
    )
    print(f"visual source sha256: {sha256_file(pbf_path)}")

    final_dir = args.dist_dir / region_id / package_version
    if final_dir.exists():
        fail(
            f"Retained visual build already exists and is immutable: {final_dir}. "
            "Use a new package version."
        )
    temp_dir = args.work_dir / region_id / f"{package_version}.building"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)

    build_command = [
        sys.executable,
        str(REPO_ROOT / "tools/build_visual_region.py"),
        "--config",
        str(args.config),
        "--pbf",
        str(pbf_path),
        "--version",
        package_version,
        "--output-dir",
        str(temp_dir),
        "--threads",
        str(int(visual.get("buildThreads") or 1)),
    ]
    if args.tilemaker_bin:
        build_command.extend(["--tilemaker-bin", args.tilemaker_bin])
    run(build_command, "visual PMTiles build")

    package_name = str(package["fileNameTemplate"]).replace("{version}", package_version)
    manifest_name = str(package["manifestFileNameTemplate"]).replace("{version}", package_version)
    road_index_name = str(package["roadIndexFileNameTemplate"]).replace("{version}", package_version)
    package_path = temp_dir / package_name
    manifest_path = temp_dir / manifest_name
    road_index_path = temp_dir / road_index_name

    road_command = [
        sys.executable,
        str(REPO_ROOT / "tools/build_visual_road_index.py"),
        "--pbf",
        str(pbf_path),
        "--polygon",
        str(polygon_path),
        "--manifest",
        str(manifest_path),
        "--package",
        str(package_path),
        "--output",
        str(road_index_path),
        "--border-tolerance-meters",
        str(float(validation["borderToleranceMeters"])),
    ]
    for road_class in validation["majorRoadClasses"]:
        road_command.extend(["--major-road-class", str(road_class)])
    run(road_command, "visual road coverage validation")

    manifest = load(manifest_path, "visual manifest")
    road_index = load(road_index_path, "visual road index")
    manifest["roadIndex"] = {
        "fileName": road_index_name,
        "sha256": sha256_file(road_index_path),
        "sourceRoadCount": int(road_index["sourceRoadCount"]),
        "majorRoadCount": int(road_index["majorRoadCount"]),
        "borderRoadCount": int(road_index["borderRoadCount"]),
        "missingRoadCount": int(road_index["missingRoadCount"]),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    run(
        [
            sys.executable,
            str(REPO_ROOT / "tools/validate_visual_pack.py"),
            "--manifest",
            str(manifest_path),
            "--package",
            str(package_path),
            "--expect-current-profile",
        ],
        "complete visual package validation",
    )

    final_dir.parent.mkdir(parents=True, exist_ok=True)
    temp_dir.replace(final_dir)
    print(f"retained visual build: {final_dir}")
    print(f"manifest: {final_dir / manifest_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
