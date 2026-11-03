#!/usr/bin/env python3
"""Validate RoadPilot surgical connectivity refresh plans."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
STATUSES = {"CURRENT", "STALE", "UNRESOLVED"}
ACTIONS = {"NONE", "REBIND_GRAPH", "REDISCOVER_BOUNDARY", "WAIT_FOR_GRAPH"}
REASONS = {
    "FROM_GRAPH_CHANGED",
    "TO_GRAPH_CHANGED",
    "FROM_BOUNDARY_CHANGED",
    "TO_BOUNDARY_CHANGED",
    "FROM_GRAPH_MISSING",
    "TO_GRAPH_MISSING",
    "FROM_BOUNDARY_MISSING",
    "TO_BOUNDARY_MISSING",
}


def fail(message: str) -> None:
    raise SystemExit(message)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def side(value: Any, label: str) -> None:
    require(isinstance(value, dict), f"{label} must be an object")
    require(bool(str(value.get("regionId") or "").strip()), f"{label}.regionId required")
    require(
        bool(str(value.get("neighborPrimaryGeofabrikId") or "").strip()),
        f"{label}.neighborPrimaryGeofabrikId required",
    )
    for key in ("boundGraphFingerprint", "boundBoundaryFingerprint"):
        item = value.get(key)
        require(
            isinstance(item, str) and bool(SHA256.fullmatch(item)),
            f"{label}.{key} invalid",
        )
    for key in ("currentGraphFingerprint", "currentBoundaryFingerprint"):
        item = value.get(key)
        require(
            item is None or (isinstance(item, str) and bool(SHA256.fullmatch(item))),
            f"{label}.{key} invalid",
        )
    for key in ("graphMatches", "boundaryMatches"):
        item = value.get(key)
        require(item is None or isinstance(item, bool), f"{label}.{key} invalid")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", required=True, type=Path)
    args = parser.parse_args()

    data = json.loads(args.artifact.read_text(encoding="utf-8"))
    require(isinstance(data, dict), "artifact must be an object")
    require(data.get("schema") == "roadpilot.connectivity-refresh-plan", "unexpected schema")
    require(data.get("version") == 1, "version must be 1")

    for key in ("currentPairCount", "stalePairCount", "unresolvedPairCount"):
        item = data.get(key)
        require(
            isinstance(item, int) and not isinstance(item, bool) and item >= 0,
            f"{key} invalid",
        )

    pairs = data.get("pairs")
    affected = data.get("affectedPairs")
    require(isinstance(pairs, list), "pairs must be an array")
    require(isinstance(affected, list), "affectedPairs must be an array")
    require(len(affected) == len(set(affected)), "affectedPairs must be unique")

    seen = set()
    actual_current = actual_stale = actual_unresolved = 0
    actual_affected = []
    previous_pair = None

    for index, pair in enumerate(pairs):
        label = f"pair[{index}]"
        require(isinstance(pair, dict), f"{label} must be an object")
        pair_id = pair.get("pairId")
        require(isinstance(pair_id, str) and pair_id, f"{label}.pairId required")
        require(pair_id not in seen, f"{label}.pairId duplicated")
        seen.add(pair_id)
        if previous_pair is not None:
            require(previous_pair <= pair_id, "pairs are not deterministically ordered")
        previous_pair = pair_id

        status = pair.get("status")
        action = pair.get("refreshAction")
        require(status in STATUSES, f"{label}.status invalid")
        require(action in ACTIONS, f"{label}.refreshAction invalid")
        reasons = pair.get("reasons")
        require(isinstance(reasons, list), f"{label}.reasons must be an array")
        require(len(reasons) == len(set(reasons)), f"{label}.reasons duplicated")
        require(set(reasons) <= REASONS, f"{label}.reasons contains unknown values")

        side(pair.get("fromSide"), f"{label}.fromSide")
        side(pair.get("toSide"), f"{label}.toSide")

        if status == "CURRENT":
            actual_current += 1
            require(action == "NONE", f"{label} CURRENT must use NONE")
            require(reasons == [], f"{label} CURRENT must have no reasons")
        elif status == "STALE":
            actual_stale += 1
            actual_affected.append(pair_id)
            require(
                action in {"REBIND_GRAPH", "REDISCOVER_BOUNDARY"},
                f"{label} STALE has invalid refresh action",
            )
            require(reasons, f"{label} STALE requires reasons")
            require(
                not any(reason.endswith("_GRAPH_MISSING") for reason in reasons),
                f"{label} missing graph must be UNRESOLVED, not STALE",
            )
            if action == "REBIND_GRAPH":
                require(
                    any(reason.endswith("_GRAPH_CHANGED") for reason in reasons),
                    f"{label} REBIND_GRAPH requires graph change",
                )
                require(
                    not any("BOUNDARY_" in reason for reason in reasons),
                    f"{label} REBIND_GRAPH cannot hide a boundary change",
                )
            else:
                require(
                    any("BOUNDARY_" in reason for reason in reasons),
                    f"{label} REDISCOVER_BOUNDARY requires boundary reason",
                )
        else:
            actual_unresolved += 1
            require(action == "WAIT_FOR_GRAPH", f"{label} UNRESOLVED must wait for graph")
            require(
                any(reason.endswith("_GRAPH_MISSING") for reason in reasons),
                f"{label} UNRESOLVED requires missing graph",
            )

    require(actual_current == data["currentPairCount"], "currentPairCount mismatch")
    require(actual_stale == data["stalePairCount"], "stalePairCount mismatch")
    require(actual_unresolved == data["unresolvedPairCount"], "unresolvedPairCount mismatch")
    require(affected == actual_affected, "affectedPairs must equal stale pair ids in order")

    generator = data.get("generator")
    require(isinstance(generator, dict), "generator required")
    require(bool(str(generator.get("name") or "").strip()), "generator.name required")
    require(bool(str(generator.get("version") or "").strip()), "generator.version required")

    print(
        f"valid connectivity refresh plan: current={actual_current} "
        f"stale={actual_stale} unresolved={actual_unresolved}"
    )


if __name__ == "__main__":
    main()
