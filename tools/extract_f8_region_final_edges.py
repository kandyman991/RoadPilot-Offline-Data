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
import shutil
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

from shapely.geometry import box, shape

SCHEMA = "roadpilot.f8-region-original-boundary-source"
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
            valhalla_config_path: Path, binary: Path) -> dict:
    manifest, selected = region_input(manifest_path, index_path, buffer_path)
    expected_version = str(manifest["valhallaVersion"])
    actual = subprocess.run([str(binary), "--version"], check=True, capture_output=True,
                            text=True, timeout=30).stdout.strip()
    if actual != expected_version:
        raise ValueError("Native Valhalla version does not match compiled graph")
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
        result = subprocess.run([str(binary), str(cfg), str(ids)], check=True,
                                capture_output=True, text=True, timeout=600)
    terminal, unresolved, complete = classify_native_rows(
        result.stdout, selected_count=len(selected), version=expected_version)
    return {
        "schema": SCHEMA,
        "schemaVersion": 1,
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
                    valhalla_config_path: Path, binary: Path, output_path: Path) -> dict:
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
    actual = subprocess.run([str(binary), "--version"], check=True,
                            capture_output=True, text=True, timeout=30).stdout.strip()
    if actual != version:
        raise ValueError("Native Valhalla version does not match compiled graph")
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
            subprocess.run([str(binary), str(cfg), str(ids)], check=True,
                           stdout=handle, stderr=subprocess.PIPE, timeout=600)
        counts = {"terminal": 0, "unresolved": 0}
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
                or completion.get("edgesEmitted") != len(seen)):
            raise ValueError("Original native boundary scan did not complete on exact inputs")
        # Original compiled graph is the retained authority. This candidate
        # inventory explicitly does NOT assert final physical-road identity.
        header = {
            "schema": SCHEMA, "schemaVersion": 1,
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--graph-index", type=Path, required=True)
    parser.add_argument("--buffer-geojson", type=Path, required=True)
    parser.add_argument("--valhalla-config", type=Path, required=True)
    parser.add_argument("--native-binary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = extract_to_file(manifest_path=args.manifest, index_path=args.graph_index,
                             buffer_path=args.buffer_geojson,
                             valhalla_config_path=args.valhalla_config,
                             binary=args.native_binary, output_path=args.output)
    print(f'region={output["regionId"]} selectedTiles={output["selectedBoundaryTileCount"]} '
          f'terminalCandidates={output["nativeTerminalCandidateCount"]} '
          f'unresolved={output["unresolvedJunctionDirectedEdgeCount"]} '
          'publication=BLOCKED')


if __name__ == "__main__":
    main()
