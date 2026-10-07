#!/usr/bin/env python3
"""Decide the cheapest refresh action for one retained RoadPilot visual build."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
PROFILE_DIR = REPO_ROOT / "visual" / "tilemaker"


def fail(message: str) -> None:
    raise SystemExit(message)


def load(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"Could not read {label} {path}: {exc}")
    if not isinstance(value, dict):
        fail(f"{label} must be a JSON object")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def current_profile_fingerprint() -> str:
    digest = hashlib.sha256()
    for path in (
        PROFILE_DIR / "config.json",
        PROFILE_DIR / "process.lua",
        PROFILE_DIR / "toolchain.json",
    ):
        if not path.is_file():
            fail(f"Visual profile file is missing: {path}")
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def current_source_fingerprint(config: dict[str, Any], pbf: Path) -> str:
    visual = config.get("visual")
    source = visual.get("source") if isinstance(visual, dict) else None
    if not isinstance(source, dict):
        fail("visual.source is required")
    if not pbf.is_file() or pbf.stat().st_size <= 0:
        fail(f"Current visual PBF is missing or empty: {pbf}")
    payload = {
        "primaryGeofabrikId": str(source.get("primaryGeofabrikId") or ""),
        "url": str(source.get("url") or ""),
        "sizeBytes": pbf.stat().st_size,
        "sha256": sha256_file(pbf),
    }
    if not payload["primaryGeofabrikId"] or not payload["url"].startswith("https://"):
        fail("Current visual source identity is invalid")
    return "sha256:" + hashlib.sha256(canonical_bytes(payload)).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--pbf", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    manifest = load(args.manifest, "visual manifest")
    config = load(args.config, "region config")
    if manifest.get("schema") != "roadpilot-visual-pack" or manifest.get("schemaVersion") != 1:
        fail("Unsupported visual manifest")
    region_id = str(manifest.get("regionId") or "")
    if region_id != str(config.get("id") or ""):
        fail("Visual manifest regionId does not match region config")

    visual = config.get("visual")
    validation = visual.get("validation") if isinstance(visual, dict) else None
    if not isinstance(validation, dict):
        fail("visual.validation is required")

    bound_source = str(manifest.get("sourceFingerprint") or "")
    current_source = current_source_fingerprint(config, args.pbf)
    source_matches = bound_source == current_source

    bound_profile = str(manifest.get("profileFingerprint") or "")
    current_profile = current_profile_fingerprint()
    profile_matches = bound_profile == current_profile

    desired_classes = sorted(str(item) for item in validation.get("majorRoadClasses") or [])
    desired_tolerance = float(validation.get("borderToleranceMeters"))

    descriptor = manifest.get("roadIndex")
    road_present = isinstance(descriptor, dict)
    road_criteria_match = False
    if road_present:
        road_path = args.manifest.parent / str(descriptor.get("fileName") or "")
        if road_path.is_file():
            road = load(road_path, "visual road index")
            road_criteria_match = (
                sorted(str(item) for item in road.get("majorRoadClasses") or []) == desired_classes
                and float(road.get("borderToleranceMeters", -1)) == desired_tolerance
                and road.get("sourceFingerprint") == bound_source
                and road.get("visualFingerprint") == manifest.get("visualFingerprint")
                and road.get("missingRoadCount") == 0
            )

    reasons: list[str] = []
    if not source_matches:
        reasons.append("SOURCE_CHANGED")
        action = "REBUILD_SOURCE"
    elif not profile_matches:
        reasons.append("PROFILE_CHANGED")
        action = "REBUILD_PROFILE"
    elif not road_present:
        reasons.append("ROAD_INDEX_MISSING")
        action = "REVALIDATE_ROADS"
    elif not road_criteria_match:
        reasons.append("ROAD_VALIDATION_CHANGED")
        action = "REVALIDATE_ROADS"
    else:
        action = "NONE"

    output = {
        "schema": "roadpilot.visual-refresh-plan",
        "version": 1,
        "regionId": region_id,
        "packageVersion": str(manifest.get("packageVersion") or ""),
        "status": "CURRENT" if action == "NONE" else "STALE",
        "action": action,
        "reasons": reasons,
        "source": {
            "boundFingerprint": bound_source,
            "currentFingerprint": current_source,
            "matches": source_matches,
        },
        "profile": {
            "boundFingerprint": bound_profile,
            "currentFingerprint": current_profile,
            "matches": profile_matches,
        },
        "roadValidation": {
            "present": road_present,
            "criteriaMatch": road_criteria_match,
            "majorRoadClasses": desired_classes,
            "borderToleranceMeters": desired_tolerance,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(f"visual refresh: {output['status']} action={action}")
    if reasons:
        print("reasons:", ", ".join(reasons))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
