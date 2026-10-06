#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path

import boto3
from botocore.exceptions import ClientError


def fail(message: str) -> None:
    raise SystemExit(message)


def required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        fail(f"Missing required environment variable: {name}")
    return value


def object_exists(client, bucket: str, key: str):
    try:
        return client.head_object(Bucket=bucket, Key=key)
    except ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code", ""))
        if code in {"404", "NoSuchKey", "NotFound"}:
            return None
        raise


def upload_immutable(client, bucket: str, path: Path, key: str, content_type: str, sha256: str | None = None):
    existing = object_exists(client, bucket, key)
    if existing is not None:
        metadata = existing.get("Metadata") or {}
        existing_sha = metadata.get("sha256")
        if sha256 and existing_sha == sha256:
            print(f"already published: s3://{bucket}/{key}")
            return
        fail(f"Refusing to overwrite immutable R2 object: {key}")

    extra = {
        "ContentType": content_type,
        "CacheControl": "public, max-age=31536000, immutable",
    }
    if sha256:
        extra["Metadata"] = {"sha256": sha256}
    client.upload_file(str(path), bucket, key, ExtraArgs=extra)
    print(f"uploaded: s3://{bucket}/{key}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--prefix", default="routing")
    args = parser.parse_args()

    account_id = required_env("CLOUDFLARE_ACCOUNT_ID")
    access_key = required_env("R2_ACCESS_KEY_ID")
    secret_key = required_env("R2_SECRET_ACCESS_KEY")
    bucket = required_env("R2_BUCKET")
    public_base = required_env("R2_PUBLIC_BASE_URL").rstrip("/")

    manifest_path = Path(args.manifest)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "roadpilot-routing-pack" or manifest.get("schemaVersion") != 1:
        fail("Not a RoadPilot routing-pack v1 manifest")

    region_id = str(manifest["regionId"])
    version = str(manifest["packageVersion"])
    artifact = manifest["artifact"]
    package_name = str(artifact["fileName"])
    package_sha = str(artifact["sha256"])
    package_path = manifest_path.parent / package_name
    checksum_path = manifest_path.parent / f"{package_name}.sha256"

    for path in (package_path, manifest_path, checksum_path):
        if not path.is_file():
            fail(f"Missing publish input: {path}")

    client = boto3.client(
        "s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="auto",
    )

    root = f"{args.prefix.strip('/')}/{region_id}"
    version_root = f"{root}/{version}"
    package_key = f"{version_root}/{package_name}"
    manifest_key = f"{version_root}/{manifest_path.name}"
    checksum_key = f"{version_root}/{checksum_path.name}"

    upload_immutable(
        client,
        bucket,
        package_path,
        package_key,
        "application/x-tar",
        package_sha,
    )
    upload_immutable(
        client,
        bucket,
        manifest_path,
        manifest_key,
        "application/json",
    )
    upload_immutable(
        client,
        bucket,
        checksum_path,
        checksum_key,
        "text/plain; charset=utf-8",
    )

    latest = {
        "schema": "roadpilot-routing-latest",
        "schemaVersion": 1,
        "regionId": region_id,
        "packageVersion": version,
        "manifestUrl": f"{public_base}/{manifest_key}",
        "artifactUrl": f"{public_base}/{package_key}",
        "checksumUrl": f"{public_base}/{checksum_key}",
        "artifactSizeBytes": int(artifact["sizeBytes"]),
        "artifactSha256": package_sha,
        "graphFingerprint": manifest["graphFingerprint"],
        "builtAtUtc": manifest["builtAtUtc"],
    }
    latest_body = (json.dumps(latest, indent=2) + "\n").encode("utf-8")
    latest_key = f"{root}/latest.json"
    client.put_object(
        Bucket=bucket,
        Key=latest_key,
        Body=latest_body,
        ContentType="application/json",
        CacheControl="public, max-age=60",
    )
    print(f"published latest pointer: {public_base}/{latest_key}")


if __name__ == "__main__":
    main()
