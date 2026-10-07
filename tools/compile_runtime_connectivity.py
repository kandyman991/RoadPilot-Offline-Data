#!/usr/bin/env python3
"""Compile compact RoadPilot runtime connectivity from proven crossing candidates.

Only PROVEN candidates are exported. Within each crossing, only mode/direction
support established by plain Valhalla proof is represented as true. Rejected and
inconclusive proof detail remains in development artifacts and is never promoted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

SCHEMA = "roadpilot.runtime-connectivity"
VERSION = 1
GENERATOR_NAME = "roadpilot-runtime-connectivity-compiler"
GENERATOR_VERSION = "1"


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


def finite(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        fail(f"{label} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        fail(f"{label} must be finite")
    return number


def positive_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        fail(f"{label} must be a positive integer")
    return value


def nullable_positive_int(value: Any, label: str) -> int | None:
    if value is None:
        return None
    return positive_int(value, label)


def coordinate(value: Any, label: str) -> dict[str, float]:
    if not isinstance(value, dict):
        fail(f"{label} must be an object")
    lat = finite(value.get("lat"), f"{label}.lat")
    lng = finite(value.get("lng"), f"{label}.lng")
    if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
        fail(f"{label} is outside valid latitude/longitude bounds")
    return {"lat": lat, "lng": lng}


def graph_identity(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail(f"{label} must be an object")
    result = {}
    for key in ("regionId", "packageVersion", "graphFingerprint", "primaryGeofabrikId"):
        item = value.get(key)
        if not isinstance(item, str) or not item:
            fail(f"{label}.{key} is required")
        result[key] = item
    return result


def require_identity_match(
    candidates: dict[str, Any],
    proofs: dict[str, Any],
) -> None:
    for key in (
        "pairId",
        "fromRegionId",
        "toRegionId",
        "fromBoundaryFingerprint",
        "toBoundaryFingerprint",
    ):
        if candidates.get(key) != proofs.get(key):
            fail(f"Candidate/proof mismatch for {key}")
    for key in ("fromGraph", "toGraph"):
        if candidates.get(key) != proofs.get(key):
            fail(f"Candidate/proof mismatch for {key}")


def passed_modes(proof: dict[str, Any], label: str) -> tuple[dict[str, Any], int]:
    modes = proof.get("modes")
    if not isinstance(modes, dict):
        fail(f"{label}.modes must be an object")
    output: dict[str, Any] = {}
    count = 0
    expected_supported: list[str] = []
    for output_mode in ("MOTORCYCLE", "CAR"):
        mode = modes.get(output_mode)
        if not isinstance(mode, dict):
            fail(f"{label}.modes.{output_mode} must be an object")
        mode_output = {}
        for field, suffix in (("fromTo", "FROM_TO"), ("toFrom", "TO_FROM")):
            direction = mode.get(field)
            if not isinstance(direction, dict) or not isinstance(direction.get("passed"), bool):
                fail(f"{label}.modes.{output_mode}.{field}.passed must be boolean")
            passed = bool(direction["passed"])
            mode_output[field] = passed
            if passed:
                count += 1
                expected_supported.append(f"{output_mode}_{suffix}")
                for graph_label in ("graphA", "graphB"):
                    leg = direction.get(graph_label)
                    if not isinstance(leg, dict):
                        fail(f"{label}.{output_mode}.{field}.{graph_label} missing")
                    if leg.get("status") != "PASSED" or leg.get("edgeMatched") is not True:
                        fail(
                            f"{label}.{output_mode}.{field} claims support without "
                            f"an exact-edge PASSED {graph_label} leg"
                        )
        output[output_mode] = mode_output

    supported = proof.get("supportedDirections")
    if not isinstance(supported, list):
        fail(f"{label}.supportedDirections must be an array")
    if supported != expected_supported:
        fail(
            f"{label}.supportedDirections does not match passed proof directions: "
            f"expected {expected_supported}, got {supported}"
        )
    return output, count


def anchor(edge: Any, label: str) -> dict[str, Any]:
    if not isinstance(edge, dict):
        fail(f"{label} must be an object")
    graph_id = positive_int(edge.get("graphId"), f"{label}.graphId")
    percent = edge.get("percentAlong")
    if percent is not None:
        percent = finite(percent, f"{label}.percentAlong")
        if not 0 <= percent <= 1:
            fail(f"{label}.percentAlong is outside [0,1]")
    return {
        "coordinate": coordinate(edge.get("correlatedCoordinate"), f"{label}.correlatedCoordinate"),
        "graphId": graph_id,
        "wayId": nullable_positive_int(edge.get("wayId"), f"{label}.wayId"),
        "percentAlong": percent,
    }


def road_summary(candidate: dict[str, Any]) -> dict[str, str | None]:
    tags = candidate.get("routingTags")
    if not isinstance(tags, dict):
        tags = {}
    def clean(key: str) -> str | None:
        value = tags.get(key)
        return value if isinstance(value, str) and value.strip() else None
    return {
        "name": clean("name"),
        "ref": clean("ref"),
        "highway": clean("highway"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", required=True, type=Path)
    parser.add_argument("--proofs", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    for path in (args.candidates, args.proofs):
        if not path.is_file():
            fail(f"Input does not exist: {path}")

    candidates = load_object(args.candidates, "candidate artifact")
    proofs = load_object(args.proofs, "proof artifact")
    if candidates.get("schema") != "roadpilot.crossing-candidates" or candidates.get("version") != 1:
        fail("Unsupported crossing candidate artifact")
    if candidates.get("validationState") != "UNPROVEN":
        fail("Crossing candidate artifact must be UNPROVEN")
    if proofs.get("schema") != "roadpilot.crossing-proofs" or proofs.get("version") != 1:
        fail("Unsupported crossing proof artifact")
    require_identity_match(candidates, proofs)

    pair_id = str(candidates.get("pairId") or "")
    from_region = str(candidates.get("fromRegionId") or "")
    to_region = str(candidates.get("toRegionId") or "")
    if pair_id != f"{from_region}__{to_region}":
        fail("Invalid directed pair identity")

    candidate_values = candidates.get("candidates")
    proof_values = proofs.get("proofs")
    if not isinstance(candidate_values, list) or not isinstance(proof_values, list):
        fail("Candidate/proof arrays are required")
    if proofs.get("sourceCandidateCount") != len(candidate_values):
        fail("Proof sourceCandidateCount does not match candidate artifact")
    if len(proof_values) != len(candidate_values):
        fail("Proof artifact must contain exactly one proof record per candidate")

    candidate_by_id: dict[str, dict[str, Any]] = {}
    for index, candidate in enumerate(candidate_values):
        if not isinstance(candidate, dict):
            fail(f"candidate[{index}] must be an object")
        candidate_id = candidate.get("id")
        if not isinstance(candidate_id, str) or not candidate_id:
            fail(f"candidate[{index}].id is required")
        if candidate_id in candidate_by_id:
            fail(f"Duplicate candidate id: {candidate_id}")
        candidate_by_id[candidate_id] = candidate

    seen_proofs = set()
    runtime_crossings = []
    supported_count = 0
    proven_count = 0
    for index, proof in enumerate(proof_values):
        if not isinstance(proof, dict):
            fail(f"proof[{index}] must be an object")
        candidate_id = proof.get("candidateId")
        if not isinstance(candidate_id, str) or candidate_id not in candidate_by_id:
            fail(f"proof[{index}] references unknown candidate")
        if candidate_id in seen_proofs:
            fail(f"Duplicate proof for candidate {candidate_id}")
        seen_proofs.add(candidate_id)

        if proof.get("proofState") != "PROVEN":
            continue
        proven_count += 1
        candidate = candidate_by_id[candidate_id]
        modes, mode_count = passed_modes(proof, f"proof[{index}]")
        if mode_count <= 0:
            fail(f"PROVEN proof {candidate_id} has no supported mode/direction")
        supported_count += mode_count

        evidence = candidate.get("evidence")
        if not isinstance(evidence, dict):
            fail(f"candidate {candidate_id} is missing evidence")
        tier = evidence.get("tier")
        if isinstance(tier, bool) or not isinstance(tier, int) or tier < 0:
            fail(f"candidate {candidate_id} has invalid evidence tier")

        rank = candidate.get("candidateRank")
        if isinstance(rank, bool) or not isinstance(rank, int) or rank < 0:
            fail(f"candidate {candidate_id} has invalid candidateRank")

        heading = finite(candidate.get("frontierHeadingDegrees"), "frontierHeadingDegrees")
        heading %= 360.0

        runtime_crossings.append(
            {
                "candidateId": candidate_id,
                "frontierRoadId": str(candidate.get("frontierRoadId") or ""),
                "stableWayId": positive_int(candidate.get("stableWayId"), "stableWayId"),
                "sourceCandidateRank": rank,
                "evidenceTier": tier,
                "frontierHeadingDegrees": heading,
                "road": road_summary(candidate),
                "fromAnchor": anchor(candidate.get("fromEdge"), "fromEdge"),
                "toAnchor": anchor(candidate.get("toEdge"), "toEdge"),
                "modes": modes,
            }
        )

    if len(seen_proofs) != len(candidate_by_id):
        missing = sorted(set(candidate_by_id) - seen_proofs)
        fail(f"Proof artifact is missing candidate ids: {', '.join(missing[:5])}")
    declared_proven = proofs.get("provenCandidateCount")
    if declared_proven != proven_count:
        fail(
            f"provenCandidateCount mismatch: declared={declared_proven} actual={proven_count}"
        )

    runtime_crossings.sort(
        key=lambda item: (
            item["evidenceTier"],
            item["sourceCandidateRank"],
            item["stableWayId"],
            item["candidateId"],
        )
    )

    output = {
        "schema": SCHEMA,
        "version": VERSION,
        "pairId": pair_id,
        "fromRegionId": from_region,
        "toRegionId": to_region,
        "fromBoundaryFingerprint": candidates["fromBoundaryFingerprint"],
        "toBoundaryFingerprint": candidates["toBoundaryFingerprint"],
        "fromGraph": graph_identity(candidates.get("fromGraph"), "fromGraph"),
        "toGraph": graph_identity(candidates.get("toGraph"), "toGraph"),
        "validationState": "VALIDATED",
        "sourceHashes": {
            "candidatesSha256": sha256_file(args.candidates),
            "proofsSha256": sha256_file(args.proofs),
        },
        "sourceCandidateCount": len(candidate_values),
        "sourceProofCount": len(proof_values),
        "validatedCrossingCount": len(runtime_crossings),
        "supportedModeDirectionCount": supported_count,
        "generator": {"name": GENERATOR_NAME, "version": GENERATOR_VERSION},
        "crossings": runtime_crossings,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(
        f"{pair_id}: validated crossings={len(runtime_crossings)} "
        f"supported mode/directions={supported_count}"
    )
    print(f"wrote: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
