#!/usr/bin/env python3
"""Generate production cross-graph transition artifacts for one directional graph pair.

The two Valhalla graphs are already finished and independently fingerprinted before this runs.
This command:
  1. derives continuous shared-frontier scan windows from Geofabrik geometry;
  2. exports every motorized DirectedEdge from both graphs in that corridor;
  3. creates exhaustive directional edge-pair candidates;
  4. asks the native Thor probe to prove each candidate for each travel mode;
  5. promotes only accepted proofs into RoadPilot's runtime bound-transition schema.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {relative_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


frontier = load_module("frontier", "tools/build_shared_frontier_windows.py")
candidates = load_module(
    "candidates", "tools/build_routing_transition_candidates.py"
)
compiler = load_module(
    "compiler", "tools/compile_bound_routing_transitions.py"
)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def run(command: list[str]) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, check=True)


def safe_pair_name(pair_config: dict[str, Any]) -> str:
    return (
        f"{pair_config['fromRegionId']}__{pair_config['toRegionId']}"
        .replace("/", "_")
        .replace(" ", "_")
    )


def generate_direction(
    *,
    pair_config_path: Path,
    from_inventory_path: Path,
    to_inventory_path: Path,
    from_config: Path,
    to_config: Path,
    transition_probe: Path,
    output_dir: Path,
    modes: list[str],
) -> list[Path]:
    pair_config = load_json(pair_config_path)
    from_inventory = load_json(from_inventory_path)
    to_inventory = load_json(to_inventory_path)
    pair_name = safe_pair_name(pair_config)

    candidate_catalog = candidates.build_candidates(
        from_inventory, to_inventory, pair_config
    )
    candidates.verify_regression_anchors(candidate_catalog, pair_config)
    candidate_path = output_dir / f"{pair_name}-candidates.json"
    write_json(candidate_path, candidate_catalog)
    run(
        [
            sys.executable,
            str(ROOT / "tools/validate_routing_transition_candidates.py"),
            "--catalog",
            str(candidate_path),
        ]
    )

    outputs: list[Path] = []
    for mode in modes:
        proof_path = output_dir / f"{pair_name}-{mode.lower()}-proofs.json"
        run(
            [
                str(transition_probe),
                "--from-config",
                str(from_config),
                "--to-config",
                str(to_config),
                "--candidates",
                str(candidate_path),
                "--mode",
                mode,
                "--output",
                str(proof_path),
            ]
        )

        proof_results = load_json(proof_path)
        bound = compiler.compile_artifact(proof_results, mode)
        bound_path = output_dir / f"{pair_name}-{mode.lower()}-bound-v1.json"
        write_json(bound_path, bound)

        run(
            [
                sys.executable,
                str(ROOT / "tools/validate_bound_routing_transitions.py"),
                "--artifact",
                str(bound_path),
            ]
        )
        outputs.append(bound_path)

    return outputs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--geofabrik-index", required=True, type=Path)
    parser.add_argument("--forward-pair-config", required=True, type=Path)
    parser.add_argument("--reverse-pair-config", required=True, type=Path)
    parser.add_argument("--from-valhalla-config", required=True, type=Path)
    parser.add_argument("--to-valhalla-config", required=True, type=Path)
    parser.add_argument("--from-fingerprint", required=True)
    parser.add_argument("--to-fingerprint", required=True)
    parser.add_argument("--boundary-inventory", required=True, type=Path)
    parser.add_argument("--transition-probe", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument(
        "--modes",
        nargs="+",
        default=["MOTORCYCLE", "CAR"],
        choices=["MOTORCYCLE", "CAR"],
    )
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    index = load_json(args.geofabrik_index)
    forward_config = load_json(args.forward_pair_config)
    reverse_config = load_json(args.reverse_pair_config)

    if (
        forward_config["fromRegionId"] != reverse_config["toRegionId"]
        or forward_config["toRegionId"] != reverse_config["fromRegionId"]
    ):
        raise ValueError("forward and reverse configs do not describe opposite directions")

    window_document = frontier.build_windows(index, forward_config)
    windows_path = args.output_dir / "shared-frontier-windows.json"
    write_json(windows_path, window_document)

    from_inventory_path = (
        args.output_dir / f"{forward_config['fromRegionId']}-boundary-inventory.json"
    )
    to_inventory_path = (
        args.output_dir / f"{forward_config['toRegionId']}-boundary-inventory.json"
    )

    run(
        [
            str(args.boundary_inventory),
            "--config",
            str(args.from_valhalla_config),
            "--region-id",
            forward_config["fromRegionId"],
            "--fingerprint",
            args.from_fingerprint,
            "--windows",
            str(windows_path),
            "--output",
            str(from_inventory_path),
        ]
    )
    run(
        [
            str(args.boundary_inventory),
            "--config",
            str(args.to_valhalla_config),
            "--region-id",
            forward_config["toRegionId"],
            "--fingerprint",
            args.to_fingerprint,
            "--windows",
            str(windows_path),
            "--output",
            str(to_inventory_path),
        ]
    )

    for inventory_path in (from_inventory_path, to_inventory_path):
        run(
            [
                sys.executable,
                str(ROOT / "tools/validate_boundary_edge_inventory.py"),
                "--inventory",
                str(inventory_path),
            ]
        )

    outputs = []
    outputs.extend(
        generate_direction(
            pair_config_path=args.forward_pair_config,
            from_inventory_path=from_inventory_path,
            to_inventory_path=to_inventory_path,
            from_config=args.from_valhalla_config,
            to_config=args.to_valhalla_config,
            transition_probe=args.transition_probe,
            output_dir=args.output_dir,
            modes=args.modes,
        )
    )
    outputs.extend(
        generate_direction(
            pair_config_path=args.reverse_pair_config,
            from_inventory_path=to_inventory_path,
            to_inventory_path=from_inventory_path,
            from_config=args.to_valhalla_config,
            to_config=args.from_valhalla_config,
            transition_probe=args.transition_probe,
            output_dir=args.output_dir,
            modes=args.modes,
        )
    )

    manifest = {
        "schema": "roadpilot.routing-transition-package-set",
        "version": 1,
        "graphFingerprints": {
            forward_config["fromRegionId"]: args.from_fingerprint,
            forward_config["toRegionId"]: args.to_fingerprint,
        },
        "artifacts": [path.name for path in outputs],
    }
    write_json(args.output_dir / "transition-package-set.json", manifest)

    print("Generated production transition artifacts:")
    for path in outputs:
        print(f"  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
