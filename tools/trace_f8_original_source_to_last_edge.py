#!/usr/bin/env python3
"""Advance native original A-source continuations to final directed terminal edges.

Seed only previously deferred *intermediate* A edges, expand ALL physical-forward
original source branches (including hierarchy), prove ordered A TripLeg seed->
terminal path, then B physical-forward and B FIRST directed TripLeg identities.
No first success or OSM way/name dedupe. Fail closed for ambiguous paths, cycles,
incomplete depth, illegal turns, unavailable B edges. Keep ordinary F8 discovery.
"""
from __future__ import annotations
import argparse, hashlib, json, os, tempfile
from collections import Counter,defaultdict
from pathlib import Path
from shapely.geometry import LineString

from build_f8_final_edge_connections import (
    fingerprint,native_lines,directed_line,receiver_anchor_index,
    nearby_receiver_ids,physical_forward_continuation,local_receiver_probe,
    prove_receiver_modes,MODES,
)
from gate_f8_source_final_native_topology import (
    hierarchy_rows,validate_mode,FINAL,INTERMEDIATE,AMBIGUOUS
)
from probe_native_f8_directed_turn import probe_point
from native_f8_original_route import route_with_original_ids
import build_f8_final_edge_connections as matcher

MAX_CHAIN_EDGES=20
MODE_BITS={"auto":1,"motorcycle":1024}


def is_ordered_subsequence(haystack,needle):
    iterator=iter(haystack)
    return all(any(x==wanted for x in iterator) for wanted in needle)


def prove_from_seed(config,route_binary,source,last,seed_id,last_id,mode,path):
    coords=[{"lat":lat,"lng":lon} for lat,lon in source["directedGeometry"]]
    try:
        start,_=probe_point(coords,incoming=False)
    except ValueError as error:
        return {"verified":False,"reason":"SOURCE_EDGE_TOO_SHORT: "+str(error)}
    dest={"lat":last["directedGeometry"][-1][0],
          "lng":last["directedGeometry"][-1][1]}
    proof=route_with_original_ids(config,start,dest,mode,route_binary,timeout=90)
    ids=proof.get("originalNativeDirectedGraphIds",[])
    ok=(proof.get("status")=="SUCCEEDED" and
       proof.get("originalRouteEdgeIdentity")=="ORIGINAL_VALHALLA_ROUTE_PROTOBUF" and
       proof.get("edgeIdOrigin")=="ORIGINAL_TRIPLEG_NODE_EDGE_PROTOBUF" and
       proof.get("firstDirectedGraphId")==seed_id and
       proof.get("lastDirectedGraphId")==last_id and
       ids and ids[0]==seed_id and ids[-1]==last_id and
       is_ordered_subsequence(ids,path) and
       isinstance(proof.get("startOffsetMeters"),(int,float)) and
       isinstance(proof.get("endOffsetMeters"),(int,float)) and
       proof["startOffsetMeters"]<=1.0 and proof["endOffsetMeters"]<=1.0)
    return {"verified":bool(ok),"originalNativeFirstGraphId":proof.get("firstDirectedGraphId"),
        "originalNativeLastGraphId":proof.get("lastDirectedGraphId"),
        "originalNativeTripLegDirectedGraphIds":ids if ok else [],
        "startSnapMeters":proof.get("startOffsetMeters"),
        "endSnapMeters":proof.get("endOffsetMeters"),
        "status":proof.get("status"),"sourceChainDirectedGraphIds":path}


def trace_native_source_branches(seed_rows,endpoint_binary,config,work):
    """Expand every actual native forward edge until native last, not success-first."""
    native={}
    roots={}
    current=[]
    for row in seed_rows:
        gid=row["sourceFinalDirectedGraphId"]
        desc=row["originalSourceFinalTopologyProof"]
        for mode in row["sourceValhallaProvedModes"]:
            if desc[mode]["status"] in (INTERMEDIATE,AMBIGUOUS):
                current.append((gid,mode,(gid,)))
    counts=Counter()
    terminals=defaultdict(list)
    deferred=[]
    for depth in range(MAX_CHAIN_EDGES):
        if not current:break
        unique={path[-1] for seed,mode,path in current}
        absent=unique-set(native)
        if absent:
            native.update(native_lines(endpoint_binary,config,absent,work))
        absent=unique-set(roots)
        if absent:
            roots.update(hierarchy_rows(endpoint_binary,config,absent,work))
        adjacent={r["graphId"] for gid in unique
                  for node in roots[gid]["nativeAllHierarchyContinuationNodes"]
                  for r in node["allOutgoingDirectedEdges"]
                  if r["graphId"]!=roots[gid]["opposingGraphId"]
                  and r["forwardAccess"]&(MODE_BITS["auto"]|MODE_BITS["motorcycle"])}
        missing=adjacent-set(native)
        if missing:
            native.update(native_lines(endpoint_binary,config,missing,work))
        nxt=[]
        for seed,mode,path in current:
            gid=path[-1]
            proof=validate_mode(native[gid],roots[gid],native,mode)
            counts["originalSourceGraphDirectedStatesVisited"]+=1
            if proof["otherUnresolvedOriginalSourceBranches"]:
                deferred.append({"seedOriginalSourceGraphId":seed,
                    "mode":mode,"pathOriginalDirectedGraphIds":list(path),
                    "reason":"AMBIGUOUS_LOCAL_SOURCE_BRANCH",
                    "unresolvedOutgoingGraphIds":[r["graphId"] for r in
                        proof["otherUnresolvedOriginalSourceBranches"]]})
                counts["ambiguousOriginalSourceBranchesRetained"]+=len(
                    proof["otherUnresolvedOriginalSourceBranches"])
            forward=proof["nativeSourceForwardContinuations"]
            if forward:
                for option in forward:
                    other=option["graphId"]
                    if other in path:
                        deferred.append({"seedOriginalSourceGraphId":seed,"mode":mode,
                            "pathOriginalDirectedGraphIds":list(path),
                            "reason":"ORIGINAL_NATIVE_SOURCE_LOOP",
                            "revisitedGraphId":other})
                        counts["nativeSourceLoopPathsDeferred"]+=1
                    else:
                        nxt.append((seed,mode,path+(other,)))
            elif proof["status"]==FINAL:
                terminals[(gid,mode)].append((seed,mode,list(path)))
                counts["nativeSourceTerminalPathCandidates"]+=1
            else:
                counts["ambiguousTerminalPathsDeferred"]+=1
        current=nxt
    for seed,mode,path in current:
        deferred.append({"seedOriginalSourceGraphId":seed,"mode":mode,
           "pathOriginalDirectedGraphIds":list(path),
           "reason":"SOURCE_NATIVE_CHAIN_MAX_DEPTH_NOT_A_PROOF"})
    counts["depthCappedPathsDeferred"]+=len(current)
    return terminals,native,roots,deferred,counts


def add_verified_target(catalog,rec,connection_index):
    key=(rec["sourceRegionId"],rec["sourceFinalDirectedGraphId"])
    old=connection_index.get(key)
    if old is None:
        catalog["connections"].append(rec)
        connection_index[key]=rec
        return True
    old["sourceValhallaProvedModes"]=sorted(set(
        old["sourceValhallaProvedModes"]+rec["sourceValhallaProvedModes"]))
    old.setdefault("originalSourceFinalTopologyProof",{}).update(
        rec["originalSourceFinalTopologyProof"])
    seen={x["receiverFirstDirectedGraphId"]:x for x in old["receiverOptions"]}
    for x in rec["receiverOptions"]:
        bid=x["receiverFirstDirectedGraphId"]
        if bid not in seen:
            old["receiverOptions"].append(x)
            seen[bid]=x
        else:
            mode=set(seen[bid]["travelModes"])|set(x["travelModes"])
            seen[bid]["travelModes"]=sorted(mode)
            seen[bid]["originalReceiverValhallaTripLeg"].update(
                x["originalReceiverValhallaTripLeg"])
    old.setdefault("additionalNativeSourceLineageWitnesses",[]).extend(
        rec.get("additionalNativeSourceLineageWitnesses",[]))
    return False


def generate(args):
    matcher.RECEIVER_SCAN_ANCHOR_LAT_DEGREES=0.0001
    if args.output.exists() or args.output.is_symlink():
        raise ValueError("Never overwrite the prior immutable F8 catalog")
    paths={"catalog":args.catalog,"from-graph":args.from_graph,
           "to-graph":args.to_graph,"from-scan":args.from_scan,
           "to-scan":args.to_scan,"native-endpoints":args.native_endpoints,
           "native-route":args.native_route}
    hashes={k:fingerprint(p) for k,p in paths.items()}
    if hashes["native-endpoints"]!=args.expected_native_endpoints_sha256 or hashes[
       "native-route"]!=args.expected_native_route_sha256:
        raise ValueError("Native original Valhalla SHA pin not matched")
    doc=json.loads(args.catalog.read_text())
    if doc["schema"]!="roadpilot.f8-final-directed-connections" or doc[
       "sourceDiscoveryComplete"] is not False or doc["productionPublication"]!="BLOCKED":
        raise ValueError("Input must be partial source-terminal-verified catalog")
    assert doc["graphFingerprints"]=={
        "from":hashes["from-graph"],"to":hashes["to-graph"]}
    docs=json.loads(json.dumps(doc))
    existing={(row["sourceRegionId"],row["sourceFinalDirectedGraphId"]):row
       for row in docs["connections"]}
    directions=[("italy-nord-est","austria",args.from_config,args.to_config,args.to_scan,
                  hashes["to-graph"]),
                ("austria","italy-nord-est",args.to_config,args.from_config,args.from_scan,
                  hashes["from-graph"])]
    counters=Counter()
    branch_proof={}
    for region,peer,config,rec_config,rec_scan,rec_sha in directions:
        source_seeds=[r for r in doc["unresolvedSourceFinalEdges"]
          if r["sourceRegionId"]==region and r.get("status")=="ORIGINAL_SOURCE_NOT_PROVED_FINAL"]
        if not source_seeds:continue
        receiver_scan=json.loads(rec_scan.read_text())
        receiver_index=receiver_anchor_index(receiver_scan)
        with tempfile.TemporaryDirectory(prefix="f8-source-forward-final-") as temp:
            work=Path(temp)
            terminal,native,roots,deferred,counts=trace_native_source_branches(
                source_seeds,args.native_endpoints,config,work)
            counters.update(counts)
            counters["intermediateOriginalSourceSeedIDsTraced"]+=len(source_seeds)
            print(region,"source seeds",len(source_seeds),"mode-specific terminal paths",
                sum(map(len,terminal.values())),"unique finals",len({gid for gid,m in terminal}),
                "deferred",len(deferred),flush=True)
            targets=defaultdict(set)
            for gid,mode in terminal:
                targets[gid].add(mode)
            candidates={}
            for gid in targets:
                shape=native[gid]
                candidates[gid]=nearby_receiver_ids(receiver_index,
                        tuple(shape["directedGeometry"][-1]))
            receiver_ids=set().union(*candidates.values()) if candidates else set()
            receiver=native_lines(args.native_endpoints,rec_config,receiver_ids,work)
            shapes={gid:directed_line(edge) for gid,edge in receiver.items()}
            counters["originalBReceivingAnchorsFetched"]+=len(receiver_ids)
            root_seed_ids={seed for items in terminal.values()
                           for seed,mode,path in items}
            seed_edges=native_lines(args.native_endpoints,config,root_seed_ids,work)
            accepted={}
            for gid in sorted(targets):
                finaledge=native[gid]
                a_modes={}
                witness=[]
                for mode in sorted(targets[gid]):
                    modepaths=terminal[(gid,mode)]
                    proved=[]
                    for seed,_,path in modepaths:
                        route=prove_from_seed(config,args.native_route,seed_edges[seed],
                              finaledge,seed,gid,mode,path)
                        counters["originalSourceCutToFinalDirectedTripLegProbes"]+=1
                        if route["verified"]:
                            proved.append({"seedOriginalSourceGraphId":seed,
                                "mode":mode,"pathOriginalDirectedGraphIds":path,
                                "originalSourceValhallaTripLeg":route})
                        else:
                            deferred.append({"seedOriginalSourceGraphId":seed,"mode":mode,
                                "pathOriginalDirectedGraphIds":path,
                                "reason":"SOURCE_VALHALLA_DIRECTED_PATH_NOT_PROVED",
                                "originalSourceValhallaTripLeg":route})
                    if proved:
                        a_modes[mode]=True
                        witness.extend(proved)
                if not a_modes:continue
                src_shape=directed_line(finaledge)
                matched=[]
                unverified=[]
                for bid in sorted(candidates[gid]):
                    match=physical_forward_continuation(src_shape,shapes[bid])
                    if not match or match["status"]!="FORWARD_CONTINUOUS":
                        unverified.append(bid)
                        continue
                    probe=local_receiver_probe(shapes[bid],
                                  match["receiverProjectionMeters"])
                    point={"lat":finaledge["directedGeometry"][-1][0],
                           "lng":finaledge["directedGeometry"][-1][1]}
                    original=prove_receiver_modes(rec_config,args.native_route,point,
                                    probe,bid,set(a_modes))
                    counters["originalBFirstDirectedTripLegProbes"]+=len(a_modes)
                    modes=[mode for mode in sorted(a_modes) if original[mode]["verified"]]
                    if not modes:
                        unverified.append(bid);continue
                    matched.append({"receiverFirstDirectedGraphId":bid,
                       "receiverGraphFingerprint":rec_sha,
                       "sourceWayIdAnnotationOnly":finaledge["wayId"],
                       "receiverWayIdAnnotationOnly":receiver[bid]["wayId"],
                       "travelModes":modes,
                       "directedPhysicalGeometry":match,
                       "originalReceiverValhallaTripLeg":original,
                       "downstreamTestPoint":probe})
                if not matched:continue
                accepted[gid]={"sourceRegionId":region,"receiverRegionId":peer,
                    "sourceFinalDirectedGraphId":gid,
                    "sourceFinalCoordinate":{"lat":finaledge["directedGeometry"][-1][0],
                        "lng":finaledge["directedGeometry"][-1][1]},
                    "sourceValhallaProvedModes":sorted(a_modes),
                    "originalSourceFinalTopologyProof":{
                       m:validate_mode(native[gid],roots[gid],native,m)
                       for m in a_modes},
                    "additionalNativeSourceLineageWitnesses":witness,
                    "receiverOptions":matched,
                    "unverifiedReceiverCandidateGraphIds":unverified,
                    "receiverAnchorCandidatesInspected":len(candidates[gid]),
                    "receiverCandidateCensusComplete":False,
                    "physicalRoadDirectionIdentity":{
                        "sourceFinalDirectedGraphId":gid,
                        "notOsMNameOrProximityDeduplication":True}}
            for gid,rec in accepted.items():
                if add_verified_target(docs,rec,existing):
                    counters["additionalVerifiedOriginalSourceFinalDirectedIDs"]+=1
                counters["additionalNativeBReceiverOptionProofs"]+=len(rec["receiverOptions"])
                # Previously unknown same id may now be proven; do not carry both
                # unresolved and accepted for the same source native GraphId.
            for row in deferred:
                row["originalSourceRegionId"]=region
            branch_proof[region]={
                "originalNativeUnresolvedSourceBranches":deferred,
                "tracedSourceSeeds":len(source_seeds),
                "resultingAcceptedSourceFinalIDs":sorted(accepted),
            }
    accepted_keys=set(existing)
    docs["unresolvedSourceFinalEdges"]=[
       x for x in docs["unresolvedSourceFinalEdges"]
       if (x["sourceRegionId"],x["sourceFinalDirectedGraphId"]) not in accepted_keys]
    docs["sourceDiscoveryComplete"]=False
    docs["physicalRoadPerDirectionGlobalUniqueness"]="NOT_VERIFIED"
    docs["forwardSourceBranchLineageVerification"]="ORIGINAL_GRAPH_NATIVE_WITNESS_AND_SOURCE_A_LAST_RECEIVER_B_FIRST_PROBED"
    docs["forwardSourceBranchTraceCounters"]=dict(counters)
    docs["forwardSourceOriginalUnresolvedBranchLedger"]=branch_proof
    docs["forwardSourceParentEvidenceSHA256"]=hashes
    docs["productionPublication"]="BLOCKED"
    ids=[(x["sourceRegionId"],x["sourceFinalDirectedGraphId"])
         for x in docs["connections"]+docs["unresolvedSourceFinalEdges"]]
    if len(ids)!=len(set(ids)):raise ValueError("Duplicate source-directed GraphId in merged catalog")
    for key,path in paths.items():
        if fingerprint(path)!=hashes[key]:
            raise ValueError("Native original F8 input changed during source lineage trace")
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile("w",delete=False,
        dir=args.output.parent,prefix=".f8-native-terminal-trace-",encoding="utf8") as stream:
        staged=Path(stream.name)
        json.dump(docs,stream,separators=(",",":"),allow_nan=False);stream.write("\n")
    try:os.link(staged,args.output)
    finally:staged.unlink(missing_ok=True)
    print("F8_TRACED_FORWARD_SOURCE_FINALS",dict(counters),"accepted",len(docs["connections"]),
          "sha256:"+hashlib.sha256(args.output.read_bytes()).hexdigest(),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("catalog","from-config","to-config","from-graph","to-graph",
                 "from-scan","to-scan","native-endpoints","native-route","output"):
        p.add_argument("--"+name,type=Path,required=True)
    p.add_argument("--expected-native-endpoints-sha256",required=True)
    p.add_argument("--expected-native-route-sha256",required=True)
    args=p.parse_args()
    generate(args)


if __name__=="__main__":
    try:main()
    except (OSError,ValueError,AssertionError,KeyError,TypeError,IndexError) as err:
        import traceback
        traceback.print_exc()
        raise SystemExit("F8_FINAL_NATIVE_CHAIN_ERROR: "+str(err)[:500])
