#!/usr/bin/env python3
"""Validate RoadPilot regional connector entry-to-exit matrix artifacts."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
ANCHOR_ID = re.compile(r"^rca1-[0-9a-f]{24}$")
MODES = ("MOTORCYCLE", "CAR")


def fail(message: str) -> None:
    raise SystemExit(message)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def numeric_or_none(value: Any, label: str) -> None:
    require(
        value is None or (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and float(value) >= 0
        ),
        f"{label} invalid",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", required=True, type=Path)
    args = parser.parse_args()

    data = json.loads(args.artifact.read_text(encoding="utf-8"))
    require(isinstance(data, dict), "artifact must be an object")
    require(data.get("schema") == "roadpilot.region-connector-matrix", "unexpected schema")
    require(data.get("version") == 1, "version must be 1")

    region_id = data.get("regionId")
    require(isinstance(region_id, str) and region_id, "regionId required")
    graph = data.get("graph")
    require(isinstance(graph, dict), "graph required")
    require(graph.get("regionId") == region_id, "graph.regionId mismatch")
    for key in ("packageVersion", "primaryGeofabrikId"):
        require(isinstance(graph.get(key), str) and graph[key], f"graph.{key} required")
    fp = graph.get("graphFingerprint")
    require(isinstance(fp, str) and bool(SHA256.fullmatch(fp)), "graph.graphFingerprint invalid")

    source_hash = data.get("sourceInventorySha256")
    require(
        isinstance(source_hash, str) and bool(SHA256.fullmatch(source_hash)),
        "sourceInventorySha256 invalid",
    )
    source_anchor_count = data.get("sourceAnchorCount")
    require(
        isinstance(source_anchor_count, int)
        and not isinstance(source_anchor_count, bool)
        and source_anchor_count >= 0,
        "sourceAnchorCount invalid",
    )

    modes = data.get("modes")
    require(isinstance(modes, dict) and set(modes) == set(MODES), "modes invalid")
    for mode_name in MODES:
        mode = modes[mode_name]
        label = f"modes.{mode_name}"
        require(isinstance(mode, dict), f"{label} must be an object")
        entries = mode.get("entryAnchorIds")
        exits = mode.get("exitAnchorIds")
        cells = mode.get("cells")
        require(isinstance(entries, list), f"{label}.entryAnchorIds must be an array")
        require(isinstance(exits, list), f"{label}.exitAnchorIds must be an array")
        require(isinstance(cells, list), f"{label}.cells must be an array")
        require(entries == sorted(set(entries)), f"{label}.entryAnchorIds must be unique/sorted")
        require(exits == sorted(set(exits)), f"{label}.exitAnchorIds must be unique/sorted")
        require(all(isinstance(x, str) and ANCHOR_ID.fullmatch(x) for x in entries), f"{label}.entryAnchorIds invalid")
        require(all(isinstance(x, str) and ANCHOR_ID.fullmatch(x) for x in exits), f"{label}.exitAnchorIds invalid")

        expected_pairs = sum(1 for entry in entries for exit_id in exits if entry != exit_id)
        require(mode.get("candidatePairCount") == expected_pairs == len(cells), f"{label}.candidatePairCount mismatch")

        statuses = {"REACHABLE": 0, "UNREACHABLE": 0, "INCONCLUSIVE": 0}
        previous_key = None
        seen_pairs = set()
        for index, cell in enumerate(cells):
            c_label = f"{label}.cells[{index}]"
            require(isinstance(cell, dict), f"{c_label} must be an object")
            from_id = cell.get("fromAnchorId")
            to_id = cell.get("toAnchorId")
            require(from_id in entries, f"{c_label}.fromAnchorId not in entries")
            require(to_id in exits, f"{c_label}.toAnchorId not in exits")
            require(from_id != to_id, f"{c_label} self-pair is not allowed")
            key = (from_id, to_id)
            require(key not in seen_pairs, f"{c_label} duplicated")
            seen_pairs.add(key)
            if previous_key is not None:
                require(previous_key <= key, f"{label}.cells are not deterministically ordered")
            previous_key = key

            status = cell.get("status")
            require(status in statuses, f"{c_label}.status invalid")
            statuses[status] += 1
            for metric in (
                "distanceKm",
                "timeSeconds",
                "matrixDistanceKm",
                "matrixTimeSeconds",
                "matrixCost",
            ):
                numeric_or_none(cell.get(metric), f"{c_label}.{metric}")
            for graph_key in ("actualFromGraphId", "actualToGraphId"):
                value = cell.get(graph_key)
                require(
                    value is None or (
                        isinstance(value, int)
                        and not isinstance(value, bool)
                        and value > 0
                    ),
                    f"{c_label}.{graph_key} invalid",
                )
            error = cell.get("error")
            require(error is None or (isinstance(error, str) and error), f"{c_label}.error invalid")

            if status == "REACHABLE":
                require(cell["distanceKm"] is not None and cell["timeSeconds"] is not None, f"{c_label} REACHABLE missing exact metrics")
                require(cell["matrixDistanceKm"] is not None and cell["matrixTimeSeconds"] is not None, f"{c_label} REACHABLE missing matrix metrics")
                require(cell["actualFromGraphId"] is not None and cell["actualToGraphId"] is not None, f"{c_label} REACHABLE missing exact graph ids")
                require(error is None, f"{c_label} REACHABLE must not contain error")
            elif status == "UNREACHABLE":
                require(
                    all(cell[name] is None for name in (
                        "distanceKm","timeSeconds","matrixDistanceKm","matrixTimeSeconds",
                        "matrixCost","actualFromGraphId","actualToGraphId"
                    )),
                    f"{c_label} UNREACHABLE must not contain route metrics/ids",
                )
                require(error is None, f"{c_label} UNREACHABLE must not contain error")
            else:
                require(cell["distanceKm"] is None and cell["timeSeconds"] is None, f"{c_label} INCONCLUSIVE must not expose exact metrics")
                require(cell["matrixDistanceKm"] is not None and cell["matrixTimeSeconds"] is not None, f"{c_label} INCONCLUSIVE must preserve matrix evidence")
                require(isinstance(error, str) and error, f"{c_label} INCONCLUSIVE requires error")

        require(mode.get("reachableCount") == statuses["REACHABLE"], f"{label}.reachableCount mismatch")
        require(mode.get("unreachableCount") == statuses["UNREACHABLE"], f"{label}.unreachableCount mismatch")
        require(mode.get("inconclusiveCount") == statuses["INCONCLUSIVE"], f"{label}.inconclusiveCount mismatch")

    generator = data.get("generator")
    require(isinstance(generator, dict), "generator required")
    require(isinstance(generator.get("name"), str) and generator["name"], "generator.name required")
    require(isinstance(generator.get("version"), str) and generator["version"], "generator.version required")

    print(
        f"valid regional connector matrix: {region_id} "
        + " ".join(
            f"{mode.lower()}={modes[mode]['reachableCount']}/"
            f"{modes[mode]['candidatePairCount']} reachable"
            for mode in MODES
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
