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

**Issue #14 — Cloudflare R2 publication manager, milestone 3: Graph Studio publication UI.**

Issue #35 is complete and closed:
- PR #36 — graph-bound connector anchor inventories;
- PR #37 — exact-edge Motorcycle/Car entry→exit matrices;
- PR #38 — sparse matrix-backed hierarchical FASTER/SHORTER composition;
- PR #39 — Graph Studio matrix topology/weights/freshness inspection and lifecycle refresh planning.

Current branch: `r2-graph-studio-manager-m3`.

M1 publication contract is merged in PR #40.
M2 plan-backed R2 publisher is merged in PR #41.

M3 Graph Studio architecture:
- credentials are stored only in Graph Studio app data, with Unix mode 0600; never in the repo or publication artifacts;
- frontend receives only masked credential state, never the stored secret;
- saved credentials are injected into publisher child processes through environment variables;
- UI can save/clear credentials and run the non-mutating bucket connection test;
- any retained validated routing build can be selected for publication;
- Graph Studio compares local package version/SHA with remote latest.json;
- publication runs asynchronously and streams M2 upload/confirmation events into the UI;
- immutable release history is displayed per region;
- rollback buttons invoke the same full-release verification before moving latest.json;
- no alternate/direct upload path exists.

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

1. Get #14 M3 Graph Studio publication-manager CI green and merge it.
2. Verify issue #14 acceptance against M1–M3 and close #14.
3. Once the user supplies real R2 credentials/bucket configuration, run the connection test and a controlled first live publication.
4. Then proceed to #16 visual map production/inspection, keeping #17 POI/search as its own later milestone.
## Handoff maintenance

Update this file after each meaningful architectural decision or milestone transition. The automatic workflow updates only `handoff/state.json`.
