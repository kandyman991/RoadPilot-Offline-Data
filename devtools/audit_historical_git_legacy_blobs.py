#!/usr/bin/env python3
"""Read-only bounded inventory of legacy v1 JSON blobs reachable by local Git refs.

Only check filenames exposed by git rev-list --objects --all, and never emit
paths, artifact contents, coordinates or raw command output. Reachable ref scope
is NOT proof about pruned/dangling objects, un-fetched branches, external backups,
or that a non-test path is a real production artifact. No validator is executed.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

if __package__:
    from .audit_historical_fixture_inventory import SCHEMAS, PAYLOAD_ARRAYS
else:
    from audit_historical_fixture_inventory import SCHEMAS, PAYLOAD_ARRAYS

DEFAULT_MAX_JSON_BLOBS = 10000
DEFAULT_MAX_BLOB_BYTES = 32 * 1024 * 1024
GIT_TIMEOUT_SECONDS = 90


def _git(root: Path, *parts: str) -> bytes:
    completed = subprocess.run(
        ["git", "-C", str(root), *parts], check=True,
        capture_output=True, timeout=GIT_TIMEOUT_SECONDS,
    )
    return completed.stdout


def inventory(
    repo_root: Path, *, max_json_blobs: int = DEFAULT_MAX_JSON_BLOBS,
    max_blob_bytes: int = DEFAULT_MAX_BLOB_BYTES,
) -> dict[str, Any]:
    if max_json_blobs < 1 or max_blob_bytes < 1:
        raise ValueError("scan limits must be positive")
    if repo_root.is_symlink() or not repo_root.is_dir():
        raise ValueError("repository root must be a real directory")
    root = repo_root.resolve(strict=True)
    toplevel = Path(_git(root, "rev-parse", "--show-toplevel").decode().strip())
    if toplevel.resolve() != root:
        raise ValueError("path must be a repository toplevel")
    head = _git(root, "rev-parse", "HEAD").decode("ascii").strip()
    all_objects = _git(root, "rev-list", "--objects", "--all")
    result: dict[str, Any] = {
        "classification": "BOUNDED_LOCAL_GIT_REFS_NOT_PRODUCTION_PROOF",
        "git_head": head,
        "git_ref_object_records": 0,
        "json_paths_considered": 0,
        "unique_json_objects_considered": 0,
        "json_objects_parsed": 0,
        "invalid_or_unreadable": 0,
        "non_blob_skipped": 0,
        "oversize_skipped": 0,
        "truncated": False,
        "legacy_schema_wrong_or_missing_version": 0,
        "legacy_by_schema_and_path_class": [],
        "historical_operational_artifacts": "NOT_PROVEN",
        "external_manual_consumers": "NOT_VERIFIED",
        "missing_artifacts_do_not_prove_global_absence": True,
    }
    unique: dict[str, str] = {}
    for line in all_objects.splitlines():
        result["git_ref_object_records"] += 1
        if b" " not in line:
            continue
        oid, name = line.split(b" ", 1)
        if not name.lower().endswith(b".json"):
            continue
        result["json_paths_considered"] += 1
        digest = oid.decode("ascii")
        if len(digest) not in (40, 64) or not all(c in "0123456789abcdef" for c in digest):
            result["invalid_or_unreadable"] += 1
            continue
        if len(unique) >= max_json_blobs and digest not in unique:
            result["truncated"] = True
            break
        synthetic = name.startswith(b"tests/fixtures/") and b"historical" in name.lower()
        label = "known_historical_test_fixture_path" if synthetic else "other_path_not_production_proof"
        unique.setdefault(digest, label)
        if unique[digest] != label:
            unique[digest] = "ambiguous_path_provenance"
    result["unique_json_objects_considered"] = len(unique)
    hits: Counter[tuple[str, str, str]] = Counter()
    for digest, label in unique.items():
        try:
            if _git(root, "cat-file", "-t", digest).strip() != b"blob":
                result["non_blob_skipped"] += 1
                continue
            size = int(_git(root, "cat-file", "-s", digest).strip())
            if size > max_blob_bytes:
                result["oversize_skipped"] += 1
                continue
            payload = _git(root, "cat-file", "blob", digest)
            if len(payload) != size:
                result["invalid_or_unreadable"] += 1
                continue
            doc = json.loads(payload)
        except (subprocess.CalledProcessError, ValueError, UnicodeError, OverflowError):
            result["invalid_or_unreadable"] += 1
            continue
        result["json_objects_parsed"] += 1
        if not isinstance(doc, dict) or doc.get("schema") not in SCHEMAS:
            continue
        if type(doc.get("version")) is not int or doc["version"] != 1:
            result["legacy_schema_wrong_or_missing_version"] += 1
            continue
        schema = doc["schema"]
        lengths = [len(value) for key, value in doc.items()
                   if key in PAYLOAD_ARRAYS and isinstance(value, list)]
        material = "nonempty_top_level_array" if any(lengths) else "no_nonempty_named_array"
        hits[(schema, label, material)] += 1
    result["legacy_by_schema_and_path_class"] = [
        {
            "schema": schema,
            "path_class": label,
            "observed_top_level_arrays": material,
            "blob_count": count,
        }
        for (schema, label, material), count in sorted(hits.items())
    ]
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--max-json-blobs", type=int, default=DEFAULT_MAX_JSON_BLOBS)
    parser.add_argument("--max-blob-bytes", type=int, default=DEFAULT_MAX_BLOB_BYTES)
    args = parser.parse_args(argv)
    try:
        result = inventory(args.repo_root, max_json_blobs=args.max_json_blobs,
                           max_blob_bytes=args.max_blob_bytes)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        parser.error(f"Git audit aborted: {type(exc).__name__}")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
