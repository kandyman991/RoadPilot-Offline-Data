#!/usr/bin/env python3
"""Build one deterministic RoadPilot visual-map PMTiles pack."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from visual_pack import (
    VisualPackError,
    canonicalize_pmtiles,
    inspect_pmtiles,
    load_json_object,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
PROFILE_DIR = REPO_ROOT / "visual" / "tilemaker"
CORE_REQUIRED_LAYERS = {"transportation", "place", "water", "boundary"}


def fail(message: str) -> None:
    raise SystemExit(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def safe_component(value: str, label: str) -> str:
    value = value.strip()
    if not value or value in {".", ".."} or "/" in value or "\\" in value or ".." in value:
        fail(f"{label} is unsafe: {value!r}")
    return value


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def profile_fingerprint(config_path: Path, process_path: Path, toolchain_path: Path) -> str:
    digest = hashlib.sha256()
    for path in (config_path, process_path, toolchain_path):
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def source_descriptor(region: dict[str, Any], pbf_path: Path) -> dict[str, Any]:
    routing = region.get("routing")
    source = routing.get("source") if isinstance(routing, dict) else None
    if not isinstance(source, dict):
        fail("Region config routing.source is required for visual build source identity")
    primary = str(source.get("primaryGeofabrikId") or "")
    pbfs = source.get("pbfs")
    if not primary or not isinstance(pbfs, list):
        fail("Region config routing.source primaryGeofabrikId/pbfs are required")
    match = next(
        (
            item for item in pbfs
            if isinstance(item, dict) and str(item.get("id") or "") == primary
        ),
        None,
    )
    if match is None:
        fail(f"Primary Geofabrik source {primary!r} is not present in routing.source.pbfs")
    url = str(match.get("url") or "")
    if not url.startswith("https://"):
        fail("Primary Geofabrik source URL must use https://")
    size = pbf_path.stat().st_size
    if size <= 0:
        fail(f"OSM PBF is empty: {pbf_path}")
    digest = sha256_file(pbf_path)
    return {
        "primaryGeofabrikId": primary,
        "url": url,
        "sizeBytes": size,
        "sha256": digest,
    }


def run_checked(command: list[str], label: str) -> str:
    try:
        result = subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
    except OSError as exc:
        fail(f"Could not start {label}: {exc}")
    if result.returncode != 0:
        fail(f"{label} failed ({result.returncode}):\n{result.stdout.strip()}")
    return result.stdout


def verify_tilemaker_version(
    toolchain: dict[str, Any],
    tilemaker_bin: str | None,
) -> tuple[str, str]:
    expected = str(toolchain.get("tilemakerVersion") or "")
    if not expected:
        fail("visual/tilemaker/toolchain.json is missing tilemakerVersion")

    executable = tilemaker_bin or shutil.which("tilemaker")
    if not executable:
        commit = str(toolchain.get("sourceCommit") or "")
        fail(
            "tilemaker is not installed. Build/install the pinned RoadPilot visual "
            f"toolchain ({expected}, source commit {commit}) or pass --tilemaker-bin."
        )
    executable = shutil.which(executable) or executable
    output = run_checked([executable, "--help"], "tilemaker --help")
    if re.search(rf"\btilemaker v?{re.escape(expected)}(?:\b|\+)", output) is None:
        fail(f"tilemaker version does not match pinned {expected}: {output.strip()}")
    return expected, executable


def build_with_tilemaker(
    pbf_path: Path,
    output_path: Path,
    config_path: Path,
    process_path: Path,
    toolchain: dict[str, Any],
    tilemaker_bin: str | None,
    threads: int,
) -> str:
    expected_version, executable = verify_tilemaker_version(toolchain, tilemaker_bin)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.unlink(missing_ok=True)

    command = [
        executable,
        str(pbf_path),
        "--output",
        str(output_path),
        "--config",
        str(config_path),
        "--process",
        str(process_path),
        "--threads",
        str(threads),
    ]
    output = run_checked(command, "tilemaker visual build")
    if not output_path.is_file():
        fail(f"tilemaker succeeded but did not create {output_path}")
    print(output.strip())
    return expected_version


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--pbf", required=True, type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument(
        "--tilemaker-bin",
        help="Use this tilemaker binary. If omitted, tilemaker must be on PATH.",
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=0,
        help="tilemaker worker threads; 0 lets tilemaker auto-detect.",
    )
    parser.add_argument(
        "--required-layer",
        action="append",
        default=[],
        help="Require this layer to occur in decoded PMTiles tiles; repeatable.",
    )
    args = parser.parse_args()

    if args.threads < 0 or args.threads > 64:
        fail("--threads must be from 0 to 64")

    for path, label in ((args.config, "region config"), (args.pbf, "OSM PBF")):
        if not path.is_file():
            fail(f"{label} does not exist: {path}")

    region = load_json_object(args.config, "region config")
    region_id = safe_component(str(region.get("id") or ""), "region id")
    region_name = str(region.get("name") or "").strip()
    version = safe_component(args.version, "package version")
    if not region_name:
        fail("Region config name is required")

    config_path = PROFILE_DIR / "config.json"
    process_path = PROFILE_DIR / "process.lua"
    toolchain_path = PROFILE_DIR / "toolchain.json"
    for path in (config_path, process_path, toolchain_path):
        if not path.is_file():
            fail(f"Visual profile file is missing: {path}")
    toolchain = load_json_object(toolchain_path, "visual toolchain")

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    package_name = f"{region_id}-visual-{version}.pmtiles"
    manifest_name = f"{region_id}-visual-{version}-manifest.json"
    package_path = output_dir / package_name
    manifest_path = output_dir / manifest_name

    source = source_descriptor(region, args.pbf.resolve())
    tilemaker_version = build_with_tilemaker(
        args.pbf.resolve(),
        package_path,
        config_path,
        process_path,
        toolchain,
        args.tilemaker_bin,
        args.threads,
    )
    try:
        canonicalize_pmtiles(package_path)
    except VisualPackError as exc:
        fail(str(exc))

    required_layers = set(args.required_layer) or set(CORE_REQUIRED_LAYERS)
    try:
        inspection = inspect_pmtiles(
            package_path,
            required_layers=required_layers,
            max_tiles_to_decode=5000,
        )
    except VisualPackError as exc:
        fail(str(exc))

    artifact_sha = sha256_file(package_path)
    source_fp_payload = {
        "primaryGeofabrikId": source["primaryGeofabrikId"],
        "url": source["url"],
        "sizeBytes": source["sizeBytes"],
        "sha256": source["sha256"],
    }
    source_fingerprint = "sha256:" + sha256_bytes(canonical_bytes(source_fp_payload))
    profile_fingerprint_value = profile_fingerprint(
        config_path,
        process_path,
        toolchain_path,
    )
    layers = sorted(
        set(inspection["metadataLayers"]) | set(inspection["observedLayers"])
    )
    built_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    manifest = {
        "schema": "roadpilot-visual-pack",
        "schemaVersion": 1,
        "regionId": region_id,
        "regionName": region_name,
        "packageVersion": version,
        "builtAtUtc": built_at,
        "tilemakerVersion": tilemaker_version,
        "visualFingerprint": "sha256:" + artifact_sha,
        "profileFingerprint": profile_fingerprint_value,
        "sourceFingerprint": source_fingerprint,
        "source": source,
        "artifact": {
            "fileName": package_name,
            "format": "pmtiles",
            "tileType": "mvt",
            "sizeBytes": package_path.stat().st_size,
            "sha256": artifact_sha,
            "tileCount": inspection["tileCount"],
            "minZoom": inspection["minZoom"],
            "maxZoom": inspection["maxZoom"],
            "bounds": inspection["bounds"],
        },
        "layers": layers,
        "validation": {
            "archiveReadable": True,
            "tileTypeMvt": True,
            "requiredLayers": sorted(required_layers),
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    checksum_path = output_dir / f"{package_name}.sha256"
    checksum_path.write_text(f"{artifact_sha}  {package_name}\n", encoding="utf-8")

    print(f"visual pack: {region_id} {version}")
    print(f"tilemaker: {tilemaker_version}")
    print(f"tiles: {inspection['tileCount']} zoom={inspection['minZoom']}..{inspection['maxZoom']}")
    print(f"layers: {', '.join(layers)}")
    print(f"pmtiles: {package_path}")
    print(f"manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
