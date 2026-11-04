#!/usr/bin/env python3
"""Read-only exhaustive graph-local terminal topology census for retained F8 overlap.

Audits every directed GraphId from the complete native overlap window scans,
including candidates that have no car/motorcycle forward access. Records
every graph-local endpoint; never collapses names, ways, ramps, lanes or
GraphIds. A terminal is NOT by itself the unique last edge of a *physical*
road, a validated inter-graph transfer or an Android F8 parity result.
"""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

from build_native_f8_pair_evidence import pair_identity, source_scans, window_catalog
from capture_native_f8_graph_windows import overlap_windows, read, positive_window_degrees
from native_f8_inputs import graph_manifest_info, load_polygon
from probe_native_f8_clipped_terminal import verified_buffer, _at
from probe_native_f8_journey import verify_retained_graph_identity
from verify_native_f8_receiver_adjacency import AUTO_ACCESS, MOTORCYCLE_ACCESS

MODES = {"auto": AUTO_ACCESS, "motorcycle": MOTORCYCLE_ACCESS}
SCHEMA = "roadpilot.f8-native-full-graph-local-terminal-census"
MAX_OUTGOING = 256


def verify_binary(path: Path, expected: str) -> str:
    if not isinstance(expected, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", expected):
        raise ValueError("Explicit SHA-256 pin is required before native execution")
    if path.is_symlink() or not path.is_file():
        raise ValueError("Native executable missing or symlink")
    with path.open("rb") as stream:
        h = sha256()
        for chunk in iter(lambda: stream.read(1024*1024), b""):
            h.update(chunk)
        actual = "sha256:" + h.hexdigest()
    if actual != expected:
        raise ValueError("Native endpoint executable hash mismatch; not executed")
    result = subprocess.run([str(path), "--version"], capture_output=True,
                            text=True, timeout=15, check=False)
    if result.returncode or result.stdout.strip() != "3.6.3":
        raise ValueError("Native endpoint executable version is not Valhalla 3.6.3")
    return actual


def verify_window_coverage(scan: dict, other: dict, from_buffer: Path,
                           to_buffer: Path, width: float = .025) -> int:
    expected = tuple(tuple(bounds.values()) for bounds in overlap_windows(
        load_polygon(from_buffer), load_polygon(to_buffer), width))
    actual = window_catalog(scan)
    if actual != window_catalog(other) or actual != expected:
        raise ValueError("Original scans do not cover the complete verified overlap window grid")
    return len(expected)


def validate_row(source: dict, row: dict) -> dict:
    """Validate every native adjacency, including shortcut/nonroad alternatives."""
    if not isinstance(row, dict):
        raise ValueError("Invalid native topology row")
    for key, native_key in (("sourceGraphId", "graphId"),
                            ("wayId", "wayId"),
                            ("forwardAccess", "forwardAccess"),
                            ("reverseAccess", "reverseAccess")):
        if row.get(key) != source.get(native_key):
            raise ValueError(f"Original scan/native topology disagreement: {key}")
    for key in ("endNodeGraphId", "opposingGraphId"):
        if type(row.get(key)) is not int or row[key] <= 0:
            raise ValueError(f"Missing native {key}")
    for key in ("deadend", "notThru", "forward"):
        if type(row.get(key)) is not bool:
            raise ValueError(f"Malformed native {key}")
    degree = row.get("nativeOutgoingDegree")
    outgoing = row.get("outgoingDirectedEdges")
    if (type(degree) is not int or not 1 <= degree <= MAX_OUTGOING
            or not isinstance(outgoing, list) or len(outgoing) != degree):
        raise ValueError("Missing/truncated native outgoing edge inventory")
    seen = set()
    for item in outgoing:
        if not isinstance(item, dict):
            raise ValueError("Malformed native outgoing entry")
        gid, mask = item.get("graphId"), item.get("forwardAccess")
        if (type(gid) is not int or gid <= 0 or gid in seen
                or type(item.get("endNodeGraphId")) is not int
                or item["endNodeGraphId"] <= 0
                or type(mask) is not int or not 0 <= mask < 2**32):
            raise ValueError("Duplicate or incomplete native outgoing identity")
        seen.add(gid)
        for name in ("isRoad", "isShortcut", "autoBit", "motorcycleBit"):
            if type(item.get(name)) is not bool:
                raise ValueError("Malformed native outgoing access flags")
        if item["autoBit"] != bool(mask & AUTO_ACCESS) or (
                item["motorcycleBit"] != bool(mask & MOTORCYCLE_ACCESS)):
            raise ValueError("Native outgoing access flag mismatch")
    if row["opposingGraphId"] not in seen:
        raise ValueError("Graph-native opposing edge omitted from outgoing evidence")
    for key, limit in (("endLat", 90), ("endLon", 180)):
        value = row.get(key)
        if type(value) not in (int, float) or not -limit <= value <= limit:
            raise ValueError("Malformed native endpoint position")
    return row


def audit_rows(edges: list[dict], rows, peer_buffer: dict) -> dict:
    """Streaming, strict ordered 1:1 inventory; no sampling and no edge dedup."""
    counts = Counter()
    terminals = {"auto": [], "motorcycle": []}
    # Capture the previously omitted exact identities of graph-local
    # mode-stranded, nondeadend edges. Counts alone silently omit possible
    # mode-specific final edges; keep all original directed GraphIds.
    mode_stranded = {"auto": [], "motorcycle": []}
    source_digest = sha256()
    consumed = 0
    rows = iter(rows)
    seen_ids = set()
    for expected, raw in zip(edges, rows):
        if not raw.endswith("\n"):
            raise ValueError("Incomplete native JSON line")
        source_digest.update(raw.encode("utf-8"))
        row = validate_row(expected, json.loads(raw))
        if row["sourceGraphId"] in seen_ids:
            raise ValueError("Repeated native directed GraphId in complete census")
        seen_ids.add(row["sourceGraphId"])
        consumed += 1
        counts["nativeDirectedEdgesAudited"] += 1
        if row["deadend"]:
            counts["nativeDeadends"] += 1
        reverse = row["opposingGraphId"]
        for mode, bit in MODES.items():
            if not row["forwardAccess"] & bit:
                continue
            counts[f"{mode}ForwardUsableEdges"] += 1
            continuations = [
                item["graphId"] for item in row["outgoingDirectedEdges"]
                if item["graphId"] != reverse and item["forwardAccess"] & bit]
            if not continuations and not row["deadend"]:
                counts[f"{mode}ModeStrandedNondeadend"] += 1
                mode_stranded[mode].append({
                    "graphId": row["sourceGraphId"],
                    "endNodeGraphId": row["endNodeGraphId"],
                    "wayIdAnnotationOnly": row["wayId"],
                    "endLat": row["endLat"],
                    "endLon": row["endLon"],
                    "insidePeerBuffer": peer_buffer["polygon"].covers(
                        _at({"lat": row["endLat"], "lng": row["endLon"]})),
                    "nativeOutgoingDegree": row["nativeOutgoingDegree"],
                    "terminalStatus": "NATIVE_MODE_STRANDED_NONDEADEND_ONLY",
                })
            if not (row["deadend"] and not continuations):
                continue
            inside_peer = peer_buffer["polygon"].covers(
                _at({"lat": row["endLat"], "lng": row["endLon"]}))
            counts[f"{mode}GraphLocalFinalDirectedEdges"] += 1
            if inside_peer:
                counts[f"{mode}FinalInsidePeerBuffer"] += 1
            # Report ALL terminal edges, including ones outside peer buffer.
            # Polygon checks are annotations, never source eligibility filters.
            terminals[mode].append({
                "graphId": row["sourceGraphId"],
                "endNodeGraphId": row["endNodeGraphId"],
                "wayIdAnnotationOnly": row["wayId"],
                "endLat": row["endLat"],
                "endLon": row["endLon"],
                "insidePeerBuffer": inside_peer,
                "terminalStatus": "NATIVE_GRAPH_LOCAL_MODE_TERMINAL_ONLY",
            })
    if consumed != len(edges):
        raise ValueError(f"Native topology incomplete: {consumed} / {len(edges)}")
    # Detect extra native rows after the entire expected scan was consumed.
    if next(rows, None) is not None:
        raise ValueError("Native topology emitted extra edges")
    for mode in MODES:
        ids = [item["graphId"] for item in terminals[mode]]
        stranded_ids = [item["graphId"] for item in mode_stranded[mode]]
        if len(ids) != len(set(ids)) or len(stranded_ids) != len(set(stranded_ids)):
            raise ValueError("Repeated terminal/stranded GraphId for one mode")
        if set(ids) & set(stranded_ids):
            raise ValueError("Mode-stranded nondeadend cannot be a deadend terminal")
        if len(stranded_ids) != counts[f"{mode}ModeStrandedNondeadend"]:
            raise ValueError("Stranded native ID coverage incomplete")
    return {"counts": dict(sorted(counts.items())),
            "nativeTopologyJsonlSha256": "sha256:" + source_digest.hexdigest(),
            "allGraphLocalModeTerminals": terminals,
            "allGraphLocalModeStrandedNondeadends": mode_stranded,
            "modeStrandedNativeIdCoverage": "ALL_MODE_STRANDED_NATIVE_IDS_RETAINED",
            "edgeCoverage": "ALL_SOURCE_NATIVE_SCAN_IDS_RECONCILED",
            "physicalRoadUniqueFinalEdge": "NOT_VERIFIED",
            "originalRouteProofForAllTerminals": "NOT_VERIFIED",
            "androidJNIParity": "NOT_VERIFIED",
            "productionPublication": "BLOCKED"}


def audit_side(binary: Path, config: Path, edges: list[dict],
               peer_buffer: dict, temp: Path) -> dict:
    ordered = sorted(edges, key=lambda e: e["graphId"])
    ids = temp / "all-ids.txt"
    with ids.open("w", encoding="ascii") as fd:
        for edge in ordered:
            fd.write(str(edge["graphId"]) + "\n")
    stderr = temp / "native-errors.txt"
    with stderr.open("w+", encoding="utf-8") as errors:
        with subprocess.Popen(
            [str(binary), str(config), str(ids), "--continuations"],
            stdout=subprocess.PIPE, stderr=errors, text=True, bufsize=1024*1024,
        ) as child:
            try:
                result = audit_rows(ordered, child.stdout, peer_buffer)
            except BaseException:
                child.kill()
                child.wait()
                raise
            rc = child.wait(timeout=900)
        if rc:
            errors.seek(0)
            raise ValueError("Native graph-local census failed; discard all partial evidence: "
                             + errors.read()[-250:])
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("pair", "from-manifest", "to-manifest", "from-buffer",
                 "to-buffer", "from-native-scan", "to-native-scan",
                 "native-summary", "native-endpoints-binary", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--expected-native-endpoints-sha256", required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Immutable census report already exists")
    def digest_file(path: Path) -> str:
        h = sha256()
        with path.open("rb") as fd:
            for block in iter(lambda: fd.read(1024 * 1024), b""):
                h.update(block)
        return "sha256:" + h.hexdigest()

    original_inputs = {str(p): digest_file(p) for p in (args.from_native_scan,
        args.to_native_scan, args.native_summary, args.from_buffer, args.to_buffer)}
    pair = read(args.pair)
    pair_identity(pair)
    summary = read(args.native_summary)
    a, b, provenance = source_scans(
        pair, from_scan=read(args.from_native_scan),
        to_scan=read(args.to_native_scan), scan_summary=summary)
    from_manifest, to_manifest = read(args.from_manifest), read(args.to_manifest)
    own = verified_buffer(args.from_buffer, from_manifest)
    peer = verified_buffer(args.to_buffer, to_manifest)
    width = positive_window_degrees(summary.get("defaultWindowDegrees", 0))
    windows = verify_window_coverage(a, b, args.from_buffer, args.to_buffer, width)
    binary_sha = verify_binary(
        args.native_endpoints_binary, args.expected_native_endpoints_sha256)
    with tempfile.TemporaryDirectory(prefix="f8-native-full-census-") as folder:
        temp = Path(folder)
        first, first_cfg = graph_manifest_info(
            args.from_manifest, pair["fromRegionId"],
            to_manifest["source"]["primaryGeofabrikId"],
            pair["fromBoundaryFingerprint"], temp, "A")
        second, second_cfg = graph_manifest_info(
            args.to_manifest, pair["toRegionId"],
            from_manifest["source"]["primaryGeofabrikId"],
            pair["toBoundaryFingerprint"], temp, "B")
        verify_retained_graph_identity(pair, first, second)
        from_result = audit_side(args.native_endpoints_binary, first_cfg, a["edges"], peer, temp)
        print(f"from: reconciled {len(a['edges'])} native directed edges", flush=True)
        to_result = audit_side(args.native_endpoints_binary, second_cfg, b["edges"], own, temp)
        print(f"to: reconciled {len(b['edges'])} native directed edges", flush=True)
    for side, manifest_path, manifest in (
            ("from", args.from_manifest, from_manifest),
            ("to", args.to_manifest, to_manifest)):
        archive = (manifest_path.parent / manifest["artifact"]["fileName"])
        if digest_file(archive) != pair[side + "GraphFingerprint"]:
            raise ValueError(f"{side} immutable native graph archive changed during census")
    if any(digest_file(Path(path)) != digest for path, digest in original_inputs.items()):
        raise ValueError("Source scan/summary/buffer changed during full census")
    if digest_file(args.native_endpoints_binary) != binary_sha:
        raise ValueError("Native binary changed during full census")
    from_source_sha = original_inputs[str(args.from_native_scan)]
    to_source_sha = original_inputs[str(args.to_native_scan)]
    doc = {
        "schema": SCHEMA, "version": 1, "pairId": pair["pairId"],
        "fromGraphFingerprint": pair["fromGraphFingerprint"],
        "toGraphFingerprint": pair["toGraphFingerprint"],
        "fromBoundaryFingerprint": pair["fromBoundaryFingerprint"],
        "toBoundaryFingerprint": pair["toBoundaryFingerprint"],
        "fromBufferSha256": own["sha256"], "toBufferSha256": peer["sha256"],
        "nativeEndpointsSha256": binary_sha,
        "sourceScanSHA256": {"from": from_source_sha, "to": to_source_sha},
        "sourceScanProvenance": provenance,
        "verifiedCompleteOverlapWindows": windows,
        "windowDegrees": width,
        "directions": {"from-to": from_result, "to-from": to_result},
        "nativeTopologyCoverage": "ALL_RETAINED_NATIVE_SCAN_EDGES",
        "globalOneFinalRetainedEdgePerPhysicalRoadDirection": "NOT_VERIFIED",
        "reason": ("Native GraphIds prove graph-local mode terminals, not an independently "
                   "established physical-road-to-edge equivalence relation. No same-way/name "
                   "grouping or geometry pre-filter has been introduced."),
        "androidActualSameGraphJNIScanParity": "NOT_VERIFIED",
        "productionPublication": "BLOCKED",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=args.output.parent,
            prefix=".f8-full-native-census-", delete=False) as fd:
        stage = Path(fd.name)
        json.dump(doc, fd, indent=2, allow_nan=False)
        fd.write("\n")
    try:
        os.link(stage, args.output)
    finally:
        stage.unlink(missing_ok=True)
    print("Census complete for every retained native source edge. "
          "Physical-road uniqueness and Android JNI parity remain NOT_VERIFIED.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as error:
        raise SystemExit("F8_FULL_NATIVE_CENSUS_ERROR: " + str(error)[:360])
