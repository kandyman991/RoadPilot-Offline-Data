#!/usr/bin/env python3
"""RoadPilot Overture/SQLite v1 query and ranking contract.

This mirrors OverturePlaceSearchService.kt so Offline-Data and Graph Studio can
exercise the same local database behavior Android consumes.
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

MAX_QUERY_TOKENS = 6
RAW_LIMIT = 240


@dataclass(frozen=True)
class Candidate:
    title: str
    address: str
    latitude: float
    longitude: float
    confidence: float


@dataclass(frozen=True)
class RankedCandidate:
    title: str
    address: str
    latitude: float
    longitude: float
    confidence: float
    score: int
    scoreConfidence: int
    scoreExact: int
    scorePrefix: int
    scoreContains: int
    scoreBrandFirst: int
    scoreTokenMatches: int


def normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", (value or "").lower())
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    mapped = "".join(ch if ch.isalnum() else " " for ch in stripped)
    return " ".join(mapped.split()).strip()


def query_database(database: Path, query: str) -> list[Candidate]:
    normalized_query = normalize(query)
    if len(normalized_query) < 2:
        return []

    tokens: list[str] = []
    for token in normalized_query.split(" "):
        if len(token) < 2 or token in tokens:
            continue
        tokens.append(token)
        if len(tokens) >= MAX_QUERY_TOKENS:
            break

    first_token = tokens[0] if tokens else normalized_query
    terms = tokens or [normalized_query]
    lookup_terms = [f"%{token}%" for token in terms]
    where = " OR ".join("(name_norm LIKE ? OR address_norm LIKE ?)" for _ in lookup_terms)
    params: list[str] = []
    for term in lookup_terms:
        params.extend([term, term])
    params.extend([first_token, f"{first_token}%"])

    connection = sqlite3.connect(database)
    try:
        rows = connection.execute(
            f"""
            SELECT name, address, latitude, longitude, confidence
            FROM places
            WHERE {where}
            ORDER BY
                CASE
                    WHEN name_norm = ? THEN 0
                    WHEN name_norm LIKE ? THEN 1
                    ELSE 2
                END,
                confidence DESC
            LIMIT {RAW_LIMIT}
            """,
            params,
        ).fetchall()
    finally:
        connection.close()

    result: list[Candidate] = []
    for name, address, latitude, longitude, confidence in rows:
        latitude = float(latitude)
        longitude = float(longitude)
        if not math.isfinite(latitude) or not math.isfinite(longitude):
            continue
        result.append(
            Candidate(
                title=str(name),
                address=str(address),
                latitude=latitude,
                longitude=longitude,
                confidence=float(confidence),
            )
        )
    return result


def _score(query: str, candidate: Candidate) -> RankedCandidate:
    query_text = normalize(query)
    ordered_query_tokens: list[str] = []
    for token in query_text.split(" "):
        if len(token) >= 2 and token not in ordered_query_tokens:
            ordered_query_tokens.append(token)
    query_tokens = set(ordered_query_tokens)
    first_token = ordered_query_tokens[0] if ordered_query_tokens else None

    title = normalize(candidate.title)
    combined = f"{title} {normalize(candidate.address)}"
    candidate_tokens = set(combined.split(" "))

    score_confidence = int(max(0.0, min(1.0, candidate.confidence)) * 100.0)
    score_exact = 4000 if title == query_text else 0
    score_prefix = 2000 if title.startswith(query_text) else 0
    score_contains = 1000 if query_text in title else 0
    score_brand_first = (
        2500
        if len(ordered_query_tokens) > 1 and first_token is not None and title == first_token
        else 0
    )
    score_token_matches = len(query_tokens.intersection(candidate_tokens)) * 250
    total = (
        score_confidence
        + score_exact
        + score_prefix
        + score_contains
        + score_brand_first
        + score_token_matches
    )
    return RankedCandidate(
        title=candidate.title,
        address=candidate.address,
        latitude=candidate.latitude,
        longitude=candidate.longitude,
        confidence=candidate.confidence,
        score=total,
        scoreConfidence=score_confidence,
        scoreExact=score_exact,
        scorePrefix=score_prefix,
        scoreContains=score_contains,
        scoreBrandFirst=score_brand_first,
        scoreTokenMatches=score_token_matches,
    )


def rank(query: str, candidates: list[Candidate], limit: int = 8) -> list[RankedCandidate]:
    seen: set[str] = set()
    unique: list[Candidate] = []
    for candidate in candidates:
        key = f"{normalize(candidate.title)}|{normalize(candidate.address)}"
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)

    scored = [_score(query, candidate) for candidate in unique]
    # Python's sort is stable, matching Kotlin's stable ordering for exact ties.
    scored.sort(key=lambda item: (item.score, item.confidence), reverse=True)
    return scored[: max(1, min(int(limit), 12))]


def search(database: Path, query: str, limit: int = 8) -> list[RankedCandidate]:
    return rank(query, query_database(database, query), limit=limit)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--query", required=True)
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if not args.database.is_file():
        raise SystemExit(f"Database does not exist: {args.database}")

    results = search(args.database, args.query, args.limit)
    payload: list[dict[str, Any]] = [asdict(item) for item in results]
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        for index, item in enumerate(payload, start=1):
            print(
                f"{index}. {item['title']} | {item['address']} | "
                f"score={item['score']} confidence={item['confidence']:.3f}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
