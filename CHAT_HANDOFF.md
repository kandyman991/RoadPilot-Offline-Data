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

**Issue #14 — Cloudflare R2 publication manager, milestone 1: immutable publication contract.**

Issue #35 is complete and closed:
- PR #36 — graph-bound connector anchor inventories;
- PR #37 — exact-edge Motorcycle/Car entry→exit matrices;
- PR #38 — sparse matrix-backed hierarchical FASTER/SHORTER composition;
- PR #39 — Graph Studio matrix topology/weights/freshness inspection and lifecycle refresh planning.

Current branch: `r2-publication-contract-m1`.

M1 publication architecture:
- keep the existing routing-pack validator as the publication gate;
- generate a credential-free `roadpilot.publication-plan`;
- payload keys are immutable and versioned;
- a deterministic immutable `release.json` describes the complete version;
- `latest.json` is the only mutable pointer;
- update order is payload objects → release.json → latest.json;
- exact retries are safe/idempotent;
- immutable key collisions with different bytes fail;
- a partial failed release cannot advance latest;
- rollback only repoints latest to an existing fully verified immutable release;
- graph-index is included when the routing manifest provides it;
- local object-store CI proves semantics before R2 credentials are involved.

Cloudflare R2 credentials are not configured or tested yet. Do not claim R2 is connected.
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

1. Get #14 M1 publication-contract CI green and merge it.
2. M2: make the R2 publisher consume the validated publication plan, configure/test credentials outside repository files, upload/HEAD-verify every immutable object, then advance latest.
3. M3: add Graph Studio local-vs-published status, upload progress, release history and rollback controls.
## Handoff maintenance

Update this file after each meaningful architectural decision or milestone transition. The automatic workflow updates only `handoff/state.json`.
