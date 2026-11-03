#!/usr/bin/env python3
"""Validate RoadPilot local plain-Valhalla crossing proofs."""

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
STATES = {"PROVEN", "REJECTED", "INCONCLUSIVE"}
LEG_STATES = {"PASSED", "FAILED", "ERROR"}
SUPPORT = {
    "MOTORCYCLE_FROM_TO",
    "MOTORCYCLE_TO_FROM",
    "CAR_FROM_TO",
    "CAR_TO_FROM",
}


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


def coord(value: Any, label: str) -> None:
    require(isinstance(value, dict), f"{label} must be an object")
    require(set(value) == {"lat", "lng"}, f"{label} must contain only lat/lng")
    lat = finite(value.get("lat"), f"{label}.lat")
    lng = finite(value.get("lng"), f"{label}.lng")
    require(-90 <= lat <= 90, f"{label}.lat invalid")
    require(-180 <= lng <= 180, f"{label}.lng invalid")


def graph(value: Any, region: str, label: str) -> None:
    require(isinstance(value, dict), f"{label} must be an object")
    require(value.get("regionId") == region, f"{label}.regionId mismatch")
    require(bool(str(value.get("packageVersion") or "").strip()), f"{label}.packageVersion required")
    fp = value.get("graphFingerprint")
    require(isinstance(fp, str) and bool(SHA256.fullmatch(fp)), f"{label}.graphFingerprint invalid")
    require(bool(str(value.get("primaryGeofabrikId") or "").strip()), f"{label}.primaryGeofabrikId required")


def leg(value: Any, expected_region: str, label: str) -> bool:
    require(isinstance(value, dict), f"{label} must be an object")
    status = value.get("status")
    require(status in LEG_STATES, f"{label}.status invalid")
    require(value.get("regionId") == expected_region, f"{label}.regionId mismatch")
    coord(value.get("start"), f"{label}.start")
    coord(value.get("end"), f"{label}.end")
    require(finite(value.get("directDistanceMeters"), f"{label}.directDistanceMeters") >= 0, f"{label}.directDistanceMeters invalid")
    expected_graph_id = value.get("expectedGraphId")
    require(
        expected_graph_id is None
        or (
            isinstance(expected_graph_id, int)
            and not isinstance(expected_graph_id, bool)
            and expected_graph_id > 0
        ),
        f"{label}.expectedGraphId invalid",
    )
    endpoint_position = value.get("endpointEdgePosition")
    require(endpoint_position in {"START", "END"}, f"{label}.endpointEdgePosition invalid")
    actual_graph_id = value.get("actualEndpointGraphId")
    require(
        actual_graph_id is None
        or (
            isinstance(actual_graph_id, int)
            and not isinstance(actual_graph_id, bool)
            and actual_graph_id > 0
        ),
        f"{label}.actualEndpointGraphId invalid",
    )
    edge_matched = value.get("edgeMatched")
    require(isinstance(edge_matched, bool), f"{label}.edgeMatched must be boolean")
    require(
        edge_matched == (
            expected_graph_id is not None
            and actual_graph_id is not None
            and expected_graph_id == actual_graph_id
        ),
        f"{label}.edgeMatched mismatch",
    )
    elapsed = value.get("elapsedMs")
    require(isinstance(elapsed, int) and not isinstance(elapsed, bool) and elapsed >= 0, f"{label}.elapsedMs invalid")
    for key in ("routeLengthKm", "routeTimeSeconds"):
        item = value.get(key)
        if item is not None:
            require(finite(item, f"{label}.{key}") >= 0, f"{label}.{key} invalid")
    if status == "PASSED":
        require("error" not in value, f"{label} PASSED must not contain error")
        require(expected_graph_id is not None, f"{label} PASSED requires expectedGraphId")
        require(edge_matched, f"{label} PASSED requires exact endpoint edge match")
    else:
        require(bool(str(value.get("error") or "").strip()), f"{label} {status} requires error")
        require(not edge_matched, f"{label} {status} cannot have edgeMatched=true")
    if expected_graph_id is None:
        require(status == "ERROR", f"{label} missing graphId must be ERROR/inconclusive")
    return status == "ERROR"


def direction(value: Any, from_region: str, to_region: str, label: str) -> tuple[bool, bool]:
    require(isinstance(value, dict), f"{label} must be an object")
    require(isinstance(value.get("passed"), bool), f"{label}.passed must be boolean")
    error_a = leg(value.get("graphA"), from_region, f"{label}.graphA")
    error_b = leg(value.get("graphB"), to_region, f"{label}.graphB")
    expected_pass = value["graphA"]["status"] == "PASSED" and value["graphB"]["status"] == "PASSED"
    require(value["passed"] == expected_pass, f"{label}.passed mismatch")
    return expected_pass, error_a or error_b


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", required=True, type=Path)
    args = parser.parse_args()

    data = json.loads(args.artifact.read_text(encoding="utf-8"))
    require(isinstance(data, dict), "artifact must be an object")
    require(data.get("schema") == "roadpilot.crossing-proofs", "unexpected schema")
    require(data.get("version") == 1, "version must be 1")

    from_region = str(data.get("fromRegionId") or "")
    to_region = str(data.get("toRegionId") or "")
    require(from_region and to_region and from_region != to_region, "invalid region pair")
    require(data.get("pairId") == f"{from_region}__{to_region}", "pairId mismatch")
    for key in ("fromBoundaryFingerprint", "toBoundaryFingerprint"):
        fp = data.get(key)
        require(isinstance(fp, str) and bool(SHA256.fullmatch(fp)), f"{key} invalid")
    graph(data.get("fromGraph"), from_region, "fromGraph")
    graph(data.get("toGraph"), to_region, "toGraph")

    generator = data.get("generator")
    require(isinstance(generator, dict), "generator must be an object")
    require(bool(str(generator.get("name") or "").strip()), "generator.name required")
    require(bool(str(generator.get("version") or "").strip()), "generator.version required")

    counts = {}
    for key in (
        "sourceCandidateCount",
        "provenCandidateCount",
        "rejectedCandidateCount",
        "inconclusiveCandidateCount",
    ):
        value = data.get(key)
        require(isinstance(value, int) and not isinstance(value, bool) and value >= 0, f"{key} invalid")
        counts[key] = value

    proofs = data.get("proofs")
    require(isinstance(proofs, list), "proofs must be an array")
    require(len(proofs) == counts["sourceCandidateCount"], "sourceCandidateCount mismatch")

    seen = set()
    actual_counts = {"PROVEN": 0, "REJECTED": 0, "INCONCLUSIVE": 0}
    for index, proof in enumerate(proofs):
        label = f"proof[{index}]"
        require(isinstance(proof, dict), f"{label} must be an object")
        cid = proof.get("candidateId")
        require(isinstance(cid, str) and bool(CANDIDATE_ID.fullmatch(cid)), f"{label}.candidateId invalid")
        require(cid not in seen, f"{label}.candidateId duplicated")
        seen.add(cid)
        fid = proof.get("frontierRoadId")
        require(isinstance(fid, str) and bool(FRONTIER_ID.fullmatch(fid)), f"{label}.frontierRoadId invalid")
        rank = proof.get("candidateRank")
        require(isinstance(rank, int) and not isinstance(rank, bool) and rank >= 0, f"{label}.candidateRank invalid")
        way = proof.get("stableWayId")
        require(isinstance(way, int) and not isinstance(way, bool) and way > 0, f"{label}.stableWayId invalid")

        state = proof.get("proofState")
        require(state in STATES, f"{label}.proofState invalid")
        actual_counts[state] += 1

        probe = proof.get("probeGeometry")
        require(isinstance(probe, dict), f"{label}.probeGeometry must be an object")
        require(probe.get("strategy") in {"REGION_INTERIOR", "FRONTIER_LONGITUDINAL"}, f"{label}.probeGeometry.strategy invalid")
        coord(probe.get("fromProbe"), f"{label}.probeGeometry.fromProbe")
        coord(probe.get("toProbe"), f"{label}.probeGeometry.toProbe")
        require(finite(probe.get("fromProbeDistanceMeters"), f"{label}.fromProbeDistanceMeters") >= 1, f"{label}.fromProbeDistanceMeters too short")
        require(finite(probe.get("toProbeDistanceMeters"), f"{label}.toProbeDistanceMeters") >= 1, f"{label}.toProbeDistanceMeters too short")

        supported = proof.get("supportedDirections")
        require(isinstance(supported, list), f"{label}.supportedDirections must be an array")
        require(all(item in SUPPORT for item in supported), f"{label}.supportedDirections invalid")
        require(len(supported) == len(set(supported)), f"{label}.supportedDirections duplicates")

        modes = proof.get("modes")
        require(isinstance(modes, dict) and set(modes) == {"MOTORCYCLE", "CAR"}, f"{label}.modes invalid")
        expected_support = []
        any_error = False
        for mode in ("MOTORCYCLE", "CAR"):
            mode_value = modes[mode]
            require(isinstance(mode_value, dict) and set(mode_value) == {"fromTo", "toFrom"}, f"{label}.modes.{mode} invalid")
            passed, errored = direction(mode_value["fromTo"], from_region, to_region, f"{label}.modes.{mode}.fromTo")
            if passed:
                expected_support.append(f"{mode}_FROM_TO")
            any_error = any_error or errored
            passed, errored = direction(mode_value["toFrom"], from_region, to_region, f"{label}.modes.{mode}.toFrom")
            if passed:
                expected_support.append(f"{mode}_TO_FROM")
            any_error = any_error or errored

        require(supported == expected_support, f"{label}.supportedDirections mismatch")
        expected_state = "PROVEN" if expected_support else ("INCONCLUSIVE" if any_error else "REJECTED")
        require(state == expected_state, f"{label}.proofState mismatch")

    require(actual_counts["PROVEN"] == counts["provenCandidateCount"], "provenCandidateCount mismatch")
    require(actual_counts["REJECTED"] == counts["rejectedCandidateCount"], "rejectedCandidateCount mismatch")
    require(actual_counts["INCONCLUSIVE"] == counts["inconclusiveCandidateCount"], "inconclusiveCandidateCount mismatch")

    print(
        f"valid crossing proofs: {data['pairId']} "
        f"(proven={actual_counts['PROVEN']} rejected={actual_counts['REJECTED']} "
        f"inconclusive={actual_counts['INCONCLUSIVE']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
