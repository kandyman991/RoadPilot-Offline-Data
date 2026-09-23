#!/usr/bin/env python3
import argparse
import json
import sqlite3
import unicodedata
from pathlib import Path

DATABASE_SCHEMA = "roadpilot-overture-v1"

def normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value or "")
    without_marks = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(
        "".join(ch.lower() if ch.isalnum() else " " for ch in without_marks).split()
    )

def clean(value) -> str:
    return " ".join(str(value or "").split()).strip()

def full_address(address: dict) -> str:
    parts = [
        clean(address.get("freeform")),
        clean(address.get("postcode")),
        clean(address.get("locality")),
        clean(address.get("region")),
        clean(address.get("country")),
    ]
    result = []
    for part in parts:
        if part and all(part.casefold() != existing.casefold() for existing in result):
            result.append(part)
    return ", ".join(result)

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--region-id", required=True)
    parser.add_argument("--country", default="")
    args = parser.parse_args()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()

    db = sqlite3.connect(output)
    db.executescript(
        """
        PRAGMA journal_mode=OFF;
        PRAGMA synchronous=OFF;
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE places (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            name_norm TEXT NOT NULL,
            address TEXT NOT NULL,
            address_norm TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            confidence REAL NOT NULL
        );
        CREATE INDEX idx_places_name_norm ON places(name_norm);
        """
    )

    inserted = 0
    with open(args.input, "r", encoding="utf-8") as source:
        for line in source:
            line = line.strip()
            if not line:
                continue
            feature = json.loads(line)
            props = feature.get("properties") or {}
            names = props.get("names") or {}
            name = clean(names.get("primary"))
            addresses = props.get("addresses") or []
            address_obj = next((item for item in addresses if isinstance(item, dict)), None)
            geometry = feature.get("geometry") or {}
            coordinates = geometry.get("coordinates") or []
            if not name or address_obj is None or len(coordinates) < 2:
                continue

            country = clean(address_obj.get("country"))
            if args.country and country and country.upper() != args.country.upper():
                continue

            address = full_address(address_obj)
            if not address:
                continue

            try:
                longitude = float(coordinates[0])
                latitude = float(coordinates[1])
                confidence = float(props.get("confidence") or 0.0)
            except (TypeError, ValueError):
                continue

            place_id = clean(props.get("id") or feature.get("id"))
            if not place_id:
                place_id = f"{normalize(name)}:{latitude:.6f}:{longitude:.6f}"

            cursor = db.execute(
                "INSERT OR IGNORE INTO places VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    place_id,
                    name,
                    normalize(name),
                    address,
                    normalize(address),
                    latitude,
                    longitude,
                    confidence,
                ),
            )
            inserted += cursor.rowcount
            if inserted and inserted % 5000 == 0:
                db.commit()

    db.executemany(
        "INSERT INTO meta(key, value) VALUES (?, ?)",
        [
            ("region_id", args.region_id),
            ("source", "Overture Maps Foundation Places"),
            ("schema", DATABASE_SCHEMA),
            ("record_count", str(inserted)),
        ],
    )
    db.commit()
    db.execute("ANALYZE")
    db.execute("VACUUM")
    db.close()
    print(f"Wrote {inserted} Overture places to {output}")

if __name__ == "__main__":
    main()
