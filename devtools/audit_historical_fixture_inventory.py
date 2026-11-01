#!/usr/bin/env python3
"""Read-only, bounded, privacy-minimal inventory of historical Graph Studio JSON.

This is *discovery evidence*, not proof of completeness or deletion permission.
The caller must nominate each root. No validator executes and no file is written.
Only allowlisted schema IDs and aggregate list lengths/hashes are reported; actual
paths, identifiers, coordinates, JSON values and personal content are omitted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any

if __package__:
    from devtools.audit_legacy_validator_dependencies import CANDIDATES
else:
    from audit_legacy_validator_dependencies import CANDIDATES

SCHEMAS = {
    "roadpilot." + filename.removeprefix("validate_").removesuffix(".py").replace("_", "-"): filename
    for filename in CANDIDATES
}
# These are indicative field names, not an assertion every legacy type has them.
PAYLOAD_ARRAYS = frozenset({
    "roads", "candidates", "proofs", "results", "correlations", "connectors",
    "entries", "segments", "chains", "crossings", "routes", "links", "pairs",
    "edges", "levels", "plans", "changes", "operations", "hops", "transitions",
})
SKIP_DIRS = frozenset({
    ".git", "node_modules", "target", ".gradle", ".venv", "venv",
    "__pycache__",
})


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def scan_root(
    path: Path, *, max_files: int = 20000, max_file_bytes: int = 16 * 1024 * 1024,
    max_depth: int = 18,
) -> dict[str, Any]:
    if max_files < 1 or max_file_bytes < 1 or max_depth < 0:
        raise ValueError("scan limits must be positive (max_depth may be zero)")
    if path.is_symlink() or not path.is_dir():
        raise ValueError("scan root must be an existing directory, not a symlink")
    root = path.resolve(strict=True)
    result: dict[str, Any] = {
        "files_checked": 0, "oversize": 0, "unreadable_or_invalid": 0,
        "non_regular_skipped": 0,
        "symlinks_skipped": 0, "non_json_skipped": 0,
        "truncated": False, "matches": [],
    }
    for parent, dirs, files in os.walk(root, followlinks=False):
        here = Path(parent)
        depth = len(here.relative_to(root).parts)
        safe_dirs = []
        for directory in dirs:
            candidate = here / directory
            if candidate.is_symlink():
                result["symlinks_skipped"] += 1
            elif directory in SKIP_DIRS:
                continue
            elif depth >= max_depth:
                result["truncated"] = True
            else:
                safe_dirs.append(directory)
        dirs[:] = sorted(safe_dirs)
        for filename in sorted(files):
            file = here / filename
            if file.is_symlink():
                result["symlinks_skipped"] += 1
                continue
            if file.suffix.lower() != ".json":
                result["non_json_skipped"] += 1
                continue
            if result["files_checked"] >= max_files:
                result["truncated"] = True
                return result
            result["files_checked"] += 1
            try:
                metadata = file.stat()
                if not stat.S_ISREG(metadata.st_mode):
                    result["non_regular_skipped"] += 1
                    continue
                if metadata.st_size > max_file_bytes:
                    result["oversize"] += 1
                    continue
                original = file.read_bytes()
                if len(original) != metadata.st_size:
                    result["unreadable_or_invalid"] += 1
                    continue
                artifact = json.loads(original)
            except (OSError, UnicodeError, ValueError):
                result["unreadable_or_invalid"] += 1
                continue
            if not isinstance(artifact, dict):
                continue
            marker = artifact.get("schema")
            if not isinstance(marker, str) or marker not in SCHEMAS:
                continue
            arrays = {
                key: len(value) for key, value in artifact.items()
                if key in PAYLOAD_ARRAYS and isinstance(value, list)
            }
            result["matches"].append({
                "validator": SCHEMAS[marker],
                "schema": marker,
                "version": artifact.get("version")
                if type(artifact.get("version")) is int else "UNEXPECTED",
                "bytes": len(original),
                "sha256": sha256(original),
                "payload_array_lengths": dict(sorted(arrays.items())),
                "frontier_roads_populated":
                    len(artifact.get("roads", [])) > 0
                    if marker == "roadpilot.frontier-road-inventory"
                    and isinstance(artifact.get("roads"), list) else None,
            })
    result["matches"].sort(key=lambda v: (v["schema"], v["sha256"]))
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, action="append", required=True,
                        help="An explicitly authorized directory to scan (repeatable)")
    parser.add_argument("--max-files", type=int, default=20000)
    parser.add_argument("--max-file-bytes", type=int, default=16 * 1024 * 1024)
    parser.add_argument("--max-depth", type=int, default=18)
    args = parser.parse_args(argv)
    try:
        roots = [
            dict(root_label=f"root_{i + 1}", **scan_root(
                path, max_files=args.max_files,
                max_file_bytes=args.max_file_bytes, max_depth=args.max_depth))
            for i, path in enumerate(args.root)
        ]
    except (ValueError, OSError) as exc:
        parser.error(f"unable to audit nominated directory: {type(exc).__name__}")
    print(json.dumps({
        "classification": "READ_ONLY_SCOPE_LIMITED_NOT_DELETION_AUTHORIZATION",
        "schema_types": sorted(SCHEMAS),
        "root_results": roots,
        "limits": {
            "max_files_per_root": args.max_files,
            "max_file_bytes": args.max_file_bytes,
            "max_depth": args.max_depth,
            "only_json_files": True,
            "symlink_traversal": False,
            "skipped_directories": sorted(SKIP_DIRS),
            "path_details_in_output": False,
        },
        "missing_matches_do_not_prove_global_absence": True,
    }, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
