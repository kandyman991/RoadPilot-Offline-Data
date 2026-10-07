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

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA = REPO_ROOT / "schemas" / "search-pack-manifest.schema.json"


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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--database", type=Path)
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    config = json.loads(args.config.read_text(encoding="utf-8"))
    validate_schema(manifest)

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
        columns = [row[1] for row in db.execute("PRAGMA table_info(places)").fetchall()]
        expected_columns = [
            "id","name","name_norm","address","address_norm",
            "latitude","longitude","confidence",
        ]
        if columns != expected_columns:
            fail(f"Unexpected roadpilot-overture-v1 places schema: {columns}")
        metadata = dict(db.execute("SELECT key, value FROM meta").fetchall())
        count = int(db.execute("SELECT COUNT(*) FROM places").fetchone()[0])
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

    print(
        f"valid search pack: {manifest['regionId']} {manifest['packVersion']} "
        f"release={source['dataRelease']} records={count} targets={validation['targetCount']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
