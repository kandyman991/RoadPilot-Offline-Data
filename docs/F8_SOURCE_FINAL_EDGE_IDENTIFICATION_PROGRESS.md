# F8 — original source-graph final directed-edge identification progress

**Date:** 2026-11-04. **Base:** merged Graph Studio PR #121, main
`d8fc29bc5bfff59fbb0e297e05fa9111f31ae8bb`.

## Binding, owner-approved production model

**ONE final original Valhalla directed edge for each actual physical road and
travel direction reaching the 25-km retained overlap.** Keep independent
carriageways, ramps, forks and mode restrictions; two vehicle modes sharing
one original GraphId are one record. Do not invent repeated intermediate
crossing points or a matrix. Do not select one path because a route succeeds
first. Never use OSM way/name, geographic proximity or graph-local GraphId
equality across independent regional graphs as proof of road equivalence.

All work here is on the **original source graph only**; receiving-graph
correlation and A→X→B are **NOT_STARTED**. Old diagnostic PRs #119/#120
are not production dependencies and have not been merged in this work.

## Original native graphs and scope

- Italy Nord-Est, Austria, retained routing packages `2026.10.13-1`,
  original Valhalla **3.6.3**.
- The 3,623-window source scan reconciles **658,345** exact native original
  directed GraphIds (Italy **323,372**; Austria **334,973**).
- The verified original build's **25-km buffer polygon SHA** is pinned
  independently of geographic intuition. The native directed edge's
  *full original geometry*, not its interior GPS sample, defines observed
  source-cut intersections.
- Original reports, graph archives and full source scans have not been
  changed. There is no production connectivity sidecar or Android update.

## New data-integrity and source-first implementation

1. Exhaustive native topology census now retains IDs, not merely totals, for
   **every mode-stranded, non-dead-end** source edge. Existing ordinary
   graph-local terminal rows are unchanged. New immutable report:
   `full-native-census-mode-stranded-ids-v4.json`,
   SHA-256 `266ed23499c537037813e3d138166da8cd2534ee6bc8c671ba76faa270b58b66`.
2. The final-directed-edge candidate register combines Car and Motorcycle
   modes **by original directed GraphId only**. Retained: **68,784** original
   unique native mode-stop GraphIds, Italy **33,755**, Austria **35,029**.
   Each mode-stranded ID remains an unresolved *native* candidate, not a
   certified physical road ending. Immutable
   `one-final-native-mode-stop-candidate-register-v3.json`,
   SHA-256 `dd358ee381b63bcfc680acbb67609e54052e1faea0ffd3973389d6225e973129`.
3. Original native end-node **hierarchy** verifier validates actual reachable
   source GraphReader transition paths (zero-length, mode-dependent) and
   retains every original branch. It also computes the source directed
   polyline's actual intersection with the SHA-bound original 25-km cut.
   Among 68,784 IDs: **44,398** have no additional mode-accessible
   hierarchy outgoing edge and **24,386** have unresolved accessible
   alternatives. These are *source-local classifications*, **not** physical
   road equivalence classes.
   Immutable `one-final-original-source-hierarchy-and-cut-v2.json`,
   SHA-256 `83f6d02f62fa4934349fccde1158a874b14dad07e2576aeed49b16815e6dda91`.
4. Of those, **251** original final directed-edge geometries intersect
   the source 25-km boundary directly: **177** Italy, **74** Austria.
   Across **both Car and Motorcycle modes**, **502/502** short local
   original Valhalla route probes exactly match their nominated
   final **original TripLeg directed GraphId**. The 3.4m Austria final
   edge requires a true original immediate source predecessor route.
   No hierarchy ambiguity is a route eligibility filter: **84**
   mode-specific alternatives remain explicitly unresolved even where
   the original last TripLeg ID is verified.
   Immutable `one-final-original-source-cut-last-tripleg-allmodes-v4.json`,
   SHA-256 `d9d86030c6a07c7d5c31bbeff5ae3cfcaeb291eae23688ade615dd92a4dcab2c`.
5. **Important missed-road correction:** **49** *additional* original
   mode-stop final directed edges lie wholly beyond the source cut. The
   final segment's geometry does not itself intersect the boundary, so a
   direct-final-shape-only inventory would silently omit them. The
   independent read-only source-only investigation found a real
   cut-intersecting original predecessor within one edge for **46/49**
   and within two predecessor edges for the remaining **3/49**. Keep
   every incoming branch; prove the precise original predecessor chain
   and final original TripLeg identity rather than grouping by way ID.

6. **49/49 beyond-cut original directed final edges** have at least one
   native same-level original predecessor chain intersecting the verified
   source cut: 46 within one predecessor edge, three within two. Original
   Valhalla short local route proof has at least one exact original final
   TripLeg GraphId for both Car and Motorcycle on each of the 49. Across
   *all* original predecessor branches, **206** individual route-mode checks
   matched the exact original entire cut-to-last directed path; ten
   individual route-mode checks were inconclusive and twelve upstream
   individual branch-mode attempts were inaccessible. Every incoming branch
   observation is retained; these are not suppressed alternatives. Two
   candidates additionally have unrelated explored branches that hit the
   explicitly bounded depth limit; source physical road completeness remains
   unverified. Immutable report
   `one-final-original-source-beyond-cut-v1.json`, SHA-256
   `4012fe7f90d89865fbd73d14f32f9ed1f36358cd2019d1dd2bf4b8d7dc836ba0`.

Combining (4) and (6), **300 distinct original source final GraphIds**
(251 whose own shape intersects the source cut, 49 beyond-cut with a
crossing predecessor path) each have successful original local TripLeg
last-edge proof for **both** vehicle modes: **600/600 source-edge/mode
pairs** in this *observed, bounded source-cut class*. These are **not**
300 globally established real physical road/direction equivalence classes,
and other native modes and unvisited/unverified road chains have not been
silently certified or excluded.

## Gates not closed / remaining work before B correlation

**GLOBAL PHYSICAL-ROAD COMPLETENESS AND UNIQUENESS REMAIN NOT_VERIFIED.**
A terminal GraphId is not inherently a distinct physical road. A same-way
or same-coordinate observation is not equivalence. Source cut coverage in
the 25-km graph-build polygon does not by itself prove that all roads
crossing the specifically intended bilateral frontier are represented;
unbuffered cores are annotations, not source-authoritative construction
fingerprints. Native hierarchy alternative states, beyond-cut source
subdivisions, short edges, physical road branches and dual-mode legality
must be reconciled in one exhaustive graph-native per-road/direction
source inventory, without suppressing unresolved F8 alternatives.

**Do not begin receiving B graph matching** while this global gate is open.
Do not declare actual cross-region legality, FASTER/SHORTER optimality,
Android JNI parity or production publication. Issues Graph Studio
#73/#82 and Android #512 remain OPEN. Release is BLOCKED.

## Source-side developer verification

- Original source evidence is SHA-bound; any missing, reordered, mutated
  native end-node/hierarchy rows must fail the entire run.
- Original source geometry and all source predecessor graph transitions
  are native GraphReader edge IDs, without matching numeric IDs to B.
- New regressions cover negative source count, missing mode-stranded IDs,
  mode union, disconnected hierarchy, false native edges, multi-branch
  source predecessor exploration, original short-edge predecessor
  TripLeg proof and fail-closed truncation.
- All source-side complete inventories stay immutable; newly generated
  diagnostic evidence is written to new files, never rewritten.

**Unchanged:** retired OSM-first crossing producer, regional connector
matrix, old bounded planner remain retired. No graph .gph modification,
Android routing runtime change or new crossing sidecar is authorized.
