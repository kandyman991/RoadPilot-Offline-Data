#!/usr/bin/env python3
"""Deterministic in-memory S3/R2 smoke test for RoadPilot publication backend."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
from typing import Any

from botocore.exceptions import ClientError

from r2_publication_backend import (
    PublicationError,
    activate_release,
    list_releases,
    publish_plan,
    test_connection,
    validate_plan_file,
)


def client_error(code: str, operation: str) -> ClientError:
    return ClientError(
        {
            "Error": {"Code": code, "Message": code},
            "ResponseMetadata": {"HTTPStatusCode": int(code) if code.isdigit() else 412},
        },
        operation,
    )


class FakeR2Client:
    def __init__(self) -> None:
        self.objects: dict[str, dict[str, Any]] = {}
        self.sequence = 0
        self.fail_next_latest_condition = False

    def _etag(self, body: bytes) -> str:
        self.sequence += 1
        digest = hashlib.md5(body, usedforsecurity=False).hexdigest()
        return f'"{digest}-{self.sequence}"'

    def head_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:
        del Bucket
        item = self.objects.get(Key)
        if item is None:
            raise client_error("404", "HeadObject")
        return {
            "ContentLength": len(item["body"]),
            "Metadata": dict(item["metadata"]),
            "ContentType": item.get("content_type"),
            "CacheControl": item.get("cache_control"),
            "ETag": item["etag"],
        }

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:
        head = self.head_object(Bucket=Bucket, Key=Key)
        item = self.objects[Key]
        return {**head, "Body": io.BytesIO(item["body"])}

    def upload_file(
        self,
        Filename: str,
        Bucket: str,
        Key: str,
        ExtraArgs: dict[str, Any] | None = None,
        Callback=None,
    ) -> None:
        del Bucket
        body = Path(Filename).read_bytes()
        if Callback is not None:
            midpoint = max(1, len(body) // 2)
            Callback(midpoint)
            Callback(len(body) - midpoint)
        extra = ExtraArgs or {}
        self.objects[Key] = {
            "body": body,
            "metadata": dict(extra.get("Metadata") or {}),
            "content_type": extra.get("ContentType"),
            "cache_control": extra.get("CacheControl"),
            "etag": self._etag(body),
        }

    def put_object(self, **kwargs) -> dict[str, Any]:
        key = str(kwargs["Key"])
        body_value = kwargs.get("Body", b"")
        body = body_value.read() if hasattr(body_value, "read") else bytes(body_value)
        current = self.objects.get(key)

        if self.fail_next_latest_condition and key.endswith("/latest.json"):
            self.fail_next_latest_condition = False
            raise client_error("PreconditionFailed", "PutObject")

        if kwargs.get("IfNoneMatch") == "*" and current is not None:
            raise client_error("PreconditionFailed", "PutObject")
        if "IfMatch" in kwargs:
            if current is None or current["etag"] != kwargs["IfMatch"]:
                raise client_error("PreconditionFailed", "PutObject")

        self.objects[key] = {
            "body": body,
            "metadata": dict(kwargs.get("Metadata") or {}),
            "content_type": kwargs.get("ContentType"),
            "cache_control": kwargs.get("CacheControl"),
            "etag": self._etag(body),
        }
        return {"ETag": self.objects[key]["etag"]}

    def list_objects_v2(self, **kwargs) -> dict[str, Any]:
        prefix = str(kwargs.get("Prefix") or "")
        max_keys = int(kwargs.get("MaxKeys") or 1000)
        continuation = kwargs.get("ContinuationToken")
        keys = sorted(key for key in self.objects if key.startswith(prefix))
        start = int(continuation) if continuation else 0
        selected = keys[start : start + max_keys]
        next_index = start + len(selected)
        truncated = next_index < len(keys)
        return {
            "KeyCount": len(selected),
            "Contents": [{"Key": key, "Size": len(self.objects[key]["body"])} for key in selected],
            "IsTruncated": truncated,
            "NextContinuationToken": str(next_index) if truncated else None,
        }


def latest(client: FakeR2Client, key: str) -> dict[str, Any]:
    return json.loads(client.objects[key]["body"].decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan-a", required=True, type=Path)
    parser.add_argument("--plan-b", required=True, type=Path)
    parser.add_argument(
        "--independent-plan",
        type=Path,
        help="Optional plan using a different namespace/latest pointer, e.g. VISUAL.",
    )
    args = parser.parse_args()

    plan_a = validate_plan_file(args.plan_a.resolve())
    plan_b = validate_plan_file(args.plan_b.resolve())
    independent = (
        validate_plan_file(args.independent_plan.resolve())
        if args.independent_plan is not None
        else None
    )
    if plan_a["latestKey"] != plan_b["latestKey"]:
        raise SystemExit("smoke plans must target the same latest pointer")
    if plan_a["releaseKey"] == plan_b["releaseKey"]:
        raise SystemExit("smoke plans must use different immutable release keys")

    client = FakeR2Client()
    bucket = "roadpilot-smoke"
    events: list[dict[str, Any]] = []

    connection = test_connection(client, bucket, "routing")
    assert connection["reachable"] is True
    assert connection["keyCountSample"] == 0

    first = publish_plan(client, bucket, plan_a, events.append)
    assert all(item["state"] == "UPLOADED" for item in first["objects"])
    assert first["release"]["state"] == "UPLOADED"
    assert latest(client, plan_a["latestKey"])["packageVersion"] == plan_a["release"]["packageVersion"]
    assert any(event["event"] == "UPLOAD_PROGRESS" for event in events)
    assert any(event["event"] == "LATEST_ADVANCED" for event in events)

    retry = publish_plan(client, bucket, plan_a)
    assert all(item["state"] == "ALREADY_PRESENT" for item in retry["objects"])
    assert retry["release"]["state"] == "ALREADY_PRESENT"

    # Simulate a concurrent latest-pointer change after all immutable B objects
    # and B release have been confirmed. The immutable release must survive,
    # while latest remains on A.
    client.fail_next_latest_condition = True
    try:
        publish_plan(client, bucket, plan_b)
    except PublicationError as exc:
        assert "changed concurrently" in str(exc)
    else:
        raise AssertionError("expected conditional latest update to fail")

    assert plan_b["releaseKey"] in client.objects
    assert latest(client, plan_a["latestKey"])["packageVersion"] == plan_a["release"]["packageVersion"]

    second = publish_plan(client, bucket, plan_b)
    assert all(item["state"] == "ALREADY_PRESENT" for item in second["objects"])
    assert second["release"]["state"] == "ALREADY_PRESENT"
    assert latest(client, plan_b["latestKey"])["packageVersion"] == plan_b["release"]["packageVersion"]

    namespace = "/".join(str(plan_a["release"]["immutablePrefix"]).split("/")[:-1])
    history = list_releases(client, bucket, namespace)
    versions = {item["packageVersion"] for item in history}
    assert plan_a["release"]["packageVersion"] in versions
    assert plan_b["release"]["packageVersion"] in versions
    assert all(item["sha256"] for item in history)

    rollback = activate_release(client, bucket, release_key=plan_a["releaseKey"])
    assert rollback["latest"]["packageVersion"] == plan_a["release"]["packageVersion"]
    assert latest(client, plan_a["latestKey"])["packageVersion"] == plan_a["release"]["packageVersion"]
    assert plan_b["releaseKey"] in client.objects

    if independent is not None:
        if independent["latestKey"] == plan_a["latestKey"]:
            raise AssertionError("independent plan must use a different latest pointer")
        routing_latest_before = dict(latest(client, plan_a["latestKey"]))
        independent_report = publish_plan(client, bucket, independent)
        assert independent_report["artifactKind"] == independent["release"]["artifactKind"]
        assert independent["releaseKey"] in client.objects
        assert independent["latestKey"] in client.objects
        assert latest(client, independent["latestKey"])["releaseKey"] == independent["releaseKey"]
        assert latest(client, plan_a["latestKey"]) == routing_latest_before

        independent_namespace = "/".join(
            str(independent["release"]["immutablePrefix"]).split("/")[:-1]
        )
        independent_history = list_releases(client, bucket, independent_namespace)
        assert {item["key"] for item in independent_history} == {independent["releaseKey"]}

        independent_activation = activate_release(
            client,
            bucket,
            release_key=independent["releaseKey"],
        )
        assert independent_activation["latestKey"] == independent["latestKey"]
        assert latest(client, plan_a["latestKey"]) == routing_latest_before

    print("R2 publication backend smoke test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
