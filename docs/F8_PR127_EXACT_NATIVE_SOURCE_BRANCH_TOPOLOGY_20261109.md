# PR #127 — original source-only native branch/topology classification

**9 November 2026; draft, unmerged, nonpublishing; D-017 unchanged.** This is
one additional analysis of the existing pair-scoped original Graph A native
terminal-first evidence, not a new discovery system. It does not use Graph B
compiled directed roads, create another handoff coordinate, route complete
journeys, walk beyond the existing single immediate successor, scan whole
graph archives, or select a road by heading/name/way/nearest coordinate.

## Native source identity and geometry rules

The existing native Valhalla 3.6.3 `--local-continuations` reader now reports
`fromNodeGraphId` — the **exact original A node GraphId owning each outgoing
directed edge** — alongside the oriented original compiled source/next-edge
shape (`departure` is the first distinct point of the original directed
edge), original outgoing `endNodeGraphId`, road class/use, bridge/tunnel/layer,
and the native car/motorcycle immediate `Allowed()` result. Protocol is now
`roadpilot.f8-native-source-7`, fail-closed on older native binaries.

The source-only Python stage verifies any direct outgoing native from-node
GraphId equals the precise incoming original A end-node GraphId; no GPS
proximity can replace this exact node topology. For every already selected
nonterminal source root **and each vehicle mode independently**:

- `SINGLE_STATIC_LEGAL_CONTINUATION`: exactly one native immediate same-node
  legal outgoing GraphId and **no unknown options** in this bounded context.
  This is structural **immediate routability only**, not a proof that the
  next edge is the same named/physical road or the final edge.
- `SINGLE_ALLOWED_WITH_UNKNOWN_ALTERNATIVES`: one immediate native positive,
  plus hierarchy, shortcut, conditional/complex or time/path-history
  alternatives whose legal status cannot be certified from one node. ALL
  alternatives remain preserved.
- `DISTINCT_NATIVE_GEOMETRIC_BRANCHES`: two or more positive immediate
  original A directed edges **share the exact native from-node**, have
  pairwise different original directed first-departure geometry **and**
  distinct original end-node GraphIds. This certifies *local geometrically
  diverging native directed branches*, not which branch continues the
  incoming physical road, and never chooses the straightest or preferred.
- `MULTIPLE_ALLOWED_OVERLAPPING_OR_UNKNOWN_GEOMETRY`: two or more positive
  edges but departure geometry or directed end-node identity is duplicated,
  missing or otherwise inadequate to prove divergence. Keep all as
  ambiguous — never deduplicate by endpoint/OSM metadata or assume hierarchy
  equivalence.
- `NO_CONFIRMED_WITH_UNKNOWN_ALTERNATIVES` and
  `NO_CONFIRMED_STATIC_CONTINUATION`: neither establishes an actual final
  physical road; lack of a positive default one-step route is not a proof of
  road termination, especially when unknown alternatives exist.

Original `sourceOriginalNativeApproach` is retained as *geometry evidence*,
not a score for choosing the most straight-looking continuation. Each
outgoing GraphId retains its exact native owning node, directed end-node,
initial departure, road class/use, bridge/tunnel/layer and original mode
access. Where multiple branches differ in class or road use, those native
attributes further explain the alternatives, but do **not** select one or
suppress genuine ramps. No route ordering/pruning or graph-by-name merging
is introduced. Every root retains `physicalRoadIdentity=NOT_VERIFIED` and
any original final-candidate GraphId retains
`physicalRoadFinalCompleteness=NOT_VERIFIED`.

The **entire original branch set** remains stored regardless of classification.
Identical native outgoing GraphIds cannot be repeated, and original A
`fromNodeGraphId`, X, directed departure and access evidence fail closed on
invalid values or inconsistent direct-node identity. No new original source
cut roots are generated, no cut edge or candidate is removed. Format for
paired source evidence is **nonpublishing schema version 5**.

## Real source Valhalla 3.6.3 evidence (original archive version 2026.10.13-1)

These data result from the identical, region-independent algorithm on the
SHA-verified **source Graph A** pair-specific 25-km shared outer cutoff.
The original Graph B 25-km footprint is used **only to select the A cutoff**,
not to inspect or pair any Graph B native directed edge.

| Mode-specific original source property | Italy NE → Austria | Austria → Italy NE |
|---|---:|---:|
| Pair-cut original A source tiles (+ immediate ring) | 72 | 60 |
| Outward/ambiguous original source roots read back | 820 | 422 |
| Native terminal candidate GraphIds independently checked (unchanged) | 505 | 269 |
| Native nonterminal source roots, no losses | **439** | **211** |
| Exactly one positive direct native outgoing; no unknowns | **121** | **71** |
| One positive native outgoing plus unknown alternatives | **25** | **8** |
| Two or more **native geometrically divergent** legal branches | **188** | **84** |
| No confirmed immediately legal continuation, with unknown alternatives | **105** | **48** |
| Branch cases with varying native original road use | 21 | 16 |
| Branch cases with varying native original road class | 19 | 16 |
| Different or overlapping geometry among the multiple positive branches | **0** ambiguous | **0** ambiguous |
| Fully identified final edge per distinct physical road/direction | **NOT_VERIFIED** | **NOT_VERIFIED** |
| B native matching / Android A→X→B / production publication | NOT_STARTED / NOT_RUN / BLOCKED | NOT_STARTED / NOT_RUN / BLOCKED |

*Counts apply to car and motorcycle independently; on these specific
archives the two vehicle-mode distributions happened to be equal. Different
original regions and modes are processed independently. The 188 and 84
branches are **roots**, not the number of distinct physical roads; some
roots have three outgoing branches. Multiple positive native branches are
not equivalent to multiple proven cross-region handoffs. The unique
immediate successor and local terminal observations likewise cannot by
themselves establish that every physical road/direction has been found.*

For example, original Italy NE source GraphId `1382016322` has two different
allowed directed original successors, `1482679618` and `1549788482`, with
different native end nodes, different departure shape points and original
road use/class (0/6 versus 3/7). The original Austrian example
`3999261962` also shows distinct native road use/class and end nodes for its
original successors `2891965706` and `2925520138`. Both alternatives
remain candidates; neither is arbitrarily labeled "the road continuation".
These are example data from actual original native source graphs only.

## Immutable source evidence

Retained on Legion under
`~/RoadPilotGraphStudio/diagnostics/f8-production/20261109/`, both output
files are nonpublishing and do **not** modify the underlying graph packs:

- `italy-ne-to-austria-branch-topology-v2.json.gz`
  SHA-256 `2ad9f3851cf568615352aa42b45346783f6fed491ab2d0f8f57f08938f364b15`,
  134,368 bytes, 3.89 seconds, 225,892 KiB peak RSS;
  original A archive fingerprint
  `sha256:e6a10d36f8622ac0e47dc3d17a8295f60b144f9a2ad478e1b5f6ef2dbea75953`.
- `austria-to-italy-ne-branch-topology-v2.json.gz`
  SHA-256 `3358cac1d8983e83ebe2629b7f8cc89cbcaf5fcf4ffb51fc094c484312e7a008`,
  68,095 bytes, 4.44 seconds, 211,516 KiB peak RSS;
  original A archive fingerprint
  `sha256:ee7baac93b639d0c2fefab8f90540d26d03fd28a283c73bff516a1d8bdc2bc7b`.

A complete comparison against the previous independently source-verified
v4 output confirms **identical original source-cut root GraphId ordering,
identical terminal-candidate GraphIds and permissions (505/269), and
identical immediate outgoing GraphIds and original native costing statuses**.
Only the extra exact native topology/geometry classification and provenance
are new. Source-only native C++ Release compilation and all **411 Python
tests** passed on Legion; the new regressions verify exact-node identity,
mode-dependent forks, ambiguous overlapping geometry, multiple distinct
one-hop terminal successors, protocol checks and fail-closed tampering.

## Remaining source-only work and stop conditions

This increment does **not** establish "which branch is the same physical
road" at a true split. A Valhalla-legal turn, a straight-looking shape,
matching road class or the existence of a single outgoing edge are NOT
sufficient to certify same physical-road identity. The 188/84 real fork
observations are legitimate divergent directed alternatives and cannot be
silently collapsed; additional unresolved hierarchy/conditional options
remain deliberately unproved. We must still establish **source-side
physical-road/direction lineage AND completeness** from authoritative
native edge identity without an unbounded graph walk, and keep any genuine
ambiguity explicit.

No release, production publication, PR merge, Graph B directed matching or
Android parity claim is permitted from these results. PR #127 stays DRAFT
pending independent review, exact-head CI and explicit owner merge approval.
