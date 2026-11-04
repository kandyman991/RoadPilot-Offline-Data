# F8 production reset — one final retained directed edge per physical road and direction

2026-11-04. Architecture contract A1–A3, B1–B4, D1–D4 and decisions D-014/D-018 remain binding.

## Goal and explicit prohibition

The production object is **ONE final original Valhalla directed edge per actual physical road and travel direction** across the 25-km shared overlap. Each direction of a divided motorway, each legitimate ramp and genuinely branching road remains separate. Mode-specific traversability is an attribute of the original directed edge, not a reason to create a duplicate crossing record. Do **not** generate a matrix of intermediate connectors, reconstruct complete source-core-to-destination-core journeys to decide *where* a crossing should be, group by OSM way/name alone or choose the first passing Valhalla route.

Graph Studio should find the unique final retained native edge **first**, then correlate its actual terminal with the receiving graph's original native road and direction, preserve unresolved alternatives, and validate actual Valhalla/Android A→X→B journeys. All source/native evidence must stay available until the actual physical-road equivalence proof is complete.

## Implemented in this narrow PR, based directly on merged main

New isolated, nonpublishing tool: tools/build_native_f8_final_edge_register.py.

- Reads the already verified **complete** 3,623-window native overlap scan and corresponding SHA-bound original graph-local terminal census; no new or modified graph builds.
- Emits exactly **one candidate record per distinct original directed GraphId** irrespective of whether Car, Motorcycle or both modes can travel on it. Different GraphIds are never merged because they share a road name, way ID, geographical proximity or output turn.
- Every record has the original terminal GraphId, native end-node identity, actual terminal GPS, Car/Motorcycle mode set and optional peer-buffer annotation. The scanner GPS is correctly marked an **interior source sample**, not confused with the end node. No per-road multiple intermediate handoff coordinates are invented.
- All original native source edges remain referenced by immutable full-source SHA-256, source counts and explicit nonterminal counts. Mode-stranded nondeadend counts remain unresolved, not silently declared impossible or pruned.
- Fingerprint mismatch, source count/GraphId disagreement, missing census coverage, mode view disagreement, stale native scanner inputs or false completeness claims fail closed. Immutable output creation refuses overwrites.
- Does **not** emit RoadPilot production handoffs or claim that graph-local deadends alone define the last edge of a physical road.

## Real Italy Nord-Est ↔ Austria evidence (original 2026.10.13-1 graphs)

Read-only Legion output:
~/RoadPilotGraphStudio/diagnostics/f8-production/20261104/one-final-directed-edge-candidate-register-v2.json

SHA-256: ebbd3709820fa15f593ac529b45931af4b2924d5f93b73da375f5b00067a167f

An initial read-only v1 report is superseded: it accidentally labeled the
native source-node coordinate as the edge interior sample. v2 explicitly stores
the independent start node, interior point and true terminal positions; no
physical class, road eligibility or graph data was changed.

| Original source | Full directed edges | Distinct graph-local terminal candidates | Car count | Motorcycle count | Mode-stranded nondeadends Car / Motorcycle |
|---|---:|---:|---:|---:|---:|
| Italy Nord-Est | 323,372 | 21,500 | 21,500 | 21,468 | 12,216 / 12,252 |
| Austria | 334,973 | 22,439 | 22,439 | 22,407 | 12,550 / 12,587 |
| Total | 658,345 | 43,939 | 43,939 | 43,875 | counts not unique road classes |

These counts are *not* the number of actual physical roads crossing the border. They contain dead-end/graph-local terminals and may still omit mode-stranded valid last edges. This is one candidate **per GraphId**; global **one per physical road** remains NOT_VERIFIED. Its utility is a stable, duplicate-free final-edge-first input for the next proof.

## Next implementation, not an optional diagnostic digression

1. Establish the true **physical-road/direction → original final directed GraphId** relationship across the 25-km overlap using authoritative native edge topology/geometry and original Valhalla directed evidence. Explicitly reconcile mode-stranded original edges, legitimate separate ramps/branches, and the scan-to-graph hierarchy cases. Keep ambiguous classes marked unresolved instead of suppressing original F8 candidates. Do **not** turn this into exhaustive core-to-core journey enumeration.
2. For each independently proven final directed A edge, match the actual B road at terminal X, allowing B to split the same physical road into different original directed edges. Require direction/mode and true Valhalla legality; do not demand equal numeric GraphIds across regions.
3. Then perform A→X→B real journey tests, original route cost comparison (FASTER/SHORTER) and Android JNI parity with exactly identical retained graphs. Preserve fallback/rollback; no release or producer until proof gates pass.

**Status:** global physical-road uniqueness NOT_VERIFIED; actual legal crossing NOT_VERIFIED; Android full-route parity NOT_VERIFIED; publication BLOCKED. The previous stacked diagnostic PRs #119/#120 remain independently open and are not dependencies of this producer.
