#!/usr/bin/env python3
"""Validate a RoadPilot routing transition candidate catalog without external dependencies."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

ALLOWED_MODES = {"MOTORCYCLE", "CAR"}
ALLOWED_EVIDENCE = {
    "SAME_OSM_WAY",
    "SHARED_ROAD_REF",
    "SHARED_ROAD_NAME",
    "SPATIAL_PROXIMITY",
}


def finite(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", required=True, type=Path)
    args = parser.parse_args()

    data = json.loads(args.catalog.read_text(encoding="utf-8"))
    errors = []

    if (
        data.get("schema") != "roadpilot.transition-candidates"
        or data.get("version") != 1
    ):
        errors.append("unsupported schema/version")
    if (
        not data.get("fromRegionId")
        or not data.get("toRegionId")
        or data.get("fromRegionId") == data.get("toRegionId")
    ):
        errors.append("invalid region pair")
    if not data.get("fromGraphFingerprint") or not data.get("toGraphFingerprint"):
        errors.append("missing graph fingerprint")

    ids = set()
    for index, candidate in enumerate(data.get("candidates", [])):
        candidate_id = candidate.get("id")
        if not isinstance(candidate_id, str) or not candidate_id.startswith("xgc1-"):
            errors.append(f"candidate[{index}] invalid id")
        elif candidate_id in ids:
            errors.append(f"candidate[{index}] duplicate id")
        else:
            ids.add(candidate_id)

        separation = candidate.get("separationMeters")
        if not finite(separation) or separation < 0:
            errors.append(f"candidate[{index}] invalid separation")

        heading = candidate.get("headingDeltaDegrees")
        if not finite(heading) or not 0 <= heading <= 180:
            errors.append(f"candidate[{index}] invalid heading delta")

        modes = set(candidate.get("commonTravelModes", []))
        if not modes or not modes <= ALLOWED_MODES:
            errors.append(f"candidate[{index}] invalid modes")

        evidence = set(candidate.get("matchEvidence", []))
        if (
            "SPATIAL_PROXIMITY" not in evidence
            or not evidence <= ALLOWED_EVIDENCE
        ):
            errors.append(f"candidate[{index}] invalid evidence")

        for side in ("fromEdge", "toEdge"):
            edge = candidate.get(side, {})
            for key in (
                "graphId",
                "opposingGraphId",
                "sourceNodeGraphId",
                "endNodeGraphId",
                "wayId",
            ):
                if not isinstance(edge.get(key), int) or edge[key] <= 0:
                    errors.append(f"candidate[{index}] {side}.{key} invalid")

            for key in ("anchorCoordinate", "innerCoordinate"):
                coordinate = edge.get(key, {})
                lat = coordinate.get("lat")
                lng = coordinate.get("lng")
                if (
                    not finite(lat)
                    or not -90 <= lat <= 90
                    or not finite(lng)
                    or not -180 <= lng <= 180
                ):
                    errors.append(
                        f"candidate[{index}] {side}.{key} invalid"
                    )

    if errors:
        raise SystemExit("\n".join(errors))

    print(
        f"valid transition candidate catalog: {args.catalog} "
        f"({len(data.get('candidates', []))} candidates)"
    )


if __name__ == "__main__":
    main()
