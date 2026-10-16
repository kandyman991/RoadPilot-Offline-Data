#!/usr/bin/env python3
"""Produce an uncapped, graph-bound F8-like directed edge inventory (NOT F8 parity).

Read-only native Valhalla GraphReader, separate from Android's JNI scanner.
Uses existing retained graph packages/configs. No PBF download, .gph changes,
first-success stopping, route inference, or "F8 parity verified" assertion.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Iterator

from shapely.geometry import box

from native_f8_inputs import load_polygon, graph_manifest_info

SCHEMA = "roadpilot.native-f8-edge-scan"
PORT = "GraphStudio.nativeUncappedRoadEdges"
WINDOW_SCHEMA = "roadpilot.graph-studio-native-edge-window"


def obj(value: Any, label: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def read(path: Path) -> dict:
    return obj(json.loads(path.read_text(encoding="utf-8")), str(path))


def scanner_version(binary: Path) -> str:
    """Read the Valhalla version baked into the C++ exporter at compile time."""
    if not binary.is_file():
        raise ValueError(f"Native scanner binary does not exist: {binary}")
    try:
        result = subprocess.run([str(binary), "--version"], text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=15, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError(f"Cannot inspect native scanner version: {exc}") from exc
    version = result.stdout.strip()
    if result.returncode != 0 or not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("Native scanner version missing or invalid; rebuild with matching libvalhalla")
    return version


def require_compatible_versions(from_manifest: dict, to_manifest: dict,
                                native_version: str) -> None:
    """No attempt to read real graph tiles using an incompatible ABI/version."""
    if not re.fullmatch(r"\d+\.\d+\.\d+", native_version):
        raise ValueError("Native scanner did not report a valid Valhalla version")
    for label, manifest in (("from", from_manifest), ("to", to_manifest)):
        version = manifest.get("valhallaVersion")
        if not isinstance(version, str) or version != native_version:
            raise ValueError(
                f"{label} retained graph Valhalla version {version!r} does not match "
                f"native scanner build {native_version!r}"
            )


def sha256_binary(binary: Path) -> str:
    digest = hashlib.sha256()
    with binary.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def positive_window_degrees(value: float) -> float:
    if not math.isfinite(value) or not 0.001 <= value <= 0.25:
        raise ValueError("window-degrees must be between 0.001 and 0.25")
    return value


def overlap_windows(from_shape: Any, to_shape: Any, degrees: float) -> Iterator[dict[str, float]]:
    """Cover the entire shared buffer, including distinct highway carriageways.

    A window is included for any positive-area overlap. Exported node positions
    may lie outside the exact shared polygon but inside a scan rectangle; this
    conservative overcount is reported, never treated as parity evidence.
    """
    degree = positive_window_degrees(degrees)
    shared = from_shape.intersection(to_shape)
    if shared.is_empty or shared.area <= 0:
        raise ValueError("Retained graph buffer polygons have no area overlap")
    min_lng, min_lat, max_lng, max_lat = shared.bounds
    lo_x, hi_x = math.floor(min_lng / degree), math.ceil(max_lng / degree)
    lo_y, hi_y = math.floor(min_lat / degree), math.ceil(max_lat / degree)
    for y in range(lo_y, hi_y):
        for x in range(lo_x, hi_x):
            west, east = x * degree, (x + 1) * degree
            south, north = y * degree, (y + 1) * degree
            if shared.intersection(box(west, south, east, north)).area > 0:
                yield {"minLat": south, "maxLat": north,
                       "minLon": west, "maxLon": east}


def scan_window(executable: Path, config: Path, bbox: dict[str, float],
                expected_version: str | None = None) -> dict:
    cmd = [str(executable), str(config),
           repr(bbox["minLat"]), repr(bbox["maxLat"]),
           repr(bbox["minLon"]), repr(bbox["maxLon"])]
    result = subprocess.run(cmd, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"Read-only Valhalla scan failed ({result.returncode}): "
                           + result.stderr[-2500:])
    payload = obj(json.loads(result.stdout), "native graph scan")
    if payload.get("schema") != WINDOW_SCHEMA or payload.get("version") != 1:
        raise ValueError("Unsupported native Graph Studio window schema")
    if payload.get("scanner") != PORT:
        raise ValueError("Native Graph Studio scanner identity mismatch")
    window_version = payload.get("valhallaVersion")
    if not isinstance(window_version, str) or not re.fullmatch(r"\d+\.\d+\.\d+", window_version):
        raise ValueError("Native graph scan did not attest its compiled Valhalla version")
    if expected_version is not None and window_version != expected_version:
        raise ValueError("Native window binary version changed after preflight")
    edges = payload.get("edges")
    if not isinstance(edges, list) or payload.get("returned") != len(edges):
        raise ValueError("Native Graph Studio window count mismatch")
    if (payload.get("complete") is not True or payload.get("truncated") is not False
            or payload.get("maxResults") is not None):
        raise ValueError("Uncapped native exporter reported a truncated/limited window")
    if (isinstance(payload.get("visitedTiles"), bool)
            or not isinstance(payload.get("visitedTiles"), int)
            or payload["visitedTiles"] < 0):
        raise ValueError("Native exporter missing visitedTiles evidence")
    seen = set()
    for edge in edges:
        item = obj(edge, "native edge")
        graph_id = item.get("graphId")
        if isinstance(graph_id, bool) or not isinstance(graph_id, int) or graph_id <= 0:
            raise ValueError("Native edge has invalid directed graphId")
        if graph_id in seen:
            raise ValueError("Duplicate directed edge in one native window")
        seen.add(graph_id)
    return payload


def capture_side(executable: Path, config: Path,
                 windows: list[dict[str, float]], label: str,
                 expected_version: str | None = None) -> dict:
    by_graph_id: dict[int, dict] = {}
    manifest = []
    complete = True
    for i, bbox in enumerate(windows):
        result = scan_window(executable, config, bbox, expected_version)
        for edge in result["edges"]:
            by_graph_id[edge["graphId"]] = edge
        window_complete = result["visitedTiles"] > 0
        complete = complete and window_complete
        manifest.append({**bbox, "index": i, "complete": window_complete,
                         "truncated": False, "maxResults": None,
                         "returned": result["returned"],
                         "visitedTiles": result["visitedTiles"],
                         "visitedNodes": result["visitedNodes"]})
        if i % 25 == 0 or i == len(windows) - 1:
            print(f"{label}: scanned {i+1}/{len(windows)} windows, "
                  f"{len(by_graph_id)} distinct graph edges", flush=True)
    return {"complete": complete and bool(manifest), "windows": manifest,
            "edges": [by_graph_id[key] for key in sorted(by_graph_id)]}


def make_capture(*, pair_manifest: dict, graph_identity_a: dict,
                 graph_identity_b: dict, from_scan: dict, to_scan: dict,
                 window_degrees: float, scanner_build: dict | None = None) -> dict:
    """Bind native scan to a source-only, UNPROVEN pair identity."""
    if pair_manifest.get("schema") != "roadpilot.cross-region-connectivity":
        raise ValueError("Expected fingerprint-bound cross-region pair manifest")
    if pair_manifest.get("validationState") != "UNPROVEN":
        raise ValueError("Native capture requires an unproven identity-only pair")
    for prefix, identity in (("from", graph_identity_a), ("to", graph_identity_b)):
        for field, own in (("RegionId", "regionId"),
                           ("PackageVersion", "packageVersion"),
                           ("GraphFingerprint", "graphFingerprint")):
            if pair_manifest.get(prefix + field) != identity.get(own):
                raise ValueError(f"Stale {prefix}{field} before capture")
    if pair_manifest.get("pairId") != (
            f"{graph_identity_a['regionId']}__{graph_identity_b['regionId']}"):
        raise ValueError("Native pairId disagrees with regional graph identities")
    if (pair_manifest.get("fromBoundarySourceId") != graph_identity_b["primaryGeofabrikId"]
            or pair_manifest.get("toBoundarySourceId") != graph_identity_a["primaryGeofabrikId"]):
        raise ValueError("Native pair source identities mismatch")
    for field in ("fromBoundaryFingerprint", "toBoundaryFingerprint"):
        if not isinstance(pair_manifest.get(field), str) or not pair_manifest[field].startswith("sha256:"):
            raise ValueError(f"Native pair is missing {field}")
    return {
        "schema": SCHEMA, "version": 1,
        "scanner": PORT,
        "derivedFrom": "RoadPilot GraphEndpointNative.scanBoundaryRoadEdges filter predicates",
        "nativeF8ReferenceCaptured": False,
        "f8GraphEdgeParity": "NOT_VERIFIED",
        "pairId": pair_manifest["pairId"],
        "fromGraph": graph_identity_a,
        "toGraph": graph_identity_b,
        "fromBoundaryFingerprint": pair_manifest["fromBoundaryFingerprint"],
        "toBoundaryFingerprint": pair_manifest["toBoundaryFingerprint"],
        "scans": {"from": from_scan, "to": to_scan},
        "windowDegrees": window_degrees,
        "scannerBuild": scanner_build or {"validation": "NOT_RUN"},
        "provenHandoffs": [],
        "knownGaps": [
            "This is an independent, uncapped Graph Studio port, not Android's F8 JNI output.",
            "Windows cover shared graph buffer bounding rectangles; extra candidate edges are expected.",
            "Native F8-backed travel-mode and direction proofs are not captured by this tool.",
            "F8 parity stays NOT_VERIFIED until same-graph Android reference comparison.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pair-manifest", required=True, type=Path)
    parser.add_argument("--from-manifest", required=True, type=Path)
    parser.add_argument("--to-manifest", required=True, type=Path)
    parser.add_argument("--from-buffer", required=True, type=Path)
    parser.add_argument("--to-buffer", required=True, type=Path)
    parser.add_argument("--scanner-binary", required=True, type=Path)
    parser.add_argument("--window-degrees", type=float, default=0.025)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    pair_manifest = read(args.pair_manifest)
    if pair_manifest.get("schema") != "roadpilot.cross-region-connectivity":
        parser.error("Provide an identity-only cross-region pair manifest")
    from_manifest, to_manifest = read(args.from_manifest), read(args.to_manifest)
    native_version = scanner_version(args.scanner_binary)
    require_compatible_versions(from_manifest, to_manifest, native_version)
    native_binary_sha = sha256_binary(args.scanner_binary)
    from_primary = obj(from_manifest.get("source"), "from source").get("primaryGeofabrikId")
    to_primary = obj(to_manifest.get("source"), "to source").get("primaryGeofabrikId")
    if not isinstance(from_primary, str) or not isinstance(to_primary, str):
        parser.error("Retained manifests lack primary Geofabrik identities")
    windows = list(overlap_windows(load_polygon(args.from_buffer),
                                   load_polygon(args.to_buffer),
                                   args.window_degrees))
    if not windows:
        parser.error("No windows intersect the buffered graph overlap")
    print(f"{pair_manifest['pairId']}: {len(windows)} windows per independent graph")
    with tempfile.TemporaryDirectory(prefix="graph-studio-native-f8-") as tmp:
        root = Path(tmp)
        identity_a, config_a = graph_manifest_info(
            args.from_manifest, pair_manifest["fromRegionId"], to_primary,
            pair_manifest["fromBoundaryFingerprint"], root, "from")
        identity_b, config_b = graph_manifest_info(
            args.to_manifest, pair_manifest["toRegionId"], from_primary,
            pair_manifest["toBoundaryFingerprint"], root, "to")
        from_scan = capture_side(args.scanner_binary, config_a, windows, "from", native_version)
        to_scan = capture_side(args.scanner_binary, config_b, windows, "to", native_version)
        if sha256_binary(args.scanner_binary) != native_binary_sha:
            raise ValueError("Native scanner binary changed during graph capture")
        output = make_capture(pair_manifest=pair_manifest, graph_identity_a=identity_a,
                              graph_identity_b=identity_b, from_scan=from_scan,
                              to_scan=to_scan, window_degrees=args.window_degrees,
                              scanner_build={"compiledValhallaVersion": native_version,
                                             "binarySha256": native_binary_sha,
                                             "validation": "VERSION_MATCHED_NOT_F8_PARITY"})
        args.output.parent.mkdir(parents=True, exist_ok=True)
        # Stage on the destination filesystem. /tmp may be tmpfs while retained
        # user maps/evidence live on an external drive: cross-device os.replace
        # fails after expensive full scans if staging uses /tmp.
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=args.output.parent,
            prefix=".f8-capture-", suffix=".json", delete=False,
        ) as handle:
            staged = Path(handle.name)
            try:
                json.dump(output, handle, indent=2)
                handle.write("\n")
            except BaseException:
                staged.unlink(missing_ok=True)
                raise
        try:
            os.replace(staged, args.output)
        finally:
            staged.unlink(missing_ok=True)
    print(f"Uncapped graph evidence: {args.output}; Android F8 parity NOT_VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
