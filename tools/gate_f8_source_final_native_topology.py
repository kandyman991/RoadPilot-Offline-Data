#!/usr/bin/env python3
"""Fail-closed original SOURCE graph final-edge gate for a partial F8 catalog.

A route that ends on edge X does not prove X is the LAST retained edge of the
same physical road/direction. Check exact native source end-node hierarchy and
all physical-forward source graph continuations, per travel mode. Intermediate
A/B geometry/Valhalla pairs are retained as UNRESOLVED, never published as
source-final matches. No OSM-way/name, coordinate-group, or success-first filter.
"""
from __future__ import annotations
import argparse,hashlib,json,os,subprocess,tempfile
from collections import Counter
from pathlib import Path
from build_f8_final_edge_connections import (
    fingerprint,native_lines,directed_line,physical_forward_continuation,MODES,
)

MODE_BITS={"auto":1,"motorcycle":1024}
FINAL="NO_OTHER_NATIVE_PHYSICAL_FORWARD_CONTINUATION"
INTERMEDIATE="ORIGINAL_SOURCE_GRAPH_HAS_FORWARD_ROAD_CONTINUATION"
AMBIGUOUS="ORIGINAL_SOURCE_OTHER_ACCESSIBLE_BRANCH_UNRESOLVED"


def hierarchy_rows(binary,config,ids,work):
    path=work/"ids-lineage.txt"
    path.write_text("".join(str(x)+"\n" for x in sorted(ids)))
    proc=subprocess.run([str(binary),str(config),str(path),"--lineage"],
                        capture_output=True,text=True,timeout=180)
    if proc.returncode:raise ValueError("Native source hierarchy failed: "+proc.stderr[-270:])
    rows=[json.loads(s) for s in proc.stdout.splitlines()]
    if len(rows)!=len(ids) or {r["sourceGraphId"] for r in rows}!=set(ids):
        raise ValueError("Native source hierarchy missing/repeated/extra IDs")
    if any("nativeAllHierarchyContinuationNodes" not in x for x in rows):
        raise ValueError("Original full hierarchy source proof missing")
    return {x["sourceGraphId"]:x for x in rows}


def validate_mode(source,root,geometries,mode):
    """No easy success by first match: collect EVERY accessible original A branch."""
    gid=root["sourceGraphId"]
    if not isinstance(root.get("opposingGraphId"),int) or root["opposingGraphId"]<=0:
        raise ValueError("Missing original opposing GraphId")
    src=directed_line(source)
    successors=[]
    ambiguous=[]
    branches={}
    for node in root["nativeAllHierarchyContinuationNodes"]:
        for row in node["allOutgoingDirectedEdges"]:
            other=row["graphId"]
            mask=row["forwardAccess"]
            if other==root["opposingGraphId"] or not mask&MODE_BITS[mode]:continue
            if other==gid:
                raise ValueError("Original source directed edge links to itself")
            if other in branches:continue
            shape=geometries[other]
            geom=directed_line(shape)
            m=physical_forward_continuation(src,geom)
            info={"graphId":other,"forwardAccess":mask,
                  "isRoad":row["isRoad"],"isShortcut":row["isShortcut"],
                  "physicalGeometry":m}
            branches[other]=info
            if m is not None and m["status"]=="FORWARD_CONTINUOUS":
                successors.append(info)
            elif m is None:
                # Same original native intersection, but geometry doesn't
                # allow a positive physical-continuation verdict.
                ambiguous.append(info)
            elif m["directionCosine"]>-0.9:
                # U-turn/reverse is not a genuinely new forward road; everything
                # else remains unresolved rather than being silently discarded.
                ambiguous.append(info)
    if successors: status=INTERMEDIATE
    elif ambiguous:status=AMBIGUOUS
    else:status=FINAL
    return {"status":status,"nativeSourceForwardContinuations":successors,
            "otherUnresolvedOriginalSourceBranches":ambiguous,
            "nativeSourceEndNodeGraphId":root["endNodeGraphId"],
            "sourceGraphId":gid}


def gate_catalog(catalog,roots,shapes,neighbor_shapes):
    output=json.loads(json.dumps(catalog))
    old=output.pop("connections")
    unresolved=output["unresolvedSourceFinalEdges"]
    certified=[]
    counts=Counter()
    for row in old:
        region=row["sourceRegionId"]
        gid=row["sourceFinalDirectedGraphId"]
        root=roots[(region,gid)]
        assertions={}
        for mode in row["sourceValhallaProvedModes"]:
            assertions[mode]=validate_mode(shapes[(region,gid)],root,
                neighbor_shapes[region],mode)
        good={mode for mode,v in assertions.items() if v["status"]==FINAL}
        counts["sourceRecordsAudited"]+=1
        if good:
            retained=json.loads(json.dumps(row))
            retained["sourceValhallaProvedModes"]=sorted(good)
            retained["originalSourceFinalTopologyProof"]=assertions
            options=[]
            discarded=[]
            for opt in retained["receiverOptions"]:
                orig=opt["travelModes"]
                keep=[m for m in orig if m in good]
                if keep:
                    opt["travelModes"]=keep
                    options.append(opt)
                for m in orig:
                    if m not in good:
                        discarded.append({"receiverGraphId":opt["receiverFirstDirectedGraphId"],
                            "mode":m,"reason":assertions[m]["status"]})
            retained["receiverOptions"]=options
            if options:
                retained["unverifiedReceiverCandidateGraphIds"]=sorted(set(
                    retained.get("unverifiedReceiverCandidateGraphIds",[])+[
                        x["receiverGraphId"] for x in discarded]))
                if discarded:retained["deferredPreTerminalModeAlternatives"]=discarded
                certified.append(retained)
                counts["sourceFinalConnectionsVerified"]+=1
                counts["nativeVerifiedReceivingOptions"]+=len(options)
                continue
        unresolved.append({
            "sourceRegionId":region,
            "receiverRegionId":row["receiverRegionId"],
            "sourceFinalDirectedGraphId":gid,
            "sourceFinalCoordinate":row["sourceFinalCoordinate"],
            "sourceValhallaProvedModes":row["sourceValhallaProvedModes"],
            "nearbyReceiverAnchorCount":row.get("receiverAnchorCandidatesInspected",0),
            "originalSourceFinalTopologyProof":assertions,
            "deferredPreTerminalReceiverOptions":row["receiverOptions"],
            "unverifiedReceiverCandidateGraphIds":row.get("unverifiedReceiverCandidateGraphIds",[]),
            "receiverCandidateCensusComplete":False,
            "status":"ORIGINAL_SOURCE_NOT_PROVED_FINAL",
            "mustNotCreateConnection":True})
        counts["intermediateOrAmbiguousSourceIDsDeferred"]+=1
    output["connections"]=certified
    ids=[(x["sourceRegionId"],x["sourceFinalDirectedGraphId"])
         for x in certified+unresolved]
    if len(ids)!=len(set(ids)):raise ValueError("Duplicate original source directed ID")
    output["sourceDiscoveryComplete"]=False
    output["physicalRoadPerDirectionGlobalUniqueness"]="NOT_VERIFIED"
    output["sourceFinalGraphNativeTopologyGate"]="REQUIRED_NO_FORWARD_OR_AMBIGUOUS_SOURCE_CONTINUATION"
    output["fullCrossRegionJourneyStatus"]="NOT_VERIFIED"
    output["productionPublication"]="BLOCKED"
    output["additionalSourceFinalGateCounts"]=dict(counts)
    return output


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--catalog",type=Path,required=True)
    p.add_argument("--from-config",type=Path,required=True)
    p.add_argument("--to-config",type=Path,required=True)
    p.add_argument("--from-graph",type=Path,required=True)
    p.add_argument("--to-graph",type=Path,required=True)
    p.add_argument("--native-endpoints",type=Path,required=True)
    p.add_argument("--expected-native-endpoints-sha256",required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    if args.output.exists() or args.output.is_symlink():
        raise ValueError("Refuse to overwrite immutable original evidence")
    if fingerprint(args.native_endpoints)!=args.expected_native_endpoints_sha256:
        raise ValueError("Native source edge reader changed")
    d=json.loads(args.catalog.read_text())
    hashes=d["graphFingerprints"]
    assert fingerprint(args.from_graph)==hashes["from"]
    assert fingerprint(args.to_graph)==hashes["to"]
    if d.get("sourceDiscoveryComplete") is not False or d.get("productionPublication")!="BLOCKED":
        raise ValueError("Cannot certify an invented complete production source catalog")
    areas={"italy-nord-est":args.from_config,"austria":args.to_config}
    rows=d["connections"]
    neighbor_shapes={}
    roots={}
    shapes={}
    with tempfile.TemporaryDirectory(prefix="f8-source-terminal-gate-") as tmp:
        work=Path(tmp)
        for region,config in areas.items():
            ids={x["sourceFinalDirectedGraphId"] for x in rows if x["sourceRegionId"]==region}
            if not ids:continue
            original=hierarchy_rows(args.native_endpoints,config,ids,work)
            native_edges=native_lines(args.native_endpoints,config,ids,work)
            for gid,root in original.items():
                roots[(region,gid)]=root
                shapes[(region,gid)]=native_edges[gid]
            allids=set()
            for root in original.values():
                for node in root["nativeAllHierarchyContinuationNodes"]:
                    allids.update(x["graphId"] for x in node["allOutgoingDirectedEdges"]
                                  if x["graphId"]!=root["opposingGraphId"])
            neighbor_shapes[region]=native_lines(
                args.native_endpoints,config,allids,work)
        output=gate_catalog(d,roots,shapes,neighbor_shapes)
    output["originalSourceFinalTopologyInputSHA256"]={
        "candidateCatalog":fingerprint(args.catalog),
        "nativeEndpoints":fingerprint(args.native_endpoints),
        "fromGraph":fingerprint(args.from_graph),
        "toGraph":fingerprint(args.to_graph)}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile("w",delete=False,dir=args.output.parent,
                                      prefix=".f8-source-final-",encoding="utf8") as file:
        staged=Path(file.name)
        json.dump(output,file,separators=(",",":"),allow_nan=False)
        file.write("\n")
    try:os.link(staged,args.output)
    finally:staged.unlink(missing_ok=True)
    print("F8_SOURCE_FINAL_GATE",output["additionalSourceFinalGateCounts"],flush=True)
    print("F8_CATALOG",args.output,hashlib.sha256(args.output.read_bytes()).hexdigest(),flush=True)


if __name__=="__main__":
    try:main()
    except (OSError,ValueError,AssertionError,TypeError,KeyError,IndexError) as exc:
        raise SystemExit("F8_SOURCE_FINAL_GATE_ERROR: "+str(exc)[:450])
