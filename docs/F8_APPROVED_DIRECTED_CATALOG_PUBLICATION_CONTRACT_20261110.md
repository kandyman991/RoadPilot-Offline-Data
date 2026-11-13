# D-017 approved directed-road catalog publication contract — proposal

> **Scope clarification, 13 November 2026:** This historical contract is
> for the prospective RoadPilot Android *consumer/public release*, NOT
> Graph Studio private completion. Android device, route-preview, signed
> APK pin and owner public-release review do not block Graph Studio. Its
> private native validated catalog is described in
> GRAPH_STUDIO_PRIVATE_NATIVE_CATALOG_ACCEPTANCE_20261113.md.
> The original RoadPilot runtime READY schema remains unchanged.

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

## Production implementation — immutable real-archive preflight (10 November 2026)

The existing PR #127 native A-final → exact X → incoming directed B road
matcher has NOT been replaced. PR #128 adds
tools/preflight_f8_approved_directed_catalog.py, which:

1. Re-runs the existing independent source/root/B-oriented-geometry audit on
   the original PR #127 evidence, rehashes BOTH compiled original Valhalla
   archives, and regenerates the independent source dispositions for equality.
2. Cross-checks every source original A directed GraphId, original X, vehicle
   permissions, all corresponding B incoming original directed GraphIds,
   END_NODE/INTERIOR relation, directed overlap, X projection and pair graph
   provenance. Missing, duplicate, altered or invented identities fail closed.
3. Outputs ONLY an immutable, nonroutable production-preflight evidence report:
   schema roadpilot.f8-approved-directed-road-production-preflight,
   publication BLOCKED and notForRoadPilotRuntime true.
4. Preserves every positive native A→X→B incoming road correspondence, even
   when no legal B outgoing turn is known under default costing. Outgoing
   continuation and same-road-after-junction identity are NEVER match gates;
   Android Valhalla will evaluate actual B turns under the real journey.
5. Lists all unverified production requirements explicitly. No READY output
   mode or automatic production pin generation exists in this tool.

### Real original compiled Valhalla 3.6.3 result

| Direction | Original A finals | Matched directed B incoming roads | Unlinked short-window roots (not additional roads) | Publication |
|---|---:|---:|---:|---|
| Italy Nord-Est → Austria | 454 | 454 | 191 | BLOCKED |
| Austria → Italy Nord-Est | 253 | 253 | 94 | BLOCKED |
| **Total** | **707** | **707** | **285** | **BLOCKED** |

Immutable original TAR SHA-256:
Italy Nord-Est e6a10d36f8622ac0e47dc3d17a8295f60b144f9a2ad478e1b5f6ef2dbea75953;
Austria ee7baac93b639d0c2fefab8f90540d26d03fd28a283c73bff516a1d8bdc2bc7b.

Local nonpublishing reports, never installed into RoadPilot, under
~/RoadPilotGraphStudio/diagnostics/f8-production/20261109/:

- italy-ne-to-austria-approved-production-preflight-BLOCKED-20261110-v1.json
  SHA-256 480642980fbfbcc815cf5e9c96a33e17ae975166ad5a2247d512851f620e938e
- austria-to-italy-ne-approved-production-preflight-BLOCKED-20261110-v1.json
  SHA-256 fcef823ce58f9fb6586396fdc13f85496c93625754d63b014b7a36e98e930c77

Both reports are intentionally rejected by the separate future production
READY JSON Schema, as checked with JSON Schema Draft 2020-12.
Synthetic corruption tests cover missing/duplicate directed A/B identities,
wrong endpoint X, access-mode escalation, mutated projection/overlap, graph
archive mismatch and false verification. No outgoing-turn condition is used
to accept or reject an A/B incoming physical-road match.

### What remains before an actual approved catalog

The existing 707 original native incoming physical-road correspondences
are now independently and deterministically reconciled. This is NOT the
same as semantic one-per-physical-road direction source lineage across
the entire relevant pair cut. That separate source proof is still
NOT_VERIFIED, as is real Android normal planner first/repeat car/motorcycle
route preview, both directions. Independent review, explicit owner
production approval and a signed APK SHA-256 catalog pin remain outstanding.

The next work should prove the source lineage using original native
topology and exercise the existing Android exact-GraphId A→X→B test
harness through normal route-preview UI, without adding a second
matcher, fake owner approval, or a hardcoded road. Only after actual
proofs and owner authorization should a controlled READY publication
step be implemented and invoked.

To reproduce the real Italy→Austria preflight on Legion:
Run python3 tools/preflight_f8_approved_directed_catalog.py with
--catalog <pair-directed-road-matches-at-x-20261110-v1.json>,
--native-evidence <pair-catalog-evidence-v2.json.gz>,
--dispositions <pair-M1-final-dispositions-20261110.json>,
--from-archive <original A compiled TAR>,
--to-archive <original B compiled TAR>,
--output <new BLOCKED report path>.
All are required, with exclusive-create output (never overwrite).
Reverse the inputs to check Austria→Italy. The executable itself contains
no hardcoded regions.

PR #128 and RoadPilot PR #543 remain DRAFT, UNMERGED and nonpublishing.

## 10 November 2026 — owner-accepted evidence, complete automatic catalog generation

The owner accepted the Legion original-native correspondence and previously
completed four explicitly chosen Android journeys as engineering evidence,
then requested automatic catalog generation and actual autonomous RoadPilot
crossing selection. This does not constitute independent READY review or
authorization to merge, release or publish a signed production APK.

New generic generator: tools/build_f8_native_auto_catalog.py.

It independently rehashes both original compiled Valhalla TAR archives,
reruns the original PR127 directed native A/B audit, reconstitutes the
independent source-terminal dispositions, verifies the exact retained
preflight report and binds its *actual* SHA-256 bytes. It preserves ALL
distinct A final directed GraphIds, B incoming directed roads, exact X
and car/motorcycle mode permissions. No new road matcher, outgoing-B-turn
gate, road-name heuristics, arbitrary crossing point or hardcoded region.

Nonpublishing automatic pair catalogs on the Legion under
~/RoadPilotGraphStudio/diagnostics/f8-production/20261109/:

| Directed pair | Original A finals | Original B incoming | Catalog SHA-256 |
|---|---:|---:|---|
| Italy Nord-Est → Austria | 454 | 454 | d5225a0ed5fd691e32d3e81304c73016362b0f0e288a3ada1a228a44ee0b8f05 |
| Austria → Italy Nord-Est | 253 | 253 | 5dd70b5d9f4639a7391bbba51672a57aac18dfc13bbc9cd20d48621917221dd3 |

CLI takes required --catalog, --native-evidence, --dispositions,
--preflight, --from-archive, --to-archive and --output parameters, all
relative to the actual original graph pair. Output is exclusively
BLOCKED_TEST_ONLY; the separate READY contract remains protected by
independent review, explicit production approval and a signed APK hash pin.
The generator is region-independent and refuses to overwrite an output.

Both full catalog files were independently loaded on the Legion Android
emulator through the explicit debug-only SHA-bound auto-selection gate.
The normal RoadPilot Planner -> Create Route -> original regional Valhalla
and exact-edge JNI -> Ferrostar -> actual visible Route Preview succeeded
in BOTH directions and for BOTH car and motorcycle, without supplying
a source GraphId:

| Direction | Automatically selected original A -> matching B incoming | Preview |
|---|---|---|
| Italy Nord-Est → Austria | 1295341612010 -> 1580218739690 | 129.7 km / 1 h 42 min |
| Austria → Italy Nord-Est | 48089797098 -> 824405135850 | 151.8 km / 6 h 29 min |

Both vehicle profiles returned the same preview for the same endpoints.
Evidence: ~/RoadPilotGraphStudio/diagnostics/f8-production/20261110/android-auto-catalog/f8-auto-catalog-four-mode-ui-BLOCKED-20261110-v1.json.
Evidence SHA-256: 604c2632d6d7e3a7dae38082e1f2453c9b842e95151e5d37bd0bc1072fd28724.
Four original Android screenshot PNGs and correlated timing logs accompany it.

**Open issue, separate from native physical-road matching:** The reverse
Faster debug selector exits on the first valid native match, producing
6 h 29 min instead of a different, earlier proven 2 h 33 min crossing.
This establishes automatic *validity* but NOT optimal route selection.
The production catalog planner currently probes all sources to select
the best, which may itself take excessive time. Improve routing selection
efficiently while retaining every certified road/direction in the catalog
and never returning to the legacy discovery.

Graph Studio PR #128 and RoadPilot PR #543 remain DRAFT and unmerged;
neither project emits a READY or owner-signed/pinned catalog yet.
