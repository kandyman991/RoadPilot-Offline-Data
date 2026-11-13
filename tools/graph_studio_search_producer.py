#!/usr/bin/env python3
"""Graph Studio's independent, immutable Search build/import entry point.

Uses canonical RoadPilot Overture SQLite pack builder and validators. No
routing/visual build or R2 publisher action occurs in this program.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLCHAIN = ROOT / "search/overture/toolchain.json"
STAC_URL = "https://stac.overturemaps.org/catalog.json"
VERSION_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}\Z")


def require(predicate: bool, message: str) -> None:
    if not predicate:
        raise ValueError(message)


def safe(value: str, label: str) -> str:
    require(bool(VERSION_RE.fullmatch(value)) and value not in {".", ".."}
            and ".." not in value, f"Unsafe {label}: {value!r}")
    return value


def load_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(data, dict), f"Expected JSON object: {path}")
    return data


def check_config(path: Path) -> tuple[dict, dict]:
    require(path.is_file(), f"Configured region file missing: {path}")
    config = load_json(path)
    overture = config.get("overture")
    require(isinstance(overture, dict) and overture.get("enabled") is True,
            "Search is disabled or not configured for this region")
    require(isinstance(overture.get("validation"), list) and overture["validation"],
            "Search needs one owner-selected deterministic validation target")
    require(isinstance(overture.get("country"), str)
            and re.fullmatch("[A-Z]{2}", overture["country"]) is not None,
            "Search country must be an actual ISO alpha-2 code")
    safe(str(config["id"]), "region id")
    subprocess.run([sys.executable, str(ROOT/"tools/validate_region_config.py"),
                    "--config", str(path)], check=True)
    return config, overture


def require_pinned_client() -> str:
    expected = str(load_json(TOOLCHAIN)["overturemapsVersion"])
    try:
        actual = importlib.metadata.version("overturemaps")
    except importlib.metadata.PackageNotFoundError as exc:
        raise ValueError("Pinned Overture client is missing; install Graph Studio requirements-search.txt") from exc
    require(actual == expected, f"Overture client {actual} does not match pinned {expected}")
    return expected


def latest_release() -> str:
    request = urllib.request.Request(STAC_URL, headers={
        "User-Agent": "RoadPilot-GraphStudio/local-overture-source-v1"})
    with urllib.request.urlopen(request, timeout=30) as response:
        require(response.url.startswith("https://stac.overturemaps.org/"),
                "Unexpected Overture STAC redirect")
        require(response.status == 200, "Overture STAC did not return HTTP 200")
        body = response.read(1024 * 1024 + 1)
    require(len(body) <= 1024 * 1024, "Overture STAC response was oversized")
    latest = str(json.loads(body).get("latest") or "").strip().strip("/")
    require(bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9./_-]{0,160}", latest)) and
            ".." not in latest, "Overture STAC latest release missing/unsafe")
    return latest


def download(config: dict, overture: dict, input_path: Path) -> str:
    require_pinned_client()
    bounds = overture["coverage"]
    bbox = ",".join(str(bounds[k]) for k in
                    ("minLng", "minLat", "maxLng", "maxLat"))
    release = latest_release()
    input_path.parent.mkdir(parents=True, exist_ok=True)
    require(not input_path.exists(), "Refusing to overwrite retained source input")
    # Exactly the hosted production source acquisition tool and pinned version.
    # No command shell, and never silently succeed with a partial file.
    cmd_path = Path(sys.executable).parent / "overturemaps"
    require(cmd_path.is_file(), "Pinned Overture download CLI is unavailable")
    for attempt, use_stac in enumerate((True, False), start=1):
        args = [str(cmd_path), "download", "--release", release,
                f"--bbox={bbox}", "--type=place", "-f", "geojsonseq",
                "-o", str(input_path)]
        if not use_stac:
            args.insert(2, "--no-stac")
        print(f"Overture Places fetch: {config['id']} source={release} "
              f"bbox={bbox} attempt={attempt}", flush=True)
        output = subprocess.run(args, check=False)
        if output.returncode == 0 and input_path.is_file() and input_path.stat().st_size:
            return release
        input_path.unlink(missing_ok=True)
    raise ValueError("Overture Places returned no complete regional GeoJSONSeq source")


def build(config_path: Path, dist: Path, work: Path, version: str,
          source_input: Path | None = None, source_release: str = "") -> Path:
    config, overture = check_config(config_path)
    region_id = safe(str(config["id"]), "region")
    version = safe(version, "pack version")
    target = dist / region_id / version
    require(not target.exists(), "Immutable search pack version already exists; choose another version")
    # Validate destination is a caller-controlled writable workspace.
    dist.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    if source_input is None:
        with tempfile.TemporaryDirectory(prefix="source-", dir=work) as folder:
            data_path = Path(folder) / "overture-places.geojsonseq"
            release = download(config, overture, data_path)
            return build_from_source(config_path, dist, work, version, data_path, release)
    require(source_input.is_file() and source_input.stat().st_size > 0,
            "Source GeoJSONSeq missing or empty")
    require(bool(source_release.strip()), "Explicit source release required for imported Places input")
    return build_from_source(config_path, dist, work, version, source_input,
                             source_release.strip())


def build_from_source(config_path: Path, dist: Path, work: Path, version: str,
                      source_input: Path, release: str) -> Path:
    config, _ = check_config(config_path)
    target = dist / config["id"] / version
    require(not target.exists(), "Immutable retained Search build already exists")
    args = [sys.executable, str(ROOT/"tools/build_search_region_pack.py"),
            "--config", str(config_path),
            "--input", str(source_input), "--source-release", release,
            "--pack-version", version, "--dist-dir", str(dist),
            "--work-dir", str(work)]
    print(f"Building independent retained Search pack: {config['id']} {version}", flush=True)
    subprocess.run(args, check=True)
    require(target.is_dir(), "Canonical Search builder returned without retained pack")
    return target


def import_pack(config_path: Path, manifest: Path, dist: Path) -> Path:
    config, overture = check_config(config_path)
    require(manifest.is_file() and not manifest.is_symlink(),
            "Search manifest must be a regular local file")
    manifest = manifest.resolve(strict=True)
    data = load_json(manifest)
    require(data.get("schema") == "roadpilot-search-pack",
            "Not a RoadPilot Search pack manifest")
    region = safe(str(data.get("regionId") or ""), "manifest region")
    version = safe(str(data.get("packVersion") or ""), "manifest version")
    require(region == config["id"], "Imported Search pack belongs to another region")
    filename = safe(str(data.get("fileName") or ""), "database file")
    require(filename == overture["fileName"],
            "Imported Search database filename disagrees with region config")
    # Ensure source manifest and each attached object are ordinary local files;
    # untrusted links must not redirect copies to private filesystem contents.
    require(not manifest.is_symlink() and manifest.is_file(),
            "Search manifest must be a regular local file")
    source_dir = manifest.parent
    database = source_dir / filename
    checksum = source_dir / (filename + ".sha256")
    require(database.is_file() and not database.is_symlink(),
            "Search database is missing or a symlink")
    require(checksum.is_file() and not checksum.is_symlink(),
            "Search database checksum file missing or a symlink")
    source_validation = source_dir / "search-validation.json"
    require(source_validation.is_file() and not source_validation.is_symlink(),
            "Original Search validation evidence missing or a symlink")
    validate = [sys.executable, str(ROOT/"tools/validate_search_pack.py"),
                "--manifest", str(manifest), "--database", str(database),
                "--config", str(config_path)]
    subprocess.run(validate, check=True)
    dest = dist / region / version
    require(not dest.exists(), "Import would overwrite immutable retained Search build")
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Stage in same parent for atomic promotion after independent revalidation.
    with tempfile.TemporaryDirectory(prefix=".search-import-", dir=dest.parent) as stage_dir:
        stage = Path(stage_dir)
        for src in (manifest, database, checksum, source_validation):
            shutil.copyfile(src, stage/src.name)
        subprocess.run([sys.executable, str(ROOT/"tools/validate_search_pack.py"),
                        "--manifest", str(stage/manifest.name),
                        "--database", str(stage/filename), "--config", str(config_path)],
                       check=True)
        # The complete retained validation report is replayed from the imported
        # original source instead of trusting filename or manifest flag alone.
        subprocess.run([sys.executable, str(ROOT/"tools/validate_overture_pack.py"),
                        "--database", str(stage/filename), "--config", str(config_path)],
                       check=True)
        stage.rename(dest)
    return dest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="operation", required=True)
    for operation in ("build", "import"):
        p = sub.add_parser(operation)
        p.add_argument("--config", required=True, type=Path)
        p.add_argument("--dist-dir", required=True, type=Path)
        if operation == "build":
            p.add_argument("--pack-version", required=True)
            p.add_argument("--work-dir", required=True, type=Path)
            p.add_argument("--input", type=Path)
            p.add_argument("--source-release", default="")
        else:
            p.add_argument("--manifest", required=True, type=Path)
    args = ap.parse_args()
    if args.operation == "build":
        target = build(args.config, args.dist_dir, args.work_dir,
                       args.pack_version, args.input, args.source_release)
    else:
        target = import_pack(args.config, args.manifest, args.dist_dir)
    print("SEARCH_RESULT "+json.dumps({"operation": args.operation,
          "region": target.parent.name, "version": target.name,
          "manifestDir": str(target)}), flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(f"SEARCH_ERROR {exc}", file=sys.stderr, flush=True)
        raise SystemExit(1)
