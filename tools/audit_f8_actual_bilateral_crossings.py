#!/usr/bin/env python3
"""Inventory only actual bilateral F8 outward road/direction crossing candidates.

An ORIGINAL source directed road must:
  * be a non-shortcut road usable in car/motorcycle forward travel;
  * cross OUTWARD over its own retained graph's 25km cut;
  * have its ORIGINAL directed geometry touch the receiving region's
    original nominal Geofabrik core.
This is an evidence scope, NOT a source-final or valid A/B connection proof.
Unrelated roads exiting the source buffer in other countries are excluded.
GraphId is never grouped by name, OSM way, approximate GPS or first success.
"""
from __future__ import annotations
import argparse,hashlib,json,os,tempfile
from collections import Counter
from pathlib import Path
from shapely.geometry import LineString
from shapely.prepared import prep
from build_f8_final_edge_connections import native_lines, fingerprint
from native_f8_inputs import load_polygon

SCHEMA = "roadpilot.f8-bilateral-original-outward-source-cut-coverage"
ORIGINAL_SOURCE_ARCHIVE_SCHEMA = "roadpilot.f8-all-original-source-archive-tile-cut-census"


def in_scope(original: dict) -> bool:
    modes=original.get("vehicleModes",{})
    return (
        original.get("originalSourceBufferCutDirectedTravel") ==
            "OUTWARD_FROM_ORIGINAL_SOURCE_BUFFER"
        and original.get("nativeIsRoad") is True
        and original.get("nativeIsShortcut") is False
        and (modes.get("auto") is True or modes.get("motorcycle") is True)
    )


def classification(original: dict, geometry: list, receiver_core,
                   connected: dict, unresolved: dict) -> dict | None:
    """Return EXACT original A directed candidate or None if unrelated region."""
    if not in_scope(original):
        return None
    gid=original["originalDirectedGraphId"]
    if len(geometry)<2:
        raise ValueError("Original A directed cut lacks geometry")
    shape=LineString([(float(lon),float(lat)) for lat,lon in geometry])
    if not shape.is_valid or shape.length==0:
        raise ValueError("Original A directed cut corrupt")
    if not receiver_core.intersects(shape):
        return None
    result={
        "originalOutwardSourceCutDirectedGraphId":gid,
        "originalSourceWayIdAnnotationOnly":original["originalWayIdAnnotationOnly"],
        "originalDirectedTerminalCoordinate":{"lat":geometry[-1][0],
                                               "lng":geometry[-1][1]},
        "carMode":original["vehicleModes"]["auto"],
        "motorcycleMode":original["vehicleModes"]["motorcycle"],
        "nativeOriginalSourceLastTripLeg":"NOT_PROVED_BY_CUT_GEOMETRY",
        "originalReceivingFirstTripLeg":"NOT_PROVED_BY_CUT_GEOMETRY",
        "status":"CROSSING_CANDIDATE_ONLY"
    }
    if gid in connected:
        result["status"]="EXACT_ORIGINAL_FINAL_SOURCE_GRAPHID_HAS_VALHALLA_B_PEER"
        result["verifiedReceiverOriginalDirectedOptions"]=[
            x["receiverFirstDirectedGraphId"] for x in connected[gid]["receiverOptions"]]
    elif gid in unresolved:
        result["status"]="ORIGINAL_SOURCE_CUT_GRAPHID_PREVIOUSLY_UNRESOLVED"
        result["unresolvedReason"]=unresolved[gid]["status"]
    else:
        result["status"]="NOT_IN_VERIFIED_OR_UNRESOLVED_SOURCE_REGISTRY"
    return result


def audit(args):
    if args.output.exists() or args.output.is_symlink():
        raise ValueError("Refusing to overwrite immutable source crossing audit")
    filepaths={
        "originalArchive":args.original_archive,
        "catalog":args.catalog,
        "italyGraph":args.from_graph,
        "austriaGraph":args.to_graph,
        "italyCore":args.from_core,
        "austriaCore":args.to_core,
        "originalNativeEndpoints":args.native_endpoints
    }
    hashes={k:fingerprint(v) for k,v in filepaths.items()}
    if hashes["originalNativeEndpoints"]!=args.expected_native_endpoints_sha256:
        raise ValueError("Original native GraphReader binary fingerprint mismatch")
    archive=json.loads(args.original_archive.read_text())
    catalog=json.loads(args.catalog.read_text())
    if archive.get("schema")!=ORIGINAL_SOURCE_ARCHIVE_SCHEMA or archive.get("version")!=1:
        raise ValueError("Original full archive cut inventory missing")
    if archive.get("originalGraphArchiveTileInventory") != (
            "ALL_GRAPHREADER_GETTILESET_TILES_ENUMERATED"):
        raise ValueError("Not an all-original-source-tile cut inventory")
    if catalog.get("schema")!="roadpilot.f8-final-directed-connections" or (
            catalog.get("sourceDiscoveryComplete") is not False) or (
            catalog.get("productionPublication")!="BLOCKED"):
        raise ValueError("Partial original A/B source-final catalog required")
    if catalog["pairId"]!=archive["pairId"] or catalog["graphFingerprints"] != {
        "from":hashes["italyGraph"],"to":hashes["austriaGraph"]}:
        raise ValueError("Bilateral crossing audit original graph SHA mismatch")
    if archive["sourceGraphFingerprints"] != catalog["graphFingerprints"]:
        raise ValueError("Archive source-cut graph SHA mismatch")
    cores={"italy-nord-est":prep(load_polygon(args.from_core)),
           "austria":prep(load_polygon(args.to_core))}
    doc={"schema":SCHEMA,"version":1,"pairId":catalog["pairId"],
         "sourceDiscoveryComplete":False,"productionPublication":"BLOCKED",
         "scope":"ONLY_OUTWARD_ORIGINAL_DIRECTED_ROADS_TOUCHING_ACTUAL_PEER_NOMINAL_CORE",
         "sourceLedgerSha256":hashes["catalog"],
         "originalArchiveCutSha256":hashes["originalArchive"],
         "originalImmutableInputSHA256":hashes,"regions":{}}
    for side,source,receiver,config in (
        ("from-to","italy-nord-est","austria",args.from_config),
        ("to-from","austria","italy-nord-est",args.to_config)):
        allcuts=archive["directions"][side]["allOriginalDirectedCutObservations"]
        out=[x for x in allcuts if in_scope(x)]
        ids={x["originalDirectedGraphId"] for x in out}
        if len(ids)!=len(out):
            raise ValueError("Original source outgoing GraphIds not unique")
        connected={r["sourceFinalDirectedGraphId"]:r for r in catalog["connections"]
                   if r["sourceRegionId"]==source}
        unresolved={r["sourceFinalDirectedGraphId"]:r
                    for r in catalog["unresolvedSourceFinalEdges"]
                    if r["sourceRegionId"]==source}
        with tempfile.TemporaryDirectory(prefix="f8-real-outward-only-") as t:
            shapes=native_lines(args.native_endpoints,config,ids,Path(t))
        stats=Counter()
        selected=[]
        for row in out:
            candidate=classification(row,shapes[row["originalDirectedGraphId"]][
                "directedGeometry"],cores[receiver],connected,unresolved)
            if candidate is None:
                stats["outwardRoadsNotTouchingThisReceiverCore"]+=1
                continue
            candidate["sourceRegionId"]=source
            candidate["receiverRegionId"]=receiver
            selected.append(candidate)
            stats[candidate["status"]]+=1
            stats["outwardRoadsTouchingActualPeerCore"]+=1
        stats["allOutwardOriginalRoadModeAccessibleCutDirectedGraphIds"]=len(out)
        stats["allOriginalDirectedArchiveCutObservations"]=len(allcuts)
        doc["regions"][side]={
            "sourceRegionId":source,"receiverRegionId":receiver,
            "counts":dict(stats),
            "actualPeerCoreOriginalDirectedRoadCutCandidates":selected}
        print(side,dict(stats),flush=True)
    for k,src in filepaths.items():
        if fingerprint(src)!=hashes[k]:
            raise ValueError("Original graph or audit input mutated")
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile("w",delete=False,dir=args.output.parent,
                                     prefix=".f8-real-outward-",encoding="utf8") as f:
        staged=Path(f.name)
        json.dump(doc,f,separators=(",",":"),allow_nan=False);f.write("\n")
    try:os.link(staged,args.output)
    finally:staged.unlink(missing_ok=True)
    print("F8_ONLY_RELEVANT_CROSSING_CANDIDATES",args.output,
          fingerprint(args.output),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for item in ("original-archive","catalog","from-core","to-core",
                 "from-config","to-config","from-graph","to-graph",
                 "native-endpoints","output"):
        p.add_argument("--"+item,type=Path,required=True)
    p.add_argument("--expected-native-endpoints-sha256",required=True)
    audit(p.parse_args())

if __name__=="__main__":
    main()
