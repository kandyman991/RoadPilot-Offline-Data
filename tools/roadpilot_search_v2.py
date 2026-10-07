#!/usr/bin/env python3
"""RoadPilot enriched offline search contract for Graph Studio and future runtimes.

The v2 contract is additive: the SQLite file keeps the Android-compatible
roadpilot-overture-v1 base columns while normalized companion tables retain
structured address, current Overture taxonomy/source identity, category
filtering and optional proximity ranking.
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

from roadpilot_search_v1 import normalize

ENRICHMENT_SCHEMA = "roadpilot-search-enrichment-v2"
RUNTIME_CONTRACT = "roadpilot-search-v2"
MAX_QUERY_TOKENS = 6
GLOBAL_RAW_LIMIT = 900
LOCAL_RAW_LIMIT = 3000
LOCAL_RADIUS_KM = 150.0

CATEGORY_RELATION_BASIC = 0
CATEGORY_RELATION_HIERARCHY = 1
CATEGORY_RELATION_ALTERNATE = 2


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


def _resolve_category_ids(
    connection: sqlite3.Connection,
    category: str,
) -> list[int]:
    normalized = normalize(category)
    if not normalized:
        return []
    return [
        int(row[0])
        for row in connection.execute(
            "SELECT id FROM search_categories WHERE name_norm = ? ORDER BY id",
            (normalized,),
        ).fetchall()
    ]


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
        basicCategory=str(row[12] or ""),
        taxonomyPrimary=str(row[13] or ""),
        taxonomyHierarchy=[],
        taxonomyAlternates=[],
        sourceProvider=str(row[14] or ""),
        sourceDataset=str(row[15] or ""),
        sourceRecordId=str(row[16] or ""),
        sourceVersion=str(row[17] or ""),
    )


def _text_clause(query: str) -> tuple[str | None, list[Any], str]:
    normalized_query = normalize(query)
    if not normalized_query:
        return None, [], ""
    terms = _tokens(query) or [normalized_query]
    clauses: list[str] = []
    params: list[Any] = []
    for token in terms:
        term = f"%{token}%"
        clauses.append("(p.name_norm LIKE ? OR p.address_norm LIKE ?)")
        params.extend([term, term])
    return "(" + " OR ".join(clauses) + ")", params, normalized_query


def _where_clause(
    query: str,
    category_ids: list[int],
) -> tuple[str, list[Any], str]:
    clauses = ["p.operating_status <> 'permanently_closed'"]
    params: list[Any] = []

    text_clause, text_params, normalized_query = _text_clause(query)
    if text_clause:
        clauses.append(text_clause)
        params.extend(text_params)

    if category_ids:
        placeholders = ",".join("?" for _ in category_ids)
        clauses.append(
            "p.rowid IN ("
            "SELECT pc.place_rowid FROM place_categories pc "
            f"WHERE pc.category_id IN ({placeholders})"
            ")"
        )
        params.extend(category_ids)

    return " AND ".join(clauses), params, normalized_query


def _select_sql(where: str) -> str:
    return f"""
        SELECT
            p.id, p.name, p.address, p.latitude, p.longitude, p.confidence,
            p.freeform,
            COALESCE(ac.postcode, ''),
            COALESCE(ac.locality, ''),
            COALESCE(ac.region, ''),
            COALESCE(ac.country, ''),
            p.operating_status,
            COALESCE(basic.name, ''),
            COALESCE(primary_category.name, ''),
            COALESCE(source.provider, ''),
            COALESCE(source.dataset, ''),
            p.source_record_id,
            COALESCE(source.version, '')
        FROM places p
        LEFT JOIN address_contexts ac
            ON ac.id = p.address_context_id
        LEFT JOIN search_categories basic
            ON basic.id = p.basic_category_id
        LEFT JOIN search_categories primary_category
            ON primary_category.id = p.taxonomy_primary_id
        LEFT JOIN search_sources source
            ON source.id = p.source_id
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

    connection = sqlite3.connect(database)
    try:
        _validate_enrichment(connection)
        category_ids = _resolve_category_ids(connection, category)
        if normalized_category and not category_ids:
            return []

        where, params, normalized_query = _where_clause(query, category_ids)
        first_token = (_tokens(query) or [normalized_query or ""])[0]
        rows: list[tuple[Any, ...]] = []

        if origin_lat is not None and origin_lng is not None:
            lat_span = LOCAL_RADIUS_KM / 111.32
            cos_lat = max(0.15, math.cos(math.radians(origin_lat)))
            lng_span = LOCAL_RADIUS_KM / (111.32 * cos_lat)
            local_where = (
                f"{where} AND p.latitude BETWEEN ? AND ? "
                "AND p.longitude BETWEEN ? AND ?"
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
                LOCAL_RAW_LIMIT,
            ]
            rows.extend(
                connection.execute(
                    _select_sql(local_where)
                    + """
                    ORDER BY
                        ((p.latitude - ?) * (p.latitude - ?))
                        + ((p.longitude - ?) * (p.longitude - ?)) ASC,
                        p.confidence DESC
                    LIMIT ?
                    """,
                    local_params,
                ).fetchall()
            )

        global_params = list(params)
        if normalized_query:
            global_sql = (
                _select_sql(where)
                + """
                ORDER BY
                    CASE
                        WHEN p.name_norm = ? THEN 0
                        WHEN p.name_norm LIKE ? THEN 1
                        ELSE 2
                    END,
                    p.confidence DESC
                LIMIT ?
                """
            )
            global_params.extend([first_token, f"{first_token}%", GLOBAL_RAW_LIMIT])
        else:
            global_sql = _select_sql(where) + " ORDER BY p.confidence DESC LIMIT ?"
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
    if not requested_category:
        score_category = 0
    elif requested_category in {basic, primary}:
        score_category = 1800
    else:
        # query_database has already proven membership through the normalized
        # place_categories relation, so parent/alternate matches remain useful.
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
        taxonomyHierarchy=[],
        taxonomyAlternates=[],
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


def _hydrate_taxonomy(
    database: Path,
    ranked: list[RankedEnhancedCandidate],
) -> list[RankedEnhancedCandidate]:
    if not ranked:
        return ranked

    ids = [item.id for item in ranked]
    placeholders = ",".join("?" for _ in ids)
    connection = sqlite3.connect(database)
    try:
        rows = connection.execute(
            f"""
            SELECT p.id, c.name, pc.relation, pc.ordinal
            FROM places p
            JOIN place_categories pc ON pc.place_rowid = p.rowid
            JOIN search_categories c ON c.id = pc.category_id
            WHERE p.id IN ({placeholders})
              AND pc.relation IN (?, ?)
            ORDER BY p.id, pc.relation, pc.ordinal, c.name
            """,
            [*ids, CATEGORY_RELATION_HIERARCHY, CATEGORY_RELATION_ALTERNATE],
        ).fetchall()
    finally:
        connection.close()

    hierarchy: dict[str, list[str]] = {item.id: [] for item in ranked}
    alternates: dict[str, list[str]] = {item.id: [] for item in ranked}
    for place_id, name, relation, _ordinal in rows:
        target = (
            hierarchy[str(place_id)]
            if int(relation) == CATEGORY_RELATION_HIERARCHY
            else alternates[str(place_id)]
        )
        value = str(name)
        if value not in target:
            target.append(value)

    return [
        replace(
            item,
            taxonomyHierarchy=hierarchy[item.id],
            taxonomyAlternates=alternates[item.id],
        )
        for item in ranked
    ]


def search(
    database: Path,
    query: str = "",
    *,
    category: str = "",
    origin_lat: float | None = None,
    origin_lng: float | None = None,
    limit: int = 8,
) -> list[RankedEnhancedCandidate]:
    ranked = rank(
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
    return _hydrate_taxonomy(database, ranked)


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
