# Chat Handoff — RoadPilot Offline Data / Graph Studio

_Last curated: 2026-10-06_

## New-chat recovery procedure

When the user says “pick up RoadPilot Offline Data” or “pick up Graph Studio from the Git handoff”:

1. Read this file.
2. Read `ROADMAP.md`.
3. Read `handoff/state.json`.
4. Check live GitHub PR/CI status before changing anything.
5. Continue the **Next exact action** without asking the user to restate prior chats.

## Project role

This repository is the canonical production pipeline for RoadPilot regional offline artifacts and Graph Studio.

Target regional artifacts are independently versioned:

- routing — Valhalla graph;
- visual — RoadPilot offline vector map;
- search — RoadPilot POI/search database.

Rebuilding one artifact or one region must not force unrelated regional/artifact downloads.

## Current focus

**Issue #14 — Cloudflare R2 publication manager, milestone 2: plan-backed R2 upload and verification.**

Issue #35 is complete and closed:
- PR #36 — graph-bound connector anchor inventories;
- PR #37 — exact-edge Motorcycle/Car entry→exit matrices;
- PR #38 — sparse matrix-backed hierarchical FASTER/SHORTER composition;
- PR #39 — Graph Studio matrix topology/weights/freshness inspection and lifecycle refresh planning.

Current branch: `r2-plan-publisher-m2`.

M1 publication contract is merged in PR #40.

M2 architecture:
- all R2 publishing consumes the validated M1 publication plan; the old direct manifest uploader now delegates to this path;
- credentials come only from process environment: CLOUDFLARE_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY and R2_BUCKET;
- test_r2_connection.py verifies bucket access without creating/deleting objects;
- payload uploads emit machine-readable progress events and are HEAD-verified for size + SHA-256 metadata;
- immutable release.json uses conditional creation and is reverified before latest can move;
- latest.json uses conditional PutObject against the observed ETag, so concurrent publishers cannot silently overwrite each other;
- exact retries are idempotent;
- immutable release history is listable from R2;
- activate_publication_release_r2.py verifies the full old release before moving latest, without deleting any retained version;
- CI uses a deterministic fake R2/S3 backend to prove upload, progress, HEAD checks, conditional latest failure, history and rollback.

Cloudflare R2 credentials are still not configured against a real bucket. Do not claim R2 is connected or live-tested.
## Critical architectural decisions

- Regional graphs stay independent.
- Valhalla pin for production compatibility is 3.6.3.
- Never manually mutate `.gph` graph files to repair a crossing.
- Manual crossings live in a RoadPilot-owned handoff override layer.
- A and B handoff coordinates are allowed to differ when independent graphs correlate the same physical road differently.
- A manual override cannot be VALID unless Valhalla proves it.
- Graph fingerprint changes invalidate/revalidate compatibility metadata.
- Expensive F8 discovery should move to graph-build preprocessing where possible.
- F8 remains runtime fallback for missing/stale/ambiguous metadata.
- Routing, visual, and POI/search distribution packages remain independent.
- Cloudflare R2 publication is not yet configured; do not claim it is connected.

## Experimental branches / PRs

PRs #5 and #6 are older transition-artifact/offline-transition experiments. Do not merge or revive them blindly. Compare their useful concepts against the current Graph Studio roadmap and issue #26 connectivity work.

## Next exact action

1. Get #14 M2 plan-backed R2 publisher CI green and merge it.
2. M3: add Graph Studio local-vs-published status, credential configuration/test via local protected storage or environment, upload progress, release history and rollback controls.
3. Once the user supplies real R2 credentials/bucket configuration, run the connection test and a controlled first live publication.
## Handoff maintenance

Update this file after each meaningful architectural decision or milestone transition. The automatic workflow updates only `handoff/state.json`.
