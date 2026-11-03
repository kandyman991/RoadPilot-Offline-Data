#!/usr/bin/env python3
"""Read-only full native-edge geometry observation for one selected F8 source edge.

No handoff, cross-graph turn, journey proof, Android parity, or exhaustive
coverage may be inferred from geometry proximity alone. Never publishes data.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile

from build_native_f8_pair_evidence import pair_identity
from native_f8_inputs import graph_manifest_info
from probe_native_f8_journey import distance, verify_retained_graph_identity
from verify_native_f8_receiver_adjacency import AUTO_ACCESS, MOTORCYCLE_ACCESS

MODES = {"auto": AUTO_ACCESS, "motorcycle": MOTORCYCLE_ACCESS}
GEOMETRY_OBSERVATION_METRES = 1.0  # Annotation, never a discovery eligibility rule.
TAIL_METRES = 20.0
MAX_RECEIVER_IDS = 2048  # Explicit diagnostic batch limit, unrelated to Android JNI 512.


def point(lat: object, lon: object) -> dict:
    if (type(lat) not in (float, int) or type(lon) not in (float, int)
            or not math.isfinite(lat) or not math.isfinite(lon)
            or not -80 <= lat <= 80 or not -180 <= lon <= 180):
        raise ValueError("Nonfinite or invalid directed geometry coordinate")
    return {"lat": float(lat), "lng": float(lon)}


def checked_edge(row: dict) -> dict:
    if not isinstance(row, dict) or type(row.get("sourceGraphId")) is not int or row["sourceGraphId"] <= 0:
        raise ValueError("Missing native directed GraphId")
    if type(row.get("wayId")) is not int or row["wayId"] <= 0:
        raise ValueError("Missing physical way ID annotation")
    mask = row.get("forwardAccess")
    if type(mask) is not int or not 0 <= mask < 2**32:
        raise ValueError("Invalid native forward access")
    shape = row.get("directedGeometry")
    if not isinstance(shape, list) or len(shape) < 2 or len(shape) > 100000:
        raise ValueError("Missing or oversized full native directed edge geometry")
    vertices = []
    for vertex in shape:
        if not isinstance(vertex, list) or len(vertex) != 2:
            raise ValueError("Invalid native directed geometry vertex")
        vertices.append(point(*vertex))
    end = point(row.get("endLat"), row.get("endLon"))
    if distance(vertices[-1], end) > 2.0:
        raise ValueError("Native directed geometry does not terminate at its graph-local end node")
    if sum(distance(a, b) for a, b in zip(vertices, vertices[1:])) < 0.01:
        raise ValueError("Degenerate native directed geometry")
    return {**row, "directedGeometry": vertices}


def offset_meters(a: dict, b: dict, reference_lat: float) -> tuple[float, float]:
    return (
        (b["lng"] - a["lng"]) * 111195.0 * math.cos(math.radians(reference_lat)),
        (b["lat"] - a["lat"]) * 111195.0,
    )


def nearest(point_to_find: dict, geometry: list[dict]) -> dict:
    """Nearest point and directed tangent on a full edge polyline; no snapping decision."""
    travelled = 0.0
    best = None
    for i, (a, b) in enumerate(zip(geometry, geometry[1:])):
        dx, dy = offset_meters(a, b, point_to_find["lat"])
        length2 = dx * dx + dy * dy
        if length2 < 1e-10:
            continue
        qx, qy = offset_meters(a, point_to_find, point_to_find["lat"])
        fraction = max(0., min(1., (qx * dx + qy * dy) / length2))
        metres = math.hypot(qx - fraction * dx, qy - fraction * dy)
        length = math.sqrt(length2)
        observation = {
            "metres": metres, "segmentIndex": i, "segmentFraction": fraction,
            "distanceAlongDirectedEdgeMeters": travelled + fraction * length,
            "tangent": (dx / length, dy / length),
        }
        if best is None or (metres, i) < (best["metres"], best["segmentIndex"]):
            best = observation
        travelled += length
    if best is None:
        raise ValueError("Degenerate receiver polyline")
    return best


def tail_points(vertices: list[dict]) -> list[dict]:
    """Last at most 20 metres of A's actual directed edge, sampled every ~2 metres."""
    lengths = [distance(a, b) for a, b in zip(vertices, vertices[1:])]
    tail = min(TAIL_METRES, sum(lengths))
    steps = max(1, min(32, math.ceil(tail / 2.)))
    samples = []
    for i in range(steps + 1):
        backwards = tail * i / steps
        position = vertices[-1]
        for j in range(len(lengths) - 1, -1, -1):
            segment = lengths[j]
            if backwards <= segment and segment > 1e-7:
                fraction = backwards / segment
                position = {
                    "lat": vertices[j + 1]["lat"] + fraction * (
                        vertices[j]["lat"] - vertices[j + 1]["lat"]),
                    "lng": vertices[j + 1]["lng"] + fraction * (
                        vertices[j]["lng"] - vertices[j + 1]["lng"]),
                }
                break
            backwards -= segment
            position = vertices[j]
        samples.append(position)
    return samples


def terminal_heading(vertices: list[dict]) -> tuple[float, float]:
    end = vertices[-1]
    for earlier in reversed(vertices[:-1]):
        x, y = offset_meters(earlier, end, end["lat"])
        magnitude = math.hypot(x, y)
        if magnitude >= .01:
            return x / magnitude, y / magnitude
    raise ValueError("Source has no terminal directed tangent")


def inspect_geometry(source: dict, receivers: list[dict], mode: str) -> dict:
    if mode not in MODES:
        raise ValueError("Unsupported vehicle mode")
    source = checked_edge(source)
    rows = [checked_edge(row) for row in receivers]
    identities = [row["sourceGraphId"] for row in rows]
    if not rows or len(set(identities)) != len(identities):
        raise ValueError("Empty or duplicate explicitly selected receiver edges")
    point_a = source["directedGeometry"][-1]
    heading = terminal_heading(source["directedGeometry"])
    samples = tail_points(source["directedGeometry"])
    observations = []
    for row in sorted(rows, key=lambda r: r["sourceGraphId"]):
        projected = nearest(point_a, row["directedGeometry"])
        cosine = sum(a * b for a, b in zip(heading, projected["tangent"]))
        observations.append({
            "receiverDirectedGraphId": row["sourceGraphId"],
            "sourceWayAndReceiverWayIdEqual": source["wayId"] == row["wayId"],
            "receiverWayId": row["wayId"],
            "modeForwardAccess": bool(row["forwardAccess"] & MODES[mode]),
            "sourceEndpointToReceiverEndNodeMeters": round(
                distance(point_a, row["directedGeometry"][-1]), 3),
            "sourceEndpointToReceiverPolylineMeters": round(projected["metres"], 3),
            "terminalProjectionSegmentIndex": projected["segmentIndex"],
            "terminalProjectionFraction": round(projected["segmentFraction"], 6),
            "sourceVsReceiverDirectedTangentCosine": round(cosine, 5),
            "terminalGeometryWithinOneMetre": (
                projected["metres"] <= GEOMETRY_OBSERVATION_METRES),
            "physicalHandoffProof": "NOT_VERIFIED",
        })
    # Each sample is compared with ALL explicitly selected receiver edges.
    # Multiple receivers and segmentation changes are never collapsed to one.
    closest = [
        min((nearest(sample, row["directedGeometry"])["metres"],
             row["sourceGraphId"]) for row in rows)
        for sample in samples
    ]
    covered = sum(metres <= GEOMETRY_OBSERVATION_METRES for metres, _ in closest)
    return {
        "schema": "roadpilot.native-f8-terminal-directed-geometry-observation",
        "version": 0, "sourceDirectedGraphId": source["sourceGraphId"],
        "sourceWayId": source["wayId"], "mode": mode,
        "sourceModeForwardAccess": bool(source["forwardAccess"] & MODES[mode]),
        "sourceTerminal": point_a,
        "receiverSelection": "EXPLICIT_GRAPH_LOCAL_IDS_NOT_EXHAUSTIVE",
        "selectedReceiverCount": len(rows),
        "receiverObservations": observations,
        "sourceTailRequestedMetres": TAIL_METRES,
        "sourceTailActualMetres": round(min(TAIL_METRES, sum(
            distance(a, b) for a, b in zip(
                source["directedGeometry"], source["directedGeometry"][1:])
        )), 3),
        "tailSampleCount": len(samples),
        "tailSamplesWithinOneMetreOfSelectedGeometry": covered,
        "maxTailSampleGapMeters": round(max(metres for metres, _ in closest), 3),
        "tailGeometryObservation": (
            "SELECTED_DIRECTED_GEOMETRY_COLOCATION_OBSERVED_NOT_A_HANDOFF_PROOF"
            if covered == len(samples) else "UNRESOLVED_FOR_SELECTED_RECEIVER_EDGES"),
        "crossGraphPhysicalContinuity": "NOT_VERIFIED",
        "crossSeamTurnLegality": "NOT_VERIFIED",
        "journeyValhallaProof": "NOT_RUN",
        "androidF8Parity": "NOT_VERIFIED",
        "coverage": "NOT_VERIFIED",
        "productionPublication": "BLOCKED",
    }


def native_rows(binary: Path, config: Path, ids: list[int], directory: Path) -> list[dict]:
    names = directory / "directed-ids.txt"
    names.write_text("".join(str(identity) + "\n" for identity in ids), encoding="ascii")
    completed = subprocess.run(
        [str(binary), str(config), str(names), "--geometry"],
        capture_output=True, text=True, timeout=180, check=False,
    )
    if completed.returncode:
        raise ValueError("Native geometry capture failed; discard partial stdout: "
                         + completed.stderr[-240:])
    rows = [json.loads(line) for line in completed.stdout.splitlines()]
    if len(rows) != len(ids) or [r.get("sourceGraphId") for r in rows] != ids:
        raise ValueError("Native geometry identities/counts mismatch explicit selection")
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("pair", "from-manifest", "to-manifest", "native-endpoints-binary"):
        parser.add_argument("--" + field, type=Path, required=True)
    parser.add_argument("--direction", choices=["from-to", "to-from"], required=True)
    parser.add_argument("--mode", choices=sorted(MODES), required=True)
    parser.add_argument("--source-graph-id", type=int, required=True)
    parser.add_argument("--receiver-graph-id", type=int, action="append", required=True)
    args = parser.parse_args()
    ids = args.receiver_graph_id
    if (type(args.source_graph_id) is not int or args.source_graph_id <= 0
            or not 1 <= len(ids) <= MAX_RECEIVER_IDS or
            any(type(i) is not int or i <= 0 for i in ids) or
            len(set(ids)) != len(ids)):
        raise ValueError("Invalid or duplicate GraphIds; explicit batch maximum is 2048")
    version = subprocess.run([str(args.native_endpoints_binary), "--version"],
                             capture_output=True, text=True, timeout=15, check=True)
    if version.stdout.strip() != "3.6.3":
        raise ValueError("Exact Valhalla 3.6.3 native geometry binary required")

    pair = json.loads(args.pair.read_text(encoding="utf-8"))
    pair_identity(pair)
    with tempfile.TemporaryDirectory(prefix="roadpilot-f8-geometry-observation-") as scratch:
        tmp = Path(scratch)
        from_manifest = json.loads(args.from_manifest.read_text(encoding="utf-8"))
        to_manifest = json.loads(args.to_manifest.read_text(encoding="utf-8"))
        source_graph, cfg_source = graph_manifest_info(
            args.from_manifest, pair["fromRegionId"],
            to_manifest["source"]["primaryGeofabrikId"],
            pair["fromBoundaryFingerprint"], tmp, "source")
        target_graph, cfg_target = graph_manifest_info(
            args.to_manifest, pair["toRegionId"],
            from_manifest["source"]["primaryGeofabrikId"],
            pair["toBoundaryFingerprint"], tmp, "target")
        verify_retained_graph_identity(pair, source_graph, target_graph)
        if args.direction == "to-from":
            cfg_source, cfg_target = cfg_target, cfg_source
        source = native_rows(args.native_endpoints_binary, cfg_source,
                             [args.source_graph_id], tmp)[0]
        receivers = native_rows(args.native_endpoints_binary, cfg_target, ids, tmp)
        result = inspect_geometry(source, receivers, args.mode)
        result.update({
            "pairId": pair["pairId"], "direction": args.direction,
            "graphFingerprints": {
                "from": pair["fromGraphFingerprint"],
                "to": pair["toGraphFingerprint"],
            },
        })
    print(json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, TypeError, KeyError, subprocess.TimeoutExpired,
            subprocess.CalledProcessError) as error:
        print("NATIVE_F8_GEOMETRY_OBSERVATION_ERROR: " + str(error)[:350],
              file=sys.stderr)
        sys.exit(2)
