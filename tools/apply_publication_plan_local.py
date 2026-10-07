#!/usr/bin/env python3
"""Apply a RoadPilot publication plan to a local object-store directory.

This is a credential-free backend used to prove R2 publication semantics in CI:
immutable objects may never change, exact retries are idempotent, release.json is
immutable, and latest.json advances only after every immutable object is confirmed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def fail(message: str) -> None:
    raise SystemExit(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def store_path(root: Path, key: str) -> Path:
    if not key or key.startswith("/"):
        fail(f"Unsafe object key: {key!r}")
    parts = key.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        fail(f"Unsafe object key: {key}")
    target = (root / key).resolve()
    root_resolved = root.resolve()
    try:
        target.relative_to(root_resolved)
    except ValueError:
        fail(f"Object key escapes store root: {key}")
    return target


def confirm_file(path: Path, expected_size: int, expected_sha: str, label: str) -> None:
    if not path.is_file():
        fail(f"{label} is missing: {path}")
    actual_size = path.stat().st_size
    if actual_size != expected_size:
        fail(f"{label} size mismatch: expected {expected_size}, got {actual_size}")
    actual_sha = sha256_file(path)
    if actual_sha != expected_sha:
        fail(f"{label} SHA mismatch: expected {expected_sha}, got {actual_sha}")


def copy_immutable(
    root: Path,
    source: Path,
    key: str,
    expected_size: int,
    expected_sha: str,
) -> str:
    target = store_path(root, key)
    if target.exists():
        confirm_file(target, expected_size, expected_sha, f"existing immutable object {key}")
        return "ALREADY_PRESENT"

    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(f".{target.name}.tmp-{os.getpid()}")
    try:
        shutil.copyfile(source, temp)
        confirm_file(temp, expected_size, expected_sha, f"staged immutable object {key}")
        if target.exists():
            confirm_file(target, expected_size, expected_sha, f"raced immutable object {key}")
            return "ALREADY_PRESENT"
        os.replace(temp, target)
    finally:
        temp.unlink(missing_ok=True)
    confirm_file(target, expected_size, expected_sha, f"published immutable object {key}")
    return "UPLOADED"


def write_immutable_bytes(root: Path, key: str, body: bytes, expected_sha: str) -> str:
    target = store_path(root, key)
    expected_size = len(body)
    if target.exists():
        confirm_file(target, expected_size, expected_sha, f"existing immutable object {key}")
        return "ALREADY_PRESENT"

    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(f".{target.name}.tmp-{os.getpid()}")
    try:
        temp.write_bytes(body)
        confirm_file(temp, expected_size, expected_sha, f"staged immutable object {key}")
        if target.exists():
            confirm_file(target, expected_size, expected_sha, f"raced immutable object {key}")
            return "ALREADY_PRESENT"
        os.replace(temp, target)
    finally:
        temp.unlink(missing_ok=True)
    confirm_file(target, expected_size, expected_sha, f"published immutable object {key}")
    return "UPLOADED"


def write_mutable_pointer(root: Path, key: str, body: bytes) -> None:
    target = store_path(root, key)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(f".{target.name}.tmp-{os.getpid()}")
    try:
        temp.write_bytes(body)
        os.replace(temp, target)
    finally:
        temp.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--store-root", required=True, type=Path)
    parser.add_argument("--report", type=Path)
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
        fail(f"Publication plan validation failed: {detail}")

    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    root = args.store_root.resolve()
    root.mkdir(parents=True, exist_ok=True)

    latest_key = str(plan["latestKey"])
    latest_target = store_path(root, latest_key)
    previous_latest = None
    if latest_target.is_file():
        try:
            previous_latest = json.loads(latest_target.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            fail(f"Existing latest pointer is not valid JSON: {latest_key}")

    object_results = []
    for item in plan["sourceObjects"]:
        source = Path(item["sourcePath"])
        state = copy_immutable(
            root,
            source,
            str(item["key"]),
            int(item["sizeBytes"]),
            str(item["sha256"]),
        )
        object_results.append({"key": item["key"], "state": state})

    # Confirm every payload object before creating/confirming release.json.
    for item in plan["sourceObjects"]:
        confirm_file(
            store_path(root, str(item["key"])),
            int(item["sizeBytes"]),
            str(item["sha256"]),
            f"confirmed immutable object {item['key']}",
        )

    release_body = canonical_json_bytes(plan["release"])
    release_sha = sha256_bytes(release_body)
    if release_sha != plan["releaseSha256"]:
        fail("Release body no longer matches publication plan releaseSha256")
    release_state = write_immutable_bytes(
        root,
        str(plan["releaseKey"]),
        release_body,
        release_sha,
    )
    confirm_file(
        store_path(root, str(plan["releaseKey"])),
        len(release_body),
        release_sha,
        "confirmed immutable release",
    )

    # This is intentionally the final write. Any failure above leaves the old
    # latest.json untouched and therefore cannot expose a partial release.
    latest_body = canonical_json_bytes(plan["latest"])
    write_mutable_pointer(root, latest_key, latest_body)

    report = {
        "schema": "roadpilot.publication-apply-report",
        "version": 1,
        "artifactKind": plan["release"]["artifactKind"],
        "regionId": plan["release"]["regionId"],
        "packageVersion": plan["release"]["packageVersion"],
        "objectResults": object_results,
        "release": {"key": plan["releaseKey"], "state": release_state},
        "previousLatest": previous_latest,
        "latest": plan["latest"],
        "latestKey": latest_key,
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_bytes(canonical_json_bytes(report))

    print(
        f"published local release: {report['artifactKind']} "
        f"{report['regionId']} {report['packageVersion']}"
    )
    for item in object_results:
        print(f"{item['state'].lower()}: {item['key']}")
    print(f"{release_state.lower()}: {plan['releaseKey']}")
    print(f"advanced latest: {latest_key}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
