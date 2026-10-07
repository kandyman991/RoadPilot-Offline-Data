#!/usr/bin/env python3
"""Activate an existing immutable RoadPilot release in Cloudflare R2."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from r2_publication_backend import (
    PublicationError,
    activate_release,
    json_line_sink,
    load_r2_settings,
    make_r2_client,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-key", required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--json-events", action="store_true")
    args = parser.parse_args()

    try:
        settings = load_r2_settings()
        client = make_r2_client(settings)
        report = activate_release(
            client,
            settings.bucket,
            release_key=args.release_key,
            sink=json_line_sink if args.json_events else None,
        )
    except PublicationError as exc:
        raise SystemExit(str(exc)) from exc

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not args.json_events:
        print(
            f"activated R2 release: {report['latest']['artifactKind']} "
            f"{report['latest']['regionId']} {report['latest']['packageVersion']}"
        )
        print(f"latest: {report['latestKey']} -> {report['releaseKey']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
