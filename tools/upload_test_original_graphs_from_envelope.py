#!/usr/bin/env python3
"""One-time Legion-only upload of two exact original Valhalla graph archives.

The GitHub-hosted workflow holds repo secrets; its artifact is an authenticated
envelope encrypted to a local one-time X25519 key. No long-lived secret is ever
saved on the Legion or in a repository file.

This is only for private R2 TEST_ONLY graph storage, NOT a READY catalog or
production graph publication. It cannot modify native A -> X -> B matching.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
import threading
import time
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from boto3.s3.transfer import TransferConfig
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

CONTEXT = b"roadpilot-r2-test-only-legion-handoff-v1"
ACCOUNT = "06feb351c2243add77c866ce1c9ceccf"
BUCKET = "roadpilot-test-graphs"
VERSION = "2026.10.13-1"
ROOT = Path.home() / "RoadPilotGraphStudio" / "builds"
TRANSFER = Path.home() / ".local/share/roadpilot-r2-transfer"
EXPECTED_GRAPHS = {
    "italy-nord-est": "e6a10d36f8622ac0e47dc3d17a8295f60b144f9a2ad478e1b5f6ef2dbea75953",
    "austria": "ee7baac93b639d0c2fefab8f90540d26d03fd28a283c73bff516a1d8bdc2bc7b",
}


def file_sha256(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while block := handle.read(8 * 1024 * 1024):
            digest.update(block)
            size += len(block)
    return size, digest.hexdigest()


def decrypt_credentials(envelope_path: Path, private_key_path: Path, now: int | None = None) -> dict:
    envelope = json.loads(envelope_path.read_text())
    if envelope.get("schema") != "roadpilot.r2.encrypted-handoff.v1":
        raise ValueError("Unexpected encrypted-envelope schema")
    if private_key_path.stat().st_mode & 0o077:
        raise ValueError("One-time decryption key has unsafe filesystem permissions")
    private = x25519.X25519PrivateKey.from_private_bytes(private_key_path.read_bytes())
    remote_public = x25519.X25519PublicKey.from_public_bytes(
        base64.b64decode(envelope["ephemeralPublicKey"], validate=True)
    )
    shared = private.exchange(remote_public)
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=CONTEXT).derive(shared)
    plain = AESGCM(key).decrypt(
        base64.b64decode(envelope["nonce"], validate=True),
        base64.b64decode(envelope["ciphertext"], validate=True),
        CONTEXT,
    )
    cfg = json.loads(plain)
    when = int(time.time() if now is None else now)
    if (cfg.get("schema") != "roadpilot.r2.test-only-credential-handoff.v1" or
        cfg.get("accountId") != ACCOUNT or cfg.get("bucket") != BUCKET or
        not cfg.get("accessKeyId") or not cfg.get("secretAccessKey") or
        not isinstance(cfg.get("issuedAt"), int) or
        not isinstance(cfg.get("expiresAt"), int) or
        when < cfg["issuedAt"] - 60 or when > cfg["expiresAt"] or
        cfg["expiresAt"] - cfg["issuedAt"] > 1800):
        raise ValueError("Expired, untrusted or mis-scoped R2 credential envelope")
    return cfg


def expected_sources() -> list[tuple[Path, str, str, str]]:
    result = []
    for region, sha in EXPECTED_GRAPHS.items():
        base = ROOT / region / (region + "-routing-" + VERSION)
        tar = Path(str(base) + ".tar")
        manifest = Path(str(base) + "-manifest.json")
        if not tar.is_file() or not manifest.is_file():
            raise FileNotFoundError(f"Original graph archive / manifest missing for {region}")
        info = json.loads(manifest.read_text())
        if (info.get("schema") != "roadpilot-routing-pack" or
            info.get("regionId") != region or info.get("packageVersion") != VERSION or
            info.get("valhallaVersion") != "3.6.3" or
            info.get("graphFingerprint") != "sha256:" + sha or
            info.get("artifact", {}).get("sha256") != sha or
            info.get("artifact", {}).get("fileName") != tar.name or
            info.get("artifact", {}).get("sizeBytes") != tar.stat().st_size or
            info.get("source", {}).get("borderBufferKm") != 25.0):
            raise ValueError(f"Original graph manifest identity mismatch for {region}")
        result.append((tar, f"test-only/original/{VERSION}/{region}/graph.tar",
                       "application/x-tar", sha))
        result.append((manifest, f"test-only/original/{VERSION}/{region}/manifest.json",
                       "application/json", ""))
    return result


def head_or_none(client, key: str):
    try:
        return client.head_object(Bucket=BUCKET, Key=key)
    except ClientError as exc:
        if str(exc.response.get("Error", {}).get("Code")) in ("404", "NoSuchKey", "NotFound"):
            return None
        raise


def verify_remote(client, key: str, expected_size: int, expected_sha: str) -> None:
    head = head_or_none(client, key)
    if (head is None or head.get("ContentLength") != expected_size or
        head.get("Metadata", {}).get("sha256") != expected_sha or
        head.get("Metadata", {}).get("roadpilot-status") != "blocked-test-only"):
        raise ValueError(f"Remote metadata/size mismatch for {key}; refusing publication")
    # Verify the real remote bytes, not only user-supplied checksum metadata.
    body = client.get_object(Bucket=BUCKET, Key=key)["Body"]
    digest, size = hashlib.sha256(), 0
    try:
        for block in body.iter_chunks(chunk_size=8 * 1024 * 1024):
            digest.update(block)
            size += len(block)
    finally:
        body.close()
    if size != expected_size or digest.hexdigest() != expected_sha:
        raise ValueError(f"R2 downloaded bytes do not match immutable original for {key}")
    print(f"REMOTE_SHA256_VERIFIED key={key} sizeBytes={size} sha256={expected_sha}", flush=True)


class Progress:
    def __init__(self, total: int, key: str):
        self.total, self.key, self.amount, self.next_report = total, key, 0, 10
        self.lock = threading.Lock()

    def __call__(self, amount: int) -> None:
        with self.lock:
            self.amount += amount
            percent = int(self.amount / self.total * 100)
            if percent >= self.next_report:
                print(f"UPLOAD_PROGRESS key={self.key} percent={min(100,percent)}", flush=True)
                self.next_report += 10


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--envelope", type=Path, default=TRANSFER / "downloaded/roadpilot-r2-encrypted-handoff.json")
    parser.add_argument("--private-key", type=Path, default=TRANSFER / "recipient-private.key")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    source_specs = expected_sources()
    verified = []
    for local, key, content_type, expected in source_specs:
        size, actual = file_sha256(local)
        if expected and actual != expected:
            raise ValueError(f"Original graph archive hash changed: {local}")
        print(f"LOCAL_SHA256_VERIFIED key={key} sizeBytes={size} sha256={actual}", flush=True)
        verified.append((local, key, content_type, size, actual))
    if args.dry_run:
        print("DRY_RUN_COMPLETE: no credentials read or uploads made", flush=True)
        return 0
    cfg = decrypt_credentials(args.envelope, args.private_key)
    client = boto3.client(
        "s3", endpoint_url=f"https://{ACCOUNT}.r2.cloudflarestorage.com",
        region_name="auto", aws_access_key_id=cfg["accessKeyId"],
        aws_secret_access_key=cfg["secretAccessKey"],
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"},
                      connect_timeout=15, read_timeout=180,
                      retries={"max_attempts": 5, "mode": "standard"},
                      request_checksum_calculation="when_required",
                      response_checksum_validation="when_required"),
    )
    settings = TransferConfig(
        multipart_threshold=16 * 1024 * 1024,
        multipart_chunksize=16 * 1024 * 1024,
        max_concurrency=4, use_threads=True,
    )
    for local, key, content_type, size, sha in verified:
        head = head_or_none(client, key)
        if head is not None:
            print(f"EXISTING_IMMUTABLE_OBJECT key={key}; verifying full bytes", flush=True)
            verify_remote(client, key, size, sha)
            continue
        print(f"UPLOAD_STARTED key={key} sizeBytes={size}", flush=True)
        client.upload_file(
            str(local), BUCKET, key,
            ExtraArgs={
                "ContentType": content_type,
                "CacheControl": "private, no-store",
                "Metadata": {"sha256": sha, "roadpilot-status": "blocked-test-only"},
            },
            Config=settings, Callback=Progress(size, key),
        )
        verify_remote(client, key, size, sha)
    print("ALL_FOUR_OBJECTS_PRIVATE_TEST_ONLY_SHA256_VERIFIED", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        # Never emit a traceback that could accidentally print a bearer token.
        print(f"UPLOAD_FAILED: {type(exc).__name__}: {str(exc)[:220] if isinstance(exc, (FileNotFoundError, ValueError)) else 'see local diagnostics'}", file=sys.stderr)
        sys.exit(1)
