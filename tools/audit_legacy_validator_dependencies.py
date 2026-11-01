#!/usr/bin/env python3
"""Read-only, reproducible static inventory of historical Graph Studio validator CLIs.

This is a *negative-dependency screen*, not proof of dead code. It reads Git-tracked
source and the current Tauri packaging map, never user workspaces, and does not
change or execute any build, routing, or artifact-generation code. Optional --probe-help
executes only the 11 fixed, repository-tracked scripts with --help.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

CANDIDATES = (
    "validate_connectivity_chain_plan.py",
    "validate_connectivity_refresh_plan.py",
    "validate_crossing_candidates.py",
    "validate_crossing_proofs.py",
    "validate_frontier_road_correlations.py",
    "validate_frontier_road_inventory.py",
    "validate_hierarchical_connectivity_plan.py",
    "validate_region_connector_inventory.py",
    "validate_region_connector_matrix.py",
    "validate_region_connector_refresh_plan.py",
    "validate_runtime_connectivity.py",
)
SOURCE_SUFFIXES = frozenset({
    ".py", ".rs", ".ts", ".tsx", ".js", ".mjs", ".c", ".cpp", ".h", ".hpp",
    ".sh", ".yml", ".yaml", ".json", ".toml", ".cmake", ".service", ".desktop",
})
EXCLUDED_AUDIT_PATHS = frozenset({
    "tools/audit_legacy_validator_dependencies.py",
    "tests/test_legacy_validator_dependency_audit.py",
})
TAURI_CONFIG = "graph-studio/src-tauri/tauri.conf.json"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def tracked_sources(root: Path) -> dict[str, Path]:
    """Return safe existing tracked source files only, ignoring links outside root."""
    root = root.resolve(strict=True)
    completed = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--cached", "-z"],
        check=True, capture_output=True,
    )
    files: dict[str, Path] = {}
    for entry in completed.stdout.split(b"\0"):
        if not entry:
            continue
        relative = entry.decode("utf-8", errors="surrogateescape")
        if relative in EXCLUDED_AUDIT_PATHS or relative.startswith("docs/"):
            continue
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            continue
        if Path(relative).suffix.lower() in SOURCE_SUFFIXES:
            files[relative] = path
    return dict(sorted(files.items()))


def audit(root: Path, probe_help: bool = False) -> dict:
    root = root.resolve(strict=True)
    tracked = tracked_sources(root)
    config = root / TAURI_CONFIG
    packaging = json.loads(config.read_text(encoding="utf-8"))
    resource_map = packaging.get("bundle", {}).get("resources", {})
    packaged = resource_map.get("../../tools/") == "pipeline/tools/"
    result: dict = {
        "classification": "EVIDENCE_ONLY_NOT_DELETION_AUTHORIZATION",
        "repository": str(root),
        "tracked_source_files_scanned": len(tracked),
        "tauri_tools_bundle_wildcard": packaged,
        "scope_limitations": [
            "Only literal references in tracked source files and workflow/config files",
            "No dynamically computed imports or runtime-dispatched filenames",
            "No external scripts, manual CLI consumers or older installed versions",
            "No historical schema fixtures, user data or Android device proof",
        ],
        "candidates": [],
    }
    for name in CANDIDATES:
        relative = "tools/" + name
        candidate = root / relative
        if not candidate.is_file() or not candidate.resolve().is_relative_to(root):
            raise FileNotFoundError(f"Historical CLI missing: {relative}")
        data = candidate.read_bytes()
        # Match the filename and full module stem only. Never count the CLI itself.
        matches: list[str] = []
        for other, path in tracked.items():
            if other == relative:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if name in text or name[:-3] in text:
                matches.append(other)
        record: dict = {
            "path": relative,
            "sha256": sha256(data),
            "literal_tracked_callers_or_mentions": sorted(matches),
            "packaged_by_wildcard": packaged,
            "external_consumers": "NOT_VERIFIED",
            "historical_fixture_compatibility": "NOT_VERIFIED",
            "retirement_decision": "RETAIN",
        }
        if probe_help:
            # Deliberately no arbitrary path/argument execution: only fixed scripts.
            run = subprocess.run(
                [sys.executable, str(candidate), "--help"], cwd=root,
                capture_output=True, timeout=15, check=False,
            )
            record["help_probe"] = {
                "exit_code": run.returncode,
                "usage_present": b"usage:" in run.stdout.lower(),
                "stdout_sha256": sha256(run.stdout),
                "stderr_sha256": sha256(run.stderr),
            }
        result["candidates"].append(record)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path,
                        default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--probe-help", action="store_true",
                        help="Additionally invoke only the 11 fixed CLIs with --help")
    args = parser.parse_args(argv)
    result = audit(args.repo_root, probe_help=args.probe_help)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
