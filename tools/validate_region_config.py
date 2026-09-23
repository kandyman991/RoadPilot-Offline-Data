#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path

SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")
SAFE_FILE = re.compile(r"^[A-Za-z0-9._-]+$")

def fail(message: str) -> None:
    raise SystemExit(message)

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    path = Path(args.config)
    config = json.loads(path.read_text(encoding="utf-8"))

    if config.get("schemaVersion") != 1:
        fail("region config schemaVersion must be 1")

    region_id = str(config.get("id") or "")
    if not SAFE_ID.fullmatch(region_id):
        fail("invalid region id")

    overture = config.get("overture")
    if not isinstance(overture, dict) or overture.get("enabled") is not True:
        fail("overture.enabled must be true for an Overture build config")

    if overture.get("databaseSchema") != "roadpilot-overture-v1":
        fail("unexpected Overture database schema")

    file_name = str(overture.get("fileName") or "")
    manifest_name = str(overture.get("manifestFileName") or "")
    if not SAFE_FILE.fullmatch(file_name) or not file_name.endswith(".sqlite"):
        fail("invalid Overture SQLite file name")
    if not SAFE_FILE.fullmatch(manifest_name) or not manifest_name.endswith(".json"):
        fail("invalid Overture manifest file name")

    coverage = overture.get("coverage")
    if not isinstance(coverage, dict):
        fail("coverage is required")

    try:
        min_lat = float(coverage["minLat"])
        max_lat = float(coverage["maxLat"])
        min_lng = float(coverage["minLng"])
        max_lng = float(coverage["maxLng"])
    except (KeyError, TypeError, ValueError):
        fail("coverage must contain numeric min/max latitude/longitude")

    if not (-90 <= min_lat < max_lat <= 90):
        fail("invalid latitude coverage")
    if not (-180 <= min_lng < max_lng <= 180):
        fail("invalid longitude coverage")

    country = str(overture.get("country") or "")
    if len(country) != 2 or not country.isalpha():
        fail("country must be a two-letter code")

    validations = overture.get("validation")
    if not isinstance(validations, list) or not validations:
        fail("at least one validation target is required")

    print(f"{region_id}: region config is valid")

if __name__ == "__main__":
    main()
