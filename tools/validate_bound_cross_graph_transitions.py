#!/usr/bin/env python3
import argparse
import json
import math
import re
from pathlib import Path

PROOF_ID = re.compile(r"^xgt1-[0-9a-f]{24}$")
MODES = {"MOTORCYCLE", "CAR", "BICYCLE", "WALKING"}

def fail(message: str) -> None:
    raise SystemExit(message)

def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)

def finite(value, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        fail(f"{label} must be numeric")
    require(math.isfinite(number), f"{label} must be finite")
    return number

def positive_int(value, label: str) -> int:
    require(isinstance(value, int) and not isinstance(value, bool) and value > 0, f"{label} must be a positive integer")
    return value

def non_negative_int(value, label: str) -> int:
    require(isinstance(value, int) and not isinstance(value, bool) and value >= 0, f"{label} must be a non-negative integer")
    return value

def coordinate(value, label: str) -> None:
    require(isinstance(value, dict), f"{label} must be an object")
    require(set(value) == {"lat", "lng"}, f"{label} must contain only lat/lng")
    lat = finite(value.get("lat"), f"{label}.lat")
    lng = finite(value.get("lng"), f"{label}.lng")
    require(-90.0 <= lat <= 90.0, f"{label}.lat is invalid")
    require(-180.0 <= lng <= 180.0, f"{label}.lng is invalid")

def edge(value, label: str) -> int:
    require(isinstance(value, dict), f"{label} must be an object")
    rank = non_negative_int(value.get("correlationRank"), f"{label}.correlationRank")
    positive_int(value.get("graphId"), f"{label}.graphId")
    positive_int(value.get("opposingGraphId"), f"{label}.opposingGraphId")
    positive_int(value.get("sourceNodeGraphId"), f"{label}.sourceNodeGraphId")
    positive_int(value.get("endNodeGraphId"), f"{label}.endNodeGraphId")
    positive_int(value.get("wayId"), f"{label}.wayId")
    coordinate(value.get("correlatedCoordinate"), f"{label}.correlatedCoordinate")

    percent = finite(value.get("percentAlong"), f"{label}.percentAlong")
    require(0.0 <= percent <= 1.0, f"{label}.percentAlong is invalid")
    distance = finite(value.get("distanceMeters"), f"{label}.distanceMeters")
    require(distance >= 0.0, f"{label}.distanceMeters is invalid")
    heading = finite(value.get("headingDegrees"), f"{label}.headingDegrees")
    require(0.0 <= heading <= 360.0, f"{label}.headingDegrees is invalid")

    non_negative_int(value.get("inboundReach"), f"{label}.inboundReach")
    non_negative_int(value.get("outboundReach"), f"{label}.outboundReach")
    non_negative_int(value.get("forwardAccess"), f"{label}.forwardAccess")
    non_negative_int(value.get("reverseAccess"), f"{label}.reverseAccess")
    non_negative_int(value.get("roadClass"), f"{label}.roadClass")
    non_negative_int(value.get("use"), f"{label}.use")

    for key in ("roadNames", "roadRefs"):
        items = value.get(key)
        require(isinstance(items, list), f"{label}.{key} must be an array")
        require(len(items) == len(set(items)), f"{label}.{key} contains duplicates")
        require(all(isinstance(item, str) and item.strip() for item in items), f"{label}.{key} contains an invalid value")
    return rank

def binding(value, expected_region: str, expected_fingerprint: str, label: str) -> None:
    require(isinstance(value, dict), f"{label} must be an object")
    require(value.get("regionId") == expected_region, f"{label}.regionId mismatch")
    require(value.get("graphFingerprint") == expected_fingerprint, f"{label}.graphFingerprint mismatch")
    coordinate(value.get("proofCoordinate"), f"{label}.proofCoordinate")
    candidates = value.get("candidates")
    require(isinstance(candidates, list) and candidates, f"{label}.candidates must be non-empty")
    ranks = [edge(candidate, f"{label}.candidates[{index}]") for index, candidate in enumerate(candidates)]
    require(len(ranks) == len(set(ranks)), f"{label}.candidates has duplicate Loki ranks")

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--from-graph-fingerprint")
    parser.add_argument("--to-graph-fingerprint")
    args = parser.parse_args()

    path = Path(args.artifact)
    artifact = json.loads(path.read_text(encoding="utf-8"))

    require(artifact.get("schema") == "roadpilot.bound-cross-graph-transitions", "unexpected artifact schema")
    require(artifact.get("version") == 1, "artifact version must be 1")

    from_region = str(artifact.get("fromRegionId") or "")
    to_region = str(artifact.get("toRegionId") or "")
    from_fingerprint = str(artifact.get("fromGraphFingerprint") or "")
    to_fingerprint = str(artifact.get("toGraphFingerprint") or "")
    mode = str(artifact.get("bindingMode") or "")

    require(from_region and to_region and from_region != to_region, "invalid region pair")
    require(from_fingerprint and to_fingerprint, "graph fingerprints are required")
    require(mode in MODES, "invalid bindingMode")

    if args.from_graph_fingerprint is not None:
        require(from_fingerprint == args.from_graph_fingerprint, "from graph fingerprint mismatch")
    if args.to_graph_fingerprint is not None:
        require(to_fingerprint == args.to_graph_fingerprint, "to graph fingerprint mismatch")

    generator = artifact.get("generator")
    require(isinstance(generator, dict), "generator is required")
    require(bool(str(generator.get("name") or "").strip()), "generator.name is required")
    require(bool(str(generator.get("version") or "").strip()), "generator.version is required")

    transitions = artifact.get("transitions")
    require(isinstance(transitions, list) and transitions, "transitions must be non-empty")

    proof_ids = []
    for index, transition in enumerate(transitions):
        label = f"transition[{index}]"
        require(isinstance(transition, dict), f"{label} must be an object")
        proof_id = str(transition.get("sourceProofId") or "")
        require(PROOF_ID.fullmatch(proof_id) is not None, f"{label}.sourceProofId is invalid")
        proof_ids.append(proof_id)
        binding(transition.get("fromBinding"), from_region, from_fingerprint, f"{label}.fromBinding")
        binding(transition.get("toBinding"), to_region, to_fingerprint, f"{label}.toBinding")

    require(len(proof_ids) == len(set(proof_ids)), "sourceProofId values must be unique")
    print(
        f"{path}: valid bound transition artifact "
        f"{from_region} -> {to_region}, mode={mode}, transitions={len(transitions)}"
    )

if __name__ == "__main__":
    main()
