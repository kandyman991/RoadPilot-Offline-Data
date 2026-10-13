# Chat Handoff — RoadPilot Offline Data / Graph Studio

## Graph Studio incomplete-arrival instrumentation — branch in review (2026-10-14)

- Reproduced **Trento → Innsbruck** on `italy-nord-est` via Legion M3:
  `46.064320,11.119191` → `47.250124,11.395549`,
  `route_endpoints_mismatch`, 1,566.47 m short, start offset 25.25 m,
  175.958 km / 7312.182 s, 4,308 vertices, 181 ms, exit 1.
- Existing Graph Studio GUI misleadingly reported that route as success
  because it inspected trip status and geometry but not decoded endpoints.
- Branch `graph-studio-route-arrival-evidence` adds **shared** endpoint
  assessment for M3 + GUI, includes actual start/end lat/lng in M3
  results, and makes GUI show INCOMPLETE, deviations, red requested end
  marker, amber actual stopping-point marker and map bounds including both.
  No region graph, OSM input, or F8 algorithm changes.
- Issue #69: https://github.com/kandyman991/RoadPilot-Offline-Data/issues/69
- **NEXT EXACT ACTION:** get Rust/UI CI green; merge the PR; verify rolling
  `.deb` release points to merge; on Legion rerun exact journey, record
  `route.actualEnd`, and check whether that position approaches Italy
  Nord-Est's actual buffered road coverage edge. Avoid guesses from screenshots.


## Reproducible cross-border incomplete route: Trento → Innsbruck (2026-10-14)

- Two new Legion screenshots show Graph Studio GUI selected `italy-nord-est`,
  motorcycle, requested start `46.064320,11.119191` (Trento) to end
  `47.250124,11.395549` (Innsbruck). GUI reports 175.96 km, 2h 1m,
  Valhalla time 201 ms, successful route.
- Blue route visibly crosses Brenner/Italy–Austria national border yet
  appears to terminate well south of the **red requested endpoint** in a
  zoomed Innsbruck screenshot. Exact actual route endpoint/offset not yet
  known; don't infer precise distance from map screenshot alone. Italy
  Nord-Est's 25 km border buffer might explain missing farther-north roads.
- **Next exact test:** Run
  `roadpilot-graph-studio --ai-verify-route italy-nord-est
  46.064320 11.119191 47.250124 11.395549 motorcycle` on installed
  Legion CLI and record JSON `route.endOffsetMeters`, `failureCategory`
  and exit code. M3 tests actual geometry arrival to 150 m, GUI just
  accepts trip.status and geometry. M3 and GUI have different default
  costing_options, so route selections might differ.
- Case added to issue #69:
  https://github.com/kandyman991/RoadPilot-Offline-Data/issues/69
  Do not rebuild Italy region, delete source/PBF cache, or assume national
  border crossing demonstrates independent graph handoff.
  

## GUI routing fixed for known Austria–Germany buffered-graph test (2026-10-13)

- User screenshot on Legion after installing PR #68 demonstrates an actual
  standard Graph Studio **GUI route displayed successfully** with Austria
  active. This supersedes the old assumption that GUI cannot route at all.
- Start `47.582889,12.162319`, destination `47.609970,12.200709`,
  motorcycle. GUI: **4.72 km**, **14m48s**, **221 ms**. Independent M3 headless
  verification of same journey: **4.725 km**, 161 ms, start/end offsets
  8.36 m/4.32 m.
- User explicitly confirms **German graph is NOT installed**; German-side
  destination falls **inside Austria's configured 25 km border buffer**.
  Graph Studio drew the connected route normally across the national boundary
  by using neighboring road coverage inside the *same* Austria Valhalla graph.
- National border != regional graph coverage boundary. This confirms ordinary
  buffered single-graph routing in Austria, but **does not** verify handoffs
  between two independently built graphs or eliminate RoadPilot F8 outside
  buffered coverage.
- PR #68 GUI parity fix **verified for this reproducible Austrian route**;
  do not claim all countries/routes fixed (prior screenshot shows GUI failure
  for a longer Italy→Austria request that may exceed Austria graph coverage).
- Evidence added to issue #69: https://github.com/kandyman991/RoadPilot-Offline-Data/issues/69
- **NEXT EXACT ACTION:** reproduce user-observed border crossing that finishes
  short of destination; capture start/destination and actual route last point,
  use M3 `--ai-verify-route` to distinguish border proof from destination
  arrival. No graph rebuild, cache purge or forced handoff heuristics.


## GUI route failure after PR #68 update — screenshot from Legion (2026-10-13)

- Screenshot shows installed GUI's standard Route Planner reporting
  `Route failed for austria: Region austria: Valhalla route valhalla_nonzero_exit`.
  Build/region inventory is visible; selected graph badge says `Austria`,
  25 km border buffer. Previous generic traffic-warning output is now a
  stable error category, so PR #68 GUI code appears installed.
- **Screenshot coordinates:** start `46.151338,12.999947` (Friuli,
  Italy, visibly southwest of Austrian boundary), end
  `47.813453,16.249428` (eastern Austria); motorcycle. The start
  appears beyond Austrian 25 km buffer. This failure alone does **not**
  prove Austria-to-Austria routing fails or demonstrate broken graph tiles.
- Screenshot footer also shows repeated `valhalla_nonzero_exit` for
  `austria` and a prior `italy-centro` route. The shared GUI runner
  (`ai_verify::valhalla_result`) discards stderr and returns just
  `valhalla_nonzero_exit` on any nonzero status, even if stdout has
  structured Valhalla error JSON. Thus actual engine code remains unknown.
- **Important request difference:** GUI always sends `costing_options`
  for motorcycle/auto with `use_highways`, `use_tolls`, `use_ferry`=1.0
  defaults. Headless M3 (success in 161 ms) omits costing_options.
  Need test exact same endpoints in both paths before attributing cause.
- **NEXT TEST:** select Austria in GUI and run the *previously proven* pair
  `47.582889,12.162319 -> 47.609970,12.200709`, Motorcycle,
  expansion disabled; compare with M3's passed 4.725 km. If GUI fails,
  investigate caller's executable PATH and/or default GUI costing_options,
  instrument sanitized Valhalla exit + error_code from bounded response;
  do not rebuild, purge cache or blame optional traffic.tar without proof.
- Existing issue #69 tracks separate border crossed vs destination reached
  check; do not conflate it with this GUI subprocess failure.


## Austria cross-border partial-route observation — issue #69 (2026-10-13)

- User reports that before GUI routing stopped working, Graph Studio's
  Austria local graph **successfully routed across national borders several
  times**. Some tests reached the requested destination; others crossed
  the border but ended short, resembling the earlier RoadPilot F8 partial-route
  symptom. Specific failed GPS pairs/miss distances were not retained.
- Code verified: M3 `ai_verify::evaluate` requires start/end routed geometry
  within 150 m to pass; GUI `plan_route` checks Valhalla status/geometry
  but doesn't check endpoint arrival. Automatic border discovery verifies a
  real national-border crossing with a deliberately looser **5-km** endpoint
  tolerance. Those prove **different things**.
- Crossing a national boundary inside one buffered Austria graph is *not* proof
  of a handoff between two independent regional graphs. Potential explanations
  for partial routes include snapped endpoints outside actual graph coverage
  or disconnected road coverage; none confirmed without a failed GPS sample.
- Tracked work: https://github.com/kandyman991/RoadPilot-Offline-Data/issues/69
  ("distinguish proven border crossing from destination arrival"): show actual
  route-end offsets, separately report crossing vs arrival, regression-test
  clipped routes, reuse M3's endpoint geometry evaluation.
- **NEXT EXPERIMENT:** once the PR #68 GUI launcher fix is installed, re-run
  one known cross-border route that arrives and one that stops short; record
  start/destination coordinates and actual last geometry point. Do not rebuild
  Austria, add hard-coded F8 portals, or raise border proof to full cross-graph
  connectivity on this evidence alone.


## GUI route parity fix — PR #68 merged (2026-10-13)

- User confirmed that standard GUI routing failed even Austria-to-Austria,
  although headless M3 routed the same Austria coordinates in 161 ms
  (4.725 km, 181 vertices and 8.36 m/4.32 m endpoint offsets).
- PR https://github.com/kandyman991/RoadPilot-Offline-Data/pull/68 **merged**
  as `a113eb84b4f9464967f46152c6fee0d9b3e49884`. Final PR head
  `827d4740b9a3ac993b3d981d96bf5257d2f476ba` has **both checks green**:
  Graph Studio Linux build plus Rust tests and offline-data repo validation.
- Code review showed GUI `normalize_process_path` prepended pyvalhalla native
  tool dir for all Valhalla operations, whereas headless M3 used the proven
  pyvalhalla launcher. Fix preserves the launcher for normal GUI routes,
  expansions, locate, handoff probes and M3, all via bounded JSON-aware
  execution; native binary tile rendering remains unchanged.
- Optional route-expansion failures cannot mask a successful standard route.
  GUI failure messages now identify region and a bounded failure category,
  rather than printing unrelated optional traffic warnings as root cause.
- Post-merge release workflow:
  https://github.com/kandyman991/RoadPilot-Offline-Data/actions/runs/38476097939
  **running** at this handoff update. The rolling `.deb` is not an
  installable #68 fix until its release notes explicitly cite `a113eb84`.
- **NEXT EXACT ACTION:** after the rolling release identifies merge
  `a113eb84`, upgrade the existing `.deb` on Legion (retain
  `~/RoadPilotGraphStudio/` intact), restart the app, select region
  `austria` and calculate:
  `47.582889,12.162319 -> 47.609970,12.200709`, Motorcycle.
  Confirm route displayed and distance around the proven 4.725 km.
  Retest route expansion separately. CI is green but the GUI fix remains
  **not yet proven on the physical Legion**; do not call it device-verified.
- Never delete PBF cache or rebuild graphs just for this GUI issue.

## Legion M3 verified — 2026-10-13: successful real Austria route

- User ran the *installed* headless M3 CLI:
  `roadpilot-graph-studio --ai-verify-route austria
  47.582889 12.162319 47.609970 12.200709 motorcycle`.
- **On-device PASS; exit code 0**, `passed=true`,
  `routeReplayed=true`, `failureCategory=null`, `elapsedMs=161`,
  `graphSource=local_working_graph`.
- Actual Valhalla result: 4.725 km, 887.728 s, 181 decoded vertices;
  start offset 8.361177 m, end offset 4.315425 m (both within the M3
  150 m tolerance). This is **real local routing evidence**, not a retained
  manifest replay or cross-region proof.
- This completes first real-device execution/verification of M1, M2 and M3
  AI CLI commands. It does NOT establish graph fingerprints against retained
  packages or prove every region or boundary.
- Earlier GUI route failed with 367 tile count and traffic warnings. Austria
  local graph has 338 retained tiles while Italy Nord-Est has 367. Since M3
  works on the Austria region, leading hypothesis is wrong GUI active region;
  confirm GUI region selection before classifying an engine bug.
- **NEXT EXACT ACTION:** in Graph Studio select Austria explicitly, re-run
  the same coordinates in the GUI and compare its result. If it still fails,
  inspect full Valhalla route stdout/status and selected config, then improve
  error surfacing. Avoid rebuilding or clearing cached OSM data. Next broader
  milestone can implement a permissioned local bridge to normal ChatGPT.

## Legion route failure follow-up — 2026-10-13 (investigating)

- User reported: `Route failed: 2026-10-13 21:50:23 [INFO] Tile extract
  successfully loaded with tile count: 367 ... [WARN] /data/valhalla/traffic.tar
  No such file or directory ... [WARN] Traffic tile extract could not be loaded`.
- The exact `Route failed:` prefix is generated by Graph Studio frontend's
  **standard GUI route planner** (`graph-studio/src/main.ts`,
  `runStandardRoute`), not M3 headless `--ai-verify-route`. On a nonzero exit,
  `plan_route` currently displays raw Valhalla stderr, which may be only
  informational warnings rather than the actual routing error.
- **367 tiles** matches recorded Italy Nord-Est graph; recorded Austria
  graph has **338**. May indicate GUI was testing Kufstein coordinates
  with Italy active. This is a hypothesis, not yet confirmed from actual
  GUI region selection/Valhalla config. Missing optional traffic archive
  alone does not establish root cause.
- **NEXT EXACT ACTION:** run
  `roadpilot-graph-studio --ai-verify-route austria 47.582889 12.162319
  47.609970 12.200709 motorcycle` and inspect complete JSON + exit code.
  If failed, inspect the selected config and returned failure category;
  avoid rebuilding or disabling checks without evidence. GUI error handling
  could be improved afterward to show engine error status and selected region.

## Legion on-device results — 2026-10-13: AI M1/M2 inspection

- User installed the Graph Studio Linux package on `mircea-gitmachine`
  (Legion, Ubuntu 26.04) and supplied **actual terminal JSON output** from
  `roadpilot-graph-studio --ai-inspect` and `--ai-diagnose`.
- M1: workspacePresent=true, runtime.attached=false (correct for headless),
  warnings=[], 3 configured routing regions: `austria` (18 sources, auto
  validation), `belgium` (16), `italy-nord-est` (9).
- M1 retained routing inventories (all package `2026.10.13-1`):
  `austria`: 338 tiles, builtAtUtc 2026-10-13T21:20:33.468220Z;
  `italy-nord-est`: 367 tiles, builtAtUtc 2026-10-13T21:29:28.106564Z;
  `belgium`: 185 tiles, builtAtUtc 2026-10-13T18:06:10.080248Z.
- M2: `artifactPresent=true` for all 3; Valhalla 3.6.3, each routing
  manifest has `routeValidation.status=recorded_pass`, `failedCount=0`.
  Austria and Belgium each have 1 recorded border route; Italy Nord-Est has
  1 border plus 1 interior route. `replayed=false`: these are **historical
  manifest records**, NOT independent fresh route probes or retained archive
  checksum verification. `borderReports.count=0` simply means no separately
  exported diagnostics report.
- M2 last build record: `regionId=italy-nord-est`,
  `outcome=succeeded`, `failureCategory=none`,
  `lastObservedStage=visual_retention`. No diagnostic warnings.
- Austria's successful routing manifest after the prior duplicate-ID build
  error is **strong device evidence** that processing got past the earlier
  Osmium failure. Do **not** claim its exact Osmium source-pruning log was
  independently inspected or that a cross-region graph chain was validated.
- Release gate: the rolling `roadpilot-graph-studio-linux` release's
  documented source was verified as M3 merge `4844bd2b` after successful
  post-merge GitHub run #136.
- **NEXT EXACT ACTION:** on the Legion run M3 against existing Austria
  working graph using `roadpilot-graph-studio --ai-verify-route austria
  47.582889 12.162319 47.609970 12.200709 motorcycle`; capture complete
  JSON and exit code. This is an explicitly requested single-region route
  test, not yet a border proof. If it fails, diagnose with output and
  reproduce against the existing `valhalla.json`, preserving graph/source
  caches. Follow with a deliberate negative test; do not automatically
  rebuild Austria. Desktop AI M3 verification remains **pending**.

## Latest verified merge — 2026-10-13: Graph Studio AI Control M3 PR #67

- PR https://github.com/kandyman991/RoadPilot-Offline-Data/pull/67 **merged**
  as `4844bd2b2a566002318c652c57e06fcb989f54a0`.
- Final PR head `31bdb63e2c15f01e88c39875ba3fad20e4a3562f` had **both**
  required checks green: Linux Graph Studio build including Rust AI-verifier
  contract tests, and offline-data repository validation.
- On-demand headless `--ai-verify-route REGION START_LAT START_LNG END_LAT END_LNG
  COSTING` and trusted Tauri `ai_verify_route` reuse one Rust verifier and
  Graph Studio's existing Valhalla request, coordinate validation and polyline
  geometry decoder. Checks actual decoded endpoints. Input/costing allowlists,
  20-second timeout, bounded stdout, process-group cancellation and sanitized
  structured outcomes. Handles pyvalhalla wrapper stdout.
- Explicit operation only, no remote listener/ChatGPT bridge or new automated
  jobs. Does not download, build, change/publish graph, or claim cross-region
  proof, retained-pack hash equivalence or full region validation.
- Post-merge Linux release workflow
  https://github.com/kandyman991/RoadPilot-Offline-Data/actions/runs/38466657609
  was in progress at handoff update. **Do not claim updated .deb is published**
  until the rolling release body refers to M3 commit `4844bd2b`.
- **NEXT EXACT ACTION:** Verify M3 post-merge rolling release assets correspond
  to `4844bd2b`. Install updated `.deb` on Legion once. Run M1/M2/M3
  commands on actual retained graphs, including positive and negative routes.
  Resume pending full Austria region rebuild with PBF cache intact to confirm
  PR #64 Osmium normalization and actual Valhalla border proof. This remains
  unverified on the physical Legion.
- An authorized ChatGPT-to-Legion bridge is still a **separate later milestone**;
  do not imply ordinary ChatGPT can currently invoke the local commands.

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
- **Historical next action (superseded by M3 entry above):** verify the rolling Linux release assets include M2's
  merge, update Graph Studio on Legion, run `--ai-capabilities`,
  `--ai-inspect`, `--ai-diagnose`; compare inventories/reports to real files.
  Repeat Austria build using the existing PBF cache to verify PR #64 source
  normalization and actual Valhalla crossing proof. Desktop test is **not yet done**.
- M3's explicit Valhalla verification is now merged in PR #67; see latest section above.


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
