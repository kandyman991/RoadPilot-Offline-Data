#!/usr/bin/env python3
"""Build the complete directed original A->exact X->B auto-routing catalog candidate.

Inputs must independently pass the native original-archive auditor and deterministic
preflight. No hardcoded region/road IDs, no legacy road scans and no outgoing B
turn-continuation gate. The default artifact remains BLOCKED_TEST_ONLY for
compatibility. --graph-studio-private-ready emits a separately named, SHA-bound
Graph Studio owner-only validated catalog without Android requirements. It
cannot impersonate RoadPilot's later public/consumer READY contract.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import audit_f8_physical_road_evidence as native_audit
from preflight_f8_approved_directed_catalog import reconcile, require

SCHEMA = "roadpilot.f8-original-directed-auto-catalog-test-only"
GRAPH_STUDIO_SCHEMA = "roadpilot.f8-graph-studio-private-validated-catalog"
GRAPH_STUDIO_NATIVE_SCOPE = "VERIFIED_WITHIN_ORIGINAL_PAIR_ENDPOINT_DOMAIN"


def build(preflight: dict, preflight_sha256: str, *,
          graph_studio_private_ready: bool = False) -> dict:
    require(preflight.get("schema") ==
            "roadpilot.f8-approved-directed-road-production-preflight" and
            preflight.get("publication") == "BLOCKED" and
            preflight.get("notForRoadPilotRuntime") is True and
            preflight.get("version") == 1,
            "Expected independently audited BLOCKED preflight")
    sha_pattern = re.compile(r"sha256:[0-9a-f]{64}\Z")
    require(isinstance(preflight_sha256, str) and
            sha_pattern.fullmatch(preflight_sha256) is not None,
            "Preflight proof SHA-256 unavailable")
    rows = preflight["nativeDirectedApproachesForReviewOnly"]
    counts = preflight["counts"]
    require(type(rows) is list and rows and
            len(rows) == counts["independentlyReconciledOriginalASourceFinals"] and
            sum(len(r["receiverDirectedRoadsAtX"]) for r in rows) ==
                counts["nativeDirectedBIncomingPhysicalRoadMatches"],
            "Incomplete original A directed road or B incoming directed road inventory")
    require(counts["unverifiedSourcePhysicalRoadLineages"] == len(rows),
            "The native source lineage gate changed; requires fresh independent review")
    original = preflight["originalGraphArchives"]
    require(set(original) == {"from", "to"} and
            all(isinstance(h, str) and sha_pattern.fullmatch(h) is not None
                for h in original.values()) and
            sha_pattern.fullmatch(preflight["nativeEvidenceSha256"]) is not None,
            "Original compiled Valhalla graph fingerprints missing")
    seen_a: set[int] = set()
    seen_b: set[int] = set()
    for row in rows:
        require(set(row) == {"sourceFinalDirectedGraphId", "exactX", "sourceModes",
                             "receiverDirectedRoadsAtX"},
                "Unexpected original A inventory field")
        aid = row["sourceFinalDirectedGraphId"]
        require(type(aid) is int and aid > 0 and aid not in seen_a,
                "Duplicate/missing original directed Graph A source")
        seen_a.add(aid)
        require(set(row["sourceModes"]) <= {"car", "motorcycle"}
                and row["sourceModes"], "Unproved original A vehicle modes")
        x = row["exactX"]
        require(-90 <= x["lat"] <= 90 and -180 <= x["lng"] <= 180,
                "Unproved original A exact X")
        require(row["receiverDirectedRoadsAtX"], "Missing directed original B road")
        for b in row["receiverDirectedRoadsAtX"]:
            bid = b["receiverDirectedGraphId"]
            require(type(bid) is int and bid > 0 and bid not in seen_b,
                    "Duplicate/missing original B directed GraphId")
            seen_b.add(bid)
            require(set(b["travelModes"]) <= set(row["sourceModes"]) and
                    b["travelModes"], "B permissions exceed original source permissions")
            require(b["receiverXPosition"] in ("END_NODE", "INTERIOR") and
                    0 <= b["nativeXGapMeters"] <= .75 and
                    (b["directedApproachOverlapMeters"] >= 1 or
                     (0.5 <= b["directedApproachOverlapMeters"] < 1
                      and b["nativeXGapMeters"] <= .10)),
                    "B original road projection or directed overlap invalid")
    require(len(seen_b) == counts["nativeDirectedBIncomingPhysicalRoadMatches"],
            "Original B directions lost in production-ready candidate generation")
    source, to = preflight["pairId"].split("__")
    require(source != to and source and to, "Invalid directed region pair")
    if graph_studio_private_ready:
        require(preflight.get("graphStudioPrivateTestingReady") is True and
                preflight.get("graphStudioNativeCoverageScope") ==
                    GRAPH_STUDIO_NATIVE_SCOPE,
                "Graph Studio native private acceptance proof is missing")
    artifact = {
        "schema": GRAPH_STUDIO_SCHEMA if graph_studio_private_ready else SCHEMA,
        "version": 1,
        "pairId": preflight["pairId"],
        "fromRegionId": source,
        "toRegionId": to,
        "publication": ("GRAPH_STUDIO_PRIVATE_READY" if graph_studio_private_ready
                        else "BLOCKED_TEST_ONLY"),
        "originalGraphArchives": original,
        "independentSourcePreflightSha256": preflight_sha256,
        "nativeEvidenceSha256": preflight["nativeEvidenceSha256"],
        "counts": {
            "originalSourceFinals": len(rows),
            "sourceConnections": len(rows),
            "receiverIncomingRoads": len(seen_b),
            "excludedOriginalSourceFinals": 0,
        },
        "connections": rows,
        "excludedSourceFinals": [],
    }
    if graph_studio_private_ready:
        # This is an actual owner-only Graph Studio build/test artifact, not a
        # consumer production READY authorization. No Android check or APK pin.
        artifact.update({
            "intendedUse": "OWNER_ONLY_GRAPH_STUDIO_TESTING",
            "notForRoadPilotRuntime": True,
            "graphStudioNativeCoverageScope": GRAPH_STUDIO_NATIVE_SCOPE,
            "sourcePhysicalRoadDirectionCompleteness": "NOT_VERIFIED",
            "unverifiedSourcePhysicalRoadLineages":
                counts["unverifiedSourcePhysicalRoadLineages"],
        })
    else:
        artifact["remainingProductionReview"] = preflight["blockingEvidence"]
    return artifact


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(2 * 1024 * 1024), b""):
            h.update(block)
    return "sha256:" + h.hexdigest()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("catalog", "native_evidence", "dispositions",
                 "from_archive", "to_archive", "preflight", "output"):
        p.add_argument("--" + name.replace("_", "-"), required=True, type=Path)
    p.add_argument("--graph-studio-private-ready", action="store_true",
                   help="Generate private validated Graph Studio catalog; never a RoadPilot-ready catalog")
    args = p.parse_args()
    original = native_audit.read_json(args.catalog)
    native_evidence = native_audit.read_json(args.native_evidence)
    disposition = native_audit.read_json(args.dispositions)
    audit = native_audit.audit(original, native_evidence)
    a_sha, b_sha = sha(args.from_archive), sha(args.to_archive)
    require(native_audit.build_bounded_physical_road_dispositions(
        original, native_evidence) == disposition,
        "Regenerated independent original source inventory differs")
    review = reconcile(
        original, disposition, audit,
        native_evidence_sha=sha(args.native_evidence),
        archive_from_sha=a_sha, archive_to_sha=b_sha
    )
    # Bind provenance to the ACTUAL externally retained immutable preflight
    # report bytes, after independently reproducing its every field. Never
    # claim an approximate reconstruction hash as the archived proof hash.
    retained_preflight = native_audit.read_json(args.preflight)
    require(retained_preflight == review,
            "Immutable preflight report differs from independently regenerated proof")
    auto = build(review, sha(args.preflight),
                 graph_studio_private_ready=args.graph_studio_private_ready)
    if args.graph_studio_private_ready:
        # Validate the distinct private wire schema before writing any bytes.
        from jsonschema import Draft202012Validator
        schema_path = Path(__file__).resolve().parents[1] / "schemas" / (
            "f8-graph-studio-native-private-catalog.schema.json")
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(auto)
    native_audit.atomic_write_new_json(args.output, auto)
    print(json.dumps({
        "pairId": auto["pairId"],
        "publication": auto["publication"],
        "sourceConnections": auto["counts"]["sourceConnections"],
        "receiverIncomingRoads": auto["counts"]["receiverIncomingRoads"],
        "output": str(args.output),
        "catalogSha256": sha(args.output)
    }, sort_keys=True))


if __name__ == "__main__":
    main()
