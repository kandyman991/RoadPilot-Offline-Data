# Retired architecture register — what is retired, what is retained, what is current

**Recorded:** 2026-11-03 (documentation only). **Authority:** `docs/ENGINEERING_DECISIONS.md` D-014 (2026-10-16) and D-015, `docs/ARCHITECTURE_CONTRACT.md`, `docs/GRAPH_STUDIO_PHASE4_DEPENDENCY_AUDIT.md`.

This file is a map for readers and agents. It changes no behaviour, removes no file and migrates no data. It is not proof of F8 completeness: Android F8 parity, exhaustive handoff discovery, Android ingestion and production publication remain **NOT_VERIFIED / BLOCKED** (issues #73, #82, Android #512).

## 1. Retired — must not return

D-014 retired the OSM-first crossing architecture from executable Graph Studio paths. The producers below are **absent from `tools/`** at the time of writing (checked against the tracked tool list). History is preserved in Git for forensic review only.

| Retired component | What it did | Status |
|---|---|---|
| OSM buffered-overlap crossing sampler (`build_frontier_road_inventory.py`) | sampled OSM road fragments across the shared buffer to produce an anchor inventory | removed; failed with more than 250,000 anchors, and a nominal-boundary variant produced zero anchors (issue #82, `docs/FAILED_APPROACHES.md`) |
| Independent locate-correlation (`correlate_frontier_roads.py`) | located stable OSM anchors in both graphs | removed |
| Candidate producer (`build_crossing_candidates.py`) | formed Graph A x Graph B candidate pairs (`roadpilot.crossing-candidates`) | removed |
| Proof producer (`prove_crossing_candidates.py`) | proved candidate pairs with Valhalla (`roadpilot.crossing-proofs`) | removed |
| Runtime connectivity compiler (`compile_runtime_connectivity.py`) | compiled proven crossings into `roadpilot.runtime-connectivity` | removed |
| Regional connector inventories and matrices | entry-to-exit matrices between connector anchors, and sparse hierarchical ranking on top | producers and composer removed (#35) |
| Bounded multi-region planner (`plan_multiregion_route.py`) | composed region chains from the stored crossings, with fixed chain and time budgets | removed |
| Connectivity refresh orchestrator (`refresh_graph_connectivity.py`) | ran the stages above | removed |

**Rules.**

- Do not recreate, call or restore any of these, however many generated candidates pass Valhalla, and do not raise their limits.
- Do not use the **candidate-pair model** they defined (`xpc1-` candidate ids, `fri1-` frontier-road ids, `stableWayId`, `sourceCandidateRank`, paired from/to anchors) as the model for native F8. Native F8 records are keyed by the receiver-side directed edge (a graph-local id inside its own fingerprint), per direction and mode.
- Do not adopt `roadpilot.runtime-connectivity`, or any extension of it, as the foundation of the native F8 production artifact. Reusing a field of a historical format requires an explicit, written compatibility justification recorded in a decision. None exists.
- References to these components in `ROADMAP.md`, `CHAT_HANDOFF.md`, older PRs and Android issue #512 describe the retired design. They do not override D-014.

## 2. Retained read-only — legacy, protected from deletion

Per the Phase 4 audit, none of the following is approved for removal. Removal or archival needs the separate P4-B/P4-C/P4-D gates, an owner decision and tested compatibility wrappers. **Current status (D-016, merged PR #104 on 2026-11-03):** the 11 validators and ten schemas below are archived under `tools/legacy_archive/connectivity/` and `schemas/legacy_archive/connectivity/`, with tested wrappers at the original validator paths; see `docs/GRAPH_STUDIO_PHASE4C_ARCHIVE_LEGACY_VALIDATORS.md`. The old top-level schema paths were not retained; external schema consumers remain unknown.

- **Legacy validators (11), shipped in the installed packages:** `validate_connectivity_chain_plan.py`, `validate_connectivity_refresh_plan.py`, `validate_crossing_candidates.py`, `validate_crossing_proofs.py`, `validate_frontier_road_correlations.py`, `validate_frontier_road_inventory.py`, `validate_hierarchical_connectivity_plan.py`, `validate_region_connector_inventory.py`, `validate_region_connector_matrix.py`, `validate_region_connector_refresh_plan.py`, `validate_runtime_connectivity.py`.
- **Legacy schemas in `schemas/`:** `connectivity-chain-plan`, `connectivity-refresh-plan`, `crossing-candidates`, `crossing-proofs`, `frontier-road-correlations`, `frontier-road-inventory`, `hierarchical-connectivity-plan`, `region-connector-inventory`, `region-connector-matrix`, `runtime-connectivity`.
- **Historical readers and viewers:** the Border Inspector saved-evidence panel, the Legacy diagnostics tab (connector-matrix inspector, OSM-way A/B road overlap), and the Rust normalizers in `graph-studio/src-tauri/src/lib.rs`.
- **Manual handoff overrides** (`handoffs/`) and historical records under `transitions/`, `connectivity/`, `connector-matrices/` and the matching `imports/` folders. Never erase or rewrite user-managed workspace data.
- **Forensic utilities and fixtures:** `tools/audit_f8_graph_edge_parity.py` (its inputs are retired-format correlations and candidates; leave it unchanged and define new parity against the native proposal inventory), and the Phase 4B historical fixtures and CLI compatibility tests.
- **Android-side learned artifacts** (`cross-graph-transitions`, bound variants) are the current Android learned-replay format; they appear in Graph Studio's viewer as legacy/debug inspection only.

These are not evidence of F8 discovery completeness.

## 3. Current — native F8 architecture (protect, build forward from here)

| Stage | Artifact or tool | Notes |
|---|---|---|
| Pair identity | `roadpilot.cross-region-connectivity` v1 from `build_connectivity_pair_manifest.py` | identity-only, `UNPROVEN`; graph and boundary fingerprints. `validate_cross_region_connectivity.py` is exercised by CI |
| Raw directed edges | `tools/native-f8-edge-scan/`, `capture_native_f8_graph_windows.py` (`roadpilot.native-f8-edge-scan`) | uncapped read-only Valhalla GraphReader scan, window catalog |
| Supporting evidence | `build_native_f8_pair_evidence.py` (`roadpilot.native-f8-physical-pair-evidence`) | exact same-way peers are evidence, never an eligibility filter |
| GPS proposals | `discover_native_f8_crossings.py` (`roadpilot.native-f8-gps-crossing-proposals`) | one receiver directed-edge seed per edge, both directions, none excluded |
| Journey proof | `probe_native_f8_journey.py` (`roadpilot.native-f8-journey-probe`) | bounded plain-Valhalla A to GPS to B; always reports its incompleteness |
| Orchestration | `graph_studio_f8_workspace.py`, Tauri `f8_*` commands, `native_f8_inputs.py` | local diagnostic workspace; publication `BLOCKED` |
| Android runtime | generalized F8 (`FrontierRouteLocalRecovery.kt`, `ManagedFrontierChainRoutingRuntime.kt`, `FrontierMultiRegionChainPlanner.kt`) | the working correctness fallback; unchanged |

Tier keys already present in these manifests (use them as the vocabulary for any new completeness reporting instead of a parallel scheme): `sourceWindowCoverage`, `proposalSourceCoverage`, `sharedBufferOverlapCoverage`, `completeGraphOverlapCoverage`, `frontierCorrelations`, `valhallaLegsProven` / `crossRegionRouteProof`, `androidF8ReferenceMatched` / `androidF8ScannerParity`, `routingOptimalityChecked` / `routeAlternativeOptimality`, `publicationState`. The meaning of `frontierCorrelations` in the native design (issue #82 asks for a finite, graph-backed reduction of buffer-interior proposals that loses no alternative) is an open owner decision.

## 4. Genuinely new work still required (not started, not authorized by this file)

Batched, checkpointed build-time Valhalla proof per receiver edge, mode and direction with explicit INCONCLUSIVE handling; independent verification of source coverage against the immutable archive; per-window scan outcomes; a parity harness against real Android JNI captures that reports what the 512-result cap and the road-key reduction lose; coverage-based region adjacency; a typed routing-package identity on Android beside the historical fingerprint; an Android reader for a future native artifact. Any new artifact schema must be derived from section 3, preserve every alternative, and pass the contract tiers. No schema or producer is defined here.

## 5. Android issue #512

The body of Android #512 still names `roadpilot.runtime-connectivity` pair artifacts and `roadpilot.region-connector-*` matrices as the data to consume. Those are the retired design. Suggested clarifying note for the issue (to be posted by the owner; this repository change does not edit issues):

> Superseded in part by Graph Studio D-014 and `docs/RETIRED_ARCHITECTURE.md`. The runtime-connectivity and connector-matrix artifacts named above are historical and must not be built on. Android should consume a future native-F8 handoff artifact, derived from the native directed-edge scan and GPS proposals, once its schema and the contract tiers (parity, both modes and directions, all alternatives, Valhalla leg proof, multi-hop cost) are approved. Fingerprint-bound installation, atomic update, rollback, F8 fallback and diagnostic provenance requirements in this issue still apply.

## 6. What this record does not do

No code, schema, workflow, test, tool, fixture or data file is changed. It does not authorize removal of any legacy item, publication, an Android change, or a new producer. Phase 4 cleanup remains independently gated.
