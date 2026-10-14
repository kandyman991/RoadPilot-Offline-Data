#!/usr/bin/env python3
"""On-demand, read-only, F8-derived multi-region Valhalla route inspection.

Only CURRENT independently-built graph identities and VALIDATED handoffs are used.
The hierarchical connector composer proposes multiple candidates; detailed local
Valhalla legs and final destination arrival decide what actually works. Partial
routes are never presented as completed journeys. Graph geometries remain separate
at handoffs so the UI cannot hide differences between correlated anchor coordinates.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from shapely.geometry import Point, shape
from build_frontier_road_inventory import load_polygon
from refresh_graph_connectivity import Graph, discover_pairs, is_current_runtime, latest_graphs, sha256_file

MODES = {"motorcycle": "MOTORCYCLE", "auto": "CAR"}
STYLES = ("FASTER", "SHORTER")
ENDPOINT_LIMIT_M = 150.0
MAX_HOPS = 6
MAX_CHAINS = 20
MAX_LEGS = 64
TIME_BUDGET = 120.0


def fail(reason: str) -> None:
    raise ValueError(reason)


def read_json(path: Path) -> dict:
    result = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        fail(f"Invalid artifact {path.name}")
    return result


def distance(a: dict, b: dict) -> float:
    lat1, lng1, lat2, lng2 = map(float, (a["lat"], a["lng"], b["lat"], b["lng"]))
    x = math.radians(lat2-lat1)
    y = math.radians(lng2-lng1)
    z = math.sin(x/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(y/2)**2
    return 2*6371008.8*math.atan2(math.sqrt(z), math.sqrt(max(0, 1-z)))


def valid_position(pos: dict) -> dict:
    lat, lng = float(pos["lat"]), float(pos["lng"])
    if not all(map(math.isfinite,(lat,lng))) or not (-90 <= lat <= 90 and -180 <= lng <= 180):
        fail("Invalid route coordinate")
    return {"lat":lat, "lng":lng}


def decode_polyline6(encoded: str) -> list[list[float]]:
    points = []
    i, lat, lng = 0, 0, 0
    while i < len(encoded):
        values=[]
        for _ in range(2):
            value, shift = 0, 0
            while True:
                if i >= len(encoded): fail("Truncated Valhalla route geometry")
                c=ord(encoded[i])-63
                i+=1
                if c < 0 or c > 63 or shift > 35: fail("Invalid polyline encoding")
                value |= (c & 31) << shift
                shift += 5
                if c < 32: break
            values.append((value >> 1) ^ -(value & 1))
        lat+=values[0]; lng+=values[1]
        point=[lng/1_000_000,lat/1_000_000]
        if not all(map(math.isfinite,point)) or abs(point[0])>180 or abs(point[1])>90:
            fail("Decoded geometry contains out-of-bounds coordinates")
        points.append(point)
    if len(points)<2: fail("Valhalla route geometry too short")
    return points


def regions_containing(work: Path, graphs: dict[str,Graph], point: dict) -> list[str]:
    p=Point(point["lng"],point["lat"])
    matches=[]
    for name in sorted(graphs):
        nominal=work/"cache"/f"{name}.poly"
        buffer=work/name/"build"/"buffer.geojson"
        if not nominal.is_file() or not buffer.is_file():
            continue
        try:
            if load_polygon(nominal).covers(p):
                matches.append((0,name))
            elif shape(read_json(buffer)["geometry"]).covers(p):
                matches.append((1,name))
        except (OSError, KeyError, ValueError, TypeError):
            continue
    return [name for _,name in sorted(matches)][:6]


def trusted_graphs(dist:Path, work:Path) -> dict[str,Graph]:
    graphs=latest_graphs(dist)
    # A Valhalla working config might point at older graphs than latest manifest.
    # Require the exact retained, SHA-matching working extract for every routed graph.
    trusted={}
    for name,g in graphs.items():
        config=work/name/"build"/"valhalla.json"
        tile=work/name/"build"/"tiles.tar"
        if not config.is_file() or not tile.is_file():
            continue
        try:
            value=read_json(config)
            configured=Path(value["mjolnir"]["tile_extract"]).resolve()
            if configured != tile.resolve() or sha256_file(tile)!=g.fingerprint:
                continue
        except (KeyError, OSError, ValueError, TypeError):
            continue
        trusted[name]=g
    return trusted


def local_assets(graphs:dict[str,Graph], connectivity:Path, matrices:Path):
    pairs=[]; affected=set()
    for a,b in discover_pairs(graphs):
        path=connectivity/f"{a.region}__{b.region}"/"runtime.json"
        if is_current_runtime(path,a,b):
            pairs.append(path);affected.update((a.region,b.region))
    inventories=[]; matrix_files=[]; lookup={}
    for region in sorted(affected):
        inv=matrices/region/"inventory.json"
        if not inv.is_file(): continue
        value=read_json(inv)
        if value.get("schema")!="roadpilot.region-connector-inventory" or (value.get("graph") or {}).get("graphFingerprint")!=graphs[region].fingerprint:
            continue
        valid_sources=True
        for source in value.get("sourceConnectivity",[]):
            linked=connectivity/str(source.get("pairId"))/"runtime.json"
            if linked not in pairs or sha256_file(linked)!=source.get("sha256"):
                valid_sources=False
                break
            neighbor=source.get("neighborPrimaryGeofabrikId")
            if source.get("regionBoundaryFingerprint")!=graphs[region].boundaries.get(neighbor):
                valid_sources=False
                break
        if not valid_sources:continue
        inventories.append(inv)
        lookup[region]={a["id"]:a for a in value.get("anchors",[]) if isinstance(a,dict) and "id" in a}
        matrix=matrices/region/"matrix.json"
        if matrix.is_file():
            data=read_json(matrix)
            if data.get("sourceInventorySha256")==sha256_file(inv) and (data.get("graph") or {}).get("graphFingerprint")==graphs[region].fingerprint:
                matrix_files.append(matrix)
    # Composer validates graph identities and exact per-inventory matrix binds.
    return pairs,inventories,matrix_files,lookup


def proposed_chains(tools:Path, root:Path, paths:list[Path], inventories:list[Path], matrices:list[Path],
                    start_region:str,end_region:str,mode:str,style:str) -> list[dict]:
    with tempfile.TemporaryDirectory(prefix="roadpilot-route-chain-") as temp:
        output=Path(temp)/"chains.json"
        args=[sys.executable,str(tools/"compose_hierarchical_connectivity.py")]
        for flag,items in (("--artifact",paths),("--inventory",inventories),("--matrix",matrices)):
            for path in items: args.extend([flag,str(path)])
        args.extend(["--from-region",start_region,"--to-region",end_region,"--mode",mode,
                     "--route-style",style,"--max-hops",str(MAX_HOPS),
                     "--max-candidates",str(MAX_CHAINS),"--output",str(output)])
        proc=subprocess.run(args,text=True,capture_output=True,timeout=20,check=False)
        if proc.returncode: fail("Connector composer rejected unavailable/stale graph data: "+proc.stderr[-450:])
        data=read_json(output)
        return data.get("chains",[])


def parse_service_json(stdout: str) -> dict:
    # The pyvalhalla launcher may put INFO text beside its JSON response.
    for line in reversed(stdout.splitlines()):
        try:
            value=json.loads(line)
            if isinstance(value,dict):return value
        except json.JSONDecodeError:
            pass
    fail("Valhalla did not return structured route JSON")


def traced_endpoint_ids(service:Path,config:Path,polyline:str,costing:str,timeout:float) -> tuple[int,int]:
    request={"encoded_polyline":polyline,"costing":costing,"shape_match":"edge_walk",
             "filters":{"attributes":["edge.id","edge.way_id"],"action":"include"}}
    try:
        cmd=subprocess.run([str(service),str(config),"trace_attributes",
                            json.dumps(request,separators=(",",":"))],
                           text=True,capture_output=True,timeout=timeout,check=False)
        if cmd.returncode:fail("Valhalla could not trace detailed route edges")
        payload=parse_service_json(cmd.stdout)
        edges=payload.get("edges")
        if not isinstance(edges,list) or not edges:fail("Valhalla trace returned no edges")
        ids=[]
        for edge in edges:
            if not isinstance(edge,dict):continue
            raw=edge.get("id")
            if isinstance(raw,(str,int)) and not isinstance(raw,bool):
                try:
                    graph_id=int(raw)
                except ValueError:
                    continue
                if graph_id>0:ids.append(graph_id)
        if not ids:fail("Valhalla trace did not contain directed graph IDs")
        return ids[0],ids[-1]
    except (subprocess.TimeoutExpired,OSError,ValueError,TypeError) as exc:
        raise ValueError(f"Exact directed-edge tracing failed: {exc}") from exc


def leg_route(service:Path, config:Path, src:dict, dst:dict, costing:str,
              options:dict, timeout:float=18.0,
              start_graph_id:int|None=None,end_graph_id:int|None=None) -> dict:
    request={"locations":[{"lat":src["lat"],"lon":src["lng"]},{"lat":dst["lat"],"lon":dst["lng"]}],
             "costing":costing,"directions_options":{"units":"kilometers"}}
    if options:request["costing_options"]={costing:options}
    try:
        cmd=subprocess.run([str(service),str(config),"route",json.dumps(request,separators=(",",":"))],
                           text=True,capture_output=True,timeout=timeout,check=False)
        if cmd.returncode:fail("Valhalla route process failed")
        result=parse_service_json(cmd.stdout)
        trip=result.get("trip")
        if not isinstance(trip,dict) or trip.get("status")!=0:fail("Valhalla reports no routed leg")
        shape_points=[]
        for leg in trip.get("legs",[]):
            points=decode_polyline6(leg["shape"])
            shape_points.extend(points if not shape_points else points[1:])
        if len(shape_points)<2:fail("No decoded route geometry")
        first={"lat":shape_points[0][1],"lng":shape_points[0][0]}
        last={"lat":shape_points[-1][1],"lng":shape_points[-1][0]}
        from_offset=distance(src,first);to_offset=distance(dst,last)
        if from_offset>ENDPOINT_LIMIT_M or to_offset>ENDPOINT_LIMIT_M:
            fail(f"Leg did not reach exact endpoint: start={from_offset:.1f}m end={to_offset:.1f}m")
        # A GPS-near handoff is not a proven handoff. Require the actual
        # detailed Valhalla route to retain the exact prevalidated
        # graph-local DirectedEdge at every crossing anchor.
        if start_graph_id is not None or end_graph_id is not None:
            traced_start,traced_end=traced_endpoint_ids(
                service,config,trip["legs"][0]["shape"],costing,timeout)
            if start_graph_id is not None and traced_start!=start_graph_id:
                fail(f"Detailed route START edge {traced_start} differs from validated anchor {start_graph_id}")
            if end_graph_id is not None and traced_end!=end_graph_id:
                fail(f"Detailed route END edge {traced_end} differs from validated anchor {end_graph_id}")
        summary=trip.get("summary") or {}
        length=float(summary["length"]);secs=float(summary["time"])
        if not all(map(math.isfinite,(length,secs))) or length<0 or secs<0:fail("Invalid route metrics")
        return {"geometry":shape_points,"distanceKm":length,"durationSeconds":secs,
                "actualStart":first,"actualEnd":last,
                "startOffsetMeters":from_offset,"endOffsetMeters":to_offset}
    except (subprocess.TimeoutExpired, OSError, ValueError, KeyError, TypeError) as e:
        raise ValueError(str(e)) from e


def anchor_point(lookup:dict,region:str,anchor_id:str) -> dict:
    anchor=lookup[region][anchor_id]["graphAnchor"]["coordinate"]
    return valid_position(anchor)


def anchor_graph_id(lookup:dict,region:str,anchor_id:str) -> int:
    graph_id=lookup[region][anchor_id]["graphAnchor"]["graphId"]
    if isinstance(graph_id,bool) or not isinstance(graph_id,int) or graph_id<=0:
        fail("Invalid fingerprint-bound DirectedEdge anchor")
    return graph_id


def chain_legs(chain:dict, lookup:dict, start:dict, end:dict) -> list[dict]:
    regions=chain["regions"]
    crossings=chain["crossings"]
    if len(regions)!=len(crossings)+1 or len(crossings)<1:fail("Malformed hierarchical chain")
    legs=[]
    for i,region in enumerate(regions):
        src=start if i==0 else anchor_point(lookup,region,crossings[i-1]["toEntryAnchorId"])
        dst=end if i==len(regions)-1 else anchor_point(lookup,region,crossings[i]["fromExitAnchorId"])
        start_id=None if i==0 else anchor_graph_id(
            lookup,region,crossings[i-1]["toEntryAnchorId"])
        end_id=None if i==len(regions)-1 else anchor_graph_id(
            lookup,region,crossings[i]["fromExitAnchorId"])
        legs.append({"regionId":region,"start":src,"end":dst,
                     "startGraphId":start_id,"endGraphId":end_id})
    return legs


def evaluate_chain(chain:dict, lookup:dict, start:dict,end:dict,graphs:dict,
                   work:Path,service:Path,costing:str,options:dict,deadline:float,
                   cache:dict) -> dict:
    requested=chain_legs(chain,lookup,start,end)
    results=[]
    for leg in requested:
        if time.monotonic()>=deadline:fail("Multi-region routing time budget exhausted")
        region=leg["regionId"]
        key=(region,leg["start"]["lat"],leg["start"]["lng"],
             leg["end"]["lat"],leg["end"]["lng"],costing,json.dumps(options,sort_keys=True),
             leg["startGraphId"],leg["endGraphId"])
        if key not in cache:
            if len(cache)>=MAX_LEGS:fail("Maximum detailed Valhalla leg probes exhausted")
            config=work/region/"build"/"valhalla.json"
            cache[key]=leg_route(service,config,leg["start"],leg["end"],costing,options,
                                 timeout=min(18.0,max(1,deadline-time.monotonic())),
                                 start_graph_id=leg["startGraphId"],
                                 end_graph_id=leg["endGraphId"])
        results.append({**leg,**cache[key]})
    gaps=[]
    for i in range(len(results)-1):
        gaps.append({
            "candidateId":chain["crossings"][i]["candidateId"],
            "fromRegionId":results[i]["regionId"],
            "toRegionId":results[i+1]["regionId"],
            "gapMeters":distance(results[i]["actualEnd"],results[i+1]["actualStart"]),
            "fromEnd":results[i]["actualEnd"],"toStart":results[i+1]["actualStart"],
        })
    final_offset=distance(end,results[-1]["actualEnd"])
    if final_offset>ENDPOINT_LIMIT_M:fail(f"Destination missed by {final_offset:.1f}m")
    return {
        "status":"ROUTE_SELECTED",
        "regions":chain["regions"],
        "chainId":chain["id"],
        "crossings":chain["crossings"],
        "geometry":{"type":"MultiLineString","coordinates":[r["geometry"] for r in results]},
        "legs":results,
        "handoffs":gaps,
        "distanceKm":sum(x["distanceKm"] for x in results),
        "durationSeconds":sum(x["durationSeconds"] for x in results),
        "destinationReached":True,
        "endOffsetMeters":final_offset,
        "graphFingerprints":{r:graphs[r].fingerprint for r in chain["regions"]},
    }


def select_best(results:list[dict],style:str)->dict:
    if not results:fail("No complete cross-region route was found")
    return min(results,key=lambda r:(r["durationSeconds"],r["distanceKm"],len(r["legs"]),r["chainId"])
               if style=="FASTER" else (r["distanceKm"],r["durationSeconds"],len(r["legs"]),r["chainId"]))


def plan(dist:Path,work:Path,connectivity:Path,matrices:Path,tools:Path,service:Path,
         start:dict,end:dict,costing:str,style:str,options:dict) -> dict:
    start=valid_position(start);end=valid_position(end)
    if costing not in MODES or style not in STYLES:fail("Unsupported mode/style")
    graphs=trusted_graphs(dist,work)
    sources=regions_containing(work,graphs,start)
    destinations=regions_containing(work,graphs,end)
    if not sources or not destinations:
        return {"status":"NO_GRAPH_COVERAGE","reason":"Origin or destination is outside installed graph coverage",
                "startRegions":sources,"endRegions":destinations}
    # If both points are inside an identical installed graph, let Valhalla
    # prove a normal complete route first. For an incomplete buffered route
    # (e.g. Trento -> Innsbruck), continue to verified cross-graph chains.
    direct_rejections=[]
    for common in (r for r in sources if r in destinations):
        try:
            route=leg_route(service,work/common/"build"/"valhalla.json",
                            start,end,costing,options)
            return {
                "status":"ROUTE_SELECTED","regions":[common],
                "chainId":"direct-"+common,
                "crossings":[],"handoffs":[],
                "geometry":{"type":"MultiLineString","coordinates":[route["geometry"]]},
                "legs":[{"regionId":common,"start":start,"end":end,**route}],
                "distanceKm":route["distanceKm"],
                "durationSeconds":route["durationSeconds"],
                "destinationReached":True,"endOffsetMeters":route["endOffsetMeters"],
                "graphFingerprints":{common:graphs[common].fingerprint},
                "startRegions":sources,"endRegions":destinations,
                "chainsAttempted":0,"legsProbed":1,"successfulChains":1,
                "routeStyle":style,"costing":costing
            }
        except (ValueError,KeyError,TypeError) as e:
            direct_rejections.append(str(e)[:180])
    runtime,inventory,matrix,anchors=local_assets(graphs,connectivity,matrices)
    if not runtime:
        return {"status":"NO_CURRENT_CONNECTIVITY","reason":"No current Valhalla-validated intergraph handoffs",
                "startRegions":sources,"endRegions":destinations}
    deadline=time.monotonic()+TIME_BUDGET
    candidates=[]; cache={};attempted=0;rejections=direct_rejections[:]
    for origin in sources:
        for dest in destinations:
            if origin==dest:continue
            if origin not in anchors or dest not in anchors:continue
            try:
                chains=proposed_chains(tools,work,runtime,inventory,matrix,origin,dest,MODES[costing],style)
            except (ValueError,subprocess.TimeoutExpired) as e:
                rejections.append(str(e)[:300]);continue
            for chain in chains[:MAX_CHAINS]:
                if time.monotonic()>=deadline or len(cache)>=MAX_LEGS:break
                attempted+=1
                try:
                    candidates.append(evaluate_chain(
                        chain,anchors,start,end,graphs,work,service,costing,options,deadline,cache))
                except (ValueError,KeyError,TypeError) as e:
                    if len(rejections)<15:rejections.append(str(e)[:240])
    if not candidates:
        return {"status":"NO_COMPLETE_ROUTE","reason":"Validated handoffs exist but no full Valhalla journey reached the destination",
                "startRegions":sources,"endRegions":destinations,"chainsAttempted":attempted,
                "legsProbed":len(cache),"rejections":rejections[:8]}
    best=select_best(candidates,style)
    best.update({"startRegions":sources,"endRegions":destinations,
                 "chainsAttempted":attempted,"legsProbed":len(cache),
                 "successfulChains":len(candidates),"routeStyle":style,"costing":costing,
                 "elapsedBudgetSeconds":TIME_BUDGET-(deadline-time.monotonic())})
    return best


def main() -> int:
    p=argparse.ArgumentParser()
    for flag in ("dist-dir","work-dir","connectivity-dir","connector-matrix-dir","valhalla-service"):
        p.add_argument("--"+flag,required=True,type=Path)
    for flag in ("start-lat","start-lng","end-lat","end-lng"):
        p.add_argument("--"+flag,required=True,type=float)
    p.add_argument("--costing",choices=MODES,required=True)
    p.add_argument("--route-style",choices=STYLES,default="FASTER")
    p.add_argument("--costing-options",default="{}")
    args=p.parse_args()
    options=json.loads(args.costing_options)
    if not isinstance(options,dict) or set(options)-{"use_highways","use_tolls","use_ferry"}:
        fail("Invalid costing options")
    for key,value in options.items():
        if not isinstance(value,(int,float)) or isinstance(value,bool) or not math.isfinite(value) or not 0<=value<=1:
            fail("Invalid costing option "+key)
    result=plan(args.dist_dir,args.work_dir,args.connectivity_dir,
                args.connector_matrix_dir,Path(__file__).resolve().parent,args.valhalla_service,
                {"lat":args.start_lat,"lng":args.start_lng},
                {"lat":args.end_lat,"lng":args.end_lng},args.costing,args.route_style,options)
    print(json.dumps(result,separators=(",",":"),allow_nan=False))
    return 0


if __name__=="__main__":
    try:
        raise SystemExit(main())
    except (ValueError,OSError,KeyError,TypeError,subprocess.TimeoutExpired) as exc:
        print(json.dumps({"status":"ERROR","reason":str(exc)[:800]}))
        raise SystemExit(1)
