#!/usr/bin/env python3
"""Reconcile immutable original-route witness pages without claiming road uniqueness.

The full graph-local census and every prioritized cut-line witness must be
represented, including failed original Valhalla routes. The small merged
report is only a proof-coverage ledger, never a connectivity sidecar.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile

from compile_native_f8_terminal_lineage_proof import SCHEMA as LEDGER_SCHEMA, digest

SCHEMA = "roadpilot.f8-original-terminal-witness-page-reconciliation"
DIRECTIONS = ("from-to", "to-from")
MODES = ("auto", "motorcycle")
MUTABLE_PER_PAGE_FIELDS = {
    "originalRouteLastEdge",
}
CONSISTENT_KEYS = (
    "pairId", "graphFingerprints", "boundaryFingerprints",
    "verified25kmBufferFingerprints", "fullNativeCensusSha256",
    "unbufferedCorePolygonProvenance", "unbufferedCorePolygonSha256",
    "originalNativeBinariesSha256", "allSourceNativeDirectedScansReconciled",
    "oneFinalEdgePerPhysicalRoadAndDirection",
    "physicalRoadEquivalenceClasses", "independentReceivingGraphDirectionalHandoff",
    "productionPublication",
)


def immutable_terminals_digest(rows: list[dict]) -> str:
    unique = set()
    h = sha256()
    for row in rows:
        gid = row.get("sourceGraphId")
        if type(gid) is not int or gid <= 0 or gid in unique:
            raise ValueError("Duplicate/invalid source-directed terminal in full page")
        unique.add(gid)
        r = {key: value for key, value in row.items()
             if key not in MUTABLE_PER_PAGE_FIELDS}
        h.update(json.dumps(r, sort_keys=True, allow_nan=False,
                            separators=(",", ":")).encode())
        h.update(b"\n")
    return "sha256:" + h.hexdigest()


def prioritized(doc: dict, band_metres: float) -> list[int]:
    rows = doc.get("allTerminals")
    if not isinstance(rows, list):
        raise ValueError("Source-complete terminal rows absent")
    eligible = [r for r in rows
                if r.get("unbufferedCoreClassification") in ("RECEIVER_CORE", "BOTH_CORES")
                and r.get("insideVerifiedPeerBuffer") is True
                and isinstance(r.get("metresToOwnVerifiedBufferOuterBoundary"), (int, float))
                and 0 <= r["metresToOwnVerifiedBufferOuterBoundary"] <= band_metres]
    eligible.sort(key=lambda r: (
        r["metresToOwnVerifiedBufferOuterBoundary"], r["sourceGraphId"]))
    return [r["sourceGraphId"] for r in eligible]


def reconcile_pages(pages: list[dict], *, band_metres: float) -> dict:
    """Validate exact page coverage for every direction/mode; no way/name grouping."""
    if not pages or not 0 < band_metres <= 1000:
        raise ValueError("Non-empty proof pages and valid witness band required")
    first = pages[0]
    if (first.get("schema") != LEDGER_SCHEMA or first.get("version") != 1
            or first.get("productionPublication") != "BLOCKED"
            or first.get("oneFinalEdgePerPhysicalRoadAndDirection") != "NOT_VERIFIED"):
        raise ValueError("Not a blocked native terminal lineage ledger")
    for page in pages:
        if page.get("schema") != LEDGER_SCHEMA or page.get("version") != 1:
            raise ValueError("Mixed or altered terminal ledger schema")
        for key in CONSISTENT_KEYS:
            if page.get(key) != first.get(key):
                raise ValueError("Mixed proof page graph/census/algorithm provenance: " + key)
        if page.get("productionPublication") != "BLOCKED":
            raise ValueError("Unexpected purported published proof page")

    all_results = {}
    for direction in DIRECTIONS:
        all_results[direction] = {}
        for mode in MODES:
            first_doc = first["directions"][direction][mode]
            canonical = immutable_terminals_digest(first_doc["allTerminals"])
            expected_ids = prioritized(first_doc, band_metres)
            if first_doc.get("prioritizedWitnessCount") != len(expected_ids):
                raise ValueError("First proof page uses different witness band")
            expected_set = set(expected_ids)
            if len(expected_set) != len(expected_ids):
                raise ValueError("Duplicate expected original directed GraphId")
            attempts = {}
            details = []
            for page in pages:
                doc = page["directions"][direction][mode]
                if immutable_terminals_digest(doc["allTerminals"]) != canonical:
                    raise ValueError("Graph-local terminal source inventory changed across pages")
                if doc.get("sourceCoverage") != "ALL_NATIVE_CENSUS_TERMINALS_RETAINED":
                    raise ValueError("Incomplete original native source terminal inventory")
                if doc.get("globalOnePhysicalRoadEdgePerDirection") != "NOT_VERIFIED":
                    raise ValueError("Unjustified global physical-road claim")
                if doc.get("allGraphLocalModeTerminalCount") != len(doc["allTerminals"]):
                    raise ValueError("Wrong original native total")
                if doc.get("prioritizedWitnessCount") != len(expected_ids):
                    raise ValueError("Different page witness universe")
                offset = doc.get("witnessPageOffset")
                size = doc.get("witnessPageSize")
                if type(offset) is not int or type(size) is not int or offset < 0 or not 0 <= size <= 24:
                    raise ValueError("Unbounded or invalid original route proof page")
                page_expected = expected_ids[offset:offset + size]
                rows = doc.get("selectedOriginalRouteWitnesses")
                if not isinstance(rows, list) or len(rows) != len(page_expected):
                    raise ValueError("Original route witness page truncated or extra")
                actual_ids = [item.get("sourceGraphId") for item in rows]
                if actual_ids != page_expected:
                    raise ValueError("Original route witnesses omit/reorder source GraphIds")
                count = 0
                terminal_by_id = {r["sourceGraphId"]: r for r in doc["allTerminals"]}
                for item in rows:
                    gid = item["sourceGraphId"]
                    if gid in attempts:
                        raise ValueError("Repeated original route witness across proof pages")
                    flag = item.get("originalLastGraphLocalEdgeMatchesTerminal")
                    status = item.get("status")
                    if type(flag) is not bool or status != (
                        "ORIGINAL_VALHALLA_LAST_EDGE_ON_THIS_ROUTE_PROVEN" if flag
                        else "ORIGINAL_VALHALLA_LAST_EDGE_NOT_PROVEN"):
                        raise ValueError("Inconsistent original native route proof status")
                    if flag and (
                        item.get("originalLastDirectedGraphId") != gid
                        or not item.get("originalGraphLocalRouteDirectedGraphIds")
                        or item["originalGraphLocalRouteDirectedGraphIds"][-1] != gid):
                        raise ValueError("Proven route lacks original matching last GraphId")
                    if terminal_by_id[gid].get("originalRouteLastEdge") != status:
                        raise ValueError("Proof page terminal evidence no longer agrees")
                    attempts[gid] = item
                    count += flag
                    details.append(item)
                if count != doc.get("originalLastEdgesProven"):
                    raise ValueError("Forged/miscounted page original Valhalla proof results")
            if set(attempts) != expected_set:
                raise ValueError("Incomplete native directed witness page coverage")
            unproven = [item for item in details
                        if not item["originalLastGraphLocalEdgeMatchesTerminal"]]
            all_results[direction][mode] = {
                "fullSourceGraphLocalModeTerminalCount": len(first_doc["allTerminals"]),
                "fullSourceNativeScanEdges": first_doc["sourceDirectedGraphIdsInNativeScan"],
                "fullTerminalDirectedGraphIdsSha256": canonical,
                "prioritizedWitnessCount": len(expected_ids),
                "originalValhallaWitnessesAttempted": len(attempts),
                "originalLastDirectedGraphIdsProven": len(attempts) - len(unproven),
                "originalRoutesNotProven": unproven,
                "fullPrioritizedWitnessPageCoverage": "PROVEN_NO_GAPS_OR_DUPLICATES",
                "allPhysicalRoadAndDirectionLineagesProven": "NOT_VERIFIED",
            }
    return {
        "schema": SCHEMA,
        "version": 1,
        "pairId": first["pairId"],
        "graphFingerprints": first["graphFingerprints"],
        "boundaryFingerprints": first["boundaryFingerprints"],
        "verified25kmBufferFingerprints": first["verified25kmBufferFingerprints"],
        "fullNativeCensusSha256": first["fullNativeCensusSha256"],
        "sourceCoreSha256": first["unbufferedCorePolygonSha256"],
        "sourceCoreStatus": first["unbufferedCorePolygonProvenance"],
        "nativeBinariesSha256": first["originalNativeBinariesSha256"],
        "witnessObservationBandMetres": band_metres,
        "directions": all_results,
        "allSourceNativeTerminalRowsRetained": True,
        "everyPrioritizedGraphLocalWitnessAttempted": True,
        "globalOneFinalPhysicalRoadEdgePerRoadAndDirection": "NOT_VERIFIED",
        "authoritativeOriginalRouteGraphIds": "PROVEN_ONLY_FOR_LISTED_SUCCESSFUL_LOCAL_LEGS",
        "crossGraphDirectedTransfer": "NOT_VERIFIED",
        "AndroidEndToEndJourney": "NOT_VERIFIED",
        "globalCandidateSuppression": "NONE",
        "productionPublication": "BLOCKED",
    }


def main() -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--page", type=Path, action="append", required=True)
    cli.add_argument("--expected-full-native-census-sha256", required=True)
    cli.add_argument("--witness-band-metres", type=float, required=True)
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    if args.output.exists() or args.output.is_symlink():
        raise ValueError("Refusing to overwrite verified immutable reconciliation")
    sources = {str(p): digest(p) for p in args.page}
    if len(sources) != len(args.page):
        raise ValueError("Same proof page submitted twice")
    if not args.expected_full_native_census_sha256.startswith("sha256:"):
        raise ValueError("Explicit source census SHA256 required")
    pages = [json.loads(p.read_text(encoding="utf-8")) for p in args.page]
    report = reconcile_pages(pages, band_metres=args.witness_band_metres)
    if report["fullNativeCensusSha256"] != args.expected_full_native_census_sha256:
        raise ValueError("Untrusted census digest in proof pages")
    if any(digest(Path(path)) != h for path, h in sources.items()):
        raise ValueError("Immutable original route page changed during reconciliation")
    report["witnessPageSha256"] = sources
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=args.output.parent,
        prefix=".f8-terminal-reconciliation-", delete=False
    ) as file:
        tmp = Path(file.name)
        json.dump(report, file, indent=2, allow_nan=False)
        file.write("\n")
    try:
        os.link(tmp, args.output)
    finally:
        tmp.unlink(missing_ok=True)
    print("Reconciled complete prioritized witness pages. Physical-road completeness"
          " and cross-graph route legality still NOT_VERIFIED.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError, IndexError) as error:
        raise SystemExit("F8_TERMINAL_PAGE_RECONCILE_ERROR: " + str(error)[:360])
