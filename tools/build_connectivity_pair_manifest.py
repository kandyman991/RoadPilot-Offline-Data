#!/usr/bin/env python3
"""Create a fingerprint-bound RoadPilot cross-region connectivity pair manifest.

This first stage does not discover or prove handoff candidates. It establishes the exact
region-pair compatibility identity that later discovery/proof stages must bind to.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SCHEMA = "roadpilot.cross-region-connectivity"
VERSION = 1
GENERATOR_NAME = "roadpilot-connectivity-pair-manifest"
GENERATOR_VERSION = "1"


def fail(message: str) -> None:
    raise SystemExit(message)


def load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"Could not read {path}: {exc}")
    if not isinstance(value, dict):
        fail(f"{path}: expected a JSON object")
    return value


def require_string(value: Any, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        fail(f"{label} is required")
    return text


def graph_index_path(manifest_path: Path, manifest: dict[str, Any]) -> Path:
    graph_index = manifest.get("graphIndex")
    if not isinstance(graph_index, dict):
        fail(f"{manifest_path}: graphIndex is required")
    name = require_string(graph_index.get("fileName"), f"{manifest_path}: graphIndex.fileName")
    path = (manifest_path.parent / name).resolve()
    root = manifest_path.parent.resolve()
    if root not in path.parents:
        fail(f"{manifest_path}: graph index escapes its build directory")
    if not path.is_file():
        fail(f"{manifest_path}: graph index does not exist: {path}")
    return path


def boundary_fingerprints(index: dict[str, Any], label: str) -> dict[str, str]:
    if index.get("schema") != "roadpilot-graph-index" or index.get("schemaVersion") != 1:
        fail(f"{label}: unsupported graph index schema/version")
    result: dict[str, str] = {}
    boundaries = index.get("boundaries")
    if not isinstance(boundaries, list):
        fail(f"{label}: boundaries must be an array")
    for item in boundaries:
        if not isinstance(item, dict):
            fail(f"{label}: invalid boundary entry")
        source_id = require_string(item.get("sourceId"), f"{label}: boundary sourceId")
        fingerprint = require_string(item.get("fingerprint"), f"{label}: {source_id} fingerprint")
        result[source_id] = fingerprint
    return result


def build_pair(
    from_manifest_path: Path,
    to_manifest_path: Path,
) -> dict[str, Any]:
    from_manifest = load_object(from_manifest_path)
    to_manifest = load_object(to_manifest_path)

    from_region = require_string(from_manifest.get("regionId"), "from regionId")
    to_region = require_string(to_manifest.get("regionId"), "to regionId")
    if from_region == to_region:
        fail("from/to regionId must be different")

    from_source = from_manifest.get("source")
    to_source = to_manifest.get("source")
    if not isinstance(from_source, dict):
        fail("from source must be an object")
    if not isinstance(to_source, dict):
        fail("to source must be an object")

    from_primary = require_string(
        from_source.get("primaryGeofabrikId"),
        "from source.primaryGeofabrikId",
    )
    to_primary = require_string(
        to_source.get("primaryGeofabrikId"),
        "to source.primaryGeofabrikId",
    )

    from_index = load_object(graph_index_path(from_manifest_path, from_manifest))
    to_index = load_object(graph_index_path(to_manifest_path, to_manifest))
    from_boundaries = boundary_fingerprints(from_index, "from graph index")
    to_boundaries = boundary_fingerprints(to_index, "to graph index")

    from_boundary = from_boundaries.get(to_primary)
    to_boundary = to_boundaries.get(from_primary)
    if not from_boundary:
        fail(
            f"{from_region}: no boundary fingerprint exists for neighboring source {to_primary}"
        )
    if not to_boundary:
        fail(
            f"{to_region}: no boundary fingerprint exists for neighboring source {from_primary}"
        )

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "pairId": f"{from_region}__{to_region}",
        "fromRegionId": from_region,
        "toRegionId": to_region,
        "fromPackageVersion": require_string(
            from_manifest.get("packageVersion"), "from packageVersion"
        ),
        "toPackageVersion": require_string(
            to_manifest.get("packageVersion"), "to packageVersion"
        ),
        "fromGraphFingerprint": require_string(
            from_manifest.get("graphFingerprint"), "from graphFingerprint"
        ),
        "toGraphFingerprint": require_string(
            to_manifest.get("graphFingerprint"), "to graphFingerprint"
        ),
        "fromBoundarySourceId": to_primary,
        "toBoundarySourceId": from_primary,
        "fromBoundaryFingerprint": from_boundary,
        "toBoundaryFingerprint": to_boundary,
        "bindingState": "STABLE_PHYSICAL",
        "validationState": "UNPROVEN",
        "generator": {
            "name": GENERATOR_NAME,
            "version": GENERATOR_VERSION,
        },
        "candidates": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-manifest", required=True, type=Path)
    parser.add_argument("--to-manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    artifact = build_pair(args.from_manifest, args.to_manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(
        f"{artifact['pairId']}: "
        f"{artifact['fromBoundarySourceId']}={artifact['fromBoundaryFingerprint']} "
        f"{artifact['toBoundarySourceId']}={artifact['toBoundaryFingerprint']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
