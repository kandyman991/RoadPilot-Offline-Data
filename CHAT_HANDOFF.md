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

**Issue #17 — POI/search production and inspection.**

Issue #16 is complete and closed:
- PR #43 — PMTiles/MVT visual artifact foundation;
- PR #44 — retained regional visual build + road validation lifecycle;
- PR #45 — Graph Studio exact-PMTiles inspector, layer controls and visual build diff;
- PR #46 — independent visual R2 publication and Graph Studio visual publication controls.

Search architecture requirements:
- reuse the existing RoadPilot Overture/SQLite search pipeline rather than creating a second search implementation;
- search packages are independent from routing and visual artifacts;
- regional config is the canonical source for search coverage and deterministic validation queries;
- generated SQLite must be exactly what RoadPilot consumes offline;
- support names, partial names, phrases, categories, address/location terms, typo tolerance where the existing implementation supports it, proximity ranking and reranking from a selected origin;
- Graph Studio must inspect result fields/ranking and highlight exact local DB results on the map;
- support practical POI category overlays from the local generated DB only;
- compare retained search builds for counts, added/removed/changed records, category deltas, size and validation changes;
- publish search independently under `search/<region>/...` using the same immutable release/latest contract.

Initial validation must retain the existing Italy Nord-Est SARP regression case.

Cloudflare R2 still has no live credentials configured; do not claim live publication has been tested.
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

1. Locate and document the existing RoadPilot Overture/SQLite search implementation and its exact database/query contract.
2. Define #17 milestones around that implementation instead of forking it.
3. Implement M1 search artifact/schema/build/validation foundation with the SARP regression target.
4. Continue through Graph Studio inspection/comparison and independent search R2 publication.
## Handoff maintenance

Update this file after each meaningful architectural decision or milestone transition. The automatic workflow updates only `handoff/state.json`.
