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

Issue #13 is complete. PRs #24-#25 delivered deterministic graph/boundary diffing.
PR #27 merged the fingerprint-bound pair-manifest foundation.
PR #28 merged stable OSM frontier-road inventory generation.
PR #29 merged independent Graph A/B Valhalla correlation.
PR #30 merged lossless Graph A × Graph B crossing-candidate generation.
PR #31 merged local plain-Valhalla exact-edge crossing proof.

Current #26 milestone branch: `connectivity-runtime-artifact-m6`.

Current runtime compilation architecture:
- only `PROVEN` candidates are promoted into the RoadPilot runtime artifact;
- within each promoted crossing, only mode/direction combinations with successful exact-edge Valhalla proof are marked supported;
- rejected/inconclusive proof records remain development diagnostics and are not shipped as routing metadata;
- pre-proof locate access/heading hints are not copied into the runtime artifact;
- exact A/B correlated coordinates and exact graph-local IDs are retained because the artifact is fingerprint-bound to those graph builds;
- candidate/proof SHA-256 hashes are embedded for reproducibility;
- a VALIDATED artifact may be empty, in which case RoadPilot must fall back to F8 rather than inventing connectivity.

Architectural split for #26:
- stable physical discovery evidence is keyed by OSM/GPS/road evidence and relevant boundary fingerprints;
- graph-local correlation/proof evidence is valid only for the exact graph fingerprints;
- only plain-Valhalla route + exact-edge evidence may promote a candidate;
- runtime metadata contains proven capabilities, not diagnostic guesses;
- F8 remains runtime fallback for missing/stale/ambiguous or empty validated metadata.
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

1. Get the compact PROVEN-only runtime connectivity artifact milestone green and merged.
2. Add multi-hop region-chain composition over validated neighboring-pair runtime artifacts.
3. Use boundary fingerprints for surgical stale detection/rebuild.
4. Expose validated runtime connectivity/current-vs-stale state in Graph Studio.
5. Keep F8 as runtime fallback for missing, stale, ambiguous or empty metadata.
## Handoff maintenance

Update this file after each meaningful architectural decision or milestone transition. The automatic workflow updates only `handoff/state.json`.
