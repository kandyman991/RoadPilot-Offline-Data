#!/usr/bin/env python3
"""Source graph ONLY: prove final directed edges at real 25km cut via original TripLeg.

Never matches B, recreates a connector matrix, traverses core-to-core routes or
deduplicates by OSM way/geometry. Every other original candidate stays retained
in the SHA-bound parent reports; unrouteable evidence remains unresolved.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import subprocess
import tempfile

from build_native_f8_pair_evidence import pair_identity
from build_native_f8_final_edge_register import digest, pinned
from capture_native_f8_graph_windows import read
from census_native_f8_final_directed_edges import verify_binary
from probe_native_f8_directed_turn import probe_point
from native_f8_inputs import graph_manifest_info
from native_f8_original_route import route_with_original_ids, verify_native_route_binary
from probe_native_f8_journey import distance, verify_retained_graph_identity

SCHEMA = "roadpilot.f8-original-source-cut-last-tripleg"
NO_ALT = "NO_OTHER_NATIVE_MODE_ACCESSIBLE_HIERARCHY_OUTGOING"
STATUS_PROVEN = "ORIGINAL_SOURCE_LAST_DIRECTED_TRIPLEG_GRAPHID_MATCHED"
TOLERANCE_METRES = 1.0


def classify_source_last_edge(probe: dict, candidate: dict) -> dict:
    """Require actual original TripLeg identity and exact start/end snap."""
    gid = candidate["finalDirectedGraphId"]
    if (type(gid) is not int or gid <= 0
            or not isinstance(probe, dict)):
        raise ValueError("Invalid source original route proof input")
    if probe.get("status") != "SUCCEEDED":
        return {"sourceLastEdgeProof": "NOT_VERIFIED",
                "originalRouteStatus": probe.get("status", "INVALID"),
                "reason": str(probe.get("reason", "route not successful"))[:250]}
    exact = (
        probe.get("originalRouteEdgeIdentity") == "ORIGINAL_VALHALLA_ROUTE_PROTOBUF"
        and probe.get("edgeIdOrigin") == "ORIGINAL_TRIPLEG_NODE_EDGE_PROTOBUF"
        and probe.get("lastDirectedGraphId") == gid
        and isinstance(probe.get("originalNativeDirectedGraphIds"), list)
        and bool(probe["originalNativeDirectedGraphIds"])
        and probe["originalNativeDirectedGraphIds"][-1] == gid
        and type(probe.get("startOffsetMeters")) in (int, float)
        and type(probe.get("endOffsetMeters")) in (int, float)
        and probe["startOffsetMeters"] <= TOLERANCE_METRES
        and probe["endOffsetMeters"] <= TOLERANCE_METRES
        and distance(probe["endActual"], candidate["nativeTerminal"])
            <= TOLERANCE_METRES
    )
    return {
        "sourceLastEdgeProof": STATUS_PROVEN if exact else "NOT_VERIFIED",
        "originalRouteStatus": "SUCCEEDED",
        "originalNativeLastGraphId": probe.get("lastDirectedGraphId"),
        "originalNativeTripLegDirectedGraphIds": probe.get(
            "originalNativeDirectedGraphIds", []),
        "startSnapMeters": probe.get("startOffsetMeters"),
        "endSnapMeters": probe.get("endOffsetMeters"),
        "reason": ("" if exact else "Route identity or original local source snap mismatch"),
    }


def native_original_rows(native: Path, config: Path, ids: list[int],
                         option: str, folder: Path) -> list[dict]:
    """Exact original GraphReader end-node evidence, not physical-road inference."""
    if (not ids or len(ids) > 256 or len(ids) != len(set(ids))
            or any(type(gid) is not int or gid <= 0 for gid in ids)):
        raise ValueError("Missing, duplicate, excessive or invalid original directed IDs")
    path = folder / "original-source-one-hop-ids.txt"
    path.write_text("".join(str(gid)+"\n" for gid in ids), encoding="ascii")
    proc = subprocess.run(
        [str(native), str(config), str(path), option],
        capture_output=True, text=True, timeout=120, check=False)
    if proc.returncode:
        raise ValueError("Original native predecessor GraphReader failed: "
                         + proc.stderr[-300:])
    lines = proc.stdout.splitlines()
    if len(lines) != len(ids):
        raise ValueError("Incomplete original native predecessor GraphReader evidence")
    rows = [json.loads(line) for line in lines]
    if [r.get("sourceGraphId") for r in rows] != ids:
        raise ValueError("Original native predecessor GraphIds reordered/substituted")
    return rows


def prove_one_hop_local_source_predecessors(
    config: Path, candidate: dict, mode: str, route_binary: Path,
    native_binary: Path,
) -> dict:
    """Retry sub-5m source edges from every original ROOT-level predecessor.

    The original directed edge may be too short for Valhalla to accept a
    source point strictly inside it. Capture every original incoming edge at
    that start node and use Valhalla's actual TripLeg first/last GraphIds.
    A success on ONE incoming road proves the nominated FINAL directed edge
    is routable; it does not establish completeness of all incoming branches.
    No first-success lock-in: every root predecessor is still tested.
    """
    gid = candidate["finalDirectedGraphId"]
    with tempfile.TemporaryDirectory(prefix="f8-one-hop-source-") as root:
        work = Path(root)
        last = native_original_rows(native_binary, config, [gid],
                                    "--continuations", work)[0]
        if last.get("endNodeGraphId") != candidate["nativeEndNodeGraphId"]:
            raise ValueError("Original source last-edge end node mutated")
        opposite = last.get("opposingGraphId")
        if type(opposite) is not int or opposite <= 0:
            raise ValueError("Missing original source reverse GraphId")
        start_node = native_original_rows(
            native_binary, config, [opposite],
            "--continuations", work)[0]
        start_id = start_node.get("endNodeGraphId")
        start_pos = {
            "lat": start_node.get("endLat"), "lng": start_node.get("endLon")}
        if (type(start_id) is not int or start_id <= 0
                or distance(start_pos, candidate["sourceStartNodeAnnotationOnly"]) > 3.0):
            raise ValueError("Original source start node/position mismatch")
        outgoing = start_node.get("outgoingDirectedEdges")
        if not isinstance(outgoing, list) or len(outgoing) > 256:
            raise ValueError("Invalid original source root outgoing inventory")
        other_outgoings = [x for x in outgoing if x.get("graphId") != gid]
        out_ids = [x.get("graphId") for x in other_outgoings]
        if sum(1 for x in outgoing if x.get("graphId") == gid) != 1:
            raise ValueError("Original final edge missing or duplicated at its start node")
        if not out_ids:
            return {"status": "NOT_VERIFIED",
                    "reason": "No original same-level upstream alternatives",
                    "allRootPredecessorAlternativesCaptured": True,
                    "upstreamProbes": []}
        if len(out_ids) > 64:
            return {"status": "NOT_VERIFIED",
                    "reason": "Root incoming fanout exceeds bounded diagnostic budget",
                    "allRootPredecessorAlternativesCaptured": False,
                    "rootIncomingCount": len(out_ids),
                    "upstreamProbes": []}
        outgoing_rows = native_original_rows(
            native_binary, config, out_ids, "--continuations", work)
        opp_ids = [x.get("opposingGraphId") for x in outgoing_rows]
        if (any(type(x) is not int or x <= 0 for x in opp_ids)
                or len(opp_ids) != len(set(opp_ids))):
            raise ValueError("Missing/duplicate original upstream opposing directed ID")
        incomings = native_original_rows(
            native_binary, config, opp_ids, "--geometry", work)
        attempts = []
        exact = []
        for out, incoming in zip(other_outgoings, incomings):
            # Align the incoming original node *topology*, not way IDs,
            # heading, road class, identity across regions or proximity.
            if (incoming["endNodeGraphId"] != start_id
                    or not isinstance(incoming.get("directedGeometry"), list)):
                raise ValueError("Original one-hop predecessor not connected to last edge")
            geom = incoming["directedGeometry"]
            vertices = [{"lat": v[0], "lng": v[1]} for v in geom]
            item = {
                "incomingOriginalDirectedGraphId": incoming["sourceGraphId"],
                "rootOriginalOutgoingGraphId": out["graphId"],
                "incomingOriginalWayIdAnnotationOnly": incoming["wayId"],
                "mode": mode,
            }
            if not incoming["forwardAccess"] & {"auto": 1, "motorcycle": 1024}[mode]:
                item["proof"] = "NOT_VERIFIED_MODE_INACCESSIBLE_IN_ORIGINAL_GRAPH"
            else:
                try:
                    near, length = probe_point(vertices, incoming=True)
                except (TypeError, ValueError, IndexError) as exc:
                    item["proof"] = "NOT_VERIFIED_SHORT_PREDECESSOR"
                    item["reason"] = str(exc)[:100]
                else:
                    original = route_with_original_ids(
                        config, near, candidate["nativeTerminal"], mode,
                        route_binary, timeout=60)
                    verdict = classify_source_last_edge(original, candidate)
                    item["originalTripLegResult"] = verdict
                    item["incomingEdgeLengthMetres"] = length
                    correct_first = original.get("firstDirectedGraphId") == incoming[
                        "sourceGraphId"]
                    item["originalTripLegFirstIsExactPredecessor"] = correct_first
                    if verdict["sourceLastEdgeProof"] == STATUS_PROVEN and correct_first:
                        item["proof"] = STATUS_PROVEN
                        exact.append((item, original))
                    else:
                        item["proof"] = "NOT_VERIFIED"
            attempts.append(item)
        return {
            "status": STATUS_PROVEN if exact else "NOT_VERIFIED",
            "rootOriginalSourceStartNodeGraphId": start_id,
            "allRootPredecessorAlternativesCaptured": True,
            "upstreamProbes": attempts,
            "exactOriginalOneHopProofCount": len(exact),
            "firstExactOriginalNativeTripLegGraphIds": (
                exact[0][1]["originalNativeDirectedGraphIds"] if exact else []),
            "physicalRoadDirectionClass": "NOT_VERIFIED",
            "receiverGraphCorrelations": "NOT_STARTED",
        }


def verify_one_side(cfg: Path, register_side: dict, hierarchy_side: dict,
                    binary: Path, label: str, endpoint_binary: Path | None = None) -> dict:
    candidates = register_side.get("terminalCandidates")
    evidence = hierarchy_side.get("allOriginalSourceFinalEdgeCandidateProofs")
    if (not isinstance(candidates, list) or not isinstance(evidence, list)
            or len(candidates) != len(evidence)
            or register_side.get("uniqueOriginalTerminalCandidateGraphIds") != len(candidates)
            or hierarchy_side.get("modeStopNativeGraphIdsReconciled") != len(candidates)):
        raise ValueError("Source final-edge register/hierarchy not exhaustive")
    by_gid = {}
    for c in candidates:
        gid = c.get("finalDirectedGraphId")
        if type(gid) is not int or gid in by_gid:
            raise ValueError("Repeated original candidate GraphId")
        by_gid[gid] = c
    counted = Counter()
    results = []
    for evidence_row in evidence:
        gid = evidence_row.get("originalDirectedGraphId")
        candidate = by_gid.get(gid)
        if candidate is None or evidence_row.get("candidateSuppressed") is not False:
            raise ValueError("Native original candidate identity not retained")
        if not evidence_row.get("originalDirectedEdgeIntersects25kmSourceCut"):
            counted["nativeCandidatesNotOnCutStillPreservedUpstream"] += 1
            continue  # no B, no geometry exclusion in upstream inventory
        if candidate.get("nativeEndNodeGraphId") != evidence_row.get("nativeEndNodeGraphId"):
            raise ValueError("Original source graph end node changed")
        proof_modes = evidence_row.get("originalModeEndStatus")
        if set(proof_modes) != set(candidate.get("vehicleModes", [])):
            raise ValueError("Native mode hierarchy proof incomplete for cut edge")
        per_mode = {}
        for mode in candidate["vehicleModes"]:
            status = proof_modes[mode]["status"]
            if status != NO_ALT:
                # Diagnostic hierarchy alternatives are NOT eligibility
                # filters. Route EVERY geometry-positive source cut candidate
                # for every supported mode, while retaining the unresolved
                # physical-road continuation status separately.
                counted["unresolvedNativeHierarchyModeAlternatives"] += 1
            res = route_with_original_ids(
                cfg, candidate["sourceInteriorSampleAnnotationOnly"],
                candidate["nativeTerminal"], mode, binary, timeout=60)
            claim = classify_source_last_edge(res, candidate)
            if claim["sourceLastEdgeProof"] != STATUS_PROVEN and endpoint_binary is not None:
                fallback = prove_one_hop_local_source_predecessors(
                    cfg, candidate, mode, binary, endpoint_binary)
                claim["originalOneHopImmediateSourcePredecessorProof"] = fallback
                counted["sourceModeProbesRequiringOriginalOneHopRetry"] += 1
                if fallback["status"] == STATUS_PROVEN:
                    claim["firstAttemptOriginalRouteStatus"] = claim["originalRouteStatus"]
                    claim["sourceLastEdgeProof"] = STATUS_PROVEN
                    claim["originalRouteStatus"] = "SUCCEEDED_WITH_ORIGINAL_SOURCE_IMMEDIATE_PREDECESSOR"
                    claim["originalNativeLastGraphId"] = candidate["finalDirectedGraphId"]
                    claim["originalNativeTripLegDirectedGraphIds"] = (
                        fallback["firstExactOriginalNativeTripLegGraphIds"])
                    claim["reason"] = ""
                    claim["proofMethod"] = "ORIGINAL_SOURCE_IMMEDIATE_PREDECESSOR_TRIPLEG"
            claim["nativeSourceHierarchyModeStatus"] = status
            claim["uniqueFinalPhysicalRoadEdgeStatus"] = "NOT_VERIFIED"
            per_mode[mode] = claim
            counted[claim["sourceLastEdgeProof"]] += 1
            if sum(counted.values()) % 50 == 0:
                print(label, "short local original TripLeg route checks",
                      sum(v for k, v in counted.items() if
                          k in (STATUS_PROVEN, "NOT_VERIFIED")), flush=True)
        results.append({
            "originalNativeSourceDirectedGraphId": gid,
            "sourceOriginalEndNodeGraphId": candidate["nativeEndNodeGraphId"],
            "originalNativeSourceCutGeometryIntersects": True,
            "vehicleModes": per_mode,
            "distinctActualPhysicalRoadDirection": "NOT_VERIFIED",
            "originalReceiverRoad": "NOT_STARTED",
            "candidateSuppressed": False,
        })
        counted["sourceCutCandidateEdgesAudited"] += 1
    if counted["sourceCutCandidateEdgesAudited"] + counted[
            "nativeCandidatesNotOnCutStillPreservedUpstream"] != len(candidates):
        raise ValueError("Source cut proof candidate inventory incomplete")
    return {
        "originalGraphSide": label,
        "allOriginalSourceModeStopCandidatesRetainedInParent": len(candidates),
        "originalSourceCutCandidateDirectedEdges": counted["sourceCutCandidateEdgesAudited"],
        "classifications": dict(sorted(counted.items())),
        "cutCandidateOriginalTripLegProof": results,
        "physicalRoadUniqueLastDirectedEdge": "NOT_VERIFIED",
        "noOriginalCandidateSuppression": True,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    for item in ("pair", "register", "hierarchy", "from-manifest",
                 "to-manifest", "native-route-binary", "native-endpoint-binary", "output"):
        ap.add_argument("--" + item, type=Path, required=True)
    for item in ("register", "hierarchy", "native-route-binary", "native-endpoint-binary"):
        ap.add_argument("--expected-" + item + "-sha256", required=True)
    args = ap.parse_args()
    if args.output.exists() or args.output.is_symlink():
        raise ValueError("Immutable source-only original TripLeg report already exists")
    files = {name: getattr(args, name.replace("-", "_")) for name in (
        "pair", "register", "hierarchy", "from-manifest",
        "to-manifest", "native-route-binary", "native-endpoint-binary")}
    hashes = {name: digest(path) for name, path in files.items()}
    for item in ("register", "hierarchy", "native-route-binary", "native-endpoint-binary"):
        pinned(files[item], getattr(args,
            "expected_" + item.replace("-", "_") + "_sha256"))
    verify_native_route_binary(args.native_route_binary,
                               expected_sha256=hashes["native-route-binary"])
    verify_binary(args.native_endpoint_binary, hashes["native-endpoint-binary"])
    pair, register, hierarchy = (read(args.pair), read(args.register),
                                 read(args.hierarchy))
    pair_identity(pair)
    if (register.get("version") != 2 or hierarchy.get("schema")
            != "roadpilot.f8-source-final-edge-hierarchy-census"
            or hierarchy.get("sourceSideProofCoverage")
            != "ALL_REGISTERED_NATIVE_MODE_STOP_END_NODES"
            or hierarchy.get("oneFinalDirectedEdgePerActualPhysicalRoadAndDirection")
            != "NOT_VERIFIED"
            or hierarchy.get("receivingGraphCorrelation") != "NOT_STARTED"
            or hierarchy.get("immutableSourceSHA256", {}).get("register")
            != hashes["register"]):
        raise ValueError("Full source-only native hierarchy original evidence invalid")
    if (hierarchy.get("pairId") != pair["pairId"]
            or register.get("pairId") != pair["pairId"]):
        raise ValueError("Source graph pair mismatch")
    for side in ("from", "to"):
        if (hierarchy.get("graphFingerprints", {}).get(side)
                != pair[side+"GraphFingerprint"]):
            raise ValueError("Stale immutable original region graph fingerprint")
    man_a, man_b = read(args.from_manifest), read(args.to_manifest)
    with tempfile.TemporaryDirectory(prefix="f8-original-final-source-only-") as root:
        temp = Path(root)
        a, cfg_a = graph_manifest_info(
            args.from_manifest, pair["fromRegionId"],
            man_b["source"]["primaryGeofabrikId"],
            pair["fromBoundaryFingerprint"], temp, "A")
        b, cfg_b = graph_manifest_info(
            args.to_manifest, pair["toRegionId"],
            man_a["source"]["primaryGeofabrikId"],
            pair["toBoundaryFingerprint"], temp, "B")
        verify_retained_graph_identity(pair, a, b)
        reports = {
            "from-to": verify_one_side(cfg_a, register["directions"]["from-to"],
                hierarchy["directions"]["from-to"], args.native_route_binary,
                pair["fromRegionId"], args.native_endpoint_binary),
            "to-from": verify_one_side(cfg_b, register["directions"]["to-from"],
                hierarchy["directions"]["to-from"], args.native_route_binary,
                pair["toRegionId"], args.native_endpoint_binary),
        }
    for side, manifest_path, manifest in (
            ("from", args.from_manifest, man_a),
            ("to", args.to_manifest, man_b)):
        archive = manifest_path.parent / manifest["artifact"]["fileName"]
        if digest(archive) != pair[side+"GraphFingerprint"]:
            raise ValueError("Immutable original graph changed during TripLeg proof")
    if any(digest(path) != hashes[k] for k, path in files.items()):
        raise ValueError("Original source-side proof source mutated during execution")
    doc = {
        "schema": SCHEMA, "version": 1, "pairId": pair["pairId"],
        "sourceGraphFingerprints": {
            "from": pair["fromGraphFingerprint"], "to": pair["toGraphFingerprint"]},
        "immutableSourceSHA256": hashes,
        "directions": reports,
        "sourceRouteScope": "ORIGINAL_VALHALLA_SHORT_ROUTE_START_INSIDE_DIRECTED_EDGE_TO_OWN_TERMINAL",
        "allPhysicalRoadDirectionsUnique": "NOT_VERIFIED",
        "receivingRegionGraphCorrelation": "NOT_STARTED",
        "completeCrossGraphJourneys": "NOT_VERIFIED",
        "productionPublication": "BLOCKED",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    stage = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8",
                dir=args.output.parent, delete=False,
                prefix=".f8-original-source-cut-tripleg-") as f:
            stage = Path(f.name)
            json.dump(doc, f, indent=2, allow_nan=False)
            f.write("\n")
        if args.output.exists() or args.output.is_symlink():
            raise ValueError("Concurrent immutable TripLeg output exists")
        os.link(stage, args.output)
    finally:
        if stage is not None:
            stage.unlink(missing_ok=True)
    print("Original source cut TripLeg identity proof completed; physical-road",
          "uniqueness NOT_VERIFIED, receiving graph NOT_STARTED.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        raise SystemExit("F8_SOURCE_CUT_TRIPLEG_ERROR: " + str(exc)[:350])
