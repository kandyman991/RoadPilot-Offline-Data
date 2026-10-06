#!/usr/bin/env python3
"""Validate RoadPilot cross-region connectivity metadata using only the standard library."""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any

SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
CANDIDATE_ID = re.compile(r"^xrc1-[0-9a-f]{24}$")
EVIDENCE = {
    "SAME_OSM_WAY",
    "SHARED_ROAD_REF",
    "SHARED_ROAD_NAME",
    "SPATIAL_PROXIMITY",
}
PROOF_STATES = {"UNTESTED", "VALID", "FAILED"}
VALIDATION_STATES = {"UNPROVEN", "PARTIAL", "VALIDATED"}


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
    require(-90.0 <= lat <= 90.0, f"{label}.lat is invalid")
    require(-180.0 <= lng <= 180.0, f"{label}.lng is invalid")


def anchor(value: Any, expected_region: str, label: str) -> None:
    require(isinstance(value, dict), f"{label} must be an object")
    require(value.get("regionId") == expected_region, f"{label}.regionId mismatch")
    coordinate(value.get("coordinate"), f"{label}.coordinate")

    percent = value.get("percentAlong")
    if percent is not None:
        percent_value = finite(percent, f"{label}.percentAlong")
        require(0.0 <= percent_value <= 1.0, f"{label}.percentAlong is invalid")

    heading = value.get("headingDegrees")
    if heading is not None:
        heading_value = finite(heading, f"{label}.headingDegrees")
        require(0.0 <= heading_value < 360.0, f"{label}.headingDegrees is invalid")

    way_id = value.get("wayId")
    if way_id is not None:
        require(
            (isinstance(way_id, int) and not isinstance(way_id, bool) and way_id > 0)
            or (isinstance(way_id, str) and way_id.strip()),
            f"{label}.wayId is invalid",
        )


def candidate(value: Any, from_region: str, to_region: str, label: str) -> str:
    require(isinstance(value, dict), f"{label} must be an object")
    candidate_id = str(value.get("id") or "")
    require(bool(CANDIDATE_ID.fullmatch(candidate_id)), f"{label}.id is invalid")
    anchor(value.get("fromAnchor"), from_region, f"{label}.fromAnchor")
    anchor(value.get("toAnchor"), to_region, f"{label}.toAnchor")

    evidence = value.get("matchEvidence")
    require(isinstance(evidence, list) and evidence, f"{label}.matchEvidence is empty")
    require(len(evidence) == len(set(evidence)), f"{label}.matchEvidence has duplicates")
    require(set(evidence) <= EVIDENCE, f"{label}.matchEvidence contains unknown evidence")

    separation = finite(value.get("separationMeters"), f"{label}.separationMeters")
    require(separation >= 0.0, f"{label}.separationMeters is invalid")

    proofs = value.get("proofs")
    require(isinstance(proofs, dict), f"{label}.proofs must be an object")
    require(set(proofs) == {"MOTORCYCLE", "CAR"}, f"{label}.proofs must contain MOTORCYCLE/CAR")
    for mode, mode_proof in proofs.items():
        require(isinstance(mode_proof, dict), f"{label}.proofs.{mode} must be an object")
        require(
            set(mode_proof) == {"fromTo", "toFrom"},
            f"{label}.proofs.{mode} must contain fromTo/toFrom",
        )
        for direction in ("fromTo", "toFrom"):
            require(
                mode_proof.get(direction) in PROOF_STATES,
                f"{label}.proofs.{mode}.{direction} is invalid",
            )
    return candidate_id


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", required=True, type=Path)
    args = parser.parse_args()

    data = json.loads(args.artifact.read_text(encoding="utf-8"))
    require(isinstance(data, dict), "artifact must be an object")
    require(data.get("schema") == "roadpilot.cross-region-connectivity", "unexpected schema")
    require(data.get("version") == 1, "version must be 1")

    from_region = str(data.get("fromRegionId") or "")
    to_region = str(data.get("toRegionId") or "")
    require(from_region and to_region and from_region != to_region, "invalid region pair")
    require(
        data.get("pairId") == f"{from_region}__{to_region}",
        "pairId must match directed region pair",
    )
    require(bool(str(data.get("fromPackageVersion") or "").strip()), "fromPackageVersion required")
    require(bool(str(data.get("toPackageVersion") or "").strip()), "toPackageVersion required")

    for key in (
        "fromGraphFingerprint",
        "toGraphFingerprint",
        "fromBoundaryFingerprint",
        "toBoundaryFingerprint",
    ):
        require(
            isinstance(data.get(key), str) and bool(SHA256.fullmatch(data[key])),
            f"{key} must be sha256:<64 lowercase hex>",
        )

    require(bool(str(data.get("fromBoundarySourceId") or "").strip()), "fromBoundarySourceId required")
    require(bool(str(data.get("toBoundarySourceId") or "").strip()), "toBoundarySourceId required")
    require(data.get("bindingState") == "STABLE_PHYSICAL", "bindingState must be STABLE_PHYSICAL")
    require(data.get("validationState") in VALIDATION_STATES, "invalid validationState")

    generator = data.get("generator")
    require(isinstance(generator, dict), "generator is required")
    require(bool(str(generator.get("name") or "").strip()), "generator.name required")
    require(bool(str(generator.get("version") or "").strip()), "generator.version required")

    candidates = data.get("candidates")
    require(isinstance(candidates, list), "candidates must be an array")
    ids: list[str] = []
    for index, item in enumerate(candidates):
        ids.append(candidate(item, from_region, to_region, f"candidate[{index}]"))
    require(len(ids) == len(set(ids)), "candidate ids must be unique")

    if data.get("validationState") == "VALIDATED":
        require(bool(candidates), "VALIDATED artifact must contain at least one candidate")
        require(
            any(
                any(
                    state == "VALID"
                    for mode in item["proofs"].values()
                    for state in mode.values()
                )
                for item in candidates
            ),
            "VALIDATED artifact must contain at least one successful proof",
        )

    print(
        f"valid connectivity metadata: {data['pairId']} "
        f"({len(candidates)} candidates, {data['validationState']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
