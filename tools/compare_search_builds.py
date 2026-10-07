#!/usr/bin/env python3
"""Compare two retained RoadPilot search SQLite artifacts."""

from __future__ import annotations
import argparse, json, sqlite3
from pathlib import Path

def counts(path: Path) -> dict:
    db = sqlite3.connect(path)
    try:
        place_count = int(db.execute("SELECT COUNT(*) FROM places").fetchone()[0])
        metadata = dict(db.execute("SELECT key, value FROM meta").fetchall())
        category_count = int(db.execute("SELECT COUNT(*) FROM search_categories").fetchone()[0])
        categorized = int(db.execute("SELECT COUNT(DISTINCT place_rowid) FROM place_categories").fetchone()[0])
        ids = {str(row[0]) for row in db.execute("SELECT id FROM places")}
        rows = {
            str(row[0]): (
                str(row[1]), str(row[2]), float(row[3]), float(row[4]),
                str(row[5] or ""), str(row[6] or "")
            )
            for row in db.execute(
                "SELECT id,name,address,latitude,longitude,source_record_id,operating_status FROM places"
            )
        }
        category_rows = {
            str(row[0]): int(row[1])
            for row in db.execute(
                """SELECT c.name, COUNT(DISTINCT pc.place_rowid)
                   FROM place_categories pc
                   JOIN search_categories c ON c.id=pc.category_id
                   GROUP BY c.name"""
            )
        }
        return {
            "placeCount": place_count,
            "categorizedPlaceCount": categorized,
            "categoryCount": category_count,
            "metadata": metadata,
            "ids": ids,
            "rows": rows,
            "categoryCounts": category_rows,
        }
    finally:
        db.close()

def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument("--a",required=True,type=Path)
    p.add_argument("--b",required=True,type=Path)
    args=p.parse_args()
    a,b=counts(args.a),counts(args.b)
    common=a["ids"] & b["ids"]
    changed=[i for i in common if a["rows"][i] != b["rows"][i]]
    categories=sorted(set(a["categoryCounts"]) | set(b["categoryCounts"]))
    payload={
        "placeCountA":a["placeCount"],"placeCountB":b["placeCount"],
        "placeCountDelta":b["placeCount"]-a["placeCount"],
        "categorizedPlaceCountA":a["categorizedPlaceCount"],
        "categorizedPlaceCountB":b["categorizedPlaceCount"],
        "addedCount":len(b["ids"]-a["ids"]),
        "removedCount":len(a["ids"]-b["ids"]),
        "changedCount":len(changed),
        "addedIds":sorted(b["ids"]-a["ids"])[:500],
        "removedIds":sorted(a["ids"]-b["ids"])[:500],
        "changedIds":sorted(changed)[:500],
        "categoryDeltas":[
            {"category":c,"a":a["categoryCounts"].get(c,0),"b":b["categoryCounts"].get(c,0),
             "delta":b["categoryCounts"].get(c,0)-a["categoryCounts"].get(c,0)}
            for c in categories if a["categoryCounts"].get(c,0)!=b["categoryCounts"].get(c,0)
        ][:500],
    }
    print(json.dumps(payload,ensure_ascii=False))
    return 0
if __name__=="__main__":
    raise SystemExit(main())
