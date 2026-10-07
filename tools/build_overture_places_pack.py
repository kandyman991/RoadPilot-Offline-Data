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


def compact_json(values: list[str]) -> str:
    return json.dumps(values, ensure_ascii=False, separators=(",", ":"))


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


def taxonomy_fields(props: dict) -> tuple[str, str, list[str], list[str], str]:
    basic_category = clean(props.get("basic_category"))
    taxonomy = props.get("taxonomy")
    if not isinstance(taxonomy, dict):
        taxonomy = {}

    primary = clean(taxonomy.get("primary"))
    hierarchy = clean_list(taxonomy.get("hierarchy"))
    alternates = clean_list(taxonomy.get("alternates"))

    # Older Overture inputs may still contain the deprecated categories object.
    # Keeping this fallback makes retained/replay builds possible while September
    # 2026+ production data uses basic_category + taxonomy.
    legacy = props.get("categories")
    if isinstance(legacy, dict):
        if not primary:
            primary = clean(legacy.get("primary"))
        if not alternates:
            alternates = clean_list(legacy.get("alternate"))

    if primary and primary not in hierarchy:
        hierarchy.append(primary)

    category_terms: list[str] = []
    for value in [basic_category, primary, *hierarchy, *alternates]:
        normalized = normalize(value)
        if normalized and normalized not in category_terms:
            category_terms.append(normalized)

    return basic_category, primary, hierarchy, alternates, " ".join(category_terms)


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
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
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
            postcode TEXT NOT NULL,
            locality TEXT NOT NULL,
            locality_norm TEXT NOT NULL,
            region TEXT NOT NULL,
            country TEXT NOT NULL,
            operating_status TEXT NOT NULL,
            basic_category TEXT NOT NULL,
            taxonomy_primary TEXT NOT NULL,
            taxonomy_hierarchy TEXT NOT NULL,
            taxonomy_alternates TEXT NOT NULL,
            category_norm TEXT NOT NULL,
            source_provider TEXT NOT NULL,
            source_dataset TEXT NOT NULL,
            source_record_id TEXT NOT NULL,
            source_version TEXT NOT NULL
        );
        CREATE INDEX idx_places_name_norm ON places(name_norm);
        CREATE INDEX idx_places_category_norm ON places(category_norm);
        CREATE INDEX idx_places_locality_norm ON places(locality_norm);
        CREATE INDEX idx_places_lat_lon ON places(latitude, longitude);
        """
    )

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
            operating_status = clean(props.get("operating_status"))
            (
                basic_category,
                taxonomy_primary,
                taxonomy_hierarchy,
                taxonomy_alternates,
                category_norm,
            ) = taxonomy_fields(props)
            (
                source_provider,
                source_dataset,
                source_record_id,
                source_version,
            ) = preferred_source(props)

            cursor = db.execute(
                """
                INSERT OR IGNORE INTO places (
                    id, name, name_norm, address, address_norm,
                    latitude, longitude, confidence,
                    freeform, postcode, locality, locality_norm, region, country,
                    operating_status, basic_category, taxonomy_primary,
                    taxonomy_hierarchy, taxonomy_alternates, category_norm,
                    source_provider, source_dataset, source_record_id, source_version
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
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
                    postcode,
                    locality,
                    normalize(locality),
                    region,
                    country,
                    operating_status,
                    basic_category,
                    taxonomy_primary,
                    compact_json(taxonomy_hierarchy),
                    compact_json(taxonomy_alternates),
                    category_norm,
                    source_provider,
                    source_dataset,
                    source_record_id,
                    source_version,
                ),
            )
            if cursor.rowcount:
                inserted += 1
                if category_norm:
                    categorized_records += 1
                if freeform or postcode or locality or region or country:
                    structured_address_records += 1
                if source_provider or source_dataset or source_record_id:
                    source_identified_records += 1

            if inserted and inserted % 5000 == 0:
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
