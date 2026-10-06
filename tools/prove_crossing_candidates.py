#!/usr/bin/env python3
"""Prove unproven crossing candidates with local plain-Valhalla route legs.

For a normal crossing:
  FROM_TO = Graph A interior -> A snap, then Graph B snap -> B interior.
  TO_FROM = Graph B interior -> B snap, then Graph A snap -> A interior.

For a road that follows the frontier, the stable OSM snippet endpoints are used as
longitudinal probes and both travel directions are still proven independently.

No heading/access metadata is used as a pre-proof rejection criterion.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from shapely.geometry import LineString, MultiLineString, Point, shape
from shapely.ops import transform

from build_frontier_road_inventory import load_polygon, local_projection
from correlate_frontier_roads import graph_manifest_info, haversine_meters

SCHEMA = "roadpilot.crossing-proofs"
VERSION = 1
GENERATOR_NAME = "roadpilot-local-valhalla-crossing-proof"
GENERATOR_VERSION = "1"


def fail(message: str) -> None:
    raise SystemExit(message)


def load_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"Could not read {label} {path}: {exc}")
    if not isinstance(value, dict):
        fail(f"{label} must be a JSON object")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def coordinate(value: Any, label: str) -> dict[str, float]:
    if not isinstance(value, dict):
        fail(f"{label} must be an object")
    try:
        lat = float(value["lat"])
        lng = float(value["lng"])
    except (KeyError, TypeError, ValueError):
        fail(f"{label} must contain numeric lat/lng")
    if not math.isfinite(lat) or not math.isfinite(lng) or not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
        fail(f"{label} has invalid lat/lng")
    return {"lat": lat, "lng": lng}


def line_parts(geometry) -> list[LineString]:
    if isinstance(geometry, LineString):
        return [geometry] if geometry.length > 0 else []
    if isinstance(geometry, MultiLineString):
        return [part for part in geometry.geoms if part.length > 0]
    if hasattr(geometry, "geoms"):
        result = []
        for item in geometry.geoms:
            result.extend(line_parts(item))
        return result
    return []


def farthest_region_probe(line: LineString, region, frontier: Point) -> Point:
    pieces = line_parts(line.intersection(region))
    candidates: list[Point] = []
    for piece in pieces:
        coords = list(piece.coords)
        if len(coords) >= 2:
            candidates.append(Point(coords[0]))
            candidates.append(Point(coords[-1]))
    if not candidates:
        fail("OSM frontier snippet has no line geometry inside a nominal region")
    return max(candidates, key=lambda point: point.distance(frontier))


def wgs_point(point: Point, backward) -> dict[str, float]:
    result = transform(backward, point)
    return {"lat": float(result.y), "lng": float(result.x)}


def derive_probes(
    road: dict[str, Any],
    from_polygon,
    to_polygon,
    forward,
    backward,
) -> dict[str, Any]:
    snippet = road.get("snippet")
    if not isinstance(snippet, dict) or snippet.get("type") != "LineString":
        fail(f"{road.get('id', '?')}: stable frontier road is missing LineString snippet")
    line_wgs = shape(snippet)
    if not isinstance(line_wgs, LineString) or line_wgs.length <= 0:
        fail(f"{road.get('id', '?')}: stable frontier snippet is invalid")
    frontier_wgs = coordinate(road.get("crossingCoordinate"), "frontier crossingCoordinate")

    line = transform(forward, line_wgs)
    frontier = transform(forward, Point(frontier_wgs["lng"], frontier_wgs["lat"]))
    from_region = transform(forward, from_polygon)
    to_region = transform(forward, to_polygon)

    kind = road.get("crossingKind")
    if kind == "CROSSING":
        from_point = farthest_region_probe(line, from_region, frontier)
        to_point = farthest_region_probe(line, to_region, frontier)
        strategy = "REGION_INTERIOR"
    elif kind == "FRONTIER_OVERLAP":
        coords = list(line.coords)
        if len(coords) < 2:
            fail(f"{road.get('id', '?')}: frontier-overlap snippet is degenerate")
        from_point = Point(coords[0])
        to_point = Point(coords[-1])
        strategy = "FRONTIER_LONGITUDINAL"
    else:
        fail(f"{road.get('id', '?')}: unsupported crossingKind {kind}")

    from_probe = wgs_point(from_point, backward)
    to_probe = wgs_point(to_point, backward)
    from_distance = haversine_meters(
        frontier_wgs["lat"], frontier_wgs["lng"], from_probe["lat"], from_probe["lng"]
    )
    to_distance = haversine_meters(
        frontier_wgs["lat"], frontier_wgs["lng"], to_probe["lat"], to_probe["lng"]
    )
    if from_distance < 1.0 or to_distance < 1.0:
        fail(f"{road.get('id', '?')}: proof probe is less than 1 m from the frontier anchor")

    return {
        "strategy": strategy,
        "fromProbe": from_probe,
        "toProbe": to_probe,
        "fromProbeDistanceMeters": from_distance,
        "toProbeDistanceMeters": to_distance,
    }


def trace_route_endpoint(
    config: Path,
    encoded_polyline: str,
    costing: str,
    endpoint_edge_position: str,
) -> tuple[int | None, str | None]:
    request = json.dumps(
        {
            "encoded_polyline": encoded_polyline,
            "costing": costing,
            "shape_match": "edge_walk",
            "filters": {
                "attributes": ["edge.id", "edge.way_id"],
                "action": "include",
            },
        },
        separators=(",", ":"),
    )
    try:
        result = subprocess.run(
            ["valhalla_service", str(config), "trace_attributes", request],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as exc:
        return None, f"Could not execute Valhalla trace_attributes: {exc}"

    if result.returncode != 0:
        return None, (
            result.stderr.strip()
            or result.stdout.strip()
            or "Valhalla trace_attributes failed"
        )

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return None, f"Valhalla trace_attributes returned invalid JSON: {exc}"
    if not isinstance(payload, dict):
        return None, "Valhalla trace_attributes response must be an object"
    edges = payload.get("edges")
    if not isinstance(edges, list) or not edges:
        return None, "Valhalla trace_attributes returned no route edges"

    graph_ids: list[int] = []
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        edge_id = edge.get("id")
        if isinstance(edge_id, int) and not isinstance(edge_id, bool) and edge_id > 0:
            graph_ids.append(edge_id)
        elif isinstance(edge_id, str):
            try:
                parsed = int(edge_id)
            except ValueError:
                continue
            if parsed > 0:
                graph_ids.append(parsed)
    if not graph_ids:
        return None, "Valhalla trace_attributes returned no valid edge.id values"

    if endpoint_edge_position == "START":
        return graph_ids[0], None
    if endpoint_edge_position == "END":
        return graph_ids[-1], None
    return None, f"Unsupported endpoint edge position: {endpoint_edge_position}"


def leg_result(
    config: Path,
    region_id: str,
    start: dict[str, float],
    end: dict[str, float],
    costing: str,
    expected_graph_id: int | None,
    endpoint_edge_position: str,
) -> dict[str, Any]:
    direct = haversine_meters(start["lat"], start["lng"], end["lat"], end["lng"])
    base = {
        "regionId": region_id,
        "start": start,
        "end": end,
        "directDistanceMeters": direct,
        "expectedGraphId": expected_graph_id,
        "endpointEdgePosition": endpoint_edge_position,
        "actualEndpointGraphId": None,
        "edgeMatched": False,
    }
    if expected_graph_id is None or expected_graph_id <= 0:
        return {
            "status": "ERROR",
            **base,
            "elapsedMs": 0,
            "routeLengthKm": None,
            "routeTimeSeconds": None,
            "error": "Candidate has no exact graphId to prove.",
        }

    request = json.dumps(
        {
            "locations": [
                {"lat": start["lat"], "lon": start["lng"]},
                {"lat": end["lat"], "lon": end["lng"]},
            ],
            "costing": costing,
            "units": "kilometers",
            "directions_options": {"units": "kilometers"},
        },
        separators=(",", ":"),
    )
    started = time.perf_counter_ns()
    try:
        result = subprocess.run(
            ["valhalla_service", str(config), "route", request],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as exc:
        elapsed = (time.perf_counter_ns() - started) // 1_000_000
        return {
            "status": "ERROR",
            **base,
            "elapsedMs": elapsed,
            "routeLengthKm": None,
            "routeTimeSeconds": None,
            "error": f"Could not execute valhalla_service: {exc}",
        }

    elapsed = (time.perf_counter_ns() - started) // 1_000_000
    if result.returncode != 0:
        return {
            "status": "FAILED",
            **base,
            "elapsedMs": elapsed,
            "routeLengthKm": None,
            "routeTimeSeconds": None,
            "error": result.stderr.strip() or result.stdout.strip() or "Valhalla route failed",
        }

    try:
        response = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return {
            "status": "ERROR",
            **base,
            "elapsedMs": elapsed,
            "routeLengthKm": None,
            "routeTimeSeconds": None,
            "error": f"Valhalla route returned invalid JSON: {exc}",
        }
    trip = response.get("trip") if isinstance(response, dict) else None
    if not isinstance(trip, dict):
        return {
            "status": "ERROR",
            **base,
            "elapsedMs": elapsed,
            "routeLengthKm": None,
            "routeTimeSeconds": None,
            "error": "Valhalla route response has no trip object",
        }

    status = trip.get("status", 0)
    summary = trip.get("summary")
    if not isinstance(summary, dict):
        summary = {}
    length = summary.get("length")
    route_time = summary.get("time")
    length_value = float(length) if isinstance(length, (int, float)) and not isinstance(length, bool) else None
    time_value = float(route_time) if isinstance(route_time, (int, float)) and not isinstance(route_time, bool) else None

    if status != 0:
        return {
            "status": "FAILED",
            **base,
            "elapsedMs": elapsed,
            "routeLengthKm": length_value,
            "routeTimeSeconds": time_value,
            "error": str(trip.get("status_message") or f"Valhalla status {status}"),
        }

    legs = trip.get("legs")
    if not isinstance(legs, list) or len(legs) != 1 or not isinstance(legs[0], dict):
        return {
            "status": "ERROR",
            **base,
            "elapsedMs": elapsed,
            "routeLengthKm": length_value,
            "routeTimeSeconds": time_value,
            "error": "Local Valhalla proof route did not return exactly one leg.",
        }
    encoded_shape = legs[0].get("shape")
    if not isinstance(encoded_shape, str) or not encoded_shape:
        return {
            "status": "ERROR",
            **base,
            "elapsedMs": elapsed,
            "routeLengthKm": length_value,
            "routeTimeSeconds": time_value,
            "error": "Local Valhalla proof route did not return an encoded shape.",
        }

    actual_graph_id, trace_error = trace_route_endpoint(
        config, encoded_shape, costing, endpoint_edge_position
    )
    traced = {
        **base,
        "actualEndpointGraphId": actual_graph_id,
        "edgeMatched": actual_graph_id == expected_graph_id,
    }
    if trace_error is not None:
        return {
            "status": "ERROR",
            **traced,
            "elapsedMs": elapsed,
            "routeLengthKm": length_value,
            "routeTimeSeconds": time_value,
            "error": trace_error,
        }
    if actual_graph_id != expected_graph_id:
        return {
            "status": "FAILED",
            **traced,
            "elapsedMs": elapsed,
            "routeLengthKm": length_value,
            "routeTimeSeconds": time_value,
            "error": (
                f"Valhalla route used endpoint edge {actual_graph_id}, "
                f"not candidate edge {expected_graph_id}."
            ),
        }

    return {
        "status": "PASSED",
        **traced,
        "elapsedMs": elapsed,
        "routeLengthKm": length_value,
        "routeTimeSeconds": time_value,
    }


def cached_leg(
    cache: dict[tuple[Any, ...], dict[str, Any]],
    graph_label: str,
    config: Path,
    region_id: str,
    start: dict[str, float],
    end: dict[str, float],
    costing: str,
    expected_graph_id: int | None,
    endpoint_edge_position: str,
) -> dict[str, Any]:
    key = (
        graph_label,
        costing,
        round(start["lat"], 7),
        round(start["lng"], 7),
        round(end["lat"], 7),
        round(end["lng"], 7),
        expected_graph_id,
        endpoint_edge_position,
    )
    if key not in cache:
        cache[key] = leg_result(
            config,
            region_id,
            start,
            end,
            costing,
            expected_graph_id,
            endpoint_edge_position,
        )
    return dict(cache[key])


def direction_proof(
    cache: dict[tuple[Any, ...], dict[str, Any]],
    costing: str,
    direction: str,
    from_config: Path,
    to_config: Path,
    from_region: str,
    to_region: str,
    from_probe: dict[str, float],
    to_probe: dict[str, float],
    from_snap: dict[str, float],
    to_snap: dict[str, float],
    from_graph_id: int | None,
    to_graph_id: int | None,
) -> dict[str, Any]:
    if direction == "FROM_TO":
        graph_a = cached_leg(
            cache,
            "A",
            from_config,
            from_region,
            from_probe,
            from_snap,
            costing,
            from_graph_id,
            "END",
        )
        graph_b = cached_leg(
            cache,
            "B",
            to_config,
            to_region,
            to_snap,
            to_probe,
            costing,
            to_graph_id,
            "START",
        )
    else:
        graph_a = cached_leg(
            cache,
            "A",
            from_config,
            from_region,
            from_snap,
            from_probe,
            costing,
            from_graph_id,
            "START",
        )
        graph_b = cached_leg(
            cache,
            "B",
            to_config,
            to_region,
            to_probe,
            to_snap,
            costing,
            to_graph_id,
            "END",
        )
    return {
        "passed": graph_a["status"] == "PASSED" and graph_b["status"] == "PASSED",
        "graphA": graph_a,
        "graphB": graph_b,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", required=True, type=Path)
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--from-manifest", required=True, type=Path)
    parser.add_argument("--to-manifest", required=True, type=Path)
    parser.add_argument("--from-polygon", required=True, type=Path)
    parser.add_argument("--to-polygon", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    for path in (
        args.candidates,
        args.inventory,
        args.from_manifest,
        args.to_manifest,
        args.from_polygon,
        args.to_polygon,
    ):
        if not path.is_file():
            fail(f"Input does not exist: {path}")

    candidates = load_object(args.candidates, "candidate artifact")
    if candidates.get("schema") != "roadpilot.crossing-candidates" or candidates.get("version") != 1:
        fail("Unsupported crossing candidate artifact")
    if candidates.get("validationState") != "UNPROVEN":
        fail("Crossing candidate artifact must be UNPROVEN")

    inventory = load_object(args.inventory, "frontier inventory")
    if inventory.get("schema") != "roadpilot.frontier-road-inventory" or inventory.get("version") != 1:
        fail("Unsupported frontier-road inventory")
    for key in ("pairId", "fromRegionId", "toRegionId", "fromBoundaryFingerprint", "toBoundaryFingerprint"):
        if candidates.get(key) != inventory.get(key):
            fail(f"Candidate/inventory mismatch for {key}")

    source = inventory.get("source")
    if not isinstance(source, dict):
        fail("Frontier inventory has no source hashes")
    if sha256_file(args.from_polygon) != source.get("fromPolygonSha256"):
        fail("Provided from-region polygon does not match frontier inventory")
    if sha256_file(args.to_polygon) != source.get("toPolygonSha256"):
        fail("Provided to-region polygon does not match frontier inventory")

    from_region = str(candidates["fromRegionId"])
    to_region = str(candidates["toRegionId"])
    from_graph_expected = candidates.get("fromGraph")
    to_graph_expected = candidates.get("toGraph")
    if not isinstance(from_graph_expected, dict) or not isinstance(to_graph_expected, dict):
        fail("Candidate artifact is missing graph identity")

    from_manifest_preview = load_object(args.from_manifest, "from routing manifest")
    to_manifest_preview = load_object(args.to_manifest, "to routing manifest")
    from_source = from_manifest_preview.get("source")
    to_source = to_manifest_preview.get("source")
    if not isinstance(from_source, dict) or not isinstance(to_source, dict):
        fail("Routing manifests are missing source objects")
    from_primary = str(from_source.get("primaryGeofabrikId") or "")
    to_primary = str(to_source.get("primaryGeofabrikId") or "")
    if not from_primary or not to_primary:
        fail("Routing manifests are missing primary Geofabrik ids")

    from_polygon = load_polygon(args.from_polygon)
    to_polygon = load_polygon(args.to_polygon)
    forward, backward = local_projection(from_polygon, to_polygon)

    roads = inventory.get("roads")
    if not isinstance(roads, list):
        fail("frontier inventory roads must be an array")
    road_by_id = {
        str(road.get("id")): road
        for road in roads
        if isinstance(road, dict) and road.get("id")
    }

    with tempfile.TemporaryDirectory(prefix="roadpilot-proof-") as temp:
        root = Path(temp)
        from_graph, from_config = graph_manifest_info(
            args.from_manifest,
            from_region,
            to_primary,
            str(candidates["fromBoundaryFingerprint"]),
            root,
            "from",
        )
        to_graph, to_config = graph_manifest_info(
            args.to_manifest,
            to_region,
            from_primary,
            str(candidates["toBoundaryFingerprint"]),
            root,
            "to",
        )
        for label, actual, expected in (
            ("fromGraph", from_graph, from_graph_expected),
            ("toGraph", to_graph, to_graph_expected),
        ):
            for key in ("regionId", "packageVersion", "graphFingerprint", "primaryGeofabrikId"):
                if actual.get(key) != expected.get(key):
                    fail(f"{label}.{key} no longer matches the candidate artifact")

        proof_records = []
        route_cache: dict[tuple[Any, ...], dict[str, Any]] = {}
        source_candidates = candidates.get("candidates")
        if not isinstance(source_candidates, list):
            fail("candidate artifact candidates must be an array")

        for index, candidate in enumerate(source_candidates):
            if not isinstance(candidate, dict):
                fail(f"candidate[{index}] must be an object")
            frontier_id = str(candidate.get("frontierRoadId") or "")
            road = road_by_id.get(frontier_id)
            if road is None:
                fail(f"candidate[{index}] references missing frontier road {frontier_id}")
            probe = derive_probes(road, from_polygon, to_polygon, forward, backward)
            from_edge = candidate.get("fromEdge")
            to_edge = candidate.get("toEdge")
            if not isinstance(from_edge, dict) or not isinstance(to_edge, dict):
                fail(f"candidate[{index}] is missing edge correlations")
            from_snap = coordinate(from_edge.get("correlatedCoordinate"), "fromEdge.correlatedCoordinate")
            to_snap = coordinate(to_edge.get("correlatedCoordinate"), "toEdge.correlatedCoordinate")
            from_graph_id = from_edge.get("graphId")
            if not isinstance(from_graph_id, int) or isinstance(from_graph_id, bool) or from_graph_id <= 0:
                from_graph_id = None
            to_graph_id = to_edge.get("graphId")
            if not isinstance(to_graph_id, int) or isinstance(to_graph_id, bool) or to_graph_id <= 0:
                to_graph_id = None

            modes: dict[str, Any] = {}
            supported: list[str] = []
            any_error = False
            for output_mode, costing in (("MOTORCYCLE", "motorcycle"), ("CAR", "auto")):
                from_to = direction_proof(
                    route_cache,
                    costing,
                    "FROM_TO",
                    from_config,
                    to_config,
                    from_region,
                    to_region,
                    probe["fromProbe"],
                    probe["toProbe"],
                    from_snap,
                    to_snap,
                    from_graph_id,
                    to_graph_id,
                )
                to_from = direction_proof(
                    route_cache,
                    costing,
                    "TO_FROM",
                    from_config,
                    to_config,
                    from_region,
                    to_region,
                    probe["fromProbe"],
                    probe["toProbe"],
                    from_snap,
                    to_snap,
                    from_graph_id,
                    to_graph_id,
                )
                modes[output_mode] = {"fromTo": from_to, "toFrom": to_from}
                if from_to["passed"]:
                    supported.append(f"{output_mode}_FROM_TO")
                if to_from["passed"]:
                    supported.append(f"{output_mode}_TO_FROM")
                any_error = any_error or any(
                    leg["status"] == "ERROR"
                    for direction in (from_to, to_from)
                    for leg in (direction["graphA"], direction["graphB"])
                )

            if supported:
                state = "PROVEN"
            elif any_error:
                state = "INCONCLUSIVE"
            else:
                state = "REJECTED"

            proof_records.append(
                {
                    "candidateId": candidate["id"],
                    "frontierRoadId": frontier_id,
                    "candidateRank": candidate["candidateRank"],
                    "stableWayId": candidate["stableWayId"],
                    "proofState": state,
                    "probeGeometry": probe,
                    "supportedDirections": supported,
                    "modes": modes,
                }
            )

    proven = sum(1 for item in proof_records if item["proofState"] == "PROVEN")
    rejected = sum(1 for item in proof_records if item["proofState"] == "REJECTED")
    inconclusive = sum(1 for item in proof_records if item["proofState"] == "INCONCLUSIVE")
    output = {
        "schema": SCHEMA,
        "version": VERSION,
        "pairId": candidates["pairId"],
        "fromRegionId": from_region,
        "toRegionId": to_region,
        "fromBoundaryFingerprint": candidates["fromBoundaryFingerprint"],
        "toBoundaryFingerprint": candidates["toBoundaryFingerprint"],
        "fromGraph": from_graph_expected,
        "toGraph": to_graph_expected,
        "generator": {"name": GENERATOR_NAME, "version": GENERATOR_VERSION},
        "sourceCandidateCount": len(proof_records),
        "provenCandidateCount": proven,
        "rejectedCandidateCount": rejected,
        "inconclusiveCandidateCount": inconclusive,
        "proofs": proof_records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(
        f"{output['pairId']}: proven={proven} rejected={rejected} "
        f"inconclusive={inconclusive} routeLegCache={len(route_cache)}"
    )
    print(f"wrote: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
