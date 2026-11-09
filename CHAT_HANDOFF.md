# Chat Handoff — RoadPilot Offline Data / Graph Studio

## Latest PR #127 source-selection correction — 2026-11-09 (pair scoped, terminal first)

**Owner directed:** Correct source-edge selection before expanding native
continuation resolution; avoid exhaustive traversal. The November 8
region-wide `--resolve-cut` traversal and angle-based continuation heuristics
have now been **removed from executable source-stage Python**.

The source-only `--resolve-cut` command now REQUIRES both original compiled
neighbors' manifests/indexes/25-km buffer polygons and reciprocal boundary
fingerprints; SHA verifies both original graph archives. Restrict original A
boundary shape to its **actual outer 25-km cutoff inside B's own original
buffered footprint**, and inspect only original A tiles touching that shared
line plus immediate native tile neighbors. Native Valhalla 3.6.3 source
protocol v5 reads actual directed geometry, modes and local terminal flags.
Select native terminal candidates FIRST; for nonterminal paired-cut edges,
retain every original directed source GraphId/branch and inspect only their
native immediate node/hierarchy adjacency plus one-hop outgoing candidates.
Never follow beyond one hop, do not classify roads by heading, road names or
OSM IDs, never substitute a second B GPS point.

Real original archive pair tests PASS, Italy NE→Austria: **72** pair tiles,
1,520 exact shared-cut directed edges, 820 outward/ambiguous roots,
381 native terminal roots, 439 nonterminal roots retained unresolved,
564 one-hop local edges inspected and **505 unique local terminal GraphIds**.
Austria→Italy NE: **60** pair tiles, 776 exact shared-cut directed edges,
422 outward/ambiguous roots, 211 native terminal roots, 211 nonterminal
roots retained unresolved, 249 one-hop edges inspected, **269 unique
local terminal GraphIds**. One previously discrepant historic original
GraphId is preserved through two immediate original A alternatives.
Local release C++ build PASS; 404 Python tests PASS in Legion (latest
source-only unit and full suite). Pair outputs and SHA-256 evidence are in
`docs/F8_PR127_PAIRED_TERMINAL_FIRST_20261109.md` and retained under
`~/RoadPilotGraphStudio/diagnostics/f8-production/20261109/`.

**NOT_VERIFIED:** one true final physical-road A directed GraphId for each
physical road/direction, full source completeness, receiving B matching,
Android real journeys/parity. Catalog BLOCKED. PR #127 must remain DRAFT
and UNMERGED pending independent review, CI, and owner merge decision.
**Next:** prove the remaining genuine local source ambiguities without
expanding into general graph traversal; only then correlate B at same X.


## New PR #127 continuation milestone — native source-cut identification (2026-11-08)

**Current draft head:** prior verified PR #127 source geometry commit `9046a68`;
this local source-cut continuation increment adds the exact original 25-km
buffer boundary filter and branch-preserving native continuation inspection.
Region-independent C++ Valhalla 3.6.3 native reader and source Python stage
remain read-only against the exact graph/index/buffer SHA.

Real Legion test, original `2026.10.13-1` original graphs:
Italy Nord-Est — 178 selected tiles, 6,180 original directed cut edges,
2,920 outward / 2,909 inward / 351 ambiguous; 3,271 outward or ambiguous
seeds traced, 1,672 locally resolved, 1,663 distinct GraphIds,
1,599 incomplete. Austria — 227 selected tiles, 8,135 cut edges,
3,891 outward / 3,885 inward / 359 ambiguous; 4,250 traced,
2,072 locally resolved, 2,062 distinct GraphIds, 2,178 incomplete.
Nine Italy and ten Austria duplicate exact final IDs preserve upstream paths.
Local `GRAPH_LOCAL_TERMINAL` is not proof of global physical-road uniqueness.
One historical projected-source-cut candidate is not a strict raw GeoJSON
cut intersection; it remains present in the unresolved native-forward
alternatives of two genuine cut seeds, NOT suppressed.

The region-neutral `tools/extract_f8_region_final_edges.py --resolve-cut`
command now integrates the entire original cutoff→local native continuation
stage in one atomic, nonpublishing candidate output (not a historical ledger).
Both original Italy and Austria archive executions PASS, with independent
source-root accounting of every outward/ambiguous seed; integrated artifact
SHA-256s are `6874f4b721ec211216de5a7d5910ebbc10645f10b84a8677446bda859f2edc15`
and `1623ccf6e84f9b99962b93ab0a59900a330284d75385f531254a1bd1cf1fe886`.
Native compiled against Valhalla 3.6.3; **404 Python tests PASS**.

**Source physical-road/direction final completeness NOT_VERIFIED.** Native
junction, hierarchy, mode, ramp and cyclic ambiguity retained; do not claim
all originals are proven just from the locally resolved counts.
Receiving original B correlation NOT_STARTED, Android full journeys NOT_RUN,
publication BLOCKED, draft PR unmerged. No old architecture resurrected.
See `docs/F8_PR127_NATIVE_SOURCE_CUT_CONTINUATIONS_20261108.md` with local
SHA-bound evidence. **Next exact step:** resolve the 1,599/2,178 actual
source-cut ambiguity cases on their original native directed topology and
reconcile true last physical-road/direction edges. Only then match B at the
same source node GPS X and run RoadPilot Android consumption.

## Current working increment — draft PR #127 (2026-11-08)

PR: https://github.com/kandyman991/RoadPilot-Offline-Data/pull/127
Branch: `feature/f8-region-independent-final-edge-source-20261106`.
Building on the original region-independent, read-only 25-km compiled
boundary-tile source extractor. This increment reads the *actual directed
Valhalla edge shape* and emits the last nonidentical approach vertex
into the original source endpoint X, retains road use and directed
orientation, and requires `roadpilot.f8-native-source-2` binary protocol.
Python fails closed on missing/nonfinite/collapsed approaches and stores
an absent/degenerate geometry explicitly as null. No candidate is
removed on polygon distance, name, OSM way, access mode or apparent
forward continuation. This is native source geometry evidence, **not**
proof of a unique last physical road edge or a receiver match.

On the Legion with Valhalla 3.6.3, native release compilation PASSED;
398 Python tests PASSED. Real original Italy Nord-Est archive read-only
extraction v3 PASSED: 178 boundary tiles, 281,290 native terminal-mode
candidates, 2,854,067 local continuation-unresolved edges, 54.59 seconds,
774,272 KiB peak RSS. The v3 SHA-256 is
`d7cafa9ebd261dfc5ec27c284413075a6daadd08d716421f6cac6835d724d5d1`.
Read-only validation retained 177/177 historical Italy Nord-Est source
cut directed GraphIds, each with its native approach tangent; 23 out of
3,135,357 emitted directed edges had no nondegenerate approach tangent
and were retained with explicit null. Prior v2 candidate counts unchanged. Source
physical-road uniqueness INCOMPLETE; receiving-B correlation NOT_STARTED;
Android full journeys NOT_RUN; producer publication BLOCKED. No graph
packages, source geometry files, Android code, or installed GUI changed.

**NEXT EXACT STEP:** determine each actual last retained source edge per
physical road/travel direction from the native directed geometry/topology
(including ambiguous continuations, ramps and hierarchy levels) using only
the original boundary tiles and immediate native references; then identify
the matching B directed geometry at the same X, preserve genuine branches
and mode intersection, integrate the versioned catalog into the build, and
run real RoadPilot Android A→X→B journeys. Italy/Austria remain test data,
never code special cases. Do not merge this draft or publish an incomplete
source inventory as completed connections.

## LATEST completed merge — PR #122 reviewed source-only evidence (2026-11-04)

Owner-authorized PR #122 was independently audited as a separate technical
review pass, corrected, exact-head CI verified (architecture-contract,
validate and Linux all PASS), and **MERGED** into main as
`5e02be669681c1f33bb212da20c7dfe56f86e01a`.
Corrected PR code head: `71c9e75d0c34ac9c70300950f044a487e40a1509`;
390/390 local Legion tests passed. Findings and evidence:
`docs/F8_PR122_TECHNICAL_REVIEW_20261104.md` and
`docs/F8_SOURCE_CUT_WINDOW_COVERAGE_AUDIT.md`.

**Do NOT duplicate PR #121 or #122.** PRs #119/#120 are older diagnostic
branches and are NOT production merge dependencies. No original graph
archives, Android runtime, receiving-B graph or connectivity sidecar changed.
The 3,623 overlap-window native ID scan is NOT the whole original graph tile
census; 880 window-captured original source cut directed observations,
549 unresolved cut IDs, 34 native predecessor IDs missing from window scan,
and two bounded unresolved branches remain. One final original directed edge
per physical road/direction is NOT_VERIFIED. Receiving-B graph correlation
NOT_STARTED; production publication BLOCKED.

The merge commit contains `[skip ci]` to prevent an **unapproved rolling
Linux prerelease publication** triggered automatically by main pushes.
Post-merge the `roadpilot-graph-studio-linux` tag was verified unchanged
at `d8fc29bc5bfff59fbb0e297e05fa9111f31ae8bb`.
Release policy hazard is tracked in Graph Studio issue #123. Do not trigger
rolling Linux publication or graph/sidecar release without explicit approval.

**NEXT production milestone:** enumerate ALL original Valhalla GraphReader
tiles and directed roads for both immutable original region archives; preserve
all ramps, carriageways and mode-specific continuations, then prove a
source-side original physical-road/direction-to-ONE final retained directed
GraphId map across the 25-km overlap BEFORE any receiving graph correlation.
Issue #73/#82 Graph Studio and #512 RoadPilot remain open.


## Active production continuation — PR #122 source-cut window coverage (2026-11-04)

Dedicated PR #122 technical review corrected missing original Car/Motorcycle
TripLeg sequence validation, short Austrian original final edge fallback
reconciliation, source path proof counters and native JSON streaming limits.
Re-ran actual immutable graph evidence with byte-identical SHA result and
390/390 local tests PASS. Documented in
docs/F8_PR122_TECHNICAL_REVIEW_20261104.md. Merge only after corrected
exact-head GitHub CI; keep Graph Studio #73/#82 and RoadPilot #512 open.

PR #121 merged, main d8fc29b then ea0afc0 handoff refresh. PR #122
`feature/f8-physical-final-edge-id-20261104` is **DRAFT, unmerged**.
The previous session left two uncommitted original SOURCE window-cut-census
files and already-generated immutable v3 results. This recovery preserved
those files, added a strict standalone source-side reconciliation tool,
regressions and documented exact coverage gaps in
`docs/F8_SOURCE_CUT_WINDOW_COVERAGE_AUDIT.md`.

The 3,623 common-overlap native scan windows capture 658,345 unique original
directed IDs, but they do **not enumerate all tiles in either original graph**.
At the SHA-bound original 25-km source buffers 880 captured directed edges
intersect the source cut (Italy 593, Austria 287). 331 have a known
source direct-final/precursor link; 549 remain unresolved, including 159
outward. Importantly 34 additional SHA-verified beyond-cut predecessor IDs
were absent from window scans (Italy 18, Austria 16). They MUST NOT be
silently excluded. Two predecessor branches remain depth-bounded unresolved.
Source-only reconciliation report
`~/RoadPilotGraphStudio/diagnostics/f8-production/20261104/source-cut-coverage-reconciliation-v1.json`
SHA256 `652c3efe77ebf3d60ae3e7be24e7d454279ba5b91ac5c6225d97596db3e68ecf`.
Full 379-test Legion suite passes when the venv bin directory is on PATH.

**NEXT EXACT PRODUCTION GATE:** Independently enumerate all original
GraphReader tiles and directed road edges from both immutable original
archives; reconcile every source cut edge and original branch with exactly
one final retained original directed GraphId per physical road/direction.
Only after that is complete begin receiving-B matching. Do not revive OSM
samplers, same-name/way grouping, connector matrices, intermediate crossing
point grids, or first-success. No graph changes, sidecar or Android release.
Leave Graph Studio #73/#82 and Android #512 open. PR #122 requires review,
new exact-head CI and owner authorization before merge.

## After PR #121 merge — source-only last physical-road-edge census (2026-11-04)

Owner explicitly authorized and the GitHub exact-head architecture, Linux and
validate checks PASSED; **PR #121 MERGED into main** at
d8fc29bc5bfff59fbb0e297e05fa9111f31ae8bb.
The new source-only worktree from this actual merged main is
feature/f8-physical-final-edge-id-20261104; any ensuing PR must remain
DRAFT until separately authorized. NO receiving B graph work in this branch.

Source-only immutable original Italy Nord-Est/Austria evidence now reconciles
all 658,345 original native directed scan IDs, full exact mode-stranded IDs,
68,784 unique Car/Motorcycle union node-stop GraphIds, reachable hierarchy
branches and original source 25-km cut geometry. 251 final native directed
shapes intersect the cut; another 49 final directed shapes wholly beyond cut
are connected from native cut-crossing ORIGINAL predecessor chains. Together
300 distinct *SOURCE* original last-edge candidate IDs each pass original
Valhalla TripLeg final directed GraphId for BOTH Car and Motorcycle: 600/600
mode-edge pairs, including 3.4m last edge with exact original predecessor
TripLeg. At least 24,386 source candidates have hierarchy alternatives,
including cases with local route success; two beyond-cut branches hit the
bounded predecessor traversal depth. Do NOT claim global one-edge-per-real-
physical-road equivalence, border completeness, legal A→X→B or Android
JNI parity. No original .gph or production producer changed.
Detailed source SHA file inventory and open blockers:
docs/F8_SOURCE_FINAL_EDGE_IDENTIFICATION_PROGRESS.md.
Source-side verification != physical-road uniqueness: the next hard gate
is proving EVERY physical road/direction across the correct shared 25-km
overlap has exactly ONE final original directed edge without grouping
OSM way/name. Retain every unresolved candidate, ramps, branches and modes.
Receiving-graph correlation is NOT_STARTED, publication BLOCKED.

## Production direction reset: ONE final original directed edge per physical road/direction (2026-11-04)

The owner rejected expansion of full road reconstruction/journey diagnostics
into the F8 production architecture. New isolated branch from main,
feature/f8-one-final-edge-register-20261104, deliberately does NOT depend on
draft PR #119 or #120. It introduces a nonpublishing final-edge register
that uses the authoritative SHA-verified complete Italy/Austria full native
census and produces one record per original directed GraphId, joining
Car/Motorcycle access into one record without collapsing different physical
roads, ramps, carriageways, branches or separate directed GraphIds.

Real Legion result: 658,345 source directed edges still retained in original
source scans; 43,939 unique graph-local final directed edge candidates
(Italy 21,500; Austria 22,439), with mode-stranded nondeadends explicitly
unresolved (Italy Car/Motorcycle 12,216/12,252; Austria 12,550/12,587).
Immutable report under
~/RoadPilotGraphStudio/diagnostics/f8-production/20261104/one-final-directed-edge-candidate-register-v2.json;
sha256 ebbd3709820fa15f593ac529b45931af4b2924d5f93b73da375f5b00067a167f.
This is one candidate per native GraphId, NOT yet one proven physical
road/direction per edge: original road equivalence, mode-stranded cases,
actual receiving B road and legal Valhalla transfer still NOT_VERIFIED.
See docs/F8_ONE_FINAL_EDGE_PRODUCTION_RESET.md. Prior diagnostics PRs
#119/#120 remain drafts, not production dependencies. No graph/Android changes,
no merged PR, no published package.

## F8-native full directed overlap census / Android parity gate (2026-11-04)

- From verified merged main `d6f9514` (PR #117 merged), new **draft production-evidence branch** `feature/f8-full-native-terminal-census-20261104`. No PR merge or release authorized.
- Read-only actual Legion GraphReader census validated 3,623 geometrically complete 25-km overlap windows, all **658,345** directed source GraphIds with exact end-node/shortcut/opposite-access adjacency, source SHA-256, and both immutable graph archive hashes. Per-graph mode-local endpoint counts: Italy 21,500 Car / 21,468 Motorcycle; Austria 22,439 Car / 22,407 Motorcycle. Detailed real evidence `~/RoadPilotGraphStudio/diagnostics/f8-production/20261104/full-native-census-v3.json`, SHA-256 `2eddf560fe544724297794ece1e8b3e20fa54d2b10ab884b9b45ec38dd659a0b`. These are NOT globally unique physical-road terminals or claimed cross-region connections. No OSM/name/direction grouping, graph/Android modification or candidate suppression.
- Eight new deterministic regression gates confirm exact topology coverage, pin-before-execution, no dedup, incomplete-adjacency failure, no mode nonroad/shortcut suppression, and honest uncertainty. See `docs/F8_FULL_NATIVE_TERMINAL_CENSUS_ANDROID_PARITY_GATE.md`.
- Physical S25 device is NOT attached to the Legion: ADB has zero connected devices; therefore **real Android JNI parity NOT_RUN**. Existing Android 512-per-window cap and Kotlin `receiverRoadKey()` reduction remain known loss risks. Real physical-road lineage uniqueness, all original-route terminal proofs and Android F8 graph-edge parity are still NOT_VERIFIED. Publication BLOCKED.
- **Next exact action:** independently review the draft PR with exact-head CI; complete native physical-road lineage and original Valhalla terminal proof for ALL legitimate paths without grouping/pruning; connect/authorize physical Android device and capture installed same-graph JNI raw/Kotlin results in both regions/modes; reconcile missing IDs before proposing any publication or merge.



## P4-C — archive the legacy validators and schemas behind wrappers (2026-11-03)

- Owner-authorized (scope: the 11 legacy validators and their schemas; method: archive with tested wrappers). Branch `archive/legacy-validators-20261103`, a **draft PR stacked on the retirement-record PR; no merge, release or deletion of data authorized**.
- Validators moved unchanged to `tools/legacy_archive/connectivity/`; thin wrappers keep the original CLI paths. The ten legacy schemas moved byte-identically to `schemas/legacy_archive/connectivity/` (a JSON file cannot be wrapped, so that path change needs owner confirmation). The active pair-manifest schema, `validate_cross_region_connectivity.py` and all native F8 tools are untouched. Decision D-016; details in `docs/GRAPH_STUDIO_PHASE4C_ARCHIVE_LEGACY_VALIDATORS.md`.
- Evidence: 151 Python tests OK locally, including the existing byte-exact historical CLI gates and 9 new wrapper tests with a pre-archive baseline. Not exercised: installed AppImage/.deb, the `linux` packaging workflow result, the Legion GUI Legacy tab, external callers (UNKNOWN).
- **Next exact action:** owner reviews the stacked draft PR, confirms the schema path change, and runs the P4-D acceptance (exact-head CI, packaged-app smoke, Legion GUI check). Do not merge before that.


## Retired-architecture documentation cleanup (2026-11-03)

- Branch `docs/retire-osm-first-architecture-20261103` from main `48f5e79` (draft PR; **documentation only**; no merge, release or deletion authorized). It follows an independent review that stopped an F8 design which had drifted toward the retired runtime-connectivity and candidate-pair format.
- Changed: new `docs/RETIRED_ARCHITECTURE.md` (retired, retained read-only, and current native F8, plus a suggested clarifying note for Android #512); D-015 in `docs/ENGINEERING_DECISIONS.md`; a rejected-design entry in `docs/FAILED_APPROACHES.md`; retirement banners and corrected status rows in `ROADMAP.md`; `graph-studio/README.md` no longer lists the retired schemas as "current".
- Not changed: any code, schema, workflow, test, fixture, tool, validator or saved data. The 11 legacy validators, their schemas, the historical viewers and all evidence remain; Phase 4 cleanup (P4-B/C/D) is still separately gated. Android code and issue #512 are untouched.
- Older sections of this handoff and of the roadmap that mention `plan_multiregion_route.py`, connector matrices or the runtime-connectivity compiler describe the retired design only.
- Verification: see the PR (existing Python suite and the architecture-contract check). Native F8 parity, exhaustive discovery, device acceptance and publication remain NOT_VERIFIED / BLOCKED.
- **Next exact action:** owner reviews the draft PR and confirms D-015 wording, the axis-to-key and `frontierCorrelations` questions listed in the PR, and whether to post the suggested note on Android #512. After that, the read-only S1 measurements (Valhalla benchmark, fingerprint interoperability, Android candidate-reduction) still need explicit owner approval before any run. Open draft PR #102 also edits this file's top section; resolve the overlap when merging.


## P4-B6 — external/manual consumer evidence and backup scope (2026-11-02)

- Owner merged PR #100 into main (squash b8c8df10dad611cdcf7322eb7b26d5f42c944310). Starting P4-B6 as separate audit branch audit/graph-studio-p4b6-external-cli-evidence-20261102; draft evidence PR only, NO MERGE/RELEASE/DEPRECATION/CLEANUP authorized in this step.
- Fresh read-only Legion evidence: actual workspace 85 JSON checked, 4 oversized; original saved frontier inventory SHA 87a1cbf59546cd42644577185a2fd5c4f5155e536f05018ebcdf24ce9add261e still has roads=[]; three other historical worktrees each 137 JSON with zero legacy matches. 12 TAR files had 5,162 members but zero .json filename entries; 8 GZIP files had no JSON schema header in the first 4 KiB; four large JSON had no known v1 schema in first 8 KiB. Scans bounded; real populated operational data STILL NOT RECOVERED.
- New developer-only, nonexecuting privacy-minimal literal CLI caller scanner with explicit roots, symlink/non-regular exclusions, limits, aggregate counts only, and eight synthetic unit tests. Nine Legion script/config/service roots: 704 eligible files, 0 literal legacy CLI mentions, 0 scan truncation. Negative local search DOES NOT resolve manual/dynamic/off-machine callers, which remain UNKNOWN; historical CI (11 validators) and retired orchestrator (7) are confirmed former consumers.
- Updated docs/GRAPH_STUDIO_PHASE4B6_REAL_ARCHIVES_EXTERNAL_CONSUMERS.md with operator attestation template and G1–G4 blockers; added dedicated hosted CI test step. No changes to shipped tools, F8, Android or real user data. Issue #89 remains OPEN (UI-01..UI-13 were previously marked done).
- Next: independent security/data-integrity review, exact-head CI, explicit owner approval before merge. Later consented archive/backup recovery and manual consumer attestations are separate G1 tasks; no removal of 11 validators.


## P4-B5 — positive synthetic historical CI and consumer gate (2026-11-01)

- After owner-authorized #99 merge, P4-B5 is developed separately on audit/graph-studio-p4b5-legacy-positive-parity-20261101. No merge, validator removal, public deprecation or release permission is implied.
- Replayed 12/12 committed pre-#84 historical CI stages in disposable Legion directories from Git 9c95ca37ef763f3e3d123fb3c77f2c9b25ab0be3. 40 reconstructed synthetic artifacts across all 11 historical validator schemas were accepted with exact return code/stdout/stderr parity by historical, current and installed Debian scripts (scripts byte-identical). THIS IS NOT recovered production data or Android F8 graph-edge evidence.
- Saved ten reconstructed nonprivate positive v1 fixture snapshots, checksummed metadata and 10-family positive/negative read-only CLI regression gate in hosted repository CI. Existing frontier positive test retained. See docs/GRAPH_STUDIO_PHASE4B5_POSITIVE_CLI_AND_CONSUMER_EVIDENCE.md.
- Independent review correction on PR #100: fresh historical replay passed 12/12 stages but only 3/10 committed JSON snapshot structures were equal; seven have replay-variant elapsedMs/source-artifact SHA fields (no claim of deterministic bytes). New CI tests pin exact source CLI stdout and invalid-schema exit/stdout/stderr digests, without modifying validators. Host CI still cannot establish installed Debian/Android runtime parity.
- Fresh scoped tracked-source scan found no direct literal runtime/workflow caller. Historical CI (11 tools) and retired orchestrator (7) remain proven past consumers. Current external/manual/other-device users remain UNKNOWN, not zero; genuine positive saved production fixtures remain NOT_RECOVERED. All eleven CLIs stay supported. Issue #89 stays OPEN; native F8 unaffected.


## P4-B4 — replay historical populated frontier data and define CLI policy (2026-11-01)

- User requested further issue #89 Phase 4B compatibility work after merged PR #98 (merge `a973fa14c4dfcfec249c2447b87c6cb711c53a7d`). Work on **draft** `audit/graph-studio-p4b4-populated-replay-deprecation-20261101`; no removal, release or main merge permission yet.
- **Key progress:** Directly replayed Git-history **`661a23a^:.github/workflows/validate.yml`** steps `Smoke-test connectivity pair manifest` and `Smoke-test stable frontier road inventory` using old `tools/` archive in disposable `/tmp` on Legion with local osmium/shapely/pyproj. Both stages passed, reconstructed `roadpilot.frontier-road-inventory` v1 with **2 populated records** (OSM synthetic way 100 CROSSING + 102 FRONTIER_OVERLAP). Historic, current repo source and installed Debian `validate_frontier_road_inventory.py` all passed with **identical exit/stdout/stderr** and same script SHA `ec9aaf917eaae7cdd704c006a05efa47a632dd9522b76e453a7fd06e2ce6110c`. Crucially this is **reconstructed synthetic historical CI**, NOT recovered production data or graph-edge parity evidence (`NOMINAL_ONLY`, `NOT_VERIFIED`).
- Added **synthetic** structurally-identical canonical snapshot `tests/fixtures/historical-frontier-v1-populated-synthetic.json`, checked by second full historical replay for semantic identity; plus four regression tests `tests/test_historical_frontier_populated.py` covering positive two roads, invalid coordinate/kind rejection, and explicit synthetic/F8-not-proven guard. First temporary Legion branch checkpoint: **131/131 tests PASS**. No user artifacts changed.
- Current tracked source has no direct callers of the 11 old CLI scripts, but historical CI called all 11; retired `refresh_graph_connectivity.py` called seven; old .deb/AppImage still ship them. Manual/external/out-of-tree callers remain UNKNOWN; genuine saved nonempty production fixtures and ten other legacy v1 formats still NOT_VERIFIED.
- Proposed safe compatibility policy in `docs/GRAPH_STUDIO_PHASE4B4_POPULATED_REPLAY_COMPAT_POLICY.md`: retain all entry point names/flags/exit/output/v1 formats; G1 consumer and fixture evidence; G2 separately approved compatibility wrapper only if justified; G3 explicitly approved versioned notice window (suggest 2 releases minimum without forced stderr warnings); G4 destructive retirement only via separate reviewed/CI/owner-authorized PR. No changes to legacy tools/installed app/native F8/Android or user data. Issue #89 also tracks unfinished UI work and **stays open**.

## P4-B3 — populated legacy fixture and external consumer follow-up (2026-11-01)

- After owner-authorized PR #97 merge (`e6203676255c2842638523e9fcf4508cd2859145`), continue #89 in **draft evidence branch `audit/graphstudio-p4b3-history-fixture-inventory-20261101`**; no merge or deletion approval.
- New **devtools-only**, non-executing `devtools/audit_historical_fixture_inventory.py` collects hashes and top-level array counts for the 11 known v1 schemas from *explicitly selected* roots. No artifact bytes, filenames or personal paths are printed or committed. Regression tests distinguish `roads: []` from populated arrays and keep `work/*/build` in scan scope.
- Legion real workspace scan: **85** JSON files checked, **81** read within the 16 MiB limit and **4** skipped above limit; only historical `roadpilot.frontier-road-inventory` v1 with **0 roads** found. Three historical F8 worktree roots each scanned **137** JSON files, no matches. No genuine populated legacy v1 saved inputs recovered; ten remaining schema types have no positive real file.
- Legacy `.github/workflows/validate.yml` from pre-#84 Git revision **used all 11 validators** and old `refresh_graph_connectivity.py` invoked seven; these are confirmed historical callers. The old CI generated temporary fixture JSON but GitHub currently reports **0 retained repository Actions artifacts**; historical committed `tests/fixtures/` samples use separate `roadpilot.boundary-edge-inventory` and `roadpilot.transition-proof-results` schemas, not legacy validator formats.
- GitHub code search across owner's default-branch indexed repositories for exact two sample validator filenames returned only this repo's audit docs/tests, and current Rust dynamic R2 dispatcher uses fixed R2 scripts, not these 11 names. Remaining external/manual callers remain UNKNOWN; all 11 installed CLI files must be RETAIN.
- Independent review of P4-B3 discovered a potential hang on non-regular `.json` files such as FIFOs; the read-only inventory now checks regular-file type before reading, with a POSIX named-pipe regression. No app/runtime changes.
- Evidence saved at `docs/GRAPH_STUDIO_PHASE4B3_HISTORICAL_POPULATED_FIXTURES_CONSUMERS.md`. Next gate: independent architecture/security/data-integrity review and exact-head CI; keep PR draft, #89 open, no data/routing/Android change.

## Phase 4B2 — actual workspace and external consumer evidence (2026-11-01)

- User requested continued P4-B historical compatibility after PR #96 squash-merged into `main` as `9f2e6919c161fa433174a05b56699659969dcf7e`; issue #89 remains open.
- Found the *actual* Linux operational workspace `~/RoadPilotGraphStudio`, approximately **53 GiB**, distinct from XDG app-data folder. Read-only parsed **81** JSON files below 8 MiB, skipped **4** larger; one genuine `roadpilot.frontier-road-inventory` v1 artifact saved under `diagnostics/f8-italy-austria-validation/` (SHA-256 `87a1cbf59546cd42644577185a2fd5c4f5155e536f05018ebcdf24ce9add261e`). **Important: `roads: []` is empty; not nonempty-road or F8 parity proof.**
- Tested checksummed **temporary copies only** against legacy source and installed Debian validator: both exit 0, exact stdout/stderr parity, no extra files, original and copies unchanged. New developer-only opt-in verifier `devtools/verify_legacy_fixture_parity.py`, now with pinned source/installed SHA-256 and same-file comparison guard, plus 6 tests; Legion clean temp checkout **120/120** Python tests passed.
- Bounded external-callers scan: owner's Bash history, Git-tracked SmartRide-Next, accessible cron/systemd scripts, runners and F8/LegionBridge worktrees show **zero exact script-name matches**, but dynamic, historical and remote callers still UNKNOWN. The tools remain in installed Debian and AppImage packages.
- **Historical consumer discovery:** Git history at pre-#84 source `661a23a^`/`2b16d2b^` confirms direct `.github/workflows/validate.yml` invocations of **all 11** validators, plus 7 original validator call sites in retired `tools/refresh_graph_connectivity.py`. Existing callers are no longer literal references in current source, but historic usage is CONFIRMED; no positive real CI fixture bytes recovered. No scripts can be called never used.
- New P4-B2 report `docs/GRAPH_STUDIO_PHASE4B_REAL_FIXTURE_EXTERNAL_CONSUMER_EVIDENCE.md`, updated earlier baseline scope; PR created on branch `audit/graph-studio-p4b-real-fixtures-callers-20261101`. **No deletion, merge, release, F8 or installed-machine changes authorized**. Next: independent code/security review, corrections, exact-head CI, collect nonempty true legacy fixtures and operator consumer attestation. Keep all 11 validator CLIs RETAIN and issue #89 OPEN.

## Phase 4B — installed CLI dependency evidence (development, 2026-11-01)

- User authorized merger of docs-only Phase 4A PR #95 and development of **P4-B**; PR #95 squash-merged as `c555dc9e45e2642433affeb5bfb97355f10ce391`, with exact-head `architecture-contract` and `validate` green.
- Separate P4-B branch `audit/graph-studio-p4b-cli-compatibility-20261101` adds a development-only scanner under `devtools/`, regression tests, and `docs/GRAPH_STUDIO_PHASE4B_CLI_COMPATIBILITY.md` with installed-package evidence. After independent review, fixed explicit CLI-execution safeguards, Git HEAD/dirty-worktree provenance and privacy; moved scanner out of shipped `tools/` wildcard to preserve installed-app surface. Corrected Legion regression baseline: 114 Python tests passed with a synthetic invalid-schema integrity check. No real historical positive-schema fixture was located in bounded local searches.
- On Legion, **11/11** validators are present in the installed `.deb` and AppImage; Debian installed file copies byte-equal to functional checkout, AppImage SHA-256 pinned; eleven CLI `--help` invocations passed. No literal tracked callers found (NOT proof of no external use).
- **New investigation:** `validate_region_connector_refresh_plan.py` has no matching tracked `schemas/region-connector-refresh-plan.schema.json`; assess historical provenance before any intervention. Real historical fixtures, installed/external consumers and Android F8 parity still NOT_VERIFIED. All 11 validators **RETAIN**.
- **NEXT:** independent review, exact-head `architecture-contract`/`validate`/`linux` CI for P4-B development PR; inspect historical fixtures and external/operational callers in a separate read-only gate. No deletion/merge/release approval for P4-B, and keep #89 open.

## Phase 4 dependency audit — draft PR #95 (2026-11-01)

- **Draft [PR #95](https://github.com/kandyman991/RoadPilot-Offline-Data/pull/95)** branched from exact GitHub main `1d71db0` and adds `docs/GRAPH_STUDIO_PHASE4_DEPENDENCY_AUDIT.md`, a read-only dependency inventory / gated cleanup plan. **No application source or user data deleted; no merge or release authorized.**
- Examined Legion Graph Studio checkout and live main documentation, all tracked tool references, Tauri commands, frontend invokes, packaging and workflow hooks. Manual overrides, historical handoff records, connector matrix inspection, legacy OSM overlap visual diagnostics, F8 core, and current region/build/publish tools are actively referenced; **retain**.
- Eleven standalone historical schema validators have no detected in-repository callers, but are bundled in installed AppImage/.deb, so external CLI consumers and historical forensic value remain unknown. They are **candidates for negative-dependency verification**, not safe deletions. The retired OSM-based F8 discovery producers are already absent and must not be restored.
- Read-only test baseline on Legion: 110 Python unit tests **PASS** when invoking the existing Graph Studio app venv with its `bin` at the start of `PATH`. No UI acceptance or real graph/device test performed. Android F8 parity `NOT_VERIFIED`; production connectivity `BLOCKED`.
- **Independent review completed on PR #95:** F01 stale architecture-gap retirement wording corrected; F02 shipped CLI path compatibility now explicitly gated; F03 per-script initial evidence matrix added with external callers and historical fixtures still UNKNOWN; F04 isolated checksummed data/rollback tests required for any later deletion. None authorizes deletion, F8 production parity or publication.
- **CI policy follow-up:** Changing protected documentation `docs/ARCHITECTURE_GAPS.md` requires the complete `Architectural impact`, `F8 invariants checklist`, and `Verification / route evidence` blocks in the PR body even when implementation is unchanged. The initial post-review architecture-contract run failed that metadata gate (not the F8 tests); the PR description now supplies preserved-contract clauses, inspected Android F8 references, evidence limits, and six explicit invariant checks. A fresh PR commit is needed to validate the corrected event payload.
- **NEXT EXACT ACTION:** verify applicable exact-head documentation CI, then request owner authorization to merge the audit PR only. Afterwards collect external CLI and historical-schema evidence in P4-B before proposing *any* implementation/removal PR. Keep issue #89 open.

## Graph Studio Phase 3 — verified installed on Legion (2026-10-17)

- Official **main-branch rolling Linux release #39009406452 SUCCESS** on squash commit `437af035331e9b983fb4d7f6f34f7a28dabd9188` (not the subsequent `[skip ci]` documentation commit). Published and installed AppImage SHA-256 **`54bac0a760fb4de98c0a083b78c34147f8c8a4ae27606520cb88deeab84dcb75`** verified identical on Legion. Installed without sudo at `~/Applications/RoadPilot-Graph-Studio-Linux.AppImage`, preserved previous Phase 2 build as `~/Applications/RoadPilot-Graph-Studio-Linux.previous.AppImage`, validated existing menu `.desktop` launcher.
- No graph build, F8 discovery or Valhalla jobs active when Graph Studio was restarted. New AppImage started and live AT-SPI verified `Map layer preset` items Borders/All diagnostics, `Clear temporary map overlays`, grouped Graph Studio workflow including Border Inspector and Native F8 connectivity, existing Regions browser and Native F8 tabs. Browser-only earlier test covered functional Border tabs and Custom persistence; live full backend interaction remains a user-device acceptance test, **not claimed completed**.
- All original UI audit items **UI-01..UI-13 DONE**, GitHub issue **#89 remains OPEN to carry the separate Phase 4 dependency audit** before any legacy function/data deletion; native F8 Android parity NOT_VERIFIED, production cross-region connectivity publication BLOCKED.


## Graph Studio Phase 3 merged; installation pending (2026-10-17)

- **PR #92 merged** into `main` as `437af035331e9b983fb4d7f6f34f7a28dabd9188` (reviewed HEAD `3fc8f35b41838c233aa5c927dcef183b0b02c940`). GitHub `architecture-contract`, `validate`, `linux` all GREEN on reviewed commit. Legion repo main ff-only synced, automatic handoff ahead commit `50ebee2`.
- Full audited list `docs/GRAPH_STUDIO_UI_AUDIT.md` now marks UI-02/03/07/13 DONE (Phase 3), making **13 of 13 UI findings DONE** across Phases 1–3; GitHub issue #89 stays **OPEN for separate Phase 4 dependency audit of legacy code/data**, not because these UI screens remain unfixed. No existing archived handoff files, manual override records or F8 diagnostics deleted. Native F8 Android parity remains NOT_VERIFIED and production publication BLOCKED.
- Phase 3 official main-branch release workflow **39009406452** initiated from exact merge SHA. Leave Legion AppImage unchanged until official artifact passes release CI and SHA-256 verification; install using `~/Applications/RoadPilot-Graph-Studio-Linux.AppImage` and retain previous binary for rollback. Live app interaction needs verification after install.


## Graph Studio Phase 3 — Border inspector and map overlay UX (2026-10-17)

- User explicitly requested Phase 3. Created `feat/graph-studio-phase3-inspection-overlays` from clean current GitHub main `f0632d3`. Scope: `docs/GRAPH_STUDIO_UI_AUDIT.md` UI-02/03/07/13; no routing/Valhalla/native F8 backend, Android, immutable graphs or historical artifacts changed.
- Border Inspector separates **Manual validation / Saved evidence / Legacy diagnostics** with keyboard accessible/persisted tabs; graph pair selector shared. Old OSM way overlap and connector matrix in legacy tab, conspicuous warning **NOT native F8 proof**, never hard filtering/pre-Valhalla rejection; no automatic heavy legacy road-diff when manual tab active. Existing saved overrides, read-only handoff inventory, export diagnostics and manual snap/save workflow remain intact, exact original UI IDs and Tauri handlers.
- Map toolbar presets **Map / Routing / Borders / All diagnostics**, plus Custom for individual checkbox modifications and persisted booleans; detailed manual layer switches remain under Visual. `Clear` removes temporary diagnostic map *renderings* without deleting POI query results, retained versions, saved overrides, editor pins or graph files; async comparison callbacks guarded to prevent unexpected overlay resurrection. Navigation selection not reset. Not a delete-content operation.
- Compiled frontend Chromium at 1920/1200/960/650px passes border-tab keyboard/persistence, all original controls present, map preset changes + custom persistence, Clear overlays, no document overflow or JS errors; TypeScript/Vite build passed. CI/publish/Legion installation pending. The isolated browser cannot validate real Tauri route/graph database operations. Native F8 Android parity NOT_VERIFIED and runtime publication BLOCKED.
- Next: run local complete Python/contract tests; submit PR and review exact-head CI; merge only after green; install official checksum-verified Linux AppImage, retain rollback binary, verify live UI and update GitHub issue #89 + handoff. Phase 4 code/data deletion requires separate dependency audit (do not confuse moved historical UX with deletion).
- PR #92 created; first architecture CI run failed only because the initial PR body had a non-exact last invariant checklist line. The PR body has been corrected to the exact required wording and the **local architecture PR policy passes**. A new commit is required to get a fresh GitHub `pull_request` event (the gate reads the event body, not the live PR description). Previous Linux/validation runs superseded by the corrected metadata are cancelled; new-HEAD checks must all be green before merge.



## Graph Studio Phase 2 Legion installation verified (2026-10-16)

- Official rolling Linux release workflow **38966295556** on merge `6606d0f33fb4d885039fe9b5ba74e92e618e1013` **SUCCESS**. Published/dowloaded AppImage SHA-256 `30a37a198b476b1b845ed7111eafcacb1380f59a91c02265233255900e8e85ec` match. Installed at `~/Applications/RoadPilot-Graph-Studio-Linux.AppImage` without admin authentication; previous AppImage retained at `~/Applications/RoadPilot-Graph-Studio-Linux.previous.AppImage`. Desktop launcher Exec/Comment validated. No active graph build/F8 tasks when restarting GUI; new AppImage launched and live AT-SPI reports header `Show toolchain details`, `Graph Studio workflow` combo, `Open toolchain diagnostics`, Regions and Native F8 controls. Live workflow comparison backend not yet human-device-tested.
- PR #91 is MERGED, `docs/GRAPH_STUDIO_UI_AUDIT.md` UI-06/09/10/11 DONE; issue #89 remains OPEN for UI-02/03/07/13 and Phase 4 dependency analysis. Continue next milestone without reintroducing removed OSM seam matching, false Android parity proof, automatic first-time F8 route rescans, or dangerous deletion of historical artifacts.


## Graph Studio Phase 2 merged (2026-10-16)

- **PR #91 MERGED** to `main` at `6606d0f33fb4d885039fe9b5ba74e92e618e1013`; reviewed head `bfb6da8962a3b287464a54d2c8ec92323b401a65` passed GitHub `architecture-contract`, `validate` and `linux` checks (all GREEN), plus local 106 Python tests, TypeScript/Vite and four-width Chromium UI tests. Remote Legion repo synchronized to main.
- Phase 2 UI-06, UI-09, UI-10, UI-11 now **DONE** in `docs/GRAPH_STUDIO_UI_AUDIT.md` and tracked by GitHub issue #89, which remains open. Tool grouping six categories, one persisted Routing/Visual/Search comparison interface (retained backends/handlers), contextual Toolchain from status and Region Editor via region tree; safe migration for persisted old contextual menu selections.
- Main rolling AppImage release workflow **#38966295556** triggered from exact merge commit; until the release passes and SHA-256 verified, installed Legion AppImage still remains Phase 1. Once available, checksum verify, retain previous AppImage rollback and launch; do not call new version installed before actual upgrade.
- NEXT milestone Phase 3: simplify Border inspector, clearly move legacy crossing surfaces to Advanced/historical views (not delete), add sensible map-layer presets and overlay lifecycle controls (UI-02, UI-03, UI-07, UI-13). Phase 4 dependency-verified deletions only. No Android/Valhalla graph/F8 changed. Android F8 parity NOT_VERIFIED and production connectivity BLOCKED.


## Graph Studio Phase 2 — grouped workflows and unified comparisons (2026-10-16)

- User requested Phase 2 directly. From current main `98d5701`, branch `feat/graph-studio-phase2-workflow-navigation`: grouped primary tool dropdown into Build / Inspect / Test / Data / Publish / Advanced (9 destination options); Region Editor and Toolchain unchanged internally but removed from top-level menu, opened contextually from left New/Edit region tree and header toolchain readiness badge / visible compact Tools status action. Back button returns to last active normal workflow; persisted tool IDs `region`/`toolchain` now migrate safely to Build on startup.
- Existing routing graph boundary/size/tiles comparison, visual PMTiles road comparison, and search SQLite comparison controls are **moved without changing IDs or backend handlers** to one `Compare builds` workflow with `Routing / Visual / Search` accessible, keyboard-switchable, persisted tabs. All original comparison evidence and map overlays remain available; no source data deleted, F8 and route planners unchanged.
- Desktop compiled TypeScript/Vite build passed. Headless Chromium at 1920/1200/960/650 verified all nine tool entries, six grouped categories, comparison tabs/keyboard and persistence, preserved comparison controls, Toolchain contextual return, and zero document overflow. Python suite and CI/review pending.
- Canonical list `docs/GRAPH_STUDIO_UI_AUDIT.md` and GitHub issue **#89** tracked. UI-06,09,10,11 locally implemented / CI pending. Phase 3 UI-02,03,07,13 and subsequent Phase 4 cleanup still OPEN. No graph, Rust, routing, F8 or Android changes; F8 JNI parity NOT_VERIFIED, runtime publication BLOCKED.
- Next exact: Python/UI suite, architecture PR gate, CI + review, merge after green; install official checksum-verified Legion AppImage after merge, only if user authorization from ongoing workflow. Never claim installed before checking.


## Graph Studio Phase 1 — merged PR #90 and issue register continuity (2026-10-16)

- Merged **PR #90** from `feat/graph-studio-responsive-foundation` at squash commit `95a95c5dd342edcbe3b10848cec3e6f185b9897d`, confirmed architecture-contract, Linux, validate all GREEN on reviewed HEAD `c771d8b64f8dfc4e1571f11b7a46933130f9c168`. Main checkout pulled.
- All **13 UI audit findings permanently preserved** in `docs/GRAPH_STUDIO_UI_AUDIT.md` and GitHub **issue #89**. UI-01, 04, 05, 08, 12 **DONE** (adaptive compact panes, saved sizes, log collapse, Build/Route eligibility and route label). UI-02, 03, 06, 07, 09, 10, 11, 13 **OPEN**, issue #89 stays open. Do not delete legacy tools/data until dependencies proven safe.
- Real front-end smoke: nine viewport sizes 650..1920px, compact picker Tools → Map → Tools, selected-pane persistence, no viewport clipping; local 102 Python tests plus TypeScript/Vite pass. F8 native Android parity still NOT_VERIFIED and runtime publication BLOCKED.
- Official main Linux release run **38961974120** for exact commit `95a95c5dd342edcbe3b10848cec3e6f185b9897d` **SUCCESS**. Published rolling AppImage SHA-256 `bbfa20c16e3ea4edb36bd1a99ea6e9a3d49ac895dc542bc58f667022c753d466` verified against actual downloaded bytes. **Installed on Legion** at `~/Applications/RoadPilot-Graph-Studio-Linux.AppImage` (non-admin AppImage), backup previous binary at `~/Applications/RoadPilot-Graph-Studio-Linux.previous.AppImage`, desktop launcher Comment/Exec corrected, `desktop-file-validate` pass. Old AppImage process terminated after confirming no active graph/F8 work; new AppImage launched. Live accessibility inspection verified RoadPilot Graph Studio window, 6 region browser, Tool picker, native F8 tab selection. Broader physical GUI interaction remains untested on device; compiled frontend browser regressions pass. Phase 2: grouped tool navigation and comparison/toolchain consolidation.


## Graph Studio UI audit and Phase 1 responsive foundation (2026-10-16)

- User approved **keeping the three-pane desktop UI** but repairing narrow-window clipping and hiding, then reorganizing tools later. Full audited list permanently saved in **`docs/GRAPH_STUDIO_UI_AUDIT.md`** (UI-01 through UI-13), mirrored in **GitHub issue #89**. Never discard/deprioritize unsolved items silently; update this document and issue after every PR.
- Working branch **`feat/graph-studio-responsive-foundation`** from `main` `99da372` after PR #88. Phase 1 includes compact Regions/Map/Tools pane switcher for <=1100px (no hidden inaccessible tools), saved compact selection, desktop stored splitter clamping, collapsed-by-default but expandable/resizable console, disabled Build until valid configured/queued region/toolchain/version, and Route until selected built graph plus valid coordinates, and legible route expansion checkbox.
- Local compiled frontend browser test at 650/800/960/1024/1100/1150/1200/1440/1920px: no horizontal document overflow; all Regions/Map/Tools reachable, shared F8 inspector accessible; console toggles without losing status/log; oversized stored panes clamped without tool loss; narrow↔wide transitions preserve selection. TypeScript/Vite build passes. Python regression suite and GitHub PR/CI/technical review still pending at branch creation. No backend routing/native F8/Valhalla/Android/R2 changes; F8 parity NOT_VERIFIED, runtime publication BLOCKED.
- UI review verified Rust route archive selection uses the latest builtAtUtc; changed displayed route version from the oldest `.at(-1)` to latest-first `.find`, preventing falsely labelled graph versions.
- Initial Build button is now explicitly disabled in HTML until the first toolchain/selection verification, preventing an unsafe enabled-looking startup state.
- Compact workflow enhancement added during PR review: Route, Border and Region Editor map-point buttons automatically switch from Tools → Map and return to Tools when the point is picked, preserving all form values. No route proof/backend change.
- **Next exact action:** run full local suite, submit Phase 1 PR with architecture contract, await green CI, technical review and merge. Update official Legion AppImage only after published release checksum verification. Then Phase 2 work from the remaining register items.


## Graph Studio native F8 split into Discovery / Journey Validation tabs (2026-10-16)

- Branch `feat/graph-studio-f8-discovery-validation-tabs` from current `main` (`017f239`) refactors ONLY the F8 inspector frontend; backend engine, valhalla proof, graph data and Android unchanged. User explicitly requested splitting the lengthy F8 panel.
- Pair selection (graph A/B), job status and cancel button shared above two ARIA tabs; Discovery contains inspect/scan/proposal inventory; Journey Validation contains readiness, direction/mode/endpoints, bounded Valhalla proof and sampled handoffs. F8 tab preference persisted in localStorage; keyboard arrows/Home/End implemented. Input state preserved across switches; stale sampled reports cleared immediately when graph pair changes.
- Local frontend `npm run build` passed; headless Chromium tested 1920×1080 and 1200×740 for tab switching, keyboard, persistence, no horizontal overflow, readiness guidance and visible shared status; separate static GUI safety regressions added. No graph rescan, no Android ingestion, production publication still BLOCKED / F8 parity NOT_VERIFIED.
- Next action: full Python suite, architecture CI, Linux packaging, technical review. Merge/update Legion AppImage only once head checks green and update is explicitly authorized. Existing installed Graph Studio still at main `703ef229` until new build installed.


## PR #87 native F8 Graph Studio GUI integration — MERGED + Legion installed (2026-10-16)

- User approved immediate integration of native F8 into Graph Studio's **Tool → Native F8 connectivity** pane. PR **#87** merged to `main` at squash **`703ef2297e263bf2545be148edd51502f8a582ce`**. Latest PR head `95e3d1d45b137fbd9438b936bcf99ab1c4ba8794`: `architecture-contract`, `linux` (Tauri/deb/AppImage) and `validate` CI all **PASS**. Rolling main release run **38947826585** completed successfully. Source checkout main was refreshed.
- The official main-release AppImage was installed under `~/Applications/RoadPilot-Graph-Studio-Linux.AppImage` (SHA-256 **`24de6aed049b58276ee5f484208a096613da17ff5ed61b63b5a601ae4c528473`**, matched GitHub release), executable, and **smoke-launched successfully**. User application-menu desktop entry `~/.local/share/applications/RoadPilot Graph Studio.desktop` and `~/.local/bin/roadpilot-graph-studio` wrapper point to that exact AppImage; desktop-file validation PASS. The system `.deb` install requested Polkit GUI authentication and was cancelled rather than obtaining a password; old system-level package remains 0.1.0 but the user's PATH/menu now selects the new AppImage. Both packages retain version 0.1.0 until automatic version bumping is implemented, so identify by merge SHA/release digest.
- Real engine proof during PR: existing immutable Italy Nord-Est ↔ Austria Valhalla 3.6.3 2026.10.13-1 scan reused without rebuilding, 334,973 / 323,372 graph-native receiver-directed GPS proposals, **3/6** sampled Motorcycle A→B journey proofs, **334,967 UNPROBED**, strong complete-source/unverified-parity gates. Local **95** Python tests and `tsc`/Vite frontend pass. Working F8 CLI diagnostic output under `~/RoadPilotGraphStudio/f8-native/italy-nord-est__austria/` persists. Source-side native scan SHA only summary-declared; actual JNI reference parity remains NOT_VERIFIED.
- New GUI supports opt-in graph-pair selection, native full retained source GPS discovery, optional fresh C++ GraphReader overlap scan if source inventory missing, per-stage progress/cancel, bounded Valhalla mode/direction journey proof and clickable sample handoffs. Separate graphs untouched; on-device Android F8 fallback unchanged. Runtime sidecar publication **BLOCKED**; no full crossing alternative/FASTEST/SHORTEST/multi-hop coverage claim.
- **Next exact action:** open the newly installed Graph Studio UI and run a firsthand GUI acceptance walkthrough with Italy Nord-Est/Austria. Then proceed to scalable complete offline F8 frontier proof scheduling, exact JNI scanner parity and Android sidecar ingestion/rollback. Project issue #82 stays OPEN and Android issue #512 stays OPEN until factual proof gates close. Do not reintroduce the retired OSM discovery pipeline.


## Graph Studio native F8 tool panel integration (2026-10-16, in review)

- New working branch `feat/graph-studio-native-f8-ui` from merged main `3cae2a2` (`#86` merge commit `9c8c6ab`). User specifically requested a **usable installed GUI tool** for the native F8 workflow, not more standalone scripts.
- New **Native F8 connectivity** tool inside the existing resizable Graph Studio right-side panel. Select two immutable retained graph builds; inspect exact graph/boundary identities; explicitly start complete retained-source native GPS proposal generation (or fresh GraphReader scan if the compatible native C++ exporter and buffered polygons are present); see real progress and cancel; select direction/mode/route and perform bounded Valhalla A→X→B validations. View sample-valid handoffs on the map and review best FASTER/SHORTER *of probed only*.
- Rust Tauri command/event bridge shares a single testable Python CLI engine `tools/graph_studio_f8_workspace.py`, isolates native subprocess process groups for cancellation, prevents concurrent region builds/F8 jobs, validates selected builds from managed workspace, never publishes Android runtime sidecars. Each pair catalog is bound to exact graph/boundary fingerprints; reuse only matches; incomplete/stale evidence fails closed.
- Real Legion test used already retained native scans for exact Italy Nord-Est/Austria `2026.10.13-1` pair and generated 334,973 / 323,372 directed receiver GPS seeds including unmatched alternatives with no graph rebuild or native rescan. Bounded Motorcycle A→B journey proof **3/6 validated**, **334,967 unprobed**. Original `.gph` packages untouched. Tests and TypeScript build passed locally; CI/review/merge/desktop-installed test NOT VERIFIED until done.
- New docs: `docs/GRAPH_STUDIO_F8_TOOL_PANEL.md`. All outputs under local `~/RoadPilotGraphStudio/f8-native` and diagnostic ONLY. Actual Android F8 JNI parity, exhaustive Valhalla proofs, multiple region chain optimality, verified Android ingestion still NOT_VERIFIED/NOT_RUN; production publication remains BLOCKED. Never describe this GUI as completed full F8 precomputation.
- **Next exact:** run Rust/Tauri + Python architecture CI on PR, technical review and correct findings, merge only after green; update Legion official `.deb` from rolling main release when authorized; inspect actual installed UI with user. Continue F8 parity and scalable offline proof scheduling after this integration.


## PR #86 technical review findings (2026-10-16)

- **Reviewed native F8 crossing producer and bounded journey proof** at branch
  `feat/native-f8-crossing-discovery`, pre-review `b8fef6e`. Two substantive
  fail-closed fixes applied: `probe_native_f8_journey.py` now checks the
  *actual retained* graph archive identity (region, version, graph SHA and
  counterpart primary Geofabrik IDs) against the pair manifest; direct
  `discover_native_f8_crossings.generate` calls also validate full source
  scans and aligned window catalogs, not only the CLI path. Proof output now
  uses exclusive atomic file creation, never silently replaces another report.
- Added regression tests including stale archive hash/version, unmatched
  source identities and direct-call invalid/incomplete scans. **88** local
  Python tests PASSED. Corrected real Italy→Austria Motorcycle route proof
  reproduced **3/6** validations with **334,967** unprobed native seeds,
  all publication/parity gates remain BLOCKED / NOT_VERIFIED.
- Next step is CI and review on amended PR #86. Merge only if latest checks
  green and no unaddressed architectural blockers; do not call full F8
  native discovery complete. Subsequent work: complete offline crossing
  scheduling, native Android parity, multi-hop and ingestion.


## Native F8 directed GPS discovery and journey-scoped proof — in PR (2026-10-16)

- Verified GitHub `main` `d754e838ea45f269fb6da5ecf9e213324d9a9d54` contains merged PR #85 (squash `b7fdf3c`); no open PR existed before this milestone. New working branch: `feat/native-f8-crossing-discovery`.
- Graph-native directed receiver-edge proposal enumeration in `tools/discover_native_f8_crossings.py`. Every scanned edge in both region directions becomes a retained GPS seed; physical peer matching is strictly diagnostic, never a gate. Deterministic gzip ledgers, hash/graph-bound manifest, no first crossing lock-in, no old OSM anchor pipeline.
- Bounded route proof in `tools/probe_native_f8_journey.py`: RoadPilot F8 A→GPS normalization via real Valhalla leg, B→destination with normal Valhalla, verify endpoint and receiver directed GraphId trace. Probe multiple candidates for FASTER and SHORTER using sum of both full-journey legs, retaining INCOMPLETE/UNPROBEN evidence.
- Same retained real Italy-Nord-Est/Austria Valhalla 3.6.3/2026.10.13-1 native captures: **334,973 A→B + 323,372 B→A proposals**, including 18,410/6,809 without exact physical peer. Real Tarvisio motorcycle + auto both directions each had **3 journey-valid proofs among 6 sampled seeds**; other >300k each direction UNPROBED. Local evidence only, no Android publication or graph rebuild. Native JNI parity/global frontier exhaustiveness still NOT_VERIFIED.
- **Draft PR #86** (`eaa79fb`, review hardening pending commit) has architecture-contract PASS, with Linux/repository checks pending at first creation; local suite now **86 PASS**. The proof consumer additionally fails closed if hashed GPS stream counts or directions contradict its manifest, even if the file hash was updated. No merge or Android publication in this milestone.
- Next: run CI/review on this PR; precompute all useful frontiers with scalable graph-native reachability/candidate scheduling and actual Android JNI scanner parity on identical graph versions; prove all modes/directions and complete journey ranking/multi-hop before enabling build integration. Never treat this bounded sample as production-ready.


## PR #85 technical review hardening (2026-10-16)

- Review on branch `feat/native-f8-directed-pair-evidence`: discovered false
  pair-scan completeness risk (window catalogs not compared) and incomplete
  access/native field validation. Fixed both; added strict geographic window
  indexing/uniqueness/bounds, matching catalogs, typed access and edge
  attributes, unambiguous region IDs and explicitly *unverified* shared-buffer
  coverage. Prevent invalid NaN diagnostic JSON.
- The complete local Python test suite now passes **72 tests**, including nine
  native directed-peer regressions. Real unchanged Italy Nord-Est/Austria scans
  rerun into `native-directed-physical-peers-v2-review`: 316,563 physical
  peers and 6,809/18,410 unmatched remain; source windows align; all three
  generated file hashes independently verified. These remain UNPROVEN,
  Android F8 parity NOT_VERIFIED and publication BLOCKED.
- Draft PR #85 needs updated CI status and independent GitHub reviewer approval
  if repository branch rules require it. Technical ChatGPT review is not an
  independent GitHub approval; no merge authorized by this request.

## PR #84 merged; native physical F8 peer foundation initiated (2026-10-16)

- PR #84 (`refactor/retire-pre-f8-connectivity`) merged, squash commit
  `2b16d2b51acdf19940b4c91c7286f335e2478078`; all three checks passed.
  Subsequent auto handoff commit on main `e968fd5` was verified before work.
- New branch `feat/native-f8-directed-pair-evidence` introduces
  `build_native_f8_pair_evidence.py` and repeatable tests: stage raw directed
  physical peer ledger and explicit unpaired-edge evidence from immutable
  previously scanned native graphs. No new OSM sampling, no GraphId equivalence,
  no hard road/heading/mode filter, no restored old pipeline.
- Real Legion 3.6.3 Italy Nord-Est/Austria retained inventory processed without
  graph rebuilding: **316,563** exact physical directed peers, **6,809 / 18,410**
  unmatched edges, faithfully reproducing October 14 independent comparison.
  Files under `~/RoadPilotGraphStudio/diagnostics/f8-italy-austria-validation/native-directed-physical-peers-v1`.
- All peers remain **UNPROVEN**. This is not a true cross-frontier route-proof
  candidate set. Historical scan sources have summary-declared identity only.
  Android F8 parity, Valhalla directions/modes, full-route optimality, Android
  ingestion and distribution remain NOT_VERIFIED / NOT_RUN / BLOCKED.
- **NEXT EXACT ACTION:** close this foundation PR after CI; construct graph-native
  F8 handoff candidate/frontier relevance using full scan evidence with no
  unproven eliminations, add route probes for both directions and vehicle modes,
  compare to true Android F8 scanner output on identical graph packages, and
  then tackle Germany/multi-hop with explicit completeness evidence.


## Latest working branch — strip old discovery before native F8 (2026-10-16)

- **User decision:** remove the obsolete Graph Studio OSM buffered-overlap
  frontier/correlation/proof/matrix/composer architecture before implementing
  native F8; preserve existing independent regional graphs, native scanner,
  single-region Valhalla routing, old diagnostics and Android F8 fallback.
- **Branch:** `refactor/retire-pre-f8-connectivity` from GitHub `main`
  `9c95ca37ef763f3e3d123fb3c77f2c9b25ab0be3` (PR/CI pending at this
  writing). Separate draft PR #83 addresses a bug in a now-retired OSM module;
  do not merge that module back or treat it as a prerequisite.
- Desktop Rust `run_build_queue` no longer invokes the obsolete connectivity
  producer, and the manual refresh and legacy multi-region route endpoints/UI
  are removed. Retired Python generation and route-planner modules are deleted,
  along with their obsolete CI smoke sections. Historical artifacts remain
  read-only, not F8 parity evidence.
- Native `capture_native_f8_graph_windows.py` is decoupled from the removed
  OSM correlation stage: `--pair-manifest` accepts an identity-only UNPROVEN
  graph-pair manifest; `tools/native_f8_inputs.py` holds shared retained graph
  hash/boundary checks and polygon geometry readers. Real retained graphs and
  local October 14 scanner evidence were not touched.
- **Local verification on Legion:** frontend `npm run build` passed; nine
  native capture tests, nine architecture/retirement tests, and sixteen F8
  parity-audit synthetic regressions passed. Rust/Tauri compile, complete CI,
  new CLI real-graph rescan, Android parity/device: NOT_RUN.
- **NEXT EXACT ACTION:** get this removal PR green and review source/tree for
  remaining active legacy production calls; then implement native directed
  frontier handoff candidate discovery + both direction/mode Valhalla proof
  on the same immutable Italy Nord-Est/Austria graph hashes. Compare actual
  Android F8 reference and then Austria/Germany/multi-hop; keep parity
  NOT_VERIFIED and do not publish production crossings until verified.


## F8 discovery-foundation correction — PR #75 merged, parity pending (2026-10-14)

- **Merged:** PR #75 https://github.com/kandyman991/RoadPilot-Offline-Data/pull/75 at squash commit `b0d60d07c89b62291be75f893026c90b552efe23`; final head `4f6b5927ada4ac1a3aea9d74844c58678b7aa083` passed all 3 checks (`architecture-contract`, `validate`, `linux`). This confirms CI and architectural disclosure, NOT native F8 graph-edge parity.
- Branch `graph-studio-f8-overlap-discovery`; exact user requirement and
  acceptance are in https://github.com/kandyman991/RoadPilot-Offline-Data/issues/73.
  Do not treat F8 as failed: it gave usable routes but first scan was too
  expensive and one cached crossing could hide better alternatives.
- Previous frontier discovery only accepted OSM ways crossing both nominal
  source polygons. Added a separate buffer-overlap source scan across **both
  graph builders' retained PBFs and buffer.geojson polygons** while retaining
  original crossings; no name/ref dedupe, no first-success shortcut. Every
  physical anchor still goes through independent graph-local correlation,
  full candidate combinations and mode/direction Valhalla proof.
- `discovery.scope`, `sourceExhausted` and `f8GraphEdgeParity=NOT_VERIFIED`
  are propagated to published runtime; old nominal-only products must be
  regenerated before reuse; an incomplete scan cannot publish.
- Tests: `tests/test_f8_overlap_discovery.py` covers same-name alternative
  roads, extra road only in Graph B, same-way clipped differently in A/B,
  long way samples and explicit no-parity assertion; existing automation
  tests updated for both buffered inputs and discovery identity.
- **IMPORTANT:** This is an OSM-seeded F8-inspired candidate-enumeration
  correction, NOT yet proven identical to the phone's native
  `GraphEndpointNative.scanBoundaryRoadEdges` (F8's exact source). Need
  Legion comparison of actual graph-edge candidate sets and a completion
  proof before changing parity to VERIFIED or treating metadata as exhaustive.
  Also route planner currently caps chain attempts at 20 per origin/dest
  region pair; issue #73 covers that separate optimality requirement.
- **NEXT EXACT ACTION:** validate the newly merged Graph Studio overlap discovery on retained real Italy Nord-Est ↔ Austria graphs, compare every actual RoadPilot F8 directed graph-edge crossing against the precomputed list, retain other valid alternatives, and record any missing edges or unresolved cases. Graph Studio issue #73 remains OPEN; Android #512 remains OPEN. Do not call `sourceExhausted=true` proof of full native F8 parity, or claim the best route without whole-journey comparison.



## Architecture drift prevention safeguards — PR #76 merged (2026-10-14)

- User authorized the binding architecture contract, PR checklist and CI regression gates **before any further F8 discovery merge**.
- **PR #76 merged** https://github.com/kandyman991/RoadPilot-Offline-Data/pull/76 — squash `50aa8cc62af40c2ae10b627eeb43c46b4c7b45f3`. All three PR checks PASSED: `architecture-contract`, `validate`, `linux`. This is NOT real-world F8 graph-edge parity evidence.
- Canonical files: docs/ARCHITECTURE_CONTRACT.md and docs/ARCHITECTURE_GAPS.md; .github/pull_request_template.md; .github/CODEOWNERS; tools/check_architecture_contract.py; tests/test_f8_architecture_regressions.py; .github/workflows/architecture-contract.yml.
- Gate tests all directed correlation alternatives (no first crossing lock-in), faster/shorter choice, cached graph/boundary fingerprints, PR disclosure of the F8 reference, all six contract invariants, known gaps, and blocks unapproved change declarations. F8 graph-edge parity remains NOT_VERIFIED.
- **Hard merge enforcement still PENDING.** GitHub `GET /rulesets?includes_parents=true` returned `[]` (checked 2026-10-14); connected GitHub tools cannot manage branch protection (403). User/admin must set Settings → Rules → Rulesets → target `main` → require `architecture-contract` check and review from CODEOWNERS. Track https://github.com/kandyman991/RoadPilot-Offline-Data/issues/77. CODEOWNERS and CI alone cannot prevent a manual merge without this setting.
- Discovery PR #75 remains OPEN and unmerged. Its broader OSM buffer overlap candidate scan is not yet proven equivalent to the actual native F8 graph-edge scanner; Graph Studio issue #73 stays OPEN. Android sidecar consumption remains tracked in RoadPilot #512.
- **NEXT EXACT ACTION:** configure and verify the GitHub ruleset. Then synchronize PR #75 with `main` and its architecture PR checklist, compare real F8 graph-edge scanner coverage with Graph Studio results on exact Legion Italy/Austria graphs, and preserve any missing alternatives as incomplete, not as fully validated. Do not merge unproven F8 parity as a completed milestone.


## F8 correctness/completeness requirement — user's explicit correction (2026-10-14)

- **F8 worked.** Android problems were prohibitively expensive first discovery
  and incorrectly using one already-learned successful section/crossing as
  sufficient knowledge, suppressing further discovery of potentially better
  crossing points for different journeys. Do not confuse caching a successful
  handoff with enumerating all available, mode-specific directed alternatives.
- **Issue #73**: https://github.com/kandyman991/RoadPilot-Offline-Data/issues/73
  records the missing Graph Studio completeness requirement and acceptance tests.
- Confirmed code gap: `build_frontier_road_inventory.py` finds OSM ways
  physically intersecting both **nominal** polygons and their boundary;
  that is not proven equivalent to F8's graph frontier scanning over
  shared/overlapping graph coverage. `VALIDATED` means generated candidates
  were proven, NOT that every usable F8 handoff was discovered.
- `plan_multiregion_route.py` limits hierarchical chains to 20 each
  source/destination pairing, 64 unique detailed Valhalla legs and
  ~120-second budget; intermediate-only ranking before origin/destination
  legs can omit better routes, and a first complete same-graph result currently
  returns immediately. These diagnostic budgets do **not** prove exhaustive
  fastest/shortest choice. Do not report globally optimal route unqualified.
- Target: build-time exhaustive or explicitly incomplete graph-frontier
  discovery with Valhalla-proven directed alternatives, fingerprint-bound
  coverage report, no first-learned lock-in; route-time uses all relevant
  alternatives and whole-journey comparison with sound pruning/fallback.
  Preserve real-device Italy/Austria and 3-region verification gates.
- **Next priority:** resolve issue #73's full-frontier equivalence and
  no-premature-pruning correctness before treating PR #71/72 metadata as
  complete for production Android issue #512. Preserve working F8.


## Multi-region route planner — PR #72 merged (2026-10-14)

- **PR:** https://github.com/kandyman991/RoadPilot-Offline-Data/pull/72
  squash merged at `fd17237fce61aba560470af82514c5776142701d`.
  Final head `e3a35d90c112730b64e09925d69bbe783b51c217`
  passed both required checks: Linux build/tests and repository validation.
- New post-merge rolling Linux release:
  https://github.com/kandyman991/RoadPilot-Offline-Data/actions/runs/38532669497
  was still in progress at this check. The downloadable rolling Linux
  .deb/AppImage still identified PR #71 merge `debab59`, NOT PR #72.
  Do **not** claim installed Graph Studio contains multi-region mode until
  the published release notes identify `fd17237`.
- **NEXT EXACT ACTION:** check rolling release notes/asset timestamp,
  install new .deb on Legion only when release identifies `fd17237`;
  Build -> Refresh connections on the existing Italy Nord-Est and Austria
  graphs; inspect real validated runtime handoffs and regional connector
  inventories/matrices. Test Trento `46.064320,11.119191` ->
  Innsbruck `47.250124,11.395549` in Multi-region, Motorcycle/FASTER.
  Require actual directed edge matches, geometry for each distinct graph
  leg, verified destination arrival and no invented seam geometry. Preserve
  F8 as on-device fallback. Android integration still tracked at
  https://github.com/kandyman991/SmartRide-Next/issues/512.

## Multi-region route planner implementation details (2026-10-14)

- New `tools/plan_multiregion_route.py` reads current local graph coverages,
  matches retained artifact fingerprint to installed working tile extract,
  selects `VALIDATED` pair runtime metadata, current connector inventories
  and exact-bound matrices; invokes existing hierarchical chain composer.
- Executes detailed per-graph Valhalla route legs for multiple F8-derived
  candidate chains; validates both leg endpoints and the final destination
  within 150m after Valhalla. Ranks by actual summed full journey time/distance,
  not intermediate matrix score. GeoJSON MultiLineString preserves separate
  geometry across graph handoff gaps rather than drawing fake joins.
- Tauri new `plan_multi_region_route` command; Route Planner Single graph /
  Multi-region toggle; graph sequence, independent route legs/handoffs and
  arrival shown in GUI. Supports Motorcycle/Auto only, while single graph
  remains unchanged. No graph mutations, fixed portals or Android changes.
- New synthetic regression tests under `tests/test_graph_studio_multiregion_route.py`
  wired into repo validation; Linux CI builds frontend and backend.
- **Next:** Check PR #72 Linux rolling .deb release identity, install it,
  validate real Italy Nord-Est/Austria connectivity and Trento→Innsbruck
  Multi-region handoff + destination arrival on Legion. Do not claim
  Android integration complete until issue #512 is validated.

## Automatic F8-derived connectivity production — PR #71 merged (2026-10-14)

- **Merged:** [PR #71](https://github.com/kandyman991/RoadPilot-Offline-Data/pull/71), squash merge `debab59f2ee9e4f03f5613a2e1b4362ad921e1ba`. Latest PR head `21a73da2b1193a0ee85971aaf51dd2dc0f9f9370`; **both required checks passed** (`linux`, `validate`). Post-merge Linux release job [38517542690](https://github.com/kandyman991/RoadPilot-Offline-Data/actions/runs/38517542690) was **running** at this check; rolling release still referred to older PR #70 merge `9e590318`. Do not install the existing .deb as PR #71 until release body names `debab59`.
- **Branch** `graph-studio-automatic-connectivity-pipeline` integrates the
  existing independent cross-graph frontier inventory, correlation, candidate
  generation, Valhalla proof and runtime connectivity compiler, plus regional
  connector inventory and exact-edge matrix, into Graph Studio's **Build selected**
  queue. An explicit **Refresh connections** action processes existing local
  graphs without rebuilding or redownloading maps.
- New `tools/refresh_graph_connectivity.py` discovers mutually compatible
  adjacent retained graphs by exact boundary fingerprints; runs only pairs
  affected by a freshly built graph, or all current pairs on manual refresh;
  skips already current fingerprints; stages validated output outside public
  artifact directories; never overwrites validated runtime with unproven data;
  preserves existing packs on errors; skips matrices if any relevant pair is
  stale/missing and reuses exact current inventory/matrix hashes.
- Uses local `work/<region>/build/buffered.osm.pbf`, local
  `work/cache/<region>.poly`, and immutable retained
  `builds/<region>/*-manifest.json`. No full PBF fetching/rebuilds in the
  connectivity refresh. All products visible under `connectivity/<pair>/`
  and `connector-matrices/<region>/`; nothing uploaded to R2 or transferred
  to Android automatically.
- New regression tests under `tests/test_connectivity_automation.py`
  are wired into both validate and Graph Studio Linux CI.
- **NEXT EXACT ACTION:** verify post-merge rolling Linux release body and assets match `debab59`, then install on Legion; run **Build → Refresh connections** against existing Italy Nord-Est/Austria retained graphs without rebuilding. Inspect exact proven pair runtime and connector inventories/matrices, repeat for CURRENT reuse; diagnose any real-device failures. Then implement/test RoadPilot Android consumption tracked at https://github.com/kandyman991/SmartRide-Next/issues/512. Do not claim Android connectivity or Germany graph installed.
- **F8 was a successful routing breakthrough**. This automation moves its
  discovery/proof work to Legion build-time; F8 remains the on-device
  fallback for missing/stale/uncovered connections.


## Important correction — F8 succeeded; Graph Studio operationalizes F8 (2026-10-14)

- The user explicitly corrected the assistant's wrong phrase "failed F6/F8
  experiments". **F8 is NOT a failed experiment.** Its generalized multi-hop,
  Valhalla-proven frontier approach was the right routing breakthrough,
  demonstrated with real cross-graph handoffs. Old F6 and discarded
  pre-Valhalla filters were the failed/rejected strategies.
- Graph Studio's original mission is to **precompute, prove, inspect and
  package the connections learned from F8** for independent regional
  graphs, moving expensive first-route frontier discovery to Legion
  build-time without replacing the F8 algorithmic principles.
- Keep F8 on the phone for stale/missing/uncovered connections; never
  reinstate hard heading/distance filters or fixed portals. Validate
  endpoint arrival and real Valhalla directed edges.
- Prioritize **end-to-end Italy Nord-Est ↔ Austria ↔ Germany metadata
  production and Android consumption** over endless GUI route planner
  polishing. Report what is implemented separately from what is verified
  on physical Legion/Android devices.


## Graph Studio incomplete-arrival instrumentation — PR #70 merged (2026-10-14)

- **PR:** https://github.com/kandyman991/RoadPilot-Offline-Data/pull/70,
  merged as `9e590318cf82b108789d5416f3ae1889638362f6`.
- Final PR head `164e911a5a1b7a2570d8001ad79c789b9612d665`
  had **both required CI checks green**: Linux Graph Studio build,
  Rust tests and offline-data repository validation.
- Reproduced **Trento → Innsbruck** on `italy-nord-est` via real Legion M3:
  `46.064320,11.119191` → `47.250124,11.395549`;
  `route_endpoints_mismatch`, endpoint **1,566.47 m** short,
  start offset 25.25 m, 175.958 km, 7,312.182 seconds,
  4,308 vertices, elapsed 181 ms, exit code 1.
- M3 and desktop planner now share **actual geometry endpoint assessment**.
  M3 returns `route.actualStart`, `route.actualEnd` and
  `route.destinationReached` even on an incomplete route.
  GUI renders partial geometry with explicit **INCOMPLETE**, deviation,
  actual coordinates, distinct actual-stop marker and requested end marker,
  including both in map bounds. No route calculation, graph/PBF data,
  F8 heuristics, or build pipeline changes.
- Post-merge Linux release workflow:
  https://github.com/kandyman991/RoadPilot-Offline-Data/actions/runs/38482056670.
  **Check release notes/assets before installing:** rolling `.deb`
  must explicitly cite merge commit `9e590318`, not earlier `a113eb84`.
- Issue #69: https://github.com/kandyman991/RoadPilot-Offline-Data/issues/69
- **NEXT EXACT ACTION:** after published updated release, install the `.deb`
  on Legion and run same Trento/Innsbruck pair in GUI and M3 CLI,
  record exact `route.actualEnd`. Determine if the last geometry coordinate
  lies near the graph's actual road coverage edge or if destination
  correlation/connectivity explains the miss. Do not claim cause from
  the 25 km buffer alone or rebuild/delete graph caches.


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
