#!/usr/bin/env python3
"""Opt-in isolated-copy parity check for one genuine historical validator artifact.

WARNING: this tool executes trusted local validator Python scripts. Temporary
copies protect the *nominated input* from direct modification, but this is NOT
a sandbox for the scripts (which could have arbitrary external side effects).
Only invoke it for known, trusted source and installed validator binaries.

No historical fixture content or personal absolute input path is emitted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

if __package__:
    from .audit_legacy_validator_dependencies import CANDIDATES
else:
    from audit_legacy_validator_dependencies import CANDIDATES

DEFAULT_INSTALLED_TOOLS = Path("/usr/lib/RoadPilot Graph Studio/pipeline/tools")
DEFAULT_MAX_BYTES = 64 * 1024 * 1024


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def schema_for(candidate: str) -> str:
    if candidate not in CANDIDATES:
        raise ValueError("not an allowlisted historical validator")
    return "roadpilot." + candidate.removeprefix("validate_").removesuffix(".py").replace("_", "-")


def _regular_file(path: Path) -> Path:
    if path.is_symlink() or not path.is_file():
        raise ValueError("expected an existing regular, non-symlink file")
    return path.resolve(strict=True)


def verify(
    candidate: str,
    fixture: Path,
    installed_tools: Path = DEFAULT_INSTALLED_TOOLS,
    *,
    repo_root: Path | None = None,
    acknowledge_execution: bool = False,
    max_bytes: int = DEFAULT_MAX_BYTES,
    python_executable: str | None = None,
) -> dict[str, Any]:
    if not acknowledge_execution:
        raise ValueError("execution of trusted Python scripts requires --acknowledge-execution")
    expected_schema = schema_for(candidate)
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    fixture_path = _regular_file(fixture)
    size = fixture_path.stat().st_size
    if size > max_bytes:
        raise ValueError("fixture exceeds maximum permitted byte count")
    original = fixture_path.read_bytes()
    if len(original) != size:
        raise RuntimeError("fixture changed size during capture")
    try:
        artifact = json.loads(original)
    except (UnicodeError, ValueError) as exc:
        raise ValueError("input is not valid JSON") from exc
    if not isinstance(artifact, dict):
        raise ValueError("fixture must be a JSON object")
    if artifact.get("schema") != expected_schema or type(artifact.get("version")) is not int or artifact["version"] != 1:
        raise ValueError("fixture schema/version does not match selected legacy validator")
    root = repo_root or Path(__file__).resolve().parent.parent
    original_script = _regular_file(root / "tools" / candidate)
    installed_script = _regular_file(installed_tools / candidate)
    if original_script.samefile(installed_script):
        raise ValueError("source and installed validators must be distinct regular files")
    source_script_sha256 = sha256(original_script.read_bytes())
    installed_script_sha256 = sha256(installed_script.read_bytes())
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1"}
    interpreter = python_executable or sys.executable
    records = {}
    with tempfile.TemporaryDirectory(prefix="roadpilot-p4b-fixture-") as directory:
        for label, script in (("source", original_script), ("installed", installed_script)):
            run_dir = Path(directory) / label
            run_dir.mkdir()
            copy = run_dir / "fixture.json"
            # Copies are throwaway; the nominated original is never passed to a CLI.
            copy.write_bytes(original)
            before_hash = sha256(copy.read_bytes())
            flag = "--inventory" if candidate == "validate_frontier_road_inventory.py" else "--artifact"
            completed = subprocess.run(
                [interpreter, str(script), flag, str(copy)],
                cwd=run_dir, capture_output=True, timeout=30, check=False, env=env,
            )
            after_hash = sha256(copy.read_bytes()) if copy.is_file() and not copy.is_symlink() else None
            extra_files = sorted(p.name for p in run_dir.iterdir() if p.name != "fixture.json")
            records[label] = {
                "exit_code": completed.returncode,
                "stdout_sha256": sha256(completed.stdout),
                "stderr_sha256": sha256(completed.stderr),
                "copy_unchanged": before_hash == after_hash,
                "new_files_created": bool(extra_files),
            }
    original_unchanged = (
        fixture_path.is_file()
        and not fixture_path.is_symlink()
        and sha256(fixture_path.read_bytes()) == sha256(original)
    )
    positive_parity = (
        records["source"]["exit_code"] == 0
        and records["installed"]["exit_code"] == 0
        and all(records["source"][key] == records["installed"][key]
                for key in ("exit_code", "stdout_sha256", "stderr_sha256"))
        and all(records[label]["copy_unchanged"] and not records[label]["new_files_created"]
                for label in ("source", "installed"))
        and original_unchanged
    )
    return {
        "classification": "REAL_INPUT_PARITY_ONLY_NOT_RETIREMENT_AUTHORIZATION",
        "validator": candidate,
        "schema": expected_schema,
        "version": 1,
        "input_size_bytes": size,
        "input_sha256": sha256(original),
        "source_script_sha256": source_script_sha256,
        "installed_script_sha256": installed_script_sha256,
        "script_bytes_identical": source_script_sha256 == installed_script_sha256,
        "original_unchanged": original_unchanged,
        "source": records["source"],
        "installed": records["installed"],
        "positive_parity": positive_parity,
        "external_consumers": "NOT_VERIFIED",
        "routing_or_android_parity": "NOT_VERIFIED",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validator", choices=CANDIDATES, required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--installed-tools", type=Path, default=DEFAULT_INSTALLED_TOOLS)
    parser.add_argument("--acknowledge-execution", action="store_true",
                        help="Explicitly accept execution of trusted source/installed scripts")
    args = parser.parse_args(argv)
    try:
        result = verify(
            args.validator, args.fixture, args.installed_tools,
            acknowledge_execution=args.acknowledge_execution,
        )
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        parser.error(f"parity check aborted: {type(exc).__name__}: {exc}")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["positive_parity"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
