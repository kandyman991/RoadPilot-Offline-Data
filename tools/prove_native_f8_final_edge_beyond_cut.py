#!/usr/bin/env python3
"""Verify original A-side final edges located BEYOND the 25km source cut.

A physical road's final native segment can lie wholly beyond the cut. Walk
ONLY original source-graph native directed immediate predecessors, preserve
every legal/illegal alternative without name/way/GPS filtering, and locate
actual cut-intersecting predecessor shapes. Do not correlate region B.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import tempfile

from build_native_f8_pair_evidence import pair_identity
from build_native_f8_final_edge_register import digest, pinned
from capture_native_f8_graph_windows import read
from census_native_f8_final_directed_edges import verify_binary
from native_f8_inputs import graph_manifest_info
from native_f8_original_route import route_with_original_ids, verify_native_route_binary
from probe_native_f8_clipped_terminal import verified_buffer
from probe_native_f8_directed_turn import probe_point
from probe_native_f8_journey import verify_retained_graph_identity
from prove_native_f8_source_cut_last_tripleg import (
    STATUS_PROVEN, classify_source_last_edge, native_original_rows,
)
from verify_native_f8_final_source_hierarchy import inspect_original_directed_cut

SCHEMA = "roadpilot.f8-original-source-beyond-cut-last-edge"
MAX_PREDECESSOR_DEPTH = 3
MAX_VISITED_PER_LAST_EDGE = 128
MAX_FANOUT_PER_NODE = 64
MODE_BITS = {"auto": 1, "motorcycle": 1024}


def original_rows_by_id(native_binary: Path, config: Path,
                        ids: list[int], option: str, work: Path) -> dict:
    """Bind ordered GraphReader rows to every exact requested original GraphId."""
    if not ids or len(ids) != len(set(ids)):
        raise ValueError("Missing or repeated source native GraphIds")
    raws = native_original_rows(native_binary, config, ids, option, work)
    if (not isinstance(raws, list) or len(raws) != len(ids)
            or [row.get("sourceGraphId") for row in raws] != ids):
        raise ValueError("Original native source GraphReader row inventory mismatch")
    return dict(zip(ids, raws))


def enumerate_original_cut_predecessor_paths(
    native_binary: Path, config: Path, final_candidate: dict, own_buffer: dict,
    work: Path, *, depth_limit: int = MAX_PREDECESSOR_DEPTH,
    budget: int = MAX_VISITED_PER_LAST_EDGE,
) -> dict:
    """Bounded original same-level directed end-to-start DFS, ALL branches.

    A missing branch or exhausted budget yields NOT_VERIFIED rather than a
    proof of global completeness. No crossing candidate elimination anywhere.
    """
    gid = final_candidate["finalDirectedGraphId"]
    if (type(gid) is not int or gid <= 0
            or not 1 <= depth_limit <= 10 or not 1 <= budget <= 4096):
        raise ValueError("Invalid bounded source predecessor traversal input")
    root = original_rows_by_id(native_binary, config, [gid],
                                 "--continuations", work)[gid]
    if (root["endNodeGraphId"] != final_candidate["nativeEndNodeGraphId"]
            or root["wayId"] != final_candidate["wayIdAnnotationOnly"]):
        raise ValueError("Final original directed edge mismatches source register")
    seen_paths = []
    cut_paths = []
    visited_count = 0
    cut_reached = False
    truncations = []
    cache: dict[tuple[int, str], dict] = {}

    def lookup(ids: list[int], option: str) -> dict:
        needed = [x for x in dict.fromkeys(ids) if (x, option) not in cache]
        if needed:
            rows = original_rows_by_id(native_binary, config, needed, option, work)
            for value, item in rows.items():
                cache[(value, option)] = item
        return {x: cache[(x, option)] for x in ids}

    # Reverse chains contain GraphIds ordered from the nominated final edge
    # back toward the cut. A complete reported path reverses that sequence.
    queue = [([gid], 0)]
    while queue:
        path, depth = queue.pop(0)
        current = path[-1]
        if depth >= depth_limit:
            truncations.append({"lastScannedSourceGraphId": current,
                                "reason": "BOUNDED_HOP_DEPTH_REACHED",
                                "nativeFinalToCurrentDirectedPath": path})
            continue
        current_row = lookup([current], "--continuations")[current]
        back = current_row.get("opposingGraphId")
        if type(back) is not int or back <= 0:
            raise ValueError("Original native opposing GraphId missing at source start")
        back_row = lookup([back], "--continuations")[back]
        start_node = back_row["endNodeGraphId"]
        next_outgoings = back_row.get("outgoingDirectedEdges")
        if not isinstance(next_outgoings, list) or len(next_outgoings) > MAX_FANOUT_PER_NODE:
            truncations.append({"lastScannedSourceGraphId": current,
                                "reason": "ORIGINAL_NODE_FANOUT_UNCERTAIN",
                                "nativeFinalToCurrentDirectedPath": path})
            continue
        if sum(x.get("graphId") == current for x in next_outgoings) != 1:
            raise ValueError("Original current directed edge missing from own start node")
        others = [x["graphId"] for x in next_outgoings if x["graphId"] != current]
        if not others:
            continue
        outgoing = lookup(others, "--continuations")
        opposing = [outgoing[x]["opposingGraphId"] for x in others]
        if len(opposing) != len(set(opposing)):
            raise ValueError("Repeated original native incoming GraphId at source node")
        incoming = lookup(opposing, "--geometry")
        for out_id, incoming_id in zip(others, opposing):
            predecessor = incoming[incoming_id]
            if predecessor["endNodeGraphId"] != start_node:
                raise ValueError("Native source predecessor not connected to current start")
            if predecessor["sourceGraphId"] in path:
                seen_paths.append({"predecessorDirectedGraphId": incoming_id,
                                   "nativeFinalToCurrentDirectedPath": path,
                                   "status": "ORIGINAL_GRAPH_LOCAL_CYCLE_RETAINED"})
                continue
            visited_count += 1
            if visited_count > budget:
                truncations.append({"lastScannedSourceGraphId": current,
                                    "reason": "BOUNDED_PREDECESSOR_BUDGET_EXHAUSTED",
                                    "nativeFinalToCurrentDirectedPath": path})
                break
            next_path = path + [incoming_id]
            observed = inspect_original_directed_cut({
                    "nativeTerminal": {
                        "lat": predecessor["endLat"], "lng": predecessor["endLon"]},
                }, predecessor, own_buffer)
            point = {
                "originalDirectedGraphId": incoming_id,
                "forwardAccess": predecessor["forwardAccess"],
                "sourceWayIdAnnotationOnly": predecessor["wayId"],
                "originalDirectedGeometrySha256": observed["originalDirectedShapeSha256"],
                "intersectsOriginalSource25kmCut": observed[
                    "originalDirectedEdgeIntersects25kmSourceCut"],
                "nativeForwardDirectedPathToFinal": list(reversed(next_path)),
                "depth": depth + 1,
            }
            seen_paths.append(point)
            if point["intersectsOriginalSource25kmCut"]:
                cut_reached = True
                cut_paths.append(point)
            else:
                queue.append((next_path, depth + 1))
        if visited_count > budget:
            break
    return {
        "originalFinalDirectedGraphId": gid,
        "nativeSourceSameLevelPredecessorEdgesVisited": visited_count,
        "predecessorTraversalLimitHops": depth_limit,
        "predecessorTraversalBudget": budget,
        "originalSourcePredecessorTraversal": seen_paths,
        "originalDirectedCutCrossingPredecessorPaths": cut_paths,
        "anyOriginalCutCrossingPredecessorLocated": cut_reached,
        "completeness": "INCOMPLETE_BOUNDED" if truncations else
                        "ALL_SAME_LEVEL_PREDECESSOR_BRANCHES_WITHIN_BOUND_VISITED",
        "truncations": truncations,
        "globalNativePhysicalRoadDirectionEquivalence": "NOT_VERIFIED",
        "noOriginalBranchesSuppressed": True,
    }


def prove_original_cut_predecessor_routes(
    candidate: dict, branches: dict, original_binary: Path,
    route_binary: Path, config: Path, work: Path,
) -> dict:
    """Probe EVERY positive source cut path and mode using original TripLeg IDs."""
    paths = branches["originalDirectedCutCrossingPredecessorPaths"]
    ids = list(dict.fromkeys(x["originalDirectedGraphId"] for x in paths))
    shapes = original_rows_by_id(original_binary, config, ids, "--geometry", work) if ids else {}
    results = []
    mode_counts = Counter()
    for path in paths:
        gid = path["originalDirectedGraphId"]
        shape = shapes[gid]
        coords = [{"lat": v[0], "lng": v[1]} for v in shape["directedGeometry"]]
        per_mode = {}
        for mode in candidate["vehicleModes"]:
            if not (shape["forwardAccess"] & MODE_BITS[mode]):
                per_mode[mode] = {
                    "sourceLastEdgeProof": "NOT_VERIFIED",
                    "reason": "ORIGINAL_CUT_PREDECESSOR_MODE_INACCESSIBLE"}
                mode_counts["ORIGINAL_CUT_PREDECESSOR_MODE_INACCESSIBLE"] += 1
                continue
            try:
                start, _ = probe_point(coords, incoming=True)
            except (ValueError, TypeError, IndexError) as exc:
                per_mode[mode] = {
                    "sourceLastEdgeProof": "NOT_VERIFIED",
                    "reason": "ORIGINAL_CUT_PREDECESSOR_TOO_SHORT: " + str(exc)}
                mode_counts["ORIGINAL_CUT_PREDECESSOR_TOO_SHORT"] += 1
                continue
            route = route_with_original_ids(
                config, start, candidate["nativeTerminal"], mode,
                route_binary, timeout=60)
            verdict = classify_source_last_edge(route, candidate)
            original_tripleg = route.get("originalNativeDirectedGraphIds", [])
            expected = path["nativeForwardDirectedPathToFinal"]
            exact_path = (
                verdict["sourceLastEdgeProof"] == STATUS_PROVEN
                and route.get("firstDirectedGraphId") == gid
                and len(original_tripleg) >= len(expected)
                and original_tripleg[-len(expected):] == expected
            )
            verdict["originalSourceCutPathExactTripLegSequence"] = exact_path
            if not exact_path:
                verdict["sourceLastEdgeProof"] = "NOT_VERIFIED"
                verdict["reason"] = "Original TripLeg did not match exact native source cut predecessor path"
            per_mode[mode] = verdict
            mode_counts[verdict["sourceLastEdgeProof"]] += 1
        results.append({
            "originalDirectedCutEdge": gid,
            "nativeForwardDirectedPathToFinal": path["nativeForwardDirectedPathToFinal"],
            "originalRouteModeProofs": per_mode,
            "physicalRoadEquivalence": "NOT_VERIFIED",
        })
    return {"originalSourceCutCrossingPathCount": len(paths),
            "originalSourceCutRouteProofs": results,
            "routeModeCounts": dict(sorted(mode_counts.items())),
            "physicalRoadEquivalence": "NOT_VERIFIED"}


def verify_one_side(config: Path, own_buffer: dict, register_side: dict,
                    hierarchy_side: dict, endpoint_binary: Path,
                    route_binary: Path, work: Path, side: str) -> dict:
    candidates = register_side["terminalCandidates"]
    evidence = hierarchy_side["allOriginalSourceFinalEdgeCandidateProofs"]
    if (register_side.get("uniqueOriginalTerminalCandidateGraphIds") != len(candidates)
            or hierarchy_side.get("modeStopNativeGraphIdsReconciled") != len(evidence)
            or len(evidence) != len(candidates)):
        raise ValueError("Original complete native mode-stop candidate coverage mismatch")
    original_lookup = {c["finalDirectedGraphId"]:c for c in candidates}
    if len(original_lookup) != len(candidates):
        raise ValueError("Duplicated original final source directed edge")
    selected = []
    status = Counter()
    for row in evidence:
        gid = row["originalDirectedGraphId"]
        if gid not in original_lookup:
            raise ValueError("Original final edge not in full candidate register")
        if (row.get("originalDirectedEdgeIntersects25kmSourceCut") is False
                and row.get("originalDirectedShapeMetresOutsideSourceBuffer", 0) > 0):
            selected.append((row, original_lookup[gid]))
    for row, candidate in selected:
        lineage = enumerate_original_cut_predecessor_paths(
            endpoint_binary, config, candidate, own_buffer, work)
        route = prove_original_cut_predecessor_routes(
            candidate, lineage, endpoint_binary, route_binary, config, work)
        lineage["originalSourceOriginalValhallaTripLeg"] = route
        lineage["originalFinalDirectedEdgeEntirelyBeyondOriginalSource25kmCut"] = True
        status["candidatePathsAudited"] += 1
        status["candidateWithOriginalCutPredecessor"] += int(
            lineage["anyOriginalCutCrossingPredecessorLocated"])
        status["candidateWithoutOriginalCutPredecessor"] += int(
            not lineage["anyOriginalCutCrossingPredecessorLocated"])
        status["candidatePathSearchIncomplete"] += int(
            lineage["completeness"] == "INCOMPLETE_BOUNDED")
        for key, n in route["routeModeCounts"].items():
            status["originalRouteMode:" + key] += n
        row["originalSourceBeyondCutPredecessorEvidence"] = lineage
    return {
        "sourceSide": side,
        "originalModeStopCandidatesPreservedInParent": len(candidates),
        "originalDirectedFinalEdgesBeyondCutIdentified": len(selected),
        "status": dict(sorted(status.items())),
        "beyondCutOriginalFinalEdgeProofs": [
            x["originalSourceBeyondCutPredecessorEvidence"] for x, _ in selected],
        "originalSourceCandidateSuppression": "NONE",
        "physicalRoadDirectionFinalUniqueness": "NOT_VERIFIED",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ("pair", "register", "hierarchy", "from-manifest", "to-manifest",
                 "from-buffer", "to-buffer", "native-binary", "route-binary", "output"):
        ap.add_argument("--" + name, type=Path, required=True)
    for name in ("register", "hierarchy", "native-binary", "route-binary"):
        ap.add_argument("--expected-" + name + "-sha256", required=True)
    args = ap.parse_args()
    if args.output.exists() or args.output.is_symlink():
        raise ValueError("Refusing to replace immutable source beyond-cut proof")
    files = {name: getattr(args, name.replace("-", "_"))
             for name in ("pair", "register", "hierarchy", "from-manifest",
                          "to-manifest", "from-buffer", "to-buffer", "native-binary",
                          "route-binary")}
    sha = {k:digest(p) for k,p in files.items()}
    for name in ("register", "hierarchy", "native-binary", "route-binary"):
        pinned(files[name],getattr(args,"expected_"+name.replace("-","_")+"_sha256"))
    verify_binary(args.native_binary, sha["native-binary"])
    verify_native_route_binary(args.route_binary,expected_sha256=sha["route-binary"])
    pair, register, hierarchy = read(args.pair),read(args.register),read(args.hierarchy)
    pair_identity(pair)
    if (register.get("pairId")!=pair["pairId"]
            or register.get("version")!=2 or register.get("productionPublication")!="BLOCKED"
            or hierarchy.get("pairId")!=pair["pairId"]
            or hierarchy.get("schema")!="roadpilot.f8-source-final-edge-hierarchy-census"
            or hierarchy.get("receivingGraphCorrelation")!="NOT_STARTED"
            or hierarchy.get("immutableSourceSHA256",{}).get("register")!=sha["register"]):
        raise ValueError("Original source register or hierarchy proof stale/incomplete")
    ma, mb = read(args.from_manifest),read(args.to_manifest)
    own_a=verified_buffer(args.from_buffer,ma)
    own_b=verified_buffer(args.to_buffer,mb)
    with tempfile.TemporaryDirectory(prefix="f8-original-beyond-cut-") as root:
        tmp=Path(root)
        ga, config_a=graph_manifest_info(args.from_manifest,pair["fromRegionId"],
            mb["source"]["primaryGeofabrikId"],pair["fromBoundaryFingerprint"],tmp,"A")
        gb, config_b=graph_manifest_info(args.to_manifest,pair["toRegionId"],
            ma["source"]["primaryGeofabrikId"],pair["toBoundaryFingerprint"],tmp,"B")
        verify_retained_graph_identity(pair,ga,gb)
        result={
            "from-to":verify_one_side(config_a,own_a,
                register["directions"]["from-to"],hierarchy["directions"]["from-to"],
                args.native_binary,args.route_binary,tmp,pair["fromRegionId"]),
            "to-from":verify_one_side(config_b,own_b,
                register["directions"]["to-from"],hierarchy["directions"]["to-from"],
                args.native_binary,args.route_binary,tmp,pair["toRegionId"]),
        }
    for side,path,man in (("from",args.from_manifest,ma),("to",args.to_manifest,mb)):
        if digest(path.parent/man["artifact"]["fileName"])!=pair[side+"GraphFingerprint"]:
            raise ValueError("Original immutable native source graph modified during proof")
    if any(digest(path)!=sha[k] for k,path in files.items()):
        raise ValueError("Original beyond-cut source changed during proof")
    doc={"schema":SCHEMA,"version":1,"pairId":pair["pairId"],
         "immutableSourceSHA256":sha,"directions":result,
         "physicalRoadPerDirectionUniqueness":"NOT_VERIFIED",
         "receivingGraphCorrelation":"NOT_STARTED",
         "productionPublication":"BLOCKED"}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    stage=None
    try:
        with tempfile.NamedTemporaryFile("w",encoding="utf8",dir=args.output.parent,
            prefix=".f8-beyond-cut-",delete=False) as stream:
            stage=Path(stream.name)
            json.dump(doc,stream,indent=2,allow_nan=False)
            stream.write("\n")
        if args.output.exists() or args.output.is_symlink():
            raise ValueError("Concurrent immutable proof output exists")
        os.link(stage,args.output)
    finally:
        if stage is not None:stage.unlink(missing_ok=True)
    print("Original beyond-cut source-only predecessor and TripLeg proof complete;",
          "global physical road uniqueness NOT_VERIFIED; receiving graph NOT_STARTED")
    return 0


if __name__=="__main__":
    try:
        raise SystemExit(main())
    except (ValueError,KeyError,TypeError,IndexError,OSError) as error:
        raise SystemExit("F8_BEYOND_CUT_ERROR: "+str(error)[:350])
