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

**Graph Studio exact graph/boundary diffing**, issue #13.

Issue #11 is complete. PRs #20-#23 delivered the Border Inspector core, road diff, handoff artifact overlays, and diagnostics export.

Current #13 milestone branch: `graph-studio-boundary-fingerprints-m1`.

Implementation direction:
- new builds emit deterministic per-`.gph` tile hashes;
- graph-wide and internal-only tile fingerprints are recorded;
- each configured neighboring Geofabrik source receives a conservative boundary/overlap fingerprint;
- Build Comparison reports added/removed/modified tiles and REFRESH/UNCHANGED for each neighbor;
- changed boundary tiles are visualized on the map;
- road/edge-level changed-road visualization follows as the next #13 refinement.
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

PRs #5 and #6 are older transition-artifact/offline-transition experiments. Do not merge or revive them blindly. Compare their useful concepts against the current Graph Studio roadmap and issue #13/build-time connectivity work.

## Next exact action

1. Finish and merge the first issue #13 deterministic graph/boundary-index milestone.
2. Add road/edge-level changed-border visualization for indexed build A/B pairs.
3. Use boundary fingerprints to drive build-time connectivity manifests / F8 seeds.
4. Then proceed to R2 publication, visual-map artifact, POI/search artifact, and scheduled updates as defined in `ROADMAP.md`.
## Handoff maintenance

Update this file after each meaningful architectural decision or milestone transition. The automatic workflow updates only `handoff/state.json`.
