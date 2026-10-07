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

**Issue #26 — build-time cross-region connectivity metadata — is completed.**

Completed delivery:
- PRs #24-#25 — deterministic graph/boundary diffing;
- PR #27 — fingerprint-bound region-pair foundation;
- PR #28 — stable OSM frontier-road inventory;
- PR #29 — independent Graph A/B Valhalla correlation;
- PR #30 — lossless Graph A × Graph B candidate generation;
- PR #31 — exact-edge plain-Valhalla motorcycle/auto proofs;
- PR #32 — compact PROVEN-only runtime connectivity;
- PR #33 — validated multi-hop region-chain composition;
- PR #34 — proven FASTER/SHORTER ranking, surgical graph/boundary refresh planning, and Graph Studio UNPROVEN/VALIDATED + CURRENT/STALE inspection.

PR #34 exact head passed full repository validation, TypeScript and Rust compilation, AppImage/.deb packaging and artifact upload before merge.

Legacy experimental PRs #5 and #6 are closed as superseded and must not be revived.

Production connectivity architecture:
- stable physical discovery is keyed by OSM/GPS/road evidence and relevant boundary fingerprints;
- graph-local correlation/proof evidence is valid only for exact graph fingerprints;
- only exact-edge plain-Valhalla proof can promote a crossing to runtime metadata;
- crossing alternatives and region chains are ranked for FASTER/SHORTER only after proof;
- graph-only changes use `REBIND_GRAPH`; relevant boundary changes use `REDISCOVER_BOUNDARY` only for the affected pair;
- F8 remains fallback for missing, stale, ambiguous, empty, or unchainable metadata;
- no fixed-seam, F6, hard-heading, hard-separation, or graph-id-as-cross-build-identity logic is part of the current architecture.
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

1. Issue #26 requires no further implementation work.
2. The next planned RoadPilot Offline Data milestone is #14, the Cloudflare R2 publication manager.
3. Visual-map production (#16) and POI/search production (#17) remain separate later milestones.
## Handoff maintenance

Update this file after each meaningful architectural decision or milestone transition. The automatic workflow updates only `handoff/state.json`.
