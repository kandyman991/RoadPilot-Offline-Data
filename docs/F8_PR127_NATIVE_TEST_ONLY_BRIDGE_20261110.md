# D-017 M1 existing-match finalization: audited original native A → X → B test input

10 November 2026. Graph Studio PR #127. **Nonpublishing, TEST ONLY.** No architecture change; the existing 25-km region overlap, source last original directed GraphId, exact terminal-node X, original B directed native geometry/topology and original vehicle-access restrictions remain the ONLY producer.

## Why we need a separate test-only artifact

The original `roadpilot.f8-final-directed-connection-candidates` v1 candidate ledger is intentionally **BLOCKED/NOT_VERIFIED**. Android cannot consume it as a production routing catalog. Existing independent audit `tools/audit_f8_physical_road_evidence.py` already proves, from the original Valhalla compiled pair:

1. source terminal directed GraphId + native original A end-node X is unchanged and accounts for the **independent bounded native** source terminal census;
2. original B native incoming edge direction/geometry overlaps source A's directed approach to X (not nearest GPS only);
3. original B outgoing directed edges start at X and are allowed by the *original native* car/motorcycle costing (not a road-name/class or angular heuristic);
4. all B alternatives and source exceptions remain visible and every original archive SHA is rehashed from the compiled TARs.

**Critical distinction:** an allowed *branch after the junction* need not be the *same road after the junction*. The verified A incoming/B incoming overlap is the **road-continuity proof up to X**; original B then handles legal vehicle turns after X. Identical road class/use or bridge/tunnel status is neither a necessary nor sufficient same-road-after-junction proof. The test-only file records this distinction explicitly and leaves post-junction same-road identity `NOT_VERIFIED`, along with physical-road source census completeness.

## Reuse of existing implementation

Optional `--test-only-catalog-output` on the existing independent native audit command emits the schema `roadpilot.f8-original-native-handoff-test-only` version 1. The producer first runs **the existing independent original-native ledger audit**, verifies the SHA-256 of **both actual original compiled TARs**, and only then writes the output with exclusive non-overwriting atomic semantics. No additional discovery pass, match heuristic, edge scan, GPS point or neighboring region identity matching exists.

The test-only document separates:
- **Original A source final directed GraphId, terminal native end-node and X**.
- **Every original B outgoing directed GraphId**, native B incoming predecessor(s) whose original directed approach overlaps A at X, legal original direction, car/motorcycle modes and native junction attributes.
- **Unresolved source finals** with exact IDs, X and reason; **unresolved original cut roots** separately, without claiming they represent additional missing physical roads.
- Original source/receiver archive SHA-256, buffer/index fingerprints, explicit `testOnly=true`, `sourcePhysicalRoadIdentityAcceptance=NOT_VERIFIED`, `productionPublication=BLOCKED`.

The candidate ledger remains untouched and unusable in product routing. The new output is a safe, finite **Android integration acceptance input** and cannot be labelled READY.

## Actual original Valhalla 3.6.3 verified results (Legion)

| Original pair | Native eligible terminal IDs | Native matched A finals | Preserved legal original B edges | Source exceptions | Matched A finals with conditional B uncertainty |
|---|---:|---:|---:|---:|---:|
| Italy Nord-Est → Austria | 454 | 260 | 401 | 194 | 16 |
| Austria → Italy Nord-Est | 253 | 160 | 245 | 93 | 5 |
| **Combined** | **707** | **420** | **646** | **287** | **21** |

Of the 646 B options, **451** have class/use/structure equal to the matched B incoming predecessor, and **195** change at least one of these attributes. Every option is retained, with native graph IDs and permissions; none is promoted merely because of its attributes, and none was discarded for a class/structure change.

Original archive fingerprints:
- Italy Nord-Est: `sha256:e6a10d36f8622ac0e47dc3d17a8295f60b144f9a2ad478e1b5f6ef2dbea75953`
- Austria: `sha256:ee7baac93b639d0c2fefab8f90540d26d03fd28a283c73bff516a1d8bdc2bc7b`

Local nonpublished artifacts:
`~/RoadPilotGraphStudio/diagnostics/f8-production/20261109/{italy-ne-to-austria,austria-to-italy-ne}-native-test-only-v1.json`

## Follow-on acceptance, still required

1. For every eligible source physical road/direction, establish that the original bounded **terminal inventory is complete for road lineage**, not just that all native A terminal GraphIds are accounted for. Retain original source-cut roots not linked within the bounded scope as explicit unverified evidence.
2. For the **287 unmatched source final directed IDs**, document whether the native B path truly cannot continue (mode-specific dead ends, legitimate restrictions, different hierarchy/path context) or the match remains incomplete. Never create a connection from a negative or unresolved record by fiat.
3. For the **21** candidates with conditional B transitions, preserve all proven legal outgoing edges and classify the *other* alternatives as unavailable or unresolved; do not drop them silently.
4. Feed the independently audited test-only catalog into the normal **installed-graph** Android Valhalla executor with pinned directed A and B GraphIds **only through an explicitly test-gated entry point**, retain `productionPublication=BLOCKED`, and collect full-route acceptance. Test original manifest identities, graph activation and exact polygon ownership.
5. Only then define a separate **production-approval catalog contract** and request user authorization to merge/release. There is no permission to silently set the old candidate v1 `samePhysicalRoadVerified=true`, `productionPublication=READY`, or turn the Graph Studio acceptance check green.

No GitHub graph artifact or production APK contains these original local graph tiles, and no private staging data is committed.
