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

**Graph Studio build-time cross-region connectivity metadata**, issue #26.

Issue #13 is complete. PR #24 added deterministic graph/boundary fingerprints and PR #25 added
retained-build road-level boundary diffing.

Current #26 milestone branch: `connectivity-pair-manifest-m1`.

Current implementation:
- `roadpilot.cross-region-connectivity` v1 schema;
- generator that binds a directed RoadPilot region pair to both graph fingerprints and both mutual boundary fingerprints;
- standard-library validator;
- hosted synthetic smoke test for mutual boundary identity;
- initial artifacts are `STABLE_PHYSICAL` / `UNPROVEN` with no graph-local IDs.

Architectural split for #26:
- stable physical discovery evidence is keyed by OSM/GPS/road evidence and relevant boundary fingerprints;
- exact graph-local bindings may be added later but are fingerprint-bound and cheap to regenerate;
- F8 remains runtime fallback for missing/stale/ambiguous metadata.
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

1. Get the first #26 pair-manifest contract/generator/validator milestone green and merged.
2. Add build-time boundary-edge inventory without using graph-local IDs as cross-build identity.
3. Generate physical crossing candidates from stable road/GPS evidence.
4. Validate candidates with plain Valhalla for motorcycle/auto and both travel directions.
5. Compile validated region-pair metadata for RoadPilot; keep F8 as fallback.
## Handoff maintenance

Update this file after each meaningful architectural decision or milestone transition. The automatic workflow updates only `handoff/state.json`.
