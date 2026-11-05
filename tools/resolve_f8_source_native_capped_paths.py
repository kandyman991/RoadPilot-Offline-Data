#!/usr/bin/env python3
"""Resume ALL depth-capped original source-road branches with state deduplication.

Every same-OSM-way native directed (seed,mode,GraphId) is visited once
regardless of how many physical branch paths converge there. OSM way ID is
used only to constrain safe lineage traversal, never to deduplicate final
edges; other physical branch IDs remain unresolved and are NOT suppressed. Exact original graph outgoing
geometry/hierarchy is inspected without a fixed edge-depth cutoff. Distinct
successor edges are never discarded. Proven native source last edges are matched
against EVERY original B graph tile's directed shapes and original Valhalla
A-LAST/B-FIRST TripLeg IDs before joining a partial unpublished F8 catalog.

The only spatial boundary is the SHA-bound actual bilateral build overlap;
any branch leaving it remains explicitly unresolved, never a negative match.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict, deque
from pathlib import Path
import hashlib, json, os, tempfile
from shapely.geometry import Point
from shapely.prepared import prep

from build_f8_final_edge_connections import (
    fingerprint, native_lines, directed_line, physical_forward_continuation,
    local_receiver_probe, prove_receiver_modes, MODES
)
from gate_f8_source_final_native_topology import (
    hierarchy_rows, validate_mode, FINAL, INTERMEDIATE, AMBIGUOUS
)
from native_f8_inputs import load_polygon
from complete_f8_original_receiving_archive import original_receiver_scan
from trace_f8_original_source_to_last_edge import prove_from_seed, add_verified_target

MODE_BITS = {"auto": 1, "motorcycle": 1024}
BATCH = 128


def discover_uncapped_from_capped(capped: list[dict], binary: Path, config: Path,
                                 native_overlap, work: Path):
    """No hop-count limit; key by original source seed, mode, directed GraphId."""
    initial = {}
    alternatives = Counter()
    for row in capped:
        if row.get("reason") != "SOURCE_NATIVE_CHAIN_MAX_DEPTH_NOT_A_PROOF":
            continue
        seed,mode,path = row["seedOriginalSourceGraphId"],row["mode"],tuple(
            row["pathOriginalDirectedGraphIds"])
        if mode not in MODE_BITS or not path or path[0] != seed:
            raise ValueError("Invalid prior original source-chain seed or mode")
        key=(seed,mode,path[-1])
        if key in initial:
            alternatives[key] += 1
            if len(path) < len(initial[key]):
                initial[key] = path
        else:
            initial[key] = path
    if not initial:
        return {}, {}, {}, [], Counter()
    pending=deque((key,path) for key,path in sorted(initial.items()))
    visited=set(initial)
    original_shapes={}
    native_rows={}
    mode_proofs={}
    terminal=defaultdict(list)
    unknown=[]
    counts=Counter()
    counts["originalDepthCappedModePathsInput"]=sum(
        x.get("reason")=="SOURCE_NATIVE_CHAIN_MAX_DEPTH_NOT_A_PROOF" for x in capped)
    counts["deduplicatedInitialOriginalSourceDirectedStates"]=len(initial)
    counts["convergedPriorOriginalSourcePathsRetainedAsCounts"]=sum(alternatives.values())
    # Preserve every alternate original directed transition even when two native
    # paths converge at one directed GraphId. The final GraphId, not a path count,
    # is the record identity.
    predecessors=defaultdict(set)
    while pending:
        chunk=[]
        for _ in range(min(BATCH,len(pending))):
            chunk.append(pending.popleft())
        gids={key[2] for key,path in chunk}
        missing=gids-set(original_shapes)
        if missing:
            original_shapes.update(native_lines(binary,config,missing,work))
        missing=gids-set(native_rows)
        if missing:
            native_rows.update(hierarchy_rows(binary,config,missing,work))
        nearby={x["graphId"] for gid in gids
                for node in native_rows[gid]["nativeAllHierarchyContinuationNodes"]
                for x in node["allOutgoingDirectedEdges"]
                if x["graphId"]!=native_rows[gid]["opposingGraphId"]
                and x["forwardAccess"] & (MODE_BITS["auto"]|MODE_BITS["motorcycle"])}
        missing=nearby-set(original_shapes)
        if missing:
            original_shapes.update(native_lines(binary,config,missing,work))
        for (seed,mode,gid),path in chunk:
            counts["originalDirectedSourceStatesExhaustivelyProcessed"]+=1
            if counts["originalDirectedSourceStatesExhaustivelyProcessed"] % 2000 == 0:
                print("F8_FULL_NATIVE_SOURCE_WALK_STATES",
                      counts["originalDirectedSourceStatesExhaustivelyProcessed"],
                      "pending",len(pending),"nativeShapes",len(original_shapes),
                      "finalModes",len(terminal),flush=True)
            e=original_shapes[gid]
            endpoint=e["directedGeometry"][-1]
            if not native_overlap[0].covers(Point(endpoint[1],endpoint[0])) or not (
                native_overlap[1].covers(Point(endpoint[1],endpoint[0]))):
                unknown.append({"seedOriginalSourceGraphId":seed,"mode":mode,
                    "originalDirectedGraphId":gid,
                    "reason":"LEFT_AUTHORITATIVE_BILATERAL_25KM_GRAPH_OVERLAP",
                    "partialLineageDirectedGraphIds":list(path)})
                counts["sourceBranchesLeaving25kmOverlapUnresolved"]+=1
                continue
            cache_key=(gid,mode)
            if cache_key not in mode_proofs:
                mode_proofs[cache_key]=validate_mode(e,native_rows[gid],
                                                     original_shapes,mode)
            proof=mode_proofs[cache_key]
            if proof["otherUnresolvedOriginalSourceBranches"]:
                counts["ambiguousOutgoingNativeSourceBranchObservations"]+=len(
                    proof["otherUnresolvedOriginalSourceBranches"])
                unknown.append({"seedOriginalSourceGraphId":seed,"mode":mode,
                    "originalDirectedGraphId":gid,
                    "reason":"OTHER_ORIGINAL_NATIVE_BRANCH_NOT_PROVED_SAME_ROAD",
                    "otherNativeOutgoingDirectedGraphIds":[
                       x["graphId"] for x in proof["otherUnresolvedOriginalSourceBranches"]]})
            followers=proof["nativeSourceForwardContinuations"]
            same_way=[]
            for successor in followers:
                child=successor["graphId"]
                child_way=original_shapes[child]["wayId"]
                same_original_physical_way=e["wayId"]>0 and child_way==e["wayId"]
                if same_original_physical_way:
                    same_way.append(child)
                else:
                    # A real ramp, road branch, or legitimate way-ID change
                    # can still be present. Never suppress its physical edge
                    # or call the source final solely because IDs differ.
                    unknown.append({
                        "seedOriginalSourceGraphId":seed,"mode":mode,
                        "originalDirectedGraphId":gid,
                        "otherForwardOriginalDirectedGraphId":child,
                        "sourceWayIdAnnotationOnly":e["wayId"],
                        "successorWayIdAnnotationOnly":child_way,
                        "reason":"PHYSICALLY_FORWARD_WAY_ID_CHANGE_REQUIRES_INDEPENDENT_ROAD_LINEAGE"})
                    counts["nativeOtherWayForwardBranchesPreservedUnverified"]+=1
            if same_way:
                for child in same_way:
                    nextkey=(seed,mode,child)
                    predecessors[nextkey].add(gid)
                    counts["sameOriginalWayForwardEdgesTraversed"]+=1
                    if nextkey in visited:
                        counts["convergentOriginalSourceRoadStateTransitions"]+=1
                        continue
                    visited.add(nextkey)
                    pending.append((nextkey,path+(child,)))
            elif not followers and proof["status"]==FINAL:
                terminal[(gid,mode)].append({
                    "seedOriginalSourceGraphId":seed,
                    "mode":mode,
                    "pathOriginalDirectedGraphIds":list(path)})
                counts["originalSourceModeTerminalRoadStates"]+=1
            elif proof["status"] not in (AMBIGUOUS,INTERMEDIATE):
                raise ValueError("Unknown original source continuation verdict")
    counts["allOriginalSourceDirectedStatesVisited"]=len(visited)
    counts["uniqueNativeSourceFinalModeStatesAfterUncappedWalk"]=len(terminal)
    counts["nativeSourceEndStatesWithDistinctParents"]=sum(
        len(v)>1 for v in predecessors.values())
    counts["unfinishedDepthLimitedSourcePaths"]=0
    counts["differentOSMWayBranchesWereMarkedResolved"] = 0
    return terminal,original_shapes,native_rows,unknown,counts


def finish(args):
    if args.output.exists() or args.output.is_symlink():
        raise ValueError("Refuse overwrite of immutable F8 native evidence")
    files={"catalog":args.catalog,
       "nativeFullReceiver":args.native_full_receiver,
       "nativeEndpoints":args.native_endpoints,
       "nativeRoute":args.native_route,
       "italyGraph":args.from_graph,
       "austriaGraph":args.to_graph,
       "italyBuffer":args.from_buffer,
       "austriaBuffer":args.to_buffer}
    hashes={key:fingerprint(path) for key,path in files.items()}
    if (hashes["nativeFullReceiver"]!=args.expected_native_full_receiver_sha256 or
        hashes["nativeEndpoints"]!=args.expected_native_endpoints_sha256 or
        hashes["nativeRoute"]!=args.expected_native_route_sha256):
        raise ValueError("Native Valhalla source/receiver binary hashes changed")
    prev=json.loads(args.catalog.read_text())
    if (prev.get("schema")!="roadpilot.f8-final-directed-connections" or
        prev.get("sourceDiscoveryComplete") is not False or
        prev.get("productionPublication")!="BLOCKED"):
        raise ValueError("Only original unpublished partial source graph input allowed")
    if prev.get("graphFingerprints")!={"from":hashes["italyGraph"],
                                        "to":hashes["austriaGraph"]}:
        raise ValueError("Original graph SHA fingerprints differ")
    # Full receiver scan from v9 is retained. New source final GraphIds are
    # added independently to that verified-only pool.
    result=json.loads(json.dumps(prev))
    indexed={(row["sourceRegionId"],row["sourceFinalDirectedGraphId"]):row
         for row in result["connections"]}
    if len(indexed)!=len(result["connections"]):
        raise ValueError("Native source existing record duplicated")
    overlap=(prep(load_polygon(args.from_buffer)),
             prep(load_polygon(args.to_buffer)))
    counters=Counter()
    per_side={}
    with tempfile.TemporaryDirectory(prefix="f8-unbounded-source-native-") as tmp:
        workspace=Path(tmp)
        for region,peer,cfg,rec_cfg in [
           ("italy-nord-est","austria",args.from_config,args.to_config),
           ("austria","italy-nord-est",args.to_config,args.from_config)]:
            old=prev.get("forwardSourceOriginalUnresolvedBranchLedger",{}).get(region)
            if not old:raise ValueError("Previous original source capped ledger missing")
            terminal,source,roots,unknown,counts=discover_uncapped_from_capped(
                old["originalNativeUnresolvedSourceBranches"],
                args.native_endpoints,cfg,overlap,workspace)
            print(region,"original source uncapped",dict(counts),
                  "native original terminal state modes",len(terminal),flush=True)
            counters.update(counts)
            coords={}
            for (gid,mode) in terminal:
                coords[gid]={"lat":source[gid]["directedGeometry"][-1][0],
                             "lng":source[gid]["directedGeometry"][-1][1]}
            if not coords:
                per_side[region]={"unresolvedOriginalSourceBranches":unknown,
                        "counts":dict(counts)}
                continue
            full_scan=original_receiver_scan(args.native_full_receiver,
                                 rec_cfg,coords,workspace)
            if (not full_scan["summary"]["allGraphReaderTilesExhaustivelyRead"] or
                full_scan["summary"]["originalReceiverTileCount"] != (
                    338 if peer=="austria" else 367)):
                raise ValueError("Original receiving graph full archive incomplete")
            peer_ids=set.union(*(v for v in full_scan["pairs"].values()))
            receivers=native_lines(args.native_endpoints,rec_cfg,peer_ids,workspace)
            peer_geometry={x:directed_line(r) for x,r in receivers.items()}
            startids={x["seedOriginalSourceGraphId"] for rows in terminal.values()
                        for x in rows}
            starters=native_lines(args.native_endpoints,cfg,startids,workspace)
            matched={}
            for gid in sorted(coords):
                row_modes={}
                witnesses=[]
                for mode in MODES:
                    lineage=terminal.get((gid,mode),())
                    if not lineage:continue
                    for candidate in lineage:
                        seed=candidate["seedOriginalSourceGraphId"]
                        route=prove_from_seed(cfg,args.native_route,
                                   starters[seed],source[gid],seed,gid,mode,
                                   candidate["pathOriginalDirectedGraphIds"])
                        counters["newOrderedAOriginalTripLegProbes"]+=1
                        if route["verified"]:
                            row_modes[mode]=True
                            witnesses.append({"seedOriginalSourceGraphId":seed,
                                "mode":mode,
                                "pathOriginalDirectedGraphIds":
                                  candidate["pathOriginalDirectedGraphIds"],
                                "originalSourceValhallaTripLeg":route})
                        else:
                            unknown.append({
                              "seedOriginalSourceGraphId":seed,"mode":mode,
                              "originalFinalCandidateGraphId":gid,
                              "reason":"ORIGINAL_A_TRIPLEG_CHAIN_NOT_VERIFIED",
                              "nativeOriginalRouteProof":route})
                if not row_modes:continue
                peeropts=[]
                a=directed_line(source[gid])
                for b_id in sorted(full_scan["pairs"][gid]):
                    match=physical_forward_continuation(a,peer_geometry[b_id])
                    if match is None or match["status"]!="FORWARD_CONTINUOUS":
                        continue
                    test=local_receiver_probe(peer_geometry[b_id],
                                             match["receiverProjectionMeters"])
                    proof=prove_receiver_modes(rec_cfg,args.native_route,
                             coords[gid],test,b_id,set(row_modes))
                    counters["newExactBOriginalFirstGraphIdModeProbes"]+=len(row_modes)
                    modes=[m for m in MODES if m in proof and proof[m]["verified"]]
                    if not modes:continue
                    peeropts.append({
                       "receiverFirstDirectedGraphId":b_id,
                       "receiverGraphFingerprint": prev["graphFingerprints"][
                         "to" if region=="italy-nord-est" else "from"],
                       "sourceWayIdAnnotationOnly":source[gid]["wayId"],
                       "receiverWayIdAnnotationOnly":receivers[b_id]["wayId"],
                       "travelModes":modes,
                       "directedPhysicalGeometry":match,
                       "originalReceiverValhallaTripLeg":proof,
                       "downstreamTestPoint":test})
                if not peeropts:continue
                matched[gid]={
                   "sourceRegionId":region,"receiverRegionId":peer,
                   "sourceFinalDirectedGraphId":gid,
                   "sourceFinalCoordinate":coords[gid],
                   "sourceValhallaProvedModes":sorted(row_modes),
                   "originalSourceFinalTopologyProof":{
                     m:validate_mode(source[gid],roots[gid],source,m)
                     for m in row_modes},
                   "additionalNativeSourceLineageWitnesses":witnesses,
                   "receiverOptions":peeropts,
                   "receiverCandidateCensusComplete":True,
                   "originalReceiverAllTileGeometryScan":
                    "EXHAUSTIVE_GETTILESET_FOR_SOURCE_END",
                   "physicalRoadDirectionIdentity":{
                      "sourceFinalDirectedGraphId":gid,
                      "notOsMNameOrProximityDeduplication":True}}
            for gid,rec in matched.items():
                key=(region,gid)
                is_new=add_verified_target(result,rec,indexed)
                counters["newOriginalBDirectedOptionsVerified"]+=len(rec["receiverOptions"])
                if is_new:
                    counters["newOriginalSourceFinalGraphIdsVerified"]+=1
                else:
                    counters["nativeOriginalSourceFinalRecordsUpdated"]+=1
            per_side[region]={
                "unresolvedOriginalSourceBranches":unknown,
                "counts":dict(counts),
                "receiverNativeFullArchiveScanSummary":full_scan["summary"],
                "newSourceFinals":sorted(matched)}
    accepted=set(indexed)
    result["unresolvedSourceFinalEdges"]=[
       r for r in result["unresolvedSourceFinalEdges"]
       if (r["sourceRegionId"],r["sourceFinalDirectedGraphId"]) not in accepted]
    keys=[(r["sourceRegionId"],r["sourceFinalDirectedGraphId"])
          for r in result["connections"]+result["unresolvedSourceFinalEdges"]]
    if len(set(keys))!=len(keys):
        raise ValueError("Native source directed records duplicate in final")
    result["uncappedOriginalSourceContinuationResults"]=per_side
    result["uncappedOriginalSourceContinuationCounts"]=dict(counters)
    result["uncappedOriginalSourceInputSHA256"]=hashes
    result["sourceDiscoveryComplete"]=False
    result["physicalRoadPerDirectionGlobalUniqueness"]="NOT_VERIFIED"
    result["productionPublication"]="BLOCKED"
    for name,p in files.items():
        if fingerprint(p)!=hashes[name]:
            raise ValueError("Original native graph or tool changed during uncapped walk")
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile("w",dir=args.output.parent,delete=False,
                                    prefix=".f8-uncapped-source-",encoding="utf8") as f:
        stage=Path(f.name)
        json.dump(result,f,separators=(",",":"),allow_nan=False)
        f.write("\n")
    try:os.link(stage,args.output)
    finally:stage.unlink(missing_ok=True)
    print("F8_UNCAPPED_ORIGINAL_SOURCE_RESULT",dict(counters),
          "allVerifiedFinalSourceGraphIds",len(result["connections"]),
          "allVerifiedBFirstDirectedOptions",
          sum(len(r["receiverOptions"]) for r in result["connections"]),
          "sha256",fingerprint(args.output),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for item in ("catalog","from-config","to-config","from-buffer","to-buffer",
                 "from-graph","to-graph","native-full-receiver",
                 "native-endpoints","native-route","output"):
        p.add_argument("--"+item,type=Path,required=True)
    for item in ("native-full-receiver","native-endpoints","native-route"):
        p.add_argument("--expected-"+item+"-sha256",required=True)
    args=p.parse_args()
    finish(args)


if __name__ == "__main__":
    try:
        main()
    except (ValueError,KeyError,TypeError,IndexError,AssertionError,OSError) as exc:
        import traceback
        traceback.print_exc()
        raise SystemExit("F8_UNCAPPED_ORIGINAL_SOURCE_FAILED: "+str(exc)[:350])
