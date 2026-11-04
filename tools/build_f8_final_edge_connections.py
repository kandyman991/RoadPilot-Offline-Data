#!/usr/bin/env python3
"""F8: one source-final directed edge -> physical forward B edge -> Valhalla.

Run on already-built, immutable regional graphs. This is a CONNECTION producer,
not an OSM, name, proximity grouping or archive census. It keeps branches and
mode failures explicit. One source GraphId has one connection record and may
carry distinct proven receiving branches; modes are attributes of those edges.
"""
from __future__ import annotations

import argparse
from bisect import bisect_left, bisect_right
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile

from pyproj import Transformer
from shapely.geometry import LineString, Point

from build_native_f8_pair_evidence import pair_identity, source_scans
from native_f8_original_route import route_with_original_ids, verify_native_route_binary

MODES = ("auto", "motorcycle")
MODE_BITS = {"auto": 1, "motorcycle": 1024}
PROVED = "ORIGINAL_SOURCE_LAST_DIRECTED_TRIPLEG_GRAPHID_MATCHED"
SCHEMA = "roadpilot.f8-final-directed-connections"
VERSION = 1
# These are geometric continuation validation tolerances, NOT pre-Valhalla
# route eligibility or filters on road name, way ID, road class or mode.
TOUCH_METRES = 3.0
MIN_DOWNSTREAM_METRES = 2.0
FORWARD_COSINE = 0.25
RECEIVER_SCAN_ANCHOR_LAT_DEGREES = 0.009
PROJECT = Transformer.from_crs("EPSG:4326", "EPSG:3035", always_xy=True)
UNPROJECT = Transformer.from_crs("EPSG:3035", "EPSG:4326", always_xy=True)


def fingerprint(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise ValueError("Missing or symlinked immutable routing input")
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def native_lines(binary: Path, config: Path, ids: set[int], tmp: Path) -> dict[int, dict]:
    """Get the ACTUAL directed geometry for every source or receiver GraphId."""
    if not ids:
        return {}
    if any(type(x) is not int or x <= 0 for x in ids):
        raise ValueError("Native directed GraphId is invalid")
    path = tmp / ("native-ids-%d.txt" % len(list(tmp.iterdir())))
    path.write_text("".join(str(x) + "\n" for x in sorted(ids)), encoding="ascii")
    run = subprocess.run(
        [str(binary), str(config), str(path), "--geometry"],
        capture_output=True, text=True, check=False, timeout=160)
    if run.returncode:
        raise ValueError("Original native edge extraction failed: " + run.stderr[-280:])
    result = {}
    for line in run.stdout.splitlines():
        row = json.loads(line)
        gid = row.get("sourceGraphId")
        if (type(gid) is not int or gid not in ids or gid in result
                or type(row.get("forwardAccess")) is not int
                or not isinstance(row.get("directedGeometry"), list)
                or len(row["directedGeometry"]) < 2):
            raise ValueError("Native directed shape or GraphId inventory inconsistent")
        result[gid] = row
    if set(result) != ids:
        raise ValueError("Original native edge extraction incomplete")
    return result


def directed_line(edge: dict) -> LineString:
    coords = edge.get("directedGeometry")
    if not isinstance(coords, list) or len(coords) < 2:
        raise ValueError("Native directed geometry missing")
    shape = LineString([PROJECT.transform(float(lon), float(lat)) for lat, lon in coords])
    if shape.is_empty or not shape.is_valid or shape.length < 1:
        raise ValueError("Native directed road shape is zero-length or corrupt")
    return shape


def source_candidates(direct: dict, beyond: dict, pair: dict) -> dict[str, dict[int, set[str]]]:
    """Previously routed A-final IDs only. Each final ID is one record, not
    a distinct OSM-way/name and not two records for auto+motorcycle."""
    if (direct.get("pairId") != pair["pairId"]
            or beyond.get("pairId") != pair["pairId"]
            or direct.get("sourceGraphFingerprints") != {
                "from": pair["fromGraphFingerprint"],
                "to": pair["toGraphFingerprint"],
            }):
        raise ValueError("Original source proof graph/pair identity mismatch")
    outcome = {}
    for side in ("from-to", "to-from"):
        direct_rows = direct["directions"][side]["cutCandidateOriginalTripLegProof"]
        beyond_rows = beyond["directions"][side]["beyondCutOriginalFinalEdgeProofs"]
        records = {}
        for row in direct_rows:
            gid = row["originalNativeSourceDirectedGraphId"]
            if type(gid) is not int or gid <= 0 or gid in records:
                raise ValueError("Repeated original source final directed GraphId")
            modes = set()
            for mode in MODES:
                evidence = (row.get("vehicleModes") or {}).get(mode) or {}
                if (evidence.get("sourceLastEdgeProof") == PROVED
                        and evidence.get("originalNativeLastGraphId") == gid
                        and evidence.get("originalNativeTripLegDirectedGraphIds", [None])[-1] == gid):
                    modes.add(mode)
            if not modes or row.get("candidateSuppressed") is not False:
                raise ValueError("Original source final has no preserved Valhalla proof")
            records[gid] = modes
        for row in beyond_rows:
            gid = row["originalFinalDirectedGraphId"]
            if type(gid) is not int or gid <= 0 or gid in records:
                raise ValueError("Repeated beyond-cut source final directed GraphId")
            modes = set()
            for route in row["originalSourceOriginalValhallaTripLeg"]["originalSourceCutRouteProofs"]:
                for mode, proof in route["originalRouteModeProofs"].items():
                    if (mode in MODES and proof.get("sourceLastEdgeProof") == PROVED
                            and proof.get("originalNativeLastGraphId") == gid
                            and proof.get("originalNativeTripLegDirectedGraphIds", [None])[-1] == gid):
                        modes.add(mode)
            if not modes or row.get("noOriginalBranchesSuppressed") is not True:
                raise ValueError("Original beyond-cut source proof missing or suppressed")
            records[gid] = modes
        outcome[side] = records
    return outcome


def receiver_anchor_index(scan: dict) -> tuple[list[float], list[dict]]:
    edges = scan.get("edges")
    if not isinstance(edges, list) or not edges:
        raise ValueError("Missing actual native receiver scan")
    original = sorted(edges, key=lambda e: e["lat"])
    return [r["lat"] for r in original], original


def nearby_receiver_ids(index, x: tuple[float, float]) -> set[int]:
    """Broad index to FETCH physical candidate shapes. Never an acceptance
    predicate, and missing anchors are explicitly unresolved, not absent roads."""
    lats, rows = index
    lat, lon = x
    radius = RECEIVER_SCAN_ANCHOR_LAT_DEGREES
    lon_radius = radius / max(0.15, math.cos(math.radians(lat)))
    found = set()
    for row in rows[bisect_left(lats, lat-radius):bisect_right(lats, lat+radius)]:
        if abs(row["lon"]-lon) <= lon_radius:
            gid = row.get("graphId")
            if type(gid) is not int or gid <= 0:
                raise ValueError("Malformed native receiver scan GraphId")
            found.add(gid)
    return found


def physical_forward_continuation(source: LineString, receiving: LineString) -> dict | None:
    """Exact native directed shapes, not same-way/name/group key.
    Reverse retracing fails the FORWARD road correspondence; a sharp
    turn is preserved in unresolved alternatives for separate review."""
    x = Point(source.coords[-1])
    gap = receiving.distance(x)
    if gap > TOUCH_METRES:
        return None
    projection = receiving.project(x)
    remain = receiving.length - projection
    if remain < MIN_DOWNSTREAM_METRES:
        return None
    approach = source.interpolate(max(0, source.length-min(12.0,source.length*.7)))
    enter = (x.x-approach.x, x.y-approach.y)
    start = receiving.interpolate(projection)
    after = receiving.interpolate(min(receiving.length, projection+min(12.0,remain*.7)))
    leave = (after.x-start.x, after.y-start.y)
    denom = math.hypot(*enter)*math.hypot(*leave)
    if denom < 0.001:
        return None
    cosine = (enter[0]*leave[0]+enter[1]*leave[1])/denom
    reverse_overlap = receiving.intersection(source.buffer(2.0)).length
    status = ("FORWARD_CONTINUOUS" if cosine > FORWARD_COSINE
              and reverse_overlap < min(12.0,source.length*.75)
              else "REVERSE_OR_AMBIGUOUS_PHYSICAL_DIRECTION")
    return {
        "status": status, "seamGapMeters": round(gap, 3),
        "directionCosine": round(cosine, 5),
        "receiverProjectionMeters": round(projection, 3),
        "receiverForwardRemainingMeters": round(remain, 3),
        "reverseSourceGeometryOverlapMeters": round(reverse_overlap, 3),
    }


def local_receiver_probe(line: LineString, position_m: float) -> dict:
    remaining = line.length - position_m
    advance = min(80.0, max(2.1, remaining*.65))
    at = position_m + advance
    if at >= line.length:
        at = position_m+remaining*.72
    lon, lat = UNPROJECT.transform(*line.interpolate(at).coords[0])
    return {"lat": lat, "lng": lon}


def prove_receiver_modes(config: Path, binary: Path, point: dict, target: dict,
                         receiver_graphid: int, source_modes: set[str]) -> dict:
    results = {}
    for mode in sorted(source_modes):
        route = route_with_original_ids(config,point,target,mode,binary,timeout=75)
        exact = (route.get("status") == "SUCCEEDED"
                 and route.get("firstDirectedGraphId") == receiver_graphid
                 and type(route.get("startOffsetMeters")) in (int,float)
                 and type(route.get("endOffsetMeters")) in (int,float)
                 and route["startOffsetMeters"] <= TOUCH_METRES
                 and route["endOffsetMeters"] <= TOUCH_METRES)
        results[mode] = {
            "verified": bool(exact),
            "actualFirstDirectedGraphId": route.get("firstDirectedGraphId"),
            "startSnapMeters": route.get("startOffsetMeters"),
            "endSnapMeters": route.get("endOffsetMeters"),
            "distanceKm": route.get("distanceKm"),
            "durationSeconds": route.get("durationSeconds"),
            "originalTripLegDirectedGraphIds": route.get(
                "originalNativeDirectedGraphIds", []) if exact else [],
            "status": route.get("status"),
        }
    return results


def pair_connections(source: dict[int, dict], receiver: dict[int, dict],
                     receiver_scan: dict, direct_modes: dict[int, set[str]],
                     receiver_config: Path, route_binary: Path,
                     receiver_region: str, source_region: str,
                     receiver_fingerprint: str) -> tuple[list[dict], list[dict], dict]:
    """One connection record per ORIGINAL final source GraphId. Keep all
    separately proved receiving branches; no first-match or mode dedupe."""
    native_lines_by_id = {gid: directed_line(edge) for gid,edge in receiver.items()}
    index = receiver_anchor_index(receiver_scan)
    connections, unresolved = [], []
    counters = Counter()
    for gid, edge in sorted(source.items()):
        x = edge["directedGeometry"][-1]
        point = {"lat": x[0], "lng": x[1]}
        src_shape = directed_line(edge)
        modes = direct_modes[gid]
        candidates = nearby_receiver_ids(index,(point["lat"],point["lng"]))
        forward, ambiguous, deferred = [], [], []
        for receiver_gid in sorted(candidates):
            rec = receiver.get(receiver_gid)
            if rec is None:
                raise ValueError("Receiver native geometries missing a scanned candidate")
            shape = native_lines_by_id[receiver_gid]
            match = physical_forward_continuation(src_shape,shape)
            if match is None:
                # Not a proved mismatch: retain candidate for full source/receiver
                # coverage. Never silently lose a separate physical branch.
                deferred.append(receiver_gid)
                continue
            if match["status"] != "FORWARD_CONTINUOUS":
                ambiguous.append(receiver_gid)
                continue
            target = local_receiver_probe(shape, match["receiverProjectionMeters"])
            valhalla = prove_receiver_modes(
                receiver_config,route_binary,point,target,receiver_gid,modes)
            verified_modes = [mode for mode in sorted(modes) if valhalla[mode]["verified"]]
            counters["originalBModeProofCalls"] += len(modes)
            if verified_modes:
                forward.append({
                    "receiverFirstDirectedGraphId": receiver_gid,
                    "receiverGraphFingerprint": receiver_fingerprint,
                    "sourceWayIdAnnotationOnly": edge["wayId"],
                    "receiverWayIdAnnotationOnly": rec["wayId"],
                    "travelModes": verified_modes,
                    "directedPhysicalGeometry": match,
                    "originalReceiverValhallaTripLeg": valhalla,
                    "downstreamTestPoint": target,
                })
            else:
                ambiguous.append(receiver_gid)
        counters["sourceFinalEdgesConsidered"] += 1
        counters["geometricAmbiguousOrReverse"] += len(ambiguous)
        counters["receiverCandidatesPendingIndependentProof"] += len(deferred) + len(ambiguous)
        if forward:
            if len(set(x["receiverFirstDirectedGraphId"] for x in forward)) != len(forward):
                raise ValueError("Duplicate verified directed receiving edge")
            connections.append({
                "sourceRegionId": source_region,
                "receiverRegionId": receiver_region,
                "sourceFinalDirectedGraphId": gid,
                "sourceFinalCoordinate": point,
                "sourceValhallaProvedModes": sorted(modes),
                "receiverOptions": forward,
                # Unproved receiver possibilities are NOT discarded just because
                # some other receiving edge had a successful Valhalla proof.
                "unverifiedReceiverCandidateGraphIds": sorted(set(deferred + ambiguous)),
                "receiverAnchorCandidatesInspected": len(candidates),
                "receiverCandidateCensusComplete": False,
                "physicalRoadDirectionIdentity": {
                    "sourceFinalDirectedGraphId": gid,
                    "notOsMNameOrProximityDeduplication": True,
                },
            })
            counters["sourceWithAnyValhallaVerifiedForwardPeer"] += 1
            if any(set(o["travelModes"]) == set(MODES) for o in forward):
                counters["sourceWithBothModesVerifiedOnSamePeer"] += 1
            counters["verifiedReceiverOptions"] += len(forward)
        else:
            unresolved.append({
                "sourceRegionId": source_region,
                "receiverRegionId": receiver_region,
                "sourceFinalDirectedGraphId": gid,
                "sourceFinalCoordinate": point,
                "sourceValhallaProvedModes": sorted(modes),
                "nearbyReceiverAnchorCount": len(candidates),
                "reverseOrAmbiguousReceiverGraphIds": sorted(set(ambiguous)),
                "unverifiedReceiverCandidateGraphIds": sorted(set(deferred + ambiguous)),
                "receiverCandidateCensusComplete": False,
                "status": "NO_VALHALLA_VERIFIED_FORWARD_RECEIVING_ROAD",
                "mustNotCreateConnection": True,
            })
            counters["sourceUnresolved"] += 1
        if counters["sourceFinalEdgesConsidered"] % 50 == 0:
            print(source_region, "processed", counters["sourceFinalEdgesConsidered"],
                  "accepted", counters["sourceWithAnyValhallaVerifiedForwardPeer"],
                  "unresolved", counters["sourceUnresolved"], flush=True)
    return connections, unresolved, dict(counters)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("pair","source-direct","source-beyond","from-scan","to-scan",
                 "scan-summary","from-config","to-config","native-endpoints",
                 "native-route","from-graph","to-graph","output"):
        p.add_argument("--"+name,type=Path,required=True)
    for name in ("native-endpoints","native-route"):
        p.add_argument("--expected-"+name+"-sha256",required=True)
    args = p.parse_args()
    if args.output.exists() or args.output.is_symlink():
        raise ValueError("Refuse to overwrite original directed connection inventory")
    files = {name:getattr(args,name.replace("-","_"))
             for name in ("pair","source-direct","source-beyond","from-scan","to-scan",
                          "scan-summary","native-endpoints","native-route",
                          "from-graph","to-graph")}
    before = {name:fingerprint(path) for name,path in files.items()}
    for name in ("native-endpoints","native-route"):
        if before[name] != getattr(args,"expected_"+name.replace("-","_")+"_sha256"):
            raise ValueError("Original Valhalla binary SHA pin mismatch: "+name)
    pair = json.loads(args.pair.read_text())
    pair_identity(pair)
    if (before["from-graph"] != pair["fromGraphFingerprint"]
            or before["to-graph"] != pair["toGraphFingerprint"]):
        raise ValueError("Immutable original graph archives SHA mismatch")
    for bin_name in ("native-endpoints","native-route"):
        result=subprocess.run([str(files[bin_name]),"--version"],
                              capture_output=True,text=True,check=True,timeout=10)
        if result.stdout.strip() != "3.6.3":
            raise ValueError("Requires actual Valhalla 3.6.3 original executable")
    d=json.loads(args.source_direct.read_text())
    b=json.loads(args.source_beyond.read_text())
    ids=source_candidates(d,b,pair)
    from_scan=json.loads(args.from_scan.read_text())
    to_scan=json.loads(args.to_scan.read_text())
    summary=json.loads(args.scan_summary.read_text())
    source_scans(pair,from_scan=from_scan,to_scan=to_scan,scan_summary=summary)
    with tempfile.TemporaryDirectory(prefix="f8-final-directed-") as work:
        tmp=Path(work)
        from_edge=native_lines(args.native_endpoints,args.from_config,
                               set(ids["from-to"]),tmp)
        to_edge=native_lines(args.native_endpoints,args.to_config,
                             set(ids["to-from"]),tmp)
        native_receiver_candidates={}
        for side,scan,source in (
            ("from-to",to_scan,from_edge),
            ("to-from",from_scan,to_edge),
        ):
            index=receiver_anchor_index(scan)
            native_receiver_candidates[side]=set().union(*(
                nearby_receiver_ids(index,tuple(
                    edge["directedGeometry"][-1])) for edge in source.values()))
        from_receiver=native_lines(args.native_endpoints,args.to_config,
                                   native_receiver_candidates["from-to"],tmp)
        to_receiver=native_lines(args.native_endpoints,args.from_config,
                                 native_receiver_candidates["to-from"],tmp)
        connections=[];unresolved=[];stats={}
        for side,records,neighbors,scan,mode_map,config,region_name,peer_name,fprint in (
            ("from-to",from_edge,from_receiver,to_scan,ids["from-to"],
             args.to_config,pair["fromRegionId"],pair["toRegionId"],
             pair["toGraphFingerprint"]),
            ("to-from",to_edge,to_receiver,from_scan,ids["to-from"],
             args.from_config,pair["toRegionId"],pair["fromRegionId"],
             pair["fromGraphFingerprint"]),
        ):
            ok,not_ok,count=pair_connections(
                records,neighbors,scan,mode_map,config,args.native_route,
                peer_name,region_name,fprint)
            connections.extend(ok);unresolved.extend(not_ok);stats[side]=count
    # Important: same GraphId values in DIFFERENT graphs are never compared.
    identities=[(c["sourceRegionId"],c["sourceFinalDirectedGraphId"]) for c in connections]
    if len(set(identities))!=len(identities):
        raise ValueError("Source physical road/direction final ID repeated in output")
    for name,path in files.items():
        if fingerprint(path)!=before[name]:
            raise ValueError("Original F8 input changed during connection build: "+name)
    result={
        "schema":SCHEMA,"version":VERSION,
        "pairId":pair["pairId"],
        "graphFingerprints":{
            "from":pair["fromGraphFingerprint"],"to":pair["toGraphFingerprint"]},
        "originalImmutableInputSHA256":before,
        "oneRecordPerSourceFinalDirectedGraphId":True,
        "noDistinctSourceOrReceiverBranchSuppressed":True,
        "sourceFinalCandidateScope":"PR121_122_PREVIOUS_300_VALHALLA_LAST_EDGE_WITNESSES",
        "sourceDiscoveryComplete":False,
        "connectionVerification":"ORIGINAL_A_FINAL_TRIPLEG_PLUS_DIRECTED_PHYSICAL_B_GEOMETRY_PLUS_ORIGINAL_B_FIRST_TRIPLEG",
        "counts":stats,
        "connections":connections,
        "unresolvedSourceFinalEdges":unresolved,
        "receivingGraphOriginalDirectedRouteProof":True,
        "realCrossGraphJourneyTests":"SEPARATE_GATE",
        "androidConsumption":"NOT_YET_TESTED",
        "productionPublication":"BLOCKED",
    }
    args.output.parent.mkdir(parents=True,exist_ok=True)
    stage=None
    try:
        with tempfile.NamedTemporaryFile("w",delete=False,dir=args.output.parent,
                                         prefix=".f8-final-directed-",encoding="utf8") as f:
            stage=Path(f.name)
            json.dump(result,f,indent=2,allow_nan=False)
            f.write("\n")
        if args.output.exists() or args.output.is_symlink():
            raise ValueError("Concurrent F8 final edge inventory file")
        os.link(stage,args.output)
    finally:
        if stage:stage.unlink(missing_ok=True)
    for side,count in stats.items():
        print("FINAL_EDGE_MATCH",side,count,flush=True)
    return 0


if __name__=="__main__":
    try:
        raise SystemExit(main())
    except (OSError,ValueError,TypeError,KeyError,IndexError,
            subprocess.CalledProcessError,subprocess.TimeoutExpired) as exc:
        raise SystemExit("F8_FINAL_CONNECTION_ERROR: "+str(exc)[:400])
