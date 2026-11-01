# Graph Studio Phase 4 — read-only dependency audit and guarded retirement plan

**Audit date:** 2026-11-01  
**Repository:** `kandyman991/RoadPilot-Offline-Data`  
**GitHub main at audit:** `1d71db035695060341dd0b54fa142ce1ee5135b5`  
**Last functional Graph Studio merge:** PR #92, `437af035331e9b983fb4d7f6f34f7a28dabd9188` (later commits on main are documentation-only).  
**Tracking:** [UI audit issue #89](https://github.com/kandyman991/RoadPilot-Offline-Data/issues/89); architecture/completeness [#73](https://github.com/kandyman991/RoadPilot-Offline-Data/issues/73), [#82](https://github.com/kandyman991/RoadPilot-Offline-Data/issues/82).

**Decision:** This is an inventory/plan only. No runtime, GUI, Python, schema, test, or shipped data is removed by this PR. All Phase 1–3 UI findings (UI-01…UI-13) are marked DONE in `docs/GRAPH_STUDIO_UI_AUDIT.md`; Phase 4 is a separate dependency and compatibility gate, **not** permission to remove every feature labeled “legacy.”

## Method and evidence limits

1. Read `AGENTS.md`, `CHAT_HANDOFF.md`, `ROADMAP.md`, `docs/ARCHITECTURE_CONTRACT.md`, `docs/ARCHITECTURE_GAPS.md`, `docs/ARCHITECTURE_MEMORY.md`, and `docs/FAILED_APPROACHES.md`; reconciled their historical claims with live main/PR/issue state.
2. Examined the Legion source checkout at `/home/mircea/projects/RoadPilot-Offline-Data`, at local commit `265eab5` (the same functional Graph Studio source as PR #92). GitHub main later adds only PR #93/#94 architecture-history documentation. Local working branch `main` was not edited.
3. Reviewed the 155 Git-tracked files, including 61 tracked files under `tools/`, frontend `graph-studio/src/main.ts`, Tauri `graph-studio/src-tauri/src/lib.rs`, packaging `graph-studio/src-tauri/tauri.conf.json`, Python tools, `tests/` and `.github/workflows/`. Searched filename/module references in *other* tracked source/test/workflow files, not just in documentation.
4. Ran the 110-test Python suite using the existing Graph Studio application venv: `PATH=/home/mircea/.cache/app.roadpilot.graphstudio/python-env/bin:$PATH PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -q` → **110 tests, OK**, 2026-11-01. An initial run using system Python failed on missing Shapely; a second run with venv Python but without venv `PATH` failed because one test subprocess invokes `python`. Neither was a product-code regression; the fully configured venv run passed. No F8 graph scan, build, publication, Android test, or live interactive GUI acceptance was performed.
5. Static “no in-repository callers” means *candidate for further review*, **not proof of dead code**: CLI scripts can be invoked externally, reflected/dynamically imported or used to inspect old artifacts. No network scan of every possible external consumer or installed historical version was done.

## Dependency inventory and disposition

| Component / source locations | Current dependency evidence | Classification and Phase 4 action |
| --- | --- | --- |
| Native F8 CLI + scan/proof pipeline: `tools/graph_studio_f8_workspace.py`, `build_native_f8_pair_evidence.py`, `capture_native_f8_graph_windows.py`, `discover_native_f8_crossings.py`, `probe_native_f8_journey.py`, `native_f8_inputs.py`, `native-f8-edge-scan/` | Tauri `f8_command` calls the workspace Python engine; frontend calls `f8_pair_overview`, `f8_start_workflow`, `f8_workflow_status`, `f8_cancel_workflow`. Native sources, tests and evidence pipeline remain linked. | **ACTIVE — PROTECT.** No changes to reference F8, edge inventories, exact fingerprints, Valhalla proof, graph packs or Android fallback. Android scanner parity and global handoff completeness remain NOT_VERIFIED; production sidecar publication BLOCKED. |
| Manual crossing and saved overrides: Tauri `snap_handoff_point`, `validate_handoff_override`, `save_handoff_override`, `list_handoff_overrides`, `delete_handoff_override` and `handoff_dir`; frontend Border Inspector Manual/Saved tabs | Frontend invoke calls and active buttons remain. `handoffs/` records are persisted and may be used by installed builds; `export_border_diagnostics` summarizes their evidence. | **ACTIVE USER DATA — PROTECT.** No deletion or format migration without import/export/round-trip and real GUI tests; no automatic destructive cleanup. |
| Historical handoff artifact viewer: Tauri `transition_artifact_dirs`, `collect_json_files`, `normalize_transition_document`, `inspect_handoff_artifacts`, `export_border_diagnostics`; frontend Saved evidence panel | Tauri searches `transitions/`, `imports/handoffs/`, `connectivity/`, `imports/connectivity/`, `connector-matrices/`, `imports/connector-matrices/`. Frontend `inspect_handoff_artifacts` and export invoke calls exist. | **LIVE READ-ONLY FORENSIC WORKFLOW — RETAIN.** Historical records remain explicitly non-authoritative as native-F8 completeness proof. Archive before considering any schema-reader retirement. |
| Historical connector inventory/matrix inspector: `inspect_region_connector_matrix` and `connector_inventory_current` in Rust; `refreshConnectorMatrix` in frontend | The Legacy diagnostics tab actively calls Tauri, checks graph/boundary fingerprints and source inventory hash, renders matrix cells and status. | **LIVE LEGACY GUI FEATURE — RETAIN IN ADVANCED/LEGACY TAB.** It is not the production F8 chooser. Any future UI removal requires explicit UX approval and saved-evidence export/compatibility checks. |
| OSM-way A/B road overlap and historical border road diff | `scheduleBorderRoadDiff` runs only when the Legacy tab is selected; `refreshBorderDiffBtn` and source overlays remain accessible. Separate routing/visual comparison features use their own backends. | **LIVE OPT-IN DIAGNOSTIC — RETAIN.** Do not confuse a non-authoritative *inspection* view with the retired OSM-based F8 *discovery producer*. |
| Region editing, source selection, routing graph building, visual PMTiles, search/POI and publication | Tauri Python subprocess dispatchers and workflow references remain, e.g. `graph_studio_regions.py`, `build_routing_region.py`, `validate_routing_pack.py`, `build_visual_region_pack.py`, `roadpilot_search_v2.py`, `compare_search_builds.py` and R2 publishing scripts. | **ACTIVE — PROTECT.** Do not remove because corresponding original menu destinations were reorganized in Phase 2. |
| `tools/build_connectivity_pair_manifest.py`, `validate_cross_region_connectivity.py` | The former is used by the native F8 workspace and validation CI; the latter is executed by `.github/workflows/validate.yml`. | **REFERENCED — PROTECT.** Do not indiscriminately remove files containing “connectivity.” |
| `tools/audit_f8_graph_edge_parity.py` | Referenced by `tests/test_f8_graph_edge_audit.py`; diagnostic parity work is still open. | **TEST/FORENSIC UTILITY — PROTECT.** |
| `tools/list_publication_releases_r2.py` | No in-repository runtime/workflow/test reference found in static search, but documented as a standalone administrative CLI. | **MANUAL OPERATIONS / UNDETERMINED — PROTECT** until external maintenance workflows are checked. |
| Old OSM-first discovery *producer* scripts (`build_frontier_road_inventory.py`, `correlate_frontier_roads.py`, `build_crossing_candidates.py`, `prove_crossing_candidates.py`, `compile_runtime_connectivity.py`, `plan_multiregion_route.py`) | These executable producer files are **already absent** from current tracked `tools/`; earlier deletion/retirement is documented in `AGENTS.md`, `docs/FAILED_APPROACHES.md`, issue #82. | **ALREADY RETIRED.** No new deletion work; never revive to restore a historical schema or as a shortcut to F8 parity. |
| Legacy schema validators listed below | Standalone `tools/validate_*.py` CLIs, with no filename/module references from other tracked application source, tests, or GitHub workflow files in this audit. A loose Python syntax check in CI still compiles all tools; Tauri bundles every `tools/` file by wildcard. | **POSSIBLE RETIREMENT CANDIDATES, NOT APPROVED FOR REMOVAL.** Need historical artifact and external CLI compatibility proof first. |

### Candidate group: 11 standalone, apparently uncalled legacy validators

All are present as tracked files, are shipped inside the application because `graph-studio/src-tauri/tauri.conf.json` maps `../../tools/` to `pipeline/tools/`, and may still be useful to inspect old records:

```
tools/validate_connectivity_chain_plan.py
tools/validate_connectivity_refresh_plan.py
tools/validate_crossing_candidates.py
tools/validate_crossing_proofs.py
tools/validate_frontier_road_correlations.py
tools/validate_frontier_road_inventory.py
tools/validate_hierarchical_connectivity_plan.py
tools/validate_region_connector_inventory.py
tools/validate_region_connector_matrix.py
tools/validate_region_connector_refresh_plan.py
tools/validate_runtime_connectivity.py
```

**Evidence level:** no in-repository caller found by filename/module-text scan; none appear as explicit `tests/` or `.github/workflows/` CLI dependencies. **Not checked:** external invocations, scripts outside this checkout, user-installed `pipeline/`, files referenced only through runtime-computed paths, historical package consumers, or actual old schema fixtures. They are *candidates to deprecate*, not conclusively safe to delete.

### Retained data and compatibility boundary

The installed/user-managed Graph Studio workspace must never be treated like disposable repository build output. In particular, do not erase or silently rewrite existing `handoffs/`, `transitions/`, `connectivity/`, `connector-matrices/`, and corresponding `imports/` records; do not delete retained regional graphs, visual PMTiles, POI DBs, manifests, source caches or diagnostic captures. Keep historical schema readers and local manual overrides until their users and forensic requirements are audited.

The current main’s resource wildcard bundles **all Python tools**, meaning a source file deletion changes the shipped AppImage/.deb CLI surface even without changing any Tauri command. Also preserve inter-repository schema compatibility with `kandyman991/SmartRide-Next` (Android ingestion issue #512). No Android production consumer equivalence or graph parity is claimed here.

## Proposed implementation sequence (separate gated PRs only)

**P4-A — This PR: inventory only.** Owner and independent reviewer inspect classifications. No code/data deletion, no version bump, no release.

**P4-B — Establish negative-dependency evidence.** For each of 11 validator candidates, confirm no use by Tauri subprocess dispatch, Python imports, CI, shell scripts, documentation, packaging install hooks, external job scripts, saved historical artifacts or Android integration contracts. Capture at least one relevant fixture for each historical schema or explicitly document fixture absence. Record preservation/migration destination and any loss of CLI compatibility. If external use cannot be ruled out, keep the validator or deprecate with a versioned migration window.

**P4-C — Small isolated removal/archival PR(s), only after explicit approval.** Prefer grouping by schema family with independent commit(s); test that the application still starts, affected current workflows work, historical artifacts remain readable where required, and rollback to the previous installed build is possible. No bulk directory removal or data migration. Keep all original diagnostic evidence in Git history and evidence registers; moving source to a documented archive can be safer than deleting public CLI behavior without notice.

**P4-D — Exact-head acceptance before merging implementation PRs.** `architecture-contract`, `validate`, `linux` CI green on corrected head; Python/unit/contract regressions; TypeScript/Vite UI checks across wide and narrow layouts; AppImage and Debian packaging smoke; live Legion GUI open and inspect Manual/Saved/Legacy tabs, map overlays, history and diagnostics export, Build/Compare/Publish/Native F8 entrypoints; saved-override roundtrip and legacy schema fixtures; no unexpected file rewrites. Independent architecture/security/data-integrity review. Keep `docs/GRAPH_STUDIO_UI_AUDIT.md` and issue #89 open until implementation acceptance.

### Absolute stop rules

- **No change to accepted F8 architecture** without owner-approved superseding decision (`docs/ARCHITECTURE_CONTRACT.md` A1–D4).
- No OSM-only F8 discovery resurrection; no first-success/cached-section lock-in; no pre-Valhalla eligibility pruning; no cross-build GraphId equivalence.
- No claims that CI alone proves F8 parity, complete FASTER/SHORTER alternatives, Android device acceptance or safe publication.
- No deletion of saved user data, old evidence, current legacy-read-only viewers, or published artifacts based solely on reference-count heuristics.
- Any implementation plan that removes a currently used public CLI, Tauri API, historical reader, or saved-data compatibility path is a **behavior change** requiring a separate approval and test-backed migration.

**Next exact action:** independent review of this dependency audit/negative-caller classification; collect evidence of external and historical validators' use. Only then propose the first bounded implementation cleanup PR and ask the owner to authorize the specific deletions.
