#!/usr/bin/env python3
"""Build the Android-compatible RoadPilot search-pack manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def fail(message: str) -> None:
    raise SystemExit(message)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--pack-version", required=True)
    parser.add_argument("--validation-report", required=True, type=Path)
    args = parser.parse_args()

    if not args.database.is_file():
        fail(f"Database does not exist: {args.database}")
    if not args.validation_report.is_file():
        fail(f"Validation report does not exist: {args.validation_report}")

    config = json.loads(args.config.read_text(encoding="utf-8"))
    overture = config["overture"]
    pack_version = args.pack_version.strip()
    if not pack_version:
        fail("pack version is required")

    db = sqlite3.connect(args.database)
    try:
        record_count = int(db.execute("SELECT COUNT(*) FROM places").fetchone()[0])
        metadata = dict(db.execute("SELECT key, value FROM meta").fetchall())
    finally:
        db.close()

    if metadata.get("region_id") != config["id"]:
        fail("database region metadata does not match config")
    if metadata.get("schema") != overture["databaseSchema"]:
        fail("database schema metadata does not match config")
    if record_count <= 0:
        fail("database contains no places")
    if metadata.get("record_count") != str(record_count):
        fail("database record_count metadata does not match actual rows")

    source_release = str(metadata.get("source_release") or "").strip()
    source_client = str(metadata.get("source_client") or "").strip()
    source_client_version = str(metadata.get("source_client_version") or "").strip()
    source_input_sha = str(metadata.get("source_input_sha256") or "").strip().lower()
    if not source_release or source_release == "unknown":
        fail("database source_release metadata is missing")
    if source_client != "overturemaps":
        fail(f"unexpected Overture source client: {source_client!r}")
    if not SEMVER.fullmatch(source_client_version):
        fail(f"invalid Overture source client version: {source_client_version!r}")
    if not re.fullmatch(r"[0-9a-f]{64}", source_input_sha):
        fail("database source_input_sha256 metadata is invalid")

    validation_report = json.loads(args.validation_report.read_text(encoding="utf-8"))
    if validation_report.get("schema") != "roadpilot-search-validation":
        fail("unexpected search validation report schema")
    if validation_report.get("version") != 1 or validation_report.get("passed") is not True:
        fail("search validation report did not pass")
    if validation_report.get("regionId") != config["id"]:
        fail("search validation report region does not match config")
    if validation_report.get("databaseSchema") != overture["databaseSchema"]:
        fail("search validation report database schema does not match config")
    if validation_report.get("recordCount") != record_count:
        fail("search validation report record count does not match database")

    digest = hashlib.sha256(args.database.read_bytes()).hexdigest()
    coverage = overture["coverage"]
    source = {
        "provider": "Overture Maps Foundation Places",
        "dataRelease": source_release,
        "client": source_client,
        "clientVersion": source_client_version,
        "inputSha256": source_input_sha,
    }
    source_fingerprint_payload = {
        **source,
        "coverage": coverage,
    }
    source_fingerprint = "sha256:" + hashlib.sha256(
        canonical_bytes(source_fingerprint_payload)
    ).hexdigest()
    built_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    payload = {
        "schema": "roadpilot-search-pack",
        "schemaVersion": 1,
        "artifactKind": "SEARCH",
        "regionId": config["id"],
        "regionName": str(config.get("name") or config["id"]),
        "packVersion": pack_version,
        "builtAtUtc": built_at,
        "databaseSchema": overture["databaseSchema"],
        "fileName": overture["fileName"],
        "downloadUrl": overture["fileName"],
        "sha256": digest,
        "searchFingerprint": "sha256:" + digest,
        "sizeBytes": args.database.stat().st_size,
        "recordCount": record_count,
        "coverage": coverage,
        "sourceFingerprint": source_fingerprint,
        "source": source,
        "validation": {
            "passed": True,
            "runtimeContract": validation_report["runtimeContract"],
            "targetCount": len(validation_report["results"]),
            "results": validation_report["results"],
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
