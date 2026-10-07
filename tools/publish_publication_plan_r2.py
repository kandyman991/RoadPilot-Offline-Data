#!/usr/bin/env python3
"""Publish a validated RoadPilot publication plan to Cloudflare R2."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from r2_publication_backend import (
    PublicationError,
    json_line_sink,
    load_r2_settings,
    make_r2_client,
    publish_plan,
    validate_plan_file,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--json-events", action="store_true")
    args = parser.parse_args()

    plan_path = args.plan.resolve()
    validator = Path(__file__).with_name("validate_publication_plan.py")
    result = subprocess.run(
        [sys.executable, str(validator), "--plan", str(plan_path)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise SystemExit(f"Publication plan validation failed: {detail}")

    try:
        plan = validate_plan_file(plan_path)
        settings = load_r2_settings()
        client = make_r2_client(settings)
        report = publish_plan(
            client,
            settings.bucket,
            plan,
            json_line_sink if args.json_events else None,
        )
    except PublicationError as exc:
        raise SystemExit(str(exc)) from exc

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if not args.json_events:
        print(
            f"published R2 release: {report['artifactKind']} "
            f"{report['regionId']} {report['packageVersion']}"
        )
        print(f"release: {report['release']['key']}")
        print(f"latest: {report['latestKey']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
