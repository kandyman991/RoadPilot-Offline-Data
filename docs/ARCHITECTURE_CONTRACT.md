# RoadPilot / Graph Studio — Binding Architecture Contract

**Status:** ACCEPTED. **Owner:** user/product owner. **Scope:** RoadPilot Android and RoadPilot Graph Studio regional offline routing, discovery, validation, caching, and packaging.

This file is the stable behavioral contract for **what must be built**. It is not proof that code already satisfies the contract. The live source, regression tests, and real graph/device evidence establish implementation status. Do not silently narrow or replace this design for convenience.

## A. Reference architecture: F8, not a replacement algorithm

**A1 — Proven baseline.** Generalized forward multi-hop F8 is the known working reference for cross-region routing. Its core implementation is in RoadPilot Android:
- app/src/main/java/com/kandyman991/smartridenext/routing/FrontierRouteLocalRecovery.kt
- app/src/main/java/com/kandyman991/smartridenext/routing/ManagedFrontierChainRoutingRuntime.kt
- app/src/main/java/com/kandyman991/smartridenext/routing/FrontierMultiRegionChainPlanner.kt

**A2 — Work moves, behavior stays.** Graph Studio moves expensive handoff discovery, directional Valhalla proofs and reusable connection inventory production onto the Legion during graph builds/refresh. It must not replace the F8 frontier scan with a narrower search unless *equivalence is demonstrated* using actual F8 graph-edge results.

**A3 — Independent graphs.** Each region remains its own immutable, independently built Valhalla graph. No direct cross-graph sharing/comparison of GraphIds; never modify raw .gph files. RoadPilot composes region-local route legs with independently correlated, exact fingerprint-bound handoffs.

## B. Discovery completeness

**B1 — No first-success lock-in.** A successful handoff, cached route, learned section, or verified connection is NOT proof that all other connections are known. Continue discovery across every relevant frontier/overlap area. Preserve all valid alternatives (including separate highway carriageways, ramps, both travel directions, separate locations on the same named road, and multi-hop chains).

**B2 — No unproven pre-Valhalla rejection.** Heading, geometry gap, road class, road name/ref, nearest distance, and a failed partial route are ranking/diagnostic evidence, not hard eligibility gates. Valhalla is authoritative for directional/mode-specific legality.

**B3 — Full source coverage must be demonstrated.** Report scanned windows/frontiers, candidate counts, unresolved/rejected/inconclusive/proven counts, modes, directions and graph fingerprints. If search is capped, cancelled, timed out, source data missing, or actual F8 graph-edge parity unverified, declare the corresponding scope **INCOMPLETE / NOT_VERIFIED**. An artifact may say VALIDATED when its generated candidates passed proof; that does not mean all F8 alternatives were found.

**B4 — Graph-edge parity gate.** A release MAY claim that Graph Studio fully precomputes F8 handoffs only when it compares the actual RoadPilot F8 graph-edge scanner against Graph Studio's emitted candidates on the SAME exact regional graph versions, in representative real Italy–Austria, Austria–Germany, motorway, one-way, local-road and multi-hop cases. Every missing F8 candidate must be explained and recovered or reported as incomplete.

## C. Route choice and caches

**C1 — Compare journey-relevant alternatives.** For FASTER and SHORTER, select using complete Valhalla-detailed journey metrics including start and final legs, not merely the first stored crossing or intermediate matrix estimates. A shortcut is valid only with a proven bound establishing it cannot hide a better eligible route. A direct success inside one graph does not automatically establish global optimality.

**C2 — No misleading completeness.** Route-time candidate/probe/time budgets are permitted for bounded interactive response, but result metadata must distinguish budget-truncated and not-yet-searched alternatives. Do not label such a result as an exhaustively optimal FASTEST/SHORTEST journey.

**C3 — Cache is evidence, never the entire frontier.** Cache exact graph/boundary fingerprints, mode/direction, discovered alternatives and completion provenance. Reusing a cached successful crossing must never freeze discovery or suppress better alternatives for another trip. Stale/unverified records fail closed to F8.

## D. Verification and acceptance

**D1 — Each protected implementation PR must:** identify which contract IDs it preserves or implements; cite inspected F8 source; disclose architecture impact, known gaps, completion/proof state and tests; add regression tests for new routing behavior. If behavior differs from any accepted clause, STOP and request explicit user approval recorded in a linked decision before implementing or merging.

**D2 — Automated regression minimum:** multiple same-name/disjoint crossing candidates retained; different correlated directed edges preserved; second faster crossing selected even when a first connection succeeds; both FASTER and SHORTER compare real full-route costs; graph fingerprint mismatch rejected; incomplete/ambiguous connection never claimed exhaustive; per-leg directed Valhalla and final destination proof not bypassed. Tests use synthetic fixtures for deterministic CI and real graph/device evidence for parity.

**D3 — Evidence tiers (NEVER interchangeable):**
1. IMPLEMENTED: committed code exists.
2. CI VERIFIED: unit/integration/regression checks passed on specified SHA.
3. F8 PARITY VERIFIED: actual reference graph-edge comparison report attached.
4. DEVICE VERIFIED: exact installed graphs, journey coordinates/mode and route diagnostics documented.
5. PRODUCTION READY: explicitly approved after the above and Android ingestion/rollback validation.

**D4 — Merge gate.** No discovery PR is declared architecture-complete or production-ready merely from green CI. Known gaps remain documented until factual comparison evidence closes them. A change that breaks an accepted invariant must not be merged without a *new user-approved* architectural decision and an updated test/evidence plan.

## E. Change control / precedence

- This contract outranks informal plans, older design drafts, convenient shortcuts and inferred assistant preferences. AGENTS.md, CHAT_HANDOFF.md and docs/ENGINEERING_DECISIONS.md point here.
- A new architecture must be proposed in a PR with the exact superseded clause, technical justification, a real comparison against F8, a tracked issue and a documented explicit approval by the user. Approval to work on a feature is NOT blanket approval to change this contract.
- Update the permanent decision log when approved; never erase previous failures or architectural choices.
- When the implementation diverges: **flag it immediately, stop modifying architecture, and describe the conflict before continuing**.

## Current known deviations

See docs/ARCHITECTURE_GAPS.md. These are not permissions to claim correctness. Treat issue #73 as the F8 discovery-completeness acceptance gate and RoadPilot Android issue #512 as the ingestion/device validation gate.

The linked PR template and architecture-contract CI check are enforcement mechanisms. GitHub rulesets/branch protection must additionally make the CI job a *required* status check and require code-owner review for contract edits; otherwise GitHub may still allow a bypass.
