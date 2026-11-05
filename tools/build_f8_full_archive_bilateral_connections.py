#!/usr/bin/env python3
"""Extend direct F8 pairing from *all* archived outward source-cut directed edges.

Original country buffer-cut geometry is a SCOPE census only, never a physical
road equivalence, legal route, B peer match, or suppression of ramps/branches.
Every accepted A/B directed pair is checked against actual original Valhalla
TripLeg IDs and both immutable regional tile archives. This is NOT a proof of
global source-road completeness or a release-sidecar publisher.
"""
from __future__ import annotations
import argparse, concurrent.futures, hashlib, json, math, os, sys, tempfile
from collections import Counter
from pathlib import Path
from shapely.geometry import LineString
from shapely.prepared import prep

from build_f8_final_edge_connections import (
    MODES, SCHEMA, VERSION, PROVED, fingerprint, native_lines,
    directed_line, receiver_anchor_index, nearby_receiver_ids,
    physical_forward_continuation, local_receiver_probe,
    prove_receiver_modes, PROJECT,
)
from native_f8_inputs import load_polygon
from build_native_f8_pair_evidence import pair_identity, source_scans
from native_f8_original_route import route_with_original_ids
from probe_native_f8_directed_turn import probe_point
import build_f8_final_edge_connections as matcher

# 11 m *prefetch* catchment around an original peer-graph native anchor:
# established matching original edges have sub-0.1m anchor discrepancy.
# A geometry cut/split can have no nearby native anchor; such connections remain
# explicitly UNRESOLVED and a geometry-complete receiving-graph scan is still due.
PREFETCH_LAT_DEGREES = 0.0001
SOURCE_SNAP_METRES = 1.0


def source_last_mode(args):
    gid, edge, mode, config, binary = args
    coords = [{"lat":lat,"lng":lon} for lat,lon in edge["directedGeometry"]]
    try:
        origin,_ = probe_point(coords,incoming=False)
        destination=coords[-1]
        route=route_with_original_ids(config,origin,destination,mode,binary,timeout=80)
        valid=(route.get("status")=="SUCCEEDED"
            and route.get("lastDirectedGraphId")==gid
            and route.get("originalRouteEdgeIdentity")=="ORIGINAL_VALHALLA_ROUTE_PROTOBUF"
            and route.get("edgeIdOrigin")=="ORIGINAL_TRIPLEG_NODE_EDGE_PROTOBUF"
            and route.get("originalNativeDirectedGraphIds",[None])[-1]==gid
            and isinstance(route.get("startOffsetMeters"),(int,float))
            and isinstance(route.get("endOffsetMeters"),(int,float))
            and route["startOffsetMeters"]<=SOURCE_SNAP_METRES
            and route["endOffsetMeters"]<=SOURCE_SNAP_METRES)
        return gid,mode,{"verified":bool(valid),
             "originalNativeLastGraphId":route.get("lastDirectedGraphId"),
             "originalNativeTripLegDirectedGraphIds":route.get("originalNativeDirectedGraphIds",[]) if valid else [],
             "startSnapMeters":route.get("startOffsetMeters"),
             "endSnapMeters":route.get("endOffsetMeters"),
             "status":route.get("status")}
    except (ValueError,TypeError,IndexError,TimeoutError) as exc:
        return gid,mode,{"verified":False,"status":"UNVERIFIED_SOURCE_ORIGINAL_ROUTE",
                         "error":str(exc)[:160]}


def verify_receiver(task):
    gid, source_modes, recid, source, receiver, rec_config, route_binary = task
    src=directed_line(source)
    rec=directed_line(receiver)
    match=physical_forward_continuation(src,rec)
    if not match or match["status"]!="FORWARD_CONTINUOUS":
        return None
    probe=local_receiver_probe(rec,match["receiverProjectionMeters"])
    proof=prove_receiver_modes(rec_config,route_binary,
           {"lat":source["directedGeometry"][-1][0],
            "lng":source["directedGeometry"][-1][1]},
           probe,recid,source_modes)
    verified=[m for m in sorted(source_modes) if proof[m]["verified"]]
    if not verified:return None
    return {"receiverFirstDirectedGraphId":recid,
        "receiverWayIdAnnotationOnly":receiver["wayId"],
        "sourceWayIdAnnotationOnly":source["wayId"],
        "travelModes":verified,
        "directedPhysicalGeometry":match,
        "originalReceiverValhallaTripLeg":proof,
        "downstreamTestPoint":probe}


def create(args):
    matcher.RECEIVER_SCAN_ANCHOR_LAT_DEGREES=PREFETCH_LAT_DEGREES
    output=args.output
    if output.exists() or output.is_symlink():raise ValueError("Refusing to overwrite original evidence")
    paths={name:getattr(args,name.replace("-","_")) for name in (
        "pair","archive-cut","known-connections","native-terminals","from-scan","to-scan",
        "scan-summary","from-core","to-core","from-buffer","to-buffer",
        "from-graph","to-graph","native-endpoints","native-route")}
    hashes={name:fingerprint(path) for name,path in paths.items()}
    known=json.loads(args.known_connections.read_text())
    terminals=json.loads(args.native_terminals.read_text())
    report=json.loads(args.archive_cut.read_text())
    pair=json.loads(args.pair.read_text())
    pair_identity(pair)
    assert terminals["schema"]=="roadpilot.f8-original-terminal-lineage-ledger"
    assert terminals["pairId"]==pair["pairId"]
    assert terminals["graphFingerprints"]=={
        "from":hashes["from-graph"],"to":hashes["to-graph"]}
    assert known["schema"]==SCHEMA and known["version"]==1
    assert known["pairId"]==report["pairId"]==pair["pairId"]
    assert known["graphFingerprints"]=={
       "from":hashes["from-graph"],"to":hashes["to-graph"]}
    assert report["sourceGraphFingerprints"]=={
       "from":hashes["from-graph"],"to":hashes["to-graph"]}
    assert report["originalGraphArchiveTileInventory"]=="ALL_GRAPHREADER_GETTILESET_TILES_ENUMERATED"
    assert hashes["native-endpoints"]==args.expected_native_endpoints_sha256
    assert hashes["native-route"]==args.expected_native_route_sha256
    for suffix in ("from","to"):
        assert hashes[suffix+"-graph"]==pair[suffix+"GraphFingerprint"]
    from_scan=json.loads(args.from_scan.read_text())
    to_scan=json.loads(args.to_scan.read_text())
    scan_summary=json.loads(args.scan_summary.read_text())
    source_scans(pair,from_scan=from_scan,to_scan=to_scan,scan_summary=scan_summary)
    known_mode={}
    known_receiver={}
    for c in known["connections"]:
        key=(c["sourceRegionId"],c["sourceFinalDirectedGraphId"])
        assert key not in known_mode
        known_mode[key]=set(c["sourceValhallaProvedModes"])
        known_receiver[key]=c["receiverOptions"]
    for c in known["unresolvedSourceFinalEdges"]:
        key=(c["sourceRegionId"],c["sourceFinalDirectedGraphId"])
        assert key not in known_mode
        known_mode[key]=set(c["sourceValhallaProvedModes"])
    all_connections=[];all_unresolved=[]; all_counts={}
    for side,src,peer,src_config,rec_config,recscan,peerbuffer in (
        ("from-to",pair["fromRegionId"],pair["toRegionId"],args.from_config,args.to_config,to_scan,args.to_buffer),
        ("to-from",pair["toRegionId"],pair["fromRegionId"],args.to_config,args.from_config,from_scan,args.from_buffer),
    ):
        peer_geo=prep(load_polygon(peerbuffer))
        source_rows=report["directions"][side]["allOriginalDirectedCutObservations"]
        bad={x["originalDirectedGraphId"] for x in report["directions"][side]["unresolvedOriginalNativeZeroLengthGeometries"]}
        if len(source_rows)!=report["directions"][side]["originalDirectedCutShapeCount"]:
            raise ValueError("Entire original archive cut inventory not reconciled")
        ids={r["originalDirectedGraphId"] for r in source_rows}
        native_terminal_modes={}
        for mode in MODES:
            for r in terminals["directions"][side][mode]["allTerminals"]:
                native_terminal_modes.setdefault(r["sourceGraphId"],set()).add(mode)
        terminal_mode_ids=set(native_terminal_modes)
        if not terminal_mode_ids:
            raise ValueError("Original full native window terminal inventory missing")
        if len(ids)!=len(source_rows):raise ValueError("Duplicate original archive cut directed edge")
        modes_from_archive={}
        eligible_scope=[]
        for r in source_rows:
            gid=r["originalDirectedGraphId"]
            if gid in bad:continue
            modes={m for m in MODES if r["vehicleModes"].get(m)}
            if modes:
                modes_from_archive[gid]=modes
            if r["originalSourceBufferCutDirectedTravel"]=="OUTWARD_FROM_ORIGINAL_SOURCE_BUFFER" and modes:
                eligible_scope.append(gid)
        # Read all archive-cut directed road geometries in the actual source graph,
        # not just the retained native 3,623-window sample.
        with tempfile.TemporaryDirectory(prefix="f8-all-archive-source-") as temp:
            work=Path(temp)
            sourcecut=native_lines(args.native_endpoints,src_config,
                        set(eligible_scope)|terminal_mode_ids,work)
            scoped=set()
            for gid,x in sourcecut.items():
                line=LineString([(lon,lat) for lat,lon in x["directedGeometry"]])
                if peer_geo.intersects(line):
                    scoped.add(gid)
            scoped |= {gid for (region,gid) in known_mode if region==src}
            # Exact original native last directed road geometry for every scoped
            # source, including prior beyond-cut predecessor proofs.
            extra=scoped-set(sourcecut)
            if extra:
                sourcecut.update(native_lines(args.native_endpoints,src_config,extra,work))
            # Receiver native geometry is fetched for ALL candidates before selecting
            # any winning branch; no name/way/group suppression.
            index=receiver_anchor_index(recscan)
            candidates={gid:nearby_receiver_ids(index,tuple(row["directedGeometry"][-1]))
                        for gid,row in sourcecut.items()}
            receiver_ids=set().union(*candidates.values())
            receiving=native_lines(args.native_endpoints,rec_config,receiver_ids,work)
            receiver_lines={gid:directed_line(row) for gid,row in receiving.items()}
            forward={}
            for gid,source in sourcecut.items():
                srcshape=directed_line(source)
                peers=[]
                for b_id in sorted(candidates[gid]):
                    match=physical_forward_continuation(srcshape,receiver_lines[b_id])
                    if match and match["status"]=="FORWARD_CONTINUOUS":
                        peers.append(b_id)
                forward[gid]=peers
            # Prove original A-LAST TripLeg identities for geometrically matched
            # source cut edges. Prior exact-A evidence is SHA-bound above.
            src_verdict={gid:{m:{"verified":True,"status":"PREVIOUS_SHA_BOUND_EXACT_A_LAST"}
                for m in known_mode[(src,gid)]} for gid in scoped if (src,gid) in known_mode}
            to_check=[]
            for gid in sorted(scoped):
                if (src,gid) in known_mode or not forward[gid]:continue
                mask=sourcecut[gid]["forwardAccess"]
                for m in sorted(modes_from_archive.get(gid,set()) |
                                native_terminal_modes.get(gid,set())):
                    if mask & {"auto":1,"motorcycle":1024}[m]:
                        to_check.append((gid,sourcecut[gid],m,src_config,args.native_route))
            print(side,"original archive outward cut",len(eligible_scope),
                  "native window final candidates",len(terminal_mode_ids),
                  "scoped to peer buffered graph",len(scoped),
                  "native matching candidates",sum(bool(x) for x in forward.values()),
                  "A mode route checks",len(to_check),flush=True)
            with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
                for gid,m,v in pool.map(source_last_mode,to_check):
                    src_verdict.setdefault(gid,{})[m]=v
            # Original B-FIRST route probes; retain every matched physical branch,
            # even if an earlier route succeeds; no first-success cap.
            tasks=[]
            mode_by_gid={}
            for gid in sorted(scoped):
                good={m for m,v in src_verdict.get(gid,{}).items() if v["verified"]}
                mode_by_gid[gid]=good
                if not good:continue
                for recid in forward[gid]:
                    tasks.append((gid,good,recid,sourcecut[gid],
                                  receiving[recid],rec_config,args.native_route))
            print(side,"verified A-last sources",sum(bool(v) for v in mode_by_gid.values()),
                  "native B first proof tasks",len(tasks),flush=True)
            results={}
            with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
                for task,option in zip(tasks,pool.map(verify_receiver,tasks)):
                    if option is not None:
                        results.setdefault(task[0],[]).append(option)
            counters=Counter()
            for gid in sorted(scoped):
                modes=mode_by_gid[gid]
                proved=results.get(gid,[])
                point={"lat":sourcecut[gid]["directedGeometry"][-1][0],
                       "lng":sourcecut[gid]["directedGeometry"][-1][1]}
                if proved:
                    peer_sha=hashes["to-graph" if side=="from-to" else "from-graph"]
                    for option in proved:
                        option["receiverGraphFingerprint"]=peer_sha
                    all_connections.append({
                        "sourceRegionId":src,"receiverRegionId":peer,
                        "sourceFinalDirectedGraphId":gid,
                        "sourceFinalCoordinate":point,
                        "sourceValhallaProvedModes":sorted(modes),
                        "originalSourceValhallaTripLeg":src_verdict.get(gid,{}),
                        "receiverOptions":proved,
                        "unverifiedReceiverCandidateGraphIds":
                           sorted(set(candidates[gid])-{o["receiverFirstDirectedGraphId"] for o in proved}),
                        "receiverAnchorCandidatesInspected":len(candidates[gid]),
                        "receiverCandidateCensusComplete":False,
                        "physicalRoadDirectionIdentity":{
                           "sourceFinalDirectedGraphId":gid,
                           "notOsMNameOrProximityDeduplication":True},
                    })
                    counters["verifiedAtoBSourceDirectedIds"]+=1
                    counters["verifiedBReceivingOptions"]+=len(proved)
                else:
                    reason=("NO_ORIGINAL_A_LAST_TRIPLEG" if not modes
                            else "NO_VALHALLA_VERIFIED_FORWARD_RECEIVING_ROAD")
                    all_unresolved.append({
                        "sourceRegionId":src,"receiverRegionId":peer,
                        "sourceFinalDirectedGraphId":gid,
                        "sourceFinalCoordinate":point,
                        "sourceValhallaProvedModes":sorted(modes),
                        "sourceRouteProofs":src_verdict.get(gid,{}),
                        "nearbyReceiverAnchorCount":len(candidates[gid]),
                        "geometricallyForwardReceiverGraphIds":forward[gid],
                        "unverifiedReceiverCandidateGraphIds":sorted(candidates[gid]),
                        "receiverCandidateCensusComplete":False,
                        "status":reason,"mustNotCreateConnection":True})
                    counters[reason]+=1
                counters["sourceDirectedIDsAudited"]+=1
            counters["originalArchiveCutDirectedIDs"]=len(source_rows)
            counters["originalNativeWindowFinalCandidateDirectedIDs"]=len(terminal_mode_ids)
            counters["originalArchiveOutwardCutModeAccessibleIDs"]=len(eligible_scope)
            counters["outwardCutScopingCountPlusKnown"]=len(scoped)
            counters["originalArchiveZeroLengthGeometriesRetainedUnverified"]=len(bad)
            all_counts[side]=dict(counters)
            print(side,"COMPLETE",dict(counters),flush=True)
    pairs=[(c["sourceRegionId"],c["sourceFinalDirectedGraphId"]) for c in all_connections+all_unresolved]
    assert len(set(pairs))==len(pairs)
    for n,p in paths.items():
        if fingerprint(p)!=hashes[n]:raise ValueError("Original input mutated "+n)
    result={"schema":SCHEMA,"version":VERSION,
      "pairId":pair["pairId"],
      "graphFingerprints":{"from":hashes["from-graph"],"to":hashes["to-graph"]},
      "originalImmutableInputSHA256":hashes,
      "oneRecordPerSourceFinalDirectedGraphId":True,
      "noDistinctSourceOrReceiverBranchSuppressed":True,
      "sourceFinalCandidateScope":"ALL_ORIGINAL_ARCHIVE_OUTWARD_SOURCE_BUFFER_CUT_EDGES_PLUS_ALL_NATIVE_WINDOW_MODE_TERMINALS_IN_PEER_BUFFER_PLUS_PREVIOUS_300",
      "sourceDiscoveryComplete":False,
      "receiverCandidateCensusComplete":False,
      "connectionVerification":"ORIGINAL_A_LAST_DIRECTED_TRIPLEG_PLUS_ORIGINAL_B_FORWARD_GEOMETRY_PLUS_ORIGINAL_B_FIRST_TRIPLEG",
      "counts":all_counts,"connections":all_connections,
      "unresolvedSourceFinalEdges":all_unresolved,
      "receivingGraphOriginalDirectedRouteProof":True,
      "realCrossGraphJourneyTests":"SEPARATE_GATE",
      "androidConsumption":"NOT_YET_TESTED",
      "productionPublication":"BLOCKED"}
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile("w",delete=False,dir=output.parent,prefix=".f8-bilateral-",encoding="utf8") as stream:
        staged=Path(stream.name)
        json.dump(result,stream,separators=(",",":"),allow_nan=False)
        stream.write("\n")
    try:
        os.link(staged,output)
    finally:staged.unlink(missing_ok=True)
    print("F8_NEW_CATALOG",output,"sha256:",hashlib.sha256(output.read_bytes()).hexdigest(),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("pair","archive-cut","known-connections","native-terminals","from-scan","to-scan",
          "scan-summary","from-core","to-core","from-buffer","to-buffer",
          "from-config","to-config","from-graph","to-graph","native-endpoints",
          "native-route","output"):
        p.add_argument("--"+name,type=Path,required=True)
    p.add_argument("--expected-native-endpoints-sha256",required=True)
    p.add_argument("--expected-native-route-sha256",required=True)
    p.add_argument("--workers",type=int,default=3)
    a=p.parse_args()
    if a.workers not in range(1,7):raise ValueError("workers must be 1..6")
    create(a)

if __name__=="__main__":
    try:main()
    except (ValueError,TypeError,KeyError,IndexError,OSError,AssertionError) as exc:
        raise SystemExit("F8_ARCHIVE_CONNECTION_ERROR: "+str(exc)[:380])
