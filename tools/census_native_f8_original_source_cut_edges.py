#!/usr/bin/env python3
"""Audit every WINDOW-SCANNED original SOURCE native GraphId at its own 25km cut.

The captured overlap-window inventory is not a complete original graph tile
archive inventory. This independent cut-first audit is therefore an input to,
not proof of, the final physical-road directed-edge completeness gate. It NEVER
uses an OSM producer, clusters way/name/position, selects handoffs or
touches the receiving graph's road correlation. Original source direction
is annotated at the actual graph-build buffer boundary, not inferred from
a successful local final-edge route.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import threading

from shapely.geometry import LineString, Point

from build_native_f8_pair_evidence import pair_identity, source_scans
from build_native_f8_final_edge_register import digest, pinned
from capture_native_f8_graph_windows import read
from census_native_f8_final_directed_edges import verify_binary, verify_window_coverage
from native_f8_inputs import graph_manifest_info
from probe_native_f8_clipped_terminal import CRS, verified_buffer
from probe_native_f8_journey import verify_retained_graph_identity

SCHEMA = "roadpilot.f8-original-all-source-native-directed-cut-census"
MODES = {"auto": 1, "motorcycle": 1024}
MAX_VERTICES = 8192
# Native GraphReader may be handed an untrusted or corrupt graph/archive.
# Bound one serialized geometry record before JSON parsing and geometry allocation.
MAX_NATIVE_JSON_LINE_CHARS = 1_000_000
MAX_NATIVE_CUT_SCAN_SECONDS = 3600


def read_native_json_line(stdout) -> dict:
    raw = stdout.readline(MAX_NATIVE_JSON_LINE_CHARS + 1)
    if len(raw) > MAX_NATIVE_JSON_LINE_CHARS or not raw.endswith("\n"):
        raise ValueError("Original GraphReader geometry line oversized or truncated")
    return json.loads(raw)


def check_native_directed_shape(expected: dict, row: dict, source_buffer: dict) -> dict | None:
    """Validate exact native original edge then observe geometry/cut direction.

    Pure: no name, way, position or direction eligibility filter. A cut
    encounter is an observation, not a complete physical-road identity.
    """
    if not isinstance(expected, dict) or not isinstance(row, dict):
        raise ValueError("Malformed original directed native source row")
    for source_name, native_name in (
            ("graphId", "sourceGraphId"), ("wayId", "wayId"),
            ("forwardAccess", "forwardAccess"), ("reverseAccess", "reverseAccess")):
        original_id, native_id = expected.get(source_name), row.get(native_name)
        if (type(original_id) is not int or type(native_id) is not int
                or original_id < 0 or original_id != native_id):
            raise ValueError("Original source/native GraphReader identity or access changed")
    if type(row.get("forward")) is not bool or type(row.get("deadend")) is not bool:
        raise ValueError("Missing original native direction/terminal flags")
    if type(row.get("endNodeGraphId")) is not int or row["endNodeGraphId"] <= 0:
        raise ValueError("Invalid original native directed end GraphId")
    geo = row.get("directedGeometry")
    if not isinstance(geo, list) or not 2 <= len(geo) <= MAX_VERTICES:
        raise ValueError("Missing/truncated original source directed edge geometry")
    vertices = []
    for vertex in geo:
        if (not isinstance(vertex, list) or len(vertex) != 2
                or any(type(v) not in (int,float) or not math.isfinite(v)
                       for v in vertex)
                or abs(vertex[0]) > 90 or abs(vertex[1]) > 180):
            raise ValueError("Corrupt original directed geometry")
        vertices.append(CRS.transform(vertex[1],vertex[0]))
    shape = LineString(vertices)
    if not shape.is_valid or shape.length <= 0:
        raise ValueError("Invalid original directed geometry polyline")
    boundary = source_buffer["polygon"].boundary
    if not shape.intersects(boundary):
        return None
    start_inside = source_buffer["polygon"].covers(Point(vertices[0]))
    end_inside = source_buffer["polygon"].covers(Point(vertices[-1]))
    if start_inside and not end_inside:
        direction = "OUTWARD_FROM_ORIGINAL_SOURCE_BUFFER"
    elif not start_inside and end_inside:
        direction = "INWARD_TOWARD_ORIGINAL_SOURCE_BUFFER"
    elif start_inside and end_inside:
        direction = "BOTH_ENDPOINTS_WITHIN_BUFFER_CUT_INTERSECTION"
    else:
        direction = "BOTH_ENDPOINTS_OUTSIDE_BUFFER_CUT_INTERSECTION"
    return {
        "originalDirectedGraphId": row["sourceGraphId"],
        "nativeEndNodeGraphId": row["endNodeGraphId"],
        "originalWayIdAnnotationOnly": row["wayId"],
        "originalNativeForwardOrientationAnnotationOnly": row["forward"],
        "originalNativeDeadend": row["deadend"],
        "nativeOriginalForwardAccess": row["forwardAccess"],
        "originalSourceBufferCutDirectedTravel": direction,
        "nativeDirectedStartInsideOwn25kmBuffer": start_inside,
        "nativeDirectedEndInsideOwn25kmBuffer": end_inside,
        "carModeForwardAccess": bool(row["forwardAccess"] & MODES["auto"]),
        "motorcycleModeForwardAccess": bool(row["forwardAccess"] & MODES["motorcycle"]),
        "physicalRoadDirectionEquivalence": "NOT_VERIFIED",
        "candidateSuppressed": False,
    }


def audit_original_native_side(binary: Path, config: Path, edges: list,
                               source_buffer: dict, work: Path, side: str) -> dict:
    if not isinstance(edges, list) or not edges:
        raise ValueError("Original complete native source edge scan missing")
    sorted_edges = sorted(edges, key=lambda e:e["graphId"])
    ids = [row["graphId"] for row in sorted_edges]
    if len(ids) != len(set(ids)):
        raise ValueError("Repeated original source directed GraphId in native source")
    file = work / (side+"-every-source-graphid.txt")
    with file.open("w",encoding="ascii") as fd:
        for gid in ids:fd.write(str(gid)+"\n")
    errors = work / (side+"-native-errors.txt")
    hits = []
    classifications = Counter()
    counts = Counter()
    with errors.open("w+",encoding="utf8") as err:
        with subprocess.Popen(
                [str(binary),str(config),str(file),"--geometry"],
                stdout=subprocess.PIPE,stderr=err,text=True,bufsize=1024*1024) as native:
            # A stalled GraphReader must not hold an audit forever. This
            # watchdog includes stdout streaming/JSON parsing time; wait()
            # alone cannot time out a blocked readline().
            watchdog = threading.Timer(MAX_NATIVE_CUT_SCAN_SECONDS, native.kill)
            watchdog.daemon = True
            watchdog.start()
            try:
                for i, expected in enumerate(sorted_edges):
                    observation = check_native_directed_shape(
                        expected, read_native_json_line(native.stdout), source_buffer)
                    counts["originalSourceDirectedGraphIdsAudited"]+=1
                    if observation is not None:
                        hits.append(observation)
                        classifications[observation["originalSourceBufferCutDirectedTravel"]]+=1
                        if observation["carModeForwardAccess"]:
                            counts["carSourceCutDirectedShapeObservations"]+=1
                        if observation["motorcycleModeForwardAccess"]:
                            counts["motorcycleSourceCutDirectedShapeObservations"]+=1
                if native.stdout.readline():
                    raise ValueError("Original native geometry emitted extra GraphIds")
            except BaseException:
                native.kill();native.wait();raise
            finally:
                watchdog.cancel()
            exitcode = native.wait(timeout=900)
        if exitcode:
            err.seek(0)
            raise ValueError("Original source GraphReader cut scan failed: "
                             +err.read()[-400:])
    if counts["originalSourceDirectedGraphIdsAudited"]!=len(edges):
        raise ValueError("Native original source GraphId coverage incomplete")
    return {
        "originalSourceDirectedGraphIdsAudited":len(sorted_edges),
        "originalSourceDirectedCutShapeCount":len(hits),
        "originalSourceBufferDirectionalCutClassifications":dict(
            sorted(classifications.items())),
        "modeAnnotations":dict(sorted(counts.items())),
        "allOriginalDirectedCutObservations":hits,
        "sourceCutObservationScope":"ALL_RETAINED_ORIGINAL_GRAPHREADER_SCAN_GRAPHIDS",
        "globalPhysicalRoadEquivalence":"NOT_VERIFIED",
        "noOriginalSourceRoadExcludedByNameWayOrProximity":True,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ("pair","from-manifest","to-manifest","from-buffer","to-buffer",
                 "from-native-scan","to-native-scan","native-summary","native-binary","output"):
        ap.add_argument("--"+name,type=Path,required=True)
    ap.add_argument("--expected-native-binary-sha256",required=True)
    for name in ("from-native-scan", "to-native-scan", "native-summary"):
        ap.add_argument("--expected-"+name+"-sha256",required=True)
    args = ap.parse_args()
    if args.output.exists() or args.output.is_symlink():
        raise ValueError("Refusing to replace immutable native source cut-first census")
    files = {key:getattr(args,key.replace("-","_")) for key in (
        "pair","from-manifest","to-manifest","from-buffer","to-buffer",
        "from-native-scan","to-native-scan","native-summary","native-binary")}
    original = {key:digest(path) for key,path in files.items()}
    for name in ("from-native-scan", "to-native-scan", "native-summary"):
        pinned(files[name], getattr(args, "expected_"+name.replace("-","_")+"_sha256"))
    actual_binary = verify_binary(args.native_binary,args.expected_native_binary_sha256)
    pair = read(args.pair)
    pair_identity(pair)
    summary = read(args.native_summary)
    first,second,provenance = source_scans(
        pair,from_scan=read(args.from_native_scan),
        to_scan=read(args.to_native_scan),scan_summary=summary)
    own_a = verified_buffer(args.from_buffer,read(args.from_manifest))
    own_b = verified_buffer(args.to_buffer,read(args.to_manifest))
    windows = verify_window_coverage(first,second,args.from_buffer,args.to_buffer,
                                      summary["defaultWindowDegrees"])
    ma,mb=read(args.from_manifest),read(args.to_manifest)
    with tempfile.TemporaryDirectory(prefix="f8-original-source-cut-first-") as work:
        tmp=Path(work)
        graph_a,cfg_a = graph_manifest_info(args.from_manifest,pair["fromRegionId"],
            mb["source"]["primaryGeofabrikId"],pair["fromBoundaryFingerprint"],tmp,"A")
        graph_b,cfg_b = graph_manifest_info(args.to_manifest,pair["toRegionId"],
            ma["source"]["primaryGeofabrikId"],pair["toBoundaryFingerprint"],tmp,"B")
        verify_retained_graph_identity(pair,graph_a,graph_b)
        a = audit_original_native_side(
            args.native_binary,cfg_a,first["edges"],own_a,tmp,"A")
        print("from source cut-first scan:",a["originalSourceDirectedGraphIdsAudited"],
              "GraphIds,",a["originalSourceDirectedCutShapeCount"],"cut directed edges",
              flush=True)
        b = audit_original_native_side(
            args.native_binary,cfg_b,second["edges"],own_b,tmp,"B")
        print("to source cut-first scan:",b["originalSourceDirectedGraphIdsAudited"],
              "GraphIds,",b["originalSourceDirectedCutShapeCount"],"cut directed edges",
              flush=True)
    for side,manifest_path,man in (
            ("from",args.from_manifest,ma),("to",args.to_manifest,mb)):
        if digest(manifest_path.parent/man["artifact"]["fileName"])!=pair[
                side+"GraphFingerprint"]:
            raise ValueError("Original native graph archive mutated during full cut census")
    if any(digest(path)!=original[key] for key,path in files.items()):
        raise ValueError("Original native source scan inputs modified during cut census")
    doc={
        "schema":SCHEMA,"version":1,"pairId":pair["pairId"],
        "sourceGraphFingerprints":{
            "from":pair["fromGraphFingerprint"],
            "to":pair["toGraphFingerprint"]},
        "originalSourceInputSHA256":original,
        "nativeBinarySHA256":actual_binary,
        "originalSourceScanProvenance":provenance,
        "verifiedOriginalOverlapWindows":windows,
        "directions":{"from-to":a,"to-from":b},
        "sourceCutCompleteness":"ALL_RETAINED_SOURCE_SCAN_ORIGINAL_DIRECTED_GRAPHIDS",
        "physicalRoadDirectionToOneLastEdgeMap":"NOT_VERIFIED",
        "sourceCutDirectedEdgesMappedToTruePhysicalRoadLastEdges":"NOT_VERIFIED",
        "receivingGraphCorrelation":"NOT_STARTED",
        "productionPublication":"BLOCKED",
    }
    args.output.parent.mkdir(parents=True,exist_ok=True)
    stage=None
    try:
        with tempfile.NamedTemporaryFile("w",encoding="utf8",dir=args.output.parent,
                prefix=".f8-source-cut-first-",delete=False) as stream:
            stage=Path(stream.name)
            json.dump(doc,stream,indent=2,allow_nan=False)
            stream.write("\n")
        if args.output.exists() or args.output.is_symlink():
            raise ValueError("Concurrent original source cut census output")
        os.link(stage,args.output)
    finally:
        if stage is not None:stage.unlink(missing_ok=True)
    print("Native source cut-first census complete; unique physical road FINAL",
          "NOT_VERIFIED, receiving B NOT_STARTED, publication BLOCKED.")
    return 0


if __name__=="__main__":
    try:
        raise SystemExit(main())
    except (OSError,ValueError,KeyError,IndexError,TypeError) as exc:
        raise SystemExit("F8_SOURCE_CUT_FIRST_ERROR: "+str(exc)[:350])
