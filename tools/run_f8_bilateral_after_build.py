#!/usr/bin/env python3
"""Automatic F8 bilateral final-edge stage AFTER successful regional builds.

Triggered by the Graph Studio build queue, not an old GPS-proposal engine.
Only retained, SHA-verified graph packages and genuinely reciprocal
cross-boundary fingerprints can form a pair. The old broader F8 discovery
/portal-matrix engine is NEVER called.

If an independent original A-LAST / B-FIRST directed-edge ledger matching the
exact pair is retained, validate every graph-local source final and every
distinct receiving option, then derive an immutable VERIFIED-ONLY TEST cache.
This does not magically discover all source-final edges: if that native evidence
is missing, the automatic stage records an explicit pending state. No partial
catalog is marked production-ready, silently published, or substituted into
RoadPilot's installed production data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from build_connectivity_pair_manifest import build_pair, load_object, boundary_fingerprints
from emit_f8_verified_android_test_catalog import make_partial_cache
from census_f8_original_source_after_build import original_source_census

SOURCE_SCHEMA = "roadpilot.f8-final-directed-connections"
RESULT_SCHEMA = "roadpilot.f8-auto-bilateral-after-build"
MAX_RETAINED_MANIFESTS = 400
MAX_SOURCE_LEDGER_BYTES = 30_000_000


def sha256(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise ValueError("F8 source is absent, or is an unexpected symlink")
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return "sha256:" + h.hexdigest()


def safe_component(token: str) -> bool:
    return (bool(token) and len(token) <= 120
            and all(c.isalnum() or c in "_-." for c in token)
            and token not in (".", ".."))


def immutable_json(path: Path, document: dict, *, compact: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(document, sort_keys=not compact,
                          indent=None if compact else 2,
                          separators=(",", ":") if compact else None,
                          ensure_ascii=True, allow_nan=False) + "\n").encode()
    if compact and len(encoded) > 3_000_000:
        raise ValueError("Android verified-only F8 test cache exceeds native parser size cap")
    if path.exists() or path.is_symlink():
        if path.is_symlink() or path.read_bytes() != encoded:
            raise ValueError("Existing F8 immutable evidence differs: " + str(path))
        return
    with tempfile.NamedTemporaryFile("wb", delete=False, dir=path.parent,
                                     prefix=".f8-pair-") as fd:
        temp = Path(fd.name)
        fd.write(encoded)
    try:
        try:
            os.link(temp, path)
        except FileExistsError:
            if path.is_symlink() or path.read_bytes() != encoded:
                raise ValueError("Concurrent F8 proof differs: " + str(path))
    finally:
        temp.unlink(missing_ok=True)


def listed_manifests(builds_root: Path) -> list[tuple[Path, dict, dict]]:
    """A bounded inventory of retained *validated* regional build artifacts.

    Never match geographically adjacent regions just by names or coordinates.
    Source+peer reciprocal boundary fingerprints are required below.
    """
    candidates = sorted(builds_root.glob("*/*-manifest.json"))
    if len(candidates) > MAX_RETAINED_MANIFESTS:
        raise ValueError("Too many retained routing manifests for bounded F8 pairing")
    result = []
    for file in candidates:
        if file.is_symlink():
            raise ValueError("Unexpected symlinked retained routing manifest")
        m = load_object(file)
        if (m.get("schema") != "roadpilot-routing-pack"
                or m.get("schemaVersion") != 1):
            continue
        region = m.get("regionId")
        version = m.get("packageVersion")
        source = m.get("source")
        if (not isinstance(region, str) or not safe_component(region)
                or not isinstance(version, str) or not safe_component(version)
                or file.parent.name != region
                or not isinstance(source, dict)
                or type(source.get("borderBufferKm")) not in (int, float)
                or source["borderBufferKm"] < 25.0):
            raise ValueError("Malformed 25-km original regional build manifest")
        artifact = m.get("artifact") or {}
        graphfile = artifact.get("fileName")
        if (not isinstance(graphfile, str) or not safe_component(graphfile)
                or not isinstance(m.get("graphFingerprint"), str)
                or not m["graphFingerprint"].startswith("sha256:")
                or len(m["graphFingerprint"]) != 71
                or not (file.parent / graphfile).is_file()
                or (file.parent / graphfile).is_symlink()):
            raise ValueError("Retained original graph package is absent or invalid")
        index = m.get("graphIndex") or {}
        index_name = index.get("fileName")
        if not isinstance(index_name, str) or not safe_component(index_name):
            raise ValueError("Retained graph index path invalid")
        index_file = file.parent / index_name
        if index_file.is_symlink() or not index_file.is_file():
            raise ValueError("Missing original graph index")
        if sha256(index_file)[7:] != index.get("sha256"):
            raise ValueError("Retained graph index SHA-256 changed")
        idx = load_object(index_file)
        if idx.get("schema") != "roadpilot-graph-index":
            raise ValueError("Invalid original graph index schema")
        result.append((file, m, boundary_fingerprints(idx, str(file))))
    return result


def select_compatible_pairs(
    manifests: list[tuple[Path, dict, dict]],
    changed: set[tuple[str, str]]
) -> list[tuple[Path, Path, dict]]:
    """Only reciprocal original-polygon neighboring pairs, deterministic order.

    Prefer the most recent retained peer build, but never pair two versions
    just because their region names are in the same build queue. GraphSHA and
    boundary SHA are part of every output key. Bidirectional travel remains
    retained in the original ledger, not reduced to a one-way connection.
    """
    available = {(m["regionId"], m["packageVersion"]) for _, m, _ in manifests}
    if not changed.issubset(available):
        raise ValueError("Build queue referenced missing validated region/version")
    selected: dict[str, tuple[Path, Path, dict]] = {}
    for current_path, current, current_boundaries in manifests:
        if (current["regionId"], current["packageVersion"]) not in changed:
            continue
        current_region = current["regionId"]
        current_source = current["source"]["primaryGeofabrikId"]
        for peer_path, peer, peer_boundaries in manifests:
            if peer["regionId"] == current_region:
                continue
            peer_source = peer["source"]["primaryGeofabrikId"]
            one = current_boundaries.get(peer_source)
            two = peer_boundaries.get(current_source)
            if not one and not two:
                continue
            if not one or not two:
                # One-way declared nominal boundary data MUST NOT be treated
                # as a complete physical A/B road pairing.
                raise ValueError(
                    "Only one original region graph index declares a reciprocal "
                    f"F8 buffer overlap: {current_region}, {peer['regionId']}")
            # reverse-lexical canonical order preserves historical Italy NE
            # -> Austria evidence identity, and is independent of build order.
            a, b = sorted((current_path, peer_path),
                          key=lambda p: p.parent.name, reverse=True)
            pair = build_pair(a, b)
            # A rebuilt graph can have more than one retained original peer
            # version. Preserve *every* distinct A/B graph+boundary identity,
            # not just the newest neighbor and not just one first-success pair.
            selected[pair_fingerprint_key(pair)] = (a,b,pair)
    if len(selected) > 400:
        raise ValueError("Too many exact original graph/boundary pairs")
    return sorted(selected.values(),
                  key=lambda row:(row[2]["fromRegionId"],row[2]["toRegionId"],
                                  row[2]["fromGraphFingerprint"],row[2]["toGraphFingerprint"]))


def pair_fingerprint_key(pair: dict) -> str:
    """Directory identity covers *both* original archives and boundary SHAs."""
    fields = [
        pair["fromRegionId"],pair["toRegionId"],
        pair["fromGraphFingerprint"],pair["toGraphFingerprint"],
        pair["fromBoundaryFingerprint"],pair["toBoundaryFingerprint"],
    ]
    value = "\n".join(fields).encode()
    return hashlib.sha256(value).hexdigest()


def find_best_native_ledger(
    evidence_root: Path, pair: dict
) -> tuple[Path, dict, str] | None:
    """Read only bounded, SHA-bound *full* native ledgers, never test caches.

    Multiple compatible versions must be monotonic supersets (including
    distinct receiver branches); otherwise refuse to choose the most
    successful one and suppress a legitimate road/direction or branch.
    """
    if not evidence_root.is_dir():
        return None
    paths = sorted(evidence_root.glob("*/*f8*json"))
    if len(paths) > 250:
        raise ValueError("Too many retained independent original F8 ledgers")
    # The source ledger's original pair SHA must refer to a retained native
    # source-proof pair manifest containing the SAME graph and BOTH boundary
    # fingerprints. Comparing only regional IDs or source graph archive SHA
    # would admit previous evidence for a different 25-km seam.
    workspace = evidence_root.parent.parent
    parent_pair_files = sorted(
        list((workspace/"f8-native"/pair["pairId"]).glob("*/pair.json"))
        + list((workspace/"diagnostics").glob("*/pair.json")))
    if len(parent_pair_files) > 250:
        raise ValueError("Too many retained original F8 source-pair manifests")
    verified_pair_hashes = {
        sha256(file)
        for file in parent_pair_files
        if file.is_file() and not file.is_symlink()
        and file.stat().st_size < 100_000
        and load_object(file) == pair
    }
    candidates = []
    for file in paths:
        if file.is_symlink() or not file.is_file() or file.stat().st_size > MAX_SOURCE_LEDGER_BYTES:
            continue
        try:
            value = json.loads(file.read_text())
        except (ValueError, UnicodeError):
            continue
        if (value.get("schema") != SOURCE_SCHEMA
                or value.get("pairId") != pair["pairId"]
                or value.get("graphFingerprints") != {
                    "from":pair["fromGraphFingerprint"],
                    "to":pair["toGraphFingerprint"]}
                or value.get("consumerCacheScope") is not None
                or not value.get("originalSourceFinalTopologyInputSHA256")
                or not value.get("originalReceivingFullArchiveCensus")
                or (value.get("originalImmutableInputSHA256") or {}).get("pair")
                   not in verified_pair_hashes):
            # Earlier raw stages, Android consumer caches and SHA-stale
            # original pair/buffer evidence are NOT eligible.
            continue
        if (value.get("sourceDiscoveryComplete") is not False
                or value.get("productionPublication") != "BLOCKED"
                or value.get("physicalRoadPerDirectionGlobalUniqueness")
                   != "NOT_VERIFIED"
                or not value.get("unresolvedSourceFinalEdges")):
            raise ValueError("Retained F8 ledger falsely claims a completed inventory")
        # The existing independent native last / receiving first proof checker.
        make_partial_cache(value, sha256(file)[7:])
        identities = {
            (c["sourceRegionId"], c["sourceFinalDirectedGraphId"],
             o["receiverFirstDirectedGraphId"], mode)
            for c in value["connections"] for o in c["receiverOptions"]
            for mode in o["travelModes"]}
        for c in value["connections"]:
            key=(c["sourceRegionId"],c["receiverRegionId"])
            if key not in (
                (pair["fromRegionId"],pair["toRegionId"]),
                (pair["toRegionId"],pair["fromRegionId"])):
                raise ValueError("Original F8 ledger contains an unrelated region direction")
            gid=c["sourceFinalDirectedGraphId"]
            for mode in c["sourceValhallaProvedModes"]:
                proof=(c.get("originalSourceValhallaTripLeg") or {}).get(mode) or {}
                route=proof.get("originalNativeTripLegDirectedGraphIds") or []
                direct = (
                    proof.get("verified") is True
                    and proof.get("originalNativeLastGraphId") == gid
                    and bool(route) and route[-1] == gid
                    and type(proof.get("startSnapMeters")) in (float,int)
                    and type(proof.get("endSnapMeters")) in (float,int)
                    and 0 <= proof["startSnapMeters"] <= 1.0
                    and 0 <= proof["endSnapMeters"] <= 1.0)
                # Earlier independently reviewed source-final ledgers retain
                # their exact A-LAST proof by pinned parent SHA rather than
                # repeating the large original TripLeg in every derived row.
                # The status alone is NOT a proof; require the original SHA
                # parent chain as well as the exact native-terminal check
                # performed by make_partial_cache above.
                prior = (
                    proof.get("verified") is True
                    and proof.get("status") == "PREVIOUS_SHA_BOUND_EXACT_A_LAST"
                    and bool(value.get("forwardSourceParentEvidenceSHA256"))
                    and bool(value.get("originalImmutableInputSHA256"))
                )
                inherited = (
                    not proof
                    and bool(value.get("originalSourceFinalTopologyInputSHA256"))
                    and bool(value.get("forwardSourceParentEvidenceSHA256"))
                    and bool(value.get("originalImmutableInputSHA256"))
                )
                # Some prior source candidates have their original A-LAST
                # evidence only in the independent parent ledgers, not copied
                # into this derived row. Do not certify or re-prove A-LAST from
                # that placeholder: retain it only as explicitly incomplete,
                # SHA-bound partial evidence, never a production output.
                if not direct and not prior and not inherited:
                    raise ValueError("Retained source lacks original A-LAST TripLeg provenance")
        candidates.append((file,value,sha256(file),identities))
    if not candidates:
        return None
    candidates.sort(key=lambda c:(len(c[3]),len(c[1]["connections"])),reverse=True)
    first = candidates[0]
    for other in candidates[1:]:
        if not other[3].issubset(first[3]):
            raise ValueError("Conflicting original F8 source/receiver proof ledgers; "
                             "cannot auto-select and suppress distinct source modes or branches")
    return first[0],first[1],first[2]


def verify_pair_archives(
    a_manifest: Path, b_manifest: Path, pair: dict
) -> None:
    for key, path in (("from",a_manifest),("to",b_manifest)):
        manifest = load_object(path)
        graph = path.parent / manifest["artifact"]["fileName"]
        if sha256(graph) != pair[key+"GraphFingerprint"]:
            raise ValueError("Original graph archive changed after manifest validation")


def build_automatic_pair_receipt(
    workspace: Path, a_manifest: Path, b_manifest: Path, pair: dict
) -> dict:
    """Immutable automatic stage; partial proof never becomes production-ready."""
    dest=(workspace/"f8-production"/"auto-pairs"/pair["pairId"]/
          pair_fingerprint_key(pair))
    # Verify both immutable ORIGINAL graph tarballs before running any native
    # process. No old region-index / OSM-way fingerprint may replace this.
    verify_pair_archives(a_manifest,b_manifest,pair)
    immutable_json(dest/"pair.json",pair)

    # Actual from-scratch ORIGINAL source GraphReader GetTileSet census in both
    # directions. The old 247-ID proof ledger is an independent *comparison*,
    # NOT the source of this inventory. The census enumerates every directed
    # ID but records only true overlap/cut terminal candidates, never chases
    # arbitrary road-name/OSM-way continuations around the network.
    scans={}
    for side,source,peer in (("from",a_manifest,b_manifest),
                             ("to",b_manifest,a_manifest)):
        scans[side]=original_source_census(workspace,source,peer,pair,side)
        if (scans[side].get("nativeTilesExhaustivelyRead") is not True or
            scans[side].get("allOriginalDirectedIdsVisited",0)<1):
            raise ValueError("Native original source GraphReader did not exhaust all tiles")
    census_summary={
        side:{"originalDirectedIdsAudited":scan["allOriginalDirectedIdsVisited"],
              "originalTilesAudited":scan["originalTileCount"],
              "nearCutCandidateDirectedGraphIds":len(scan["allScopedRoadEndpoints"]),
              "nativeGraphLocalDeadendCandidateDirectedGraphIds":sum(
                  x["nativeOriginalGraphDeadend"]
                  for x in scan["allScopedRoadEndpoints"]),
              "outwardOrBeyondOriginal25kmCutCandidateDirectedGraphIds":sum(
                  x["outwardSourceCutClassification"] in (
                      "OUTWARD_CROSSING_OWN_SOURCE_25KM_CUT",
                      "ALREADY_BEYOND_OWN_SOURCE_25KM_CUT")
                  for x in scan["allScopedRoadEndpoints"]),
              "originalGraphCutCensusArtifact":scan["sourceCensusArtifact"],
              "graphArchiveSHA256":scan["immutableOriginalSourceCensusInputs"][
                  "sourceOriginalArchiveSHA256"]}
        for side,scan in scans.items()}
    ledger=find_best_native_ledger(workspace/"diagnostics"/"f8-production",pair)
    base={
        "schema":RESULT_SCHEMA,"version":2,
        "pairId":pair["pairId"],
        "fromGraphFingerprint":pair["fromGraphFingerprint"],
        "toGraphFingerprint":pair["toGraphFingerprint"],
        "fromBoundaryFingerprint":pair["fromBoundaryFingerprint"],
        "toBoundaryFingerprint":pair["toBoundaryFingerprint"],
        "sourceDiscoveryComplete":False,
        "physicalRoadPerDirectionGlobalUniqueness":"NOT_VERIFIED",
        "productionPublication":"BLOCKED",
        "fullAndroidAcceptance":"NOT_VERIFIED",
        "oldGpsPortalDiscoveryInvoked":False,
        "originalSourceGraphFullTileCensus":census_summary,
        "originalSourceCensusProofScope":
            "EVERY_NATIVE_DIRECTED_GRAPHID_VISITED_ONLY_REAL_SEAM_CANDIDATES_RETAINED",
    }
    if ledger is None:
        receipt=dict(base,
            stage="SOURCE_ALL_TILES_CENSUSED_A_LAST_B_FIRST_PENDING",
            reason="Fresh original native source archive census completed in BOTH "
                   "directions. Candidate terminal edges still require original "
                   "A-LAST TripLeg/source-topology and original B-FIRST matching.",
            verifiedSourceFinalDirectedGraphIds=0,
            verifiedReceivingDirectedOptions=0)
        immutable_json(dest/"pending-source-route-proof-v5.json",receipt)
        print("F8_POST_BUILD_SOURCE_CENSUSED_PENDING",pair["pairId"],
              "complete ORIGINAL source tile scans; A-LAST/B-FIRST pending",flush=True)
        return receipt
    path,source,source_sha=ledger
    # The old proof set must be a subset of the NEW exhaustive original source
    # graph census. It cannot 'teach' the census which GraphIds to discover.
    for side,region in (("from",pair["fromRegionId"]),
                        ("to",pair["toRegionId"])):
        discovered={c["originalDirectedGraphId"]
                    for c in scans[side]["allScopedRoadEndpoints"]}
        proved={c["sourceFinalDirectedGraphId"] for c in source["connections"]
                if c["sourceRegionId"]==region}
        omitted=proved-discovered
        if omitted:
            raise ValueError(
                "Fresh original source census missed previously Valhalla-proven "
                f"directed GraphIds in {region}: count {len(omitted)}; "
                "will not suppress legitimate road/direction branches")
    partial=make_partial_cache(source,source_sha[7:])
    counts=partial["counts"]
    # Android's bounded parser only accepts a compact <=3MB test cache.
    # Historical precompact files must never be overwritten or promoted.
    proofdir=dest/"verified-only-android-v5"/source_sha[7:]
    immutable_json(proofdir/"verified-native-test-only.json",partial,compact=True)
    receipt=dict(base,
        stage="PARTIAL_ORIGINAL_DIRECTED_ROAD_CONNECTIONS_VERIFIED_ONLY",
        originalUnpublishedLedgerSha256=source_sha,
        originalUnpublishedLedgerSource=str(path),
        verifiedSourceFinalDirectedGraphIds=counts["nativeVerifiedSourceDirectedIDs"],
        verifiedReceivingDirectedOptions=counts["nativeVerifiedReceivingDirectedOptions"],
        originalSourceTripLegRerunDuringAutomaticStage=False,
        originalSourceTripLegCurrentStatus="PREVIOUS_NATIVE_SHA_BOUND_EVIDENCE_ONLY",
        unresolvedOriginalCandidateIds=counts[
            "unresolvedOriginalNativeCandidateIDsRetainedInGraphStudioEvidence"],
        verifiedOnlyAndroidTestCache=str(
            proofdir/"verified-native-test-only.json"),
        mandatoryRemainingWork=(
            "Classify exact outgoing cut candidate road/directions into one "
            "true original source final per physical road/direction, then "
            "A-LAST/B-FIRST prove all new candidates and run full Android; "
            "no automatic production catalog published."))
    immutable_json(proofdir/"receipt.json",receipt)
    print("F8_POST_BUILD_VERIFIED_PARTIAL",pair["pairId"],
          counts["nativeVerifiedSourceDirectedIDs"],"source directed GraphIds",
          counts["nativeVerifiedReceivingDirectedOptions"],"B original-directed options; "
          "production BLOCKED",flush=True)
    return receipt


def run_after_build(
    workspace: Path, changed: set[tuple[str,str]],
    *, extra_manifest_dir: Path | None = None
) -> dict:
    if not changed or any(not (safe_component(r) and safe_component(v))
                          for r,v in changed):
        raise ValueError("Invalid completed regional build/version selection")
    builds = extra_manifest_dir or (workspace/"builds")
    found=listed_manifests(builds)
    pairs=select_compatible_pairs(found,changed)
    statuses=[]
    for a,b,pair in pairs:
        statuses.append(build_automatic_pair_receipt(workspace,a,b,pair))
    print("F8_POST_BUILD_SUMMARY",
          json.dumps({"checkedBuiltRegionVersions":sorted(changed),
                      "compatibleOriginalGraphPairs":len(pairs),
                      "verifiedPartialPairCount":sum(s["stage"].startswith("PARTIAL_") for s in statuses),
                      "freshOriginalSourceFullTileCensusPairs":sum(
                          bool(s.get("originalSourceGraphFullTileCensus")) for s in statuses),
                      "pendingOriginalNativeProofPairCount":sum(
                          s["stage"]=="SOURCE_ALL_TILES_CENSUSED_A_LAST_B_FIRST_PENDING"
                          for s in statuses),
                      "allProductionPublicationBlocked":True},
                     separators=(",",":")),flush=True)
    return {"pairs":statuses,"count":len(pairs)}


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace",type=Path,required=True)
    parser.add_argument("--built-region",action="append",required=True,
                        help="Region IDs whose regional graph just finished")
    parser.add_argument("--package-version",required=True)
    args=parser.parse_args()
    changed={(name,args.package_version) for name in args.built_region}
    run_after_build(args.workspace,changed)
    return 0


if __name__=="__main__":
    raise SystemExit(main())
