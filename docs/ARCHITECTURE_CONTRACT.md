# RoadPilot / Graph Studio — Binding Architecture Contract

**Status:** ACCEPTED. **Owner:** user/product owner. **Scope:** RoadPilot Android and RoadPilot Graph Studio regional offline routing, discovery, validation, caching, and packaging.

This file is the stable behavioral contract for **what must be built**. It is not proof that code already satisfies the contract. The live source, regression tests, and real graph/device evidence establish implementation status. Do not silently narrow or replace this design for convenience.

## A. Reference architecture: F8, not a replacement algorithm

**A1 — Proven baseline.** Generalized forward multi-hop F8 is the known working reference for cross-region routing. Its core implementation is in RoadPilot Android:
- app/src/main/java/com/kandyman991/smartridenext/routing/FrontierRouteLocalRecovery.kt
- app/src/main/java/com/kandyman991/smartridenext/routing/ManagedFrontierChainRoutingRuntime.kt
- app/src/main/java/com/kandyman991/smartridenext/routing/FrontierMultiRegionChainPlanner.kt

**A2 — Build-time final-edge production.** Under owner decision D-017, Graph Studio reads the final native directed road edges at each original 25-km graph cutoff, correlates the actual receiving graph's same physical road and direction, and precomputes a reusable connection catalog. It does **not** perform individual Valhalla route/TripLeg proof calls for each connection. F8 remains the Android runtime routing/fallback foundation; real Android A→X→B journeys validate the finished integration. Implementation is specified by [F8 boundary final-edge contract](F8_BOUNDARY_FINAL_EDGE_IMPLEMENTATION_CONTRACT.md).

**A3 — Independent graphs.** Each region remains its own immutable, independently built Valhalla graph. No direct cross-graph sharing/comparison of GraphIds; never modify raw .gph files. RoadPilot composes region-local route legs with independently correlated, exact fingerprint-bound handoffs.

## B. Discovery completeness

**B1 — No first-success lock-in.** A successful handoff, cached route, learned section, or verified connection is NOT proof that all other connections are known. Continue discovery across every relevant frontier/overlap area. Preserve all valid alternatives (including separate highway carriageways, ramps, both travel directions, separate locations on the same named road, and multi-hop chains).

**B2 — Direct compiled-graph matching, no invented filters.** Producer eligibility comes from actual native directed edges near the original source graph's 25-km cutoff, the same physical receiving road and direction, and the vehicle-access bits stored in each compiled Valhalla graph. Never suppress a genuine physical branch using name, way ID, road class, approximate proximity, arbitrary numeric caps or a first successful match. No separate Valhalla route is required merely to re-prove compiled final/receiving GraphIds.

**B3 — Only complete *boundary* coverage counts.** Graph Studio must account for all relevant original boundary-area tiles, final physical road/directions and actual receiving correlations; retain a simple unmatched/incomplete status, mode sets and graph fingerprints. A full original graph edge census, arbitrary off-boundary continuation traversal or per-entry route-proof ledger is **not** required. Missing/rebuilt graphs, ambiguous physical matching or truncated native boundary selection mean **INCOMPLETE**, not zero crossings or successful publication.

**B4 — Real Android journey acceptance (RoadPilot consumer/release only).** The catalog's **RoadPilot Android runtime integration and public/consumer release** are accepted only after RoadPilot consumes it with the **same exact original graph versions** and successfully navigates real A→X→B journeys in both directions and supported modes, including motorway, ramps, local roads and multi-hop cases. Confirm useful alternate crossings and FASTER/SHORTER behavior. Do not require a separate all-edge diagnostic parity scan or thousands of graph-build-time A-last/B-first Valhalla route calls. **This is NOT a prerequisite for completing Graph Studio's independent owner-only native producer**: when native SHA-pinned final-edge/B-directed matching and independent audit pass, Graph Studio may emit `GRAPH_STUDIO_PRIVATE_READY` without Android journey, JNI, signed APK or catalog-pin evidence (PR #135). The private catalog is explicitly `notForRoadPilotRuntime=true`; it is not RoadPilot public READY.

## C. Route choice and caches

**C1 — Compare journey-relevant alternatives.** For FASTER and SHORTER, select using complete Valhalla-detailed journey metrics including start and final legs, not merely the first stored crossing or intermediate matrix estimates. A shortcut is valid only with a proven bound establishing it cannot hide a better eligible route. A direct success inside one graph does not automatically establish global optimality.

**C2 — No misleading completeness.** Route-time candidate/probe/time budgets are permitted for bounded interactive response, but result metadata must distinguish budget-truncated and not-yet-searched alternatives. Do not label such a result as an exhaustively optimal FASTEST/SHORTEST journey.

**C3 — Cache is evidence, never the entire frontier.** Cache exact graph/boundary fingerprints, mode/direction, discovered alternatives and completion provenance. Reusing a cached successful crossing must never freeze discovery or suppress better alternatives for another trip. Stale/unverified records fail closed to F8.

## D. Verification and acceptance

**D1 — Each protected implementation PR must:** identify which contract IDs it preserves or implements; cite inspected F8 source; disclose architecture impact, known gaps, completion/proof state and tests; add regression tests for new routing behavior. If behavior differs from any accepted clause, STOP and request explicit user approval recorded in a linked decision before implementing or merging.

**D2 — Minimal functional regression:** boundary-only native final-edge selection (including `deadend=false` and `is_road=false` cases), same-direction receiving physical correlation, genuine branch and both-mode preservation, graph/buffer fingerprint invalidation, no first-success lock-in and honest incomplete status. Android journey tests cover FASTER/SHORTER and final destination using Valhalla on the actual route legs. Do not add a separate producer diagnostic/proof pipeline.

**D3 — Evidence tiers (NEVER interchangeable):**
1. IMPLEMENTED: committed code exists.
2. CI VERIFIED: unit/integration/regression checks passed on specified SHA.
3. BOUNDARY CATALOG VERIFIED: all relevant source final directed edges and receiving branches accounted for in the produced catalog on exact graph fingerprints.
4. ANDROID JOURNEYS VERIFIED: exact installed graph versions, real A→X→B journeys, modes, direction and final destination recorded.
5. PRODUCTION READY: explicitly approved after the above and Android ingestion/rollback validation.

**Owner private development tier (approved 13 November 2026):** `GRAPH_STUDIO_PRIVATE_READY` is distinct from items 4–5 above. It means independently native-audited, immutable original A-final→X→B catalog coverage **within its documented bounded endpoint domain**, without asserting globally unique physical-road/direction lineage or Android consumption. It does not change the requirement to validate real Android journeys **when RoadPilot integration itself is later released**. See [Graph Studio native private catalog acceptance](GRAPH_STUDIO_PRIVATE_NATIVE_CATALOG_ACCEPTANCE_20261113.md) and [issue #73](https://github.com/kandyman991/RoadPilot-Offline-Data/issues/73).

**D4 — Merge gate.** No discovery PR is declared architecture-complete or production-ready merely from green CI. Known gaps remain documented until factual comparison evidence closes them. A change that breaks an accepted invariant must not be merged without a *new user-approved* architectural decision and an updated test/evidence plan.

## E. Change control / precedence

- This contract outranks informal plans, older design drafts, convenient shortcuts and inferred assistant preferences. AGENTS.md, CHAT_HANDOFF.md and docs/ENGINEERING_DECISIONS.md point here.
- A new architecture must be proposed in a PR with the exact superseded clause, technical justification, a real comparison against F8, a tracked issue and a documented explicit approval by the user. Approval to work on a feature is NOT blanket approval to change this contract.
- Update the permanent decision log when approved; never erase previous failures or architectural choices.
- When the implementation diverges: **flag it immediately, stop modifying architecture, and describe the conflict before continuing**.

## F. Owner-approved F8 production implementation (D-017, 2026-11-05)

**Binding four-step specification:** [F8 boundary final-edge implementation contract](F8_BOUNDARY_FINAL_EDGE_IMPLEMENTATION_CONTRACT.md). The accepted implementation is **source final original directed edge → same physical receiving directed edge → one per-road/direction connection with mode union and distinct branches → real Android journeys**. Use boundary-related compiled graph tiles and immediate native edge references; do not enumerate millions of unrelated original edges. Valhalla's compiled `GraphId`, end node, geometry, access and topology are authoritative inputs, while `deadend` is a hint rather than an exact graph-buffer cutoff flag. **No automatic per-connection A-last/B-first TripLeg route proof.** In conflicts this specific D-017 implementation supersedes earlier Graph Studio *producer* requirements in D-002, D-012, D-014 and D-015; independent regional graphs, F8 Android fallback and actual trip routing remain unchanged.

The all-tile build census and previously retained-ledger flow on draft PR #125 are **not compliant** with this owner-approved producer contract. Do not merge or release them as the new producer. This approval does not claim implementation, Android acceptance or catalog publication.

## Current known deviations

See docs/ARCHITECTURE_GAPS.md for the **dated and explicitly reconciled** evidence. [Issue #73](https://github.com/kandyman991/RoadPilot-Offline-Data/issues/73) tracks broader global physical-road-lineage / route-alternative completeness **without blocking private Graph Studio catalogs**. [Issue #82](https://github.com/kandyman991/RoadPilot-Offline-Data/issues/82) is superseded/closed (retired OSM sampler). RoadPilot Android [issue #512](https://github.com/kandyman991/SmartRide-Next/issues/512) separately tracks ingestion/device validation.

The linked PR template and architecture-contract CI check are enforcement mechanisms. GitHub rulesets/branch protection must additionally make the CI job a *required* status check and require code-owner review for contract edits; otherwise GitHub may still allow a bypass.
