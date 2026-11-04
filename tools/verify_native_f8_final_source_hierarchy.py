#!/usr/bin/env python3
"""Exhaust original A-side final-edge candidates against ALL native end-node hierarchy levels.

This verifies source-graph terminal evidence, never receiving graph matching,
road-name/way deduplication, intermediate connector generation or full journeys.
Even no further native mode-accessible edge at an endpoint does NOT itself
prove a unique physical-road/direction class. Preserve every candidate.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict, deque
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile

from build_native_f8_pair_evidence import pair_identity, source_scans
from build_native_f8_final_edge_register import digest, pinned
from census_native_f8_final_directed_edges import verify_binary
from native_f8_inputs import graph_manifest_info
from probe_native_f8_clipped_terminal import CRS, _at, verified_buffer
from shapely.geometry import LineString, Point
from probe_native_f8_journey import verify_retained_graph_identity
from capture_native_f8_graph_windows import read

SCHEMA = "roadpilot.f8-source-final-edge-hierarchy-census"
MODE_BITS = {"auto": 1, "motorcycle": 1024}
MAX_HIERARCHY_NODES = 32
MAX_HIERARCHY_DEPTH = 4
MAX_OUTGOING = 256
SOURCE_STATUS = {
    "ORIGINAL_NATIVE_GRAPH_LOCAL_TERMINAL_ONLY": True,
    "ORIGINAL_NATIVE_MODE_STRANDED_NODE_ONLY": False,
}


def positive_int(value: object, message: str) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError("Missing original native " + message)
    return value


def _native_edge(item: dict) -> tuple:
    if not isinstance(item, dict):
        raise ValueError("Malformed original native outgoing edge")
    gid = positive_int(item.get("graphId"), "outgoing GraphId")
    end = positive_int(item.get("endNodeGraphId"), "outgoing end node")
    mask = item.get("forwardAccess")
    if type(mask) is not int or not 0 <= mask < 2**32:
        raise ValueError("Malformed original native outgoing mode mask")
    if type(item.get("isRoad")) is not bool or type(item.get("isShortcut")) is not bool:
        raise ValueError("Missing original native road/shortcut evidence")
    return (gid, end, mask, item["isRoad"], item["isShortcut"])


def prove_original_end_hierarchy(candidate: dict, source: dict, row: dict) -> dict:
    """Strict, independently testable BFS reachability, no geometry/way grouping."""
    if not isinstance(candidate, dict) or not isinstance(source, dict) or not isinstance(row, dict):
        raise ValueError("Invalid source hierarchy proof input")
    gid = positive_int(candidate.get("finalDirectedGraphId"), "candidate GraphId")
    root = positive_int(candidate.get("nativeEndNodeGraphId"), "candidate end node")
    if (source.get("graphId") != gid
            or row.get("sourceGraphId") != gid or row.get("endNodeGraphId") != root
            or row.get("wayId") != source.get("wayId")
            or candidate.get("wayIdAnnotationOnly") != source.get("wayId")
            or row.get("forwardAccess") != source.get("forwardAccess")):
        raise ValueError("Original source GraphId/end/way/access mismatch")
    dead = SOURCE_STATUS.get(candidate.get("candidateStatus"))
    if dead is None or type(row.get("deadend")) is not bool or row["deadend"] != dead:
        raise ValueError("Original deadend/stranded native classification mismatch")
    terminal = candidate.get("nativeTerminal")
    if (not isinstance(terminal, dict)
            or any(type(terminal.get(k)) not in (int, float)
                   or not math.isfinite(terminal[k]) for k in ("lat", "lng"))
            or abs(row.get("endLat", 999) - terminal["lat"]) > 0.0000001
            or abs(row.get("endLon", 999) - terminal["lng"]) > 0.0000001):
        raise ValueError("Original candidate terminal GPS mismatch")
    reverse = positive_int(row.get("opposingGraphId"), "opposing GraphId")
    root_out = row.get("outgoingDirectedEdges")
    count = row.get("nativeOutgoingDegree")
    if (not isinstance(root_out, list) or type(count) is not int
            or not 1 <= count <= MAX_OUTGOING or len(root_out) != count):
        raise ValueError("Truncated original native root outgoing inventory")
    root_map = {}
    for e in root_out:
        tup = _native_edge(e)
        if tup[0] in root_map:
            raise ValueError("Duplicate root outgoing directed GraphId")
        root_map[tup[0]] = tup
        if (type(e.get("autoBit")) is not bool
                or e["autoBit"] != bool(tup[2] & MODE_BITS["auto"])
                or type(e.get("motorcycleBit")) is not bool
                or e["motorcycleBit"] != bool(tup[2] & MODE_BITS["motorcycle"])):
            raise ValueError("Root original mode mask flag mismatch")
    if reverse not in root_map:
        raise ValueError("Original opposing directed GraphId absent from root")

    nodes = row.get("nativeAllHierarchyContinuationNodes")
    if not isinstance(nodes, list) or not 1 <= len(nodes) <= MAX_HIERARCHY_NODES:
        raise ValueError("Missing/truncated original native hierarchy nodes")
    by_id = {}
    node_out = {}
    transitions = {}
    for n in nodes:
        node_id = positive_int(n.get("nodeGraphId"), "hierarchy node ID")
        depth = n.get("transitionDepth")
        if node_id in by_id or type(depth) is not int or not 0 <= depth <= MAX_HIERARCHY_DEPTH:
            raise ValueError("Repeated/malformed original hierarchy node or depth")
        by_id[node_id] = depth
        for c in ("nodeLat", "nodeLon"):
            if type(n.get(c)) not in (int, float) or not math.isfinite(n[c]):
                raise ValueError("Invalid original hierarchy node GPS")
        outgoing = n.get("allOutgoingDirectedEdges")
        if not isinstance(outgoing, list) or len(outgoing) > MAX_OUTGOING:
            raise ValueError("Missing/truncated hierarchy outgoing inventory")
        ids = set()
        node_out[node_id] = []
        for e in outgoing:
            tup = _native_edge(e)
            if tup[0] in ids:
                raise ValueError("Repeated original outgoing GraphId at hierarchy node")
            ids.add(tup[0])
            node_out[node_id].append(tup)
        links = n.get("nativeHierarchyTransitions")
        if not isinstance(links, list) or len(links) > MAX_HIERARCHY_NODES:
            raise ValueError("Missing original hierarchy transition inventory")
        next_nodes = []
        for link in links:
            target = positive_int(link.get("nodeGraphId"), "hierarchy transition target")
            if type(link.get("up")) is not bool or target in next_nodes:
                raise ValueError("Invalid/duplicate native hierarchy transition")
            next_nodes.append(target)
        transitions[node_id] = next_nodes

    if root not in by_id or by_id[root] != 0 or nodes[0]["nodeGraphId"] != root:
        raise ValueError("Original root native end node not first and depth zero")
    if {r[0]: r for r in node_out[root]} != root_map:
        raise ValueError("Original root hierarchy inventory contradicts direct GraphReader")
    reachable = {root: 0}
    queue = deque([root])
    while queue:
        current = queue.popleft()
        for target in transitions[current]:
            if target not in by_id:
                raise ValueError("Unreported original native hierarchy transition target")
            if target not in reachable:
                reachable[target] = reachable[current] + 1
                queue.append(target)
    if set(reachable) != set(by_id):
        raise ValueError("Disconnected original native hierarchy node")
    for node_id, shortest in reachable.items():
        if shortest != by_id[node_id]:
            raise ValueError("False native hierarchy transition depth/reachability")

    modes = candidate.get("vehicleModes")
    if (not isinstance(modes, list) or not modes or len(modes) != len(set(modes))
            or any(mode not in MODE_BITS for mode in modes)):
        raise ValueError("Missing/duplicate original source mode")
    results = {}
    for mode in modes:
        bit = MODE_BITS[mode]
        if not source["forwardAccess"] & bit:
            raise ValueError("Candidate source is not traversable by claimed mode")
        # The upstream full census reports zero same-node nonopposing
        # forward-access alternatives for each nominated mode. This exact
        # assertion stops downstream loss of a legitimate original branch.
        same_node = [t[0] for t in node_out[root]
                     if t[0] != reverse and t[2] & bit]
        if same_node:
            raise ValueError("Upstream mode-stranded/native terminal has a root continuation")
        # A different hierarchy level can expose a road, ferry, shortcut or
        # reverse. Keep ALL such alternatives as unresolved until original
        # Valhalla legality identifies the true mode-specific continuation.
        hierarchy_edges = [
            {"nodeGraphId": node_id, "directedGraphId": edge[0],
             "isRoad": edge[3], "isShortcut": edge[4]}
            for node_id in by_id if node_id != root
            for edge in node_out[node_id] if edge[2] & bit
        ]
        results[mode] = {
            "status": ("HIERARCHY_MODE_ACCESSIBLE_ALTERNATIVES_UNRESOLVED"
                       if hierarchy_edges else
                       "NO_OTHER_NATIVE_MODE_ACCESSIBLE_HIERARCHY_OUTGOING"),
            "originalOtherHierarchyDirectedEdges": hierarchy_edges,
            "exactNativeEndNodeProved": True,
            "physicalRoadUniqueness": "NOT_VERIFIED",
        }
    return {
        "originalDirectedGraphId": gid,
        "nativeEndNodeGraphId": root,
        "candidateSourceStatus": candidate["candidateStatus"],
        "rootOriginalOpposingGraphId": reverse,
        "nativeHierarchyNodesAudited": len(by_id),
        "originalModeEndStatus": results,
        "sourcePhysicalRoadDirectionEquivalence": "NOT_VERIFIED",
        "candidateSuppressed": False,
    }


def inspect_original_directed_cut(candidate: dict, native: dict,
                                  own_buffer: dict) -> dict:
    """Actual Valhalla source directed shape vs SHA-bound original 25km cut.

    Detect positive source-edge crossing of the cut; the absence of an
    intersection does not exclude that road or establish a physical class.
    Never round/snap the path into a proposed handoff or consult region B.
    """
    vertices = native.get("directedGeometry")
    if not isinstance(vertices, list) or not 2 <= len(vertices) <= 8192:
        raise ValueError("Original native directed edge geometry missing/truncated")
    points = []
    for raw in vertices:
        if not isinstance(raw, list) or len(raw) != 2:
            raise ValueError("Malformed original native directed coordinate")
        lat, lon = raw
        if (type(lat) not in (int, float) or type(lon) not in (int, float)
                or not math.isfinite(lat) or not math.isfinite(lon)
                or abs(lat) > 90 or abs(lon) > 180):
            raise ValueError("Nonfinite/out-of-range original native directed shape")
        points.append(CRS.transform(lon, lat))
    line = LineString(points)
    if not line.is_valid or line.length <= 0:
        raise ValueError("Invalid original native road polyline")
    terminal = _at(candidate["nativeTerminal"])
    if terminal.distance(Point(points[-1])) > 3.0:
        raise ValueError("Original directed shape end disagrees with native terminal")
    own_shape = own_buffer["polygon"]
    boundary = own_shape.boundary
    source_cut_intersection = line.intersects(boundary)
    shape_fingerprint = "sha256:" + hashlib.sha256(
        json.dumps(vertices, separators=(",", ":"), allow_nan=False).encode("utf8")
    ).hexdigest()
    return {
        "originalDirectedShapeSha256": shape_fingerprint,
        "originalDirectedShapeVertexCount": len(vertices),
        "metresToOriginal25kmBoundaryFromEntireEdge": round(
            line.distance(boundary), 3),
        "originalDirectedEdgeIntersects25kmSourceCut": source_cut_intersection,
        "originalDirectedShapeMetresOutsideSourceBuffer": round(
            line.difference(own_shape).length, 3),
        "geometryCutRelation": (
            "ORIGINAL_GRAPH_DIRECTED_SHAPE_TOUCHES_SHA_BOUND_SOURCE_BUFFER_CUT"
            if source_cut_intersection else
            "NO_SOURCE_CUT_INTERSECTION_ON_THIS_FINAL_DIRECTED_EDGE"),
        "geometryClaim": "SOURCE_SIDE_ONLY_PHYSICAL_ROAD_UNIQUENESS_NOT_VERIFIED",
    }


def audit_native_side(binary: Path, config: Path, candidates: list, scan: dict,
                      own_buffer: dict, work: Path, label: str) -> dict:
    edges = scan.get("edges")
    if not isinstance(edges, list):
        raise ValueError("Missing native source scan")
    sources = {}
    for src in edges:
        gid = positive_int(src.get("graphId"), "full original source GraphId")
        if gid in sources:
            raise ValueError("Repeated full original directed source GraphId")
        sources[gid] = src
    ids = [positive_int(c.get("finalDirectedGraphId"), "candidate GraphId")
           for c in candidates]
    if not ids or len(ids) != len(set(ids)) or ids != sorted(ids):
        raise ValueError("Source candidates missing, repeated or not deterministically ordered")
    if any(gid not in sources for gid in ids):
        raise ValueError("Original source candidate GraphId missing from full scan")
    ordered = work / (label + "-all-mode-stop-ids.txt")
    ordered.write_text("".join(str(gid)+"\n" for gid in ids), encoding="ascii")
    errors = work / (label + "-native-stderr.txt")
    report = []
    classes = {mode: Counter() for mode in MODE_BITS}
    proximity = Counter()
    source_cut = Counter()
    native_shapes = defaultdict(list)
    with errors.open("w+", encoding="utf-8") as err:
        with subprocess.Popen(
            [str(binary), str(config), str(ordered), "--terminal-hierarchy"],
            stdout=subprocess.PIPE, stderr=err, text=True, bufsize=1024*1024,
        ) as proc:
            try:
                for i, candidate in enumerate(candidates):
                    raw = proc.stdout.readline()
                    if not raw.endswith("\n"):
                        raise ValueError("Missing/truncated source native hierarchy record")
                    native_row = json.loads(raw)
                    item = prove_original_end_hierarchy(
                        candidate, sources[ids[i]], native_row)
                    cut_observation = inspect_original_directed_cut(
                        candidate, native_row, own_buffer)
                    item.update(cut_observation)
                    pos = _at(candidate["nativeTerminal"])
                    metres = own_buffer["polygon"].boundary.distance(pos)
                    item["metresToOriginalSource25kmCutAnnotationOnly"] = round(metres, 3)
                    item["within100mOfSourceCutAnnotationOnly"] = metres <= 100.0
                    proximity["within100m" if metres <= 100 else "beyond100m"] += 1
                    source_cut["intersects" if cut_observation[
                        "originalDirectedEdgeIntersects25kmSourceCut"] else
                        "notIntersects"] += 1
                    native_shapes[(
                        candidate["wayIdAnnotationOnly"],
                        cut_observation["originalDirectedShapeSha256"],
                        candidate["nativeEndNodeGraphId"],
                    )].append(item["originalDirectedGraphId"])
                    for mode, status in item["originalModeEndStatus"].items():
                        classes[mode][status["status"]] += 1
                    report.append(item)
                if proc.stdout.readline():
                    raise ValueError("Extra native directed end identity; inventory incomplete")
            except BaseException:
                proc.kill()
                proc.wait()
                raise
            rc = proc.wait(timeout=900)
        if rc:
            err.seek(0)
            raise ValueError("Native source hierarchy failed; reject partial proof: "
                             + err.read()[-400:])
    return {
        "originalDirectedSourceGraphIds": len(edges),
        "modeStopNativeGraphIdsReconciled": len(report),
        "modeEndStatusCounts": {mode: dict(sorted(counts.items()))
                               for mode, counts in classes.items()},
        "verifiedCutDistanceAnnotations": dict(sorted(proximity.items())),
        "originalDirectedCutIntersections": dict(sorted(source_cut.items())),
        "nativeExactSameWayGeometryEndNodeCollisionGroups": [
            sorted(ids) for ids in native_shapes.values() if len(ids) > 1],
        "cutCrossingIsPositiveObservationNotEligibilityFilter": True,
        "allOriginalSourceFinalEdgeCandidateProofs": report,
        "hierarchyNodeProofScope": "ALL_ORIGINAL_SOURCE_MODE_STOP_END_NODES",
        "physicalRoadUniqueness": "NOT_VERIFIED",
        "noOriginalCandidatesSuppressed": True,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ("pair", "register", "census", "from-scan", "to-scan",
                 "native-summary", "from-manifest", "to-manifest",
                 "from-buffer", "to-buffer", "native-binary", "output"):
        ap.add_argument("--" + name, required=True, type=Path)
    for name in ("register", "census", "native-binary"):
        ap.add_argument("--expected-" + name + "-sha256", required=True)
    args = ap.parse_args()
    if args.output.exists() or args.output.is_symlink():
        raise ValueError("Refusing to overwrite immutable original source hierarchy report")
    paths = {name: getattr(args, name.replace("-", "_")) for name in (
        "pair", "register", "census", "from-scan", "to-scan",
        "native-summary", "from-manifest", "to-manifest", "from-buffer",
        "to-buffer", "native-binary")}
    original_hashes = {name: digest(path) for name, path in paths.items()}
    for name in ("register", "census", "native-binary"):
        pinned(paths[name], getattr(args, "expected_" + name.replace("-", "_") + "_sha256"))
    native_hash = verify_binary(args.native_binary, original_hashes["native-binary"])
    pair, register, census = (read(args.pair), read(args.register), read(args.census))
    pair_identity(pair)
    if (register.get("schema") != "roadpilot.f8-one-final-directed-edge-candidate-register"
            or register.get("version") != 2 or
            register.get("roadDirectionClasses") != "NOT_VERIFIED" or
            register.get("productionPublication") != "BLOCKED" or
            census.get("nativeTopologyCoverage") != "ALL_RETAINED_NATIVE_SCAN_EDGES"):
        raise ValueError("Full source-only terminal candidate register/census unavailable")
    if (register.get("pairId") != pair["pairId"]
            or census.get("pairId") != pair["pairId"]):
        raise ValueError("Stale pair identity")
    scans = source_scans(pair, from_scan=read(args.from_scan), to_scan=read(args.to_scan),
                         scan_summary=read(args.native_summary))
    a, b, scan_provenance = scans
    if (register.get("immutableSourceSHA256", {}).get("census")
            != original_hashes["census"]
            or register.get("immutableSourceSHA256", {}).get("fromScan")
            != original_hashes["from-scan"]
            or register.get("immutableSourceSHA256", {}).get("toScan")
            != original_hashes["to-scan"]
            or register.get("immutableSourceSHA256", {}).get("nativeSummary")
            != original_hashes["native-summary"]
            or census.get("sourceScanProvenance") != scan_provenance
            or census.get("sourceScanSHA256") != {
                "from": original_hashes["from-scan"],
                "to": original_hashes["to-scan"]}):
        raise ValueError("Immutable original native scan/census/register SHA chain mismatch")
    man_a, man_b = read(args.from_manifest), read(args.to_manifest)
    own_a = verified_buffer(args.from_buffer, man_a)
    own_b = verified_buffer(args.to_buffer, man_b)
    if (census.get("fromBufferSha256") != own_a["sha256"]
            or census.get("toBufferSha256") != own_b["sha256"]):
        raise ValueError("25km original source boundary SHA-256 mismatch")
    with tempfile.TemporaryDirectory(prefix="f8-source-terminal-hierarchy-") as temp_name:
        root = Path(temp_name)
        native_a, cfg_a = graph_manifest_info(args.from_manifest, pair["fromRegionId"],
            man_b["source"]["primaryGeofabrikId"], pair["fromBoundaryFingerprint"],
            root, "A")
        native_b, cfg_b = graph_manifest_info(args.to_manifest, pair["toRegionId"],
            man_a["source"]["primaryGeofabrikId"], pair["toBoundaryFingerprint"],
            root, "B")
        verify_retained_graph_identity(pair, native_a, native_b)
        from_report = audit_native_side(
            args.native_binary, cfg_a,
            register["directions"]["from-to"]["terminalCandidates"],
            a, own_a, root, "A")
        to_report = audit_native_side(
            args.native_binary, cfg_b,
            register["directions"]["to-from"]["terminalCandidates"],
            b, own_b, root, "B")
    for tag, path, graph in (("from", args.from_manifest, man_a),
                             ("to", args.to_manifest, man_b)):
        archive = path.parent / graph["artifact"]["fileName"]
        if digest(archive) != pair[tag + "GraphFingerprint"]:
            raise ValueError("Original immutable graph archive changed during native proof")
    for name, path in paths.items():
        if digest(path) != original_hashes[name]:
            raise ValueError("Original native hierarchy source mutated during proof: " + name)
    doc = {
        "schema": SCHEMA, "version": 1, "pairId": pair["pairId"],
        "graphFingerprints": {
            "from": pair["fromGraphFingerprint"], "to": pair["toGraphFingerprint"]},
        "boundaryFingerprints": {
            "from": pair["fromBoundaryFingerprint"], "to": pair["toBoundaryFingerprint"]},
        "immutableSourceSHA256": original_hashes,
        "nativeHierarchyBinarySHA256": native_hash,
        "directions": {"from-to": from_report, "to-from": to_report},
        "sourceSideProofCoverage": "ALL_REGISTERED_NATIVE_MODE_STOP_END_NODES",
        "oneFinalDirectedEdgePerActualPhysicalRoadAndDirection": "NOT_VERIFIED",
        "physicalRoadDirectionEquivalence": "NOT_ESTABLISHED",
        "receivingGraphCorrelation": "NOT_STARTED",
        "originalValhallaLegalCrossGraphJourney": "NOT_VERIFIED",
        "productionPublication": "BLOCKED",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    stage = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=args.output.parent, delete=False,
            prefix=".f8-source-final-hierarchy-") as stream:
            stage = Path(stream.name)
            json.dump(doc, stream, indent=2, allow_nan=False)
            stream.write("\n")
        if args.output.exists() or args.output.is_symlink():
            raise ValueError("Concurrent source native proof output already exists")
        os.link(stage, args.output)
    finally:
        if stage is not None:
            stage.unlink(missing_ok=True)
    print("Source-only full mode-stop hierarchy proof complete; physical-road identity",
          "NOT_VERIFIED, receiver correlation NOT_STARTED, publication BLOCKED")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, TypeError, KeyError, IndexError,
            subprocess.TimeoutExpired) as error:
        raise SystemExit("F8_SOURCE_FINAL_EDGE_ERROR: " + str(error)[:350])
