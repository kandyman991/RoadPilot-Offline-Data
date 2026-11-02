#!/usr/bin/env python3
"""Bounded, read-only, privacy-minimal audit of literal legacy CLI mentions.

Only inspect operator-nominated directories of scripts/configuration. This
is neither a full filesystem sandbox nor evidence that zero manual/dynamic/
external consumers exist. Never print source paths, command text or secrets.
No validators execute, no history content is printed, and no network is used.
"""
from __future__ import annotations

import argparse
import json
import os
import stat
from pathlib import Path
from typing import Any

if __package__:
    from .audit_legacy_validator_dependencies import CANDIDATES
else:
    from audit_legacy_validator_dependencies import CANDIDATES

SOURCE_SUFFIXES = frozenset({
    ".py", ".sh", ".bash", ".zsh", ".fish", ".ps1", ".bat", ".cmd",
    ".service", ".timer", ".desktop", ".conf", ".ini",
    ".yml", ".yaml", ".json", ".toml", ".xml",
})
SKIP_DIRS = frozenset({
    ".git", "node_modules", "target", ".gradle", ".venv", "venv",
    "__pycache__", ".cache", "dist", "build",
})
MAX_FILES = 10000
MAX_FILE_BYTES = 512 * 1024
MAX_DEPTH = 12


def audit_root(
    path: Path, *, max_files: int = MAX_FILES,
    max_file_bytes: int = MAX_FILE_BYTES, max_depth: int = MAX_DEPTH,
) -> dict[str, Any]:
    if max_files < 1 or max_file_bytes < 1 or max_depth < 0:
        raise ValueError("invalid scan limits")
    if path.is_symlink() or not path.is_dir():
        raise ValueError("root must be an existing directory, not a symlink")
    root = path.resolve(strict=True)
    result: dict[str, Any] = {
        "files_checked": 0,
        "non_regular_skipped": 0,
        "symlinks_skipped": 0,
        "oversize_skipped": 0,
        "unreadable_skipped": 0,
        "unreadable_directories": 0,
        "truncated": False,
        "matching_files": 0,
        "validator_literal_file_counts": dict.fromkeys(CANDIDATES, 0),
    }
    def on_walk_error(_error: OSError) -> None:
        # os.walk silently skips inaccessible subtrees without onerror.
        result["unreadable_directories"] += 1

    for parent, dirs, files in os.walk(root, followlinks=False, onerror=on_walk_error):
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

        for name in sorted(files):
            file = here / name
            if file.is_symlink():
                result["symlinks_skipped"] += 1
                continue
            if file.suffix.lower() not in SOURCE_SUFFIXES:
                continue
            if result["files_checked"] >= max_files:
                result["truncated"] = True
                return result
            result["files_checked"] += 1
            fd = None
            try:
                fd = os.open(file, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
                             | getattr(os, "O_NONBLOCK", 0))
                metadata = os.fstat(fd)
                if not stat.S_ISREG(metadata.st_mode):
                    result["non_regular_skipped"] += 1
                    continue
                if metadata.st_size > max_file_bytes:
                    result["oversize_skipped"] += 1
                    continue
                with os.fdopen(fd, "rb", closefd=True) as stream:
                    fd = None
                    raw = stream.read(max_file_bytes + 1)
                if len(raw) > max_file_bytes:
                    result["oversize_skipped"] += 1
                    continue
            except OSError:
                result["unreadable_skipped"] += 1
                continue
            finally:
                if fd is not None:
                    os.close(fd)

            # Ignore binary/invalid source. This is a literal-only screen.
            if b"\0" in raw:
                continue
            text = raw.decode("utf-8", errors="replace")
            found = [name for name in CANDIDATES
                     if name in text or name.removesuffix(".py") in text]
            if found:
                result["matching_files"] += 1
                for validator in found:
                    result["validator_literal_file_counts"][validator] += 1
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, action="append", type=Path,
                        help="Explicitly authorized scripts/config directory (repeatable)")
    parser.add_argument("--max-files", type=int, default=MAX_FILES)
    parser.add_argument("--max-file-bytes", type=int, default=MAX_FILE_BYTES)
    parser.add_argument("--max-depth", type=int, default=MAX_DEPTH)
    args = parser.parse_args(argv)
    try:
        roots = [
            dict(root_label=f"root_{i+1}",
                 **audit_root(path, max_files=args.max_files,
                              max_file_bytes=args.max_file_bytes,
                              max_depth=args.max_depth))
            for i, path in enumerate(args.root)
        ]
    except (OSError, ValueError) as exc:
        parser.error(f"bounded audit aborted: {type(exc).__name__}")
    print(json.dumps({
        "classification": "LITERAL_ONLY_PRIVACY_MINIMAL_NOT_RETIREMENT_APPROVAL",
        "root_results": roots,
        "limits": {
            "max_files_per_root": args.max_files,
            "max_file_bytes": args.max_file_bytes,
            "max_depth": args.max_depth,
            "symlink_traversal": False,
            "contents_or_absolute_paths_reported": False,
        },
        "manual_and_dynamic_consumers": "UNKNOWN",
        "missing_matches_do_not_prove_no_external_consumers": True,
        "validators_to_retain": list(CANDIDATES),
    }, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
