#!/usr/bin/env python3
"""Compile exact Valhalla proof results into RoadPilot's runtime bound-transition artifact.

This tool never performs discovery and never upgrades a rejected/unproven candidate. Its input must
come from the native exact-Thor validator, which is responsible for proving direction/reachability
and for normalizing each selected DirectedEdge into the traversal direction used at runtime.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SCHEMA = "roadpilot.bound-cross-graph-transitions"
VERSION = 1
GENERATOR_NAME = "roadpilot-offline-transition-compiler"
GENERATOR_VERSION = "1"


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def e6(value: float) -> int:
    return round(float(value) * 1_000_000.0)


def physical_identity(item: dict[str, Any]) -> tuple[int, int, int, int, int, int]:
    from_binding = item["fromBinding"]
    to_binding = item["toBinding"]
    from_coordinate = from_binding["proofCoordinate"]
    to_coordinate = to_binding["proofCoordinate"]
    return (
        int(from_binding["candidates"][0]["graphId"]),
        int(to_binding["candidates"][0]["graphId"]),
        e6(from_coordinate["lat"]),
        e6(from_coordinate["lng"]),
        e6(to_coordinate["lat"]),
        e6(to_coordinate["lng"]),
    )


def require_proof_document(data: dict[str, Any]) -> None:
    if (
        data.get("schema") != "roadpilot.transition-proof-results"
        or data.get("version") != 1
    ):
        raise ValueError("unsupported transition proof result schema")
    for key in (
        "fromRegionId",
        "toRegionId",
        "fromGraphFingerprint",
        "toGraphFingerprint",
        "results",
    ):
        if key not in data:
            raise ValueError(f"proof results missing {key}")


def compile_artifact(data: dict[str, Any], mode: str) -> dict[str, Any]:
    require_proof_document(data)
    if mode not in {"MOTORCYCLE", "CAR"}:
        raise ValueError(
            "bound transition compiler currently supports MOTORCYCLE or CAR"
        )

    accepted = []
    for result in data["results"]:
        if result.get("bindingMode") != mode or not result.get("accepted"):
            continue
        if "fromBinding" not in result or "toBinding" not in result:
            raise ValueError(
                f"accepted proof {result.get('candidateId', '?')} "
                "is missing exact bindings"
            )
        accepted.append(
            {
                "sourceProofId": result["candidateId"],
                "fromBinding": result["fromBinding"],
                "toBinding": result["toBinding"],
            }
        )

    # Keep one definition per physical directed transition. Exact proof IDs remain deterministic,
    # but overlapping frontier windows can present the same pair more than once.
    by_physical: dict[
        tuple[int, int, int, int, int, int], dict[str, Any]
    ] = {}
    for item in sorted(accepted, key=lambda value: value["sourceProofId"]):
        by_physical.setdefault(physical_identity(item), item)

    transitions = sorted(
        by_physical.values(), key=lambda value: value["sourceProofId"]
    )
    if not transitions:
        raise ValueError(f"no accepted {mode} transitions were proven")

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "fromRegionId": data["fromRegionId"],
        "toRegionId": data["toRegionId"],
        "fromGraphFingerprint": data["fromGraphFingerprint"],
        "toGraphFingerprint": data["toGraphFingerprint"],
        "bindingMode": mode,
        "generator": {
            "name": GENERATOR_NAME,
            "version": GENERATOR_VERSION,
        },
        "transitions": transitions,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--proof-results", required=True, type=Path)
    parser.add_argument(
        "--mode", required=True, choices=["MOTORCYCLE", "CAR"]
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    artifact = compile_artifact(load(args.proof_results), args.mode)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(artifact, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"{artifact['fromRegionId']} -> {artifact['toRegionId']} "
        f"{args.mode}: {len(artifact['transitions'])} proven transitions"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
