#!/usr/bin/env python3
"""M6c: read-only graph-local clipped-road terminal and receiving-graph probe.

A native graph-local terminal near the SHA-bound 25 km buffer boundary is not
yet a verified final *physical* road edge, cross-region turn, or route-edge ID.
Keep every returned B locate alternative, whether routeable or inconclusive.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Callable

from pyproj import Transformer
from shapely.geometry import Point, shape
import shapely

from build_native_f8_pair_evidence import pair_identity
from native_f8_inputs import graph_manifest_info
from probe_native_f8_actual_journey import verify_native_extractor
from probe_native_f8_directed_turn import native_adjacency, point_along
from probe_native_f8_journey import (
    ARRIVAL_TOLERANCE_METERS, distance, route, verify_retained_graph_identity,
)
from probe_native_f8_terminal_geometry import MODES, checked_edge, native_rows, nearest
from probe_native_f8_terminal_handoffs import strict_point

MAX_SOURCE_IDS = 8
MAX_B_LOCATE_RESULTS = 64
MAX_RADIUS_METRES = 100
BOUNDARY_OBSERVATION_METRES = 200.0
MIN_LOCAL_LEG_METRES = 10.0
ROUTE_SAMPLE_METRES = 40.0
CRS = Transformer.from_crs("EPSG:4326", "EPSG:3035", always_xy=True)


class SourceIntegrityError(ValueError):
    """Corrupt, mismatched, or unauthorised input must stop the entire batch."""


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verified_buffer(path: Path, manifest: dict) -> dict:
    """Load the *actual* buffer polygon bound into the immutable graph manifest."""
    source = manifest.get("source") if isinstance(manifest, dict) else None
    if (not isinstance(source, dict)
            or type(source.get("borderBufferKm")) not in (int, float)
            or source["borderBufferKm"] != 25.0):
        raise SourceIntegrityError("Graph does not declare approved 25 km buffer")
    reference = source.get("bufferGeoJsonSha256")
    digest = _file_sha256(path)
    if (not isinstance(reference, str)
            or reference.removeprefix("sha256:") != digest):
        raise SourceIntegrityError("Buffer GeoJSON SHA-256 mismatches graph manifest")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("type") == "FeatureCollection":
        from shapely.ops import unary_union
        features = raw.get("features", [])
        if not features:
            raise SourceIntegrityError("Empty buffer FeatureCollection")
        polygon = unary_union([shape(f["geometry"]) for f in features])
    elif raw.get("type") == "Feature":
        polygon = shape(raw["geometry"])
    else:
        polygon = shape(raw)
    if polygon.is_empty or not polygon.is_valid or polygon.geom_type not in (
            "Polygon", "MultiPolygon"):
        raise SourceIntegrityError("Invalid retained buffer polygon")
    metric = shapely.transform(polygon, CRS.transform, interleaved=False)
    return {
        "polygon": metric,
        "sha256": "sha256:" + digest,
        "bufferKm": 25.0,
        "provenance": "MATCHED_ROUTING_PACKAGE_MANIFEST",
    }


def _at(point: dict) -> Point:
    x, y = CRS.transform(point["lng"], point["lat"])
    return Point(x, y)


def check_source_terminal(edge: dict, adjacency: dict, mode: str,
                          own_buffer: dict, peer_buffer: dict) -> dict:
    """Exhaust *one* source native end node; no whole-road lineage claim."""
    if mode not in MODES:
        raise ValueError("Unsupported vehicle mode")
    source = checked_edge(edge)
    if not isinstance(adjacency, dict):
        raise SourceIntegrityError("Missing native adjacency")
    for field, expected in (
        ("sourceGraphId", source["sourceGraphId"]),
        ("endNodeGraphId", source["endNodeGraphId"]),
        ("wayId", source["wayId"]),
        ("forwardAccess", source["forwardAccess"]),
    ):
        if adjacency.get(field) != expected:
            raise SourceIntegrityError("Native adjacency identity mismatch: " + field)
    degree = adjacency.get("nativeOutgoingDegree")
    reverse = adjacency.get("opposingGraphId")
    entries = adjacency.get("outgoingDirectedEdges")
    if (type(degree) is not int or not 1 <= degree <= 256
            or type(reverse) is not int or reverse <= 0
            or not isinstance(entries, list) or len(entries) != degree):
        raise SourceIntegrityError("Truncated/invalid native source outgoing inventory")
    ids = []
    for item in entries:
        if (not isinstance(item, dict)
                or type(item.get("graphId")) is not int or item["graphId"] <= 0
                or type(item.get("forwardAccess")) is not int
                or not 0 <= item["forwardAccess"] < 2**32
                or any(type(item.get(field)) is not bool for field in (
                    "isRoad", "isShortcut", "autoBit", "motorcycleBit"))):
            raise SourceIntegrityError("Malformed source outgoing directed edge")
        if (item["autoBit"] != bool(item["forwardAccess"] & MODES["auto"])
                or item["motorcycleBit"] != bool(
                    item["forwardAccess"] & MODES["motorcycle"])):
            raise SourceIntegrityError("Native source mode bits inconsistent")
        ids.append(item["graphId"])
    if len(ids) != len(set(ids)) or ids.count(reverse) != 1:
        raise SourceIntegrityError("Duplicate outgoing IDs or missing native reverse")
    if type(source.get("deadend")) is not bool:
        raise SourceIntegrityError("Missing native source deadend flag")

    # A legal graph-native shortcut must never be excluded from the
    # mode-usable continuation inventory. It may be important even when
    # Valhalla does not classify it as an ordinary road.
    mode_usable_nonreverse = [
        item["graphId"] for item in entries
        if item["graphId"] != reverse
        and bool(item["forwardAccess"] & MODES[mode])
    ]
    mode_legal_nonreverse = [
        item["graphId"] for item in entries
        if item["graphId"] != reverse
        and item["isRoad"] and not item["isShortcut"]
        and bool(item["forwardAccess"] & MODES[mode])
    ]
    endpoint = {"lat": source["endLat"], "lng": source["endLon"]}
    at = _at(endpoint)
    own_shape = own_buffer["polygon"]
    peer_shape = peer_buffer["polygon"]
    own_dist = own_shape.boundary.distance(at)
    peer_dist = peer_shape.boundary.distance(at)
    # Distance from a buffer's *polygon outline* cannot exclude a true
    # source-graph terminal. Real A22 shows ~1 km outline discrepancy.
    # Preserve the candidate and report proximity as diagnostic evidence only.
    graph_local_terminal = (
        source.get("deadend") is True
        and bool(source["forwardAccess"] & MODES[mode])
        and not mode_usable_nonreverse
    )
    candidate = graph_local_terminal and peer_shape.covers(at)
    near_buffer_outline = own_dist <= BOUNDARY_OBSERVATION_METRES
    return {
        "sourceGraphId": source["sourceGraphId"],
        "sourceEndNodeGraphId": source["endNodeGraphId"],
        "sourceDirectedEndpoint": endpoint,
        "sourceNativeDeadend": source.get("deadend"),
        "sourceNativeForwardModeAccess": bool(
            source["forwardAccess"] & MODES[mode]),
        "allNativeOutgoingAlternatives": entries,
        "nativeOutgoingDegree": degree,
        "nativeOpposingReverseGraphId": reverse,
        "modeUsableNonreverseOutgoingGraphIds": mode_usable_nonreverse,
        "modeLegalNonreverseOutgoingRoadGraphIds": mode_legal_nonreverse,
        "shortcutAndNonroadContinuationsPreserved": True,
        "ownBufferBoundaryDistanceMeters": round(own_dist, 3),
        "peerBufferBoundaryDistanceMeters": round(peer_dist, 3),
        "sourceEndInsideOwnRetainedBuffer": own_shape.covers(at),
        "sourceEndInsidePeerRetainedBuffer": peer_shape.covers(at),
        "ownBufferSha256": own_buffer["sha256"],
        "peerBufferSha256": peer_buffer["sha256"],
        "bufferProvenance": "BOTH_SHA_BOUND_TO_RESPECTIVE_GRAPH_MANIFESTS",
        "graphLocalModeTerminalConfirmed": graph_local_terminal,
        "graphLocalClippedTerminalCandidate": candidate,
        "nearSampledOwnBufferOutline": near_buffer_outline,
        "boundaryProximityEligibility": "NOT_A_FILTER",
        "graphLocalTerminalStatus": (
            "NATIVE_MODE_LOCAL_TERMINAL_IN_PEER_BUFFER_NEAR_OWN_OUTLINE"
            if candidate and near_buffer_outline
            else "NATIVE_MODE_LOCAL_TERMINAL_IN_PEER_BUFFER_OUTLINE_FARTHER"
            if candidate else "NOT_VERIFIED_AS_CLIP_TERMINAL"),
        "physicalRoadFinalEdgeIdentity": "NOT_VERIFIED",
        "realAndroidF8Parity": "NOT_VERIFIED",
        "crossGraphDirectedTransfer": "NOT_VERIFIED",
    }


def locate_receiver_edges(
    config: Path, point: dict, mode: str, *, radius: int = 25,
    runner: Callable = subprocess.run,
) -> list[dict]:
    """Read Valhalla B locate in a bounded window; no completeness claim."""
    if mode not in MODES or type(radius) is not int or not 1 <= radius <= MAX_RADIUS_METRES:
        raise ValueError("Unsupported mode or locate radius")
    position = strict_point(point, "source endpoint")
    query = {
        "locations": [{"lat": position["lat"], "lon": position["lng"]}],
        "costing": mode, "verbose": True, "radius": radius,
    }
    result = runner(
        ["valhalla_service", str(config), "locate",
         json.dumps(query, separators=(",", ":"))],
        capture_output=True, text=True, timeout=70,
    )
    if result.returncode:
        raise OSError("Graph B locate failed")
    try:
        doc, end = json.JSONDecoder().raw_decode(result.stdout.lstrip())
    except (json.JSONDecodeError, AttributeError) as error:
        raise SourceIntegrityError("Malformed Valhalla B locate JSON") from error
    trailing = result.stdout.lstrip()[end:].strip()
    if trailing and not all(
            line.startswith("[INFO] Running ") for line in trailing.splitlines()):
        raise SourceIntegrityError("Unexpected Valhalla locate stdout suffix")
    if not isinstance(doc, list) or len(doc) != 1:
        raise SourceIntegrityError("Valhalla locate returned malformed count")
    if not isinstance(doc[0], dict):
        raise SourceIntegrityError("Malformed Valhalla locate location")
    located = doc[0].get("edges", [])
    if not isinstance(located, list) or len(located) > MAX_B_LOCATE_RESULTS:
        raise SourceIntegrityError("Incomplete/oversized B locate result")
    ids = set()
    observations = []
    for item in located:
        if not isinstance(item, dict) or not isinstance(item.get("edge_id"), dict):
            raise SourceIntegrityError("Malformed B locate entry")
        gid = item["edge_id"].get("value")
        if type(gid) is not int or gid <= 0 or gid in ids:
            raise SourceIntegrityError("Missing/duplicate B native directed identity")
        ids.add(gid)
        dist = item.get("distance")
        if type(dist) not in (int, float) or not math.isfinite(dist) or dist < 0:
            raise SourceIntegrityError("Invalid B correlation distance")
        record = item.get("edge")
        if (not isinstance(record, dict) or
                type(record.get("deadend")) is not bool or
                type(record.get("forward")) is not bool):
            raise SourceIntegrityError("Malformed locate directed edge metadata")
        observations.append({
            "receiverGraphId": gid,
            "locateDistanceMeters": float(dist),
            "locateNativeDeadend": record["deadend"],
            "locateForward": record["forward"],
        })
    return observations


def inspect_receivers(
    source_endpoint: dict, located: list[dict], receiver_rows: list[dict],
    mode: str,
) -> list[dict]:
    if len(located) != len(receiver_rows):
        raise SourceIntegrityError("B located edge set/native geometry count mismatch")
    output = []
    for locator, raw in zip(located, receiver_rows):
        if (not isinstance(raw, dict)
                or type(raw.get("sourceGraphId")) is not int
                or raw["sourceGraphId"] != locator["receiverGraphId"]):
            raise SourceIntegrityError("Wrong/missing B native GraphId for locate identity")
        b = checked_edge(raw)
        p = nearest(source_endpoint, b["directedGeometry"])
        lengths = [distance(a, z) for a, z in zip(
            b["directedGeometry"], b["directedGeometry"][1:])]
        remain = max(0.0, sum(lengths) - p["distanceAlongDirectedEdgeMeters"])
        output.append({
            **locator,
            "modeForwardAccess": bool(b["forwardAccess"] & MODES[mode]),
            "nativeDeadend": b.get("deadend"),
            "nearSourceTerminalMeters": round(p["metres"], 3),
            "remainingBDirectedEdgeMeters": round(remain, 3),
            "nativeBEdgeLengthMeters": round(sum(lengths), 3),
            "candidatePhysicalRoadRelation": "NOT_VERIFIED",
            "crossGraphLegalTransfer": "NOT_VERIFIED",
        })
    return output


def local_journey_sample(
    source: dict, receiver: dict, source_cfg: Path, receiver_cfg: Path,
    mode: str, route_fn: Callable = route,
) -> dict:
    """One source-local terminal route and one B-local departure route.

    Never infer actual Valhalla route edge identity from these endpoints.
    """
    a, b = checked_edge(source), checked_edge(receiver)
    a_total = sum(distance(p, q) for p, q in zip(
        a["directedGeometry"], a["directedGeometry"][1:]))
    b_total = sum(distance(p, q) for p, q in zip(
        b["directedGeometry"], b["directedGeometry"][1:]))
    endpoint = {"lat": a["endLat"], "lng": a["endLon"]}
    proj = nearest(endpoint, b["directedGeometry"])
    remaining = b_total - proj["distanceAlongDirectedEdgeMeters"]
    base = {
        "routeEdgeIdentityFidelity": "NOT_VERIFIED",
        "crossGraphDirectedTransfer": "NOT_VERIFIED",
        "sourcePhysicalRoadFinalEdgeIdentity": "NOT_VERIFIED",
    }
    if (not a["forwardAccess"] & MODES[mode] or
            not b["forwardAccess"] & MODES[mode] or
            a_total <= MIN_LOCAL_LEG_METRES or
            remaining <= MIN_LOCAL_LEG_METRES):
        return {**base, "status": "NOT_ATTEMPTED_SHORT_OR_INACCESSIBLE_LOCAL_LEG"}
    origin = point_along(
        a["directedGeometry"],
        max(1.0, a_total - min(ROUTE_SAMPLE_METRES, a_total * 0.5)))
    dest = point_along(
        b["directedGeometry"], min(
            b_total - 1, proj["distanceAlongDirectedEdgeMeters"] +
            min(ROUTE_SAMPLE_METRES, remaining * 0.5)))
    try:
        first = route_fn(source_cfg, origin, endpoint, mode)
        if first.get("status") != "SUCCEEDED":
            return {**base, "status": "INCONCLUSIVE_SOURCE_LOCAL_ROUTE"}
        normalized = strict_point(first["endActual"], "A normalized terminal")
        second = route_fn(receiver_cfg, normalized, dest, mode)
        if second.get("status") != "SUCCEEDED":
            return {**base, "status": "INCONCLUSIVE_B_RECEIVER_LOCAL_ROUTE"}
        a_start = distance(
            origin, strict_point(first["startActual"], "A actual origin"))
        a_arrival = distance(normalized, endpoint)
        b_start = distance(
            normalized, strict_point(second["startActual"], "B departure"))
        b_arrival = distance(
            dest, strict_point(second["endActual"], "B local destination"))
        offsets = []
        for leg in (first, second):
            for key in ("startOffsetMeters", "endOffsetMeters"):
                value = leg.get(key)
                if (type(value) not in (float, int) or
                        not math.isfinite(value) or value < 0):
                    return {**base, "status": "INCONCLUSIVE_INVALID_ROUTE_SNAP_EVIDENCE"}
                offsets.append(value)
        costs = [first.get("durationSeconds"), first.get("distanceKm"),
                 second.get("durationSeconds"), second.get("distanceKm")]
        if any(type(x) not in (int, float) or not math.isfinite(x)
               or x < 0 for x in costs):
            return {**base, "status": "INCONCLUSIVE_INVALID_ROUTE_COST_EVIDENCE"}
        if any(x > ARRIVAL_TOLERANCE_METERS for x in (
                a_start, a_arrival, b_start, b_arrival, *offsets)):
            return {**base, "status": "UNPROVEN_ENDPOINT_ALIGNMENT",
                    "sourceOriginOffsetMeters": round(a_start, 3),
                    "terminalArrivalMeters": round(a_arrival, 3),
                    "crossGraphStartGapMeters": round(b_start, 3),
                    "receiverArrivalMeters": round(b_arrival, 3),
                    "reportedSnapOffsetsMeters": offsets}
        return {
            **base,
            "status": "TWO_GRAPH_LOCAL_ROUTE_LEGS_SUCCEEDED_FOR_TERMINAL_SAMPLE",
            "sourceOriginOffsetMeters": round(a_start, 3),
            "terminalArrivalMeters": round(a_arrival, 3),
            "crossGraphStartGapMeters": round(b_start, 3),
            "receiverArrivalMeters": round(b_arrival, 3),
            "reportedSnapOffsetsMeters": offsets,
            "routeEdgeIdentityFidelity": "NOT_VERIFIED",
            "sourceLocalDurationSeconds": first["durationSeconds"],
            "receiverLocalDurationSeconds": second["durationSeconds"],
            "sourceLocalDistanceKm": first["distanceKm"],
            "receiverLocalDistanceKm": second["distanceKm"],
            "routeStart": origin,
            "requestedNativeTerminal": endpoint,
            "receiverLocalDestination": dest,
        }
    except (ValueError, KeyError, TypeError, OSError, subprocess.TimeoutExpired):
        return {**base, "status": "INCONCLUSIVE_LOCAL_ROUTE_CAPTURE"}


def inspect_receiver_alternatives(
    source: dict, source_endpoint: dict, located: list[dict],
    capture: Callable[[int], dict], config_a: Path, config_b: Path, mode: str,
    route_fn: Callable = route,
) -> list[dict]:
    """Preserve all B locate identities; one recoverable capture failure
    must not hide a different alternative or silently accept wrong GraphIds.
    """
    reports = []
    for identity in located:
        try:
            raw = capture(identity["receiverGraphId"])
            observed = inspect_receivers(
                source_endpoint, [identity], [raw], mode)[0]
            observed["localJourney"] = local_journey_sample(
                source, raw, config_a, config_b, mode, route_fn)
        except SourceIntegrityError:
            raise
        except ValueError as error:
            if (isinstance(error, json.JSONDecodeError) or
                    "Native geometry identities/counts mismatch explicit selection" in str(error)):
                raise SourceIntegrityError(
                    "Native B geometry identities/counts mismatch selected locate ID"
                ) from error
            observed = {
                **identity,
                "nativeGeometry": "INCONCLUSIVE_B_NATIVE_CAPTURE",
                "candidatePhysicalRoadRelation": "NOT_VERIFIED",
                "crossGraphLegalTransfer": "NOT_VERIFIED",
                "localJourney": {"status": "INCONCLUSIVE_B_NATIVE_CAPTURE"},
                "reason": str(error)[:200],
            }
        except (OSError, TypeError, IndexError, KeyError,
                subprocess.TimeoutExpired, subprocess.CalledProcessError) as error:
            observed = {
                **identity,
                "nativeGeometry": "INCONCLUSIVE_B_NATIVE_CAPTURE",
                "candidatePhysicalRoadRelation": "NOT_VERIFIED",
                "crossGraphLegalTransfer": "NOT_VERIFIED",
                "localJourney": {"status": "INCONCLUSIVE_B_NATIVE_CAPTURE"},
                "reason": str(error)[:200],
            }
        reports.append(observed)
    return reports


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "pair", "from-manifest", "to-manifest",
        "from-buffer", "to-buffer", "native-endpoints-binary"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--direction", required=True, choices=("from-to", "to-from"))
    parser.add_argument("--mode", required=True, choices=sorted(MODES))
    parser.add_argument("--source-graph-id", action="append", required=True, type=int)
    parser.add_argument("--locate-radius", type=int, default=25)
    args = parser.parse_args()
    if (len(args.source_graph_id) > MAX_SOURCE_IDS or
            any(i <= 0 for i in args.source_graph_id) or
            len(args.source_graph_id) != len(set(args.source_graph_id))):
        raise ValueError("Invalid/duplicate explicit source terminal selection")
    native = verify_native_extractor(args.native_endpoints_binary)
    pair = json.loads(args.pair.read_text(encoding="utf-8"))
    pair_identity(pair)
    ma = json.loads(args.from_manifest.read_text(encoding="utf-8"))
    mb = json.loads(args.to_manifest.read_text(encoding="utf-8"))
    ba = verified_buffer(args.from_buffer, ma)
    bb = verified_buffer(args.to_buffer, mb)
    with tempfile.TemporaryDirectory(prefix="roadpilot-f8-m6c-terminal-") as folder:
        temp = Path(folder)
        ga, ca = graph_manifest_info(
            args.from_manifest, pair["fromRegionId"],
            mb["source"]["primaryGeofabrikId"],
            pair["fromBoundaryFingerprint"], temp, "A")
        gb, cb = graph_manifest_info(
            args.to_manifest, pair["toRegionId"],
            ma["source"]["primaryGeofabrikId"],
            pair["toBoundaryFingerprint"], temp, "B")
        verify_retained_graph_identity(pair, ga, gb)
        if args.direction == "to-from":
            ca, cb = cb, ca
            ba, bb = bb, ba
        results = []
        for gid in args.source_graph_id:
            src = native_rows(args.native_endpoints_binary, ca, [gid], temp)[0]
            adj = native_adjacency(args.native_endpoints_binary, ca, gid, temp)
            terminal = check_source_terminal(src, adj, args.mode, ba, bb)
            endpoint = terminal["sourceDirectedEndpoint"]
            found = []
            try:
                found = locate_receiver_edges(
                    cb, endpoint, args.mode, radius=args.locate_radius)
                def capture_b(gid: int) -> dict:
                    return native_rows(
                        args.native_endpoints_binary, cb, [gid], temp)[0]
                receiver_observations = inspect_receiver_alternatives(
                    src, endpoint, found, capture_b, ca, cb, args.mode)
                receiver_error = None
            except SourceIntegrityError:
                # Wrong/missing B native IDs, altered locate counts and
                # invalid/mismatched native evidence must stop the entire
                # diagnostic, not silently downgrade another graph identity.
                raise
            except (OSError, ValueError, TypeError,
                    subprocess.TimeoutExpired) as error:
                # A recoverable B read/correlation failure does not erase a
                # source terminal or previously returned B locator identities.
                receiver_observations = [{
                    **item, "nativeGeometry": "INCONCLUSIVE_B_NATIVE_CAPTURE",
                    "candidatePhysicalRoadRelation": "NOT_VERIFIED",
                    "crossGraphLegalTransfer": "NOT_VERIFIED",
                    "localJourney": {"status": "INCONCLUSIVE_B_NATIVE_CAPTURE"},
                } for item in found]
                receiver_error = str(error)[:230]
            results.append({
                "source": terminal,
                "receiverLocatedGraphIds": [
                    item["receiverGraphId"] for item in found],
                "receivers": receiver_observations,
                "receiverLocateFailure": receiver_error,
                "receiverDiscoveryCompleteness": "NOT_VERIFIED_RADIUS_ONLY",
                "physicalRoadContinuity": "NOT_VERIFIED",
                "legalSeamTransfer": "NOT_VERIFIED",
                "publicationState": "BLOCKED",
            })
    print(json.dumps({
        "schema": "roadpilot.f8-native-m6c-retained-clip-terminal-diagnostic",
        "version": 0, "direction": args.direction, "mode": args.mode,
        "pairId": pair["pairId"],
        "fromGraphFingerprint": pair["fromGraphFingerprint"],
        "toGraphFingerprint": pair["toGraphFingerprint"],
        "fromBoundaryFingerprint": pair["fromBoundaryFingerprint"],
        "toBoundaryFingerprint": pair["toBoundaryFingerprint"],
        **native,
        "selectedSourceTerminalCount": len(results),
        "selectedSourceTerminalEvidence": results,
        "fullRetainedRoadTerminalIdentity": "NOT_VERIFIED",
        "routeEdgeIdentityFidelity": "NOT_VERIFIED",
        "androidF8Parity": "NOT_VERIFIED",
        "discoveryCoverage": "NOT_VERIFIED",
        "publicationState": "BLOCKED",
    }, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, TypeError,
            subprocess.TimeoutExpired, subprocess.CalledProcessError) as error:
        print("NATIVE_F8_M6C_CLIP_TERMINAL_ERROR: " + str(error)[:380],
              file=sys.stderr)
        sys.exit(2)
