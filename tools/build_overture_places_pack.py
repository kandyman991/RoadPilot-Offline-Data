#!/usr/bin/env python3
import argparse
import hashlib
import json
import sqlite3
import unicodedata
from pathlib import Path

DATABASE_SCHEMA = "roadpilot-overture-v1"
ENRICHMENT_SCHEMA = "roadpilot-search-enrichment-v2"
ENHANCED_RUNTIME_CONTRACT = "roadpilot-search-v2"

CATEGORY_RELATION_BASIC = 0
CATEGORY_RELATION_HIERARCHY = 1
CATEGORY_RELATION_ALTERNATE = 2


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value or "")
    without_marks = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(
        "".join(ch.lower() if ch.isalnum() else " " for ch in without_marks).split()
    )


def clean(value) -> str:
    return " ".join(str(value or "").split()).strip()


def clean_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        text = clean(item)
        if text and text not in result:
            result.append(text)
    return result


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


def taxonomy_fields(props: dict) -> tuple[str, str, list[str], list[str]]:
    basic_category = clean(props.get("basic_category"))
    taxonomy = props.get("taxonomy")
    if not isinstance(taxonomy, dict):
        taxonomy = {}

    primary = clean(taxonomy.get("primary"))
    hierarchy = clean_list(taxonomy.get("hierarchy"))
    alternates = clean_list(taxonomy.get("alternates"))

    # Reproducible rebuilds may use Overture releases from before September 2026.
    legacy = props.get("categories")
    if isinstance(legacy, dict):
        if not primary:
            primary = clean(legacy.get("primary"))
        if not alternates:
            alternates = clean_list(legacy.get("alternate"))

    if primary and primary not in hierarchy:
        hierarchy.append(primary)
    return basic_category, primary, hierarchy, alternates


def preferred_source(props: dict) -> tuple[str, str, str, str]:
    sources = [item for item in (props.get("sources") or []) if isinstance(item, dict)]
    if not sources:
        return "", "", "", ""

    def score(item: dict) -> tuple[float, str, str, str, str]:
        try:
            confidence = float(item.get("confidence"))
        except (TypeError, ValueError):
            confidence = -1.0
        provider = clean(item.get("provider"))
        dataset = clean(item.get("dataset") or item.get("resource"))
        record_id = clean(item.get("record_id") or item.get("recordId"))
        version = clean(item.get("version"))
        return (confidence, provider, dataset, record_id, version)

    selected = max(sources, key=score)
    return (
        clean(selected.get("provider")),
        clean(selected.get("dataset") or selected.get("resource")),
        clean(selected.get("record_id") or selected.get("recordId")),
        clean(selected.get("version")),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--region-id", required=True)
    parser.add_argument("--country", default="")
    parser.add_argument("--source-release", default="unknown")
    parser.add_argument("--source-client-version", default="unknown")
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

        CREATE TABLE meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        -- The first eight columns are the shipped Android v1 contract. Never
        -- rename, reorder or remove them while roadpilot-overture-v1 is supported.
        CREATE TABLE places (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            name_norm TEXT NOT NULL,
            address TEXT NOT NULL,
            address_norm TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            confidence REAL NOT NULL,
            freeform TEXT NOT NULL,
            address_context_id INTEGER NOT NULL,
            operating_status TEXT NOT NULL,
            basic_category_id INTEGER NOT NULL,
            taxonomy_primary_id INTEGER NOT NULL,
            source_id INTEGER NOT NULL,
            source_record_id TEXT NOT NULL
        );
        CREATE INDEX idx_places_name_norm ON places(name_norm);
        CREATE INDEX idx_places_lat_lon ON places(latitude, longitude);

        CREATE TABLE address_contexts (
            id INTEGER PRIMARY KEY,
            postcode TEXT NOT NULL,
            locality TEXT NOT NULL,
            region TEXT NOT NULL,
            country TEXT NOT NULL,
            UNIQUE(postcode, locality, region, country)
        );

        CREATE TABLE search_categories (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            name_norm TEXT NOT NULL
        );
        CREATE INDEX idx_search_categories_name_norm
            ON search_categories(name_norm);

        CREATE TABLE place_categories (
            place_rowid INTEGER NOT NULL,
            category_id INTEGER NOT NULL,
            relation INTEGER NOT NULL,
            ordinal INTEGER NOT NULL,
            PRIMARY KEY(place_rowid, category_id, relation)
        ) WITHOUT ROWID;
        CREATE INDEX idx_place_categories_category
            ON place_categories(category_id, place_rowid);

        CREATE TABLE search_sources (
            id INTEGER PRIMARY KEY,
            provider TEXT NOT NULL,
            dataset TEXT NOT NULL,
            version TEXT NOT NULL,
            UNIQUE(provider, dataset, version)
        );
        """
    )

    address_cache: dict[tuple[str, str, str, str], int] = {}
    category_cache: dict[str, int] = {}
    source_cache: dict[tuple[str, str, str], int] = {}

    def address_context_id(postcode: str, locality: str, region: str, country: str) -> int:
        key = (postcode, locality, region, country)
        cached = address_cache.get(key)
        if cached is not None:
            return cached
        cursor = db.execute(
            """
            INSERT OR IGNORE INTO address_contexts(postcode, locality, region, country)
            VALUES (?, ?, ?, ?)
            """,
            key,
        )
        if cursor.rowcount:
            value = int(cursor.lastrowid)
        else:
            row = db.execute(
                """
                SELECT id FROM address_contexts
                WHERE postcode = ? AND locality = ? AND region = ? AND country = ?
                """,
                key,
            ).fetchone()
            if row is None:
                raise RuntimeError("Could not resolve normalized address context")
            value = int(row[0])
        address_cache[key] = value
        return value

    def category_id(name: str) -> int:
        if not name:
            return 0
        cached = category_cache.get(name)
        if cached is not None:
            return cached
        cursor = db.execute(
            "INSERT OR IGNORE INTO search_categories(name, name_norm) VALUES (?, ?)",
            (name, normalize(name)),
        )
        if cursor.rowcount:
            value = int(cursor.lastrowid)
        else:
            row = db.execute(
                "SELECT id FROM search_categories WHERE name = ?",
                (name,),
            ).fetchone()
            if row is None:
                raise RuntimeError("Could not resolve search category")
            value = int(row[0])
        category_cache[name] = value
        return value

    def source_id(provider: str, dataset: str, version: str) -> int:
        if not (provider or dataset or version):
            return 0
        key = (provider, dataset, version)
        cached = source_cache.get(key)
        if cached is not None:
            return cached
        cursor = db.execute(
            """
            INSERT OR IGNORE INTO search_sources(provider, dataset, version)
            VALUES (?, ?, ?)
            """,
            key,
        )
        if cursor.rowcount:
            value = int(cursor.lastrowid)
        else:
            row = db.execute(
                """
                SELECT id FROM search_sources
                WHERE provider = ? AND dataset = ? AND version = ?
                """,
                key,
            ).fetchone()
            if row is None:
                raise RuntimeError("Could not resolve normalized search source")
            value = int(row[0])
        source_cache[key] = value
        return value

    inserted = 0
    categorized_records = 0
    structured_address_records = 0
    source_identified_records = 0

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

            freeform = clean(address_obj.get("freeform"))
            postcode = clean(address_obj.get("postcode"))
            locality = clean(address_obj.get("locality"))
            region = clean(address_obj.get("region"))
            context_id = address_context_id(postcode, locality, region, country)
            operating_status = clean(props.get("operating_status"))
            basic_category, taxonomy_primary, hierarchy, alternates = taxonomy_fields(props)
            basic_id = category_id(basic_category)
            primary_id = category_id(taxonomy_primary)
            (
                source_provider,
                source_dataset,
                source_record_id,
                source_version,
            ) = preferred_source(props)
            normalized_source_id = source_id(
                source_provider,
                source_dataset,
                source_version,
            )

            cursor = db.execute(
                """
                INSERT OR IGNORE INTO places (
                    id, name, name_norm, address, address_norm,
                    latitude, longitude, confidence,
                    freeform, address_context_id, operating_status,
                    basic_category_id, taxonomy_primary_id,
                    source_id, source_record_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    place_id,
                    name,
                    normalize(name),
                    address,
                    normalize(address),
                    latitude,
                    longitude,
                    confidence,
                    freeform,
                    context_id,
                    operating_status,
                    basic_id,
                    primary_id,
                    normalized_source_id,
                    source_record_id,
                ),
            )
            if not cursor.rowcount:
                continue

            inserted += 1
            place_rowid = int(cursor.lastrowid)
            linked_categories = False

            if basic_id:
                db.execute(
                    """
                    INSERT OR IGNORE INTO place_categories
                    (place_rowid, category_id, relation, ordinal)
                    VALUES (?, ?, ?, 0)
                    """,
                    (place_rowid, basic_id, CATEGORY_RELATION_BASIC),
                )
                linked_categories = True

            for ordinal, category in enumerate(hierarchy):
                cid = category_id(category)
                if not cid:
                    continue
                db.execute(
                    """
                    INSERT OR IGNORE INTO place_categories
                    (place_rowid, category_id, relation, ordinal)
                    VALUES (?, ?, ?, ?)
                    """,
                    (place_rowid, cid, CATEGORY_RELATION_HIERARCHY, ordinal),
                )
                linked_categories = True

            for ordinal, category in enumerate(alternates):
                cid = category_id(category)
                if not cid:
                    continue
                db.execute(
                    """
                    INSERT OR IGNORE INTO place_categories
                    (place_rowid, category_id, relation, ordinal)
                    VALUES (?, ?, ?, ?)
                    """,
                    (place_rowid, cid, CATEGORY_RELATION_ALTERNATE, ordinal),
                )
                linked_categories = True

            if linked_categories:
                categorized_records += 1
            if freeform or postcode or locality or region or country:
                structured_address_records += 1
            if normalized_source_id or source_record_id:
                source_identified_records += 1

            if inserted % 5000 == 0:
                db.commit()

    input_path = Path(args.input)
    source_input_sha256 = sha256_file(input_path)
    db.executemany(
        "INSERT INTO meta(key, value) VALUES (?, ?)",
        [
            ("region_id", args.region_id),
            ("source", "Overture Maps Foundation Places"),
            ("schema", DATABASE_SCHEMA),
            ("record_count", str(inserted)),
            ("source_release", args.source_release.strip() or "unknown"),
            ("source_client", "overturemaps"),
            ("source_client_version", args.source_client_version.strip() or "unknown"),
            ("source_input_sha256", source_input_sha256),
            ("search_enrichment_schema", ENRICHMENT_SCHEMA),
            ("enhanced_runtime_contract", ENHANCED_RUNTIME_CONTRACT),
            ("categorized_record_count", str(categorized_records)),
            ("structured_address_record_count", str(structured_address_records)),
            ("source_identified_record_count", str(source_identified_records)),
        ],
    )
    db.commit()
    db.execute("ANALYZE")
    db.execute("VACUUM")
    db.close()
    print(
        f"Wrote {inserted} Overture places to {output} "
        f"(categorized={categorized_records}, structuredAddress={structured_address_records}, "
        f"sourceIdentified={source_identified_records})"
    )


if __name__ == "__main__":
    main()
