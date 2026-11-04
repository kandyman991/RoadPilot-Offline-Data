#!/usr/bin/env python3
"""Reconcile known source final TripLeg candidates with ALL original archive tiles.

This proves membership and preserves source mode/branch proof witnesses; it does
NOT prove each *physical road* has exactly one final edge, nor correlate B.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile

from census_native_f8_original_archive_tiles import SCHEMA as ARCHIVE_SCHEMA
from reconcile_native_f8_source_cut_coverage import (
    _valid_direct_final_proof, _original_tripleg_matches, PROVED, MODES,
)
from reconcile_native_f8_archive_window_coverage import unique_ids

SCHEMA = "roadpilot.f8-original-archive-known-final-candidate-membership"
SIDES = ("from-to", "to-from")


def present_in_native_archive(gid: object, tiles: dict[int, int]) -> bool:
    if type(gid) is not int or gid <= 0:
        return False
    original_tile = gid & ((1 << 25) - 1)
    index = gid >> 25
    return (original_tile in tiles and index < tiles[original_tile])


def reconcile(archive: dict, direct: dict, beyond: dict) -> dict:
    if any(not isinstance(x, dict) for x in (archive,direct,beyond)):
        raise ValueError("Missing original native source final-edge evidence")
    if (archive.get("schema") != ARCHIVE_SCHEMA or archive.get("version") != 1
            or direct.get("schema") != "roadpilot.f8-original-source-cut-last-tripleg"
            or beyond.get("schema") != "roadpilot.f8-original-source-beyond-cut-last-edge"):
        raise ValueError("Wrong original source final-edge provenance schema")
    if (archive.get("originalGraphArchiveTileInventory") !=
            "ALL_GRAPHREADER_GETTILESET_TILES_ENUMERATED"):
        raise ValueError("Missing whole ORIGINAL archive tile census")
    if any(x.get("productionPublication") != "BLOCKED" for x in (archive,direct,beyond)):
        raise ValueError("Production publication cannot be claimed by original source proofs")
    if (not archive.get("pairId")
            or archive["pairId"] != direct.get("pairId")
            or archive["pairId"] != beyond.get("pairId")):
        raise ValueError("Original source graph pair disagreement")
    if archive.get("sourceGraphFingerprints") != direct.get("sourceGraphFingerprints"):
        raise ValueError("Original source graph archive SHA fingerprints mismatch")
    source = archive.get("immutableOriginalSourceSHA256")
    other = direct.get("immutableSourceSHA256")
    final = beyond.get("immutableSourceSHA256")
    if any(not isinstance(x, dict) for x in (source,other,final)):
        raise ValueError("Unpinned original graph source manifests")
    for name in ("pair","from-manifest","to-manifest"):
        if not (source.get(name) == other.get(name) == final.get(name)):
            raise ValueError("Original source final candidate manifest SHA differs")
    for name in ("from-buffer","to-buffer"):
        if source.get(name) != final.get(name):
            raise ValueError("Original source final boundary SHA differs")
    out = {}
    for side in SIDES:
        side_archive = (archive.get("directions") or {}).get(side)
        side_direct = (direct.get("directions") or {}).get(side)
        side_beyond = (beyond.get("directions") or {}).get(side)
        if any(not isinstance(x, dict) for x in (side_archive,side_direct,side_beyond)):
            raise ValueError("Missing original graph source side")
        native_tiles = {}
        for row in side_archive.get("originalArchiveTiles",[]):
            if not isinstance(row,dict):
                raise ValueError("Malformed original source graph tile")
            base, count = row.get("tileGraphId"),row.get("originalDirectedCount")
            if (type(base) is not int or base in native_tiles
                    or type(count) is not int or count < 0 or count >= (1<<21)):
                raise ValueError("Invalid original source archive tile range")
            native_tiles[base] = count
        if len(native_tiles) != side_archive.get("archiveTileCount"):
            raise ValueError("Missing original archive tile in final-edge review")
        cut_ids = unique_ids(side_archive.get("allOriginalDirectedCutObservations"),
                             "originalDirectedGraphId")
        if len(cut_ids) != side_archive.get("originalDirectedCutShapeCount"):
            raise ValueError("Source cut directed identity count changed")
        direct_rows = side_direct.get("cutCandidateOriginalTripLegProof")
        beyond_rows = side_beyond.get("beyondCutOriginalFinalEdgeProofs")
        if not isinstance(direct_rows,list) or not isinstance(beyond_rows,list):
            raise ValueError("Missing original final-edge candidate inventory")
        direct_ids = unique_ids(direct_rows,"originalNativeSourceDirectedGraphId")
        beyond_ids = unique_ids(beyond_rows,"originalFinalDirectedGraphId")
        if direct_ids & beyond_ids:
            raise ValueError("Original source final directed ID duplicated across classes")
        if not direct_ids.issubset(cut_ids):
            raise ValueError("Direct source final candidate absent from full cut inventory")
        if beyond_ids & cut_ids:
            raise ValueError("Claimed beyond-cut final original directed edge intersects cut")
        zero_length = unique_ids(
            side_archive.get("unresolvedOriginalNativeZeroLengthGeometries"),
            "originalDirectedGraphId")
        if (len(zero_length) != side_archive.get("unresolvedOriginalNativeZeroLengthGeometryCount")
                or (direct_ids | beyond_ids) & zero_length):
            raise ValueError("Original final edge must not be missing/zero-length geometry")
        if not all(present_in_native_archive(gid,native_tiles) for gid in direct_ids|beyond_ids):
            raise ValueError("Original source final GraphId absent from native archive")
        for row in direct_rows:
            gid = row["originalNativeSourceDirectedGraphId"]
            if row.get("candidateSuppressed") is not False:
                raise ValueError("Original source direct final candidate suppressed")
            for mode in MODES:
                if not _valid_direct_final_proof(
                    (row.get("vehicleModes") or {}).get(mode),gid,mode):
                    raise ValueError("Original final edge route mode proof invalid")
        predecessors = set()
        paths_count = 0
        route_confirmations = 0
        for row in beyond_rows:
            gid = row["originalFinalDirectedGraphId"]
            if (row.get("originalFinalDirectedEdgeEntirelyBeyondOriginalSource25kmCut") is not True
                    or row.get("noOriginalBranchesSuppressed") is not True):
                raise ValueError("Original beyond-cut final branch suppression")
            paths = row.get("originalDirectedCutCrossingPredecessorPaths")
            route = (row.get("originalSourceOriginalValhallaTripLeg") or {}).get(
                "originalSourceCutRouteProofs")
            if (not isinstance(paths,list) or not paths
                    or not isinstance(route,list) or len(paths)!=len(route)):
                raise ValueError("Original source beyond-cut predecessor coverage incomplete")
            mode_success = set()
            expected_paths = set()
            for p in paths:
                pred, ordered = p.get("originalDirectedGraphId"),p.get(
                    "nativeForwardDirectedPathToFinal")
                if (p.get("intersectsOriginalSource25kmCut") is not True
                        or type(pred) is not int or pred not in cut_ids
                        or not isinstance(ordered,list) or len(ordered) < 2
                        or ordered[0] != pred or ordered[-1] != gid
                        or not all(present_in_native_archive(x,native_tiles) for x in ordered)):
                    raise ValueError("Original beyond-cut predecessor chain missing from archive")
                path = tuple(ordered)
                if path in expected_paths:
                    raise ValueError("Duplicated original native source predecessor branch")
                expected_paths.add(path)
                predecessors.add(pred)
                paths_count += 1
            actual_paths = set()
            for witness in route:
                path = witness.get("nativeForwardDirectedPathToFinal")
                if (not isinstance(path,list) or tuple(path) not in expected_paths
                        or tuple(path) in actual_paths
                        or witness.get("originalDirectedCutEdge") != path[0]):
                    raise ValueError("Original beyond-cut Valhalla route witness path changed")
                actual_paths.add(tuple(path))
                per_mode = witness.get("originalRouteModeProofs")
                if not isinstance(per_mode,dict) or set(per_mode) != set(MODES):
                    raise ValueError("Original final candidate mode witness missing")
                for mode in MODES:
                    proof = per_mode[mode]
                    if not isinstance(proof,dict):
                        raise ValueError("Malformed original candidate mode witness")
                    if proof.get("sourceLastEdgeProof") == PROVED:
                        if (proof.get("originalRouteStatus") != "SUCCEEDED"
                                or proof.get("originalSourceCutPathExactTripLegSequence") is not True
                                or not _original_tripleg_matches(proof,gid,path)):
                            raise ValueError("Original Valhalla TripLeg final GraphId/branch changed")
                        mode_success.add(mode)
                        route_confirmations += 1
                    elif proof.get("sourceLastEdgeProof") != "NOT_VERIFIED":
                        raise ValueError("Unrecognized original source candidate witness mode")
            if actual_paths != expected_paths or mode_success != set(MODES):
                raise ValueError("Original last edge lacks all-mode exact predecessor provenance")
        out[side] = {
            "originalDirectFinalGraphIdsAtCut": sorted(direct_ids),
            "originalDirectFinalCandidateCount": len(direct_ids),
            "originalBeyondCutFinalGraphIdsInArchive": sorted(beyond_ids),
            "originalBeyondCutFinalCandidateCount": len(beyond_ids),
            "allPreviouslyProvedFinalDirectedGraphIdsPresentInOriginalArchive": (
                len(direct_ids)+len(beyond_ids)),
            "allBeyondCutOriginalPredecessorRoutes": paths_count,
            "distinctBeyondCutOriginalCutPredecessorGraphIds": sorted(predecessors),
            "valhallaExactBeyondCutRouteModeWitnesses": route_confirmations,
            "globalPhysicalRoadDirectionUniqueness": "NOT_VERIFIED",
            "noRoadBranchSuppressed": True,
        }
    return {
        "schema": SCHEMA,"version":1,"pairId":archive["pairId"],
        "directions":out,
        "originalArchiveMembershipIsNotPhysicalRoadEquivalence":True,
        "allSourcePhysicalRoadFinalEdges":"NOT_VERIFIED",
        "receivingGraphCorrelation":"NOT_STARTED",
        "productionPublication":"BLOCKED",
    }


def checked(path: Path, expected: str) -> dict:
    if not isinstance(expected,str) or len(expected)!=71 or not expected.startswith("sha256:"):
        raise ValueError("Original source proof SHA pin missing")
    if "sha256:"+hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
        raise ValueError("Original immutable native candidate input SHA changed")
    return json.loads(path.read_text(encoding="utf8"))


def main() -> int:
    ap=argparse.ArgumentParser(description=__doc__)
    for x in ("archive","direct","beyond","output"):
        ap.add_argument("--"+x,type=Path,required=True)
    for x in ("archive","direct","beyond"):
        ap.add_argument("--expected-"+x+"-sha256",required=True)
    a=ap.parse_args()
    if a.output.exists() or a.output.is_symlink():
        raise ValueError("Refusing to overwrite source candidate membership proof")
    docs={name:checked(getattr(a,name),getattr(a,"expected_"+name+"_sha256"))
          for name in ("archive","direct","beyond")}
    out=reconcile(docs["archive"],docs["direct"],docs["beyond"])
    out["inputSourceEvidenceSHA256"]={name:getattr(a,"expected_"+name+"_sha256")
                                      for name in ("archive","direct","beyond")}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    stage=None
    try:
        with tempfile.NamedTemporaryFile("w",encoding="utf8",delete=False,
                                         prefix=".f8-source-final-membership-",
                                         dir=a.output.parent) as fd:
            stage=Path(fd.name)
            json.dump(out,fd,indent=2,allow_nan=False)
            fd.write("\n")
        if a.output.exists() or a.output.is_symlink():
            raise ValueError("Concurrent original candidate evidence publication")
        os.link(stage,a.output)
    finally:
        if stage:stage.unlink(missing_ok=True)
    for side,row in out["directions"].items():
        print(side,"known original final candidates",
              row["allPreviouslyProvedFinalDirectedGraphIdsPresentInOriginalArchive"],
              "beyond-cut predecessor paths",row["allBeyondCutOriginalPredecessorRoutes"])
    return 0


if __name__=="__main__":
    try: raise SystemExit(main())
    except (ValueError,TypeError,OSError,KeyError,IndexError) as exc:
        raise SystemExit("F8_ORIGINAL_FINAL_MEMBERSHIP_ERROR: "+str(exc)[:400])
