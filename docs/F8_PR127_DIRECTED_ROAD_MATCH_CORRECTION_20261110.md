# PR #127 — Directed-road match is independent of B outgoing turns

10 November 2026. Original Valhalla 3.6.3. Draft/nonpublishing. D-017 architecture unchanged.

## Contract correction

The accepted *road correspondence* is original A final directed GraphId → exact original endpoint X → original B directed road GraphId that overlaps A's directed approach at X. A road in B does NOT become unmatched because its next B road has no verified outgoing turn at X.

The existing native matcher already produces receiverDirectedCandidatesAtX with oriented original geometry, structural/layer and vehicle access evidence. The existing catalog now adds nativeDirectedRoadMatchesAtX as its PRIMARY record set (one per eligible original A final directed GraphId, all matching original B directed road IDs retained). The historical outgoing-turn connectionCandidates and unresolvedSourceFinalEdges remain separate diagnostics, not a gate on directed road correspondence. A mustNotCreateConnection flag on a historical outgoing-turn exception does not override its independent original B road match.

Each new B road record preserves the original receiving GraphId, X position END_NODE or INTERIOR, allowed A/B vehicle-mode mask, directional approach overlap and native class/use/structure. Wrong-way, grade-separated, unrelated nearby or unproved approaches are rejected. Fingerprints of both original compiled graph archives and the 25-km source/receiver buffers remain unchanged. No name/OSM-way matching, B road succession classification, second GPS coordinate, additional discovery system or exhaustive graph scan has been added.

## Real archive verification

| Pair | Eligible A finals | Primary directed B road matches at X | Missing original B road matches |
|---|---:|---:|---:|
| Italy Nord-Est → Austria | 454 | 454 | 0 |
| Austria → Italy Nord-Est | 253 | 253 | 0 |
| Total | 707 | 707 | 0 |

Original B incoming edge GraphIds were unique for these 707 A finals. The old 420 vs 287 partition was a measure of B outgoing-turn costing: 420 had at least one statically allowed B outgoing option; 287 had none under the checked context. All 287 have a matching original B directed incoming road at X. The 646 legal B outgoing edges and all conditional/unknown mode alternatives remain intact as diagnostics, not as match criteria. The 285 unrelated bounded source-cut root observations do not indicate 285 missing physical roads.

Original archive SHA-256 (Italy NE): e6a10d36f8622ac0e47dc3d17a8295f60b144f9a2ad478e1b5f6ef2dbea75953
Original archive SHA-256 (Austria): ee7baac93b639d0c2fefab8f90540d26d03fd28a283c73bff516a1d8bdc2bc7b

Real locally generated immutable catalog evidence:
- italy-ne-to-austria-directed-road-matches-at-x-20261110-v1.json — SHA-256 c8502685ebce4b7963787b1658aa7518432339a4719a6a92b0a961080dbc5c22
- austria-to-italy-ne-directed-road-matches-at-x-20261110-v1.json — SHA-256 b77d582ddb85c9f693cb60ed8822281a3276f9e23fe70fd97828538b5414d92c
Both saved under ~/RoadPilotGraphStudio/diagnostics/f8-production/20261109/, with independently saved *-direct-road-match-audit-v1.json. Both catalogs pass JSON Schema Draft 2020-12 validation and the independent SHA-bound original TAR audit.

## Acceptance scope and Android integration

These 707 correspondences are **native directed geometry matches** in the bounded original region-pair terminal inventory, not blanket production READY and not proof that a B leg can be started *after* an incoming B edge ending at X. RoadPilot must consume the new primary road match record with correct original graph fingerprints, snap direction and routing context, and test actual end-user A→X→B journeys without backtracking. Android PR #543's existing successor-based test-only adapter does NOT yet consume the new primary field, and the previous v1 test-only artifact remains unchanged.

Physical-road source-cut lineage completeness across all regions and normal Android journey acceptance are separate gates. Publication remains BLOCKED, physical-road overall approval NOT_VERIFIED, PR #127 stays draft/unmerged. The architectural policy must not be made green by checking unproven invariants.
