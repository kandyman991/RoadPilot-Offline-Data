# D-017 approved directed-road catalog publication contract — proposal

10 November 2026 · **NONPUBLISHING schema contract only**. This deliberately does not assert that PR #127's completed native A → exact X → B matching has passed separate completeness, time-dependent or Android UI acceptance. PR #127 was merged into main and its `roadpilot.f8-final-directed-connection-candidates` v1 schema remains **BLOCKED**, regardless of the number of native directed matches.

## Wire schema

`schemas/f8-approved-native-directed-road-connections.schema.json` defines `roadpilot.f8-approved-native-directed-road-connections` version 1, separate from all candidate/test-only formats. It is compatible with RoadPilot PR #543's strict reader. Each connection represents a distinct original A source final directed GraphId, original terminal node **exact X**, permitted vehicle modes, and **all corresponding incoming directed B GraphIds** that share its physical directed approach up to X. B road identity is not a preselected post-X turn: END_NODE and INTERIOR positions are separately recorded. B legal forward travel is decided by normal Valhalla routing from X.

Required provenance: original A and B immutable compiled archive SHA-256, exact graph source inventory proof hash, original directed B match proof hash, producer/Android acceptance commits, independently reviewed Android normal-planner first/repeat report hash and actual route-preview UI acceptance report hash. Reconcile counts from the authoritative native inventory, not the JSON document itself; each A source has exactly one connection record or an explicit independent native-supported rejection. Distinct B road matches may not be suppressed. Exclusions must include a proof SHA and `mustNotCreateConnection=true`.

Required approval: source physical-road/direction completeness VERIFIED, receiver directional identity VERIFIED, genuine branches preserved, normal installed-graph planner first/repeat device acceptance VERIFIED, real route-preview device acceptance VERIFIED, independent review VERIFIED, explicit owner approval GRANTED and productionPublication READY. Any remaining NOT_VERIFIED/NOT_RUN/UNKNOWN/BLOCKED/PENDING values **must prevent publication**.

## Publication safeguards

A schema-valid JSON file is not itself proof: **the existing PR #127 producer must not emit READY from its current evidence**. A future producer implementation must compare the complete independent original A census, original B matches, branch/mode restrictions, all explicit exceptions and Android product evidence, and fail closed if anything is unresolved. It may use this exact v1 output shape only after those checks are genuinely satisfied.

The RoadPilot app validates every field and original graph SHA against managed, byte-verified installed originals. Its activation additionally requires the SHA-256 of the **entire published JSON file** in the signed APK's owner-reviewed catalog-pin manifest. PR #543's pin manifest is currently empty, and staging a fabricated READY JSON cannot enable ordinary routing. On graph change, corrupted manifest, unknown exact region polygon, missing authentic original TAR parity, wrong vehicle mode, duplicate or omitted GraphIds, or failed owner approval, activation must fail closed; no old F8 fallback may hide the error.

## Remaining actual work

The acceptance data from PR #127 was merged without falsely ticking complete physical-road direction proof and Android UI acceptance. To publish any READY catalog, finish those objective gates on original Valhalla 3.6.3 graph data, produce reviewed proof refs, generate an immutable deterministic artifact in the already existing Graph Studio post-build flow after both neighboring graphs exist, and secure owner approval. RoadPilot must run normal `ManagedFrontierChainRoutingRuntime.plan()` + `RoadPilotProductRouteProvider.getRoutes()` and user-visible route-preview, both directions in car and motorcycle first/repeat with branch, stacked road, loop, restriction and cancellation cases.

This proposal **does not create an approved production catalog**, does not change the existing discovery/matching architecture or its 25-km buffer, does not release an APK, and does not authorize PR #543 merge.
