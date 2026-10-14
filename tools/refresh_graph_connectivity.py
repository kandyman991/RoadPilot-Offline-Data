#!/usr/bin/env python3
"""Produce F8-derived connectivity for already-built neighboring Valhalla graphs.

No .gph mutation, source downloads, graph rebuilds, or hard-coded border portals.
Pair products become visible only after all discovery, Valhalla proof and schema
validation stages succeed. Previously published metadata is never overwritten
with unproven candidates. This is a local build-time operation, not Android F8.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

SAFE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")


def fail(message: str) -> None:
    raise RuntimeError(message)


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        fail(f"Expected JSON object: {path}")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(part)
    return "sha256:" + digest.hexdigest()


@dataclass(frozen=True)
class Graph:
    region: str
    manifest_path: Path
    fingerprint: str
    primary: str
    boundaries: dict[str, str]

    @classmethod
    def from_manifest(cls, path: Path) -> "Graph":
        data = read_json(path)
        region = data.get("regionId")
        if not isinstance(region, str) or not SAFE.fullmatch(region):
            fail(f"Invalid graph region: {path}")
        if data.get("schema") != "roadpilot-routing-pack":
            fail(f"Not a routing manifest: {path}")
        if path.parent.name != region:
            fail(f"Routing manifest in wrong region directory: {path}")
        source = data.get("source") or {}
        index = data.get("graphIndex") or {}
        boundaries = index.get("boundaryFingerprints") or {}
        if not isinstance(boundaries, dict):
            fail(f"Invalid boundary fingerprints: {path}")
        fingerprint = data.get("graphFingerprint")
        primary = source.get("primaryGeofabrikId")
        if not isinstance(fingerprint, str) or not fingerprint.startswith("sha256:"):
            fail(f"Missing graph fingerprint: {path}")
        if not isinstance(primary, str) or not primary:
            fail(f"Missing primary source: {path}")
        index_file = index.get("fileName")
        if not isinstance(index_file, str) or Path(index_file).name != index_file:
            fail(f"Missing safe graph index file: {path}")
        if not (path.parent / index_file).is_file():
            fail(f"Graph index unavailable for {path}")
        return cls(region, path, fingerprint, primary, boundaries)


def latest_graphs(dist: Path) -> dict[str, Graph]:
    """Choose latest retained build per region, never an arbitrary glob hit."""
    graphs: dict[str, Graph] = {}
    for path in sorted(dist.glob("*/*-manifest.json"),
                       key=lambda p: (p.stat().st_mtime_ns, str(p)), reverse=True):
        region = path.parent.name
        if region not in graphs:
            graphs[region] = Graph.from_manifest(path)
    return graphs


def discover_pairs(graphs: dict[str, Graph],
                   changed: set[str] | None = None) -> list[tuple[Graph, Graph]]:
    pairs = []
    for index, name in enumerate(sorted(graphs)):
        a = graphs[name]
        for other in sorted(graphs)[index + 1:]:
            b = graphs[other]
            if changed is not None and a.region not in changed and b.region not in changed:
                continue
            # Both graphs must really include their neighbor in the recorded
            # tile-index boundary fingerprint, not merely share a country.
            if b.primary in a.boundaries and a.primary in b.boundaries:
                pairs.append((a, b))
    return pairs


def is_current_runtime(path: Path, a: Graph, b: Graph) -> bool:
    try:
        data = read_json(path)
    except (OSError, ValueError):
        return False
    return (
        data.get("schema") == "roadpilot.runtime-connectivity"
        and data.get("validationState") == "VALIDATED"
        and data.get("pairId") == f"{a.region}__{b.region}"
        and (data.get("fromGraph") or {}).get("graphFingerprint") == a.fingerprint
        and (data.get("toGraph") or {}).get("graphFingerprint") == b.fingerprint
        and data.get("fromBoundaryFingerprint") == a.boundaries.get(b.primary)
        and data.get("toBoundaryFingerprint") == b.boundaries.get(a.primary)
        and (data.get("discovery") or {}).get("scope") == "OSM_BUFFER_OVERLAP"
        and (data.get("discovery") or {}).get("sourceExhausted") is True
        and (data.get("discovery") or {}).get("f8GraphEdgeParity") == "NOT_VERIFIED"
    )


_active: subprocess.Popen | None = None


def _terminate_children(_signal: int, _frame: object) -> None:
    global _active
    if _active is not None and _active.poll() is None:
        if os.name == "posix":
            os.killpg(_active.pid, signal.SIGTERM)
        else:
            _active.terminate()
    raise KeyboardInterrupt("Connectivity build cancelled")


def run_tool(tools: Path, name: str, *args: object, timeout: int = 7200) -> None:
    global _active
    command = [sys.executable, "-u", str(tools / (name + ".py")), *map(str, args)]
    print("connectivity stage:", name, flush=True)
    _active = subprocess.Popen(command, start_new_session=(os.name == "posix"))
    try:
        status = _active.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        if os.name == "posix":
            os.killpg(_active.pid, signal.SIGKILL)
        else:
            _active.kill()
        _active.wait()
        fail(f"Connectivity stage {name} timed out after {timeout}s")
    finally:
        _active = None
    if status != 0:
        fail(f"Connectivity stage {name} failed with exit code {status}")


STAGES = (
    ("pair", "build_connectivity_pair_manifest", "validate_cross_region_connectivity"),
    ("frontier", "build_frontier_road_inventory", "validate_frontier_road_inventory"),
    ("correlations", "correlate_frontier_roads", "validate_frontier_road_correlations"),
    ("candidates", "build_crossing_candidates", "validate_crossing_candidates"),
    ("proofs", "prove_crossing_candidates", "validate_crossing_proofs"),
    ("runtime", "compile_runtime_connectivity", "validate_runtime_connectivity"),
)


def build_pair(tools: Path, work: Path, output_root: Path,
               a: Graph, b: Graph, stage_root: Path) -> Path:
    pair_id = f"{a.region}__{b.region}"
    staged = stage_root / pair_id
    staged.mkdir(parents=True)
    paths = {name: staged / (name + ".json") for name, _, _ in STAGES}
    polygon_a = work / "cache" / (a.region + ".poly")
    polygon_b = work / "cache" / (b.region + ".poly")
    # The first graph's complete-ways, buffered OSM snapshot has actual
    # geometry on both sides of the shared nominal frontier.
    osm = work / a.region / "build" / "buffered.osm.pbf"
    osm_b = work / b.region / "build" / "buffered.osm.pbf"
    buffer_a = work / a.region / "build" / "buffer.geojson"
    buffer_b = work / b.region / "build" / "buffer.geojson"
    for path in (polygon_a, polygon_b, osm, osm_b, buffer_a, buffer_b):
        if not path.is_file():
            fail(f"{pair_id}: missing retained local input {path}; no download or rebuild attempted")

    steps: dict[str, list[object]] = {
        "pair": ["--from-manifest", a.manifest_path, "--to-manifest", b.manifest_path],
        "frontier": ["--pair-manifest", paths["pair"], "--from-polygon", polygon_a,
                     "--to-polygon", polygon_b, "--osm-source", osm,
                     "--to-osm-source", osm_b,
                     "--from-buffer-polygon", buffer_a,
                     "--to-buffer-polygon", buffer_b],
        "correlations": ["--inventory", paths["frontier"],
                         "--from-manifest", a.manifest_path, "--to-manifest", b.manifest_path],
        "candidates": ["--correlations", paths["correlations"]],
        "proofs": ["--candidates", paths["candidates"], "--inventory", paths["frontier"],
                   "--from-manifest", a.manifest_path, "--to-manifest", b.manifest_path,
                   "--from-polygon", polygon_a, "--to-polygon", polygon_b],
        "runtime": ["--candidates", paths["candidates"], "--proofs", paths["proofs"]],
    }
    for name, builder, validator in STAGES:
        run_tool(tools, builder, *steps[name], "--output", paths[name])
        switch = "--inventory" if name == "frontier" else "--artifact"
        run_tool(tools, validator, switch, paths[name])

    if not is_current_runtime(paths["runtime"], a, b):
        fail(f"{pair_id}: validated runtime does not match exact current graphs")
    # Commit the VALIDATED runtime last so interrupted processing never
    # exposes a partially generated new proof as current.
    committed = output_root / pair_id
    committed.mkdir(parents=True, exist_ok=True)
    for name, _, _ in STAGES:
        if name != "runtime":
            os.replace(paths[name], committed / (name + ".json"))
    os.replace(paths["runtime"], committed / "runtime.json")
    return committed / "runtime.json"


def build_region_matrices(tools: Path, graphs: dict[str, Graph],
                          pairs: list[tuple[Graph, Graph]], output_root: Path,
                          matrix_root: Path, stage_root: Path) -> int:
    touched = sorted({g.region for pair in pairs for g in pair})
    completed = 0
    for region in touched:
        graph = graphs[region]
        touching = [(a, b) for a, b in discover_pairs(graphs)
                    if region in (a.region, b.region)]
        runtimes = [output_root / f"{a.region}__{b.region}" / "runtime.json"
                    for a, b in touching]
        if not runtimes or any(not is_current_runtime(path, a, b)
                               for (a, b), path in zip(touching, runtimes)):
            print(f"connectivity: {region} matrices skipped (missing/stale pair proof)",
                  flush=True)
            continue

        stage = stage_root / ("region-" + region)
        stage.mkdir(parents=True)
        inventory = stage / "inventory.json"
        target_dir = matrix_root / region
        saved_inventory = target_dir / "inventory.json"
        saved_matrix = target_dir / "matrix.json"
        params: list[object] = ["--region", region]
        for runtime in runtimes:
            params.extend(["--artifact", runtime])
        run_tool(tools, "build_region_connector_inventory", *params, "--output", inventory)
        run_tool(tools, "validate_region_connector_inventory", "--artifact", inventory)
        fingerprint = sha256_file(inventory)
        # Matrix is graph-and-inventory-bound; avoid unnecessary Valhalla
        # many-to-many work when all validated connections are unchanged.
        try:
            saved = read_json(saved_matrix)
            matrix_current = (
                saved.get("sourceInventorySha256") == fingerprint
                and (saved.get("graph") or {}).get("graphFingerprint") == graph.fingerprint
                and saved_inventory.is_file()
                and sha256_file(saved_inventory) == fingerprint
            )
        except (OSError, ValueError):
            matrix_current = False
        if matrix_current:
            print(f"connectivity: {region} connector matrix CURRENT; reused", flush=True)
            completed += 1
            continue
        matrix = stage / "matrix.json"
        run_tool(tools, "build_region_connector_matrix", "--inventory", inventory,
                 "--manifest", graph.manifest_path, "--output", matrix)
        run_tool(tools, "validate_region_connector_matrix", "--artifact", matrix)
        target_dir.mkdir(parents=True, exist_ok=True)
        # Never replace the source inventory without its newly proven matrix.
        os.replace(matrix, saved_matrix)
        os.replace(inventory, saved_inventory)
        completed += 1
    return completed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist-dir", required=True, type=Path)
    parser.add_argument("--work-dir", required=True, type=Path)
    parser.add_argument("--connectivity-dir", required=True, type=Path)
    parser.add_argument("--connector-matrix-dir", required=True, type=Path)
    parser.add_argument("--changed-region", action="append", default=[])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if any(not SAFE.fullmatch(x) for x in args.changed_region):
        parser.error("Invalid changed region id")
    tools = Path(__file__).resolve().parent
    graphs = latest_graphs(args.dist_dir)
    changed = set(args.changed_region) if args.changed_region else None
    if changed and not changed <= graphs.keys():
        fail(f"Changed graph(s) missing: {sorted(changed - graphs.keys())}")
    pairs = discover_pairs(graphs, changed)
    print(f"connectivity: {len(graphs)} retained graphs, {len(pairs)} relevant adjacent pairs",
          flush=True)
    for a, b in pairs:
        print(f"connectivity pair: {a.region} ↔ {b.region}", flush=True)
    if args.dry_run or not pairs:
        return 0

    args.connectivity_dir.mkdir(parents=True, exist_ok=True)
    args.connector_matrix_dir.mkdir(parents=True, exist_ok=True)
    # Keep intermediates outside the visible connectivity artifact directories.
    with tempfile.TemporaryDirectory(prefix="connectivity-staging-",
                                      dir=args.work_dir) as temp:
        stage_root = Path(temp)
        errors = []
        for a, b in pairs:
            dest = args.connectivity_dir / f"{a.region}__{b.region}" / "runtime.json"
            if is_current_runtime(dest, a, b):
                print(f"connectivity: {a.region}__{b.region} CURRENT; reused", flush=True)
                continue
            try:
                build_pair(tools, args.work_dir, args.connectivity_dir, a, b, stage_root)
                print(f"connectivity: {a.region}__{b.region} VALIDATED", flush=True)
            except RuntimeError as error:
                errors.append(str(error))
                print(f"connectivity FAILED: {error}", file=sys.stderr, flush=True)
        try:
            matrix_count = build_region_matrices(
                tools, graphs, pairs, args.connectivity_dir,
                args.connector_matrix_dir, stage_root,
            )
            print(f"connectivity: {matrix_count} regional connector matrices current",
                  flush=True)
        except RuntimeError as error:
            errors.append(str(error))
            print(f"connectivity FAILED: {error}", file=sys.stderr, flush=True)
        if errors:
            fail(f"{len(errors)} connectivity step(s) failed; existing routing graphs remain valid")
    print("connectivity: all selected cross-region metadata validated", flush=True)
    return 0


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _terminate_children)
    signal.signal(signal.SIGINT, _terminate_children)
    try:
        raise SystemExit(main())
    except (RuntimeError, KeyboardInterrupt) as error:
        print(f"connectivity: {error}", file=sys.stderr, flush=True)
        raise SystemExit(1)
