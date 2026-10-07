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

**Issue #16 — visual map production/inspection, milestone 3: Graph Studio exact-PMTiles inspector.**

Issue #14 is complete and closed:
- PR #40 — immutable publication contract;
- PR #41 — plan-backed R2 upload/verification/history/rollback;
- PR #42 — Graph Studio R2 publication manager.

Current branch: `visual-map-inspector-m3`.

M1 is merged in PR #43.
M2 is merged in PR #44.

M3 Graph Studio inspector:
- selected-region build queue now invokes the independent M2 visual build after routing validation when visual.enabled is true;
- retained visual builds live under Graph Studio's visual-build store, separate from routing builds;
- AppImage/DEB resources now include requirements-visual.txt and visual/tilemaker;
- toolchain readiness checks exact tilemaker 3.2.0 compatibility;
- list_visual_builds exposes retained PMTiles metadata and road validation counts;
- visual_archive_range permits only bounded byte reads from the exact PMTiles named by a retained visual manifest;
- the frontend uses the official pmtiles 4.5.0 decoder over those Tauri range reads;
- RoadPilot visual layers render directly from the exact user-download PMTiles;
- online OpenFreeMap remains an independently toggleable reference layer;
- one map-layer control surface toggles offline visual, reference, Valhalla edges/nodes/shortcuts/access restrictions, buffer, Graph A/B, route, expansion and handoffs;
- visual inspector shows size, tile count, zoom/coverage, SHA, source/profile fingerprints, layers and major/border/missing road counts;
- visual A/B comparison uses original OSM feature IDs and currently loaded exact-PMTiles tiles to classify unchanged/removed/added/changed roads;
- region editor regenerates visual source/package configuration whenever the primary Geofabrik region changes.

M2 regional lifecycle:
- visual source is independently configured with primary Geofabrik PBF + nominal polygon;
- the production command caches both inputs and builds into a temporary version directory;
- completed versions are atomically retained under dist/visual/<region>/<version> and cannot be overwritten;
- visual PMTiles keep OSM feature IDs so source-road coverage can be proven;
- a roadpilot-visual-road-index extracts configured major roads plus boundary-corridor roads from the same PBF and checks every required OSM way is present in PMTiles;
- the visual manifest binds the road-index SHA and zero-missing-road counts;
- refresh planning chooses NONE, REVALIDATE_ROADS, REBUILD_PROFILE or REBUILD_SOURCE based on source/profile/validation changes;
- CI uses a pre-seeded source cache and real tilemaker/PMTiles build to prove retained-build immutability and refresh-action precedence.

M1 visual architecture:
- visual packages remain independent from routing and POI/search;
- format is PMTiles v3 containing MVT;
- tilemaker 3.2.0 is pinned to exact upstream commit `c7d1dbfaf87baa9e0bc9b2e984e0dae90dcf00c5`; hosted CI compiles that commit and any production native binary must report the same pinned version;
- first profile contains transportation, transportation_name, place, water, waterway, boundary and mountain_peak;
- buildings and POIs are deliberately excluded; #17 remains the POI/search pipeline;
- source identity is inherited from the region's configured primary Geofabrik PBF;
- visualFingerprint is the exact PMTiles SHA-256;
- profileFingerprint binds config + Lua + pinned toolchain;
- sourceFingerprint binds primary source URL/size/SHA;
- validator opens the exact PMTiles archive, verifies header/metadata/counts/bounds/zooms, decodes real MVT tiles, proves required layers and rejects forbidden dense layers;
- CI builds the same synthetic OSM fixture twice and requires byte-identical PMTiles, then proves a truncated archive fails validation.

M4 will publish visual artifacts independently through the R2 contract.
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

1. Get #16 M3 Graph Studio exact-PMTiles inspector CI green and merge it.
2. M4: publish visual artifacts independently through the immutable R2 contract and add Graph Studio visual publication status/control.
3. Verify issue #16 acceptance and close it after M4.
4. Keep #17 POI/search separate.
## Handoff maintenance

Update this file after each meaningful architectural decision or milestone transition. The automatic workflow updates only `handoff/state.json`.
