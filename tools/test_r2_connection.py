#!/usr/bin/env python3
"""Test RoadPilot Cloudflare R2 credentials without publishing objects."""

from __future__ import annotations

import argparse
import json

from r2_publication_backend import (
    PublicationError,
    load_r2_settings,
    make_r2_client,
    test_connection,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefix", default="routing")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        settings = load_r2_settings()
        client = make_r2_client(settings)
        result = test_connection(client, settings.bucket, args.prefix)
    except PublicationError as exc:
        raise SystemExit(str(exc)) from exc

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(
            f"R2 connection OK: bucket={result['bucket']} "
            f"prefix={result['prefix']} sampleKeys={result['keyCountSample']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
