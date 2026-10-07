#!/usr/bin/env python3
"""Backward-compatible routing publisher that now uses the publication-plan contract.

Prefer:
  prepare_routing_publication.py
  publish_publication_plan_r2.py
for new integrations.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path


def run(command: list[str]) -> None:
    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--prefix", default="routing")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--json-events", action="store_true")
    args = parser.parse_args()

    tools_dir = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(prefix="roadpilot-r2-plan-") as tmp:
        plan = Path(tmp) / "publication-plan.json"
        run([
            sys.executable,
            str(tools_dir / "prepare_routing_publication.py"),
            "--manifest",
            str(args.manifest.resolve()),
            "--prefix",
            args.prefix,
            "--output",
            str(plan),
        ])
        command = [
            sys.executable,
            str(tools_dir / "publish_publication_plan_r2.py"),
            "--plan",
            str(plan),
        ]
        if args.report is not None:
            command.extend(["--report", str(args.report.resolve())])
        if args.json_events:
            command.append("--json-events")
        run(command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
