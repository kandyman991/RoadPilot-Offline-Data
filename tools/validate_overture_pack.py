#!/usr/bin/env python3
"""Validate a RoadPilot Overture SQLite pack using the Android v1 search contract."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

from roadpilot_search_v1 import search

RUNTIME_CONTRACT = "android-overture-place-search-v1"


def fail(message: str) -> None:
    raise SystemExit(message)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    if not args.database.is_file():
        fail(f"Database does not exist: {args.database}")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    overture = config["overture"]
    expected_region = config["id"]
    expected_schema = overture["databaseSchema"]

    db = sqlite3.connect(args.database)
    try:
        quick_check = db.execute("PRAGMA quick_check").fetchone()
        if quick_check is None or quick_check[0] != "ok":
            fail(f"SQLite quick_check failed: {quick_check}")

        metadata = dict(db.execute("SELECT key, value FROM meta").fetchall())
        if metadata.get("region_id") != expected_region:
            fail(
                f"Unexpected region_id: {metadata.get('region_id')!r} != {expected_region!r}"
            )
        if metadata.get("schema") != expected_schema:
            fail(
                f"Unexpected database schema: {metadata.get('schema')!r} != {expected_schema!r}"
            )

        count = int(db.execute("SELECT COUNT(*) FROM places").fetchone()[0])
        if count <= 0:
            fail("Overture place pack is empty")
        if metadata.get("record_count") != str(count):
            fail(
                f"record_count metadata mismatch: {metadata.get('record_count')!r} != {count}"
            )
        for key in (
            "source",
            "source_release",
            "source_client",
            "source_client_version",
            "source_input_sha256",
        ):
            if not str(metadata.get(key) or "").strip():
                fail(f"Database metadata is missing {key}")
        if metadata["source"] != "Overture Maps Foundation Places":
            fail(f"Unexpected source provider: {metadata['source']!r}")
        if metadata["source_client"] != "overturemaps":
            fail(f"Unexpected source client: {metadata['source_client']!r}")
        input_sha = metadata["source_input_sha256"]
        if len(input_sha) != 64 or any(ch not in "0123456789abcdef" for ch in input_sha):
            fail("source_input_sha256 metadata is invalid")
    finally:
        db.close()

    results: list[dict[str, Any]] = []
    for target in overture.get("validation", []):
        expected_name = str(target.get("nameEquals") or "").strip()
        contains_any = [
            str(value).lower()
            for value in target.get("addressContainsAny", [])
            if str(value).strip()
        ]
        query = str(target.get("query") or expected_name).strip()
        limit = int(target.get("limit") or 8)
        if not expected_name:
            fail("Validation target is missing nameEquals")
        if len(query) < 2:
            fail(f"Validation target {expected_name!r} has an invalid query")
        if not (1 <= limit <= 12):
            fail(f"Validation target {expected_name!r} limit must be from 1 to 12")

        ranked = search(args.database, query, limit=limit)
        matched_rank = None
        matched = None
        for index, candidate in enumerate(ranked, start=1):
            if candidate.title.casefold() != expected_name.casefold():
                continue
            if contains_any and not any(
                fragment in candidate.address.lower() for fragment in contains_any
            ):
                continue
            matched_rank = index
            matched = candidate
            break

        print(
            f"Runtime validation {expected_name!r} query={query!r}: "
            f"rank={matched_rank} top={ranked[0].title if ranked else None!r}"
        )
        if matched is None or matched_rank is None:
            preview = [
                {"rank": index, "title": item.title, "address": item.address, "score": item.score}
                for index, item in enumerate(ranked[:5], start=1)
            ]
            fail(
                f"Expected runtime-search target {expected_name!r} is missing from top {limit}: "
                f"{json.dumps(preview, ensure_ascii=False)}"
            )

        results.append(
            {
                "nameEquals": expected_name,
                "query": query,
                "passed": True,
                "matchedRank": matched_rank,
                "matchedName": matched.title,
                "matchedAddress": matched.address,
                "score": matched.score,
            }
        )

    if not results:
        fail("At least one Overture runtime validation target is required")

    report = {
        "schema": "roadpilot-search-validation",
        "version": 1,
        "regionId": expected_region,
        "databaseSchema": expected_schema,
        "runtimeContract": RUNTIME_CONTRACT,
        "recordCount": count,
        "passed": True,
        "results": results,
    }
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(f"valid Overture search pack: {expected_region} records={count} targets={len(results)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
