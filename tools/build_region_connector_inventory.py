#!/usr/bin/env python3
"""Build a deterministic regional connector-anchor inventory from VALIDATED runtime connectivity."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

SCHEMA = "roadpilot.region-connector-inventory"
VERSION = 1
GENERATOR_NAME = "roadpilot-region-connector-inventory"
GENERATOR_VERSION = "1"
MODES = ("MOTORCYCLE", "CAR")


def fail(message: str) -> None:
    raise SystemExit(message)


def load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"Could not read {path}: {exc}")
    if not isinstance(value, dict):
        fail(f"{path}: expected JSON object")
    if value.get("schema") != "roadpilot.runtime-connectivity" or value.get("version") != 1:
        fail(f"{path}: unsupported runtime connectivity schema/version")
    if value.get("validationState") != "VALIDATED":
        fail(f"{path}: runtime connectivity must be VALIDATED")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def graph_identity(value: Any, label: str) -> dict[str, str]:
    if not isinstance(value, dict):
        fail(f"{label} must be an object")
    result: dict[str, str] = {}
    for key in ("regionId", "packageVersion", "graphFingerprint", "primaryGeofabrikId"):
        item = value.get(key)
        if not isinstance(item, str) or not item:
            fail(f"{label}.{key} is required")
        result[key] = item
    return result


def graph_anchor(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail(f"{label} must be an object")
    coordinate = value.get("coordinate")
    if not isinstance(coordinate, dict):
        fail(f"{label}.coordinate must be an object")
    try:
        lat = float(coordinate["lat"])
        lng = float(coordinate["lng"])
        graph_id = int(value["graphId"])
    except (KeyError, TypeError, ValueError) as exc:
        fail(f"{label} is invalid: {exc}")
    if not (-90 <= lat <= 90 and -180 <= lng <= 180 and graph_id > 0):
        fail(f"{label} contains invalid coordinate/graphId")
    way_id = value.get("wayId")
    if way_id is not None and (isinstance(way_id, bool) or not isinstance(way_id, int) or way_id <= 0):
        fail(f"{label}.wayId invalid")
    percent = value.get("percentAlong")
    if percent is not None:
        if isinstance(percent, bool) or not isinstance(percent, (int, float)) or not 0 <= float(percent) <= 1:
            fail(f"{label}.percentAlong invalid")
        percent = float(percent)
    return {
        "coordinate": {"lat": lat, "lng": lng},
        "graphId": graph_id,
        "wayId": way_id,
        "percentAlong": percent,
    }


def anchor_id(region_id: str, candidate_id: str, neighbor_region_id: str) -> str:
    raw = f"{region_id}|{candidate_id}|{neighbor_region_id}".encode("utf-8")
    return "rca1-" + hashlib.sha256(raw).hexdigest()[:24]


def roles_for_side(modes: Any, side: str) -> dict[str, list[str]]:
    if not isinstance(modes, dict):
        fail("crossing.modes must be an object")
    output: dict[str, list[str]] = {}
    for mode_name in MODES:
        mode = modes.get(mode_name)
        if not isinstance(mode, dict):
            fail(f"crossing.modes.{mode_name} must be an object")
        from_to = mode.get("fromTo")
        to_from = mode.get("toFrom")
        if not isinstance(from_to, bool) or not isinstance(to_from, bool):
            fail(f"crossing.modes.{mode_name} direction flags must be boolean")
        roles: list[str] = []
        if side == "from":
            if to_from:
                roles.append("ENTRY")
            if from_to:
                roles.append("EXIT")
        elif side == "to":
            if from_to:
                roles.append("ENTRY")
            if to_from:
                roles.append("EXIT")
        else:
            fail(f"unsupported side {side}")
        output[mode_name] = roles
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", required=True)
    parser.add_argument("--artifact", action="append", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    selected_graph: dict[str, str] | None = None
    sources: list[dict[str, str]] = []
    anchors: list[dict[str, Any]] = []
    seen_pairs: set[str] = set()
    seen_anchor_ids: set[str] = set()

    for path in sorted(args.artifact, key=lambda item: str(item)):
        if not path.is_file():
            fail(f"Artifact does not exist: {path}")
        data = load(path)
        pair_id = str(data.get("pairId") or "")
        from_region = str(data.get("fromRegionId") or "")
        to_region = str(data.get("toRegionId") or "")
        if pair_id != f"{from_region}__{to_region}":
            fail(f"{path}: invalid pair identity")
        if args.region not in (from_region, to_region):
            continue
        if pair_id in seen_pairs:
            fail(f"Duplicate runtime pair supplied: {pair_id}")
        seen_pairs.add(pair_id)

        side = "from" if args.region == from_region else "to"
        other_side = "to" if side == "from" else "from"
        region_graph = graph_identity(data.get(f"{side}Graph"), f"{path}.{side}Graph")
        neighbor_graph = graph_identity(data.get(f"{other_side}Graph"), f"{path}.{other_side}Graph")
        if region_graph["regionId"] != args.region:
            fail(f"{path}: selected graph region mismatch")
        if selected_graph is None:
            selected_graph = region_graph
        elif selected_graph != region_graph:
            fail(
                f"Conflicting graph identity for {args.region}: "
                f"{selected_graph['graphFingerprint']} vs {region_graph['graphFingerprint']}"
            )

        boundary_key = f"{side}BoundaryFingerprint"
        boundary = data.get(boundary_key)
        if not isinstance(boundary, str) or not boundary.startswith("sha256:") or len(boundary) != 71:
            fail(f"{path}: {boundary_key} invalid")

        sources.append({
            "pairId": pair_id,
            "sha256": sha256_file(path),
            "neighborRegionId": neighbor_graph["regionId"],
            "neighborPrimaryGeofabrikId": neighbor_graph["primaryGeofabrikId"],
            "regionBoundaryFingerprint": boundary,
        })

        crossings = data.get("crossings")
        if not isinstance(crossings, list):
            fail(f"{path}: crossings must be an array")
        for index, crossing in enumerate(crossings):
            if not isinstance(crossing, dict):
                fail(f"{path}: crossing[{index}] must be an object")
            candidate_id = crossing.get("candidateId")
            frontier_id = crossing.get("frontierRoadId")
            stable_way = crossing.get("stableWayId")
            if not isinstance(candidate_id, str) or not candidate_id:
                fail(f"{path}: crossing[{index}].candidateId required")
            if not isinstance(frontier_id, str) or not frontier_id:
                fail(f"{path}: crossing[{index}].frontierRoadId required")
            if isinstance(stable_way, bool) or not isinstance(stable_way, int) or stable_way <= 0:
                fail(f"{path}: crossing[{index}].stableWayId invalid")

            roles = roles_for_side(crossing.get("modes"), side)
            if not any(roles[mode] for mode in MODES):
                continue

            aid = anchor_id(args.region, candidate_id, neighbor_graph["regionId"])
            if aid in seen_anchor_ids:
                fail(f"Duplicate connector anchor id {aid}")
            seen_anchor_ids.add(aid)
            anchors.append({
                "id": aid,
                "candidateId": candidate_id,
                "frontierRoadId": frontier_id,
                "stableWayId": stable_way,
                "neighborRegionId": neighbor_graph["regionId"],
                "sourcePairId": pair_id,
                "graphAnchor": graph_anchor(
                    crossing.get(f"{side}Anchor"),
                    f"{path}.crossing[{index}].{side}Anchor",
                ),
                "roles": roles,
            })

    if selected_graph is None:
        fail(f"No VALIDATED runtime connectivity artifacts touch region {args.region}")

    sources.sort(key=lambda item: (item["neighborRegionId"], item["pairId"]))
    anchors.sort(
        key=lambda item: (
            item["neighborRegionId"],
            item["stableWayId"],
            item["candidateId"],
            item["id"],
        )
    )
    output = {
        "schema": SCHEMA,
        "version": VERSION,
        "regionId": args.region,
        "graph": selected_graph,
        "sourceConnectivity": sources,
        "anchorCount": len(anchors),
        "anchors": anchors,
        "generator": {"name": GENERATOR_NAME, "version": GENERATOR_VERSION},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(
        f"{args.region}: connector anchors={len(anchors)} "
        f"neighbors={len(sources)} graph={selected_graph['graphFingerprint']}"
    )
    print(f"wrote: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
