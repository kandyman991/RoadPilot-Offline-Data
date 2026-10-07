#!/usr/bin/env python3
"""Graph Studio inspection helpers for retained RoadPilot search databases."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

from roadpilot_search_v1 import normalize

MAX_OVERLAY = 5000
MAX_DIFF_POINTS = 1000


def connect(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise SystemExit(f"Search database does not exist: {path}")
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    metadata = dict(db.execute("SELECT key, value FROM meta").fetchall())
    if metadata.get("search_enrichment_schema") != "roadpilot-search-enrichment-v2":
        db.close()
        raise SystemExit("Graph Studio inspection requires roadpilot-search-enrichment-v2")
    return db


def category_catalog(database: Path, contains: str) -> list[dict[str, Any]]:
    db = connect(database)
    try:
        needle = normalize(contains)
        params: list[Any] = []
        where = ""
        if needle:
            where = "WHERE c.name_norm LIKE ?"
            params.append(f"%{needle}%")
        rows = db.execute(
            f"""
            SELECT c.name, c.name_norm, COUNT(DISTINCT pc.place_rowid) AS place_count
            FROM search_categories c
            JOIN place_categories pc ON pc.category_id = c.id
            {where}
            GROUP BY c.id, c.name, c.name_norm
            ORDER BY place_count DESC, c.name ASC
            LIMIT 1000
            """,
            params,
        ).fetchall()
        return [
            {
                "name": str(row["name"]),
                "normalized": str(row["name_norm"]),
                "placeCount": int(row["place_count"]),
            }
            for row in rows
        ]
    finally:
        db.close()


def overlay(
    database: Path,
    categories: list[str],
    min_lat: float,
    min_lng: float,
    max_lat: float,
    max_lng: float,
    limit: int,
) -> list[dict[str, Any]]:
    if min_lat > max_lat or min_lng > max_lng:
        raise SystemExit("Invalid overlay bounds")
    db = connect(database)
    try:
        normalized = [normalize(value) for value in categories if normalize(value)]
        if not normalized:
            return []
        placeholders = ",".join("?" for _ in normalized)
        category_ids = [
            int(row["id"])
            for row in db.execute(
                f"SELECT id FROM search_categories WHERE name_norm IN ({placeholders})",
                normalized,
            ).fetchall()
        ]
        if not category_ids:
            return []
        id_placeholders = ",".join("?" for _ in category_ids)
        rows = db.execute(
            f"""
            SELECT
                p.id,
                p.name,
                p.address,
                p.latitude,
                p.longitude,
                p.confidence,
                COALESCE(basic.name, '') AS basic_category,
                COALESCE(primary_category.name, '') AS taxonomy_primary
            FROM places p
            LEFT JOIN search_categories basic ON basic.id = p.basic_category_id
            LEFT JOIN search_categories primary_category ON primary_category.id = p.taxonomy_primary_id
            WHERE p.operating_status <> 'permanently_closed'
              AND p.latitude BETWEEN ? AND ?
              AND p.longitude BETWEEN ? AND ?
              AND p.rowid IN (
                  SELECT pc.place_rowid
                  FROM place_categories pc
                  WHERE pc.category_id IN ({id_placeholders})
              )
            ORDER BY p.confidence DESC, p.id ASC
            LIMIT ?
            """,
            [
                min_lat,
                max_lat,
                min_lng,
                max_lng,
                *category_ids,
                max(1, min(int(limit), MAX_OVERLAY)),
            ],
        ).fetchall()
        return [
            {
                "id": str(row["id"]),
                "title": str(row["name"]),
                "address": str(row["address"]),
                "latitude": float(row["latitude"]),
                "longitude": float(row["longitude"]),
                "confidence": float(row["confidence"]),
                "basicCategory": str(row["basic_category"]),
                "taxonomyPrimary": str(row["taxonomy_primary"]),
            }
            for row in rows
        ]
    finally:
        db.close()


def category_counts(db: sqlite3.Connection, prefix: str = "") -> dict[str, int]:
    table_prefix = f"{prefix}." if prefix else ""
    rows = db.execute(
        f"""
        SELECT c.name, COUNT(DISTINCT pc.place_rowid) AS place_count
        FROM {table_prefix}search_categories c
        JOIN {table_prefix}place_categories pc ON pc.category_id = c.id
        GROUP BY c.id, c.name
        """
    ).fetchall()
    return {str(row[0]): int(row[1]) for row in rows}


def compare(database_a: Path, database_b: Path, point_limit: int) -> dict[str, Any]:
    db = connect(database_a)
    try:
        db.execute("ATTACH DATABASE ? AS other", (str(database_b),))
        other_meta = dict(db.execute("SELECT key, value FROM other.meta").fetchall())
        if other_meta.get("search_enrichment_schema") != "roadpilot-search-enrichment-v2":
            raise SystemExit("Comparison build B is not roadpilot-search-enrichment-v2")

        count_a = int(db.execute("SELECT COUNT(*) FROM places").fetchone()[0])
        count_b = int(db.execute("SELECT COUNT(*) FROM other.places").fetchone()[0])
        added = int(
            db.execute(
                """
                SELECT COUNT(*)
                FROM other.places b
                LEFT JOIN places a ON a.id = b.id
                WHERE a.id IS NULL
                """
            ).fetchone()[0]
        )
        removed = int(
            db.execute(
                """
                SELECT COUNT(*)
                FROM places a
                LEFT JOIN other.places b ON b.id = a.id
                WHERE b.id IS NULL
                """
            ).fetchone()[0]
        )

        stable_difference = """
            a.name <> b.name
            OR a.address <> b.address
            OR a.latitude <> b.latitude
            OR a.longitude <> b.longitude
            OR a.confidence <> b.confidence
            OR a.operating_status <> b.operating_status
            OR COALESCE(abc.name, '') <> COALESCE(bbc.name, '')
            OR COALESCE(apc.name, '') <> COALESCE(bpc.name, '')
            OR COALESCE(aa.postcode, '') <> COALESCE(ba.postcode, '')
            OR COALESCE(aa.locality, '') <> COALESCE(ba.locality, '')
            OR COALESCE(aa.region, '') <> COALESCE(ba.region, '')
            OR COALESCE(aa.country, '') <> COALESCE(ba.country, '')
            OR COALESCE(asrc.provider, '') <> COALESCE(bsrc.provider, '')
            OR COALESCE(asrc.dataset, '') <> COALESCE(bsrc.dataset, '')
            OR a.source_record_id <> b.source_record_id
        """
        changed_join = f"""
            FROM places a
            JOIN other.places b ON b.id = a.id
            LEFT JOIN search_categories abc ON abc.id = a.basic_category_id
            LEFT JOIN other.search_categories bbc ON bbc.id = b.basic_category_id
            LEFT JOIN search_categories apc ON apc.id = a.taxonomy_primary_id
            LEFT JOIN other.search_categories bpc ON bpc.id = b.taxonomy_primary_id
            LEFT JOIN address_contexts aa ON aa.id = a.address_context_id
            LEFT JOIN other.address_contexts ba ON ba.id = b.address_context_id
            LEFT JOIN search_sources asrc ON asrc.id = a.source_id
            LEFT JOIN other.search_sources bsrc ON bsrc.id = b.source_id
            WHERE {stable_difference}
        """
        changed = int(
            db.execute(f"SELECT COUNT(*) {changed_join}").fetchone()[0]
        )

        limit = max(1, min(int(point_limit), MAX_DIFF_POINTS))
        points: list[dict[str, Any]] = []

        for row in db.execute(
            """
            SELECT b.id, b.name, b.latitude, b.longitude
            FROM other.places b
            LEFT JOIN places a ON a.id = b.id
            WHERE a.id IS NULL
            ORDER BY b.id
            LIMIT ?
            """,
            (limit,),
        ).fetchall():
            points.append(
                {
                    "status": "added",
                    "id": str(row[0]),
                    "title": str(row[1]),
                    "latitude": float(row[2]),
                    "longitude": float(row[3]),
                }
            )

        remaining = max(0, limit - len(points))
        if remaining:
            for row in db.execute(
                """
                SELECT a.id, a.name, a.latitude, a.longitude
                FROM places a
                LEFT JOIN other.places b ON b.id = a.id
                WHERE b.id IS NULL
                ORDER BY a.id
                LIMIT ?
                """,
                (remaining,),
            ).fetchall():
                points.append(
                    {
                        "status": "removed",
                        "id": str(row[0]),
                        "title": str(row[1]),
                        "latitude": float(row[2]),
                        "longitude": float(row[3]),
                    }
                )

        remaining = max(0, limit - len(points))
        if remaining:
            for row in db.execute(
                f"""
                SELECT b.id, b.name, b.latitude, b.longitude
                {changed_join}
                ORDER BY b.id
                LIMIT ?
                """,
                (remaining,),
            ).fetchall():
                points.append(
                    {
                        "status": "changed",
                        "id": str(row[0]),
                        "title": str(row[1]),
                        "latitude": float(row[2]),
                        "longitude": float(row[3]),
                    }
                )

        counts_a = category_counts(db)
        counts_b = category_counts(db, "other")
        category_names = sorted(set(counts_a) | set(counts_b))
        category_changes = [
            {
                "category": name,
                "countA": counts_a.get(name, 0),
                "countB": counts_b.get(name, 0),
                "delta": counts_b.get(name, 0) - counts_a.get(name, 0),
            }
            for name in category_names
            if counts_a.get(name, 0) != counts_b.get(name, 0)
        ]
        category_changes.sort(key=lambda item: (-abs(item["delta"]), item["category"]))

        return {
            "countA": count_a,
            "countB": count_b,
            "countDelta": count_b - count_a,
            "added": added,
            "removed": removed,
            "changed": changed,
            "categoryChanges": category_changes[:250],
            "points": points,
            "pointsTruncated": added + removed + changed > len(points),
        }
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    categories_parser = subparsers.add_parser("categories")
    categories_parser.add_argument("--database", required=True, type=Path)
    categories_parser.add_argument("--contains", default="")

    overlay_parser = subparsers.add_parser("overlay")
    overlay_parser.add_argument("--database", required=True, type=Path)
    overlay_parser.add_argument("--category", action="append", default=[])
    overlay_parser.add_argument("--min-lat", required=True, type=float)
    overlay_parser.add_argument("--min-lng", required=True, type=float)
    overlay_parser.add_argument("--max-lat", required=True, type=float)
    overlay_parser.add_argument("--max-lng", required=True, type=float)
    overlay_parser.add_argument("--limit", type=int, default=2000)

    compare_parser = subparsers.add_parser("compare")
    compare_parser.add_argument("--database-a", required=True, type=Path)
    compare_parser.add_argument("--database-b", required=True, type=Path)
    compare_parser.add_argument("--point-limit", type=int, default=1000)

    args = parser.parse_args()
    if args.command == "categories":
        payload = category_catalog(args.database, args.contains)
    elif args.command == "overlay":
        payload = overlay(
            args.database,
            args.category,
            args.min_lat,
            args.min_lng,
            args.max_lat,
            args.max_lng,
            args.limit,
        )
    else:
        payload = compare(args.database_a, args.database_b, args.point_limit)
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
