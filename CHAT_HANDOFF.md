# Chat Handoff — RoadPilot Offline Data / Graph Studio

## M3 AI Control implementation — branch in review (2026-10-13)

- Branch `graph-studio-ai-control-m3-valhalla-verify`. On-demand `--ai-verify-route`
  and Tauri `ai_verify_route` share one Rust verification engine and the existing
  Valhalla route request and polyline decoding helpers.
- Input allowlists, strict local graph checks, no shell, 20s timeout and 1-MiB
  output cap; structured endpoint-checked results without raw stderr.
- Graph work/tiles must exist; no source downloads, writes, builds or publishing.
  Cross-region validity and retained package fingerprint are explicitly not proven.
- NEXT: check PR Linux Rust tests and validation CI; merge only if green. Verify
  installed commands later on Legion. Pending Austria full build remains untested.



## Latest verified merge — 2026-10-13: AI Control M2 PR #66

- PR: https://github.com/kandyman991/RoadPilot-Offline-Data/pull/66 — **merged**
  as `b3a4400e311bf1c2fe9c085cac0487888aa3ae38`.
- Both required PR checks **green** on head `8426755b`: offline-data validation
  and Graph Studio Linux build, including M1/M2 Rust tests and AppImage/DEB.
  Post-merge rolling Linux release build was triggered; verify its published
  tag/assets separately before claiming users can install M2.
- Shared Rust `diagnose` operation works via Tauri `ai_control_command` and
  packaged `--ai-diagnose` without a GUI or remote listener. It summarizes only
  **recorded** Valhalla validation from manifests, previously exported border
  reports (may be stale), and sanitized last build outcome. No raw stderr/credentials
  are surfaced; no new route is run or graph altered.
- For build completions **after installing M2**, existing Graph Studio build queue
  writes one allowlisted `diagnostics/latest-build.json` entry. Its safe
  failure category recognizes the historical `Node ID twice in input` signature
  if the log line is observed; this does not assert Austria is fixed on-device.
- M1 PR #65 merged previously as `b3f5539a`, introducing
  `--ai-capabilities` and `--ai-inspect`; M2 is additive and read-only.
- **NEXT EXACT ACTION:** verify the rolling Linux release assets include M2's
  merge, update Graph Studio on Legion, run `--ai-capabilities`,
  `--ai-inspect`, `--ai-diagnose`; compare inventories/reports to real files.
  Repeat Austria build using the existing PBF cache to verify PR #64 source
  normalization and actual Valhalla crossing proof. Desktop test is **not yet done**.
- After real tests, consider M3 explicit permissioned and instrumented
  Valhalla revalidation; do not silently rebuild/publish or infer GUI state
  from a headless snapshot.


## Latest verified merge — 2026-10-13: PR #64 Austria overlapping PBF fix

- Device failure: Austria build, configured with 18 extracts including `austria`, `dach`, `alps`, and neighbors, failed `osmium extract` with `Node ID twice in input`, before Valhalla; on-device console supplied by user.
- Cause: `osmium merge` deduplicates identical versions but emits multiple revisions of a node/way when overlapping Geofabrik snapshots differ in time. Normal `osmium extract` refuses history-like inputs.
- PR https://github.com/kandyman991/RoadPilot-Offline-Data/pull/64 — **merged** as `541656ed87a534c27cb491daa5fafa5c5d18aee6`; required CI repository validation and Linux app build **both green**. CI uses real Osmium commands on synthetic overlapping versions to reproduce old failure and verify normal extraction after fix.
- Production pipeline now first uses cached exact .poly geometry to select smaller sources contributing novel buffer coverage (automatically skips redundant aggregate/thematic PBFs, no region hardcodes), then streams remaining `osmium merge -f pbf` into `osmium time-filter -F pbf` to normalize current object versions. Keeps memory low and avoids another huge intermediate PBF.
- `osmium check-refs` remains mandatory; graph construction/Valhalla proof and raw cached Geofabrik sources untouched. Users **must not delete PBF cache or builds** to apply fix.
- **NEXT EXACT ACTION:** Verify rolling release tag `roadpilot-graph-studio-linux` points to merged commit `541656e` and assets are published. Update Ubuntu .deb on Legion, re-run the same Austria build with the existing cache and report source-pruning logs, absence of duplicate ID, real route validation, and any further errors. Full Austria desktop validation **not yet done**.


## Latest merged milestone — 2026-10-13: PR #63 shared source cache

- PR https://github.com/kandyman991/RoadPilot-Offline-Data/pull/63 **merged** as commit `7d255b40e7939fe4ea2cdd89cfb1bab0ca3a5084`. Both required PR CI checks green; real Legion full build/rebuild is **not yet device tested**.
- One shared `work/cache/<source-id>.osm.pbf` for routing and visual, hardlink-migrating earlier visual source files; 24h checksum sidecar detection, atomic MD5-checked downloads, fail-closed force refresh and explicitly warned offline reuse.
- Repeated unchanged graph build skips broad PBF merge, buffering extraction and administrative data regeneration via `work/<region>/build/source-preparation.json` keyed by all input SHA-256s, exact polygon SHA-256 and Valhalla engine version. Retained prepared outputs verified by SHA-256. Temporary full `merged.osm.pbf` deleted after admin DB construction.
- Build panel exposes **Force source re-download** unchecked by default. Existing independently versioned routing, visual and search artifacts remain independent.
- Limits: first uncached use still downloads whole required Geofabrik leaf neighbors. Admins still require complete broad source context for *first* build; cropping this prematurely risks truncated administrative relations. See `docs/geofabrik-shared-cache.md`.

**Next exact action:** Verify rolling Linux release tag points to `7d255b4`, install updated .deb on Legion, perform one small-border-region graph build and a version-bumped repeat. Confirm cache hit and skipped full-source merge; compare validated artifacts/Valhalla route diagnostics. After real smoke tests evaluate smaller boundary-only downloads by safe admin-context filtering or diff-based updates — do not assume source byte-range clipping works.


## Latest verified merge — 2026-10-13: PR #62 automatic region builds

- PR: https://github.com/kandyman991/RoadPilot-Offline-Data/pull/62 — **merged into main**.
- Merge SHA: `a0ba5f653f3d3527d36495121154b286e65cee9c`.
- PR-head CI: validation and Graph Studio Linux build **both green**; no real large regional graph build or Legion smoke test completed.
- User-visible workflow: select a Geofabrik catalog region → Build selected → Graph Studio auto-saves a routing-only config with exact buffered sources → builds Valhalla tiles → tries to discover a real nominal-border road route with Valhalla.
- Safety: new `routing.validationMode=auto` allows **no initial route**, but package publication requires at least one actual Valhalla-proved road crossing whose decoded routed polyline crosses the nominal boundary. No fallback fabricated GPS, no unconditional green. Existing manual configs remain compatible.
- Region editor provides **Pick start/end on map**, draggable pins synchronized to coordinate fields, and Clear pins. Manual route is fallback if auto proof fails.
- Visual and search packs are **not** rebuilt by an automatic routing-only region config.
- CI includes offline synthetic positive/negative proof tests; device test evidence **missing**.

**Next exact action:** Confirm the rolling Linux release tag and package assets were refreshed to merge SHA `a0ba5f6`; update Graph Studio on Legion. Exercise Belgium from the catalog with *Build selected* and capture the build console, actual Valhalla proof, and any errors. If auto crossing cannot be proved, inspect the retained tile build and select two road points via map pins; do not hard-code an exception. Explicitly check download footprint of source PBF neighbors (especially coastal intersections).

The previous October 6 search/POI notes below remain historical and are not proof of the current work queue.


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

**Issue #17 — POI/search production and inspection, milestone 1: Android-compatible search artifact foundation.**

Current branch: `search-artifact-foundation-m1`.

M1 architecture:
- preserve `roadpilot-overture-v1` so current Android can still install/search the generated database;
- `roadpilot_search_v1.py` mirrors current Android normalization, SQL token retrieval, dedupe and confidence/exact/prefix/contains/brand/token scoring;
- Italy Nord-Est SARP validation runs the runtime-style query `SARP Food Technologies`;
- pin the Overture source client to `overturemaps 1.0.2` and record the exact Overture data release;
- SQLite metadata records source release/client/version/input SHA;
- retained manifests add search/source fingerprints and runtime validation results while retaining all Android-required fields;
- retained builds are atomic under `dist/search/<region>/<version>/` and cannot overwrite an existing version;
- CI uses synthetic Overture features to prove deterministic SQLite bytes, SARP ranking parity, accent normalization, immutable version refusal and corrupt database rejection.

M2 will evolve the schema/runtime for categories and proximity rather than pretending v1 already supports them.
M3 is Graph Studio search/POI inspection and comparison.
M4 is independent search R2 publication.
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

1. Get #17 M1 retained search-pack/runtime-parity CI green and merge it.
2. M2: add category/source/address fields and proximity/category ranking through an explicit compatibility-tested schema evolution.
3. M3: add the Graph Studio Search/POI workspace and retained-build comparison.
4. M4: publish search independently through the immutable R2 contract.
## Handoff maintenance

Update this file after each meaningful architectural decision or milestone transition. The automatic workflow updates only `handoff/state.json`.


## Persistent ChatGPT continuity

For all future sessions read `AGENTS.md` and the decision/rejection registers under `docs/`. At every meaningful milestone update this curated handoff with exact tested results and next action, independently of `handoff/state.json`. See `docs/CONTINUITY_PLAYBOOK.md`.
