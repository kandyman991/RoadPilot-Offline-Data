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

**Issue #35 — regional connector matrices, milestone 3: sparse hierarchical composition.**

Merged #35 milestones:
- PR #36 — deterministic per-region connector anchor inventories with proven Motorcycle/Car ENTRY/EXIT roles;
- PR #37 — Valhalla sources-to-targets entry→exit matrices, with normal-route + trace exact first/last DirectedEdge validation and explicit REACHABLE/UNREACHABLE/INCONCLUSIVE cells.

Current branch: `regional-connector-matrix-m3`.

M3 architecture:
- keep #26's adjacency-only composer intact as fallback/diagnostic behavior;
- add a stricter matrix-backed hierarchical composer;
- a selected crossing enters an intermediate region at its exact connector ENTRY anchor;
- the next crossing may leave that region only if the regional matrix has a `REACHABLE` ENTRY→EXIT cell for the requested mode;
- `UNREACHABLE` and `INCONCLUSIVE` cells are unusable, never penalized into existence;
- matrix distance/time is the only build-time intermediate-region ranking cost;
- tiny local border-proof probe metrics are not counted as journey costs;
- FASTER uses proven intermediate time; SHORTER uses proven intermediate distance;
- score scope is explicitly `INTERMEDIATE_REGIONS_ONLY` because origin/destination legs depend on the live route query;
- multiple sparse crossing chains are retained for final detailed Valhalla selection;
- graph/inventory/matrix fingerprints must agree exactly.

Issue #26 remains the physical-crossing/proof foundation and F8 remains fallback for missing/stale/ambiguous precomputed metadata.
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

1. Get #35 M3 matrix-backed hierarchical composition green and merged.
2. M4: expose connector anchors, REACHABLE/UNREACHABLE/INCONCLUSIVE matrix cells, weights and freshness in Graph Studio.
3. Integrate connector-matrix staleness/surgical rebuild state into the lifecycle and close #35 when acceptance is met.
4. Then proceed to #14 Cloudflare R2 publication.
## Handoff maintenance

Update this file after each meaningful architectural decision or milestone transition. The automatic workflow updates only `handoff/state.json`.
