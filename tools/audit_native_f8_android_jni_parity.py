#!/usr/bin/env python3
"""Compare actual Android F8 JNI raw-edge captures with the native GraphReader scan.

The scanner can silently cap each request at 512. Android Kotlin additionally
groups distinct receiver GraphIds by receiverRoadKey. This audit reports
per-window missing ids and post-grouping losses; it cannot authenticate a
device by accepting a user-supplied JSON label. Actual same-graph device
capture and independent provenance are required for parity acceptance.
No crossing/road catalogue, no geometry filters, no Android mutation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from build_native_f8_pair_evidence import validated_scan, pair_identity, source_scans
from capture_native_f8_graph_windows import read

MAX_JNI_RESULTS = 512
SCHEMA = "roadpilot.android-actual-f8-jni-scan-capture"


def inspect_window(native_edges: list[dict], entry: dict) -> dict:
    bounds = entry.get("bounds")
    if (not isinstance(bounds, dict)
            or set(bounds) != {"minLat", "maxLat", "minLon", "maxLon"}):
        raise ValueError("Android JNI window must name all four exact bounds")
    for name,limit in (("minLat",90),("maxLat",90),
                       ("minLon",180),("maxLon",180)):
        x = bounds[name]
        if type(x) not in (float,int) or not math.isfinite(x) or abs(x)>limit:
            raise ValueError("Invalid JNI scan bounds")
    if not (bounds["minLat"] < bounds["maxLat"]
            and bounds["minLon"] < bounds["maxLon"]):
        raise ValueError("Invalid JNI scan bounding box ordering")
    req = entry.get("requestedMaxResults")
    if type(req) is not int or req < 1:
        raise ValueError("Missing Android JNI requested max-results")
    returned = entry.get("returned")
    raw = entry.get("rawGraphIds")
    if (not isinstance(raw,list) or type(returned) is not int
            or returned != len(raw) or len(raw)>min(req,MAX_JNI_RESULTS)):
        raise ValueError("Invalid Android JNI raw selection/count")
    if (any(type(g) is not int or g<=0 for g in raw)
            or len(set(raw))!=len(raw)):
        raise ValueError("Duplicate or invalid Android JNI directed GraphIds")
    after = entry.get("afterKotlinRoadKeyGroupingGraphIds")
    if (not isinstance(after,list)
            or any(type(g) is not int or g<=0 for g in after)
            or len(after)!=len(set(after))
            or not set(after).issubset(set(raw))):
        raise ValueError("Malformed Android Kotlin grouped edge IDs")
    expected = {
        row["graphId"]
        for row in native_edges
        if bounds["minLat"]<=row["lat"]<=bounds["maxLat"]
        and bounds["minLon"]<=row["lon"]<=bounds["maxLon"]
    }
    seen=set(raw)
    missing=sorted(expected-seen)
    unknown=sorted(seen-expected)
    hidden=sorted(seen-set(after))
    saturated=returned >= min(req,MAX_JNI_RESULTS)
    return {
        "windowIdentity":bounds,
        "nativeGraphStudioDistinctDirectedEdgesInWindow":len(expected),
        "actualJNIRequested":req,
        "actualJNIReturned":returned,
        "actualJNIHardCap":MAX_JNI_RESULTS,
        "nativeDirectedIdsMissingFromJNI":missing,
        "JNIDirectedIdsMissingFromNative":unknown,
        "receiverRoadKeyGroupedAwayGraphIds":hidden,
        "jniWindowMayBeTruncated":saturated,
        "allDirectedAlternativesPreservedThroughKotlin":not hidden,
        "losslessWindowParity":not missing and not unknown and not hidden and not saturated,
    }


def audit(pair:dict,native:dict,capture:dict,direction:str)->dict:
    pair_identity(pair)
    if direction not in ("from-to","to-from"):
        raise ValueError("Unknown independent native F8 travel direction")
    side = "to" if direction=="from-to" else "from"
    if capture.get("schema")!=SCHEMA or capture.get("version")!=1:
        raise ValueError("Unknown actual JNI scanner capture schema")
    graph_info={
        "graphId":pair[side+"RegionId"],
        "fingerprint":pair[side+"GraphFingerprint"],
        "boundary":pair[side+"BoundaryFingerprint"],
    }
    if (capture.get("regionId")!=graph_info["graphId"]
            or capture.get("graphFingerprint")!=graph_info["fingerprint"]
            or capture.get("boundaryFingerprint")!=graph_info["boundary"]
            or capture.get("direction")!=direction):
        raise ValueError("Android JNI capture graph/direction fingerprints mismatch")
    validated_scan(native,side)
    windows=capture.get("windows")
    if not isinstance(windows,list) or not windows:
        raise ValueError("Android JNI capture must include at least one real scan window")
    if len(windows)>10000:
        raise ValueError("JNI capture window count beyond audit bound")
    seen_windows=set()
    examined=[]
    for item in windows:
        if not isinstance(item,dict):
            raise ValueError("Malformed JNI capture window")
        details=inspect_window(native["edges"],item)
        key=tuple(details["windowIdentity"][f]
                  for f in ("minLat","maxLat","minLon","maxLon"))
        if key in seen_windows:
            raise ValueError("Duplicate actual JNI scan window")
        seen_windows.add(key)
        examined.append(details)
    catalog={
        tuple(v[f] for f in ("minLat","maxLat","minLon","maxLon"))
        for v in native["windows"]
    }
    covered=seen_windows==catalog
    outcomes={
        "losslessScopedWindows":sum(x["losslessWindowParity"] for x in examined),
        "jniSaturatedWindows":sum(x["jniWindowMayBeTruncated"] for x in examined),
        "receiverRoadKeyLostDistinctEdges":sum(len(x["receiverRoadKeyGroupedAwayGraphIds"])
                                             for x in examined),
        "nativeDirectedIdsNotReturnedByJNI":sum(len(x["nativeDirectedIdsMissingFromJNI"])
                                               for x in examined),
        "androidEmittedIdsAbsentFromNative":sum(len(x["JNIDirectedIdsMissingFromNative"])
                                               for x in examined),
    }
    return {
        "schema":"roadpilot.f8-jni-native-graph-parity-audit",
        "version":1,
        "pairId":pair["pairId"],
        "direction":direction,
        "regionId":graph_info["graphId"],
        "graphFingerprint":graph_info["fingerprint"],
        "boundaryFingerprint":graph_info["boundary"],
        "androidBuildCommit":capture.get("androidBuildCommit"),
        "reportedDevice":capture.get("device"),
        "reportedCaptureSource":capture.get("captureSource"),
        "actualAndroidDeviceEvidenceAuthentication":
            "NOT_VERIFIED_REQUIRES_INDEPENDENT_ON_DEVICE_CAPTURE_ATTESTATION",
        "exactOriginalWindowCatalogMatches":covered,
        "scopedWindowsExamined":len(examined),
        "nativeFullWindowCatalogCount":len(catalog),
        "lossCounters":outcomes,
        "perWindow":examined,
        "f8GraphEdgeParity":"NOT_VERIFIED",
        "reason":(
            "Source-window and Kotlin road-key losses or saturation must be "
            "resolved; even all lossless rows cannot alone authenticate an "
            "actual JNI capture or prove Android F8 full-graph/route equivalence"
        ),
        "productionPublication":"BLOCKED",
    }


def main()->int:
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ("pair","android-capture","output"):
        parser.add_argument("--"+name,required=True,type=Path)
    parser.add_argument("--native-capture",type=Path)
    parser.add_argument("--from-native-scan",type=Path)
    parser.add_argument("--to-native-scan",type=Path)
    parser.add_argument("--native-summary",type=Path)
    parser.add_argument("--direction",choices=("from-to","to-from"),
                        required=True)
    args=parser.parse_args()
    pair=read(args.pair)
    if args.native_capture:
        if any((args.from_native_scan,args.to_native_scan,args.native_summary)):
            parser.error("Provide either native capture or both retained scan sides/summary")
        a,b,provenance=source_scans(pair,capture=read(args.native_capture))
    else:
        if not all((args.from_native_scan,args.to_native_scan,args.native_summary)):
            parser.error("Both complete native side scans and their exact summary required")
        a,b,provenance=source_scans(
            pair,from_scan=read(args.from_native_scan),
            to_scan=read(args.to_native_scan),
            scan_summary=read(args.native_summary))
    native=b if args.direction=="from-to" else a
    doc=audit(pair,native,read(args.android_capture),args.direction)
    doc["verifiedNativeScanProvenance"]=provenance
    args.output.parent.mkdir(parents=True,exist_ok=True)
    if args.output.exists():
        raise ValueError("Refusing to overwrite parity audit")
    import os,tempfile
    with tempfile.NamedTemporaryFile(
            "w",encoding="utf-8",dir=args.output.parent,
            prefix=".native-jni-audit-",delete=False) as fd:
        tmp=Path(fd.name)
        json.dump(doc,fd,indent=2)
        fd.write("\n")
    try:
        os.link(tmp,args.output)
    finally:
        tmp.unlink(missing_ok=True)
    print("Android JNI parity remains NOT_VERIFIED; detailed source-window "
          "loss and grouping diagnostics written to an immutable report.")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
