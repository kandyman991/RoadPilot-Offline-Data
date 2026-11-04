"""Read original Valhalla 3.6.3 routing TripLeg::Node::Edge GraphIds.

This only executes an original per-graph Valhalla route. It NEVER calls
trace_attributes(edge_walk), matches across graph IDs, produces crossing
candidates, declares a last retained physical-road edge, or publishes routes.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import subprocess

from probe_native_f8_journey import decode_polyline6, distance


SCHEMA = "roadpilot.f8-original-valhalla-route-edges"
VERSION = "3.6.3"


def verify_native_route_binary(binary: Path, runner=subprocess.run) -> str:
    if not binary.is_file():
        raise ValueError("Pinned original Valhalla route-edge binary unavailable")
    proc = runner([str(binary), "--version"], capture_output=True,
                  text=True, timeout=10, check=False)
    if proc.returncode or proc.stdout.strip() != VERSION:
        raise ValueError("Original route-edge binary version mismatch: requires Valhalla 3.6.3")
    import hashlib
    with binary.open("rb") as src:
        return "sha256:" + hashlib.file_digest(src, "sha256").hexdigest()


def validate_original_route(response: dict, start: dict, end: dict) -> dict:
    if (not isinstance(response, dict) or response.get("schema") != SCHEMA
            or response.get("version") != 1
            or response.get("valhallaVersion") != VERSION
            or response.get("routeCalculationCount") != 1
            or response.get("graphLocalOnly") is not True
            or response.get("edgeIdOrigin") != "ORIGINAL_TRIPLEG_NODE_EDGE_PROTOBUF"
            or response.get("legCount") != 1
            or response.get("routeEdgeIdentity") != "ORIGINAL_VALHALLA_ROUTE_PROTOBUF"
            or response.get("crossGraphLegalTransfer") != "NOT_VERIFIED"
            or response.get("physicalRoadFinalEdge") != "NOT_VERIFIED"
            or response.get("productionPublication") != "BLOCKED"):
        raise ValueError("Invalid original-route protobuf evidence identity")
    edges = response.get("directedEdges")
    if (not isinstance(edges, list) or not edges
            or type(response.get("nodeCount")) is not int
            or not len(edges) <= response["nodeCount"] <= len(edges)+2):
        raise ValueError("Native original route has missing edge-node inventory")
    ids = []
    for edge in edges:
        if (not isinstance(edge, dict)
                or type(edge.get("graphId")) is not int or edge["graphId"] <= 0
                or type(edge.get("wayId")) is not int or edge["wayId"] <= 0):
            raise ValueError("Invalid native original route directed edge ID")
        ids.append(edge["graphId"])
    if (response.get("firstDirectedGraphId") != ids[0]
            or response.get("lastDirectedGraphId") != ids[-1]):
        raise ValueError("Original route first/last directed IDs disagree")
    seconds = response.get("durationSeconds")
    km = response.get("distanceKm")
    if (type(seconds) not in (int, float) or type(km) not in (int, float)
            or any(not math.isfinite(x) or x <= 0 for x in (seconds, km))):
        raise ValueError("Original route has invalid positive Valhalla costs")
    shape = response.get("encodedShape")
    if not isinstance(shape, str):
        raise ValueError("Original route missing encoded shape")
    decoded = decode_polyline6(shape)
    if len(decoded) < 2:
        raise ValueError("Original route missing geometrically distinct endpoints")
    first = {"lat": decoded[0][1], "lng": decoded[0][0]}
    last = {"lat": decoded[-1][1], "lng": decoded[-1][0]}
    offsets = [distance(start, first), distance(end, last)]
    if any(not math.isfinite(x) for x in offsets):
        raise ValueError("Nonfinite original route snap offsets")
    return {
        "status": "SUCCEEDED",
        "startActual": first, "endActual": last,
        "startOffsetMeters": round(offsets[0], 2),
        "endOffsetMeters": round(offsets[1], 2),
        "durationSeconds": seconds, "distanceKm": km,
        "encodedShape": shape,
        "originalNativeDirectedGraphIds": ids,
        "firstDirectedGraphId": ids[0],
        "lastDirectedGraphId": ids[-1],
        "originalRouteEdgeIdentity": "ORIGINAL_VALHALLA_ROUTE_PROTOBUF",
        "edgeIdOrigin": "ORIGINAL_TRIPLEG_NODE_EDGE_PROTOBUF",
        "crossGraphLegalTransfer": "NOT_VERIFIED",
        "physicalLastRetainedRoadEdge": "NOT_VERIFIED",
    }


def route_with_original_ids(config: Path, start: dict, end: dict, mode: str,
                            binary: Path, runner=subprocess.run,
                            timeout: int = 60) -> dict:
    if mode not in ("auto", "motorcycle"):
        raise ValueError("Unsupported native route mode")
    req = {
        "locations": [
            {"lat": start["lat"], "lon": start["lng"]},
            {"lat": end["lat"], "lon": end["lng"]},
        ],
        "costing": mode,
        "units": "kilometers",
        "directions_options": {"units": "kilometers"},
    }
    call = runner([str(binary), str(config)],
                  input=json.dumps(req, separators=(",", ":")),
                  capture_output=True, text=True, timeout=timeout, check=False)
    if call.returncode:
        # The native process explicitly demands discarding partial stdout.
        return {"status": "FAILED",
                "reason": (call.stderr or "Native route failed")[-400:],
                "originalRouteEdgeIdentity": "NOT_VERIFIED"}
    try:
        return validate_original_route(json.loads(call.stdout), start, end)
    except (ValueError, KeyError, TypeError, IndexError) as error:
        return {"status": "INCONCLUSIVE",
                "reason": "Invalid original native Valhalla route: " + str(error)[:220],
                "originalRouteEdgeIdentity": "NOT_VERIFIED"}
