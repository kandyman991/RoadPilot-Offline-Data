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

**Issue #35 — precomputed per-region border-entry → border-exit routing matrices.**

Issue #26 is completed and remains the foundation:
- stable OSM frontier discovery;
- independent Graph A/B correlation;
- exact-edge Valhalla crossing proof;
- compact validated runtime connectivity;
- multi-hop chain composition;
- graph/boundary fingerprint freshness;
- F8 fallback.

Organic Maps' cross-MWM architecture revealed the next missing layer: a valid A→B crossing and a valid B→C crossing do not by themselves prove that the selected entry into B can reach the selected exit from B. #35 adds that proof and cost at build time.

Target #35 architecture:
- collect every validated RoadPilot border anchor touching a region;
- classify graph-bound entry/exit states per Motorcycle and Car;
- use plain Valhalla many-to-many / sources-to-targets on the regional graph;
- store sparse reachable entry→exit time and distance metrics;
- bind those weights to the exact regional graph fingerprint;
- keep unreachable pairs explicit;
- use the matrix for genuine FASTER/SHORTER sparse-chain ranking;
- keep multiple candidate chains until detailed Valhalla routing resolves the final journey;
- inspect topology/weights/freshness in Graph Studio;
- execute #35 before #14 Cloudflare R2 publication.

Do not copy Organic Maps' strict same-geometry twin assumption. RoadPilot keeps independent A/B correlation and fingerprint-bound graph-local bindings.
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

1. Implement #35 regional connector matrices in milestones.
2. First milestone: define the graph-fingerprint-bound matrix artifact and deterministic anchor inventory for one regional graph.
3. Next: populate entry→exit reachability/time/distance with plain Valhalla for Motorcycle and Car.
4. Then replace adjacency-only multi-hop scoring with matrix-backed FASTER/SHORTER candidate chains and add Graph Studio inspection.
5. After #35 is green and merged, proceed to #14 Cloudflare R2 publication.
## Handoff maintenance

Update this file after each meaningful architectural decision or milestone transition. The automatic workflow updates only `handoff/state.json`.
