#!/usr/bin/env python3
"""Validate a RoadPilot visual refresh plan."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA = REPO_ROOT / "schemas" / "visual-refresh-plan.schema.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True, type=Path)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(schema).iter_errors(plan), key=lambda e: list(e.path))
    if errors:
        detail = "\n".join(
            f"- {'.'.join(str(part) for part in error.path) or '<root>'}: {error.message}"
            for error in errors[:20]
        )
        raise SystemExit(f"Visual refresh plan validation failed:\n{detail}")
    print(f"valid visual refresh plan: {plan['regionId']} {plan['status']} {plan['action']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
