# PR #127 — Independent original-graph physical identity evidence audit (9 Nov 2026)

**Scope:** D-017 original Valhalla 3.6.3 directed final edge A → exact native terminal X → original Graph B directed successor. Read-only verification; no new discovery, GPS nearest-edge substitution, cross-graph GraphId matching, OSM/name heuristics, arbitrary point Y, TripLeg per-connection requirement, branch suppression, production promotion, or merge.

## Implemented and run on Legion

The new tool **tools/audit_f8_physical_road_evidence.py** independently rereads Graph Studio's existing original graph native evidence and blocked candidate/exception catalog. It hashes both original compiled Valhalla TAR archives and compares source/receiver/buffer/index/boundary SHA fingerprints with paired native evidence. For every candidate it verifies:

- Original directed source GraphId, native source end-node identity and exact X unchanged.
- Original B incoming directed predecessor has geometry overlapping A's directed approach at X, with native structure/layer agreement and <=0.75 m approach difference.
- EVERY permitted original B outgoing directed branch belongs to an independently matched predecessor and starts at X, preserves its native Valhalla legal-turn status, original B GraphId, mode access bits, class/use/bridge/tunnel/layer and its descriptive ambiguity category.
- Every eligible original A final edge has exactly one candidate or unresolved exception **and the full set of original final GraphIds is compared with the independent original native bounded tile inventory**, not just self-reported candidate counts. No B alternative is dropped, invented, duplicated, or promoted.
- Original B branch evidence category totals match independently read native alternatives exactly; 12 mutation tests fail closed on changed X, dropped options, fake physical-road approvals, wrong fingerprints, altered attributes, etc.

This tool independently verifies original native evidence previously produced from the **actual compiled Valhalla 3.6.3 graphs**; it does NOT claim to replace that native traversal with a new implementation or to infer roads from GPS proximity.

| Audited property | Italy NE → Austria | Austria → Italy NE | Combined |
|---|---:|---:|---:|
| Original A exterior eligible directed finals | 454 | 253 | **707** |
| Candidate A source directed IDs | 260 | 160 | **420** |
| Unmatched source exception IDs retained | 194 | 93 | **287** |
| Native directed B options preserved | 401 | 245 | **646** |
| Matching native predecessor/successor class/use/structure | 280 | 171 | 451 |
| Class/use changed at original B junction | 90 | 63 | 153 |
| Bridge/tunnel/layer structure changed | 31 | 11 | 42 |
| Options permitted for car and motorcycle | 394 | 240 | 634 |
| Options permitted for motorcycle only | 7 | 5 | 12 |
| Data-integrity, original graph archive SHA | **PASS** | **PASS** | **PASS** |
| **All options same physical road certified** | **NO** | **NO** | **NO** |

Original archive fingerprints actually hashed: Italy NE e6a10d36f8622ac0e47dc3d17a8295f60b144f9a2ad478e1b5f6ef2dbea75953; Austria ee7baac93b639d0c2fefab8f90540d26d03fd28a283c73bff516a1d8bdc2bc7b.

Original native audit output (local, NONPUBLISHING):
~/RoadPilotGraphStudio/diagnostics/f8-production/20261109/{italy-ne-to-austria,austria-to-italy-ne}-physical-road-audit-v1.json.

## Physical-road acceptance STILL BLOCKED

The same original B incoming geometry as A's approach plus a legal original B outgoing turn demonstrates physical junction adjacency, NOT necessarily that each outgoing edge is the *same physical road*. Actual road branches include real ramps and junctions and must remain distinct. Even equal class/use/structure is not by itself a proof of every physical-road identity. **None of 646 options may be promoted merely by this audit**, and none is suppressed.

Before producer physical-road identity can be ACCEPTED, independent evidence must resolve original-source physical-road lineage/completeness across all eligible source road/directions and genuine source/receiver branch relationships (including the 195 changed-attribute options), native/Android acceptance of real cross-region journeys on the same installed archives, and unresolved exception handling. This remains a finite review of the existing D-017 catalog; not an invitation to create a different discovery architecture.

Full independent source native-inventory comparison detects an otherwise self-consistent but incomplete candidate ledger; the exact original source GraphIds in the bounded native census are authoritative.

The PR #127 architecture contract must remain unsatisfied until its remaining real acceptance conditions are proven. Catalog v1 still has physicalRoadIdentityAcceptance=NOT_VERIFIED, productionPublication=BLOCKED, sourceDiscoveryComplete=false, and receiverMatchingComplete=false. Never change these fields or CI to green prematurely.

## Reproduction

Run: python3 -m unittest tests/test_f8_physical_road_evidence_audit.py

Run the audit tool with --catalog, --evidence (original compressed paired native evidence), --from-archive and --to-archive (immutable original compiled Valhalla TARs), and --output. Reverse the directions/archives for Austria → Italy NE.

The committed small test fixture contains real original native records for one A terminal and two B options plus one unresolved exception. Full 707/646/287 verified on Legion against the actual TAR bytes, not by injecting large graph archives into GitHub.

RoadPilot PR #543 separately validates actual extracted/installed compiled tile bytes against these original SHA-bound TARs. Android JNI route success cannot by itself certify physical-road lineage or authorize product publication.

