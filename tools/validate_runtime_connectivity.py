#!/usr/bin/env python3
"""Validate compact RoadPilot runtime connectivity metadata."""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any

SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
CANDIDATE_ID = re.compile(r"^xpc1-[0-9a-f]{24}$")
FRONTIER_ID = re.compile(r"^fri1-[0-9a-f]{24}$")


def fail(message: str) -> None:
    raise SystemExit(message)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def finite(value: Any, label: str) -> float:
    require(
        isinstance(value, (int, float)) and not isinstance(value, bool),
        f"{label} must be numeric",
    )
    number = float(value)
    require(math.isfinite(number), f"{label} must be finite")
    return number


def coordinate(value: Any, label: str) -> None:
    require(isinstance(value, dict), f"{label} must be an object")
    require(set(value) == {"lat", "lng"}, f"{label} must contain only lat/lng")
    lat = finite(value.get("lat"), f"{label}.lat")
    lng = finite(value.get("lng"), f"{label}.lng")
    require(-90 <= lat <= 90, f"{label}.lat invalid")
    require(-180 <= lng <= 180, f"{label}.lng invalid")


def graph(value: Any, expected_region: str, label: str) -> None:
    require(isinstance(value, dict), f"{label} must be an object")
    require(value.get("regionId") == expected_region, f"{label}.regionId mismatch")
    for key in ("packageVersion", "primaryGeofabrikId"):
        require(bool(str(value.get(key) or "").strip()), f"{label}.{key} required")
    fingerprint = value.get("graphFingerprint")
    require(
        isinstance(fingerprint, str) and bool(SHA256.fullmatch(fingerprint)),
        f"{label}.graphFingerprint invalid",
    )


def anchor(value: Any, label: str) -> None:
    require(isinstance(value, dict), f"{label} must be an object")
    coordinate(value.get("coordinate"), f"{label}.coordinate")
    graph_id = value.get("graphId")
    require(
        isinstance(graph_id, int) and not isinstance(graph_id, bool) and graph_id > 0,
        f"{label}.graphId invalid",
    )
    way_id = value.get("wayId")
    if way_id is not None:
        require(
            isinstance(way_id, int) and not isinstance(way_id, bool) and way_id > 0,
            f"{label}.wayId invalid",
        )
    percent = value.get("percentAlong")
    if percent is not None:
        number = finite(percent, f"{label}.percentAlong")
        require(0 <= number <= 1, f"{label}.percentAlong invalid")


def mode_support(value: Any, label: str) -> int:
    require(isinstance(value, dict), f"{label} must be an object")
    require(set(value) == {"fromTo", "toFrom"}, f"{label} must contain fromTo/toFrom")
    count = 0
    for key in ("fromTo", "toFrom"):
        require(isinstance(value.get(key), bool), f"{label}.{key} must be boolean")
        count += int(value[key])
    return count

def route_metric(value: Any, label: str) -> None:
    require(isinstance(value, dict), f"{label} must be an object")
    require(set(value) == {"distanceKm", "timeSeconds"}, f"{label} fields invalid")
    distance = finite(value.get("distanceKm"), f"{label}.distanceKm")
    route_time = finite(value.get("timeSeconds"), f"{label}.timeSeconds")
    require(distance >= 0, f"{label}.distanceKm invalid")
    require(route_time >= 0, f"{label}.timeSeconds invalid")


def validate_route_metrics(modes: dict[str, Any], metrics: Any, label: str) -> None:
    require(isinstance(metrics, dict), f"{label} must be an object")
    require(set(metrics) == {"MOTORCYCLE", "CAR"}, f"{label} keys invalid")
    for mode_name in ("MOTORCYCLE", "CAR"):
        mode_metrics = metrics.get(mode_name)
        require(isinstance(mode_metrics, dict), f"{label}.{mode_name} must be an object")
        require(
            set(mode_metrics) == {"fromTo", "toFrom"},
            f"{label}.{mode_name} must contain fromTo/toFrom",
        )
        mode_support_value = modes[mode_name]
        for direction in ("fromTo", "toFrom"):
            metric = mode_metrics.get(direction)
            if mode_support_value[direction]:
                route_metric(metric, f"{label}.{mode_name}.{direction}")
            else:
                require(
                    metric is None,
                    f"{label}.{mode_name}.{direction} must be null when unsupported",
                )



def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", required=True, type=Path)
    args = parser.parse_args()

    data = json.loads(args.artifact.read_text(encoding="utf-8"))
    require(isinstance(data, dict), "artifact must be an object")
    require(data.get("schema") == "roadpilot.runtime-connectivity", "unexpected schema")
    require(data.get("version") == 1, "version must be 1")
    require(data.get("validationState") == "VALIDATED", "validationState must be VALIDATED")

    from_region = str(data.get("fromRegionId") or "")
    to_region = str(data.get("toRegionId") or "")
    require(from_region and to_region and from_region != to_region, "invalid region pair")
    require(data.get("pairId") == f"{from_region}__{to_region}", "pairId mismatch")

    for key in ("fromBoundaryFingerprint", "toBoundaryFingerprint"):
        value = data.get(key)
        require(
            isinstance(value, str) and bool(SHA256.fullmatch(value)),
            f"{key} invalid",
        )
    graph(data.get("fromGraph"), from_region, "fromGraph")
    graph(data.get("toGraph"), to_region, "toGraph")

    source_hashes = data.get("sourceHashes")
    require(isinstance(source_hashes, dict), "sourceHashes must be an object")
    require(
        set(source_hashes) == {"candidatesSha256", "proofsSha256"},
        "sourceHashes must contain candidate/proof hashes",
    )
    for key, value in source_hashes.items():
        require(
            isinstance(value, str) and bool(SHA256.fullmatch(value)),
            f"sourceHashes.{key} invalid",
        )

    generator = data.get("generator")
    require(isinstance(generator, dict), "generator must be an object")
    require(bool(str(generator.get("name") or "").strip()), "generator.name required")
    require(bool(str(generator.get("version") or "").strip()), "generator.version required")

    for key in (
        "sourceCandidateCount",
        "sourceProofCount",
        "validatedCrossingCount",
        "supportedModeDirectionCount",
    ):
        value = data.get(key)
        require(
            isinstance(value, int) and not isinstance(value, bool) and value >= 0,
            f"{key} invalid",
        )

    require(
        data["sourceProofCount"] == data["sourceCandidateCount"],
        "sourceProofCount must match sourceCandidateCount",
    )

    crossings = data.get("crossings")
    require(isinstance(crossings, list), "crossings must be an array")
    require(
        len(crossings) == data["validatedCrossingCount"],
        "validatedCrossingCount mismatch",
    )

    ids = set()
    actual_supported = 0
    previous_key = None
    for index, crossing in enumerate(crossings):
        label = f"crossing[{index}]"
        require(isinstance(crossing, dict), f"{label} must be an object")
        candidate_id = crossing.get("candidateId")
        frontier_id = crossing.get("frontierRoadId")
        require(
            isinstance(candidate_id, str) and bool(CANDIDATE_ID.fullmatch(candidate_id)),
            f"{label}.candidateId invalid",
        )
        require(candidate_id not in ids, f"{label}.candidateId duplicated")
        ids.add(candidate_id)
        require(
            isinstance(frontier_id, str) and bool(FRONTIER_ID.fullmatch(frontier_id)),
            f"{label}.frontierRoadId invalid",
        )
        stable_way = crossing.get("stableWayId")
        require(
            isinstance(stable_way, int) and not isinstance(stable_way, bool) and stable_way > 0,
            f"{label}.stableWayId invalid",
        )
        rank = crossing.get("sourceCandidateRank")
        tier = crossing.get("evidenceTier")
        require(
            isinstance(rank, int) and not isinstance(rank, bool) and rank >= 0,
            f"{label}.sourceCandidateRank invalid",
        )
        require(
            isinstance(tier, int) and not isinstance(tier, bool) and tier >= 0,
            f"{label}.evidenceTier invalid",
        )
        heading = finite(crossing.get("frontierHeadingDegrees"), f"{label}.frontierHeadingDegrees")
        require(0 <= heading < 360, f"{label}.frontierHeadingDegrees invalid")

        road = crossing.get("road")
        require(isinstance(road, dict), f"{label}.road must be an object")
        require(set(road) == {"name", "ref", "highway"}, f"{label}.road fields invalid")
        for key, value in road.items():
            require(value is None or isinstance(value, str), f"{label}.road.{key} invalid")

        anchor(crossing.get("fromAnchor"), f"{label}.fromAnchor")
        anchor(crossing.get("toAnchor"), f"{label}.toAnchor")

        modes = crossing.get("modes")
        require(isinstance(modes, dict), f"{label}.modes must be an object")
        require(set(modes) == {"MOTORCYCLE", "CAR"}, f"{label}.modes keys invalid")
        supported = (
            mode_support(modes["MOTORCYCLE"], f"{label}.modes.MOTORCYCLE")
            + mode_support(modes["CAR"], f"{label}.modes.CAR")
        )
        require(supported > 0, f"{label} must have at least one proven mode/direction")
        validate_route_metrics(modes, crossing.get("routeMetrics"), f"{label}.routeMetrics")
        actual_supported += supported

        ordering = (tier, rank, stable_way, candidate_id)
        if previous_key is not None:
            require(previous_key <= ordering, "crossings are not deterministically ordered")
        previous_key = ordering

        forbidden = {
            "proofState",
            "error",
            "supportedDirections",
            "access",
            "headingDeltaDegrees",
            "combinedCorrelationDistanceMeters",
        }
        require(
            forbidden.isdisjoint(crossing.keys()),
            f"{label} leaked development-only proof/correlation fields",
        )

    require(
        actual_supported == data["supportedModeDirectionCount"],
        "supportedModeDirectionCount mismatch",
    )
    require(
        data["validatedCrossingCount"] <= data["sourceCandidateCount"],
        "validatedCrossingCount cannot exceed sourceCandidateCount",
    )

    print(
        f"valid runtime connectivity: {data['pairId']} "
        f"({len(crossings)} crossings, {actual_supported} mode/directions)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
