#!/usr/bin/env python3
"""Validate the app-consumable RoadPilot bound cross-graph transition artifact."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def finite(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def validate_binding(binding, region, fingerprint, label, errors):
    if binding.get("regionId") != region:
        errors.append(f"{label}: region mismatch")
    if binding.get("graphFingerprint") != fingerprint:
        errors.append(f"{label}: fingerprint mismatch")

    coordinate = binding.get("proofCoordinate", {})
    if not finite(coordinate.get("lat")) or not finite(coordinate.get("lng")):
        errors.append(f"{label}: invalid proof coordinate")

    candidates = binding.get("candidates", [])
    if not candidates:
        errors.append(f"{label}: no graph candidates")
        return

    ranks = set()
    for edge in candidates:
        rank = edge.get("correlationRank")
        if (
            not isinstance(rank, int)
            or rank < 0
            or rank in ranks
        ):
            errors.append(f"{label}: invalid/duplicate correlation rank")
        ranks.add(rank)

        for key in (
            "graphId",
            "opposingGraphId",
            "sourceNodeGraphId",
            "endNodeGraphId",
            "wayId",
        ):
            if not isinstance(edge.get(key), int) or edge[key] <= 0:
                errors.append(f"{label}: invalid {key}")

        percent = edge.get("percentAlong")
        if not finite(percent) or not 0 <= percent <= 1:
            errors.append(f"{label}: invalid percentAlong")

        distance = edge.get("distanceMeters")
        if not finite(distance) or distance < 0:
            errors.append(f"{label}: invalid distanceMeters")

        heading = edge.get("headingDegrees")
        if not finite(heading) or not 0 <= heading <= 360:
            errors.append(f"{label}: invalid headingDegrees")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", required=True, type=Path)
    args = parser.parse_args()
    data = json.loads(args.artifact.read_text(encoding="utf-8"))

    errors = []
    if (
        data.get("schema") != "roadpilot.bound-cross-graph-transitions"
        or data.get("version") != 1
    ):
        errors.append("unsupported schema/version")
    if data.get("bindingMode") not in {"MOTORCYCLE", "CAR"}:
        errors.append("unsupported bindingMode")

    from_region = data.get("fromRegionId")
    to_region = data.get("toRegionId")
    from_fingerprint = data.get("fromGraphFingerprint")
    to_fingerprint = data.get("toGraphFingerprint")

    if (
        not from_region
        or not to_region
        or from_region == to_region
    ):
        errors.append("invalid region pair")
    if not from_fingerprint or not to_fingerprint:
        errors.append("missing graph fingerprints")

    transitions = data.get("transitions", [])
    if not transitions:
        errors.append("transition artifact is empty")

    proof_ids = set()
    for index, transition in enumerate(transitions):
        proof_id = transition.get("sourceProofId")
        if not proof_id or proof_id in proof_ids:
            errors.append(
                f"transition[{index}] invalid/duplicate sourceProofId"
            )
        proof_ids.add(proof_id)

        validate_binding(
            transition.get("fromBinding", {}),
            from_region,
            from_fingerprint,
            f"transition[{index}].fromBinding",
            errors,
        )
        validate_binding(
            transition.get("toBinding", {}),
            to_region,
            to_fingerprint,
            f"transition[{index}].toBinding",
            errors,
        )

    if errors:
        raise SystemExit("\n".join(errors))

    print(
        f"valid bound transition artifact: {args.artifact} "
        f"({len(transitions)} transitions)"
    )


if __name__ == "__main__":
    main()
