#!/usr/bin/env python3
import argparse
import json
import sqlite3
from pathlib import Path

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True)
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    database = Path(args.database)
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    overture = config["overture"]
    expected_region = config["id"]
    expected_schema = overture["databaseSchema"]

    db = sqlite3.connect(database)
    try:
        metadata = dict(db.execute("SELECT key, value FROM meta").fetchall())
        if metadata.get("region_id") != expected_region:
            raise SystemExit(
                f"Unexpected region_id: {metadata.get('region_id')!r} != {expected_region!r}"
            )
        if metadata.get("schema") != expected_schema:
            raise SystemExit(
                f"Unexpected database schema: {metadata.get('schema')!r} != {expected_schema!r}"
            )

        count = db.execute("SELECT COUNT(*) FROM places").fetchone()[0]
        if count <= 0:
            raise SystemExit("Overture place pack is empty")
        print("Overture place count:", count)

        for target in overture.get("validation", []):
            expected_name = str(target.get("nameEquals") or "").strip()
            contains_any = [
                str(value).lower()
                for value in target.get("addressContainsAny", [])
                if str(value).strip()
            ]
            if not expected_name:
                raise SystemExit("Validation target is missing nameEquals")

            rows = db.execute(
                """
                SELECT name, address, latitude, longitude, confidence
                FROM places
                WHERE lower(name) = lower(?)
                ORDER BY confidence DESC
                """,
                (expected_name,),
            ).fetchall()

            match = next(
                (
                    row
                    for row in rows
                    if not contains_any
                    or any(fragment in (row[1] or "").lower() for fragment in contains_any)
                ),
                None,
            )
            print(f"Validation record for {expected_name}:", match)
            if match is None:
                raise SystemExit(
                    f"Expected validation record {expected_name!r} is missing"
                )
    finally:
        db.close()

if __name__ == "__main__":
    main()
