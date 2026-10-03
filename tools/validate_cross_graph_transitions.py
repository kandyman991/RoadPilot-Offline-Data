#!/usr/bin/env python3
import argparse
import json
import math
import re
from pathlib import Path

ID_PATTERN = re.compile(r"^xgt1-[0-9a-f]{24}$")
ALLOWED_MODES = {"MOTORCYCLE", "CAR", "BICYCLE", "WALKING"}
FORBIDDEN_BUILD_LOCAL_KEYS = {
    "graphId",
    "edgeId",
    "directedEdgeId",
    "nodeId",
    "tileId",
}

def fail(message: str) -> None:
    raise SystemExit(message)

def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)

def finite_non_negative(value, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        fail(f"{label} must be numeric")
    require(math.isfinite(number) and number >= 0.0, f"{label} must be finite and non-negative")
    return number

def validate_coordinate(value, label: str) -> None:
    require(isinstance(value, dict), f"{label} must be an object")
    require(set(value) == {"lat", "lng"}, f"{label} must contain only lat/lng")
    try:
        lat = float(value["lat"])
        lng = float(value["lng"])
    except (TypeError, ValueError, KeyError):
        fail(f"{label} must contain numeric lat/lng")
    require(math.isfinite(lat) and -90.0 <= lat <= 90.0, f"{label}.lat is invalid")
    require(math.isfinite(lng) and -180.0 <= lng <= 180.0, f"{label}.lng is invalid")

def reject_build_local_identity(value, location: str = "artifact") -> None:
    if isinstance(value, dict):
        forbidden = sorted(FORBIDDEN_BUILD_LOCAL_KEYS.intersection(value))
        require(not forbidden, f"{location} contains unbound build-local fields: {', '.join(forbidden)}")
        for key, nested in value.items():
            reject_build_local_identity(nested, f"{location}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            reject_build_local_identity(nested, f"{location}[{index}]")

def validate_anchor(anchor, expected_region: str, label: str) -> None:
    require(isinstance(anchor, dict), f"{label} must be an object")
    require(anchor.get("regionId") == expected_region, f"{label}.regionId mismatch")
    validate_coordinate(anchor.get("coordinate"), f"{label}.coordinate")
    heading = anchor.get("headingDegrees")
    if heading is not None:
        try:
            heading = float(heading)
        except (TypeError, ValueError):
            fail(f"{label}.headingDegrees must be numeric")
        require(math.isfinite(heading) and 0.0 <= heading < 360.0, f"{label}.headingDegrees is invalid")

def validate_transition(item, from_region: str, to_region: str, index: int) -> str:
    label = f"transition[{index}]"
    require(isinstance(item, dict), f"{label} must be an object")

    transition_id = str(item.get("id") or "")
    require(ID_PATTERN.fullmatch(transition_id) is not None, f"{label}.id is invalid")

    validate_anchor(item.get("fromAnchor"), from_region, f"{label}.fromAnchor")
    validate_anchor(item.get("toAnchor"), to_region, f"{label}.toAnchor")

    proposal = item.get("proposedCoordinate")
    if proposal is not None:
        validate_coordinate(proposal, f"{label}.proposedCoordinate")
    validate_coordinate(item.get("proofOriginCoordinate"), f"{label}.proofOriginCoordinate")
    validate_coordinate(item.get("proofDestinationCoordinate"), f"{label}.proofDestinationCoordinate")

    require(bool(str(item.get("matchEvidence") or "").strip()), f"{label}.matchEvidence is required")

    modes = item.get("provenTravelModes")
    require(isinstance(modes, list) and modes, f"{label}.provenTravelModes must be a non-empty array")
    require(len(modes) == len(set(modes)), f"{label}.provenTravelModes contains duplicates")
    unknown_modes = set(modes) - ALLOWED_MODES
    require(not unknown_modes, f"{label}.provenTravelModes contains unknown values: {sorted(unknown_modes)}")

    first_distance = finite_non_negative(item.get("firstLegDistanceMeters"), f"{label}.firstLegDistanceMeters")
    first_duration = finite_non_negative(item.get("firstLegDurationSeconds"), f"{label}.firstLegDurationSeconds")
    second_distance = finite_non_negative(item.get("secondLegDistanceMeters"), f"{label}.secondLegDistanceMeters")
    second_duration = finite_non_negative(item.get("secondLegDurationSeconds"), f"{label}.secondLegDurationSeconds")
    total_distance = finite_non_negative(item.get("totalDistanceMeters"), f"{label}.totalDistanceMeters")
    total_duration = finite_non_negative(item.get("totalDurationSeconds"), f"{label}.totalDurationSeconds")

    require(
        math.isclose(total_distance, first_distance + second_distance, rel_tol=0.0, abs_tol=0.01),
        f"{label}.totalDistanceMeters does not equal both regional legs",
    )
    require(
        math.isclose(total_duration, first_duration + second_duration, rel_tol=0.0, abs_tol=0.01),
        f"{label}.totalDurationSeconds does not equal both regional legs",
    )

    separation = item.get("frontierSeparationMeters")
    if separation is not None:
        finite_non_negative(separation, f"{label}.frontierSeparationMeters")

    heading_delta = item.get("seamHeadingDeltaDegrees")
    if heading_delta is not None:
        heading_delta = finite_non_negative(heading_delta, f"{label}.seamHeadingDeltaDegrees")
        require(heading_delta <= 180.0, f"{label}.seamHeadingDeltaDegrees must be <= 180")

    return transition_id

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--from-region")
    parser.add_argument("--to-region")
    parser.add_argument("--from-graph-fingerprint")
    parser.add_argument("--to-graph-fingerprint")
    args = parser.parse_args()

    path = Path(args.artifact)
    artifact = json.loads(path.read_text(encoding="utf-8"))
    reject_build_local_identity(artifact)

    require(artifact.get("schema") == "roadpilot.cross-graph-transitions", "unexpected artifact schema")
    require(artifact.get("version") == 1, "artifact version must be 1")

    from_region = str(artifact.get("fromRegionId") or "")
    to_region = str(artifact.get("toRegionId") or "")
    from_fingerprint = str(artifact.get("fromGraphFingerprint") or "")
    to_fingerprint = str(artifact.get("toGraphFingerprint") or "")

    require(from_region, "fromRegionId is required")
    require(to_region, "toRegionId is required")
    require(from_region != to_region, "artifact must connect two different regions")
    require(from_fingerprint, "fromGraphFingerprint is required")
    require(to_fingerprint, "toGraphFingerprint is required")

    if args.from_region is not None:
        require(from_region == args.from_region, "fromRegionId mismatch")
    if args.to_region is not None:
        require(to_region == args.to_region, "toRegionId mismatch")
    if args.from_graph_fingerprint is not None:
        require(from_fingerprint == args.from_graph_fingerprint, "from graph fingerprint mismatch")
    if args.to_graph_fingerprint is not None:
        require(to_fingerprint == args.to_graph_fingerprint, "to graph fingerprint mismatch")

    generator = artifact.get("generator")
    require(isinstance(generator, dict), "generator is required")
    require(bool(str(generator.get("name") or "").strip()), "generator.name is required")
    require(bool(str(generator.get("version") or "").strip()), "generator.version is required")

    transitions = artifact.get("transitions")
    require(isinstance(transitions, list) and transitions, "transitions must be a non-empty array")

    ids = [validate_transition(item, from_region, to_region, index) for index, item in enumerate(transitions)]
    require(len(ids) == len(set(ids)), "transition ids must be unique")

    print(
        f"{path}: valid cross-graph transition artifact "
        f"{from_region} -> {to_region}, transitions={len(transitions)}"
    )

if __name__ == "__main__":
    main()
