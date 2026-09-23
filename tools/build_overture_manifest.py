#!/usr/bin/env python3
import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--pack-version", required=True)
    args = parser.parse_args()

    database = Path(args.database)
    output = Path(args.output)
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    overture = config["overture"]
    pack_version = args.pack_version.strip()
    if not pack_version:
        raise SystemExit("pack version is required")

    db = sqlite3.connect(database)
    try:
        record_count = db.execute("SELECT COUNT(*) FROM places").fetchone()[0]
        metadata = dict(db.execute("SELECT key, value FROM meta").fetchall())
    finally:
        db.close()

    if metadata.get("region_id") != config["id"]:
        raise SystemExit("database region metadata does not match config")
    if metadata.get("schema") != overture["databaseSchema"]:
        raise SystemExit("database schema metadata does not match config")
    if record_count <= 0:
        raise SystemExit("database contains no places")

    digest = hashlib.sha256(database.read_bytes()).hexdigest()
    payload = {
        "schemaVersion": 1,
        "regionId": config["id"],
        "packVersion": pack_version,
        "databaseSchema": overture["databaseSchema"],
        "fileName": overture["fileName"],
        "downloadUrl": overture["fileName"],
        "sha256": digest,
        "sizeBytes": database.stat().st_size,
        "recordCount": record_count,
        "coverage": overture["coverage"],
        "source": "Overture Maps Foundation Places",
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))

if __name__ == "__main__":
    main()
