#!/usr/bin/env python3
"""List immutable RoadPilot releases published in Cloudflare R2."""

from __future__ import annotations

import argparse
import json

from r2_publication_backend import (
    PublicationError,
    list_releases,
    load_r2_settings,
    make_r2_client,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--namespace", required=True, help="Example: routing/italy-nord-est")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        settings = load_r2_settings()
        client = make_r2_client(settings)
        releases = list_releases(client, settings.bucket, args.namespace)
    except PublicationError as exc:
        raise SystemExit(str(exc)) from exc

    if args.json:
        print(json.dumps(releases, indent=2, sort_keys=True))
    else:
        for item in releases:
            print(
                f"{item['packageVersion']}\t{item['builtAtUtc']}\t"
                f"{item['sha256']}\t{item['key']}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
