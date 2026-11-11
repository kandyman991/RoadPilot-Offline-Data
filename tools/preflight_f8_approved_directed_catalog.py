#!/usr/bin/env python3
"""Nonpublishing D-017 publication preflight over the *existing* PR127 native matcher.

The source evidence is the independently audited original Graph A final-edge inventory
and original B incoming directed geometry at exact X. This script does NOT find roads,
trace continuations, infer physical lineage or emit the production READY wire format.

Read-only on source graphs; the only output is an immutable BLOCKED preflight report.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path

import audit_f8_physical_road_evidence as native_audit

SCHEMA = "roadpilot.f8-approved-directed-road-production-preflight"
MASK_TO_NAME = ((1, "car"), (1024, "motorcycle"))


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def modes(mask: int) -> list[str]:
    require(type(mask) is int and mask > 0 and not mask & ~1025,
            "Native modes contain invalid vehicle bits")
    return [name for bit, name in MASK_TO_NAME if mask & bit]


def exact_float(value: object) -> float:
    require(type(value) in (float, int) and math.isfinite(value),
            "Native geometry contains invalid/NaN coordinate or distance")
    return float(value)


def reconcile(
    catalog: dict,
    original_native_dispositions: dict,
    original_native_audit: dict,
    *,
    native_evidence_sha: str,
    archive_from_sha: str,
    archive_to_sha: str,
) -> dict:
    """Strict independent census/readback equality, preserving all A/B incoming roads.

    Output may be used to prepare future proof review, NEVER used as a routable catalog.
    The standalone native auditor must run beforehand on original graph evidence.
    """
    pair = catalog["pairId"]
    source = catalog["fromRegionId"]
    receiver = catalog["toRegionId"]
    require(pair == source + "__" + receiver and source != receiver,
            "Original pair identity does not agree")
    require(catalog["schema"] == "roadpilot.f8-final-directed-connection-candidates" and
            catalog["version"] == 1 and
            catalog["productionPublication"] == "BLOCKED" and
            catalog["physicalRoadIdentityAcceptance"] == "NOT_VERIFIED",
            "Expected strictly BLOCKED, native-audited PR127 original evidence")
    require(catalog["graphFingerprints"] == {
        "from": archive_from_sha, "to": archive_to_sha
    }, "Original compiled graph archives do not match the native catalog")

    d = original_native_dispositions
    require(d["schema"] == "roadpilot.f8-pr127-bounded-physical-road-dispositions" and
            d["version"] == 1 and
            d["pairId"] == pair and
            d["fromRegionId"] == source and d["toRegionId"] == receiver and
            d["productionPublication"] == "BLOCKED" and
            d["originalGraphArchiveSha256"] == {
                "from": archive_from_sha, "to": archive_to_sha
            }, "Independent source disposition identity or publication state mismatch")
    for attr in ("sourceBufferFingerprint", "receiverBufferFingerprint",
                 "sourceGraphIndexFingerprint", "receiverGraphIndexFingerprint"):
        require(d[attr] == catalog[attr],
                "Native original pair fingerprint mismatch: " + attr)

    a = original_native_audit
    require(a["pairId"] == pair and
            a["productionPublication"] == "BLOCKED" and
            a["originalArchiveFingerprints"] == {
                "from": archive_from_sha, "to": archive_to_sha
            } and
            a["originalSourceFinalIdsCheckedAgainstIndependentNativeInventory"] is True and
            a["originalBIncomingApproachReadbackVerified"] is True,
            "Independent original archive/native audit was not successful")
    require(d["nativeOriginalSourceTerminalCensus"] ==
                "EXHAUSTIVE_WITHIN_PAIR_ENDPOINT_DOMAIN" and
            d["nativeLongEdgeOwningTileCoverage"] ==
                "VERIFIED_WITHIN_PAIR_ENDPOINT_DOMAIN" and
            d["noAdditionalRoadTracingPerformed"] is True,
            "Independent original A native inventory scope not attested")

    native_rows = catalog["nativeDirectedRoadMatchesAtX"]
    dispositions = d["nativeOriginalASourceFinalDispositions"]
    require(type(native_rows) is list and type(dispositions) is list,
            "Native A terminal list is missing")
    ids = [r["sourceFinalDirectedGraphId"] for r in native_rows]
    dids = [r["originalASourceFinalDirectedGraphId"] for r in dispositions]
    require(all(type(x) is int and x > 0 for x in ids + dids) and
            len(ids) == len(set(ids)) and len(dids) == len(set(dids)) and
            set(ids) == set(dids), "Original A directed final edge inventory incomplete/duplicated")
    require(len(ids) == catalog["counts"]["eligibleSourceFinals"] ==
            d["counts"]["eligibleOriginalAExteriorTerminals"] ==
            a["eligibleOriginalSourceFinals"] ==
            a["verifiedNativeAOriginalBDirectedIncomingAtExactX"],
            "Independent original A final inventory does not reconcile")

    by_disposition = {r["originalASourceFinalDirectedGraphId"]: r for r in dispositions}
    seen_b: set[int] = set()
    projected = []
    no_default_b_exit = Counter()
    source_modes_count = Counter()

    for row in sorted(native_rows, key=lambda r: r["sourceFinalDirectedGraphId"]):
        gid = row["sourceFinalDirectedGraphId"]
        disp = by_disposition[gid]
        require(row["status"] == "NATIVE_DIRECTED_ROAD_MATCH_AT_X" and
                row["productionRouteVerified"] is False and
                disp["originalAtoBIncomingDirectedApproach"] ==
                    "NATIVE_GEOMETRY_TOPOLOGY_VERIFIED",
                "Unverified original A/B incoming road correspondence")
        require(row["sourceFinalCoordinate"] == disp["exactX"],
                "Native original A exact X disagrees with independent disposition")
        source_modes = set(row["sourceValhallaProvedModes"])
        require(source_modes == set(
            "auto" if m == "car" else m
            for m in modes(disp["originalSourceCarMotorcycleModeMask"])
        ), "Original A vehicle permissions differ from native inventory")
        projected_receivers = []
        b_ids = set()
        for road in row["receiverDirectedRoadsAtX"]:
            bgid = road["receiverDirectedGraphId"]
            require(type(bgid) is int and bgid > 0 and
                    bgid not in b_ids and bgid not in seen_b,
                    "Original B incoming GraphId duplicated or invalid")
            b_ids.add(bgid)
            seen_b.add(bgid)
            require(road["receiverXPosition"] in ("END_NODE", "INTERIOR") and
                    road["productionRouteVerified"] is False,
                    "Original B X position or publication proof invalid")
            gap = exact_float(road["distanceXMetres"])
            overlap = exact_float(road["directedApproachOverlapMetres"])
            require(0 <= gap <= .75 and overlap >= 1,
                    "Original B incoming road has unsupported physical geometry")
            rmask = road["nativeCommonVehicleModes"]
            rmodes = modes(rmask)
            require(rmask & ~disp["originalSourceCarMotorcycleModeMask"] == 0,
                    "B native permissions wider than A original modes")
            expected_overlap = disp["nativeBIncomingDirectedOverlapMetres"].get(str(bgid))
            require(expected_overlap == road["directedApproachOverlapMetres"],
                    "Original B directed approach overlap changed from independent native proof")
            projected_receivers.append({
                "receiverDirectedGraphId": bgid,
                "receiverXPosition": road["receiverXPosition"],
                "travelModes": rmodes,
                "nativeXGapMeters": gap,
                "directedApproachOverlapMeters": overlap,
            })
        require(b_ids and b_ids == set(disp["nativeBIncomingDirectedGraphIds"]),
                "Native original B incoming matches were omitted or invented")
        require(max(r["nativeXGapMeters"] for r in projected_receivers) ==
                    disp["nativeBIncomingAtXMaxDeviationMetres"],
                "Native B exact X deviation differs from independently audited proof")
        no_default_b_exit[disp["disposition"]] += 1
        source_modes_count["+".join(sorted(source_modes))] += 1
        # Important: NO outgoing-turn gate. B incoming physical-road matching
        # remains valid even if default-costing B outgoing alternatives are absent.
        projected.append({
            "sourceFinalDirectedGraphId": gid,
            "exactX": row["sourceFinalCoordinate"],
            "sourceModes": ["car" if x == "auto" else x
                            for x in ("auto", "motorcycle") if x in source_modes],
            "receiverDirectedRoadsAtX": sorted(projected_receivers,
                                                key=lambda x: x["receiverDirectedGraphId"]),
        })

    require(a["fullPhysicalRoadIdentityApproval"] == "NOT_VERIFIED" and
            d["physicalRoadDirectionCompleteness"] == "NOT_VERIFIED" and
            d["androidProductionUIAcceptance"] == "NOT_VERIFIED" and
            all(row["sourceRoadDirectionCensusCompleteness"] == "NOT_VERIFIED" and
                row["mustNotPublishAsReady"] is True for row in dispositions),
            "Unexpected approval/completeness change: require new independently reviewed proof")

    # More than one native B incoming road can legitimately match a source A
    # final at the same X.  The disposition count measures matched A approaches;
    # the catalog and independent audit count every distinct B directed road.
    # Never assume those totals are equal or drop genuine receiver branches.
    require(len(seen_b) == catalog["counts"]["nativeBDirectedRoadMatchesAtX"] ==
            a["originalBDirectRoadMatchCount"] and
            d["counts"]["nativeBMatchedIncomingAApproaches"] == len(native_rows),
            "Original B directed match count mismatch")

    # Always nonpublishing. No approval, READY flag, B outgoing dependency,
    # signed APK pin, or production schema is constructed by this command.
    return {
        "schema": SCHEMA,
        "version": 1,
        "pairId": pair,
        "publication": "BLOCKED",
        "notForRoadPilotRuntime": True,
        "originalGraphArchives": {"from": archive_from_sha, "to": archive_to_sha},
        "nativeEvidenceSha256": native_evidence_sha,
        "counts": {
            "independentlyReconciledOriginalASourceFinals": len(ids),
            "nativeDirectedBIncomingPhysicalRoadMatches": len(seen_b),
            "unverifiedSourcePhysicalRoadLineages": sum(
                row["sourceRoadDirectionCensusCompleteness"] != "VERIFIED"
                for row in dispositions
            ),
            "unlinkedBoundedSourceRootsNotProvenDistinctRoads":
                d["counts"]["unlinkedOriginalSourceCutRootObservations"],
            "outgoingBContextDispositionsNotRoadMatchGates": dict(sorted(no_default_b_exit.items())),
            "originalAModeSets": dict(sorted(source_modes_count.items())),
        },
        "blockingEvidence": [
            "SEMANTIC_ORIGINAL_SOURCE_PHYSICAL_ROAD_LINEAGE_NOT_VERIFIED",
            "ANDROID_NORMAL_A_X_B_ROUTE_PREVIEW_NOT_VERIFIED",
            "ANDROID_FIRST_REPEAT_BOTH_DIRECTIONS_AND_MODES_NOT_VERIFIED",
            "INDEPENDENT_READY_CATALOG_REVIEW_MISSING",
            "OWNER_PRODUCTION_PUBLICATION_APPROVAL_MISSING",
            "SIGNED_APK_SHA256_PIN_MISSING",
        ],
        "nativeDirectedApproachesForReviewOnly": projected,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("catalog", "native_evidence", "dispositions", "from_archive",
                 "to_archive", "output"):
        parser.add_argument("--" + name.replace("_", "-"), type=Path, required=True)
    args = parser.parse_args()

    catalog = native_audit.read_json(args.catalog)
    native_evidence = native_audit.read_json(args.native_evidence)
    dispositions = native_audit.read_json(args.dispositions)
    audit = native_audit.audit(catalog, native_evidence)
    from_sha = native_audit.digest(args.from_archive)
    to_sha = native_audit.digest(args.to_archive)
    require(from_sha == catalog["graphFingerprints"]["from"] and
            to_sha == catalog["graphFingerprints"]["to"],
            "Original compiled Valhalla TAR SHA-256 mismatch")
    # The disposition is regenerated independently from original native evidence,
    # instead of trusting the selected preexisting file's counts or source GraphIds.
    require(native_audit.build_bounded_physical_road_dispositions(
        catalog, native_evidence
    ) == dispositions,
            "Stored independent disposition differs from original native source evidence")

    report = reconcile(
        catalog, dispositions, audit,
        native_evidence_sha=native_audit.digest(args.native_evidence),
        archive_from_sha=from_sha, archive_to_sha=to_sha,
    )
    native_audit.atomic_write_new_json(args.output, report)
    print(json.dumps({
        "pairId": report["pairId"],
        "publication": report["publication"],
        "counts": report["counts"],
        "blockingEvidence": report["blockingEvidence"],
        "nonpublishingReport": str(args.output),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
