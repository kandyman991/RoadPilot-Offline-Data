#!/usr/bin/env python3
"""Plan refresh work for one graph-bound RoadPilot regional connector inventory/matrix."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

SCHEMA = "roadpilot.region-connector-refresh-plan"
VERSION = 1
GENERATOR_NAME = "roadpilot-region-connector-refresh-planner"
GENERATOR_VERSION = "1"


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
    return "sha256:" + digest.hexdigest()


def manifest_identity(value: dict[str, Any], label: str) -> dict[str, Any]:
    if value.get("schema") != "roadpilot-routing-pack" or value.get("schemaVersion") != 1:
        fail(f"{label}: unsupported routing manifest")
    region = str(value.get("regionId") or "")
    graph = str(value.get("graphFingerprint") or "")
    source = value.get("source")
    index = value.get("graphIndex")
    if not region or not graph or not isinstance(source, dict) or not isinstance(index, dict):
        fail(f"{label}: region/graph/source/index required")
    primary = str(source.get("primaryGeofabrikId") or "")
    boundaries = index.get("boundaryFingerprints")
    if not primary or not isinstance(boundaries, dict):
        fail(f"{label}: primaryGeofabrikId/boundaryFingerprints required")
    return {
        "regionId": region,
        "graphFingerprint": graph,
        "primaryGeofabrikId": primary,
        "boundaryFingerprints": {
            str(key): str(value)
            for key, value in boundaries.items()
            if isinstance(key, str) and isinstance(value, str)
        },
    }


def inventory_identity(value: dict[str, Any], label: str) -> dict[str, Any]:
    if value.get("schema") != "roadpilot.region-connector-inventory" or value.get("version") != 1:
        fail(f"{label}: unsupported connector inventory")
    region = str(value.get("regionId") or "")
    graph = value.get("graph")
    sources = value.get("sourceConnectivity")
    anchors = value.get("anchors")
    if not region or not isinstance(graph, dict) or not isinstance(sources, list) or not isinstance(anchors, list):
        fail(f"{label}: region/graph/sourceConnectivity/anchors required")
    if graph.get("regionId") != region:
        fail(f"{label}: graph.regionId mismatch")
    return {
        "regionId": region,
        "graph": graph,
        "sources": sources,
        "anchorCount": len(anchors),
    }


def matrix_identity(value: dict[str, Any], label: str) -> dict[str, Any]:
    if value.get("schema") != "roadpilot.region-connector-matrix" or value.get("version") != 1:
        fail(f"{label}: unsupported connector matrix")
    region = str(value.get("regionId") or "")
    graph = value.get("graph")
    source_hash = str(value.get("sourceInventorySha256") or "")
    source_anchor_count = value.get("sourceAnchorCount")
    if not region or not isinstance(graph, dict) or not source_hash:
        fail(f"{label}: region/graph/sourceInventorySha256 required")
    if graph.get("regionId") != region:
        fail(f"{label}: graph.regionId mismatch")
    if isinstance(source_anchor_count, bool) or not isinstance(source_anchor_count, int) or source_anchor_count < 0:
        fail(f"{label}: sourceAnchorCount invalid")
    return {
        "regionId": region,
        "graph": graph,
        "sourceInventorySha256": source_hash,
        "sourceAnchorCount": source_anchor_count,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--inventory", type=Path)
    parser.add_argument("--matrix", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    if not args.manifest.is_file():
        fail(f"Manifest does not exist: {args.manifest}")
    current = manifest_identity(load(args.manifest, "routing manifest"), str(args.manifest))

    inventory = None
    inventory_hash = None
    inventory_current = False
    inventory_reasons: list[str] = []
    boundary_checks: list[dict[str, Any]] = []

    if args.inventory is None or not args.inventory.is_file():
        inventory_reasons.append("INVENTORY_MISSING")
    else:
        inventory = inventory_identity(load(args.inventory, "connector inventory"), str(args.inventory))
        inventory_hash = sha256_file(args.inventory)
        if inventory["regionId"] != current["regionId"]:
            fail("Inventory region does not match routing manifest")

        bound_graph = str(inventory["graph"].get("graphFingerprint") or "")
        if bound_graph != current["graphFingerprint"]:
            inventory_reasons.append("INVENTORY_GRAPH_CHANGED")

        for index, source in enumerate(inventory["sources"]):
            if not isinstance(source, dict):
                fail(f"sourceConnectivity[{index}] must be an object")
            neighbor_primary = str(source.get("neighborPrimaryGeofabrikId") or "")
            bound_boundary = str(source.get("regionBoundaryFingerprint") or "")
            if not neighbor_primary or not bound_boundary:
                fail(f"sourceConnectivity[{index}] missing neighbor/boundary identity")
            current_boundary = current["boundaryFingerprints"].get(neighbor_primary)
            matches = current_boundary == bound_boundary
            boundary_checks.append({
                "neighborPrimaryGeofabrikId": neighbor_primary,
                "boundBoundaryFingerprint": bound_boundary,
                "currentBoundaryFingerprint": current_boundary,
                "matches": matches,
            })
            if current_boundary is None:
                inventory_reasons.append(f"BOUNDARY_MISSING:{neighbor_primary}")
            elif not matches:
                inventory_reasons.append(f"BOUNDARY_CHANGED:{neighbor_primary}")

        inventory_current = not inventory_reasons

    matrix = None
    matrix_reasons: list[str] = []
    matrix_current = False
    if args.matrix is None or not args.matrix.is_file():
        matrix_reasons.append("MATRIX_MISSING")
    else:
        matrix = matrix_identity(load(args.matrix, "connector matrix"), str(args.matrix))
        if matrix["regionId"] != current["regionId"]:
            fail("Matrix region does not match routing manifest")
        if str(matrix["graph"].get("graphFingerprint") or "") != current["graphFingerprint"]:
            matrix_reasons.append("MATRIX_GRAPH_CHANGED")
        if inventory_hash is None:
            matrix_reasons.append("MATRIX_SOURCE_INVENTORY_UNAVAILABLE")
        elif matrix["sourceInventorySha256"] != inventory_hash:
            matrix_reasons.append("MATRIX_SOURCE_INVENTORY_CHANGED")
        if inventory is not None and matrix["sourceAnchorCount"] != inventory["anchorCount"]:
            matrix_reasons.append("MATRIX_SOURCE_ANCHOR_COUNT_CHANGED")
        matrix_current = inventory_current and not matrix_reasons

    if not inventory_current:
        status = "MISSING" if inventory is None else "STALE"
        refresh_action = "BUILD_INVENTORY_AND_MATRIX" if inventory is None else "REBUILD_INVENTORY_AND_MATRIX"
    elif matrix is None:
        status = "MISSING"
        refresh_action = "BUILD_MATRIX"
    elif not matrix_current:
        status = "STALE"
        refresh_action = "REBUILD_MATRIX"
    else:
        status = "CURRENT"
        refresh_action = "NONE"

    output = {
        "schema": SCHEMA,
        "version": VERSION,
        "regionId": current["regionId"],
        "status": status,
        "refreshAction": refresh_action,
        "currentGraphFingerprint": current["graphFingerprint"],
        "inventory": {
            "present": inventory is not None,
            "current": inventory_current,
            "sha256": inventory_hash,
            "anchorCount": inventory["anchorCount"] if inventory is not None else None,
            "reasons": inventory_reasons,
            "boundaryChecks": boundary_checks,
        },
        "matrix": {
            "present": matrix is not None,
            "current": matrix_current,
            "sourceInventorySha256": matrix["sourceInventorySha256"] if matrix is not None else None,
            "sourceAnchorCount": matrix["sourceAnchorCount"] if matrix is not None else None,
            "reasons": matrix_reasons,
        },
        "generator": {"name": GENERATOR_NAME, "version": GENERATOR_VERSION},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(f"{current['regionId']}: {status} action={refresh_action}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
