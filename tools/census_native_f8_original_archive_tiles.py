#!/usr/bin/env python3
"""Archive-wide source GraphReader tile/edge audit, not a handoff producer.

Enumerates *every* original source archive tile and edge (native C++), then
verifies all geometry candidates close to the source's own 25-km buffer cut.
All modes, ramps, branches, level transitions, ferry and shortcut identities
stay separate. No receiving graph matching or physical-road deduplication.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import threading

from shapely.geometry import LineString, Point, shape

from build_native_f8_pair_evidence import pair_identity
from native_f8_inputs import graph_manifest_info
from probe_native_f8_clipped_terminal import CRS, verified_buffer
from probe_native_f8_journey import verify_retained_graph_identity

SCHEMA = "roadpilot.f8-all-original-source-archive-tile-cut-census"
VERSION = 1
NATIVE_VALHALLA_VERSION = "3.6.3"
MAX_NATIVE_ROW_CHARS = 4_000_000
NATIVE_TIMEOUT_SECONDS = 2400
BOUNDARY_MARGIN_DEGREES = 0.05
MAX_GEO_VERTICES = 32768
MODE_BITS = {"auto": 1, "motorcycle": 1024}
class NonSpatialOriginalDirectedGeometry(ValueError):
    """A native directed GraphId exists, but its actual decoded shape is zero-length."""




def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def original_geojson_polygon(path: Path):
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("type") == "Feature":
        geom = shape(raw["geometry"])
    elif raw.get("type") == "FeatureCollection":
        from shapely.ops import unary_union
        geom = unary_union([shape(f["geometry"]) for f in raw.get("features", [])])
    else:
        geom = shape(raw)
    if not geom.is_valid or geom.is_empty or geom.geom_type not in ("Polygon", "MultiPolygon"):
        raise ValueError("Original SHA-verified geographic buffer polygon invalid")
    return geom


def rectangles_from_original_buffer(polygon) -> list[tuple[float, float, float, float]]:
    """Conservative per-boundary-segment bounding envelopes, NEVER road cuts."""
    boundary = polygon.boundary
    lines = boundary.geoms if hasattr(boundary, "geoms") else [boundary]
    output = []
    for line in lines:
        coords = list(line.coords)
        for a, b in zip(coords, coords[1:]):
            if any(not math.isfinite(v) for v in (*a, *b)):
                raise ValueError("Nonfinite original buffer polygon")
            margin = BOUNDARY_MARGIN_DEGREES
            bounds = (max(-180, min(a[0], b[0])-margin),
                      max(-90, min(a[1], b[1])-margin),
                      min(180, max(a[0], b[0])+margin),
                      min(90, max(a[1], b[1])+margin))
            if bounds[0] >= bounds[2] or bounds[1] >= bounds[3]:
                raise ValueError("Invalid boundary segment rectangle")
            output.append(bounds)
    if not 1 <= len(output) <= 20000:
        raise ValueError("Original boundary segments absent or excessive")
    return output


def serialize_rectangles(rectangles) -> bytes:
    return "".join("%.11f %.11f %.11f %.11f\n" % box
                   for box in rectangles).encode("ascii")


def integer(value, label: str, *, zero: bool = True) -> int:
    if type(value) is not int or value < (0 if zero else 1):
        raise ValueError("Invalid original " + label)
    return value


def source_cut_observation(row: dict, original_buffer: dict) -> dict | None:
    """Exact transformed native directed shape; never selects or dedups roads."""
    coords = row.get("directedGeometry")
    if not isinstance(coords, list) or not 2 <= len(coords) <= MAX_GEO_VERTICES:
        raise ValueError("Original native candidate geometry missing/truncated")
    latlon = []
    for item in coords:
        if (not isinstance(item, list) or len(item) != 2
                or any(type(v) not in (int, float) or not math.isfinite(v)
                       for v in item)
                or abs(item[0]) > 90 or abs(item[1]) > 180):
            raise ValueError("Invalid original native geometry coordinate")
        latlon.append(item)
    points = [CRS.transform(lon, lat) for lat, lon in latlon]
    geom = LineString(points)
    if geom.is_empty or geom.length <= 0:
        raise NonSpatialOriginalDirectedGeometry(
            "Native original directed GraphId " + str(row["originalDirectedGraphId"]) +
            " has zero-length geometry; preserve exact ID as unresolved")
    if not geom.is_valid:
        raise ValueError("Original native directed shape is malformed")
    boundary = original_buffer["polygon"].boundary
    if not geom.intersects(boundary):
        return None
    polygon = original_buffer["polygon"]
    first = polygon.covers(Point(points[0]))
    last = polygon.covers(Point(points[-1]))
    status = ("OUTWARD_FROM_ORIGINAL_SOURCE_BUFFER" if first and not last
              else "INWARD_TOWARD_ORIGINAL_SOURCE_BUFFER" if last and not first
              else "BOTH_ENDPOINTS_WITHIN_BUFFER_CUT_INTERSECTION" if first and last
              else "BOTH_ENDPOINTS_OUTSIDE_BUFFER_CUT_INTERSECTION")
    return {
        "originalDirectedGraphId": row["originalDirectedGraphId"],
        "originalEndNodeGraphId": row["originalEndNodeGraphId"],
        "nativeForwardAccess": row["forwardAccess"],
        "nativeReverseAccess": row["reverseAccess"],
        "nativeIsRoad": row["isRoad"],
        "nativeIsShortcut": row["isShortcut"],
        "nativeDeadend": row["deadend"],
        "originalWayIdAnnotationOnly": row["wayIdAnnotationOnly"],
        "originalDirectedShapeSha256": "sha256:" + hashlib.sha256(
            json.dumps(latlon, separators=(",", ":"), allow_nan=False).encode()
        ).hexdigest(),
        "originalSourceBufferCutDirectedTravel": status,
        "nativeDirectedStartInsideOwnBuffer": first,
        "nativeDirectedEndInsideOwnBuffer": last,
        "vehicleModes": {m: bool(row["forwardAccess"] & bit)
                         for m, bit in MODE_BITS.items()},
        "physicalRoadDirectionLastEdge": "NOT_VERIFIED",
        "candidateSuppressed": False,
    }


def audit_stream(lines, source_buffer: dict) -> dict:
    """Fail-closed ordered tile+candidate ledger with implicit FULL GraphId ranges."""
    tiles: list[dict] = []
    seen: set[int] = set()
    hits = []
    nonspatial = []
    total_edges = total_bbox = 0
    current_id = None
    pending_count = 0
    previous_edge_index = -1
    classes = Counter()
    after_summary = False
    record_count = 0
    summary = None
    for raw in lines:
        if after_summary:
            raise ValueError("Original GraphReader emitted trailing archive records")
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        if len(raw) > MAX_NATIVE_ROW_CHARS or not raw.endswith("\n"):
            raise ValueError("Original archive-native JSON line oversized/truncated")
        row = json.loads(raw)
        record_count += 1
        if not isinstance(row, dict):
            raise ValueError("Malformed archive-native ledger")
        kind = row.get("type")
        if kind == "candidate":
            base = integer(row.get("tileGraphId"), "tile GraphId")
            gid = integer(row.get("originalDirectedGraphId"), "directed GraphId")
            index = gid >> 25
            if (base != (gid & ((1 << 25)-1)) or index <= previous_edge_index
                    or (current_id is not None and base != current_id)
                    or (tiles and base <= tiles[-1]["tileGraphId"])):
                raise ValueError("Original directed GraphId does not match its tile/index")
            current_id = base
            pending_count += 1
            previous_edge_index = index
            for field in ("originalEndNodeGraphId", "forwardAccess",
                          "reverseAccess", "wayIdAnnotationOnly"):
                integer(row.get(field), field)
            for field in ("isRoad", "isShortcut", "deadend"):
                if type(row.get(field)) is not bool:
                    raise ValueError("Incomplete original directed native classification")
            try:
                observation = source_cut_observation(row, source_buffer)
            except NonSpatialOriginalDirectedGeometry:
                nonspatial.append({
                    "originalDirectedGraphId": gid,
                    "tileGraphId": base,
                    "nativeEndNodeGraphId": row["originalEndNodeGraphId"],
                    "nativeForwardAccess": row["forwardAccess"],
                    "nativeIsRoad": row["isRoad"],
                    "nativeIsShortcut": row["isShortcut"],
                    "originalWayIdAnnotationOnly": row["wayIdAnnotationOnly"],
                    "geometryCutIntersection": "UNRESOLVED_NATIVE_ZERO_LENGTH",
                    "candidateSuppressed": False,
                })
                observation = None
            if observation is not None:
                hits.append(observation)
                classes[observation["originalSourceBufferCutDirectedTravel"]] += 1
        elif kind == "tile":
            base = integer(row.get("tileGraphId"), "tile GraphId")
            level = integer(row.get("level"), "tile level")
            tile_id = integer(row.get("tileId"), "tile numeric ID")
            count = integer(row.get("originalDirectedCount"), "tile directed count")
            got = integer(row.get("bboxCandidateCount"), "tile bbox candidate count")
            node_count = integer(row.get("nodeCount"), "tile node count")
            if (level >= 8 or tile_id >= (1 << 22)
                    or base != (level | (tile_id << 3))
                    or base in seen or (tiles and base <= tiles[-1]["tileGraphId"])
                    or got != pending_count or got > count
                    or (current_id is not None and current_id != base)
                    or (got and previous_edge_index >= count)):
                raise ValueError("Original archive tile inventory incomplete or contradictory")
            tiles.append({
                "tileGraphId": base, "hierarchyLevel": level,
                "nativeTileId": tile_id, "nodeCount": node_count,
                "originalDirectedCount": count,
                "geometryEnvelopeCandidateCount": got,
            })
            seen.add(base)
            total_edges += count
            total_bbox += got
            pending_count = 0
            previous_edge_index = -1
            current_id = None
        elif kind == "summary":
            if current_id is not None or pending_count:
                raise ValueError("Original directed archive tile data missing terminal header")
            if row.get("valhallaVersion") != NATIVE_VALHALLA_VERSION:
                raise ValueError("Original Valhalla version mismatch")
            if (integer(row.get("archiveTileCount"), "archive tile count") != len(tiles)
                    or integer(row.get("allOriginalDirectedCount"), "directed total") != total_edges
                    or integer(row.get("bboxCandidateCount"), "bbox count") != total_bbox
                    or not tiles or total_edges == 0):
                raise ValueError("Native GraphReader archive totals disagree with complete tile ledger")
            summary = row
            after_summary = True
        else:
            raise ValueError("Unrecognized original native archive record")
    if not after_summary or summary is None:
        raise ValueError("Original archive-wide GraphReader did not finish all tiles")
    return {
        "archiveTileCount": len(tiles),
        "allOriginalDirectedEdgesEnumerated": total_edges,
        "originalGeometryBoundaryEnvelopeCandidates": total_bbox,
        "originalDirectedCutShapeCount": len(hits),
        "unresolvedOriginalNativeZeroLengthGeometryCount": len(nonspatial),
        "unresolvedOriginalNativeZeroLengthGeometries": nonspatial,
        "originalSourceBufferDirectionalCutClassifications": dict(sorted(classes.items())),
        "originalArchiveTiles": tiles,
        "allOriginalDirectedCutObservations": hits,
        "tileEdgeInventoryProof": "ALL_GRAPHREADER_GETTILESET_DIRECTED_INDEX_RANGES",
        "originalNativeGeometryFilter": "CONSERVATIVE_ORIGINAL_BUFFER_BOUNDARY_RECTANGLES",
        "physicalRoadDirectionFinalEdge": "NOT_VERIFIED",
        "crossGraphMatching": "NOT_STARTED",
        "noSourceDirectedRoadSuppressedByNameWayOrMode": True,
    }


def run_native(binary: Path, config: Path, rectangles: Path, original_buffer: dict,
               stderr_path: Path) -> dict:
    with stderr_path.open("w+", encoding="utf-8") as errors:
        with subprocess.Popen(
            [str(binary), str(config), "--boundary-rectangles", str(rectangles)],
            stdout=subprocess.PIPE, stderr=errors, text=True, bufsize=65536,
        ) as child:
            timeout_hit = [False]
            def terminate() -> None:
                timeout_hit[0] = True
                child.kill()
            watchdog = threading.Timer(NATIVE_TIMEOUT_SECONDS, terminate)
            watchdog.daemon = True
            watchdog.start()
            try:
                def checked_lines():
                    while True:
                        raw = child.stdout.readline(MAX_NATIVE_ROW_CHARS + 1)
                        if not raw:
                            break
                        yield raw
                result = audit_stream(checked_lines(), original_buffer)
                exit_code = child.wait(timeout=90)
                if exit_code or timeout_hit[0]:
                    errors.seek(0)
                    raise ValueError("Native full archive scan failed: " + errors.read()[-300:])
                return result
            except BaseException:
                child.kill()
                child.wait()
                raise
            finally:
                watchdog.cancel()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ("pair", "from-manifest", "to-manifest", "from-buffer",
                 "to-buffer", "native-binary", "output"):
        ap.add_argument("--" + name, required=True, type=Path)
    ap.add_argument("--expected-native-binary-sha256", required=True)
    args = ap.parse_args()
    if args.output.exists() or args.output.is_symlink():
        raise ValueError("Refusing to overwrite immutable archive-wide source census")
    files = {x: getattr(args, x.replace("-", "_")) for x in (
        "pair", "from-manifest", "to-manifest", "from-buffer",
        "to-buffer", "native-binary")}
    start_sha = {name: sha(path) for name, path in files.items()}
    if args.expected_native_binary_sha256 != start_sha["native-binary"]:
        raise ValueError("Unpinned native original Valhalla executable identity")
    version = subprocess.run([str(args.native_binary), "--version"],
                             capture_output=True, text=True, check=True, timeout=30)
    if version.stdout.strip() != NATIVE_VALHALLA_VERSION:
        raise ValueError("Native Valhalla binary is not 3.6.3")
    pair = json.loads(args.pair.read_text(encoding="utf-8"))
    pair_identity(pair)
    first_manifest = json.loads(args.from_manifest.read_text())
    second_manifest = json.loads(args.to_manifest.read_text())
    original_a = verified_buffer(args.from_buffer, first_manifest)
    original_b = verified_buffer(args.to_buffer, second_manifest)
    with tempfile.TemporaryDirectory(prefix="f8-original-archive-tiles-") as folder:
        temp = Path(folder)
        ma, cfg_a = graph_manifest_info(
            args.from_manifest, pair["fromRegionId"],
            second_manifest["source"]["primaryGeofabrikId"],
            pair["fromBoundaryFingerprint"], temp, "A")
        mb, cfg_b = graph_manifest_info(
            args.to_manifest, pair["toRegionId"],
            first_manifest["source"]["primaryGeofabrikId"],
            pair["toBoundaryFingerprint"], temp, "B")
        verify_retained_graph_identity(pair, ma, mb)
        outputs = {}
        rectangle_checksums = {}
        for side, buffer_path, verified, config in (
            ("from-to", args.from_buffer, original_a, cfg_a),
            ("to-from", args.to_buffer, original_b, cfg_b),
        ):
            polygon = original_geojson_polygon(buffer_path)
            rectangle_path = temp / (side + "-source-boundary-rectangles.txt")
            rectangle_path.write_bytes(
                serialize_rectangles(rectangles_from_original_buffer(polygon)))
            rectangle_checksums[side] = sha(rectangle_path)
            data = run_native(args.native_binary, config, rectangle_path, verified,
                              temp / (side + "-native-stderr.log"))
            data["originalBoundaryRectangleSHA256"] = rectangle_checksums[side]
            data["originalBufferGeoJSONSHA256"] = verified["sha256"]
            outputs[side] = data
            print(side, "native archive tiles", data["archiveTileCount"],
                  "directed IDs", data["allOriginalDirectedEdgesEnumerated"],
                  "cut directed observations", data["originalDirectedCutShapeCount"],
                  "zero-length unresolved", data["unresolvedOriginalNativeZeroLengthGeometryCount"],
                  flush=True)
    for side, manifest, document in (
        ("from", args.from_manifest, first_manifest),
        ("to", args.to_manifest, second_manifest),
    ):
        original_archive = manifest.parent / document["artifact"]["fileName"]
        if sha(original_archive) != pair[side+"GraphFingerprint"]:
            raise ValueError("Original graph archive changed during native inventory")
    if any(sha(file) != start_sha[name] for name, file in files.items()):
        raise ValueError("Native original source inputs modified during archive inventory")
    result = {
        "schema": SCHEMA, "version": VERSION,
        "pairId": pair["pairId"],
        "sourceGraphFingerprints": {
            "from": pair["fromGraphFingerprint"], "to": pair["toGraphFingerprint"]},
        "immutableOriginalSourceSHA256": start_sha,
        "originalGraphArchiveTileInventory": "ALL_GRAPHREADER_GETTILESET_TILES_ENUMERATED",
        "directions": outputs,
        "allPhysicalRoadDirectionFinalDirectedEdgeUniqueness": "NOT_VERIFIED",
        "receivingGraphCorrelation": "NOT_STARTED",
        "productionPublication": "BLOCKED",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    stage = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False,
                                         prefix=".f8-archive-original-", dir=args.output.parent) as fd:
            stage = Path(fd.name)
            json.dump(result, fd, indent=2, allow_nan=False)
            fd.write("\n")
        if args.output.exists() or args.output.is_symlink():
            raise ValueError("Concurrent original full archive census report")
        os.link(stage, args.output)
    finally:
        if stage:
            stage.unlink(missing_ok=True)
    print("ARCHIVE-WIDE ORIGINAL DIRECTED TILE/EDGE INVENTORY VERIFIED;"
          " PHYSICAL ROAD FINAL UNIQUENESS NOT_VERIFIED; publication BLOCKED.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, TypeError, KeyError, IndexError,
            subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise SystemExit("F8_ORIGINAL_ARCHIVE_CENSUS_ERROR: " + str(exc)[:400])
