#!/usr/bin/env python3
"""Inspect published RoadPilot routing state for one region in Cloudflare R2."""

from __future__ import annotations

import argparse
import json

from r2_publication_backend import (
    PublicationError,
    head_object,
    list_releases,
    load_r2_settings,
    make_r2_client,
    read_json_object,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", required=True)
    parser.add_argument("--prefix", default="routing")
    args = parser.parse_args()

    region = args.region.strip()
    prefix = args.prefix.strip("/")
    if not region or "/" in region or "\\" in region or ".." in region:
        raise SystemExit("Unsafe region id")
    namespace = f"{prefix}/{region}"
    latest_key = f"{namespace}/latest.json"

    try:
        settings = load_r2_settings()
        client = make_r2_client(settings)
        latest = None
        if head_object(client, settings.bucket, latest_key) is not None:
            latest, _ = read_json_object(client, settings.bucket, latest_key)

        history = list_releases(client, settings.bucket, namespace)
        releases = [
            {
                "key": item["key"],
                "sha256": item["sha256"],
                "artifactKind": item["artifactKind"],
                "regionId": item["regionId"],
                "packageVersion": item["packageVersion"],
                "builtAtUtc": item["builtAtUtc"],
            }
            for item in history
        ]
    except PublicationError as exc:
        raise SystemExit(str(exc)) from exc

    print(json.dumps({
        "schema": "roadpilot.r2-region-publication-status",
        "version": 1,
        "regionId": region,
        "namespace": namespace,
        "latestKey": latest_key,
        "latest": latest,
        "releases": releases,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
