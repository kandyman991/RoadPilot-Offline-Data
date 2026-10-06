#!/usr/bin/env python3
import argparse
import hashlib
import json
import re
import tarfile
from pathlib import Path

SHA256 = re.compile(r"^[0-9a-f]{64}$")


def fail(message: str) -> None:
    raise SystemExit(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--package")
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if manifest.get("schema") != "roadpilot-routing-pack":
        fail("unexpected routing manifest schema")
    if manifest.get("schemaVersion") != 1:
        fail("routing manifest schemaVersion must be 1")

    artifact = manifest.get("artifact")
    if not isinstance(artifact, dict):
        fail("artifact is required")

    expected_name = str(artifact.get("fileName") or "")
    expected_size = int(artifact.get("sizeBytes") or 0)
    expected_sha = str(artifact.get("sha256") or "").lower()
    expected_tiles = int(artifact.get("tileCount") or 0)
    fingerprint = str(manifest.get("graphFingerprint") or "")

    if not expected_name.endswith(".tar"):
        fail("routing artifact must be a .tar tile extract")
    if expected_size <= 0 or expected_tiles <= 0 or not SHA256.fullmatch(expected_sha):
        fail("routing artifact integrity metadata is incomplete")
    if fingerprint != f"sha256:{expected_sha}":
        fail("graphFingerprint must match the routing artifact SHA-256")

    package_path = Path(args.package) if args.package else manifest_path.parent / expected_name
    if package_path.name != expected_name:
        fail("package file name does not match manifest")
    if not package_path.is_file():
        fail(f"routing package is missing: {package_path}")
    if package_path.stat().st_size != expected_size:
        fail("routing package size mismatch")
    if sha256(package_path) != expected_sha:
        fail("routing package SHA-256 mismatch")

    with tarfile.open(package_path, "r") as archive:
        names = archive.getnames()
    actual_tiles = sum(1 for name in names if name.endswith(".gph"))
    if "index.bin" not in names:
        fail("routing package is missing index.bin")
    if actual_tiles != expected_tiles:
        fail(f"routing tile count mismatch: {actual_tiles} != {expected_tiles}")

    source = manifest.get("source")
    if not isinstance(source, dict) or float(source.get("borderBufferKm") or 0) <= 0:
        fail("source.borderBufferKm must be positive")
    pbfs = source.get("pbfs")
    if not isinstance(pbfs, list) or not pbfs:
        fail("source.pbfs must be non-empty")
    for item in pbfs:
        if not isinstance(item, dict):
            fail("invalid source PBF record")
        if int(item.get("sizeBytes") or 0) <= 0:
            fail("source PBF size is invalid")
        if not SHA256.fullmatch(str(item.get("sha256") or "")):
            fail("source PBF SHA-256 is invalid")

    validation = manifest.get("validation")
    routes = validation.get("routes") if isinstance(validation, dict) else None
    if not isinstance(routes, list) or not routes:
        fail("validation.routes must be non-empty")
    if not any(route.get("kind") == "border" and route.get("passed") is True for route in routes):
        fail("at least one border route must pass before publication")
    if any(route.get("passed") is not True for route in routes):
        fail("all recorded validation routes must pass")

    print(
        f"{manifest_path}: valid routing pack {manifest['regionId']} "
        f"version={manifest['packageVersion']} tiles={actual_tiles} bytes={expected_size}"
    )


if __name__ == "__main__":
    main()
