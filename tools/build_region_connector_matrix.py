#!/usr/bin/env python3
"""Build exact-edge-validated entry->exit matrices for one RoadPilot regional graph."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from prove_crossing_candidates import trace_route_endpoint

SCHEMA = "roadpilot.region-connector-matrix"
VERSION = 1
GENERATOR_NAME = "roadpilot-region-connector-matrix"
GENERATOR_VERSION = "1"
MODE_COSTING = {"MOTORCYCLE": "motorcycle", "CAR": "auto"}
PAIR_BATCH_LIMIT = 1600


def fail(message: str) -> None:
    raise SystemExit(message)


def load_object(path: Path, label: str) -> dict[str, Any]:
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


def run_capture(command: list[str]) -> str:
    try:
        result = subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as exc:
        fail(f"Could not execute {command[0]}: {exc}")
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        fail(f"Command failed ({result.returncode}): {' '.join(command)}\n{detail}")
    return result.stdout


def safe_child(parent: Path, name: str, label: str) -> Path:
    child = (parent / name).resolve()
    root = parent.resolve()
    try:
        child.relative_to(root)
    except ValueError:
        fail(f"{label} escapes manifest directory: {name}")
    return child


def load_inventory(path: Path) -> dict[str, Any]:
    data = load_object(path, "connector inventory")
    if data.get("schema") != "roadpilot.region-connector-inventory" or data.get("version") != 1:
        fail("Unsupported regional connector inventory schema/version")
    region_id = str(data.get("regionId") or "")
    graph = data.get("graph")
    anchors = data.get("anchors")
    sources = data.get("sourceConnectivity")
    if not region_id or not isinstance(graph, dict) or not isinstance(anchors, list) or not isinstance(sources, list):
        fail("Connector inventory is missing region/graph/anchors/sourceConnectivity")
    if graph.get("regionId") != region_id:
        fail("Connector inventory graph.regionId mismatch")
    if data.get("anchorCount") != len(anchors):
        fail("Connector inventory anchorCount mismatch")
    return data


def prepare_graph(
    manifest_path: Path,
    inventory: dict[str, Any],
    temp_root: Path,
) -> tuple[dict[str, str], Path]:
    manifest = load_object(manifest_path, "routing manifest")
    if manifest.get("schema") != "roadpilot-routing-pack" or manifest.get("schemaVersion") != 1:
        fail("Unsupported routing manifest schema/version")

    expected_graph = inventory["graph"]
    for key in ("regionId", "packageVersion", "graphFingerprint"):
        if manifest.get(key) != expected_graph.get(key):
            fail(
                f"Routing manifest {key} does not match connector inventory: "
                f"manifest={manifest.get(key)} inventory={expected_graph.get(key)}"
            )
    source = manifest.get("source")
    if not isinstance(source, dict) or source.get("primaryGeofabrikId") != expected_graph.get("primaryGeofabrikId"):
        fail("Routing manifest primaryGeofabrikId does not match connector inventory")

    graph_index = manifest.get("graphIndex")
    boundaries = graph_index.get("boundaryFingerprints") if isinstance(graph_index, dict) else None
    if not isinstance(boundaries, dict):
        fail("Routing manifest graphIndex.boundaryFingerprints required")
    for index, source_item in enumerate(inventory["sourceConnectivity"]):
        if not isinstance(source_item, dict):
            fail(f"sourceConnectivity[{index}] must be an object")
        neighbor_primary = source_item.get("neighborPrimaryGeofabrikId")
        expected_boundary = source_item.get("regionBoundaryFingerprint")
        if boundaries.get(neighbor_primary) != expected_boundary:
            fail(
                f"Boundary fingerprint for {neighbor_primary} is stale: "
                f"inventory={expected_boundary} manifest={boundaries.get(neighbor_primary)}"
            )

    artifact = manifest.get("artifact")
    if not isinstance(artifact, dict):
        fail("Routing manifest artifact required")
    artifact_name = str(artifact.get("fileName") or "")
    if not artifact_name:
        fail("Routing manifest artifact.fileName required")
    artifact_path = safe_child(manifest_path.parent, artifact_name, "routing artifact")
    if not artifact_path.is_file():
        fail(f"Routing artifact does not exist: {artifact_path}")
    actual_sha = sha256_file(artifact_path)
    graph_fp = str(manifest["graphFingerprint"])
    if graph_fp != actual_sha:
        fail(
            f"Routing graph fingerprint does not match retained artifact: "
            f"manifest={graph_fp} actual={actual_sha}"
        )
    declared_sha = artifact.get("sha256")
    if declared_sha is not None and f"sha256:{declared_sha}" != actual_sha and str(declared_sha) != actual_sha:
        fail("Routing artifact.sha256 does not match retained artifact")

    if shutil.which("valhalla_build_config") is None:
        fail("valhalla_build_config is required")
    if shutil.which("valhalla_service") is None:
        fail("valhalla_service is required")

    tile_dir = temp_root / "tiles"
    tile_dir.mkdir(parents=True, exist_ok=True)
    config_text = run_capture([
        "valhalla_build_config",
        "--mjolnir-tile-dir",
        str(tile_dir),
        "--mjolnir-tile-extract",
        str(artifact_path),
    ])
    try:
        config = json.loads(config_text)
    except json.JSONDecodeError as exc:
        fail(f"valhalla_build_config returned invalid JSON: {exc}")
    if not isinstance(config, dict):
        fail("Valhalla config must be an object")

    # These are local build-time requests, not a public service. Raise only request
    # guards so a large regional frontier is not rejected before the matrix algorithm runs.
    service_limits = config.setdefault("service_limits", {})
    if isinstance(service_limits, dict):
        for costing in MODE_COSTING.values():
            limits = service_limits.setdefault(costing, {})
            if isinstance(limits, dict):
                limits["max_matrix_distance"] = max(
                    int(limits.get("max_matrix_distance") or 0),
                    40_000_000,
                )
                limits["max_matrix_location_pairs"] = max(
                    int(limits.get("max_matrix_location_pairs") or 0),
                    PAIR_BATCH_LIMIT,
                )
                limits["max_locations"] = max(
                    int(limits.get("max_locations") or 0),
                    2000,
                )

    config_path = temp_root / "valhalla.json"
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return (
        {
            "regionId": str(manifest["regionId"]),
            "packageVersion": str(manifest["packageVersion"]),
            "graphFingerprint": graph_fp,
            "primaryGeofabrikId": str(source["primaryGeofabrikId"]),
        },
        config_path,
    )


def coordinate(anchor: dict[str, Any]) -> dict[str, float]:
    value = anchor.get("graphAnchor")
    if not isinstance(value, dict):
        fail(f"Anchor {anchor.get('id')} has no graphAnchor")
    point = value.get("coordinate")
    if not isinstance(point, dict):
        fail(f"Anchor {anchor.get('id')} has no coordinate")
    return {"lat": float(point["lat"]), "lon": float(point["lng"])}


def graph_id(anchor: dict[str, Any]) -> int:
    value = anchor.get("graphAnchor")
    graph_id_value = value.get("graphId") if isinstance(value, dict) else None
    if isinstance(graph_id_value, bool) or not isinstance(graph_id_value, int) or graph_id_value <= 0:
        fail(f"Anchor {anchor.get('id')} has invalid graphId")
    return graph_id_value


def matrix_batches(
    config_path: Path,
    costing: str,
    entries: list[dict[str, Any]],
    exits: list[dict[str, Any]],
) -> dict[tuple[str, str], dict[str, float] | None]:
    output: dict[tuple[str, str], dict[str, float] | None] = {}
    if not entries or not exits:
        return output

    target_chunk_size = max(1, min(len(exits), int(math.sqrt(PAIR_BATCH_LIMIT))))
    source_chunk_size = max(1, PAIR_BATCH_LIMIT // target_chunk_size)

    for source_start in range(0, len(entries), source_chunk_size):
        source_chunk = entries[source_start : source_start + source_chunk_size]
        for target_start in range(0, len(exits), target_chunk_size):
            target_chunk = exits[target_start : target_start + target_chunk_size]
            request = {
                "sources": [coordinate(anchor) for anchor in source_chunk],
                "targets": [coordinate(anchor) for anchor in target_chunk],
                "costing": costing,
                "units": "kilometers",
                "verbose": True,
                "expansion_max_distance": 0,
            }
            raw = run_capture([
                "valhalla_service",
                str(config_path),
                "sources_to_targets",
                json.dumps(request, separators=(",", ":")),
            ])
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as exc:
                fail(f"Valhalla matrix returned invalid JSON: {exc}")
            rows = payload.get("sources_to_targets") if isinstance(payload, dict) else None
            if not isinstance(rows, list) or len(rows) != len(source_chunk):
                fail("Valhalla matrix response row count mismatch")
            for source_index, row in enumerate(rows):
                if not isinstance(row, list) or len(row) != len(target_chunk):
                    fail("Valhalla matrix response column count mismatch")
                source_anchor = source_chunk[source_index]
                for target_index, cell in enumerate(row):
                    target_anchor = target_chunk[target_index]
                    key = (str(source_anchor["id"]), str(target_anchor["id"]))
                    if not isinstance(cell, dict):
                        fail("Valhalla matrix cell must be an object")
                    distance = cell.get("distance")
                    route_time = cell.get("time")
                    cost = cell.get("cost")
                    if distance is None or route_time is None:
                        output[key] = None
                        continue
                    if any(
                        isinstance(value, bool) or not isinstance(value, (int, float))
                        for value in (distance, route_time)
                    ):
                        fail("Valhalla matrix returned invalid distance/time")
                    output[key] = {
                        "distanceKm": float(distance),
                        "timeSeconds": float(route_time),
                        "cost": float(cost) if isinstance(cost, (int, float)) and not isinstance(cost, bool) else float(route_time),
                    }
    return output


def exact_route(
    config_path: Path,
    costing: str,
    entry: dict[str, Any],
    exit_anchor: dict[str, Any],
    matrix_value: dict[str, float],
) -> dict[str, Any]:
    request = {
        "locations": [coordinate(entry), coordinate(exit_anchor)],
        "costing": costing,
        "units": "kilometers",
        "directions_options": {"units": "kilometers"},
    }
    try:
        result = subprocess.run(
            [
                "valhalla_service",
                str(config_path),
                "route",
                json.dumps(request, separators=(",", ":")),
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as exc:
        return inconclusive(entry, exit_anchor, matrix_value, f"Could not execute valhalla_service: {exc}")

    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "Valhalla route failed"
        return inconclusive(entry, exit_anchor, matrix_value, detail)

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return inconclusive(entry, exit_anchor, matrix_value, f"Valhalla route returned invalid JSON: {exc}")
    trip = payload.get("trip") if isinstance(payload, dict) else None
    if not isinstance(trip, dict) or trip.get("status", 0) != 0:
        return inconclusive(
            entry,
            exit_anchor,
            matrix_value,
            str(trip.get("status_message") if isinstance(trip, dict) else "Valhalla route has no trip"),
        )
    legs = trip.get("legs")
    if not isinstance(legs, list) or len(legs) != 1 or not isinstance(legs[0], dict):
        return inconclusive(entry, exit_anchor, matrix_value, "Valhalla route did not return exactly one leg")
    shape = legs[0].get("shape")
    if not isinstance(shape, str) or not shape:
        return inconclusive(entry, exit_anchor, matrix_value, "Valhalla route returned no encoded shape")

    actual_from, from_error = trace_route_endpoint(config_path, shape, costing, "START")
    actual_to, to_error = trace_route_endpoint(config_path, shape, costing, "END")
    expected_from = graph_id(entry)
    expected_to = graph_id(exit_anchor)
    if from_error or to_error:
        return inconclusive(
            entry,
            exit_anchor,
            matrix_value,
            "; ".join(error for error in (from_error, to_error) if error),
            actual_from,
            actual_to,
        )
    if actual_from != expected_from or actual_to != expected_to:
        return inconclusive(
            entry,
            exit_anchor,
            matrix_value,
            (
                f"Endpoint edge mismatch: expected {expected_from}->{expected_to}, "
                f"got {actual_from}->{actual_to}"
            ),
            actual_from,
            actual_to,
        )

    summary = trip.get("summary")
    if not isinstance(summary, dict):
        return inconclusive(entry, exit_anchor, matrix_value, "Valhalla route has no trip summary", actual_from, actual_to)
    distance = summary.get("length")
    route_time = summary.get("time")
    if any(
        isinstance(value, bool) or not isinstance(value, (int, float))
        for value in (distance, route_time)
    ):
        return inconclusive(entry, exit_anchor, matrix_value, "Valhalla route summary metrics invalid", actual_from, actual_to)

    return {
        "fromAnchorId": entry["id"],
        "toAnchorId": exit_anchor["id"],
        "status": "REACHABLE",
        "distanceKm": float(distance),
        "timeSeconds": float(route_time),
        "matrixDistanceKm": matrix_value["distanceKm"],
        "matrixTimeSeconds": matrix_value["timeSeconds"],
        "matrixCost": matrix_value["cost"],
        "actualFromGraphId": actual_from,
        "actualToGraphId": actual_to,
        "error": None,
    }


def inconclusive(
    entry: dict[str, Any],
    exit_anchor: dict[str, Any],
    matrix_value: dict[str, float],
    error: str,
    actual_from: int | None = None,
    actual_to: int | None = None,
) -> dict[str, Any]:
    return {
        "fromAnchorId": entry["id"],
        "toAnchorId": exit_anchor["id"],
        "status": "INCONCLUSIVE",
        "distanceKm": None,
        "timeSeconds": None,
        "matrixDistanceKm": matrix_value["distanceKm"],
        "matrixTimeSeconds": matrix_value["timeSeconds"],
        "matrixCost": matrix_value["cost"],
        "actualFromGraphId": actual_from,
        "actualToGraphId": actual_to,
        "error": error or "Exact endpoint proof was inconclusive",
    }


def build_mode(
    config_path: Path,
    mode_name: str,
    anchors: list[dict[str, Any]],
) -> dict[str, Any]:
    costing = MODE_COSTING[mode_name]
    entries = [
        anchor for anchor in anchors
        if "ENTRY" in (anchor.get("roles", {}).get(mode_name) or [])
    ]
    exits = [
        anchor for anchor in anchors
        if "EXIT" in (anchor.get("roles", {}).get(mode_name) or [])
    ]
    entries.sort(key=lambda item: item["id"])
    exits.sort(key=lambda item: item["id"])
    matrix = matrix_batches(config_path, costing, entries, exits)

    cells: list[dict[str, Any]] = []
    for entry in entries:
        for exit_anchor in exits:
            if entry["id"] == exit_anchor["id"]:
                continue
            matrix_value = matrix.get((entry["id"], exit_anchor["id"]))
            if matrix_value is None:
                cells.append({
                    "fromAnchorId": entry["id"],
                    "toAnchorId": exit_anchor["id"],
                    "status": "UNREACHABLE",
                    "distanceKm": None,
                    "timeSeconds": None,
                    "matrixDistanceKm": None,
                    "matrixTimeSeconds": None,
                    "matrixCost": None,
                    "actualFromGraphId": None,
                    "actualToGraphId": None,
                    "error": None,
                })
            else:
                cells.append(exact_route(config_path, costing, entry, exit_anchor, matrix_value))

    cells.sort(key=lambda item: (item["fromAnchorId"], item["toAnchorId"]))
    return {
        "entryAnchorIds": [anchor["id"] for anchor in entries],
        "exitAnchorIds": [anchor["id"] for anchor in exits],
        "candidatePairCount": len(cells),
        "reachableCount": sum(cell["status"] == "REACHABLE" for cell in cells),
        "unreachableCount": sum(cell["status"] == "UNREACHABLE" for cell in cells),
        "inconclusiveCount": sum(cell["status"] == "INCONCLUSIVE" for cell in cells),
        "cells": cells,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    for path in (args.inventory, args.manifest):
        if not path.is_file():
            fail(f"Input does not exist: {path}")

    inventory = load_inventory(args.inventory)
    anchors = inventory["anchors"]
    with tempfile.TemporaryDirectory(prefix="roadpilot-region-matrix-") as temp_dir:
        graph, config_path = prepare_graph(args.manifest, inventory, Path(temp_dir))
        modes = {
            mode_name: build_mode(config_path, mode_name, anchors)
            for mode_name in MODE_COSTING
        }

    output = {
        "schema": SCHEMA,
        "version": VERSION,
        "regionId": inventory["regionId"],
        "graph": graph,
        "sourceInventorySha256": sha256_file(args.inventory),
        "sourceAnchorCount": len(anchors),
        "modes": modes,
        "generator": {"name": GENERATOR_NAME, "version": GENERATOR_VERSION},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(
        f"{output['regionId']}: "
        + " ".join(
            f"{mode.lower()} reachable={value['reachableCount']} "
            f"unreachable={value['unreachableCount']} inconclusive={value['inconclusiveCount']}"
            for mode, value in modes.items()
        )
    )
    print(f"wrote: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
