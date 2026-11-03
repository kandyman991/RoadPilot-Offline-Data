#!/usr/bin/env python3
"""Validate RoadPilot regional connector-anchor inventories."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
ANCHOR_ID = re.compile(r"^rca1-[0-9a-f]{24}$")
CANDIDATE_ID = re.compile(r"^xpc1-[0-9a-f]{24}$")
FRONTIER_ID = re.compile(r"^fri1-[0-9a-f]{24}$")
MODES = ("MOTORCYCLE", "CAR")
ROLES = {"ENTRY", "EXIT"}


def fail(message: str) -> None:
    raise SystemExit(message)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def graph(value: Any, region_id: str) -> None:
    require(isinstance(value, dict), "graph must be an object")
    require(value.get("regionId") == region_id, "graph.regionId mismatch")
    for key in ("packageVersion", "primaryGeofabrikId"):
        require(bool(str(value.get(key) or "").strip()), f"graph.{key} required")
    fp = value.get("graphFingerprint")
    require(isinstance(fp, str) and bool(SHA256.fullmatch(fp)), "graph.graphFingerprint invalid")


def graph_anchor(value: Any, label: str) -> None:
    require(isinstance(value, dict), f"{label} must be an object")
    coordinate = value.get("coordinate")
    require(isinstance(coordinate, dict), f"{label}.coordinate required")
    lat = coordinate.get("lat")
    lng = coordinate.get("lng")
    require(isinstance(lat, (int, float)) and not isinstance(lat, bool) and -90 <= lat <= 90, f"{label}.lat invalid")
    require(isinstance(lng, (int, float)) and not isinstance(lng, bool) and -180 <= lng <= 180, f"{label}.lng invalid")
    graph_id = value.get("graphId")
    require(isinstance(graph_id, int) and not isinstance(graph_id, bool) and graph_id > 0, f"{label}.graphId invalid")
    way_id = value.get("wayId")
    require(way_id is None or (isinstance(way_id, int) and not isinstance(way_id, bool) and way_id > 0), f"{label}.wayId invalid")
    percent = value.get("percentAlong")
    require(percent is None or (isinstance(percent, (int, float)) and not isinstance(percent, bool) and 0 <= percent <= 1), f"{label}.percentAlong invalid")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", required=True, type=Path)
    args = parser.parse_args()

    data = json.loads(args.artifact.read_text(encoding="utf-8"))
    require(isinstance(data, dict), "artifact must be an object")
    require(data.get("schema") == "roadpilot.region-connector-inventory", "unexpected schema")
    require(data.get("version") == 1, "version must be 1")
    region_id = str(data.get("regionId") or "")
    require(region_id, "regionId required")
    graph(data.get("graph"), region_id)

    sources = data.get("sourceConnectivity")
    require(isinstance(sources, list), "sourceConnectivity must be an array")
    previous_source = None
    seen_pairs = set()
    for index, source in enumerate(sources):
        label = f"sourceConnectivity[{index}]"
        require(isinstance(source, dict), f"{label} must be an object")
        pair_id = source.get("pairId")
        require(isinstance(pair_id, str) and pair_id, f"{label}.pairId required")
        require(pair_id not in seen_pairs, f"{label}.pairId duplicated")
        seen_pairs.add(pair_id)
        fp = source.get("sha256")
        require(isinstance(fp, str) and bool(SHA256.fullmatch(fp)), f"{label}.sha256 invalid")
        boundary = source.get("regionBoundaryFingerprint")
        require(isinstance(boundary, str) and bool(SHA256.fullmatch(boundary)), f"{label}.regionBoundaryFingerprint invalid")
        neighbor = source.get("neighborRegionId")
        primary = source.get("neighborPrimaryGeofabrikId")
        require(isinstance(neighbor, str) and neighbor and neighbor != region_id, f"{label}.neighborRegionId invalid")
        require(isinstance(primary, str) and primary, f"{label}.neighborPrimaryGeofabrikId required")
        key = (neighbor, pair_id)
        if previous_source is not None:
            require(previous_source <= key, "sourceConnectivity is not deterministically ordered")
        previous_source = key

    anchors = data.get("anchors")
    require(isinstance(anchors, list), "anchors must be an array")
    require(data.get("anchorCount") == len(anchors), "anchorCount mismatch")
    seen_ids = set()
    previous_anchor = None
    for index, anchor in enumerate(anchors):
        label = f"anchors[{index}]"
        require(isinstance(anchor, dict), f"{label} must be an object")
        aid = anchor.get("id")
        cid = anchor.get("candidateId")
        fid = anchor.get("frontierRoadId")
        require(isinstance(aid, str) and bool(ANCHOR_ID.fullmatch(aid)), f"{label}.id invalid")
        require(aid not in seen_ids, f"{label}.id duplicated")
        seen_ids.add(aid)
        require(isinstance(cid, str) and bool(CANDIDATE_ID.fullmatch(cid)), f"{label}.candidateId invalid")
        require(isinstance(fid, str) and bool(FRONTIER_ID.fullmatch(fid)), f"{label}.frontierRoadId invalid")
        stable_way = anchor.get("stableWayId")
        require(isinstance(stable_way, int) and not isinstance(stable_way, bool) and stable_way > 0, f"{label}.stableWayId invalid")
        neighbor = anchor.get("neighborRegionId")
        pair_id = anchor.get("sourcePairId")
        require(isinstance(neighbor, str) and neighbor and neighbor != region_id, f"{label}.neighborRegionId invalid")
        require(pair_id in seen_pairs, f"{label}.sourcePairId does not reference sourceConnectivity")
        graph_anchor(anchor.get("graphAnchor"), f"{label}.graphAnchor")

        roles = anchor.get("roles")
        require(isinstance(roles, dict), f"{label}.roles must be an object")
        require(set(roles) == set(MODES), f"{label}.roles keys invalid")
        has_role = False
        for mode in MODES:
            values = roles.get(mode)
            require(isinstance(values, list), f"{label}.roles.{mode} must be an array")
            require(len(values) == len(set(values)), f"{label}.roles.{mode} duplicated")
            require(set(values) <= ROLES, f"{label}.roles.{mode} invalid")
            require(values == sorted(values), f"{label}.roles.{mode} must be deterministic")
            has_role = has_role or bool(values)
        require(has_role, f"{label} must have at least one ENTRY/EXIT role")

        key = (neighbor, stable_way, cid, aid)
        if previous_anchor is not None:
            require(previous_anchor <= key, "anchors are not deterministically ordered")
        previous_anchor = key

    generator = data.get("generator")
    require(isinstance(generator, dict), "generator required")
    require(bool(str(generator.get("name") or "").strip()), "generator.name required")
    require(bool(str(generator.get("version") or "").strip()), "generator.version required")

    print(
        f"valid regional connector inventory: {region_id} "
        f"anchors={len(anchors)} neighbors={len(sources)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
