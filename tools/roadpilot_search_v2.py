#!/usr/bin/env python3
"""RoadPilot enriched offline search contract for Graph Studio and future runtimes.

The v2 contract is additive: the SQLite database retains the Android-compatible
roadpilot-overture-v1 base columns while exposing structured address, current
Overture taxonomy/source fields, category filtering and optional proximity
ranking.
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from roadpilot_search_v1 import normalize

ENRICHMENT_SCHEMA = "roadpilot-search-enrichment-v2"
RUNTIME_CONTRACT = "roadpilot-search-v2"
MAX_QUERY_TOKENS = 6
GLOBAL_RAW_LIMIT = 900
LOCAL_RAW_LIMIT = 3000
LOCAL_RADIUS_KM = 150.0


@dataclass(frozen=True)
class EnhancedCandidate:
    id: str
    title: str
    address: str
    latitude: float
    longitude: float
    confidence: float
    freeform: str
    postcode: str
    locality: str
    region: str
    country: str
    operatingStatus: str
    basicCategory: str
    taxonomyPrimary: str
    taxonomyHierarchy: list[str]
    taxonomyAlternates: list[str]
    sourceProvider: str
    sourceDataset: str
    sourceRecordId: str
    sourceVersion: str


@dataclass(frozen=True)
class RankedEnhancedCandidate:
    id: str
    title: str
    address: str
    latitude: float
    longitude: float
    confidence: float
    freeform: str
    postcode: str
    locality: str
    region: str
    country: str
    operatingStatus: str
    basicCategory: str
    taxonomyPrimary: str
    taxonomyHierarchy: list[str]
    taxonomyAlternates: list[str]
    sourceProvider: str
    sourceDataset: str
    sourceRecordId: str
    sourceVersion: str
    distanceMeters: float | None
    score: int
    scoreConfidence: int
    scoreExact: int
    scorePrefix: int
    scoreContains: int
    scoreBrandFirst: int
    scoreTokenMatches: int
    scoreCategory: int
    scoreProximity: int


def _json_list(value: str) -> list[str]:
    try:
        parsed = json.loads(value or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed if str(item).strip()]


def _tokens(query: str) -> list[str]:
    result: list[str] = []
    for token in normalize(query).split(" "):
        if len(token) < 2 or token in result:
            continue
        result.append(token)
        if len(result) >= MAX_QUERY_TOKENS:
            break
    return result


def _haversine_meters(
    lat_a: float,
    lng_a: float,
    lat_b: float,
    lng_b: float,
) -> float:
    radius = 6_371_008.8
    phi_a = math.radians(lat_a)
    phi_b = math.radians(lat_b)
    d_phi = math.radians(lat_b - lat_a)
    d_lambda = math.radians(lng_b - lng_a)
    value = (
        math.sin(d_phi / 2.0) ** 2
        + math.cos(phi_a) * math.cos(phi_b) * math.sin(d_lambda / 2.0) ** 2
    )
    return 2.0 * radius * math.asin(min(1.0, math.sqrt(value)))


def _validate_enrichment(connection: sqlite3.Connection) -> None:
    metadata = dict(connection.execute("SELECT key, value FROM meta").fetchall())
    actual = metadata.get("search_enrichment_schema")
    if actual != ENRICHMENT_SCHEMA:
        raise ValueError(
            f"Search database does not expose {ENRICHMENT_SCHEMA}: {actual!r}"
        )


def _candidate_from_row(row: tuple[Any, ...]) -> EnhancedCandidate | None:
    latitude = float(row[3])
    longitude = float(row[4])
    if not math.isfinite(latitude) or not math.isfinite(longitude):
        return None
    return EnhancedCandidate(
        id=str(row[0]),
        title=str(row[1]),
        address=str(row[2]),
        latitude=latitude,
        longitude=longitude,
        confidence=float(row[5]),
        freeform=str(row[6]),
        postcode=str(row[7]),
        locality=str(row[8]),
        region=str(row[9]),
        country=str(row[10]),
        operatingStatus=str(row[11]),
        basicCategory=str(row[12]),
        taxonomyPrimary=str(row[13]),
        taxonomyHierarchy=_json_list(str(row[14])),
        taxonomyAlternates=_json_list(str(row[15])),
        sourceProvider=str(row[16]),
        sourceDataset=str(row[17]),
        sourceRecordId=str(row[18]),
        sourceVersion=str(row[19]),
    )


def _where_clause(query: str, category: str) -> tuple[str, list[Any], str]:
    normalized_query = normalize(query)
    tokens = _tokens(query)
    normalized_category = normalize(category)

    clauses = ["operating_status <> 'permanently_closed'"]
    params: list[Any] = []

    if normalized_query:
        terms = tokens or [normalized_query]
        text_clauses = []
        for token in terms:
            term = f"%{token}%"
            text_clauses.append(
                "(name_norm LIKE ? OR address_norm LIKE ? OR "
                "locality_norm LIKE ? OR category_norm LIKE ?)"
            )
            params.extend([term, term, term, term])
        clauses.append("(" + " OR ".join(text_clauses) + ")")

    if normalized_category:
        clauses.append("category_norm LIKE ?")
        params.append(f"%{normalized_category}%")

    return " AND ".join(clauses), params, normalized_query


def _select_sql(where: str) -> str:
    return f"""
        SELECT
            id, name, address, latitude, longitude, confidence,
            freeform, postcode, locality, region, country, operating_status,
            basic_category, taxonomy_primary, taxonomy_hierarchy,
            taxonomy_alternates, source_provider, source_dataset,
            source_record_id, source_version
        FROM places
        WHERE {where}
    """


def query_database(
    database: Path,
    query: str = "",
    *,
    category: str = "",
    origin_lat: float | None = None,
    origin_lng: float | None = None,
) -> list[EnhancedCandidate]:
    normalized_query = normalize(query)
    normalized_category = normalize(category)
    if not normalized_query and not normalized_category:
        return []
    if normalized_query and len(normalized_query) < 2 and not normalized_category:
        return []
    if (origin_lat is None) != (origin_lng is None):
        raise ValueError("origin_lat and origin_lng must be supplied together")
    if origin_lat is not None and not (-90.0 <= origin_lat <= 90.0):
        raise ValueError("origin_lat is invalid")
    if origin_lng is not None and not (-180.0 <= origin_lng <= 180.0):
        raise ValueError("origin_lng is invalid")

    where, params, normalized_query = _where_clause(query, category)
    first_token = (_tokens(query) or [normalized_query or ""])[0]

    connection = sqlite3.connect(database)
    try:
        _validate_enrichment(connection)
        rows: list[tuple[Any, ...]] = []

        if origin_lat is not None and origin_lng is not None:
            lat_span = LOCAL_RADIUS_KM / 111.32
            cos_lat = max(0.15, math.cos(math.radians(origin_lat)))
            lng_span = LOCAL_RADIUS_KM / (111.32 * cos_lat)
            local_where = (
                f"{where} AND latitude BETWEEN ? AND ? "
                "AND longitude BETWEEN ? AND ?"
            )
            local_params = [
                *params,
                origin_lat - lat_span,
                origin_lat + lat_span,
                origin_lng - lng_span,
                origin_lng + lng_span,
                origin_lat,
                origin_lat,
                origin_lng,
                origin_lng,
            ]
            rows.extend(
                connection.execute(
                    _select_sql(local_where)
                    + """
                    ORDER BY
                        ((latitude - ?) * (latitude - ?))
                        + ((longitude - ?) * (longitude - ?)) ASC,
                        confidence DESC
                    LIMIT ?
                    """,
                    [*local_params, LOCAL_RAW_LIMIT],
                ).fetchall()
            )

        global_params = list(params)
        if normalized_query:
            global_sql = (
                _select_sql(where)
                + """
                ORDER BY
                    CASE
                        WHEN name_norm = ? THEN 0
                        WHEN name_norm LIKE ? THEN 1
                        ELSE 2
                    END,
                    confidence DESC
                LIMIT ?
                """
            )
            global_params.extend([first_token, f"{first_token}%", GLOBAL_RAW_LIMIT])
        else:
            global_sql = _select_sql(where) + " ORDER BY confidence DESC LIMIT ?"
            global_params.append(GLOBAL_RAW_LIMIT)
        rows.extend(connection.execute(global_sql, global_params).fetchall())
    finally:
        connection.close()

    result: list[EnhancedCandidate] = []
    seen: set[str] = set()
    for row in rows:
        candidate = _candidate_from_row(row)
        if candidate is None or candidate.id in seen:
            continue
        seen.add(candidate.id)
        result.append(candidate)
    return result


def _score(
    query: str,
    category: str,
    candidate: EnhancedCandidate,
    origin_lat: float | None,
    origin_lng: float | None,
) -> RankedEnhancedCandidate:
    query_text = normalize(query)
    ordered_query_tokens = _tokens(query)
    query_tokens = set(ordered_query_tokens)
    first_token = ordered_query_tokens[0] if ordered_query_tokens else None

    title = normalize(candidate.title)
    combined = f"{title} {normalize(candidate.address)}"
    candidate_tokens = set(combined.split(" "))

    score_confidence = int(max(0.0, min(1.0, candidate.confidence)) * 100.0)
    score_exact = 4000 if query_text and title == query_text else 0
    score_prefix = 2000 if query_text and title.startswith(query_text) else 0
    score_contains = 1000 if query_text and query_text in title else 0
    score_brand_first = (
        2500
        if len(ordered_query_tokens) > 1 and first_token is not None and title == first_token
        else 0
    )
    score_token_matches = (
        len(query_tokens.intersection(candidate_tokens)) * 250 if query_tokens else 0
    )

    requested_category = normalize(category)
    basic = normalize(candidate.basicCategory)
    primary = normalize(candidate.taxonomyPrimary)
    hierarchy = {normalize(item) for item in candidate.taxonomyHierarchy}
    alternates = {normalize(item) for item in candidate.taxonomyAlternates}
    if not requested_category:
        score_category = 0
    elif requested_category in {basic, primary}:
        score_category = 1800
    elif requested_category in hierarchy:
        score_category = 1500
    elif requested_category in alternates:
        score_category = 1300
    else:
        score_category = 1000

    distance_meters: float | None = None
    score_proximity = 0
    if origin_lat is not None and origin_lng is not None:
        distance_meters = _haversine_meters(
            origin_lat,
            origin_lng,
            candidate.latitude,
            candidate.longitude,
        )
        distance_km = distance_meters / 1000.0
        score_proximity = max(0, 900 - int(min(distance_km, 100.0) * 9.0))

    total = (
        score_confidence
        + score_exact
        + score_prefix
        + score_contains
        + score_brand_first
        + score_token_matches
        + score_category
        + score_proximity
    )
    return RankedEnhancedCandidate(
        id=candidate.id,
        title=candidate.title,
        address=candidate.address,
        latitude=candidate.latitude,
        longitude=candidate.longitude,
        confidence=candidate.confidence,
        freeform=candidate.freeform,
        postcode=candidate.postcode,
        locality=candidate.locality,
        region=candidate.region,
        country=candidate.country,
        operatingStatus=candidate.operatingStatus,
        basicCategory=candidate.basicCategory,
        taxonomyPrimary=candidate.taxonomyPrimary,
        taxonomyHierarchy=candidate.taxonomyHierarchy,
        taxonomyAlternates=candidate.taxonomyAlternates,
        sourceProvider=candidate.sourceProvider,
        sourceDataset=candidate.sourceDataset,
        sourceRecordId=candidate.sourceRecordId,
        sourceVersion=candidate.sourceVersion,
        distanceMeters=distance_meters,
        score=total,
        scoreConfidence=score_confidence,
        scoreExact=score_exact,
        scorePrefix=score_prefix,
        scoreContains=score_contains,
        scoreBrandFirst=score_brand_first,
        scoreTokenMatches=score_token_matches,
        scoreCategory=score_category,
        scoreProximity=score_proximity,
    )


def rank(
    query: str,
    category: str,
    candidates: list[EnhancedCandidate],
    *,
    origin_lat: float | None = None,
    origin_lng: float | None = None,
    limit: int = 8,
) -> list[RankedEnhancedCandidate]:
    scored = [
        _score(query, category, candidate, origin_lat, origin_lng)
        for candidate in candidates
    ]
    scored.sort(
        key=lambda item: (
            item.score,
            item.confidence,
            -(item.distanceMeters if item.distanceMeters is not None else math.inf),
        ),
        reverse=True,
    )
    return scored[: max(1, min(int(limit), 50))]


def search(
    database: Path,
    query: str = "",
    *,
    category: str = "",
    origin_lat: float | None = None,
    origin_lng: float | None = None,
    limit: int = 8,
) -> list[RankedEnhancedCandidate]:
    return rank(
        query,
        category,
        query_database(
            database,
            query,
            category=category,
            origin_lat=origin_lat,
            origin_lng=origin_lng,
        ),
        origin_lat=origin_lat,
        origin_lng=origin_lng,
        limit=limit,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--query", default="")
    parser.add_argument("--category", default="")
    parser.add_argument("--origin-lat", type=float)
    parser.add_argument("--origin-lng", type=float)
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if not args.database.is_file():
        raise SystemExit(f"Database does not exist: {args.database}")
    if not args.query.strip() and not args.category.strip():
        raise SystemExit("Provide --query and/or --category")

    try:
        results = search(
            args.database,
            args.query,
            category=args.category,
            origin_lat=args.origin_lat,
            origin_lng=args.origin_lng,
            limit=args.limit,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    payload: list[dict[str, Any]] = [asdict(item) for item in results]
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        for index, item in enumerate(payload, start=1):
            distance = item["distanceMeters"]
            distance_text = "" if distance is None else f" distance={distance:.0f}m"
            print(
                f"{index}. {item['title']} | {item['address']} | "
                f"category={item['basicCategory'] or item['taxonomyPrimary']} "
                f"score={item['score']}{distance_text}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
