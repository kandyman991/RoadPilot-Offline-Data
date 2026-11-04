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
        for item in direct_rows:
            gid = item["originalNativeSourceDirectedGraphId"]
            for mode in MODES:
                m = (item.get("vehicleModes") or {}).get(mode)
                if (not isinstance(m, dict) or
                        m.get("sourceLastEdgeProof") !=
                        "ORIGINAL_SOURCE_LAST_DIRECTED_TRIPLEG_GRAPHID_MATCHED" or
                        m.get("originalNativeLastGraphId") != gid):
                    raise ValueError("Previously proved original TripLeg identity changed")
        beyond_rows = latter.get("beyondCutOriginalFinalEdgeProofs")
        beyond_ids = _unique_ids(beyond_rows, side+" beyond-cut final", "originalFinalDirectedGraphId")
        if direct_ids & beyond_ids:
            raise ValueError("Original final GraphId counted twice as direct and beyond-cut")
        predecessor_ids: set[int] = set()
        unbounded: list[int] = []
        for item in beyond_rows:
            end = item["originalFinalDirectedGraphId"]
            if item.get("originalFinalDirectedEdgeEntirelyBeyondOriginalSource25kmCut") is not True:
                raise ValueError("False original beyond-cut source final claim")
            paths = item.get("originalDirectedCutCrossingPredecessorPaths")
            if not isinstance(paths, list) or not paths:
                raise ValueError("Source beyond-cut candidate has no original cut predecessor")
            if item.get("completeness") != "ALL_SAME_LEVEL_PREDECESSOR_BRANCHES_WITHIN_BOUND_VISITED":
                unbounded.append(end)
            for p in paths:
                if not isinstance(p, dict) or p.get("intersectsOriginalSource25kmCut") is not True:
                    raise ValueError("False original source cut predecessor claim")
                gid = p.get("originalDirectedGraphId")
                route = p.get("nativeForwardDirectedPathToFinal")
                if (type(gid) is not int or gid <= 0 or not isinstance(route, list) or
                        len(route) < 2 or route[0] != gid or route[-1] != end or
                        any(type(x) is not int or x <= 0 for x in route)):
                    raise ValueError("Invalid original directed predecessor-to-last path endpoints")
                predecessor_ids.add(gid)
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
