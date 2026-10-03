#!/usr/bin/env python3
"""Build exhaustive cross-graph transition candidates from two boundary-edge inventories.

This is the offline equivalent of F8's discovery stage, not its proof stage. The tool deliberately
keeps spatially plausible candidates even when road labels or OSM way IDs differ. Valhalla/Thor
must still prove direction and reachability before any candidate can be promoted into a production
bound transition artifact.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable

SCHEMA = "roadpilot.transition-candidates"
VERSION = 1
GENERATOR_NAME = "roadpilot-offline-boundary-pairer"
GENERATOR_VERSION = "1"
EARTH_RADIUS_M = 6_371_008.8
AUTO_ACCESS_MASK = 1
MOTORCYCLE_ACCESS_MASK = 1024


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def require_inventory(value: dict[str, Any], label: str) -> None:
    if value.get("schema") != "roadpilot.boundary-edge-inventory" or value.get("version") != 1:
        raise ValueError(f"{label}: unsupported boundary-edge inventory")
    if not value.get("regionId") or not value.get("graphFingerprint"):
        raise ValueError(f"{label}: missing regionId/graphFingerprint")
    if not isinstance(value.get("edges"), list):
        raise ValueError(f"{label}: edges must be an array")


def require_pair_config(value: dict[str, Any]) -> None:
    if value.get("schemaVersion") != 1:
        raise ValueError("pair config: unsupported schemaVersion")
    for key in ("id", "fromRegionId", "toRegionId", "candidateSearch"):
        if key not in value:
            raise ValueError(f"pair config: missing {key}")


def radians(value: float) -> float:
    return value * math.pi / 180.0


def distance_m(a: dict[str, float], b: dict[str, float]) -> float:
    lat1, lon1 = radians(float(a["lat"])), radians(float(a["lng"]))
    lat2, lon2 = radians(float(b["lat"])), radians(float(b["lng"]))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(h)))


def heading_delta(a: float, b: float) -> float:
    raw = abs(float(a) - float(b)) % 360.0
    return min(raw, 360.0 - raw)


def normalize_token(value: str) -> str:
    return "".join(ch.lower() for ch in value if ch.isalnum())


def normalized_set(values: Iterable[str]) -> set[str]:
    return {token for item in values if (token := normalize_token(str(item)))}


def motorized_modes_for_access(access_mask: int) -> set[str]:
    modes: set[str] = set()
    if int(access_mask) & AUTO_ACCESS_MASK:
        modes.add("CAR")
    if int(access_mask) & MOTORCYCLE_ACCESS_MASK:
        modes.add("MOTORCYCLE")
    return modes


def candidate_id(
    from_region: str,
    to_region: str,
    from_fingerprint: str,
    to_fingerprint: str,
    from_edge: dict[str, Any],
    to_edge: dict[str, Any],
) -> str:
    canonical = "|".join(
        [
            "v1",
            from_region,
            to_region,
            from_fingerprint,
            to_fingerprint,
            str(int(from_edge["graphId"])),
            str(int(to_edge["graphId"])),
        ]
    )
    return "xgc1-" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]


def evidence(from_edge: dict[str, Any], to_edge: dict[str, Any]) -> list[str]:
    result: list[str] = []
    if int(from_edge["wayId"]) == int(to_edge["wayId"]):
        result.append("SAME_OSM_WAY")
    if normalized_set(from_edge.get("roadRefs", [])) & normalized_set(to_edge.get("roadRefs", [])):
        result.append("SHARED_ROAD_REF")
    if normalized_set(from_edge.get("roadNames", [])) & normalized_set(to_edge.get("roadNames", [])):
        result.append("SHARED_ROAD_NAME")
    result.append("SPATIAL_PROXIMITY")
    return result


def match_score(item: dict[str, Any]) -> tuple[float, float, int, str]:
    # Heading is deliberately soft evidence only. We retain the candidate regardless of heading
    # and let Thor prove direction later, mirroring the post-F8 architecture.
    evidence_bonus = 0.0
    ev = set(item["matchEvidence"])
    if "SAME_OSM_WAY" in ev:
        evidence_bonus -= 40.0
    if "SHARED_ROAD_REF" in ev:
        evidence_bonus -= 12.0
    if "SHARED_ROAD_NAME" in ev:
        evidence_bonus -= 6.0
    return (
        float(item["separationMeters"]) + 0.08 * float(item["headingDeltaDegrees"]) + evidence_bonus,
        float(item["separationMeters"]),
        int(item["roadClassDelta"]),
        item["id"],
    )


def build_spatial_index(
    edges: list[dict[str, Any]],
    max_separation_m: float,
) -> tuple[dict[tuple[int, int], list[dict[str, Any]]], float, float]:
    latitudes = [float(e["anchorCoordinate"]["lat"]) for e in edges]
    reference_lat = sum(latitudes) / len(latitudes) if latitudes else 0.0
    lat_cell = max_separation_m / 111_320.0
    lon_scale = max(0.1, math.cos(radians(reference_lat)))
    lon_cell = max_separation_m / (111_320.0 * lon_scale)
    index: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for edge in edges:
        q = edge["anchorCoordinate"]
        key = (
            math.floor(float(q["lat"]) / lat_cell),
            math.floor(float(q["lng"]) / lon_cell),
        )
        index.setdefault(key, []).append(edge)
    return index, lat_cell, lon_cell


def nearby_edges(
    index: dict[tuple[int, int], list[dict[str, Any]]],
    lat_cell: float,
    lon_cell: float,
    coord: dict[str, float],
):
    base = (
        math.floor(float(coord["lat"]) / lat_cell),
        math.floor(float(coord["lng"]) / lon_cell),
    )
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            yield from index.get((base[0] + dy, base[1] + dx), ())


def build_candidates(
    from_inventory: dict[str, Any],
    to_inventory: dict[str, Any],
    pair_config: dict[str, Any],
) -> dict[str, Any]:
    require_inventory(from_inventory, "from inventory")
    require_inventory(to_inventory, "to inventory")
    require_pair_config(pair_config)

    from_region = str(pair_config["fromRegionId"])
    to_region = str(pair_config["toRegionId"])
    if from_inventory["regionId"] != from_region:
        raise ValueError("from inventory region does not match pair config")
    if to_inventory["regionId"] != to_region:
        raise ValueError("to inventory region does not match pair config")

    search = pair_config["candidateSearch"]
    max_separation = float(search["maxSeparationMeters"])
    if max_separation <= 0:
        raise ValueError("maxSeparationMeters must be positive")

    from_fp = str(from_inventory["graphFingerprint"])
    to_fp = str(to_inventory["graphFingerprint"])
    all_candidates: list[dict[str, Any]] = []
    to_index, lat_cell, lon_cell = build_spatial_index(
        to_inventory["edges"], max_separation
    )

    for from_edge in from_inventory["edges"]:
        local: list[dict[str, Any]] = []
        # Scanner edges are directed boundary -> interior. For A -> B, A travels
        # on the opposing direction (reverseAccess) and B travels on the stored
        # direction (forwardAccess). Filter with those exact directional masks.
        from_modes = motorized_modes_for_access(from_edge.get("reverseAccess", 0))
        if not from_modes:
            continue
        for to_edge in nearby_edges(
            to_index, lat_cell, lon_cell, from_edge["anchorCoordinate"]
        ):
            to_modes = motorized_modes_for_access(
                to_edge.get("forwardAccess", 0)
            )
            common_modes = sorted(from_modes & to_modes)
            if not common_modes:
                continue
            seam = distance_m(
                from_edge["anchorCoordinate"], to_edge["anchorCoordinate"]
            )
            if seam > max_separation:
                continue
            item = {
                "id": candidate_id(
                    from_region, to_region, from_fp, to_fp, from_edge, to_edge
                ),
                "fromEdge": from_edge,
                "toEdge": to_edge,
                "separationMeters": round(seam, 3),
                "headingDeltaDegrees": round(
                    heading_delta(
                        from_edge["headingDegrees"], to_edge["headingDegrees"]
                    ),
                    3,
                ),
                "roadClassDelta": abs(
                    int(from_edge["roadClass"]) - int(to_edge["roadClass"])
                ),
                "matchEvidence": evidence(from_edge, to_edge),
                "commonTravelModes": common_modes,
            }
            local.append(item)

        local.sort(key=match_score)
        all_candidates.extend(local)

    # Overlapping boundary windows can discover the exact same pair repeatedly. GraphId-pair
    # identity is exact for this graph build, so collapse only true duplicates.
    deduped = {item["id"]: item for item in all_candidates}
    candidates = sorted(deduped.values(), key=match_score)

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "fromRegionId": from_region,
        "toRegionId": to_region,
        "fromGraphFingerprint": from_fp,
        "toGraphFingerprint": to_fp,
        "generator": {
            "name": GENERATOR_NAME,
            "version": GENERATOR_VERSION,
        },
        "candidates": candidates,
    }


def verify_regression_anchors(
    catalog: dict[str, Any], pair_config: dict[str, Any]
) -> None:
    failures: list[str] = []
    for anchor in pair_config.get("regressionAnchors", []):
        point = anchor["coordinate"]
        radius = float(anchor["radiusMeters"])
        from_refs = normalized_set(anchor.get("fromRefs", []))
        to_refs = normalized_set(anchor.get("toRefs", []))

        matches = []
        for candidate in catalog["candidates"]:
            midpoint = {
                "lat": (
                    float(candidate["fromEdge"]["anchorCoordinate"]["lat"])
                    + float(candidate["toEdge"]["anchorCoordinate"]["lat"])
                )
                / 2.0,
                "lng": (
                    float(candidate["fromEdge"]["anchorCoordinate"]["lng"])
                    + float(candidate["toEdge"]["anchorCoordinate"]["lng"])
                )
                / 2.0,
            }
            if distance_m(midpoint, point) > radius:
                continue
            candidate_from_refs = normalized_set(
                candidate["fromEdge"].get("roadRefs", [])
            )
            candidate_to_refs = normalized_set(
                candidate["toEdge"].get("roadRefs", [])
            )
            if from_refs and not (from_refs & candidate_from_refs):
                continue
            if to_refs and not (to_refs & candidate_to_refs):
                continue
            matches.append(candidate)
        if not matches:
            failures.append(str(anchor["name"]))

    if failures:
        raise ValueError(
            "required routing regression corridor(s) missing from candidate catalog: "
            + ", ".join(failures)
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-inventory", required=True, type=Path)
    parser.add_argument("--to-inventory", required=True, type=Path)
    parser.add_argument("--pair-config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    from_inventory = load_json(args.from_inventory)
    to_inventory = load_json(args.to_inventory)
    pair_config = load_json(args.pair_config)
    catalog = build_candidates(from_inventory, to_inventory, pair_config)
    verify_regression_anchors(catalog, pair_config)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(catalog, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"{catalog['fromRegionId']} -> {catalog['toRegionId']}: "
        f"{len(catalog['candidates'])} transition candidates"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
