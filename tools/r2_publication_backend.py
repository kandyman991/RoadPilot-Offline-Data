#!/usr/bin/env python3
"""Shared Cloudflare R2 publication backend for RoadPilot publication plans."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Callable

import boto3
from botocore.exceptions import ClientError


class PublicationError(RuntimeError):
    pass


@dataclass(frozen=True)
class R2Settings:
    account_id: str
    access_key_id: str
    secret_access_key: str
    bucket: str
    endpoint_url: str


def required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise PublicationError(f"Missing required environment variable: {name}")
    return value


def load_r2_settings() -> R2Settings:
    account_id = required_env("CLOUDFLARE_ACCOUNT_ID")
    access_key_id = required_env("R2_ACCESS_KEY_ID")
    secret_access_key = required_env("R2_SECRET_ACCESS_KEY")
    bucket = required_env("R2_BUCKET")
    endpoint_override = os.environ.get("R2_ENDPOINT_URL", "").strip()
    endpoint_url = endpoint_override or f"https://{account_id}.r2.cloudflarestorage.com"
    return R2Settings(
        account_id=account_id,
        access_key_id=access_key_id,
        secret_access_key=secret_access_key,
        bucket=bucket,
        endpoint_url=endpoint_url.rstrip("/"),
    )


def make_r2_client(settings: R2Settings):
    return boto3.client(
        "s3",
        endpoint_url=settings.endpoint_url,
        aws_access_key_id=settings.access_key_id,
        aws_secret_access_key=settings.secret_access_key,
        region_name="auto",
    )


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def client_error_code(exc: ClientError) -> str:
    return str(exc.response.get("Error", {}).get("Code", ""))


def is_not_found(exc: ClientError) -> bool:
    return client_error_code(exc) in {"404", "NoSuchKey", "NotFound"}


def is_precondition_failed(exc: ClientError) -> bool:
    return client_error_code(exc) in {"412", "PreconditionFailed"}


def head_object(client, bucket: str, key: str) -> dict[str, Any] | None:
    try:
        return client.head_object(Bucket=bucket, Key=key)
    except ClientError as exc:
        if is_not_found(exc):
            return None
        raise


def metadata_sha(head: dict[str, Any]) -> str | None:
    metadata = head.get("Metadata") or {}
    value = metadata.get("sha256")
    return str(value) if value is not None else None


def confirm_head(
    head: dict[str, Any] | None,
    *,
    key: str,
    expected_size: int,
    expected_sha: str,
    require_sha_metadata: bool = True,
) -> dict[str, Any]:
    if head is None:
        raise PublicationError(f"Published object is missing after write: {key}")
    actual_size = int(head.get("ContentLength") or -1)
    if actual_size != expected_size:
        raise PublicationError(
            f"R2 object size mismatch for {key}: expected {expected_size}, got {actual_size}"
        )
    actual_sha = metadata_sha(head)
    if require_sha_metadata and actual_sha != expected_sha:
        raise PublicationError(
            f"R2 object SHA metadata mismatch for {key}: expected {expected_sha}, got {actual_sha}"
        )
    return head


def emit_event(event: dict[str, Any], sink: Callable[[dict[str, Any]], None] | None) -> None:
    if sink is not None:
        sink(event)


class UploadProgress:
    def __init__(
        self,
        *,
        key: str,
        total: int,
        sink: Callable[[dict[str, Any]], None] | None,
    ) -> None:
        self.key = key
        self.total = total
        self.transferred = 0
        self.sink = sink

    def __call__(self, bytes_amount: int) -> None:
        self.transferred += int(bytes_amount)
        emit_event(
            {
                "event": "UPLOAD_PROGRESS",
                "key": self.key,
                "bytesTransferred": min(self.transferred, self.total),
                "totalBytes": self.total,
            },
            self.sink,
        )


def verify_local_source(item: dict[str, Any]) -> Path:
    path = Path(str(item.get("sourcePath") or ""))
    if not path.is_file():
        raise PublicationError(f"Publication source is missing: {path}")
    expected_size = int(item.get("sizeBytes") or -1)
    expected_sha = str(item.get("sha256") or "")
    actual_size = path.stat().st_size
    if actual_size != expected_size:
        raise PublicationError(
            f"Local publication source size changed for {path}: "
            f"expected {expected_size}, got {actual_size}"
        )
    actual_sha = sha256_file(path)
    if actual_sha != expected_sha:
        raise PublicationError(
            f"Local publication source SHA changed for {path}: "
            f"expected {expected_sha}, got {actual_sha}"
        )
    return path


def upload_immutable_file(
    client,
    bucket: str,
    item: dict[str, Any],
    sink: Callable[[dict[str, Any]], None] | None = None,
) -> str:
    key = str(item["key"])
    expected_size = int(item["sizeBytes"])
    expected_sha = str(item["sha256"])
    content_type = str(item["contentType"])
    source = verify_local_source(item)

    existing = head_object(client, bucket, key)
    if existing is not None:
        try:
            confirm_head(
                existing,
                key=key,
                expected_size=expected_size,
                expected_sha=expected_sha,
            )
        except PublicationError as exc:
            raise PublicationError(
                f"Refusing to overwrite immutable R2 object {key}: {exc}"
            ) from exc
        emit_event({"event": "IMMUTABLE_PRESENT", "key": key}, sink)
        return "ALREADY_PRESENT"

    emit_event(
        {
            "event": "UPLOAD_STARTED",
            "key": key,
            "totalBytes": expected_size,
        },
        sink,
    )
    client.upload_file(
        str(source),
        bucket,
        key,
        ExtraArgs={
            "ContentType": content_type,
            "CacheControl": "public, max-age=31536000, immutable",
            "Metadata": {"sha256": expected_sha},
        },
        Callback=UploadProgress(key=key, total=expected_size, sink=sink),
    )
    confirmed = head_object(client, bucket, key)
    confirm_head(
        confirmed,
        key=key,
        expected_size=expected_size,
        expected_sha=expected_sha,
    )
    emit_event({"event": "UPLOAD_CONFIRMED", "key": key}, sink)
    return "UPLOADED"


def put_immutable_bytes(
    client,
    bucket: str,
    *,
    key: str,
    body: bytes,
    sha256: str,
    content_type: str,
    sink: Callable[[dict[str, Any]], None] | None = None,
) -> str:
    existing = head_object(client, bucket, key)
    if existing is not None:
        try:
            confirm_head(
                existing,
                key=key,
                expected_size=len(body),
                expected_sha=sha256,
            )
        except PublicationError as exc:
            raise PublicationError(
                f"Refusing to overwrite immutable R2 object {key}: {exc}"
            ) from exc
        emit_event({"event": "IMMUTABLE_PRESENT", "key": key}, sink)
        return "ALREADY_PRESENT"

    try:
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=body,
            ContentType=content_type,
            CacheControl="public, max-age=31536000, immutable",
            Metadata={"sha256": sha256},
            IfNoneMatch="*",
        )
    except ClientError as exc:
        if not is_precondition_failed(exc):
            raise
        # Another publisher may have won the conditional create. Accept it only
        # if the exact expected immutable object is now present.
        raced = head_object(client, bucket, key)
        try:
            confirm_head(
                raced,
                key=key,
                expected_size=len(body),
                expected_sha=sha256,
            )
        except PublicationError as mismatch:
            raise PublicationError(
                f"Immutable R2 object {key} appeared concurrently with different content"
            ) from mismatch
        emit_event({"event": "IMMUTABLE_PRESENT", "key": key}, sink)
        return "ALREADY_PRESENT"

    confirmed = head_object(client, bucket, key)
    confirm_head(
        confirmed,
        key=key,
        expected_size=len(body),
        expected_sha=sha256,
    )
    emit_event({"event": "UPLOAD_CONFIRMED", "key": key}, sink)
    return "UPLOADED"


def read_json_object(client, bucket: str, key: str) -> tuple[dict[str, Any], dict[str, Any]]:
    response = client.get_object(Bucket=bucket, Key=key)
    body_obj = response.get("Body")
    raw = body_obj.read() if hasattr(body_obj, "read") else bytes(body_obj or b"")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PublicationError(f"R2 object is not valid UTF-8 JSON: {key}: {exc}") from exc
    if not isinstance(value, dict):
        raise PublicationError(f"R2 JSON object must be an object: {key}")
    return value, response


def put_latest_conditionally(
    client,
    bucket: str,
    *,
    key: str,
    latest: dict[str, Any],
    sink: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any] | None:
    body = canonical_json_bytes(latest)
    body_sha = sha256_bytes(body)
    previous_head = head_object(client, bucket, key)
    previous_latest = None
    if previous_head is not None:
        try:
            previous_latest, _ = read_json_object(client, bucket, key)
        except PublicationError:
            previous_latest = None

    args: dict[str, Any] = {
        "Bucket": bucket,
        "Key": key,
        "Body": body,
        "ContentType": "application/json",
        "CacheControl": "public, max-age=60",
        "Metadata": {
            "sha256": body_sha,
            "release-sha256": str(latest["releaseSha256"]),
        },
    }
    if previous_head is None:
        args["IfNoneMatch"] = "*"
    else:
        etag = str(previous_head.get("ETag") or "").strip()
        if not etag:
            raise PublicationError(
                f"Existing latest pointer has no ETag; refusing non-conditional update: {key}"
            )
        args["IfMatch"] = etag

    try:
        client.put_object(**args)
    except ClientError as exc:
        if is_precondition_failed(exc):
            raise PublicationError(
                f"Latest pointer changed concurrently; immutable release is safe but {key} was not advanced"
            ) from exc
        raise

    confirmed = head_object(client, bucket, key)
    confirm_head(
        confirmed,
        key=key,
        expected_size=len(body),
        expected_sha=body_sha,
    )
    emit_event(
        {
            "event": "LATEST_ADVANCED",
            "key": key,
            "packageVersion": latest.get("packageVersion"),
            "releaseKey": latest.get("releaseKey"),
        },
        sink,
    )
    return previous_latest


def validate_plan_file(plan_path: Path) -> dict[str, Any]:
    from validate_publication_plan import CONTRACT

    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PublicationError(f"Could not read publication plan {plan_path}: {exc}") from exc
    if not isinstance(plan, dict):
        raise PublicationError("Publication plan must be a JSON object")
    if plan.get("schema") != "roadpilot.publication-plan" or plan.get("version") != 1:
        raise PublicationError("Unsupported publication plan")
    if plan.get("contract") != CONTRACT:
        raise PublicationError("Unexpected publication plan contract")

    # Re-run the authoritative local validator in-process by duplicating its key
    # integrity checks that matter immediately before network I/O.
    release = plan.get("release")
    latest = plan.get("latest")
    sources = plan.get("sourceObjects")
    if not isinstance(release, dict) or not isinstance(latest, dict) or not isinstance(sources, list):
        raise PublicationError("Publication plan release/latest/sourceObjects are required")
    expected_release_sha = str(plan.get("releaseSha256") or "")
    actual_release_sha = sha256_bytes(canonical_json_bytes(release))
    if actual_release_sha != expected_release_sha:
        raise PublicationError("Publication release body no longer matches releaseSha256")
    for item in sources:
        if not isinstance(item, dict):
            raise PublicationError("Publication source item must be an object")
        verify_local_source(item)
    if latest.get("releaseKey") != plan.get("releaseKey"):
        raise PublicationError("latest.releaseKey does not match plan.releaseKey")
    if latest.get("releaseSha256") != expected_release_sha:
        raise PublicationError("latest.releaseSha256 does not match plan.releaseSha256")
    return plan


def publish_plan(
    client,
    bucket: str,
    plan: dict[str, Any],
    sink: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    source_results = []
    for item in plan["sourceObjects"]:
        state = upload_immutable_file(client, bucket, item, sink)
        source_results.append({"key": item["key"], "state": state})

    # Re-confirm every payload object immediately before publishing the release.
    for item in plan["sourceObjects"]:
        confirm_head(
            head_object(client, bucket, str(item["key"])),
            key=str(item["key"]),
            expected_size=int(item["sizeBytes"]),
            expected_sha=str(item["sha256"]),
        )

    release_body = canonical_json_bytes(plan["release"])
    release_sha = sha256_bytes(release_body)
    if release_sha != plan["releaseSha256"]:
        raise PublicationError("Release SHA changed before R2 publication")
    release_state = put_immutable_bytes(
        client,
        bucket,
        key=str(plan["releaseKey"]),
        body=release_body,
        sha256=release_sha,
        content_type="application/json",
        sink=sink,
    )

    # Re-confirm release and all payloads before the only mutable write.
    for item in plan["sourceObjects"]:
        confirm_head(
            head_object(client, bucket, str(item["key"])),
            key=str(item["key"]),
            expected_size=int(item["sizeBytes"]),
            expected_sha=str(item["sha256"]),
        )
    confirm_head(
        head_object(client, bucket, str(plan["releaseKey"])),
        key=str(plan["releaseKey"]),
        expected_size=len(release_body),
        expected_sha=release_sha,
    )

    previous_latest = put_latest_conditionally(
        client,
        bucket,
        key=str(plan["latestKey"]),
        latest=plan["latest"],
        sink=sink,
    )
    return {
        "schema": "roadpilot.r2-publication-report",
        "version": 1,
        "artifactKind": plan["release"]["artifactKind"],
        "regionId": plan["release"]["regionId"],
        "packageVersion": plan["release"]["packageVersion"],
        "objects": source_results,
        "release": {"key": plan["releaseKey"], "state": release_state},
        "previousLatest": previous_latest,
        "latest": plan["latest"],
        "latestKey": plan["latestKey"],
    }


def list_releases(client, bucket: str, namespace_prefix: str) -> list[dict[str, Any]]:
    prefix = namespace_prefix.strip("/") + "/"
    token = None
    keys: list[str] = []
    while True:
        args: dict[str, Any] = {"Bucket": bucket, "Prefix": prefix, "MaxKeys": 1000}
        if token:
            args["ContinuationToken"] = token
        response = client.list_objects_v2(**args)
        for item in response.get("Contents") or []:
            key = str(item.get("Key") or "")
            if key.endswith("/release.json"):
                keys.append(key)
        if not response.get("IsTruncated"):
            break
        token = response.get("NextContinuationToken")
        if not token:
            raise PublicationError("R2 release listing was truncated without continuation token")

    releases = []
    for key in sorted(set(keys)):
        release, _ = read_json_object(client, bucket, key)
        if release.get("schema") != "roadpilot.publication-release" or release.get("version") != 1:
            continue
        head = head_object(client, bucket, key)
        if head is None:
            continue
        releases.append(
            {
                "key": key,
                "sha256": metadata_sha(head),
                "artifactKind": release.get("artifactKind"),
                "regionId": release.get("regionId"),
                "packageVersion": release.get("packageVersion"),
                "builtAtUtc": release.get("builtAtUtc"),
                "release": release,
            }
        )
    releases.sort(key=lambda item: (str(item.get("builtAtUtc") or ""), str(item.get("packageVersion") or "")), reverse=True)
    return releases


def activate_release(
    client,
    bucket: str,
    *,
    release_key: str,
    sink: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    release, release_response = read_json_object(client, bucket, release_key)
    if release.get("schema") != "roadpilot.publication-release" or release.get("version") != 1:
        raise PublicationError("Unsupported publication release")
    immutable_prefix = str(release.get("immutablePrefix") or "")
    if release_key != f"{immutable_prefix}/release.json":
        raise PublicationError("Release key does not match immutablePrefix")

    for item in release.get("objects") or []:
        if not isinstance(item, dict):
            raise PublicationError("Release object entry is invalid")
        confirm_head(
            head_object(client, bucket, str(item["key"])),
            key=str(item["key"]),
            expected_size=int(item["sizeBytes"]),
            expected_sha=str(item["sha256"]),
        )

    release_head = head_object(client, bucket, release_key)
    if release_head is None:
        raise PublicationError("Release disappeared during activation")
    release_sha = metadata_sha(release_head)
    if not release_sha:
        raw = canonical_json_bytes(release)
        release_sha = sha256_bytes(raw)
        response_body = release_response.get("Body")
        # read_json_object consumed the stream already; canonical SHA is authoritative
        # for RoadPilot releases because prepare_routing_publication writes canonical JSON.

    parts = immutable_prefix.split("/")
    if len(parts) < 3:
        raise PublicationError("Release immutablePrefix lacks namespace/region/version")
    latest_key = "/".join(parts[:-1]) + "/latest.json"
    latest = {
        "schema": "roadpilot.publication-latest",
        "version": 1,
        "artifactKind": release["artifactKind"],
        "regionId": release["regionId"],
        "packageVersion": release["packageVersion"],
        "releaseKey": release_key,
        "releaseSha256": release_sha,
        "builtAtUtc": release["builtAtUtc"],
    }
    previous_latest = put_latest_conditionally(
        client,
        bucket,
        key=latest_key,
        latest=latest,
        sink=sink,
    )
    return {
        "schema": "roadpilot.r2-activation-report",
        "version": 1,
        "releaseKey": release_key,
        "latestKey": latest_key,
        "previousLatest": previous_latest,
        "latest": latest,
    }


def test_connection(client, bucket: str, prefix: str = "routing") -> dict[str, Any]:
    response = client.list_objects_v2(Bucket=bucket, Prefix=prefix.strip("/") + "/", MaxKeys=1)
    return {
        "bucket": bucket,
        "prefix": prefix.strip("/"),
        "reachable": True,
        "keyCountSample": int(response.get("KeyCount") or 0),
    }


def json_line_sink(event: dict[str, Any]) -> None:
    print(json.dumps(event, sort_keys=True), flush=True, file=sys.stdout)
