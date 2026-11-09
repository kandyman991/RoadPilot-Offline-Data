#!/usr/bin/env python3
"""Region-independent F8 original source graph boundary reader (D-017).

This is the source-identification stage, NOT an Android handoff publisher.
It examines only actual buffered-cut tiles (+ immediate tile neighbours),
keeps native mode-terminal edges, and leaves physical-forward junction cases
unresolved until the original receiving graph is correlated. No historical
ledger, named road, guessed GPS point, route probe, or full archive edge scan.
"""
from __future__ import annotations

import argparse
import gzip
import math
import shutil
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

from shapely.geometry import box, shape, mapping, MultiLineString, Point, LineString

SCHEMA = "roadpilot.f8-region-original-boundary-source"
NATIVE_PROTOCOL = "roadpilot.f8-native-source-8"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def expected_sha256(raw: str) -> str:
    value = raw.removeprefix("sha256:")
    if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError("Malformed SHA-256 fingerprint")
    return value


def require_fingerprint(path: Path, claimed: str) -> None:
    if sha256(path) != expected_sha256(claimed):
        raise ValueError(f"Immutable build input changed: {path.name}")


def select_cut_tiles(graph_index: dict, buffered: dict, *, shared_cut=None) -> list[dict]:
    """Pick tile-index entries intersecting the actual outer 25km cutoff.

    Include one immediate native neighbour ring at each hierarchy level so
    an edge originating on the inside of a tile boundary is not omitted.
    Never enumerate the entire graph or derive tile IDs from region names.
    """
    if graph_index.get("schema") != "roadpilot-graph-index":
        raise ValueError("Missing original compiled graph index")
    geo = shape(buffered.get("geometry") if buffered.get("type") == "Feature" else buffered)
    if geo.is_empty or not geo.is_valid or geo.geom_type not in {"Polygon", "MultiPolygon"}:
        raise ValueError("Invalid original buffered footprint")
    outline = geo.boundary if shared_cut is None else shared_cut
    if outline.is_empty or not outline.is_valid:
        raise ValueError("No valid shared original 25-km cutoff geometry")
    indexed: dict[tuple[int, int], dict] = {}
    selected: set[tuple[int, int]] = set()
    widths: dict[int, int] = {}
    for tile in graph_index["tiles"]:
        level = int(tile["level"])
        number = int(tile["tileIndex"])
        bounds = tile["bounds"]
        width = float(bounds["maxLng"]) - float(bounds["minLng"])
        if not width > 0:
            raise ValueError("Bad original tile bounding box")
        lon_columns = round(360 / width)
        if not 1 <= lon_columns <= 10000:
            raise ValueError("Bad tile hierarchy size")
        if level in widths and widths[level] != lon_columns:
            raise ValueError("Mixed tile sizes at a single Valhalla hierarchy level")
        widths[level] = lon_columns
        key = level, number
        if key in indexed:
            raise ValueError("Duplicated compiled graph tile index")
        indexed[key] = tile
        bounds_box = box(bounds["minLng"], bounds["minLat"],
                         bounds["maxLng"], bounds["maxLat"])
        if outline.intersects(bounds_box):
            selected.add(key)
    if not selected:
        raise ValueError("No compiled graph tile touches its recorded buffer cutoff")
    expanded = set(selected)
    for level, number in selected:
        columns = widths[level]
        row, col = divmod(number, columns)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                next_row = row + dy
                next_col = col + dx
                if 0 <= next_col < columns and next_row >= 0:
                    peer = (level, next_row * columns + next_col)
                    if peer in indexed:
                        expanded.add(peer)
    if len(expanded) >= len(indexed) and len(indexed) > 30:
        # This may be a valid small or coastal region, but it is not
        # sufficient evidence that an all-tile scan is forbidden here:
        # the spatial selector still did not blindly enumerate graph tiles.
        pass
    return [indexed[key] for key in sorted(expanded)]


def region_input(manifest: Path, graph_index: Path, buffer_geojson: Path) -> tuple[dict, list[dict]]:
    m = load_json(manifest)
    idx = load_json(graph_index)
    cut = load_json(buffer_geojson)
    if m.get("schema") != "roadpilot-routing-pack" or not m.get("regionId"):
        raise ValueError("Unrecognized regional routing manifest")
    if idx.get("regionId") != m["regionId"] or idx.get("packageVersion") != m.get("packageVersion"):
        raise ValueError("Original routing manifest/index region or version mismatch")
    if float(m["source"]["borderBufferKm"]) != 25.0:
        raise ValueError("D-017 requires the retained original 25-km overlap")
    if float(cut.get("properties", {}).get("borderBufferKm", -1)) != 25.0:
        raise ValueError("Original buffer geometry and manifest disagree")
    require_fingerprint(graph_index, m["graphIndex"]["sha256"])
    require_fingerprint(buffer_geojson, m["source"]["bufferGeoJsonSha256"])
    archive_name = m["artifact"]["fileName"]
    if Path(archive_name).name != archive_name:
        raise ValueError("Graph archive filename must not contain a directory")
    archive = manifest.parent / archive_name
    require_fingerprint(archive, m["graphFingerprint"])
    if expected_sha256(m["artifact"]["sha256"]) != expected_sha256(m["graphFingerprint"]):
        raise ValueError("Source graph archive fingerprint mismatch")
    selected = select_cut_tiles(idx, cut)
    return m, selected



def verified_shared_cut(*, source_manifest: Path, source_index: Path,
                        source_buffer: Path, receiver_manifest: Path,
                        receiver_index: Path, receiver_buffer: Path):
    """Identify ONLY A's actual outer cutoff inside B's retained footprint.

    Both graph archives, indexes and original 25-km GeoJSON footprints are
    SHA-verified. Reciprocal boundary entries must identify the same neighbor
    pair. This is a *pair-scoped source selector*, not a receiving road match:
    only B's compiled directed geometry at X can prove the same physical road.
    """
    a, _ = region_input(source_manifest, source_index, source_buffer)
    b, _ = region_input(receiver_manifest, receiver_index, receiver_buffer)
    if a["regionId"] == b["regionId"]:
        raise ValueError("Source/receiving region must be different")
    a_primary = a.get("source", {}).get("primaryGeofabrikId")
    b_primary = b.get("source", {}).get("primaryGeofabrikId")
    if not a_primary or not b_primary or a_primary == b_primary:
        raise ValueError("Missing distinct regional source identities")
    a_index = load_json(source_index)
    b_index = load_json(receiver_index)
    def reciprocal(index, other_primary):
        rows = [x for x in index.get("boundaries", [])
                if x.get("sourceId") == other_primary]
        if (len(rows) != 1 or not isinstance(rows[0].get("fingerprint"), str)
                or not rows[0]["fingerprint"].startswith("sha256:")
                or len(expected_sha256(rows[0]["fingerprint"])) != 64):
            raise ValueError("Missing reciprocal original compiled boundary identity")
        return rows[0]["fingerprint"]
    a_peer = reciprocal(a_index, b_primary)
    b_peer = reciprocal(b_index, a_primary)
    from_poly = shape(load_json(source_buffer)["geometry"])
    to_poly = shape(load_json(receiver_buffer)["geometry"])
    raw = from_poly.boundary.intersection(to_poly)
    def nonempty_lines(geom):
        if geom.geom_type == "LineString":
            return [geom] if geom.length > 0 else []
        if geom.geom_type in ("MultiLineString", "GeometryCollection"):
            return [segment for part in geom.geoms for segment in nonempty_lines(part)]
        return []
    lines = nonempty_lines(raw)
    if not lines:
        raise ValueError("Original neighboring region buffers have no shared source cutoff")
    shared = MultiLineString([list(line.coords) for line in lines])
    # A line entering B's recorded buffered geometry indicates potential B
    # graph coverage, NOT the presence of an actual B road; this remains
    # an explicit physical-match acceptance gate.
    return {
        "geometry": shared,
        "source": a,
        "receiver": b,
        "reciprocalBoundaryFingerprints": {"from": a_peer, "to": b_peer},
        "sourceBufferFingerprint": "sha256:" + sha256(source_buffer),
        "receiverBufferFingerprint": "sha256:" + sha256(receiver_buffer),
        "sourceIndexFingerprint": "sha256:" + sha256(source_index),
        "receiverIndexFingerprint": "sha256:" + sha256(receiver_index),
        "selectedSourceTiles": select_cut_tiles(a_index,
            load_json(source_buffer), shared_cut=shared),
        "receiverTilesTouchingSharedCut": select_cut_tiles(b_index,
            load_json(receiver_buffer), shared_cut=shared),
    }

def validate_directed_approach(entry: dict) -> None:
    """The native tangent must point INTO the original terminal coordinate X.

    Coordinates are evidence, not proof of the receiving physical road. A
    missing/degenerate native geometry must never be silently fabricated.
    """
    if type(entry.get("hasNativeApproachTangent")) is not bool:
        raise ValueError("Native edge missing directed-geometry capability")
    end = (entry.get("endLat"), entry.get("endLon"))
    if any(type(v) not in (float, int) or not math.isfinite(v) for v in end):
        raise ValueError("Invalid original directed edge endpoint")
    if not (-90 <= end[0] <= 90 and -180 <= end[1] <= 180):
        raise ValueError("Out-of-range native endpoint")
    tangent = (entry.get("approachLat"), entry.get("approachLon"))
    if not entry["hasNativeApproachTangent"]:
        if tangent != (None, None):
            raise ValueError("Degenerate native shape must not invent a tangent")
        return
    if any(type(v) not in (float, int) or not math.isfinite(v) for v in tangent):
        raise ValueError("Invalid native approach tangent")
    if not (-90 <= tangent[0] <= 90 and -180 <= tangent[1] <= 180):
        raise ValueError("Out-of-range native approach tangent")
    if abs(tangent[0] - end[0]) <= 1e-8 and abs(tangent[1] - end[1]) <= 1e-8:
        raise ValueError("Native approach tangent collapses to the terminal node")


def require_native_protocol(binary: Path, version: str) -> None:
    for flag, expected in (("--version", version), ("--protocol", NATIVE_PROTOCOL)):
        result = subprocess.run([str(binary), flag], check=True, capture_output=True,
                                text=True, timeout=30)
        if result.stdout.strip() != expected:
            raise ValueError(f"Native Valhalla/protocol mismatch: {flag}")


NATIVE_COSTING_STATUSES = frozenset({
    "ALLOWED_NATIVE_IMMEDIATE", "DENIED_NATIVE_IMMEDIATE",
    "NO_MODE_ACCESS", "UNRESOLVED_SHORTCUT",
    "UNRESOLVED_HIERARCHY_CONTEXT", "UNRESOLVED_PATH_OR_TIME_CONTEXT",
})


def validate_immediate_native_observation(record: dict) -> None:
    """Validate one native node/hierarchy lookup; NEVER infer road identity.

    No heading thresholds, straightest-road selection, recursive traversal
    or route probes. Every outgoing branch identity remains visible.
    """
    if record.get("kind") != "local-continuations":
        raise ValueError("Missing original local native node evidence")
    source = record.get("source")
    if not isinstance(source, dict) or type(source.get("graphId")) is not int:
        raise ValueError("Invalid original local source directed GraphId")
    seen: set[int] = set()
    options = record.get("options")
    if not isinstance(options, list):
        raise ValueError("Missing original native node adjacency")
    for row in options:
        if not isinstance(row, dict) or type(row.get("viaHierarchy")) is not bool:
            raise ValueError("Invalid native hierarchy transition evidence")
        edge = row.get("edge")
        if not isinstance(edge, dict) or type(edge.get("graphId")) is not int:
            raise ValueError("Invalid original outgoing directed GraphId")
        if edge["graphId"] in seen:
            raise ValueError("Duplicate original outgoing directed GraphId")
        seen.add(edge["graphId"])
        if (type(edge.get("access")) is not int or type(edge.get("shortcut")) is not bool
                or type(edge.get("transit")) is not bool):
            raise ValueError("Missing native outgoing access/representation evidence")
        for field in ("startLat", "startLon", "endLat", "endLon"):
            value = edge.get(field)
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError("Invalid original native outgoing geometry")
        # fromNodeGraphId is the native node that actually owns this edge;
        # matching GPS or a heading must never establish a node transition.
        from_id = row.get("fromNodeGraphId")
        if from_id is not None:
            if type(from_id) is not int or from_id < 0:
                raise ValueError("Invalid original outgoing native from-node GraphId")
            if (not row["viaHierarchy"] and
                    from_id != source.get("endNodeGraphId")):
                raise ValueError("Original direct incident edge has wrong native from-node")
        departure = edge.get("departure")
        if departure is not None and (not isinstance(departure, list) or
                len(departure) != 2 or
                any(type(x) not in (float, int) or not math.isfinite(x)
                    for x in departure)):
            raise ValueError("Invalid original native shape departure")
        costing = row.get("nativeImmediateCosting")
        if costing is not None:
            if (not isinstance(costing, dict) or
                    set(costing) != {"car", "motorcycle"} or
                    any(x not in NATIVE_COSTING_STATUSES for x in costing.values())):
                raise ValueError("Invalid native vehicle-specific one-step costing evidence")


def classify_source_native_branch_topology(options: list[dict],
                                         source_end_node_id: int) -> dict:
    """Bounded original A junction classification, not physical-road identity.

    Identical native FROM-node IDs establish true directed topology, while
    Valhalla's directed shape departure and end-node identity establish
    geometric divergence between different positive original branches.
    No angle, road-name, way-ID, proximity, preferred-turn or multi-hop rule.
    All other plausible alternatives are retained as unverified possibilities.
    """
    if type(source_end_node_id) is not int or source_end_node_id < 0:
        raise ValueError("Missing original source end-node for branch verification")
    vehicle = {}
    for mode, bit in (("car", 1), ("motorcycle", 1024)):
        allowed = []
        unknown = []
        denied = []
        for opt in options:
            gid = opt["graphId"]
            result = opt["nativeImmediateCosting"][mode]
            if result == "NOT_EVALUATED":
                continue
            if result == "ALLOWED_NATIVE_IMMEDIATE":
                if not (opt["nativeVehicleModes"] & bit):
                    raise ValueError("Native costing allowed a vehicle without original access")
                if opt["viaHierarchy"] or opt.get("nativeFromNodeGraphId") != source_end_node_id:
                    raise ValueError("Native immediate legal edge is not from the exact A end node")
                allowed.append(opt)
            elif result.startswith("UNRESOLVED_"):
                unknown.append(gid)
            else:
                denied.append(gid)
        allowed_ids = [x["graphId"] for x in allowed]
        if len(allowed_ids) != len(set(allowed_ids)):
            raise ValueError("Repeated original legal outgoing directed GraphId")
        if all(x["nativeImmediateCosting"][mode] == "NOT_EVALUATED" for x in options):
            status = "NOT_EVALUATED"
        elif len(allowed) >= 2:
            valid_departures = all(
                isinstance(x.get("nativeDirectedDeparture"), list) and
                len(x["nativeDirectedDeparture"]) == 2 and
                all(type(c) in (int, float) and math.isfinite(c)
                    for c in x["nativeDirectedDeparture"])
                for x in allowed)
            end_nodes = [x.get("nativeEndNodeGraphId") for x in allowed]
            departures = [tuple(x["nativeDirectedDeparture"])
                          for x in allowed] if valid_departures else []
            if (valid_departures and
                    all(type(n) is int and n >= 0 for n in end_nodes) and
                    len(set(end_nodes)) == len(allowed) and
                    len(set(departures)) == len(allowed)):
                status = "DISTINCT_NATIVE_GEOMETRIC_BRANCHES"
            else:
                status = "MULTIPLE_ALLOWED_OVERLAPPING_OR_UNKNOWN_GEOMETRY"
        elif len(allowed) == 1:
            status = ("SINGLE_ALLOWED_WITH_UNKNOWN_ALTERNATIVES" if unknown
                      else "SINGLE_STATIC_LEGAL_CONTINUATION")
        else:
            status = ("NO_CONFIRMED_WITH_UNKNOWN_ALTERNATIVES" if unknown
                      else "NO_CONFIRMED_STATIC_CONTINUATION")
        vehicle[mode] = {
            "nativeTopologyStatus": status,
            "staticallyAllowedDirectedGraphIds": allowed_ids,
            "unresolvedDirectedGraphIds": unknown,
            "nativeDeniedOrUnavailableGraphIds": denied,
            "hasUnresolvedAlternatives": bool(unknown),
            "physicalRoadIdentity": "NOT_VERIFIED",
        }
    return vehicle


def native_terminal_modes_from_adjacency(native_observation: dict) -> int:
    """Prove a directed edge's graph-LOCAL terminal vehicle modes.

    Iterate ALL original outgoing edges at its actual compiled end node and
    immediate native hierarchy peers (including shortcuts). This cannot
    establish physical-road identity at a fork or a corresponding B road.
    """
    validate_immediate_native_observation(native_observation)
    source = native_observation["source"]
    if (type(source.get("access")) is not int or source["access"] <= 0):
        raise ValueError("Missing original native source vehicle modes")
    all_outgoing = 0
    for row in native_observation["options"]:
        if row["edge"]["transit"]:
            raise ValueError("Transit found among native road-only adjacency")
        all_outgoing |= row["edge"]["access"]
    return source["access"] & ~all_outgoing


def verify_cut_root_native_identity(cut_row: dict, native_observation: dict) -> int:
    """Independent native read-back of exact A GraphId, X and local modes.

    Fail closed on stale source rows or missing hierarchy/branch options;
    never infer a physical road from GPS, names, mode or bearing.
    """
    modes = native_terminal_modes_from_adjacency(native_observation)
    source = native_observation["source"]
    for field in ("graphId", "endNodeGraphId", "access"):
        if type(cut_row.get(field)) is not int or cut_row[field] != source.get(field):
            raise ValueError(f"Native directed source identity mismatch: {field}")
    for field in ("endLat", "endLon"):
        first, second = cut_row.get(field), source.get(field)
        if (type(first) not in (int, float) or type(second) not in (int, float)
                or not math.isfinite(first) or not math.isfinite(second)
                or abs(first - second) > 1e-7):
            raise ValueError(f"Original native terminal node GPS mismatch: {field}")
    if (type(cut_row.get("nativeTerminalModes")) is not int or
            modes != cut_row["nativeTerminalModes"]):
        raise ValueError("Original native terminal mask disagrees with independently read local adjacency")
    return modes


def inspect_local_source_edges(*, manifest_path: Path, index_path: Path,
                               buffer_path: Path, valhalla_config_path: Path,
                               binary: Path, source_graph_ids: list[int],
                               allowed_tile_ids: set[int] | None = None,
                               evaluate_native_costing: bool = False) -> list[dict]:
    """Read immediate Valhalla incident edges for explicitly selected sources.

    Uses the same SHA-pinned original graph as the streaming source stage.
    It never discovers a new road from a historical ledger or scans all tiles.
    Supplying seed IDs is an internal step of selecting actual source-cut
    edges, NOT a separate user-defined handoff or production fallback.
    """
    manifest, selected = region_input(manifest_path, index_path, buffer_path)
    require_native_protocol(binary, str(manifest["valhallaVersion"]))
    original_tiles = {int(x["level"]) | (int(x["tileIndex"]) << 3)
                      for x in selected}
    permissible = original_tiles if allowed_tile_ids is None else allowed_tile_ids
    if not permissible.issubset(original_tiles):
        raise ValueError("Local source node inspection exceeds native boundary tiles")
    if not source_graph_ids or any(type(gid) is not int or gid <= 0 or
                                   (gid & ((1 << 25) - 1)) not in permissible
                                   for gid in source_graph_ids):
        raise ValueError("Input source directed IDs must belong to selected original cutoff tiles")
    if len(set(source_graph_ids)) != len(source_graph_ids):
        raise ValueError("Repeated input source directed ID")
    config = load_json(valhalla_config_path)
    if "mjolnir" not in config:
        raise ValueError("Not a Valhalla routing config")
    with tempfile.TemporaryDirectory(prefix="f8-native-source-continuations-") as tmp:
        root = Path(tmp)
        params = dict(config)
        params["mjolnir"] = dict(config["mjolnir"])
        params["mjolnir"]["tile_extract"] = str((manifest_path.parent / manifest["artifact"]["fileName"]).resolve())
        params["mjolnir"]["tile_dir"] = str(root / "no-unpacked-tiles")
        cfg = root / "valhalla.json"
        cfg.write_text(json.dumps(params), encoding="utf-8")
        ids = root / "original-source-directed-ids.txt"
        ids.write_text("".join(f"{gid}\n" for gid in source_graph_ids), encoding="utf-8")
        command = [str(binary), "--local-continuations", str(cfg), str(ids)]
        if evaluate_native_costing:
            command.append("--evaluate-native-costing")
        run = subprocess.run(command, capture_output=True, text=True,
                             check=True, timeout=600)
    lines = run.stdout.splitlines()
    records = [json.loads(line) for line in lines]
    if (not records or records[-1].get("kind") != "complete" or
        records[-1].get("edgesInspected") != len(source_graph_ids) or
        records[-1].get("valhallaVersion") != str(manifest["valhallaVersion"])):
        raise ValueError("Original native continuation inspection incomplete")
    observations = records[:-1]
    if ([x.get("kind") for x in observations] != ["local-continuations"] * len(source_graph_ids)
        or [x["source"]["graphId"] for x in observations] != source_graph_ids):
        raise ValueError("Native local continuation output differs from requested source IDs")
    for record in observations:
        validate_immediate_native_observation(record)
        if evaluate_native_costing and any(
                "nativeImmediateCosting" not in x or
                type(x.get("fromNodeGraphId")) is not int or
                type(x["edge"].get("endNodeGraphId")) is not int
                for x in record["options"]):
            raise ValueError("Native one-step Valhalla costing/topology not acknowledged")
    return observations


def classify_native_rows(lines: str, *, selected_count: int, version: str) -> tuple[list[dict], list[dict], dict]:
    """Separate graph-local terminal modes from unresolved junction cases.

    Neither list alone establishes that the *same physical road* ends here;
    receiving-graph correlation is essential before declaring final edges.
    """
    terminal: list[dict] = []
    unresolved: list[dict] = []
    seen: set[int] = set()
    completion = None
    for line in lines.splitlines():
        entry = json.loads(line)
        if entry.get("kind") == "complete":
            if completion is not None:
                raise ValueError("Repeated native completion record")
            completion = entry
            continue
        if completion is not None or entry.get("kind") != "edge":
            raise ValueError("Invalid native boundary record sequence")
        validate_directed_approach(entry)
        gid = entry["graphId"]
        if not isinstance(gid, int) or gid in seen:
            raise ValueError("Repeated or nonnumeric original directed GraphId")
        seen.add(gid)
        if int(entry["nativeTerminalModes"]) & ~int(entry["access"]):
            raise ValueError("Native terminal mode exceeds original forward access")
        if int(entry["nativeTerminalModes"]):
            terminal.append(entry)
        else:
            unresolved.append(entry)
    if (not completion or completion.get("selectedTiles") != selected_count
            or completion.get("valhallaVersion") != version
            or completion.get("edgesEmitted") != len(seen)):
        raise ValueError("Original native boundary scan did not complete on exact inputs")
    return terminal, unresolved, completion


def extract(*, manifest_path: Path, index_path: Path, buffer_path: Path,
            valhalla_config_path: Path, binary: Path, cut_only: bool = False,
            paired_scope: dict | None = None) -> dict:
    manifest, selected = region_input(manifest_path, index_path, buffer_path)
    if paired_scope is not None:
        if not cut_only or paired_scope["source"]["graphFingerprint"] != manifest["graphFingerprint"]:
            raise ValueError("Paired source scan requires the exact source graph and original cutoff")
        selected = paired_scope["selectedSourceTiles"]
    expected_version = str(manifest["valhallaVersion"])
    require_native_protocol(binary, expected_version)
    # Keep exactly the validated original routing archive, and never read
    # a potentially stale unpacked tile directory from a previous build.
    config = load_json(valhalla_config_path)
    if "mjolnir" not in config:
        raise ValueError("Not a Valhalla routing config")
    original_archive = manifest_path.parent / manifest["artifact"]["fileName"]
    with tempfile.TemporaryDirectory(prefix="f8-boundary-") as temp:
        root = Path(temp)
        params = dict(config)
        params["mjolnir"] = dict(config["mjolnir"])
        params["mjolnir"]["tile_extract"] = str(original_archive.resolve())
        params["mjolnir"]["tile_dir"] = str(root / "no-unpacked-tiles")
        cfg = root / "valhalla.json"
        cfg.write_text(json.dumps(params), encoding="utf-8")
        ids = root / "selected-original-tiles.txt"
        ids.write_text("".join(f'{int(tile["level"]) | int(tile["tileIndex"]) << 3}\n'
                               for tile in selected), encoding="utf-8")
        command = [str(binary), str(cfg), str(ids)]
        if cut_only:
            command.append(str(buffer_path.resolve()))
        if paired_scope is not None:
            shared = root / "sha-bound-shared-original-cut.geojson"
            shared.write_text(json.dumps({"type": "Feature", "properties": {},
                            "geometry": mapping(paired_scope["geometry"])}), encoding="utf-8")
            command.append(str(shared))
        result = subprocess.run(command, check=True,
                                capture_output=True, text=True, timeout=600)
    terminal, unresolved, complete = classify_native_rows(
        result.stdout, selected_count=len(selected), version=expected_version)
    if complete.get("originalCutFilterApplied") is not cut_only:
        raise ValueError("Native original-buffer-cut selection not acknowledged")
    if paired_scope is not None and complete.get("sharedCutFilterApplied") is not True:
        raise ValueError("Native shared-pair source cutoff selection not acknowledged")
    if cut_only and any(e.get("originalCutOrientation") not in
                        ("OUTWARD", "INWARD", "AMBIGUOUS") for e in terminal + unresolved):
        raise ValueError("Missing authoritative cut orientation evidence")
    return {
        "schema": SCHEMA,
        "schemaVersion": 3 if cut_only else 2,
        "actualOriginalCutGeometryFilter": cut_only,
        "sharedCutFilterApplied": paired_scope is not None,
        "regionId": manifest["regionId"],
        "packageVersion": manifest["packageVersion"],
        "graphFingerprint": manifest["graphFingerprint"],
        "bufferFingerprint": "sha256:" + sha256(buffer_path),
        "graphIndexFingerprint": "sha256:" + sha256(index_path),
        "valhallaVersion": expected_version,
        "selectedBoundaryTileCount": len(selected),
        "nativeDirectedEdgesInSelectedTiles": complete["directedExamined"],
        "nativeModeTerminalCandidates": terminal,
        "unresolvedJunctionDirectedEdges": unresolved,
        "sourcePhysicalRoadFinalIdentification": "INCOMPLETE",
        "receiverCorrelation": "NOT_STARTED",
        "productionPublication": "BLOCKED",
    }



def extract_to_file(*, manifest_path: Path, index_path: Path, buffer_path: Path,
                    valhalla_config_path: Path, binary: Path, output_path: Path,
                    cut_only: bool = False) -> dict:
    """Stream the same complete, explicitly UNPROVEN boundary evidence to disk.

    The original region graph is never modified. This is storage efficiency,
    not an extra discovery algorithm or a change in candidate eligibility.
    Large selected boundary tiles may contain millions of unrelated edges;
    neither the native output nor its arrays may be materialized in memory.
    """
    if output_path.exists():
        raise ValueError("Output already exists; refusing to overwrite original region evidence")
    manifest, selected = region_input(manifest_path, index_path, buffer_path)
    version = str(manifest["valhallaVersion"])
    require_native_protocol(binary, version)
    config = load_json(valhalla_config_path)
    if "mjolnir" not in config:
        raise ValueError("Not a Valhalla routing config")
    original_archive = manifest_path.parent / manifest["artifact"]["fileName"]
    with tempfile.TemporaryDirectory(prefix="f8-boundary-stream-") as temp:
        root = Path(temp)
        params = dict(config)
        params["mjolnir"] = dict(config["mjolnir"])
        params["mjolnir"]["tile_extract"] = str(original_archive.resolve())
        params["mjolnir"]["tile_dir"] = str(root / "no-unpacked-tiles")
        cfg = root / "valhalla.json"
        cfg.write_text(json.dumps(params), encoding="utf-8")
        ids = root / "selected-original-tiles.txt"
        ids.write_text("".join(f'{int(t["level"]) | int(t["tileIndex"]) << 3}\n'
                               for t in selected), encoding="utf-8")
        native_path = root / "native.jsonl"
        with native_path.open("wb") as handle:
            command = [str(binary), str(cfg), str(ids)]
            if cut_only:
                command.append(str(buffer_path.resolve()))
            subprocess.run(command, check=True,
                           stdout=handle, stderr=subprocess.PIPE, timeout=600)
        counts = {"terminal": 0, "unresolved": 0}
        cut_orientations = {"OUTWARD": 0, "INWARD": 0, "AMBIGUOUS": 0}
        spool_paths = {category: root / (category + ".json-part")
                       for category in counts}
        seen = set()
        completion = None
        with (native_path.open("r", encoding="utf-8") as source,
              spool_paths["terminal"].open("w", encoding="utf-8") as terminals,
              spool_paths["unresolved"].open("w", encoding="utf-8") as unresolved):
            targets = {"terminal": terminals, "unresolved": unresolved}
            for line in source:
                entry = json.loads(line)
                if entry.get("kind") == "complete":
                    if completion is not None:
                        raise ValueError("Repeated native completion record")
                    completion = entry
                    continue
                if completion is not None or entry.get("kind") != "edge":
                    raise ValueError("Invalid native boundary record sequence")
                validate_directed_approach(entry)
                if cut_only:
                    orientation = entry.get("originalCutOrientation")
                    if orientation not in cut_orientations:
                        raise ValueError("Original native geometry lacks cut orientation")
                    cut_orientations[orientation] += 1
                gid = entry.get("graphId")
                if not isinstance(gid, int) or gid in seen:
                    raise ValueError("Repeated or nonnumeric original directed GraphId")
                seen.add(gid)
                if int(entry["nativeTerminalModes"]) & ~int(entry["access"]):
                    raise ValueError("Native terminal mode exceeds original access")
                category = "terminal" if entry["nativeTerminalModes"] else "unresolved"
                target = targets[category]
                if counts[category]:
                    target.write(",")
                target.write(line.rstrip("\r\n"))
                counts[category] += 1
        if (completion is None or completion.get("selectedTiles") != len(selected)
                or completion.get("valhallaVersion") != version
                or completion.get("edgesEmitted") != len(seen)
                or completion.get("originalCutFilterApplied") is not cut_only):
            raise ValueError("Original native boundary scan did not complete on exact inputs")
        # Original compiled graph is the retained authority. This candidate
        # inventory explicitly does NOT assert final physical-road identity.
        header = {
            "schema": SCHEMA, "schemaVersion": 3 if cut_only else 2,
            "actualOriginalCutGeometryFilter": cut_only,
            "originalCutOrientations": cut_orientations if cut_only else None,
            "regionId": manifest["regionId"],
            "packageVersion": manifest["packageVersion"],
            "graphFingerprint": manifest["graphFingerprint"],
            "bufferFingerprint": "sha256:" + sha256(buffer_path),
            "graphIndexFingerprint": "sha256:" + sha256(index_path),
            "valhallaVersion": version,
            "selectedBoundaryTileCount": len(selected),
            "nativeDirectedEdgesInSelectedTiles": completion["directedExamined"],
        }
        footer = {
            "sourcePhysicalRoadFinalIdentification": "INCOMPLETE",
            "receiverCorrelation": "NOT_STARTED",
            "productionPublication": "BLOCKED",
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=output_path.parent, delete=False) as tempfile_output:
            staged = Path(tempfile_output.name)
        try:
            opener = gzip.open if output_path.suffix == ".gz" else open
            with opener(staged, "wt", encoding="utf-8") as result:
                result.write(json.dumps(header, separators=(",", ":"))[:-1])
                for name, filename in (("nativeModeTerminalCandidates", spool_paths["terminal"]),
                                       ("unresolvedJunctionDirectedEdges", spool_paths["unresolved"])):
                    result.write(',"' + name + '":[')
                    with filename.open("r", encoding="utf-8") as rows:
                        shutil.copyfileobj(rows, result, length=1024 * 1024)
                    result.write("]")
                result.write("," + json.dumps(footer, separators=(",", ":"))[1:] + "\n")
            if output_path.exists():
                raise ValueError("Refusing to overwrite existing original region evidence")
            staged.replace(output_path)
        finally:
            staged.unlink(missing_ok=True)
        return {**header, **footer,
                "nativeTerminalCandidateCount": counts["terminal"],
                "unresolvedJunctionDirectedEdgeCount": counts["unresolved"]}


def select_pair_terminal_candidates(cut_rows: list[dict], read_local,
                                    *, source_cut_tile_ids: set[int],
                                    receiver_footprint) -> dict:
    """Terminal-first one-hop native source selection, never graph traversal.

    Every outward/ambiguous source cutoff edge is preserved exactly once.
    Edges with native terminal modes are direct *candidates*. The remaining
    directed roads undergo one immediate node/hierarchy inspection only.
    Their immediate ORIGINAL non-shortcut outgoing edges are checked once for
    local terminal eligibility (including beyond-cut finals), never followed.
    Their forks remain unresolved regardless of heading, name or class.
    """
    ids: set[int] = set()
    roots = []
    for row in cut_rows:
        gid = row.get("graphId")
        if type(gid) is not int or gid in ids:
            raise ValueError("Repeated or invalid original paired-cut GraphId")
        ids.add(gid)
        if row.get("originalCutOrientation") in ("OUTWARD", "AMBIGUOUS"):
            roots.append(row)
        elif row.get("originalCutOrientation") != "INWARD":
            raise ValueError("Unclassified original directed shared-cut encounter")
    if not roots:
        raise ValueError("Original pair-shared cutoff has no outward/ambiguous directed edges")
    # Reopen every A source-cut root from the ORIGINAL compiled Valhalla
    # graph. The stream's own terminal mask is not a proof: recalculate it
    # from actual outgoing directed edges and immediate hierarchy peers.
    root_observations = read_local([row["graphId"] for row in roots])
    if len(root_observations) != len(roots):
        raise ValueError("Incomplete source-cut native identity verification")
    root_inspected: dict[int, dict] = {}
    for row, record in zip(roots, root_observations):
        verify_cut_root_native_identity(row, record)
        root_inspected[row["graphId"]] = record

    direct = [r for r in roots if r["nativeTerminalModes"]]
    nonterminal = [r for r in roots if r["access"] & ~r["nativeTerminalModes"]]
    nonterminal_by_gid = {r["graphId"]: r for r in nonterminal}
    terminal: dict[int, dict] = {}
    def retain(gid: int, modes: int, origin: int, native: dict, *, kind: str,
               proof: dict):
        if modes & ~native["access"] or not modes:
            raise ValueError("Native terminal permissions disagree with original access")
        data = terminal.setdefault(gid, {"sourceFinalCandidateGraphId": gid,
            "terminalVehicleModes": 0, "access": native["access"],
            "endLat": native["endLat"], "endLon": native["endLon"],
            "endNodeGraphId": native["endNodeGraphId"],
            "sourceCutGraphIds": [], "selectionKinds": [],
            "originalNativeLocalProof": proof,
            "nativeGraphLocalTerminalProof": "VERIFIED",
            "physicalRoadFinalCompleteness": "NOT_VERIFIED"})
        if (data["endLat"], data["endLon"], data["access"],
                data["endNodeGraphId"]) != (native["endLat"], native["endLon"],
                native["access"], native["endNodeGraphId"]):
            raise ValueError("Conflicting original native terminal GraphId identity")
        if data["originalNativeLocalProof"] != proof:
            raise ValueError("Conflicting original native terminal proof for same directed GraphId")
        data["terminalVehicleModes"] |= modes
        if origin not in data["sourceCutGraphIds"]:
            data["sourceCutGraphIds"].append(origin)
        if kind not in data["selectionKinds"]:
            data["selectionKinds"].append(kind)
    for row in direct:
        record = root_inspected[row["graphId"]]
        retain(row["graphId"], row["nativeTerminalModes"],
               row["graphId"], record["source"],
               kind="NATIVE_TERMINAL_AT_SHARED_CUT",
               proof={"method": "INDEPENDENT_ORIGINAL_END_NODE_ADJACENCY",
                      "endNodeGraphId": row["endNodeGraphId"],
                      "outgoingOriginalDirectedGraphIds": [v["edge"]["graphId"]
                                               for v in record["options"]],
                      "hierarchyPeersIncluded": True,
                      "terminalModes": row["nativeTerminalModes"]})
    unresolved = []
    pending: dict[int, list[int]] = {}
    for root in nonterminal:
        native = root_inspected[root["graphId"]]
        options = []
        for opt in native["options"]:
            edge = opt["edge"]
            pending_modes = root["access"] & ~root["nativeTerminalModes"]
            eligible_modes = edge["access"] & pending_modes
            eligible = bool(eligible_modes and not edge["shortcut"] and not edge["transit"])
            in_scope = (edge["graphId"] & ((1 << 25) - 1)) in source_cut_tile_ids
            options.append({"graphId": edge["graphId"],
                "viaHierarchy": opt["viaHierarchy"],
                "nativeVehicleModes": edge["access"] & root["access"],
                "shortcut": edge["shortcut"], "transit": edge["transit"],
                "eligibleOriginalForward": eligible,
                "inSelectedSourceTiles": in_scope,
                "nativeFromNodeGraphId": opt.get("fromNodeGraphId"),
                "nativeEndNodeGraphId": edge.get("endNodeGraphId"),
                "nativeDirectedDeparture": edge.get("departure"),
                "nativeOriginalRoadClass": edge.get("roadClass"),
                "nativeOriginalRoadUse": edge.get("roadUse"),
                "nativeOriginalLayer": edge.get("layer"),
                "nativeOriginalBridge": edge.get("bridge"),
                "nativeOriginalTunnel": edge.get("tunnel"),
                "nativeImmediateCosting": opt.get("nativeImmediateCosting",
                                                  {"car": "NOT_EVALUATED",
                                                   "motorcycle": "NOT_EVALUATED"})})
            if eligible and in_scope:
                pending.setdefault(edge["graphId"], []).append(root["graphId"])
        unresolved.append({"sourceCutGraphId": root["graphId"],
            "sourceOriginalEndNodeGraphId": native["source"].get("endNodeGraphId"),
            "sourceOriginalNativeApproach": native["source"].get("approach"),
            "nativeVehicleModes": root["access"],
            "immediateNativeOutgoing": options,
            "modeSpecificNativeBranchTopology": classify_source_native_branch_topology(
                options, native["source"]["endNodeGraphId"]),
            "status": "NONTERMINAL_LOCAL_RELATION_UNRESOLVED",
            "physicalRoadIdentity": "NOT_VERIFIED"})
    # Inspect only IMMEDIATE successors, then STOP. In particular, the
    # algorithm does not recursively follow graph edges, even on curves,
    # junctions or hierarchy transitions. B footprint is a source scope
    # check, NEVER the actual B-directed edge identity.
    successor_ids = sorted(pending)
    successors = read_local(successor_ids) if successor_ids else []
    if len(successors) != len(successor_ids):
        raise ValueError("Incomplete original one-hop source local inspection")
    observed_one_hop: set[int] = set()
    for gid, row in zip(successor_ids, successors):
        if row.get("kind") != "local-continuations" or row["source"]["graphId"] != gid:
            raise ValueError("Wrong original immediate forward directed GraphId")
        source = row["source"]
        available = native_terminal_modes_from_adjacency(row)
        if not receiver_footprint.covers(Point(
                source["endLon"], source["endLat"])):
            continue
        observed_one_hop.add(gid)
        if available:
            # One predecessor may be a fork or hierarchy peer. Preserve
            # every distinct source origin rather than assign road identity.
            for origin in pending[gid]:
                root = nonterminal_by_gid[origin]
                modes = available & root["access"] & ~root["nativeTerminalModes"]
                if modes:
                    retain(gid, modes, origin, source,
                           kind="NATIVE_TERMINAL_ONE_IMMEDIATE_HOP_UNPROVEN",
                           proof={"method": "INDEPENDENT_ORIGINAL_END_NODE_ADJACENCY",
                                  "endNodeGraphId": source["endNodeGraphId"],
                                  "outgoingOriginalDirectedGraphIds": [v["edge"]["graphId"]
                                                     for v in row["options"]],
                                  "hierarchyPeersIncluded": True,
                                  "terminalModes": available})
    # A bounded structural proof is possible only for a single native
    # immediate successor with no shortcuts/branch alternatives and a
    # terminal end-node for *all* previously continuing vehicle modes.
    # A physical-road identity is NOT inferred; every original root remains
    # present in the unresolved register for full D-017 acceptance.
    structurally_single_hop = 0
    for root in unresolved:
        source_id = root["sourceCutGraphId"]
        row = nonterminal_by_gid[source_id]
        continuing = row["access"] & ~row["nativeTerminalModes"]
        options = root["immediateNativeOutgoing"]
        if len(options) == 1 and options[0]["eligibleOriginalForward"]:
            successor = terminal.get(options[0]["graphId"])
            if (successor is not None and
                    options[0]["graphId"] != source_id and
                    (continuing & ~successor["terminalVehicleModes"]) == 0 and
                    source_id in successor["sourceCutGraphIds"]):
                root["localStructuralStatus"] = "SINGLE_IMMEDIATE_NATIVE_TERMINAL"
                root["uniqueNativeOneHopTerminalGraphId"] = options[0]["graphId"]
                root["locallyVerifiedContinuingVehicleModes"] = continuing
                structurally_single_hop += 1
                continue
        root["localStructuralStatus"] = ("MULTIPLE_NATIVE_OUTGOING_UNRESOLVED"
                                         if len(options) > 1 else
                                         "SINGLE_NATIVE_OUTGOING_UNRESOLVED")
        root["uniqueNativeOneHopTerminalGraphId"] = None
        root["locallyVerifiedContinuingVehicleModes"] = 0

    # Only flag identical native end node or exact GPS X; never collapse
    # candidates on proximity, bearings, names or hierarchy representation.
    # Legitimate multi-road junctions remain separate even if X coincides.
    by_end_node: dict[int, list[int]] = {}
    by_exact_x: dict[tuple[float, float], list[int]] = {}
    for candidate in terminal.values():
        gid = candidate["sourceFinalCandidateGraphId"]
        by_end_node.setdefault(candidate["endNodeGraphId"], []).append(gid)
        by_exact_x.setdefault((candidate["endLat"], candidate["endLon"]), []).append(gid)
    repeated_nodes = [sorted(ids) for ids in by_end_node.values() if len(ids) > 1]
    repeated_x = [sorted(ids) for ids in by_exact_x.values() if len(ids) > 1]
    repeated_nodes.sort()
    repeated_x.sort()
    branching_counts = {mode: {} for mode in ("car", "motorcycle")}
    for source_row in unresolved:
        for mode, result in source_row["modeSpecificNativeBranchTopology"].items():
            status = result["nativeTopologyStatus"]
            branching_counts[mode][status] = branching_counts[mode].get(status, 0) + 1
    return {
        "modeSpecificNativeBranchTopologyCounts": branching_counts,
        "sourceNativeBranchClassification": "EXACT_NODE_AND_DIRECTED_DEPARTURE_ONLY",
        "originalPairedCutDirectedEvidence": cut_rows,
        "outwardOrAmbiguousSourceCutCount": len(roots),
        "directNativeTerminalRootCount": len(direct),
        "cutRootsIndependentlyReadBackCount": len(root_inspected),
        "nativeTerminalRootsIndependentlyVerifiedCount": len(direct),
        "nonterminalSourceCutCount": len(nonterminal),
        "singleNativeOneHopTerminalRootCount": structurally_single_hop,
        "oneHopInspectedGraphIdCount": len(successor_ids),
        "oneHopReceiverFootprintGraphIdCount": len(observed_one_hop),
        "nativeGraphLocalTerminalCandidateCount": len(terminal),
        "nativeImmediateCostingAssessment": "ONE_STEP_NO_PATH_HISTORY",
        "nativeImmediateCostingMayResolvePhysicalRoad": False,
        "exactEndNodeCoincidenceGroups": repeated_nodes,
        "exactTerminalGpsCoincidenceGroups": repeated_x,
        "terminalCandidatesByExactSourceGraphId": [terminal[gid] for gid in sorted(terminal)],
        "unresolvedNonterminalSourceCutObservations": unresolved,
        "sourcePhysicalRoadDirectionCompleteness": "NOT_VERIFIED",
        "receiverCorrelation": "NOT_STARTED",
        "productionPublication": "BLOCKED",
    }


def resolve_original_cut_to_file(*, manifest_path: Path, index_path: Path,
                                 buffer_path: Path, valhalla_config_path: Path,
                                 binary: Path, output_path: Path,
                                 receiver_manifest_path: Path,
                                 receiver_index_path: Path,
                                 receiver_buffer_path: Path) -> dict:
    """Source A terminal-first, restricted to the *A→B shared* original cut.

    Not a graph walk, not an OSM/country heuristic, not a receiving match.
    """
    if output_path.exists():
        raise ValueError("Source final evidence already exists; refusing overwrite")
    pair = verified_shared_cut(source_manifest=manifest_path,
        source_index=index_path, source_buffer=buffer_path,
        receiver_manifest=receiver_manifest_path,
        receiver_index=receiver_index_path, receiver_buffer=receiver_buffer_path)
    evidence = extract(manifest_path=manifest_path, index_path=index_path,
                       buffer_path=buffer_path, valhalla_config_path=valhalla_config_path,
                       binary=binary, cut_only=True, paired_scope=pair)
    cut_rows = evidence["nativeModeTerminalCandidates"] + evidence["unresolvedJunctionDirectedEdges"]
    selected_ids = {int(row["level"]) | (int(row["tileIndex"]) << 3)
                    for row in pair["selectedSourceTiles"]}
    def inspect(gids):
        return inspect_local_source_edges(manifest_path=manifest_path,
            index_path=index_path, buffer_path=buffer_path,
            valhalla_config_path=valhalla_config_path, binary=binary,
            source_graph_ids=gids, allowed_tile_ids=selected_ids,
            evaluate_native_costing=True)
    observed = select_pair_terminal_candidates(cut_rows, inspect,
        source_cut_tile_ids=selected_ids,
        receiver_footprint=shape(load_json(receiver_buffer_path)["geometry"]))
    # Read both manifest-bound index/buffer identities again before writing.
    # Do not rewrite original graph archives or installed packages.
    original, _ = region_input(manifest_path, index_path, buffer_path)
    receiver, _ = region_input(receiver_manifest_path, receiver_index_path,
                               receiver_buffer_path)
    if (original["graphFingerprint"] != evidence["graphFingerprint"]
            or original["graphFingerprint"] != pair["source"]["graphFingerprint"]
            or receiver["graphFingerprint"] != pair["receiver"]["graphFingerprint"]):
        raise ValueError("Either original graph archive changed during paired source selection")
    for path, sha in ((receiver_index_path, pair["receiverIndexFingerprint"]),
                      (receiver_buffer_path, pair["receiverBufferFingerprint"]),
                      (index_path, pair["sourceIndexFingerprint"]),
                      (buffer_path, pair["sourceBufferFingerprint"])):
        require_fingerprint(path, sha)
    output = {
        "schema": "roadpilot.f8-paired-source-local-terminal-candidates",
        "schemaVersion": 5,
        "fromRegionId": pair["source"]["regionId"],
        "toRegionId": pair["receiver"]["regionId"],
        "fromGraphFingerprint": pair["source"]["graphFingerprint"],
        "toGraphFingerprint": pair["receiver"]["graphFingerprint"],
        "fromBufferFingerprint": pair["sourceBufferFingerprint"],
        "toBufferFingerprint": pair["receiverBufferFingerprint"],
        "fromGraphIndexFingerprint": pair["sourceIndexFingerprint"],
        "toGraphIndexFingerprint": pair["receiverIndexFingerprint"],
        "reciprocalBoundaryFingerprints": pair["reciprocalBoundaryFingerprints"],
        "originalSharedSourceCutGeometryFingerprint": "sha256:" +
            hashlib.sha256(pair["geometry"].wkb).hexdigest(),
        "selectedOriginalSourceBoundaryTiles": len(pair["selectedSourceTiles"]),
        "receiverOriginalTilesTouchingSharedCut": len(pair["receiverTilesTouchingSharedCut"]),
        "nativeDirectedEdgesInspectedInSelectedTiles": evidence["nativeDirectedEdgesInSelectedTiles"],
        "originalDirectedCutEdgeCount": len(cut_rows),
        **observed,
        "androidFullJourneyValidation": "NOT_RUN",
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=output_path.parent, delete=False) as temp:
        staged = Path(temp.name)
    try:
        writer = gzip.open if output_path.suffix == ".gz" else open
        with writer(staged, "wt", encoding="utf-8") as stream:
            json.dump(output, stream, ensure_ascii=False, separators=(",", ":"))
            stream.write("\n")
        if output_path.exists():
            raise ValueError("Source final evidence appeared during build; refusing overwrite")
        staged.replace(output_path)
    finally:
        staged.unlink(missing_ok=True)
    return {k: output[k] for k in ("fromRegionId", "toRegionId",
        "selectedOriginalSourceBoundaryTiles", "originalDirectedCutEdgeCount",
        "outwardOrAmbiguousSourceCutCount", "directNativeTerminalRootCount",
        "nonterminalSourceCutCount", "oneHopInspectedGraphIdCount",
        "sourcePhysicalRoadDirectionCompleteness", "productionPublication")}



def indexed_receiver_edges_at_x(*, receiver_manifest_path: Path,
                                receiver_index_path: Path,
                                receiver_buffer_path: Path,
                                receiver_valhalla_config: Path,
                                native_binary: Path, source_candidates: list[dict]) -> list[dict]:
    """Native original B Valhalla spatial bins around X, no whole-B scan.

    Candidate IDs and original endpoint X come ONLY from independently
    verified A GraphIds. Valhalla's B bins also find long edges that start
    outside X's containing tile and index opposing directed travel.
    """
    manifest, _ = region_input(receiver_manifest_path, receiver_index_path,
                               receiver_buffer_path)
    require_native_protocol(native_binary, manifest["valhallaVersion"])
    if not source_candidates:
        raise ValueError("No original source terminal candidates")
    seen = set()
    for item in source_candidates:
        gid = item.get("sourceFinalCandidateGraphId")
        if type(gid) is not int or gid in seen:
            raise ValueError("Duplicated or malformed original source final candidate")
        seen.add(gid)
        for field in ("endLat", "endLon"):
            if type(item.get(field)) not in (int, float) or not math.isfinite(item[field]):
                raise ValueError("Invalid original source handoff X")
    with tempfile.TemporaryDirectory(prefix="f8-native-receiver-at-x-") as tmp:
        work = Path(tmp)
        conf = load_json(receiver_valhalla_config)
        if "mjolnir" not in conf:
            raise ValueError("Not a Valhalla receiver configuration")
        conf["mjolnir"] = dict(conf["mjolnir"])
        conf["mjolnir"]["tile_extract"] = str(
            (receiver_manifest_path.parent / manifest["artifact"]["fileName"]).resolve())
        conf["mjolnir"]["tile_dir"] = str(work / "no-unpacked-tiles")
        conf_path = work / "receiver.json"
        conf_path.write_text(json.dumps(conf), encoding="utf-8")
        seeds = work / "source-X.jsonl"
        seeds.write_text(''.join(json.dumps({
            "sourceGraphId": item["sourceFinalCandidateGraphId"],
            "xLat": item["endLat"], "xLon": item["endLon"]
        }, separators=(",", ":")) + "\n" for item in source_candidates), encoding="utf-8")
        run = subprocess.run([str(native_binary), "--receiver-at-x",
                              str(conf_path), str(seeds)], capture_output=True,
                             check=True, text=True, timeout=600)
    lines = [json.loads(row) for row in run.stdout.splitlines()]
    if (len(lines) != len(source_candidates) + 1 or
            lines[-1].get("kind") != "complete-receiver" or
            lines[-1].get("sourcesInspected") != len(source_candidates) or
            lines[-1].get("valhallaVersion") != manifest["valhallaVersion"]):
        raise ValueError("Incomplete native original B receiving edge lookup")
    for source, observed in zip(source_candidates, lines[:-1]):
        if (observed.get("kind") != "receiver-at-x" or
                observed.get("sourceGraphId") != source["sourceFinalCandidateGraphId"] or
                abs(observed.get("xLat", float('inf')) - source["endLat"]) > 1e-7 or
                abs(observed.get("xLon", float('inf')) - source["endLon"]) > 1e-7):
            raise ValueError("Receiver native lookup disagrees with exact original A source X")
        edges = observed.get("originalBDirectedEdges")
        if not isinstance(edges, list):
            raise ValueError("Receiver original directed edge array missing")
        seen_edges = set()
        for option in edges:
            edge = option.get("edge", {})
            gid = edge.get("graphId")
            if type(gid) is not int or gid in seen_edges or type(edge.get("access")) is not int:
                raise ValueError("Invalid or repeated native B directed GraphId")
            seen_edges.add(gid)
            coordinates = option.get("directedShape")
            if not isinstance(coordinates, list) or len(coordinates) < 2:
                raise ValueError("Missing original B directed edge geometry")
            for point in coordinates:
                if (not isinstance(point, list) or len(point) != 2 or
                        any(type(value) not in (int, float) or not math.isfinite(value)
                            for value in point)):
                    raise ValueError("Invalid original B directed shape vertex")
            distance = option.get("nativeDistanceToXMetres")
            if (type(distance) not in (float, int) or
                    not 0 <= distance <= 4.00001):
                raise ValueError("Native receiver spatial index returned out-of-range shape")
    return lines[:-1]


def read_b_native_immediate_continuations(*, receiver_manifest_path: Path,
                                          receiver_index_path: Path,
                                          receiver_buffer_path: Path,
                                          receiver_valhalla_config: Path,
                                          native_binary: Path,
                                          original_b_predecessor_graph_ids: list[int]) -> dict[int, dict]:
    """Reopen ONLY native B predecessor edges proven at source X.

    Reuses the same native original GraphReader local-node view already used
    for A, in B's exact SHA-pinned archive. No route search or B graph walk.
    """
    if not original_b_predecessor_graph_ids:
        return {}
    ids = sorted(set(original_b_predecessor_graph_ids))
    manifest, _ = region_input(receiver_manifest_path, receiver_index_path,
                               receiver_buffer_path)
    require_native_protocol(native_binary, manifest['valhallaVersion'])
    with tempfile.TemporaryDirectory(prefix='f8-native-b-exact-node-') as tmp:
        root = Path(tmp)
        cfg = load_json(receiver_valhalla_config)
        if 'mjolnir' not in cfg:
            raise ValueError('Missing original B Valhalla config')
        cfg['mjolnir'] = dict(cfg['mjolnir'])
        cfg['mjolnir']['tile_extract'] = str(
            (receiver_manifest_path.parent / manifest['artifact']['fileName']).resolve())
        cfg['mjolnir']['tile_dir'] = str(root / 'no-unpacked-tiles')
        conf_path = root / 'receiver.json'
        conf_path.write_text(json.dumps(cfg), encoding='utf-8')
        ids_path = root / 'source-B-original-predecessors.txt'
        ids_path.write_text(''.join(f'{gid}\n' for gid in ids), encoding='utf-8')
        run = subprocess.run([str(native_binary), '--local-continuations',
            str(conf_path), str(ids_path), '--evaluate-native-costing'],
            capture_output=True, text=True, check=True, timeout=600)
    records = [json.loads(row) for row in run.stdout.splitlines()]
    if (len(records) != len(ids) + 1 or
            records[-1].get('kind') != 'complete' or
            records[-1].get('edgesInspected') != len(ids) or
            records[-1].get('valhallaVersion') != manifest['valhallaVersion']):
        raise ValueError('Incomplete original B immediate node evidence')
    for gid, record in zip(ids, records[:-1]):
        validate_immediate_native_observation(record)
        if record['source']['graphId'] != gid:
            raise ValueError('Wrong original B predecessor GraphId identity')
        if any('nativeImmediateCosting' not in opt or
               type(opt.get('fromNodeGraphId')) is not int
               for opt in record['options']):
            raise ValueError('Incomplete original B native legal successor evidence')
    return dict(zip(ids, records[:-1]))


def classify_original_b_directional_overlap(source: dict, receiver: dict) -> dict:
    """Compare actual A final directed shape at X to original B directed edge.

    GPS proximity is ONLY a candidate finder. Positive evidence requires the
    *same directed source approach segment* overlapping B geometry in order,
    no opposing travel, and compiled layer/bridge/tunnel concordance.
    Anything less remains an explicitly unresolved candidate, not a match.
    """
    edge = receiver["edge"]
    mask = source["access"] & edge["access"] & (1 | 1024)
    if not mask:
        return {"status": "REJECTED_NO_SHARED_VEHICLE_MODE", "commonVehicleModes": 0}
    xlat, xlon = source["endLat"], source["endLon"]
    approach = source.get("approach")
    if (not isinstance(approach, list) or len(approach) != 2 or
            any(type(v) not in (int, float) or not math.isfinite(v) for v in approach)):
        return {"status": "UNRESOLVED_SOURCE_APPROACH_MISSING", "commonVehicleModes": mask}
    metres_lon = 111320.0 * math.cos(math.radians(xlat))
    def xy(coord):
        return ((coord[1] - xlon) * metres_lon, (coord[0] - xlat) * 111320.0)
    a_approach = Point(xy(approach))
    x = Point(0, 0)
    b = LineString([xy(vertex) for vertex in receiver["directedShape"]])
    if b.length <= 0:
        return {"status": "UNRESOLVED_B_GEOMETRY_DEGENERATE", "commonVehicleModes": mask}
    x_dist = b.distance(x)
    approach_dist = b.distance(a_approach)
    x_along = b.project(x)
    approach_along = b.project(a_approach)
    remaining = b.length - x_along
    # Compiled Valhalla original shape nodes are stored at ~1e-7 degrees.
    # Two-point overlap means far more than near proximity of X alone.
    strict_overlap = x_dist <= 0.75 and approach_dist <= 0.75
    travelled = x_along - approach_along
    source_segment_len = a_approach.distance(x)
    if strict_overlap and travelled <= -0.5:
        status = "REJECTED_OPPOSITE_DIRECTED_SHAPE"
    elif strict_overlap and travelled >= 1.0 and source_segment_len >= 1.0:
        if (source["layer"] != edge["layer"] or
                source["bridge"] != edge["bridge"] or
                source["tunnel"] != edge["tunnel"]):
            status = "UNRESOLVED_NATIVE_LEVEL_OR_STRUCTURE_CONFLICT"
        elif remaining < 1.0:
            status = "B_PREDECESSOR_ENDS_AT_X_NEEDS_NATIVE_SUCCESSOR"
        else:
            status = "MATCHED_DIRECTED_SOURCE_GEOMETRY_OVERLAP"
    else:
        status = "UNRESOLVED_NO_DIRECTED_SOURCE_OVERLAP"
    return {"status": status, "commonVehicleModes": mask,
            "distanceXMetres": round(x_dist, 3),
            "distanceSourceApproachMetres": round(approach_dist, 3),
            "directedOverlapProgressMetres": round(travelled, 3),
            "receiverRemainingMetresAfterX": round(remaining, 3),
            "sameRoadUse": source["roadUse"] == edge["roadUse"],
            "sameRoadClass": source["roadClass"] == edge["roadClass"],
            "sameLayerBridgeTunnel": (source["layer"], source["bridge"], source["tunnel"]) ==
                                     (edge["layer"], edge["bridge"], edge["tunnel"])}


def correlate_verified_source_candidates(*, source_candidates: list[dict],
                                          source_observations: list[dict],
                                          receiver_observations: list[dict],
                                          receiver_predecessor_observations: dict[int, dict] | None = None) -> dict:
    """One source terminal record per original A directed GraphId; preserve all B alternatives."""
    if not (len(source_candidates) == len(source_observations) == len(receiver_observations)):
        raise ValueError("Incomplete original A-X-B candidate lookups")
    result = []
    totals = {}
    receiver_predecessor_observations = receiver_predecessor_observations or {}
    for candidate, a, b in zip(source_candidates, source_observations, receiver_observations):
        gid = candidate["sourceFinalCandidateGraphId"]
        original = a.get("source", {})
        if (a.get("kind") != "local-continuations" or original.get("graphId") != gid or
                candidate.get("nativeGraphLocalTerminalProof") != "VERIFIED" or
                original.get("endNodeGraphId") != candidate.get("endNodeGraphId") or
                original.get("access") != candidate.get("access") or
                any(abs(original[k] - candidate[k]) > 1e-7 for k in ("endLat", "endLon")) or
                b.get("sourceGraphId") != gid):
            raise ValueError("Original A terminal proof/identity changed before receiver matching")
        original_terminal_modes = native_terminal_modes_from_adjacency(a)
        proven = candidate.get('originalNativeLocalProof', {})
        terminal_modes = candidate.get('terminalVehicleModes')
        if (type(terminal_modes) is not int or terminal_modes <= 0 or
                (terminal_modes & ~original_terminal_modes) != 0 or
                proven.get('terminalModes') != original_terminal_modes or
                proven.get('endNodeGraphId') != original['endNodeGraphId'] or
                proven.get('outgoingOriginalDirectedGraphIds') != [
                    entry['edge']['graphId'] for entry in a['options']] or
                proven.get('hierarchyPeersIncluded') is not True):
            raise ValueError('Original A independently recomputed native terminal modes/proof mismatch')
        alternatives = []
        for row in b["originalBDirectedEdges"]:
            verdict = classify_original_b_directional_overlap(original, row)
            entry = {"receiverDirectedGraphId": row["edge"]["graphId"],
                     "receiverNativeRoadClass": row["edge"]["roadClass"],
                     "receiverNativeRoadUse": row["edge"]["roadUse"],
                     "receiverNativeLayer": row["edge"]["layer"],
                     "receiverNativeBridge": row["edge"]["bridge"],
                     "receiverNativeTunnel": row["edge"]["tunnel"],
                     "originalReceiverAccess": row["edge"]["access"], **verdict}
            alternatives.append(entry)
        overlap = [x for x in alternatives
                   if x["status"] == "MATCHED_DIRECTED_SOURCE_GEOMETRY_OVERLAP"]
        upstream = [x for x in alternatives
                    if x["status"] == "B_PREDECESSOR_ENDS_AT_X_NEEDS_NATIVE_SUCCESSOR"]
        b_successors = {}
        b_predecessor_ids = []
        b_continuation_uncertainties = []
        for predecessor in upstream:
            predecessor_gid = predecessor['receiverDirectedGraphId']
            b_predecessor_ids.append(predecessor_gid)
            b_local = receiver_predecessor_observations.get(predecessor_gid)
            if b_local is None:
                b_continuation_uncertainties.append({
                    'receiverPredecessorGraphId': predecessor_gid,
                    'reason': 'MISSING_ORIGINAL_B_NATIVE_NODE_READBACK'})
                continue
            b_source = b_local['source']
            if (b_source['graphId'] != predecessor_gid or
                    abs(b_source['endLat'] - candidate['endLat']) > 1e-5 or
                    abs(b_source['endLon'] - candidate['endLon']) > 1e-5):
                raise ValueError('Original B native predecessor does not end at the exact source X')
            for opt in b_local['options']:
                successor = opt['edge']
                succid = successor['graphId']
                if not opt['viaHierarchy'] and opt['fromNodeGraphId'] != b_source['endNodeGraphId']:
                    raise ValueError('Wrong native B junction outgoing from-node GraphId')
                statuses = opt['nativeImmediateCosting']
                common_modes = 0
                if (statuses['car'] == 'ALLOWED_NATIVE_IMMEDIATE' and
                        candidate['terminalVehicleModes'] & 1 and successor['access'] & 1):
                    common_modes |= 1
                if (statuses['motorcycle'] == 'ALLOWED_NATIVE_IMMEDIATE' and
                        candidate['terminalVehicleModes'] & 1024 and successor['access'] & 1024):
                    common_modes |= 1024
                if common_modes:
                    value = b_successors.setdefault(succid, {
                        'receiverDirectedGraphId': succid,
                        'sharedVehicleModes': 0,
                        'fromNativeBPredecessorGraphIds': [],
                        'receiverNativeRoadClass': successor['roadClass'],
                        'receiverNativeRoadUse': successor['roadUse'],
                        'receiverNativeLayer': successor['layer'],
                        'receiverNativeBridge': successor['bridge'],
                        'receiverNativeTunnel': successor['tunnel'],
                        'status': 'VERIFIED_B_ORIGINAL_SAME_NODE_LEGAL_BRANCH'})
                    value['sharedVehicleModes'] |= common_modes
                    if predecessor_gid not in value['fromNativeBPredecessorGraphIds']:
                        value['fromNativeBPredecessorGraphIds'].append(predecessor_gid)
                if (any(state.startswith('UNRESOLVED_') for state in statuses.values())):
                    b_continuation_uncertainties.append({
                        'receiverPredecessorGraphId': predecessor_gid,
                        'receiverDirectedGraphId': succid,
                        'car': statuses['car'], 'motorcycle': statuses['motorcycle']})
        if overlap:
            for edge in overlap:
                succid = edge['receiverDirectedGraphId']
                if succid not in b_successors:
                    b_successors[succid] = {
                        'receiverDirectedGraphId': succid,
                        'sharedVehicleModes': edge['commonVehicleModes'] &
                                              candidate['terminalVehicleModes'],
                        'fromNativeBPredecessorGraphIds': [],
                        'status': 'VERIFIED_B_DIRECTED_INTERIOR_SOURCE_OVERLAP'}
        if b_continuation_uncertainties:
            status = 'B_NODE_CONTINUATION_PARTIALLY_UNRESOLVED'
        elif len(b_successors) > 0 and len(b_predecessor_ids) <= 1 and len(overlap) <= 1:
            status = 'B_NATIVE_DIRECTIONAL_CONTINUATIONS_IDENTIFIED'
        elif len(b_successors) > 0:
            status = 'B_MULTIPLE_OVERLAPPING_PREDECESSORS_UNRESOLVED'
        elif upstream:
            status = 'NO_PROVEN_B_NATIVE_OUTGOING_AFTER_X'
        else:
            status = 'NO_PROVEN_CORRESPONDING_B_DIRECTION'
        # These are B edge correspondence observations ONLY; no complete
        # physical-road source census or Android consumer verification.
        totals[status] = totals.get(status, 0) + 1
        result.append({"sourceFinalDirectedGraphId": gid,
            "sourceOriginalEndNodeGraphId": original["endNodeGraphId"],
            "x": {"lat": candidate["endLat"], "lon": candidate["endLon"]},
            "sourceVehicleModes": candidate["terminalVehicleModes"],
            "sourceCutGraphIds": candidate["sourceCutGraphIds"],
            "sourcePhysicalRoadFinalCompleteness": "NOT_VERIFIED",
            "receiverCorrelationStatus": status,
            "confirmedGeometricOverlapOptions": [v["receiverDirectedGraphId"] for v in overlap],
            "correspondingBPredecessorAtXGraphIds": b_predecessor_ids,
            "receivingNativeDirectedContinuationOptions": [b_successors[k] for k in sorted(b_successors)],
            "receivingNativeUnresolvedContinuations": b_continuation_uncertainties,
            "receiverDirectedCandidatesAtX": alternatives})
    return {"sourceTerminalCandidatesCorrelated": len(result),
            "nativeReceiverStatusCounts": totals,
            "sourceToReceiverCandidates": result,
            "sourcePhysicalRoadDirectionCompleteness": "NOT_VERIFIED",
            "androidFullJourneyValidation": "NOT_RUN",
            "productionPublication": "BLOCKED"}





def recover_missing_source_terminal_candidates(*, prior: dict,
                                               read_local, source_cut_tile_ids: set[int],
                                               receiver_footprint) -> dict:
    """One strictly bounded extra A native hop for roots missing a final.

    This is reconciliation inside the existing D-017 A→X→B producer, NOT a
    second discovery system. The only seeds are the previous source-cut roots
    having NO terminal candidate already recorded. Read immediate original
    A successors, then their immediate incident edges, and STOP; no recursion
    or outward network scan. Preserve all forks and uncertain modes.
    """
    originals = prior['terminalCandidatesByExactSourceGraphId']
    existing = {c['sourceFinalCandidateGraphId']: c for c in originals}
    linked = {gid for c in originals for gid in c['sourceCutGraphIds']}
    unresolved = {r['sourceCutGraphId']: r for r in
                  prior['unresolvedNonterminalSourceCutObservations']}
    all_roots = {row['graphId'] for row in prior['originalPairedCutDirectedEvidence']
                 if row['originalCutOrientation'] in ('OUTWARD', 'AMBIGUOUS')}
    if (len(existing) != len(originals) or not linked <= all_roots or
            len(unresolved) != prior['nonterminalSourceCutCount']):
        raise ValueError('Cannot reconcile duplicate/missing original source root identities')
    missing = sorted(all_roots - linked)
    if any(root not in unresolved for root in missing):
        raise ValueError('Source missing-root observation not in original native nonterminal evidence')

    def allowed_modes(status: dict) -> int:
        return ((1 if status.get('car') == 'ALLOWED_NATIVE_IMMEDIATE' else 0) |
                (1024 if status.get('motorcycle') == 'ALLOWED_NATIVE_IMMEDIATE' else 0))

    first_paths: dict[int, list[tuple[int, int, dict]]] = {}
    for root_gid in missing:
        for option in unresolved[root_gid]['immediateNativeOutgoing']:
            vehicle_modes = (allowed_modes(option['nativeImmediateCosting']) &
                             option['nativeVehicleModes'] &
                             unresolved[root_gid]['nativeVehicleModes'])
            if not (vehicle_modes and option['eligibleOriginalForward'] and
                    option['inSelectedSourceTiles'] and not option['viaHierarchy']):
                continue
            first_paths.setdefault(option['graphId'], []).append(
                (root_gid, vehicle_modes, option))
    first_ids = sorted(first_paths)
    first_records = read_local(first_ids) if first_ids else []
    if len(first_records) != len(first_ids):
        raise ValueError('Incomplete first immediate original A successor readback')

    second_paths: dict[int, list[tuple[int, int, int]]] = {}
    second_native_identity: dict[int, dict] = {}
    for gid, observed in zip(first_ids, first_records):
        validate_immediate_native_observation(observed)
        native = observed['source']
        if native['graphId'] != gid:
            raise ValueError('Unexpected original first A successor identity')
        for root_id, vehicle_modes, original_option in first_paths[gid]:
            if ((native['access'] & unresolved[root_id]['nativeVehicleModes'] & 1025) !=
                    original_option['nativeVehicleModes'] or
                    native['endNodeGraphId'] != original_option['nativeEndNodeGraphId']):
                raise ValueError('Previous A cutoff successor changed on original graph readback')
            # Exactly one more original native edge from THIS immediate node;
            # positive car/motorcycle costing is required at both transitions.
            for option in observed['options']:
                edge = option['edge']
                modes = allowed_modes(option['nativeImmediateCosting']) & vehicle_modes & edge['access']
                if (not modes or option['viaHierarchy'] or edge['shortcut'] or
                        edge['transit'] or
                        (edge['graphId'] & ((1 << 25) - 1)) not in source_cut_tile_ids):
                    continue
                if edge['graphId'] in second_native_identity:
                    old = second_native_identity[edge['graphId']]
                    if any(old[k] != edge[k] for k in ('endNodeGraphId', 'access',
                             'endLat', 'endLon', 'roadClass', 'roadUse',
                             'layer', 'bridge', 'tunnel')):
                        raise ValueError('Conflicting original A second-hop GraphId identity')
                else:
                    second_native_identity[edge['graphId']] = edge
                second_paths.setdefault(edge['graphId'], []).append((root_id, gid, modes))

    second_ids = sorted(second_paths)
    second_records = read_local(second_ids) if second_ids else []
    if len(second_records) != len(second_ids):
        raise ValueError('Incomplete bounded second original A successor readback')
    newly_verified: dict[int, dict] = {}
    links: list[dict] = []
    for gid, observed in zip(second_ids, second_records):
        validate_immediate_native_observation(observed)
        source = observed['source']
        if source['graphId'] != gid:
            raise ValueError('Unexpected original second-hop A GraphId')
        expected = second_native_identity[gid]
        if any(source[k] != expected[k] for k in ('endNodeGraphId', 'access',
                'endLat', 'endLon', 'roadClass', 'roadUse', 'layer', 'bridge', 'tunnel')):
            raise ValueError('Original A second-hop directed edge changed on native readback')
        terminal_modes = native_terminal_modes_from_adjacency(observed)
        if (not terminal_modes or not receiver_footprint.covers(Point(
                source['endLon'], source['endLat']))):
            continue
        proof = {"method": "INDEPENDENT_ORIGINAL_END_NODE_ADJACENCY",
                 "endNodeGraphId": source['endNodeGraphId'],
                 "outgoingOriginalDirectedGraphIds": [row['edge']['graphId']
                     for row in observed['options']],
                 "hierarchyPeersIncluded": True,
                 "terminalModes": terminal_modes}
        if gid in existing:
            original = existing[gid]
            if (original['endNodeGraphId'] != source['endNodeGraphId'] or
                    original['access'] != source['access'] or
                    original['endLat'] != source['endLat'] or
                    original['endLon'] != source['endLon'] or
                    original['originalNativeLocalProof'] != proof):
                raise ValueError('Existing original A terminal candidate differs from exact native edge')
        else:
            newly_verified[gid] = {"sourceFinalCandidateGraphId": gid,
                "terminalVehicleModes": 0, "access": source['access'],
                "endLat": source['endLat'], "endLon": source['endLon'],
                "endNodeGraphId": source['endNodeGraphId'],
                "sourceCutGraphIds": [],
                "selectionKinds": ["NATIVE_TERMINAL_TWO_BOUNDED_HOPS_UNPROVEN"],
                "originalNativeLocalProof": proof,
                "nativeGraphLocalTerminalProof": "VERIFIED",
                "physicalRoadFinalCompleteness": "NOT_VERIFIED"}
        for root_gid, via_gid, available in second_paths[gid]:
            connected_modes = available & terminal_modes
            if not connected_modes:
                continue
            links.append({"originalSourceCutGraphId": root_gid,
                          "firstOriginalNativeSuccessorGraphId": via_gid,
                          "terminalOriginalGraphId": gid,
                          "staticallyAllowedVehicleModes": connected_modes,
                          "sourcePhysicalRoadIdentity": "NOT_VERIFIED"})
            if gid in newly_verified:
                candidate = newly_verified[gid]
                candidate['terminalVehicleModes'] |= connected_modes
                if root_gid not in candidate['sourceCutGraphIds']:
                    candidate['sourceCutGraphIds'].append(root_gid)

    remaining = set(missing) - {link['originalSourceCutGraphId'] for link in links}
    return {"priorMissingSourceRootCount": len(missing),
            "firstOriginalNativeSuccessorsReopened": len(first_ids),
            "secondOriginalNativeSuccessorsReopened": len(second_ids),
            "newOriginalNativeTerminalCandidates": [newly_verified[gid]
                                                      for gid in sorted(newly_verified)],
            "boundedExistingAndNewTerminalLinks": links,
            "rootsWithBoundedNativeTerminalLinks": len(set(missing) - remaining),
            "rootsStillWithoutTerminalWithinTwoHops": len(remaining),
            "sourceCoverageProven": False,
            "additionalGraphExplorationAllowed": False}


def match_original_receiver_to_file(*, source_evidence_path: Path,
                                   manifest_path: Path, index_path: Path,
                                   buffer_path: Path, valhalla_config_path: Path,
                                   receiver_manifest_path: Path,
                                   receiver_index_path: Path,
                                   receiver_buffer_path: Path,
                                   receiver_valhalla_config_path: Path,
                                   binary: Path, output_path: Path,
                                   bounded_missing_source_recovery: bool = False) -> dict:
    """D-017 A final candidate → exact original X → compiled B directed edge.

    Match B at X without finding arbitrary Y, best-road selection or a graph
    scan. Keep source incompleteness visible and publication hard-blocked.
    """
    if output_path.exists():
        raise ValueError("Original A-X-B matching evidence exists; refusing overwrite")
    pair = verified_shared_cut(source_manifest=manifest_path,
        source_index=index_path, source_buffer=buffer_path,
        receiver_manifest=receiver_manifest_path,
        receiver_index=receiver_index_path, receiver_buffer=receiver_buffer_path)
    opener = gzip.open if source_evidence_path.suffix == '.gz' else open
    with opener(source_evidence_path, 'rt', encoding='utf-8') as reader:
        prior = json.load(reader)
    if (prior.get('schema') != 'roadpilot.f8-paired-source-local-terminal-candidates' or
            prior.get('schemaVersion') != 5 or
            prior.get('fromRegionId') != pair['source']['regionId'] or
            prior.get('toRegionId') != pair['receiver']['regionId'] or
            prior.get('fromGraphFingerprint') != pair['source']['graphFingerprint'] or
            prior.get('toGraphFingerprint') != pair['receiver']['graphFingerprint'] or
            prior.get('fromBufferFingerprint') != pair['sourceBufferFingerprint'] or
            prior.get('toBufferFingerprint') != pair['receiverBufferFingerprint'] or
            prior.get('fromGraphIndexFingerprint') != pair['sourceIndexFingerprint'] or
            prior.get('toGraphIndexFingerprint') != pair['receiverIndexFingerprint'] or
            prior.get('reciprocalBoundaryFingerprints') != pair['reciprocalBoundaryFingerprints'] or
            prior.get('sourcePhysicalRoadDirectionCompleteness') != 'NOT_VERIFIED' or
            prior.get('productionPublication') != 'BLOCKED'):
        raise ValueError('Original native source pair evidence does not match current immutable archives')
    candidates = prior['terminalCandidatesByExactSourceGraphId']
    if (not isinstance(candidates, list) or len(candidates) == 0 or
            len({r['sourceFinalCandidateGraphId'] for r in candidates}) != len(candidates)):
        raise ValueError('Missing unique original A terminal candidates')
    original_candidate_count = len(candidates)
    selected_ids = {int(row['level']) | int(row['tileIndex']) << 3
                    for row in pair['selectedSourceTiles']}
    extra_source = None
    if bounded_missing_source_recovery:
        def read_targeted(gids):
            return inspect_local_source_edges(manifest_path=manifest_path,
                index_path=index_path, buffer_path=buffer_path,
                valhalla_config_path=valhalla_config_path, binary=binary,
                source_graph_ids=gids, allowed_tile_ids=selected_ids,
                evaluate_native_costing=True)
        extra_source = recover_missing_source_terminal_candidates(
            prior=prior, read_local=read_targeted,
            source_cut_tile_ids=selected_ids,
            receiver_footprint=shape(load_json(receiver_buffer_path)['geometry']))
        # Original source records remain immutable; only add justified
        # potential root link IDs in the in-memory native correlation stage.
        candidates = [{**c, 'sourceCutGraphIds': list(c['sourceCutGraphIds'])}
                      for c in candidates]
        candidate_by_gid = {c['sourceFinalCandidateGraphId']:c for c in candidates}
        for link in extra_source['boundedExistingAndNewTerminalLinks']:
            original = candidate_by_gid.get(link['terminalOriginalGraphId'])
            if original is not None and link['originalSourceCutGraphId'] not in original['sourceCutGraphIds']:
                original['sourceCutGraphIds'].append(link['originalSourceCutGraphId'])
        candidates += extra_source['newOriginalNativeTerminalCandidates']
    ids = [r['sourceFinalCandidateGraphId'] for r in candidates]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate original source final GraphIds after bounded recovery')
    if any((gid & ((1 << 25) - 1)) not in selected_ids for gid in ids):
        raise ValueError('A terminal candidate outside verified source cutoff tiles')
    # Always re-open A candidate originals before comparing any receiving B
    # edge, including one-hop candidates whose initial root is elsewhere.
    source_native = inspect_local_source_edges(manifest_path=manifest_path,
        index_path=index_path, buffer_path=buffer_path,
        valhalla_config_path=valhalla_config_path, binary=binary,
        source_graph_ids=ids, allowed_tile_ids=selected_ids,
        evaluate_native_costing=True)
    b_native = indexed_receiver_edges_at_x(receiver_manifest_path=receiver_manifest_path,
        receiver_index_path=receiver_index_path,
        receiver_buffer_path=receiver_buffer_path,
        receiver_valhalla_config=receiver_valhalla_config_path,
        native_binary=binary, source_candidates=candidates)
    # B matching at a native X endpoint often requires one zero-distance
    # node transition after the original B incoming edge. Query exactly
    # those original B predecessor GraphIds, not the wider receiving graph.
    exact_b_predecessors = set()
    for candidate, a_record, b_record in zip(candidates, source_native, b_native):
        for receiver_option in b_record['originalBDirectedEdges']:
            assessed = classify_original_b_directional_overlap(
                a_record['source'], receiver_option)
            if assessed['status'] == 'B_PREDECESSOR_ENDS_AT_X_NEEDS_NATIVE_SUCCESSOR':
                exact_b_predecessors.add(receiver_option['edge']['graphId'])
    b_local = read_b_native_immediate_continuations(
        receiver_manifest_path=receiver_manifest_path,
        receiver_index_path=receiver_index_path,
        receiver_buffer_path=receiver_buffer_path,
        receiver_valhalla_config=receiver_valhalla_config_path,
        native_binary=binary, original_b_predecessor_graph_ids=list(exact_b_predecessors))
    result = correlate_verified_source_candidates(source_candidates=candidates,
        source_observations=source_native, receiver_observations=b_native,
        receiver_predecessor_observations=b_local)
    result['originalBPredecessorsIndependentlyReadBackAtX'] = len(b_local)
    result['originalVerifiedSourceTerminalCandidateCount'] = original_candidate_count
    if extra_source is not None:
        result['boundedMissingSourceRecovery'] = extra_source
    # No new source search: exact original A cutoff-root coverage accounting
    # from the retained root IDs on every already verified terminal candidate.
    # A B option does NOT prove source physical-road completeness.
    linked = {}
    for item in result['sourceToReceiverCandidates']:
        for root in item['sourceCutGraphIds']:
            linked.setdefault(root, []).append(item)
    coverage = []
    counts = {}
    for cut_row in prior['originalPairedCutDirectedEvidence']:
        if cut_row['originalCutOrientation'] not in ('OUTWARD', 'AMBIGUOUS'):
            continue
        gid = cut_row['graphId']
        related = linked.get(gid, [])
        good = [row for row in related if row['receivingNativeDirectedContinuationOptions']]
        if good:
            state = 'ROOT_HAS_NATIVE_RECEIVER_OPTIONS_SOURCE_LINEAGE_UNPROVEN'
        elif related:
            state = 'ROOT_TERMINAL_CANDIDATE_NO_CONFIRMED_RECEIVER'
        else:
            state = ('ROOT_NO_TERMINAL_CANDIDATE_WITHIN_TWO_BOUNDED_HOPS'
                     if bounded_missing_source_recovery else
                     'ROOT_NO_TERMINAL_CANDIDATE_WITHIN_ONE_NATIVE_HOP')
        counts[state] = counts.get(state, 0) + 1
        coverage.append({'originalSourceCutGraphId': gid,
            'originalNativeTerminalModes': cut_row['nativeTerminalModes'],
            'boundedRelatedAOriginalFinalGraphIds': [
                row['sourceFinalDirectedGraphId'] for row in related],
            'boundedOriginalSourceRootStatus': state,
            'physicalRoadDirectionCompleteness': 'NOT_VERIFIED'})
    if len(coverage) != prior['outwardOrAmbiguousSourceCutCount'] or len({
            row['originalSourceCutGraphId'] for row in coverage}) != len(coverage):
        raise ValueError('Source cut-root coverage incomplete or repeated')
    result['originalSourceCutRootCoverageCounts'] = counts
    result['originalSourceCutRootCoverage'] = coverage
    # Before writing, recompute immutable Graph A and B archive/buffer/index
    # proofs. The output cannot be promoted to production while any source
    # boundary road or Android consumption remains unverified.
    verified_shared_cut(source_manifest=manifest_path,
        source_index=index_path, source_buffer=buffer_path,
        receiver_manifest=receiver_manifest_path,
        receiver_index=receiver_index_path, receiver_buffer=receiver_buffer_path)
    unresolved_roots = prior.get('unresolvedNonterminalSourceCutObservations')
    if (not isinstance(unresolved_roots, list) or
            len(unresolved_roots) != prior['nonterminalSourceCutCount']):
        raise ValueError('Original source unresolved roots missing from coverage gate')
    output = {'schema': 'roadpilot.f8-paired-native-receiver-correlation-evidence',
        'schemaVersion': 1,
        'sourceEvidenceSha256': 'sha256:' + sha256(source_evidence_path),
        'sourceGraphFingerprint': pair['source']['graphFingerprint'],
        'receiverGraphFingerprint': pair['receiver']['graphFingerprint'],
        'sourceRegionId': pair['source']['regionId'],
        'receiverRegionId': pair['receiver']['regionId'],
        'sourceBufferFingerprint': pair['sourceBufferFingerprint'],
        'receiverBufferFingerprint': pair['receiverBufferFingerprint'],
        'sourceIndexFingerprint': pair['sourceIndexFingerprint'],
        'receiverIndexFingerprint': pair['receiverIndexFingerprint'],
        'reciprocalBoundaryFingerprints': pair['reciprocalBoundaryFingerprints'],
        'sourceUnresolvedNonterminalRootGraphIds': [
            r['sourceCutGraphId'] for r in unresolved_roots],
        'sourceUnresolvedNonterminalRootCount': len(unresolved_roots),
        'sourceFinalCandidateCount': len(candidates),
        **result}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=output_path.parent, delete=False) as temp:
        staged = Path(temp.name)
    try:
        writer = gzip.open if output_path.suffix == '.gz' else open
        with writer(staged, 'wt', encoding='utf-8') as stream:
            json.dump(output, stream, ensure_ascii=False, separators=(',', ':'))
            stream.write('\n')
        if output_path.exists():
            raise ValueError('Original B correlation output appeared during verification')
        staged.replace(output_path)
    finally:
        staged.unlink(missing_ok=True)
    return {'sourceFinalCandidateCount': len(candidates),
        'sourceUnresolvedNonterminalRootCount': len(unresolved_roots),
        'nativeReceiverStatusCounts': result['nativeReceiverStatusCounts'],
        'productionPublication': 'BLOCKED'}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--graph-index", type=Path, required=True)
    parser.add_argument("--buffer-geojson", type=Path, required=True)
    parser.add_argument("--valhalla-config", type=Path, required=True)
    parser.add_argument("--native-binary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cut-only", action="store_true",
                        help="Only original directed edges intersecting the exact 25-km buffered cutoff; seeds, not proven road finals")
    parser.add_argument("--resolve-cut", action="store_true",
                        help="Source/receiver shared 25-km cutoff; terminal first, immediate native topology only, never graph traversal")
    parser.add_argument("--receiver-manifest", type=Path)
    parser.add_argument("--receiver-graph-index", type=Path)
    parser.add_argument("--receiver-buffer-geojson", type=Path)
    parser.add_argument("--match-receiver", action="store_true",
                        help="Read previously verified A terminal candidates and match original B directed edges at the exact source endpoint X")
    parser.add_argument("--source-evidence", type=Path,
                        help="Previously completed --resolve-cut original A terminal candidate evidence")
    parser.add_argument("--receiver-valhalla-config", type=Path,
                        help="Compiled Valhalla B routing configuration for its exact original archive")
    parser.add_argument("--bounded-missing-source-recovery", action="store_true",
                        help="With --match-receiver only: reopen up to one additional native source hop for previously unmatched source cutoff roots; never a general graph walk")
    args = parser.parse_args()
    if args.bounded_missing_source_recovery and not args.match_receiver:
        parser.error("--bounded-missing-source-recovery requires --match-receiver")
    if sum((args.cut_only, args.resolve_cut, args.match_receiver)) > 1:
        parser.error("Select only one source/receiving inspection action")
    if args.match_receiver:
        if not all((args.receiver_manifest, args.receiver_graph_index,
                    args.receiver_buffer_geojson, args.source_evidence,
                    args.receiver_valhalla_config)):
            parser.error("--match-receiver requires original source evidence and exact receiver inputs")
        output = match_original_receiver_to_file(source_evidence_path=args.source_evidence,
            manifest_path=args.manifest, index_path=args.graph_index,
            buffer_path=args.buffer_geojson, valhalla_config_path=args.valhalla_config,
            binary=args.native_binary, output_path=args.output,
            receiver_manifest_path=args.receiver_manifest,
            receiver_index_path=args.receiver_graph_index,
            receiver_buffer_path=args.receiver_buffer_geojson,
            receiver_valhalla_config_path=args.receiver_valhalla_config,
            bounded_missing_source_recovery=args.bounded_missing_source_recovery)
        print(f'originalSourceFinalCandidates={output["sourceFinalCandidateCount"]} '
              f'unresolvedSourceRoots={output["sourceUnresolvedNonterminalRootCount"]} '
              f'receiverStatusCounts={output["nativeReceiverStatusCounts"]} '
              'sourceCompleteness=NOT_VERIFIED publication=BLOCKED')
    elif args.resolve_cut:
        if not all((args.receiver_manifest, args.receiver_graph_index,
                    args.receiver_buffer_geojson)):
            parser.error("--resolve-cut requires receiver manifest, graph index and original 25-km buffer")
        output = resolve_original_cut_to_file(manifest_path=args.manifest,
            index_path=args.graph_index, buffer_path=args.buffer_geojson,
            valhalla_config_path=args.valhalla_config,
            binary=args.native_binary, output_path=args.output,
            receiver_manifest_path=args.receiver_manifest,
            receiver_index_path=args.receiver_graph_index,
            receiver_buffer_path=args.receiver_buffer_geojson)
        print(f'pair={output["fromRegionId"]}->{output["toRegionId"]} '
              f'selectedTiles={output["selectedOriginalSourceBoundaryTiles"]} '
              f'pairCutDirectedEdges={output["originalDirectedCutEdgeCount"]} '
              f'terminalRoots={output["directNativeTerminalRootCount"]} '
              f'nonterminalUnresolved={output["nonterminalSourceCutCount"]} '
              'physicalCompleteness=NOT_VERIFIED publication=BLOCKED')
    else:
        output = extract_to_file(manifest_path=args.manifest, index_path=args.graph_index,
                                 buffer_path=args.buffer_geojson,
                                 valhalla_config_path=args.valhalla_config,
                                 binary=args.native_binary, output_path=args.output,
                                 cut_only=args.cut_only)
        print(f'region={output["regionId"]} selectedTiles={output["selectedBoundaryTileCount"]} '
              f'terminalCandidates={output["nativeTerminalCandidateCount"]} '
              f'unresolved={output["unresolvedJunctionDirectedEdgeCount"]} '
              'publication=BLOCKED')


if __name__ == "__main__":
    main()
