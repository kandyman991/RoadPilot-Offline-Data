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

**Final completion of Graph Studio build-time cross-region connectivity metadata**, issue #26.

Merged milestones:
- PRs #24-#25 — deterministic graph/boundary diffing;
- PR #27 — fingerprint-bound region-pair foundation;
- PR #28 — stable OSM frontier-road inventory;
- PR #29 — independent Graph A/B Valhalla correlation;
- PR #30 — lossless Graph A × Graph B candidate generation;
- PR #31 — exact-edge plain-Valhalla motorcycle/auto proofs;
- PR #32 — compact PROVEN-only runtime connectivity;
- PR #33 — validated multi-hop region-chain composition.

Current final branch: `connectivity-finalize-m8`.

Final lifecycle work on this branch:
- proven Valhalla route distance/time is promoted into runtime metadata only for supported mode/directions;
- crossing alternatives and all simple valid region chains up to maxHops are ranked post-proof for FASTER or SHORTER;
- graph-only fingerprint changes mark only affected pair metadata STALE with `REBIND_GRAPH`, preserving stable physical discovery;
- relevant boundary fingerprint changes mark only that neighboring pair STALE with `REDISCOVER_BOUNDARY`;
- missing current graphs are `UNRESOLVED` / `WAIT_FOR_GRAPH`, never guessed;
- Graph Studio Border Inspector recognizes generated `roadpilot.crossing-candidates` and validated `roadpilot.runtime-connectivity` artifacts;
- Graph Studio shows validation state separately from CURRENT/STALE and checks both exact graph and relevant boundary fingerprints for new artifacts;
- F8 remains fallback for missing, stale, ambiguous, empty, or unchainable metadata.

This final branch does not reintroduce any legacy fixed-seam, F6, hard-heading, hard-separation, or graph-id-as-cross-build-identity experiments.
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

1. Get the final #26 lifecycle PR green and merge it.
2. Close issue #26 only after exact-head repository validation and Graph Studio packaging are green.
3. Close legacy experimental PRs #5 and #6 as superseded so they cannot be mistaken for current architecture.
4. Then continue with the next RoadPilot Offline Data roadmap milestone.
## Handoff maintenance

Update this file after each meaningful architectural decision or milestone transition. The automatic workflow updates only `handoff/state.json`.
