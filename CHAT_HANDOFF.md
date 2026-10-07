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

## Current focus\n\n**Issue #17 — POI/search production and inspection, milestone 1: Android-compatible search artifact foundation.**\n\nCurrent branch: `search-artifact-foundation-m1`.\n\nM1 architecture:\n- preserve `roadpilot-overture-v1` so current Android can still install/search the generated database;\n- `roadpilot_search_v1.py` mirrors current Android normalization, SQL token retrieval, dedupe and confidence/exact/prefix/contains/brand/token scoring;\n- Italy Nord-Est SARP validation runs the runtime-style query `SARP Food Technologies`;\n- pin the Overture source client to `overturemaps 1.0.2` and record the exact Overture data release;\n- SQLite metadata records source release/client/version/input SHA;\n- retained manifests add search/source fingerprints and runtime validation results while retaining all Android-required fields;\n- retained builds are atomic under `dist/search/<region>/<version>/` and cannot overwrite an existing version;\n- CI uses synthetic Overture features to prove deterministic SQLite bytes, SARP ranking parity, accent normalization, immutable version refusal and corrupt database rejection.\n\nM2 will evolve the schema/runtime for categories and proximity rather than pretending v1 already supports them.\nM3 is Graph Studio search/POI inspection and comparison.\nM4 is independent search R2 publication.\n## Critical architectural decisions

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

## Next exact action\n\n1. Get #17 M1 retained search-pack/runtime-parity CI green and merge it.\n2. M2: add category/source/address fields and proximity/category ranking through an explicit compatibility-tested schema evolution.\n3. M3: add the Graph Studio Search/POI workspace and retained-build comparison.\n4. M4: publish search independently through the immutable R2 contract.\n## Handoff maintenance

Update this file after each meaningful architectural decision or milestone transition. The automatic workflow updates only `handoff/state.json`.
