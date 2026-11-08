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

from shapely.geometry import box, shape

SCHEMA = "roadpilot.f8-region-original-boundary-source"
NATIVE_PROTOCOL = "roadpilot.f8-native-source-4"
VALID_MODES = 0  # Native executable owns the exact Valhalla access bit masks.


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


def select_cut_tiles(graph_index: dict, buffered: dict) -> list[dict]:
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
    outline = geo.boundary
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


def _direction_delta(source: dict, target: dict) -> float | None:
    """Angular bend between two *original directed* native road shapes.

    Does not establish road identity by itself, and is never used to discard
    a different native branch from the candidate's evidence.
    """
    a = source.get("approach")
    b = target.get("departure")
    if not isinstance(a, list) or not isinstance(b, list) or len(a) != 2 or len(b) != 2:
        return None
    x = (source["endLat"], source["endLon"])
    y = (target["startLat"], target["startLon"])
    if any(not isinstance(z, (float, int)) or not math.isfinite(z)
           for z in (*a, *b, *x, *y)):
        raise ValueError("Invalid native continuation direction")
    if abs(x[0] - y[0]) > 0.00001 or abs(x[1] - y[1]) > 0.00001:
        # Source/receiver X must never be replaced by a nearby GPS point;
        # local hierarchy peers may have different endpoints: unresolved.
        return None
    lat = math.radians(x[0])
    east_scale = math.cos(lat)
    v1 = ((x[1] - a[1]) * east_scale, x[0] - a[0])
    v2 = ((b[1] - y[1]) * east_scale, b[0] - y[0])
    mag = math.hypot(*v1) * math.hypot(*v2)
    if mag < 1e-16:
        return None
    cos_a = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / mag))
    return math.degrees(math.acos(cos_a))


def classify_local_continuations(observation: dict, mode: int) -> dict:
    """Classify one-step original topology without ever dropping branch IDs.

    A sole straight, structurally consistent outgoing native edge is locally
    continuous. Multiple forward choices retain all branches even when one
    is uniquely aligned; that alignment is NOT a global road identity proof.
    This never makes a receiver match or declares a catalog complete.
    """
    if mode not in (1, 1024):
        raise ValueError("Only native Valhalla auto/motorcycle mode bits supported")
    if observation.get("kind") != "local-continuations":
        raise ValueError("Missing native local-continuation evidence")
    source = observation["source"]
    if not source["access"] & mode:
        return {"status": "MODE_NOT_ALLOWED", "nextGraphId": None, "allForwardGraphIds": []}
    candidates = []
    seen = set()
    for row in observation["options"]:
        peer = row["edge"]
        gid = peer["graphId"]
        if gid in seen:
            raise ValueError("Invalid or duplicate native local continuation")
        seen.add(gid)
        if peer["access"] & mode:
            candidates.append((peer, _direction_delta(source, peer)))
    ids = sorted(p["graphId"] for p, _ in candidates)
    result = {"status": "UNRESOLVED", "nextGraphId": None,
              "allForwardGraphIds": ids}
    if not candidates:
        return {**result, "status": "NATIVE_GRAPH_TERMINAL"}
    # In native hierarchy, a shortcut or mismatched-layer edge might be a
    # shadow representation; do not treat it as a proved continuation or
    # eliminate it silently.
    if any(peer["shortcut"] or angle is None for peer, angle in candidates):
        return result
    same_structure = lambda peer: (peer["roadClass"] == source["roadClass"]
                                   and peer["roadUse"] == source["roadUse"]
                                   and peer["layer"] == source["layer"]
                                   and peer["bridge"] == source["bridge"]
                                   and peer["tunnel"] == source["tunnel"])
    # A hairpin, class change, grade separation or fork is not automatically
    # the same physical road. No name/way ID or arbitrary GPS snapping.
    if len(candidates) == 1:
        peer, angle = candidates[0]
        if same_structure(peer) and angle <= 55.0:
            return {**result, "status": "UNIQUE_LOCAL_FORWARD",
                    "nextGraphId": peer["graphId"]}
        return result
    aligned = [(peer, angle) for peer, angle in candidates
               if same_structure(peer) and angle <= 20.0]
    if len(aligned) == 1 and all(
            other["graphId"] == aligned[0][0]["graphId"] or angle >= 65.0
            for other, angle in candidates):
        return {**result, "status": "BRANCH_ALIGNED_FORWARD_UNPROVEN",
                "nextGraphId": aligned[0][0]["graphId"]}
    return result


def inspect_local_source_edges(*, manifest_path: Path, index_path: Path,
                               buffer_path: Path, valhalla_config_path: Path,
                               binary: Path, source_graph_ids: list[int]) -> list[dict]:
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
    if not source_graph_ids or any(type(gid) is not int or gid <= 0 or
                                   (gid & ((1 << 25) - 1)) not in original_tiles
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
        run = subprocess.run([str(binary), "--local-continuations", str(cfg), str(ids)],
                             capture_output=True, text=True, check=True, timeout=600)
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
        for mode in (1, 1024):
            classify_local_continuations(record, mode)
    return observations


def resolve_local_source_chains(source_graph_ids: list[int], read_native,
                                selected_tile_graph_ids: set[int]) -> list[dict]:
    """Follow only unambiguous local physical-forward *original* graph links.

    read_native(ids) supplies the same SHA-validated native immediate node
    observations as inspect_local_source_edges. This procedure has no road-name
    or way-id lookup, network route probe, arbitrary cap, or full-network walk.
    A branch is explicitly recorded but is not silently suppressed. Leaving
    the selected 25-km cut tile ring, a loop, or a junction leaves the source
    final INCOMPLETE; it must never be mistaken for a retained final.
    """
    if not source_graph_ids or len(source_graph_ids) != len(set(source_graph_ids)):
        raise ValueError("Need unique original source-cut directed GraphIds")
    mask = (1 << 25) - 1
    def in_cut_scope(gid):
        return type(gid) is int and (gid & mask) in selected_tile_graph_ids
    if any(not in_cut_scope(g) for g in source_graph_ids):
        raise ValueError("Source edge lies outside selected original cutoff tiles")
    cache: dict[int, dict] = {}
    initial = read_native(source_graph_ids)
    if len(initial) != len(source_graph_ids):
        raise ValueError("Incomplete original source continuation observations")
    for gid, row in zip(source_graph_ids, initial):
        if row.get("kind") != "local-continuations" or row["source"]["graphId"] != gid:
            raise ValueError("Original source GraphId observation mismatch")
        cache[gid] = row
    active = []
    for gid in source_graph_ids:
        access = cache[gid]["source"]["access"]
        for mode in (1, 1024):
            if access & mode:
                active.append({"root": gid, "mode": mode, "path": [gid],
                               "branches": []})
    results: dict[tuple[int, int], dict] = {}
    while active:
        missing = list(dict.fromkeys(job["path"][-1] for job in active
                                     if job["path"][-1] not in cache))
        if missing:
            rows = read_native(missing)
            if len(rows) != len(missing):
                raise ValueError("Missing original local continuation graph identities")
            for gid, row in zip(missing, rows):
                if row.get("kind") != "local-continuations" or row["source"]["graphId"] != gid:
                    raise ValueError("Original local continuation GraphId mismatch")
                cache[gid] = row
        pending = []
        for job in active:
            gid = job["path"][-1]
            evidence = classify_local_continuations(cache[gid], job["mode"])
            status = evidence["status"]
            item = {"mode": job["mode"], "path": job["path"],
                    "branchAlternatives": job["branches"],
                    "localCandidateFinalGraphId": None}
            if status == "NATIVE_GRAPH_TERMINAL":
                item.update(status="GRAPH_LOCAL_TERMINAL", localCandidateFinalGraphId=gid)
            elif status in ("UNIQUE_LOCAL_FORWARD", "BRANCH_ALIGNED_FORWARD_UNPROVEN"):
                target = evidence["nextGraphId"]
                if status == "BRANCH_ALIGNED_FORWARD_UNPROVEN":
                    job["branches"] = job["branches"] + [{
                        "atGraphId": gid,
                        "allForwardGraphIds": evidence["allForwardGraphIds"],
                        "alignedButNotProvenGraphId": target}]
                if not in_cut_scope(target):
                    item.update(status="EXITS_CUTOFF_TILE_SCOPE_UNRESOLVED",
                                allForwardGraphIds=evidence["allForwardGraphIds"])
                elif target in job["path"]:
                    item.update(status="CYCLIC_LOCAL_CONTINUATION_UNRESOLVED",
                                allForwardGraphIds=evidence["allForwardGraphIds"])
                else:
                    pending.append({**job, "path": job["path"] + [target]})
                    continue
            else:
                item.update(status="AMBIGUOUS_LOCAL_CONTINUATION",
                            allForwardGraphIds=evidence["allForwardGraphIds"])
            # The next incoming iteration is the only place the updated
            # branch list is reused; preserve it on every terminal outcome.
            item["branchAlternatives"] = job["branches"]
            results[(job["root"], job["mode"])] = item
        active = pending
    final = []
    for gid in source_graph_ids:
        per_mode = [results[(gid, mode)] for mode in (1, 1024)
                    if (gid, mode) in results]
        ids = [x["localCandidateFinalGraphId"] for x in per_mode]
        # Never conflate different mode-local finals or claim uniqueness at
        # a branch. A true global physical-road final remains a later gate.
        one_local = (ids[0] if ids and all(v == ids[0] and v is not None for v in ids)
                     and all(not x["branchAlternatives"] for x in per_mode)
                     else None)
        final.append({"sourceGraphId": gid, "localCandidateFinalGraphId": one_local,
                      "modeResults": per_mode,
                      "physicalRoadFinalCompleteness": "NOT_VERIFIED",
                      "receivingCorrelation": "NOT_STARTED"})
    return final


def consolidate_exact_source_final_ids(resolutions: list[dict]) -> dict:
    """One candidate per identical *original* final GraphId, never per name.

    This is NOT a physical-road equivalence proof: separate original GraphIds
    always remain distinct. Preserve each upstream cut observation and every
    unresolved branch rather than treating a common downstream ID as proof
    that two source roads/branches were identical.
    """
    confirmed: dict[int, dict] = {}
    unresolved = []
    seen_sources: set[int] = set()
    for row in resolutions:
        source_id = row["sourceGraphId"]
        if type(source_id) is not int or source_id in seen_sources:
            raise ValueError("Duplicate source-cut directed GraphId in local final register")
        seen_sources.add(source_id)
        final_id = row.get("localCandidateFinalGraphId")
        if final_id is None:
            unresolved.append(row)
            continue
        if type(final_id) is not int:
            raise ValueError("Invalid exact original source final GraphId")
        if row.get("physicalRoadFinalCompleteness") != "NOT_VERIFIED":
            raise ValueError("Local source grouping cannot certify global road identity")
        item = confirmed.setdefault(final_id, {
            "localCandidateFinalGraphId": final_id,
            "sourceCutGraphIds": [], "sourceCutModePaths": [],
            "physicalRoadFinalCompleteness": "NOT_VERIFIED"})
        item["sourceCutGraphIds"].append(source_id)
        item["sourceCutModePaths"].append(row["modeResults"])
    return {"distinctLocalFinalCandidateRecords": [confirmed[k] for k in sorted(confirmed)],
            "unresolvedSourceCutObservations": unresolved,
            "productionPublication": "BLOCKED"}


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
            valhalla_config_path: Path, binary: Path, cut_only: bool = False) -> dict:
    manifest, selected = region_input(manifest_path, index_path, buffer_path)
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
        result = subprocess.run(command, check=True,
                                capture_output=True, text=True, timeout=600)
    terminal, unresolved, complete = classify_native_rows(
        result.stdout, selected_count=len(selected), version=expected_version)
    if complete.get("originalCutFilterApplied") is not cut_only:
        raise ValueError("Native original-buffer-cut selection not acknowledged")
    if cut_only and any(e.get("originalCutOrientation") not in
                        ("OUTWARD", "INWARD", "AMBIGUOUS") for e in terminal + unresolved):
        raise ValueError("Missing authoritative cut orientation evidence")
    return {
        "schema": SCHEMA,
        "schemaVersion": 3 if cut_only else 2,
        "actualOriginalCutGeometryFilter": cut_only,
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


def resolve_original_cut_to_file(*, manifest_path: Path, index_path: Path,
                                 buffer_path: Path, valhalla_config_path: Path,
                                 binary: Path, output_path: Path) -> dict:
    """A single region-independent, NONPUBLISHING cutoff→final candidate stage.

    Never consumes historical ledgers, an OSM scan or a manually chosen
    crossing. The source IDs come only from the native compiled graph shapes
    intersecting the exact SHA-bound outer 25-km cutoff. Native physical-road
    ambiguity remains explicit; a local result is not a valid B handoff.
    """
    if output_path.exists():
        raise ValueError("Source final evidence already exists; refusing overwrite")
    evidence = extract(manifest_path=manifest_path, index_path=index_path,
                       buffer_path=buffer_path, valhalla_config_path=valhalla_config_path,
                       binary=binary, cut_only=True)
    cut_rows = (evidence["nativeModeTerminalCandidates"] +
                evidence["unresolvedJunctionDirectedEdges"])
    cut_ids = [r["graphId"] for r in cut_rows]
    if len(set(cut_ids)) != len(cut_ids):
        raise ValueError("Repeated original directed edge on the cutoff")
    orientation_counts = {"OUTWARD": 0, "INWARD": 0, "AMBIGUOUS": 0}
    for row in cut_rows:
        orientation = row.get("originalCutOrientation")
        if orientation not in orientation_counts:
            raise ValueError("Original compiled edge does not establish its cut direction")
        orientation_counts[orientation] += 1
    seeds = sorted(row["graphId"] for row in cut_rows
                   if row["originalCutOrientation"] in ("OUTWARD", "AMBIGUOUS"))
    if not seeds:
        raise ValueError("No original outward/ambiguous source cut edges; no complete catalog")
    _, selected = region_input(manifest_path, index_path, buffer_path)
    selected_ids = {int(row["level"]) | (int(row["tileIndex"]) << 3)
                    for row in selected}
    def inspect(gids):
        return inspect_local_source_edges(manifest_path=manifest_path,
            index_path=index_path, buffer_path=buffer_path,
            valhalla_config_path=valhalla_config_path, binary=binary,
            source_graph_ids=gids)
    source_rows = resolve_local_source_chains(seeds, inspect, selected_ids)
    grouped = consolidate_exact_source_final_ids(source_rows)
    one_local = len(source_rows) - len(grouped["unresolvedSourceCutObservations"])
    # The original source archive and both boundary/index inputs must still
    # match their manifest before writing durable evidence.
    manifest_again, selected_again = region_input(manifest_path, index_path, buffer_path)
    if (manifest_again["graphFingerprint"] != evidence["graphFingerprint"]
            or selected_again != selected):
        raise ValueError("Original source graph/boundary inputs changed mid-extraction")
    report = {
        "schema": "roadpilot.f8-original-cut-local-final-candidates",
        "schemaVersion": 1,
        "regionId": evidence["regionId"],
        "packageVersion": evidence["packageVersion"],
        "graphFingerprint": evidence["graphFingerprint"],
        "bufferFingerprint": evidence["bufferFingerprint"],
        "graphIndexFingerprint": evidence["graphIndexFingerprint"],
        "valhallaVersion": evidence["valhallaVersion"],
        "selectedBoundaryTileCount": evidence["selectedBoundaryTileCount"],
        "nativeDirectedEdgesInSelectedTiles": evidence["nativeDirectedEdgesInSelectedTiles"],
        "originalDirectedCutEvidence": cut_rows,
        "cutOrientationCounts": orientation_counts,
        "cutSourceSeedCount": len(seeds),
        "locallyResolvedSeedCount": one_local,
        "distinctLocalFinalGraphIds": len(grouped["distinctLocalFinalCandidateRecords"]),
        "candidateRecordsByExactOriginalFinalGraphId": grouped["distinctLocalFinalCandidateRecords"],
        "unresolvedSourceCutObservations": grouped["unresolvedSourceCutObservations"],
        "sourcePhysicalRoadDirectionCompleteness": "NOT_VERIFIED",
        "receiverCorrelation": "NOT_STARTED",
        "androidFullJourneyValidation": "NOT_RUN",
        "productionPublication": "BLOCKED",
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=output_path.parent, delete=False) as temp:
        staged = Path(temp.name)
    try:
        writer = gzip.open if output_path.suffix == ".gz" else open
        with writer(staged, "wt", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, separators=(",", ":"))
            stream.write("\n")
        if output_path.exists():
            raise ValueError("Source final evidence appeared during build; refusing overwrite")
        staged.replace(output_path)
    finally:
        staged.unlink(missing_ok=True)
    return {k: report[k] for k in ("regionId", "selectedBoundaryTileCount",
        "cutOrientationCounts", "cutSourceSeedCount", "locallyResolvedSeedCount",
        "distinctLocalFinalGraphIds", "sourcePhysicalRoadDirectionCompleteness",
        "productionPublication")}


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
                        help="Cutoff source seeds and local native forward chains in one nonpublishing, region-independent pass")
    args = parser.parse_args()
    if args.cut_only and args.resolve_cut:
        parser.error("Select --cut-only OR --resolve-cut, not both")
    if args.resolve_cut:
        output = resolve_original_cut_to_file(manifest_path=args.manifest,
            index_path=args.graph_index, buffer_path=args.buffer_geojson,
            valhalla_config_path=args.valhalla_config,
            binary=args.native_binary, output_path=args.output)
        print(f'region={output["regionId"]} selectedTiles={output["selectedBoundaryTileCount"]} '
              f'sources={output["cutSourceSeedCount"]} '
              f'exactFinalGraphIds={output["distinctLocalFinalGraphIds"]} '
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
