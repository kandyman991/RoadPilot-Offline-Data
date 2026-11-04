#!/usr/bin/env python3
"""Cross-check complete ORIGINAL GraphReader tile census vs old window capture.

Window scan omissions must remain evidence, never be interpreted as absent
roads. Validate the exact 34 known missing predecessor GraphIds from original
route proofs, preserve all newly found cut IDs and modes. No B correlation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile

from census_native_f8_original_archive_tiles import SCHEMA as ARCHIVE_SCHEMA

SCHEMA = "roadpilot.f8-original-archive-versus-window-cut-coverage"
SIDES = ("from-to", "to-from")


def unique_ids(items: object, key: str) -> set[int]:
    if not isinstance(items, list):
        raise ValueError("Original source directed inventory absent")
    result = set()
    for row in items:
        if not isinstance(row, dict):
            raise ValueError("Invalid original source observation")
        gid = row.get(key)
        if type(gid) is not int or gid <= 0 or gid in result:
            raise ValueError("Duplicate/invalid original source GraphId")
        result.add(gid)
    return result


def reconcile(archive: dict, window: dict, previous: dict) -> dict:
    if any(not isinstance(x, dict) for x in (archive, window, previous)):
        raise ValueError("Missing original source evidence")
    if archive.get("schema") != ARCHIVE_SCHEMA or archive.get("version") != 1:
        raise ValueError("Invalid full original archive GraphReader evidence schema")
    if window.get("schema") != "roadpilot.f8-original-all-source-native-directed-cut-census":
        raise ValueError("Invalid original source window cut evidence schema")
    if previous.get("schema") != "roadpilot.f8-source-cut-window-coverage-reconciliation":
        raise ValueError("Invalid original source cut coverage baseline schema")
    if (archive.get("originalGraphArchiveTileInventory") !=
            "ALL_GRAPHREADER_GETTILESET_TILES_ENUMERATED"):
        raise ValueError("Unverified full original tile enumeration")
    if any(x.get("productionPublication") != "BLOCKED" for x in (archive, window, previous)):
        raise ValueError("Prior original source proof illegally marked publishable")
    if (not archive.get("pairId") or archive["pairId"] != window.get("pairId")
            or archive["pairId"] != previous.get("pairId")):
        raise ValueError("Original source pair fingerprint mismatch")
    if (archive.get("sourceGraphFingerprints") != window.get("sourceGraphFingerprints")
            or archive.get("sourceGraphFingerprints") != previous.get("originalGraphFingerprints")):
        raise ValueError("Original source graph archive fingerprints mismatch")
    hashes = archive.get("immutableOriginalSourceSHA256")
    old_hashes = window.get("originalSourceInputSHA256")
    if (not isinstance(hashes, dict) or not isinstance(old_hashes, dict) or
            any(hashes.get(x) != old_hashes.get(x) for x in (
                "pair", "from-manifest", "to-manifest",
                "from-buffer", "to-buffer"))):
        raise ValueError("Original source manifest/25km buffer provenance mismatch")
    outputs = {}
    for side in SIDES:
        a = (archive.get("directions") or {}).get(side)
        w = (window.get("directions") or {}).get(side)
        p = (previous.get("directions") or {}).get(side)
        if any(not isinstance(x, dict) for x in (a, w, p)):
            raise ValueError("Original source direction missing")
        tiles = a.get("originalArchiveTiles")
        if not isinstance(tiles, list) or len(tiles) != a.get("archiveTileCount") or not tiles:
            raise ValueError("Original archive tile ledger incomplete")
        seen_tiles = set()
        total = 0
        for row in tiles:
            if not isinstance(row, dict):
                raise ValueError("Malformed original tile")
            base, count = row.get("tileGraphId"), row.get("originalDirectedCount")
            if (type(base) is not int or base in seen_tiles
                    or type(count) is not int or count < 0):
                raise ValueError("Repeated/malformed original archive tile")
            seen_tiles.add(base)
            total += count
        if total != a.get("allOriginalDirectedEdgesEnumerated"):
            raise ValueError("Full original GraphReader tile edge count mismatch")
        new_ids = unique_ids(a.get("allOriginalDirectedCutObservations"),
                             "originalDirectedGraphId")
        old_ids = unique_ids(w.get("allOriginalDirectedCutObservations"),
                             "originalDirectedGraphId")
        if len(new_ids) != a.get("originalDirectedCutShapeCount"):
            raise ValueError("Incomplete native source archive cut list")
        if len(old_ids) != w.get("originalSourceDirectedCutShapeCount"):
            raise ValueError("Incomplete native original overlap window cut list")
        if a.get("noSourceDirectedRoadSuppressedByNameWayOrMode") is not True:
            raise ValueError("Original source road suppression detected")
        if (a.get("physicalRoadDirectionFinalEdge") != "NOT_VERIFIED"
                or a.get("crossGraphMatching") != "NOT_STARTED"):
            raise ValueError("Full archive cut observations falsely claim physical-road proof")
        if not old_ids.issubset(new_ids):
            raise ValueError("Known original source window cut GraphIds absent from complete archive")
        previously_absent = p.get("beyondCutPredecessorsMissingFromWindowScan")
        if (not isinstance(previously_absent, list)
                or any(type(x) is not int or x <= 0 for x in previously_absent)
                or len(set(previously_absent)) != len(previously_absent)
                or set(previously_absent) & old_ids):
            raise ValueError("Previously missing source cut predecessor inventory invalid")
        recovered = set(previously_absent) & new_ids
        unresolved_prior = set(previously_absent) - new_ids
        # Physical source coverage is not certified while a known original
        # native cut-crossing predecessor remains missing from this inventory.
        if unresolved_prior:
            raise ValueError("Known original native cut predecessor still missing from archive cut census")
        nonspatial = unique_ids(a.get("unresolvedOriginalNativeZeroLengthGeometries"),
                               "originalDirectedGraphId")
        if len(nonspatial) != a.get("unresolvedOriginalNativeZeroLengthGeometryCount"):
            raise ValueError("Native nonspatial source IDs omitted")
        if nonspatial & new_ids:
            raise ValueError("Zero-length GraphId incorrectly claimed source cut geometry")
        outputs[side] = {
            "allOriginalArchiveTilesEnumerated": len(tiles),
            "allOriginalArchiveDirectedEdgeIndicesEnumerated": total,
            "originalGeometryBoundaryEnvelopeCandidates": a.get(
                "originalGeometryBoundaryEnvelopeCandidates"),
            "allNativeOriginalCutDirectedObservations": len(new_ids),
            "previousWindowOriginalCutObservations": len(old_ids),
            "newCutDirectedGraphIdsNotInWindow": sorted(new_ids-old_ids),
            "newCutDirectedGraphIdsNotInWindowCount": len(new_ids-old_ids),
            "originalPreviouslyAbsentCutPredecessorsRecovered": sorted(recovered),
            "originalPreviouslyAbsentCutPredecessorsRecoveredCount": len(recovered),
            "unresolvedZeroLengthOriginalNativeGraphIds": sorted(nonspatial),
            "unresolvedZeroLengthOriginalNativeGraphIdCount": len(nonspatial),
            "physicalRoadDirectionToOneFinalOriginalGraphId": "NOT_VERIFIED",
            "noSourceCandidateSuppression": True,
        }
    return {
        "schema": SCHEMA,
        "version": 1,
        "pairId": archive["pairId"],
        "sourceGraphFingerprints": archive["sourceGraphFingerprints"],
        "directions": outputs,
        "previousWindowCoverageGapsReconciledWithoutWayOrLocationGrouping": True,
        "allSourcePhysicalRoadsMappedToOneOriginalFinalGraphId": "NOT_VERIFIED",
        "receivingGraphCorrelation": "NOT_STARTED",
        "productionPublication": "BLOCKED",
    }


def checked(path: Path, expected: str) -> dict:
    if (not isinstance(expected, str) or len(expected) != 71
            or not expected.startswith("sha256:")):
        raise ValueError("Original evidence must have SHA256 pin")
    actual = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    if expected != actual:
        raise ValueError("Immutable original source evidence SHA mismatch")
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ("archive", "window", "previous", "output"):
        ap.add_argument("--"+name, type=Path, required=True)
    for name in ("archive", "window", "previous"):
        ap.add_argument("--expected-"+name+"-sha256", required=True)
    args=ap.parse_args()
    if args.output.exists() or args.output.is_symlink():
        raise ValueError("Refuse to overwrite immutable original archive gap analysis")
    reports={name:checked(getattr(args,name),
                          getattr(args,"expected_"+name+"_sha256"))
             for name in ("archive","window","previous")}
    result=reconcile(reports["archive"],reports["window"],reports["previous"])
    result["inputOriginalEvidenceSHA256"]={
        name:getattr(args,"expected_"+name+"_sha256")
        for name in ("archive","window","previous")}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    stage=None
    try:
        with tempfile.NamedTemporaryFile("w",encoding="utf-8",delete=False,
                                         prefix=".f8-archive-gaps-",
                                         dir=args.output.parent) as fd:
            stage=Path(fd.name)
            json.dump(result,fd,indent=2,allow_nan=False)
            fd.write("\n")
        if args.output.exists() or args.output.is_symlink():
            raise ValueError("Concurrent immutable original archive gap proof")
        os.link(stage,args.output)
    finally:
        if stage:stage.unlink(missing_ok=True)
    for side, data in result["directions"].items():
        print(side, "full original directed",data["allOriginalArchiveDirectedEdgeIndicesEnumerated"],
              "new cut ids",data["newCutDirectedGraphIdsNotInWindowCount"],
              "old missing predecessors recovered",
              data["originalPreviouslyAbsentCutPredecessorsRecoveredCount"])
    return 0


if __name__=="__main__":
    try:raise SystemExit(main())
    except (OSError,TypeError,ValueError,KeyError,IndexError) as exc:
        raise SystemExit("F8_ARCHIVE_SOURCE_GAP_ERROR: "+str(exc)[:400])
