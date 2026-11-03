#!/usr/bin/env python3
"""Validate RoadPilot regional connector refresh plans."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
STATUSES = {"CURRENT", "STALE", "MISSING"}
ACTIONS = {
    "NONE",
    "BUILD_INVENTORY_AND_MATRIX",
    "REBUILD_INVENTORY_AND_MATRIX",
    "BUILD_MATRIX",
    "REBUILD_MATRIX",
}


def fail(message: str) -> None:
    raise SystemExit(message)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", required=True, type=Path)
    args = parser.parse_args()

    data = json.loads(args.artifact.read_text(encoding="utf-8"))
    require(isinstance(data, dict), "artifact must be an object")
    require(data.get("schema") == "roadpilot.region-connector-refresh-plan", "unexpected schema")
    require(data.get("version") == 1, "version must be 1")
    region = data.get("regionId")
    require(isinstance(region, str) and region, "regionId required")
    require(data.get("status") in STATUSES, "status invalid")
    require(data.get("refreshAction") in ACTIONS, "refreshAction invalid")
    graph = data.get("currentGraphFingerprint")
    require(isinstance(graph, str) and bool(SHA256.fullmatch(graph)), "currentGraphFingerprint invalid")

    inventory = data.get("inventory")
    require(isinstance(inventory, dict), "inventory required")
    require(isinstance(inventory.get("present"), bool), "inventory.present invalid")
    require(isinstance(inventory.get("current"), bool), "inventory.current invalid")
    inv_sha = inventory.get("sha256")
    require(inv_sha is None or (isinstance(inv_sha, str) and SHA256.fullmatch(inv_sha)), "inventory.sha256 invalid")
    anchor_count = inventory.get("anchorCount")
    require(
        anchor_count is None
        or (isinstance(anchor_count, int) and not isinstance(anchor_count, bool) and anchor_count >= 0),
        "inventory.anchorCount invalid",
    )
    reasons = inventory.get("reasons")
    checks = inventory.get("boundaryChecks")
    require(isinstance(reasons, list) and all(isinstance(item, str) for item in reasons), "inventory.reasons invalid")
    require(isinstance(checks, list), "inventory.boundaryChecks invalid")
    for index, check in enumerate(checks):
        label = f"inventory.boundaryChecks[{index}]"
        require(isinstance(check, dict), f"{label} must be an object")
        require(isinstance(check.get("neighborPrimaryGeofabrikId"), str) and check["neighborPrimaryGeofabrikId"], f"{label}.neighbor invalid")
        require(isinstance(check.get("boundBoundaryFingerprint"), str), f"{label}.bound fingerprint invalid")
        current = check.get("currentBoundaryFingerprint")
        require(current is None or isinstance(current, str), f"{label}.current fingerprint invalid")
        require(isinstance(check.get("matches"), bool), f"{label}.matches invalid")

    matrix = data.get("matrix")
    require(isinstance(matrix, dict), "matrix required")
    require(isinstance(matrix.get("present"), bool), "matrix.present invalid")
    require(isinstance(matrix.get("current"), bool), "matrix.current invalid")
    source_sha = matrix.get("sourceInventorySha256")
    require(
        source_sha is None or (isinstance(source_sha, str) and SHA256.fullmatch(source_sha)),
        "matrix.sourceInventorySha256 invalid",
    )
    source_anchor_count = matrix.get("sourceAnchorCount")
    require(
        source_anchor_count is None
        or (isinstance(source_anchor_count, int) and not isinstance(source_anchor_count, bool) and source_anchor_count >= 0),
        "matrix.sourceAnchorCount invalid",
    )
    matrix_reasons = matrix.get("reasons")
    require(isinstance(matrix_reasons, list) and all(isinstance(item, str) for item in matrix_reasons), "matrix.reasons invalid")

    status = data["status"]
    action = data["refreshAction"]
    if status == "CURRENT":
        require(action == "NONE", "CURRENT must have NONE refreshAction")
        require(inventory["current"] is True and matrix["current"] is True, "CURRENT requires current inventory and matrix")
    if action == "BUILD_MATRIX":
        require(inventory["current"] is True and matrix["present"] is False, "BUILD_MATRIX requires current inventory and missing matrix")
    if action == "REBUILD_MATRIX":
        require(inventory["current"] is True and matrix["present"] is True and matrix["current"] is False, "REBUILD_MATRIX state invalid")
    if action in {"BUILD_INVENTORY_AND_MATRIX", "REBUILD_INVENTORY_AND_MATRIX"}:
        require(inventory["current"] is False, f"{action} requires non-current inventory")

    generator = data.get("generator")
    require(isinstance(generator, dict), "generator required")
    require(isinstance(generator.get("name"), str) and generator["name"], "generator.name required")
    require(isinstance(generator.get("version"), str) and generator["version"], "generator.version required")

    print(f"valid connector refresh plan: {region} {status} action={action}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
