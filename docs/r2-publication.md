# RoadPilot Cloudflare R2 publication

RoadPilot publishes through the validated publication-plan contract. Do not upload a routing pack directly to R2.

## Credentials

Secrets are never stored in repository files. The publisher reads them from the process environment:

- `CLOUDFLARE_ACCOUNT_ID`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`
- `R2_BUCKET`

Optional:

- `R2_ENDPOINT_URL` — overrides the normal `https://<ACCOUNT_ID>.r2.cloudflarestorage.com` endpoint for compatible test infrastructure.

Graph Studio may later supply these values from OS-protected local credential storage, but it must not write access keys or secret keys into the repository or generated publication artifacts.

## Test credentials without publishing

```bash
python tools/test_r2_connection.py --prefix routing
```

The test only performs a bounded object listing. It does not create, overwrite, or delete objects.

## Prepare a routing release

```bash
python tools/prepare_routing_publication.py \
  --manifest /path/to/region-version-manifest.json \
  --output /tmp/roadpilot-publication-plan.json

python tools/validate_publication_plan.py \
  --plan /tmp/roadpilot-publication-plan.json
```

The plan records every immutable object key, local source path, size and SHA-256, plus the immutable `release.json` and mutable `latest.json` pointer.

## Publish

```bash
python tools/publish_publication_plan_r2.py \
  --plan /tmp/roadpilot-publication-plan.json \
  --report /tmp/roadpilot-r2-report.json
```

For Graph Studio integration, add `--json-events`. The publisher writes machine-readable progress events such as `UPLOAD_STARTED`, `UPLOAD_PROGRESS`, `UPLOAD_CONFIRMED`, `IMMUTABLE_PRESENT`, `LATEST_ADVANCED`, and `LATEST_ALREADY_CURRENT`.

Publication order is fixed:

1. revalidate all local plan inputs;
2. upload or confirm every immutable payload object;
3. HEAD-confirm size and SHA-256 metadata for every payload;
4. conditionally create or confirm immutable `release.json`;
5. re-confirm the complete release;
6. conditionally update `latest.json`.

A versioned object that already exists with different size/SHA metadata is never overwritten. An exact retry is idempotent.

The `latest.json` update uses R2 conditional `PutObject` semantics. If another publisher changes the pointer after this publisher reads it, the update is refused. The completed immutable release remains available, but it is not silently made latest.

## Published history

```bash
python tools/list_publication_releases_r2.py \
  --namespace routing/italy-nord-est
```

Each retained version has its own immutable `release.json`; listing release descriptors provides publication history without relying on mutable state.

## Roll back latest

```bash
python tools/activate_publication_release_r2.py \
  --release-key routing/italy-nord-est/<version>/release.json
```

Before moving `latest.json`, RoadPilot HEAD-verifies every immutable object in the selected historical release. Rollback changes only the latest pointer. It never deletes or mutates retained version objects.

## Legacy command

`tools/publish_routing_pack_r2.py` remains as a compatibility wrapper. It now prepares a publication plan and routes through the same safe plan-backed publisher; it no longer has an independent direct-upload implementation.
