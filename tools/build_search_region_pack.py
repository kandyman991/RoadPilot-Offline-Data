#!/usr/bin/env python3
"""Build and retain one complete RoadPilot regional Overture search pack."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLCHAIN = REPO_ROOT / "search" / "overture" / "toolchain.json"


def fail(message: str) -> None:
    raise SystemExit(message)


def run(command: list[str], label: str) -> None:
    print("+", " ".join(command), flush=True)
    result = subprocess.run(command, text=True, check=False)
    if result.returncode != 0:
        fail(f"{label} failed with exit code {result.returncode}")


def load(path: Path, label: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"Could not read {label} {path}: {exc}")
    if not isinstance(value, dict):
        fail(f"{label} must be a JSON object")
    return value


def safe_component(value: str, label: str) -> str:
    value = value.strip()
    if not value or value in {".", ".."} or "/" in value or "\\" in value or ".." in value:
        fail(f"Unsafe {label}: {value!r}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--input", required=True, type=Path, help="Bounded Overture place GeoJSONSeq")
    parser.add_argument("--source-release", required=True)
    parser.add_argument("--pack-version", required=True)
    parser.add_argument("--dist-dir", default="dist/search", type=Path)
    parser.add_argument("--work-dir", default=".search-work", type=Path)
    args = parser.parse_args()

    if not args.config.is_file():
        fail(f"Region config does not exist: {args.config}")
    if not args.input.is_file() or args.input.stat().st_size <= 0:
        fail(f"Overture GeoJSONSeq input is missing or empty: {args.input}")

    run(
        [sys.executable, str(REPO_ROOT / "tools/validate_region_config.py"), "--config", str(args.config)],
        "region config validation",
    )
    config = load(args.config, "region config")
    overture = config.get("overture")
    if not isinstance(overture, dict) or overture.get("enabled") is not True:
        fail("overture.enabled must be true")

    toolchain = load(TOOLCHAIN, "search toolchain")
    if toolchain.get("databaseSchema") != overture.get("databaseSchema"):
        fail("Search toolchain database schema does not match region config")
    client_version = str(toolchain.get("overturemapsVersion") or "")
    if not client_version:
        fail("Search toolchain is missing overturemapsVersion")

    region_id = safe_component(str(config.get("id") or ""), "region id")
    pack_version = safe_component(args.pack_version, "pack version")
    source_release = args.source_release.strip().rstrip("/")
    if not source_release:
        fail("source release is required")

    final_dir = args.dist_dir / region_id / pack_version
    if final_dir.exists():
        fail(
            f"Retained search build already exists and is immutable: {final_dir}. "
            "Use a new pack version."
        )

    temp_dir = args.work_dir / region_id / f"{pack_version}.building"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)

    database = temp_dir / overture["fileName"]
    manifest = temp_dir / overture["manifestFileName"]
    validation_report = temp_dir / "search-validation.json"

    run(
        [
            sys.executable,
            str(REPO_ROOT / "tools/build_overture_places_pack.py"),
            "--input", str(args.input),
            "--output", str(database),
            "--region-id", region_id,
            "--country", str(overture.get("country") or ""),
            "--source-release", source_release,
            "--source-client-version", client_version,
        ],
        "search SQLite build",
    )

    run(
        [
            sys.executable,
            str(REPO_ROOT / "tools/validate_overture_pack.py"),
            "--database", str(database),
            "--config", str(args.config),
            "--report", str(validation_report),
        ],
        "runtime search regression validation",
    )

    run(
        [
            sys.executable,
            str(REPO_ROOT / "tools/build_overture_manifest.py"),
            "--database", str(database),
            "--output", str(manifest),
            "--config", str(args.config),
            "--pack-version", pack_version,
            "--validation-report", str(validation_report),
        ],
        "search manifest build",
    )

    checksum = database.with_name(database.name + ".sha256")
    import hashlib
    digest = hashlib.sha256(database.read_bytes()).hexdigest()
    checksum.write_text(f"{digest}  {database.name}\n", encoding="utf-8")

    run(
        [
            sys.executable,
            str(REPO_ROOT / "tools/validate_search_pack.py"),
            "--manifest", str(manifest),
            "--database", str(database),
            "--config", str(args.config),
        ],
        "complete retained search pack validation",
    )

    final_dir.parent.mkdir(parents=True, exist_ok=True)
    temp_dir.replace(final_dir)
    print(f"retained search build: {final_dir}")
    print(f"database: {final_dir / database.name}")
    print(f"manifest: {final_dir / manifest.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
