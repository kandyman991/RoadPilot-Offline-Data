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

**Issue #16 — visual map production/inspection, milestone 4: independent visual R2 publication.**

M1 is merged in PR #43.
M2 is merged in PR #44.
M3 is merged in PR #45; exact-head repository validation and Graph Studio packaging were green after fixing one Rust PathBuf borrow/move error.

Current branch: `visual-map-r2-publication-m4`.

M4 architecture:
- `prepare_visual_publication.py` revalidates the exact retained visual pack before a publication plan can exist;
- production visual publication requires the bound road index and `missingRoadCount=0`;
- immutable visual objects are PMTiles, manifest, checksum and road-index JSON;
- visual release metadata includes visual/profile/source fingerprints, tilemaker version, tile counts/zoom/layers and road-validation counts;
- visual namespace is `visual/<region>/<version>/...` with mutable `visual/<region>/latest.json`;
- routing remains under `routing/<region>/...` with its own latest pointer;
- the existing generic R2 uploader/history/rollback backend is reused unchanged;
- fake-R2 CI publishes routing and visual into the same bucket and proves visual publish/activation leaves routing latest unchanged;
- Graph Studio's R2 panel now switches between Routing graph and Visual PMTiles retained builds;
- Tauri selects the matching safe manifest root and publication-plan preparer based on artifactKind;
- remote status/history queries use the selected `routing` or `visual` prefix;
- rollback accepts only safe release keys under those two namespaces;
- publication artifact selection is locked while an upload is running.

Cloudflare R2 is still not connected to a real bucket; do not claim live credentials have been tested.
POI/search remains separate in issue #17.
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

1. Get #16 M4 visual R2 publication CI green and merge it.
2. Verify all #16 acceptance criteria across PRs #43-#46 and close issue #16.
3. Update ROADMAP/CHAT_HANDOFF to mark visual map production/inspection complete.
4. Start #17 POI/search production/inspection as its own artifact pipeline.
## Handoff maintenance

Update this file after each meaningful architectural decision or milestone transition. The automatic workflow updates only `handoff/state.json`.
