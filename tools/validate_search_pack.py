#!/usr/bin/env python3
"""Validate one retained RoadPilot regional search artifact exactly."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from roadpilot_search_v1 import search
from roadpilot_search_v2 import search as enhanced_search

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA = REPO_ROOT / "schemas" / "search-pack-manifest.schema.json"
ENRICHMENT_SCHEMA = "roadpilot-search-enrichment-v2"
ENHANCED_RUNTIME_CONTRACT = "roadpilot-search-v2"

BASE_COLUMNS = [
    "id",
    "name",
    "name_norm",
    "address",
    "address_norm",
    "latitude",
    "longitude",
    "confidence",
]
ENRICHED_COLUMNS = [
    "freeform",
    "address_context_id",
    "operating_status",
    "basic_category_id",
    "taxonomy_primary_id",
    "source_id",
    "source_record_id",
]
EXPECTED_AUX_COLUMNS = {
    "address_contexts": ["id", "postcode", "locality", "region", "country"],
    "search_categories": ["id", "name", "name_norm"],
    "place_categories": ["place_rowid", "category_id", "relation", "ordinal"],
    "search_sources": ["id", "provider", "dataset", "version"],
}


def fail(message: str) -> None:
    raise SystemExit(message)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_schema(value: dict[str, Any]) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(schema).iter_errors(value), key=lambda e: list(e.path))
    if errors:
        detail = "\n".join(
            f"- {'.'.join(str(part) for part in error.path) or '<root>'}: {error.message}"
            for error in errors[:20]
        )
        fail(f"Search manifest schema validation failed:\n{detail}")


def parse_count(metadata: dict[str, str], key: str, maximum: int) -> int:
    try:
        value = int(metadata[key])
    except (KeyError, TypeError, ValueError):
        fail(f"SQLite metadata {key} is missing or invalid")
    if not (0 <= value <= maximum):
        fail(f"SQLite metadata {key} is outside record-count bounds")
    return value


def table_columns(db: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in db.execute(f"PRAGMA table_info({table})").fetchall()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--database", type=Path)
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    validate_schema(manifest)

    if args.config is not None:
        config = json.loads(args.config.read_text(encoding="utf-8"))
        overture = config["overture"]
        if manifest["regionId"] != config["id"]:
            fail("Search manifest regionId does not match config")
        if manifest["regionName"] != str(config.get("name") or config["id"]):
            fail("Search manifest regionName does not match config")
        if manifest["databaseSchema"] != overture["databaseSchema"]:
            fail("Search manifest databaseSchema does not match config")
        if manifest["coverage"] != overture["coverage"]:
            fail("Search manifest coverage does not match config")
        if manifest["fileName"] != overture["fileName"]:
            fail("Search manifest fileName does not match config")

    database = (args.database or (args.manifest.parent / manifest["fileName"])).resolve()
    if not database.is_file():
        fail(f"Search database does not exist: {database}")
    actual_size = database.stat().st_size
    actual_sha = sha256_file(database)
    if actual_size != manifest["sizeBytes"]:
        fail(f"Search database size mismatch: {actual_size} != {manifest['sizeBytes']}")
    if actual_sha != manifest["sha256"]:
        fail(f"Search database SHA mismatch: {actual_sha} != {manifest['sha256']}")
    if manifest["searchFingerprint"] != f"sha256:{actual_sha}":
        fail("searchFingerprint must equal the exact SQLite SHA-256")

    checksum = database.with_name(database.name + ".sha256")
    if checksum.is_file():
        expected = f"{actual_sha}  {database.name}"
        actual = checksum.read_text(encoding="utf-8").strip()
        if actual != expected:
            fail(f"Search checksum file mismatch: expected {expected!r}, got {actual!r}")

    db = sqlite3.connect(database)
    try:
        quick = db.execute("PRAGMA quick_check").fetchone()
        if quick is None or quick[0] != "ok":
            fail(f"SQLite quick_check failed: {quick}")

        columns = table_columns(db, "places")
        metadata = dict(db.execute("SELECT key, value FROM meta").fetchall())
        count = int(db.execute("SELECT COUNT(*) FROM places").fetchone()[0])

        enrichment_schema = str(metadata.get("search_enrichment_schema") or "").strip()
        if enrichment_schema:
            if enrichment_schema != ENRICHMENT_SCHEMA:
                fail(f"Unsupported SQLite search enrichment schema: {enrichment_schema!r}")
            if columns != BASE_COLUMNS + ENRICHED_COLUMNS:
                fail(f"Unexpected enriched roadpilot-overture-v1 places schema: {columns}")
            for table, expected in EXPECTED_AUX_COLUMNS.items():
                actual = table_columns(db, table)
                if actual != expected:
                    fail(f"Unexpected {table} schema: {actual}")

            orphan_category_links = int(
                db.execute(
                    """
                    SELECT COUNT(*)
                    FROM place_categories pc
                    LEFT JOIN places p ON p.rowid = pc.place_rowid
                    LEFT JOIN search_categories c ON c.id = pc.category_id
                    WHERE p.rowid IS NULL OR c.id IS NULL
                    """
                ).fetchone()[0]
            )
            if orphan_category_links:
                fail(f"Search category relation contains {orphan_category_links} orphan rows")

            categorized_count = int(
                db.execute(
                    "SELECT COUNT(DISTINCT place_rowid) FROM place_categories"
                ).fetchone()[0]
            )
            structured_count = int(
                db.execute(
                    """
                    SELECT COUNT(*)
                    FROM places p
                    JOIN address_contexts ac ON ac.id = p.address_context_id
                    WHERE p.freeform <> '' OR ac.postcode <> '' OR ac.locality <> ''
                       OR ac.region <> '' OR ac.country <> ''
                    """
                ).fetchone()[0]
            )
            source_identified_count = int(
                db.execute(
                    """
                    SELECT COUNT(*)
                    FROM places
                    WHERE source_id <> 0 OR source_record_id <> ''
                    """
                ).fetchone()[0]
            )
            enhanced_sample = db.execute(
                """
                SELECT p.id, c.name, p.latitude, p.longitude
                FROM place_categories pc
                JOIN places p ON p.rowid = pc.place_rowid
                JOIN search_categories c ON c.id = pc.category_id
                WHERE p.operating_status <> 'permanently_closed'
                ORDER BY p.id, pc.relation, pc.ordinal
                LIMIT 1
                """
            ).fetchone()
        else:
            if columns != BASE_COLUMNS:
                fail(f"Unexpected roadpilot-overture-v1 places schema: {columns}")
            categorized_count = structured_count = source_identified_count = 0
            enhanced_sample = None
    finally:
        db.close()

    if count != manifest["recordCount"]:
        fail(f"Search record count mismatch: {count} != {manifest['recordCount']}")
    if metadata.get("region_id") != manifest["regionId"]:
        fail("SQLite region metadata does not match manifest")
    if metadata.get("schema") != manifest["databaseSchema"]:
        fail("SQLite database schema metadata does not match manifest")
    if metadata.get("record_count") != str(count):
        fail("SQLite record_count metadata does not match actual rows")

    source = manifest["source"]
    expected_meta = {
        "source": source["provider"],
        "source_release": source["dataRelease"],
        "source_client": source["client"],
        "source_client_version": source["clientVersion"],
        "source_input_sha256": source["inputSha256"],
    }
    for key, expected in expected_meta.items():
        if metadata.get(key) != expected:
            fail(f"SQLite metadata {key} does not match manifest source")

    source_payload = {**source, "coverage": manifest["coverage"]}
    source_fingerprint = "sha256:" + hashlib.sha256(canonical_bytes(source_payload)).hexdigest()
    if source_fingerprint != manifest["sourceFingerprint"]:
        fail(
            f"sourceFingerprint mismatch: expected {source_fingerprint}, "
            f"got {manifest['sourceFingerprint']}"
        )

    enrichment = manifest.get("enrichment")
    capabilities = manifest.get("capabilities")
    if enrichment_schema:
        if not isinstance(enrichment, dict) or not isinstance(capabilities, dict):
            fail("Enriched search database is missing manifest enrichment/capabilities")
        if enrichment["schema"] != enrichment_schema:
            fail("Manifest search enrichment schema does not match SQLite metadata")
        recorded_counts = {
            "categorizedRecordCount": parse_count(metadata, "categorized_record_count", count),
            "structuredAddressRecordCount": parse_count(
                metadata, "structured_address_record_count", count
            ),
            "sourceIdentifiedRecordCount": parse_count(
                metadata, "source_identified_record_count", count
            ),
        }
        actual_counts = {
            "categorizedRecordCount": categorized_count,
            "structuredAddressRecordCount": structured_count,
            "sourceIdentifiedRecordCount": source_identified_count,
        }
        if any(value <= 0 for value in actual_counts.values()):
            fail(f"Enriched search pack is missing required enrichment coverage: {actual_counts}")
        if recorded_counts != actual_counts:
            fail(
                f"SQLite search enrichment counts changed: recorded={recorded_counts} "
                f"actual={actual_counts}"
            )
        for key, actual in actual_counts.items():
            if enrichment[key] != actual:
                fail(f"Manifest {key} does not match enriched SQLite content")
        if metadata.get("enhanced_runtime_contract") != ENHANCED_RUNTIME_CONTRACT:
            fail("SQLite enhanced runtime contract metadata is invalid")
        runtime_contracts = capabilities["runtimeContracts"]
        if ENHANCED_RUNTIME_CONTRACT not in runtime_contracts:
            fail("Manifest does not advertise the enhanced search runtime contract")
        if "android-overture-place-search-v1" not in runtime_contracts:
            fail("Manifest dropped the Android v1 compatibility runtime contract")
        if enhanced_sample is None:
            fail("Enriched search pack has no open categorized runtime sample")
        sample_id, sample_category, sample_lat, sample_lng = enhanced_sample
        enhanced_results = enhanced_search(
            database,
            category=str(sample_category),
            origin_lat=float(sample_lat),
            origin_lng=float(sample_lng),
            limit=8,
        )
        if not enhanced_results:
            fail(
                f"Enhanced runtime returned no results for category sample "
                f"{sample_category!r} at {sample_id!r}"
            )
        if enhanced_results[0].scoreProximity <= 0:
            fail("Enhanced runtime proximity scoring did not activate")
    elif enrichment is not None or capabilities is not None:
        fail("Historical v1 database must not advertise M2 enrichment capabilities")

    validation = manifest["validation"]
    if validation["targetCount"] != len(validation["results"]):
        fail("Search validation targetCount does not match result list")
    for result in validation["results"]:
        ranked = search(database, result["query"], limit=12)
        rank = int(result["matchedRank"])
        if rank < 1 or rank > len(ranked):
            fail(f"Recorded match rank is no longer available for query {result['query']!r}")
        current = ranked[rank - 1]
        if (
            current.title != result["matchedName"]
            or current.address != result["matchedAddress"]
            or current.score != result["score"]
        ):
            fail(
                f"Runtime search result changed for query {result['query']!r}: "
                f"recorded={result['matchedName']!r}@{rank}/{result['score']} "
                f"actual={current.title!r}@{rank}/{current.score}"
            )
        if current.title.casefold() != result["nameEquals"].casefold():
            fail(f"Recorded runtime target name mismatch for query {result['query']!r}")

    if not re.fullmatch(r"\d+\.\d+\.\d+", source["clientVersion"]):
        fail("Source client version is not semantic")

    enrichment_text = (
        f" enriched={categorized_count}/{count}" if enrichment_schema else ""
    )
    print(
        f"valid search pack: {manifest['regionId']} {manifest['packVersion']} "
        f"release={source['dataRelease']} records={count} "
        f"targets={validation['targetCount']}{enrichment_text}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
