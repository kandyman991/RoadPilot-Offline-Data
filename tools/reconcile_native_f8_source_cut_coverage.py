#!/usr/bin/env python3
"""Fail-closed reconciliation of window-scanned cut edges and source-only final-edge witnesses.

No OSM/name/way matching, receiver lookups, road equivalence or publication.
The 3,623-window native scan is NOT an exhaustive inventory of the graph
archive: a predecessor may cross the verified buffer cut but be outside
the common-overlap window scan. Keep those exact original GraphIds unresolved.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile

SCHEMA = "roadpilot.f8-source-cut-window-coverage-reconciliation"
CUT_SCHEMA = "roadpilot.f8-original-all-source-native-directed-cut-census"
CUT_SCOPE = "ALL_RETAINED_SOURCE_SCAN_ORIGINAL_DIRECTED_GRAPHIDS"
SIDES = ("from-to", "to-from")
MODES = ("auto", "motorcycle")
PROVED = "ORIGINAL_SOURCE_LAST_DIRECTED_TRIPLEG_GRAPHID_MATCHED"


def _original_tripleg_matches(proof: object, final_id: int,
                             required_suffix: list[int]) -> bool:
    """Require the actual ordered original TripLeg IDs, not a status label."""
    if not isinstance(proof, dict):
        return False
    trip = proof.get("originalNativeTripLegDirectedGraphIds")
    return (
        proof.get("sourceLastEdgeProof") == PROVED
        and proof.get("originalNativeLastGraphId") == final_id
        and isinstance(trip, list) and len(trip) >= len(required_suffix)
        and all(type(g) is int and g > 0 for g in trip)
        and trip[-len(required_suffix):] == required_suffix
        and type(proof.get("startSnapMeters")) in (int, float)
        and 0 <= proof["startSnapMeters"] <= 1
        and type(proof.get("endSnapMeters")) in (int, float)
        and 0 <= proof["endSnapMeters"] <= 1
    )




def _valid_original_one_hop(proof: dict, final_id: int, mode: str) -> bool:
    """The 3.4-m original final edge needs an actual upstream TripLeg, not
    invented missing top-level offsets or a successful route-status label."""
    if (not isinstance(proof, dict)
            or proof.get("originalRouteStatus") !=
            "SUCCEEDED_WITH_ORIGINAL_SOURCE_IMMEDIATE_PREDECESSOR"
            or proof.get("proofMethod") != "ORIGINAL_SOURCE_IMMEDIATE_PREDECESSOR_TRIPLEG"):
        return False
    ledger = proof.get("originalOneHopImmediateSourcePredecessorProof")
    if (not isinstance(ledger, dict) or ledger.get("status") != PROVED
            or ledger.get("allRootPredecessorAlternativesCaptured") is not True):
        return False
    probes = ledger.get("upstreamProbes")
    if not isinstance(probes, list) or not probes:
        return False
    exact = []
    for item in probes:
        if not isinstance(item, dict) or item.get("mode") != mode:
            return False
        row = item.get("originalTripLegResult")
        incoming = item.get("incomingOriginalDirectedGraphId")
        if item.get("proof") == PROVED:
            if (type(incoming) is not int or incoming <= 0
                    or item.get("originalTripLegFirstIsExactPredecessor") is not True
                    or not _original_tripleg_matches(row, final_id, [incoming, final_id])
                    or row.get("originalRouteStatus") != "SUCCEEDED"):
                return False
            exact.append(row["originalNativeTripLegDirectedGraphIds"])
        elif item.get("proof") != "NOT_VERIFIED":
            return False
    return (bool(exact)
            and ledger.get("exactOriginalOneHopProofCount") == len(exact)
            and ledger.get("firstExactOriginalNativeTripLegGraphIds") == exact[0]
            and proof.get("originalNativeTripLegDirectedGraphIds") == exact[0]
            and proof.get("originalNativeLastGraphId") == final_id)


def _valid_direct_final_proof(proof: object, final_id: int, mode: str) -> bool:
    if not isinstance(proof, dict):
        return False
    if proof.get("originalRouteStatus") == "SUCCEEDED":
        return _original_tripleg_matches(proof, final_id, [final_id])
    return _valid_original_one_hop(proof, final_id, mode)


def _unique_ids(items: list, name: str, key: str) -> set[int]:
    if not isinstance(items, list):
        raise ValueError("Missing original " + name)
    ids = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Malformed original " + name)
        value = item.get(key)
        if type(value) is not int or value <= 0:
            raise ValueError("Invalid original " + name + " GraphId")
        ids.append(value)
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate original " + name + " GraphId")
    return set(ids)


def reconcile(cut: dict, direct: dict, beyond: dict) -> dict:
    """Preserve every observation; make missing predecessor/window coverage explicit."""
    if not all(isinstance(x, dict) for x in (cut, direct, beyond)):
        raise ValueError("Missing native original source evidence")
    if cut.get("schema") != CUT_SCHEMA or cut.get("version") != 1:
        raise ValueError("Unexpected or unverified original directed cut census")
    if cut.get("sourceCutCompleteness") != CUT_SCOPE:
        raise ValueError("Unverified window-scanned original directed census scope")
    if direct.get("schema") != "roadpilot.f8-original-source-cut-last-tripleg":
        raise ValueError("Unexpected original native source-last TripLeg report")
    if beyond.get("schema") != "roadpilot.f8-original-source-beyond-cut-last-edge":
        raise ValueError("Unexpected original native beyond-cut path report")
    if any(x.get("productionPublication") != "BLOCKED" for x in (cut, direct, beyond)):
        raise ValueError("Source-only evidence may not claim to be published")
    pairs = [x.get("pairId") for x in (cut, direct, beyond)]
    if not all(isinstance(x, str) and x and x == pairs[0] for x in pairs):
        raise ValueError("Independent source evidence pair mismatch")
    if cut.get("sourceGraphFingerprints") != direct.get("sourceGraphFingerprints"):
        raise ValueError("Original source graph archive fingerprints mismatch")
    source_shas = [cut.get("originalSourceInputSHA256"),
                   direct.get("immutableSourceSHA256"),
                   beyond.get("immutableSourceSHA256")]
    if any(not isinstance(x, dict) for x in source_shas):
        raise ValueError("Missing source SHA-bound provenance")
    shared = set.intersection(*(set(x) for x in source_shas))
    mandatory = {"pair", "from-manifest", "to-manifest"}
    if not mandatory.issubset(shared):
        raise ValueError("Incomplete shared original source identities")
    for key in shared:
        vals = [x[key] for x in source_shas]
        if any(v != vals[0] or not isinstance(v, str) or
               not v.startswith("sha256:") or len(v) != 71 for v in vals):
            raise ValueError("Original source SHA mismatch: " + key)
    if not (source_shas[0].get("native-binary") ==
            source_shas[1].get("native-endpoint-binary") ==
            source_shas[2].get("native-binary")):
        raise ValueError("Original GraphReader executable identity mismatched")
    outputs = {}
    for side in SIDES:
        observed = (cut.get("directions") or {}).get(side)
        previous = (direct.get("directions") or {}).get(side)
        latter = (beyond.get("directions") or {}).get(side)
        if not all(isinstance(x, dict) for x in (observed, previous, latter)):
            raise ValueError("Original source direction absent: " + side)
        rows = observed.get("allOriginalDirectedCutObservations")
        cut_ids = _unique_ids(rows, side+" cut observation", "originalDirectedGraphId")
        if len(cut_ids) != observed.get("originalSourceDirectedCutShapeCount"):
            raise ValueError("Native cut observation count mismatch")
        if (type(observed.get("originalSourceDirectedGraphIdsAudited")) is not int or
                observed["originalSourceDirectedGraphIdsAudited"] < len(cut_ids)):
            raise ValueError("Invalid complete original source window count")
        direct_rows = previous.get("cutCandidateOriginalTripLegProof")
        direct_ids = _unique_ids(direct_rows, side+" direct final", "originalNativeSourceDirectedGraphId")
        missing_direct = direct_ids - cut_ids
        if missing_direct:
            raise ValueError("Previously proved direct original final GraphId absent from cut inventory")
        if (previous.get("originalSourceCutCandidateDirectedEdges") != len(direct_rows)
                or previous.get("noOriginalCandidateSuppression") is not True):
            raise ValueError("Original direct final inventory or preservation claim changed")
        for item in direct_rows:
            gid = item["originalNativeSourceDirectedGraphId"]
            if (item.get("originalNativeSourceCutGeometryIntersects") is not True
                    or item.get("candidateSuppressed") is not False):
                raise ValueError("Original direct cut geometry or candidate preservation changed")
            for mode in MODES:
                proof = (item.get("vehicleModes") or {}).get(mode)
                if not _valid_direct_final_proof(proof, gid, mode):
                    raise ValueError("Previously proved original TripLeg identity changed")
        beyond_rows = latter.get("beyondCutOriginalFinalEdgeProofs")
        beyond_ids = _unique_ids(beyond_rows, side+" beyond-cut final", "originalFinalDirectedGraphId")
        if direct_ids & beyond_ids:
            raise ValueError("Original final GraphId counted twice as direct and beyond-cut")
        if (latter.get("originalDirectedFinalEdgesBeyondCutIdentified") != len(beyond_rows)
                or latter.get("originalSourceCandidateSuppression") != "NONE"):
            raise ValueError("Original beyond-cut candidate inventory or preservation changed")
        predecessor_ids: set[int] = set()
        unbounded: list[int] = []
        for item in beyond_rows:
            end = item["originalFinalDirectedGraphId"]
            if (item.get("originalFinalDirectedEdgeEntirelyBeyondOriginalSource25kmCut") is not True
                    or item.get("noOriginalBranchesSuppressed") is not True
                    or item.get("anyOriginalCutCrossingPredecessorLocated") is not True):
                raise ValueError("False original beyond-cut source final or preservation claim")
            paths = item.get("originalDirectedCutCrossingPredecessorPaths")
            if not isinstance(paths, list) or not paths:
                raise ValueError("Source beyond-cut candidate has no original cut predecessor")
            bounded = item.get("completeness")
            truncations = item.get("truncations")
            if (bounded not in ("INCOMPLETE_BOUNDED",
                                "ALL_SAME_LEVEL_PREDECESSOR_BRANCHES_WITHIN_BOUND_VISITED")
                    or not isinstance(truncations, list)
                    or bool(truncations) != (bounded == "INCOMPLETE_BOUNDED")):
                raise ValueError("Invalid or concealed original predecessor traversal cap")
            if bounded == "INCOMPLETE_BOUNDED":
                unbounded.append(end)
            native_paths = {}
            for path in paths:
                if not isinstance(path, dict) or path.get("intersectsOriginalSource25kmCut") is not True:
                    raise ValueError("False original source cut predecessor claim")
                gid = path.get("originalDirectedGraphId")
                route = path.get("nativeForwardDirectedPathToFinal")
                if (type(gid) is not int or gid <= 0 or not isinstance(route, list) or
                        len(route) < 2 or route[0] != gid or route[-1] != end or
                        any(type(x) is not int or x <= 0 for x in route)
                        or len(set(route)) != len(route)):
                    raise ValueError("Invalid original directed predecessor-to-last path endpoints")
                key = (gid, tuple(route))
                if key in native_paths:
                    raise ValueError("Repeated original source predecessor path")
                native_paths[key] = route
                predecessor_ids.add(gid)
            route_report = item.get("originalSourceOriginalValhallaTripLeg")
            if not isinstance(route_report, dict):
                raise ValueError("Missing original Valhalla beyond-cut route evidence")
            witnesses = route_report.get("originalSourceCutRouteProofs")
            if (not isinstance(witnesses, list)
                    or route_report.get("originalSourceCutCrossingPathCount") != len(paths)
                    or len(witnesses) != len(paths)):
                raise ValueError("Incomplete original source predecessor route witness coverage")
            seen_witnesses: set[tuple] = set()
            successful_modes: set[str] = set()
            successful_checks = 0
            for witness in witnesses:
                if not isinstance(witness, dict):
                    raise ValueError("Malformed original Valhalla source witness")
                start = witness.get("originalDirectedCutEdge")
                ordered = witness.get("nativeForwardDirectedPathToFinal")
                if not isinstance(ordered, list):
                    raise ValueError("Missing original source witness path")
                key = (start, tuple(ordered))
                if key not in native_paths or key in seen_witnesses:
                    raise ValueError("Original source witness mismatches cut predecessor path")
                seen_witnesses.add(key)
                mode_proofs = witness.get("originalRouteModeProofs")
                if not isinstance(mode_proofs, dict) or set(mode_proofs) != set(MODES):
                    raise ValueError("Incomplete original source Valhalla witness modes")
                for mode in MODES:
                    proof = mode_proofs[mode]
                    if not isinstance(proof, dict):
                        raise ValueError("Malformed original source route witness")
                    if proof.get("sourceLastEdgeProof") == PROVED:
                        if (proof.get("originalRouteStatus") != "SUCCEEDED"
                                or proof.get("originalSourceCutPathExactTripLegSequence") is not True
                                or not _original_tripleg_matches(proof, end, ordered)
                                or proof["originalNativeTripLegDirectedGraphIds"][0] != start):
                            raise ValueError("False original Valhalla beyond-cut mode proof")
                        successful_modes.add(mode)
                        successful_checks += 1
                    elif proof.get("sourceLastEdgeProof") != "NOT_VERIFIED":
                        raise ValueError("Unrecognized original Valhalla source witness status")
            if seen_witnesses != set(native_paths):
                raise ValueError("Incomplete original source cut predecessor witness paths")
            if successful_modes != set(MODES):
                raise ValueError("Beyond-cut final has no exact original Valhalla proof for both modes")
            if (not isinstance(route_report.get("routeModeCounts"), dict)
                    or route_report["routeModeCounts"].get(PROVED, 0) != successful_checks):
                raise ValueError("Original beyond-cut route proof count mismatch")
        covered = cut_ids & (direct_ids | predecessor_ids)
        uncertain = cut_ids - covered
        outward = {r["originalDirectedGraphId"] for r in rows
                   if r.get("originalSourceBufferCutDirectedTravel") ==
                   "OUTWARD_FROM_ORIGINAL_SOURCE_BUFFER"}
        directions = {r.get("originalSourceBufferCutDirectedTravel") for r in rows}
        if None in directions or not directions.issubset({
                "OUTWARD_FROM_ORIGINAL_SOURCE_BUFFER",
                "INWARD_TOWARD_ORIGINAL_SOURCE_BUFFER",
                "BOTH_ENDPOINTS_WITHIN_BUFFER_CUT_INTERSECTION",
                "BOTH_ENDPOINTS_OUTSIDE_BUFFER_CUT_INTERSECTION"}):
            raise ValueError("Unknown original source-buffer directed cut observation")
        outputs[side] = {
            "windowCapturedOriginalSourceEdgesAudited": observed["originalSourceDirectedGraphIdsAudited"],
            "windowCapturedDirectedCutObservations": len(cut_ids),
            "provedDirectOriginalLastEdgesPresentInWindowCensus": len(direct_ids),
            "provedBeyondCutOriginalLastEdges": len(beyond_ids),
            "uniqueBeyondCutPredecessorDirectedGraphIds": len(predecessor_ids),
            "beyondCutPredecessorsMissingFromWindowScan": sorted(predecessor_ids-cut_ids),
            "beyondCutPredecessorsMissingFromWindowScanCount": len(predecessor_ids-cut_ids),
            "directOrPredecessorLinkedWindowCutGraphIds": len(covered),
            "unlinkedWindowCutGraphIds": sorted(uncertain),
            "unlinkedWindowCutGraphIdsCount": len(uncertain),
            "unlinkedOutwardWindowCutGraphIds": sorted(outward-covered),
            "unlinkedOutwardWindowCutGraphIdsCount": len(outward-covered),
            "beyondCutCandidatesWithBoundedUnresolvedBranches": sorted(unbounded),
            "physicalRoadLastOriginalGraphId": "NOT_VERIFIED",
            "noCutObservationSuppressed": True,
        }
    return {
        "schema": SCHEMA,
        "version": 1,
        "pairId": pairs[0],
        "originalGraphFingerprints": cut["sourceGraphFingerprints"],
        "windowCensusCompleteness": CUT_SCOPE,
        "completeOriginalGraphArchiveTileInventory": "NOT_VERIFIED",
        "directions": outputs,
        "missingPredecessorsAreExactNativeGraphIdsNotOSMGrouping": True,
        "allPhysicalRoadDirectionsMappedToOneFinalOriginalDirectedEdge": "NOT_VERIFIED",
        "receivingGraphCorrelation": "NOT_STARTED",
        "productionPublication": "BLOCKED",
    }


def checked(path: Path, expected: str) -> tuple[dict, str]:
    if not isinstance(expected, str) or not expected.startswith("sha256:") or len(expected) != 71:
        raise ValueError("Input SHA256 must be explicitly pinned")
    actual = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    if expected != actual:
        raise ValueError("Pinned original report checksum mismatch: "+path.name)
    return json.loads(path.read_text(encoding="utf8")), actual


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    for key in ("cut-census", "last-proof", "beyond-proof", "output"):
        ap.add_argument("--"+key, type=Path, required=True)
    for key in ("cut-census", "last-proof", "beyond-proof"):
        ap.add_argument("--expected-"+key+"-sha256", required=True)
    args = ap.parse_args()
    if args.output.exists() or args.output.is_symlink():
        raise ValueError("Refusing to overwrite immutable source-cut reconciliation")
    evidence = {}
    refs = {}
    for key in ("cut_census", "last_proof", "beyond_proof"):
        evidence[key], refs[key] = checked(
            getattr(args,key), getattr(args,"expected_"+key+"_sha256"))
    doc = reconcile(evidence["cut_census"], evidence["last_proof"], evidence["beyond_proof"])
    doc["inputReportSHA256"] = refs
    args.output.parent.mkdir(parents=True,exist_ok=True)
    stage = None
    try:
        with tempfile.NamedTemporaryFile("w",encoding="utf8",delete=False,
                                         prefix=".f8-cut-reconciliation-",dir=args.output.parent) as fd:
            stage = Path(fd.name)
            json.dump(doc,fd,indent=2,allow_nan=False)
            fd.write("\n")
        if args.output.exists() or args.output.is_symlink():
            raise ValueError("Concurrent original source-cut reconciliation")
        os.link(stage,args.output)
    finally:
        if stage is not None:
            stage.unlink(missing_ok=True)
    print("Original cut coverage reconciled; graph-archive completeness NOT_VERIFIED, "
          "one physical road / direction -> final original edge NOT_VERIFIED, release BLOCKED.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        raise SystemExit("F8_SOURCE_CUT_RECONCILE_ERROR: "+str(exc)[:350])
