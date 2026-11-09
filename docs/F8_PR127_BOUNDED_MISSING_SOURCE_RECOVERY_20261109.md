# PR #127 — narrowly bounded recovery of missing source final edges

**9 November 2026 — original Valhalla 3.6.3 compiled graph tests; draft/nonpublishing.**

## Goal and strict boundary

The owner explicitly requested **Step 1 only**: start with the 392 original
outward/ambiguous A source-cut observations that did **not** have a final A
GraphId in the previously permitted one-hop view, reconcile them with the
**existing A→exact X→B candidates**, and identify genuinely missing native
source terminal edges. **No new discovery architecture**, full-graph walk,
route preference, road-name/OSM matching, GPS-fabricated crossing point,
second B handoff coordinate Y or catalog publication is allowed.

This increment adds `--bounded-missing-source-recovery` as an optional
extension to the SAME existing `--match-receiver` CLI command in
`tools/extract_f8_region_final_edges.py` — not a new producer. It uses the
unchanged SHA-bound source `--resolve-cut` original 25-km shared-cut evidence
and both existing original graph manifests/indexes/buffer GeoJSON files.
The native Valhalla 3.6.3 C++ reader protocol v8 is unchanged.

The *only* source seeds are original outward-cut roots not already associated
with one of the previous independently proven 505/269 A terminal GraphIds.
Only exact original directed same-node successor GraphIds already recorded
under those roots may be reopened. This source-root audit then reads at most
ONE further original native incident edge per statically permitted
car/motorcycle successor, checks those exact original GraphIds for a real
native terminal at their original compiled end-node, and **STOPS**. No
recursive continuation, no network traversal and no arbitrary depth limit
that could be mistaken for complete source census. Immediate original
shortcuts, hierarchy-peer edges, time/conditional/path-history ambiguities
and all distinct forks are preserved as unresolved; positive native
costing is necessary for candidate lineage but NOT physical-road identity.

For every proposed additional A final:
- Require both exact original native same-node transitions to have native
  allowed vehicle modes; intersect those mode sets with original directed
  access and actual terminal modes. Never imply motorcycle permission from
  a car-only source path or vice versa.
- Independently reread the actual second-hop original A directed edge and
  verify its original GraphId, compiled destination-node identity, GPS,
  layer, bridge, tunnel, road class/use and access against the first-hop
  outgoing native record.
- Independently recompute true **graph-local** terminal vehicle modes from
  all immediate original outgoing and transition-linked hierarchy peers.
  A short or nearby road that still continues in A is never promoted.
- Require exact original X to fall within the SHA-verified receiving B
  original 25-km footprint; add only truly new *GraphIds*. If the candidate
  GraphId is already among the previous verified terminals, add a possible
  cutoff-root association but **do not duplicate** the terminal record.
- Reuse the **existing** A→X→B original B directed-geometry, node identity
  and vehicle-access validation on these additional A candidates. Do not
  automatically accept a B point merely because it is nearby; multiple
  legal B branches remain distinct. Unmatched candidates are retained.

Neither a statically permitted two-edge chain nor a terminal A GraphId
alone proves which physical road/direction the source cut represents. The
results remain explicitly `sourcePhysicalRoadDirectionCompleteness=
NOT_VERIFIED`, Android `NOT_RUN`, and publication `BLOCKED`.

## Results on the original immutable 2026.10.13-1 graph archives

| Actual source A/B result | Italy NE → Austria | Austria → Italy NE |
|---|---:|---:|
| Original A source cutoff roots without a terminal within one native hop | **263** | **129** |
| Unique original first-hop A directed successors reopened (positive native costing only) | 210 | 103 |
| Unique original second-hop A directed successors reopened | 298 | 152 |
| **New original graph-local terminal A GraphIds** (not already in 505/269) | **43** | **16** |
| Original source roots now linked to an existing OR new terminal through two permitted edges | 72 | 35 |
| Remaining original source roots without a bounded two-hop terminal | **191** | **94** |
| Previously verified original A terminal GraphIds | 505 | 269 |
| **New total distinct native A terminal candidates** | **548** | **285** |
| New candidates with at least one native permitted B directed continuation | **2** | **4** |
| Original B directed options on those new source terminals, all preserved | 4 | 6 |
| New + original A candidates with ≥1 B native allowed successor | **259** | **159** |
| Source cutoff roots with a B-native continuation option (lineage still unproven) | 322 | 196 |
| Source cutoff roots with terminal candidate but no proven B outgoing option | 307 | 132 |
| Source cutoff roots with no terminal candidate within these bounds | 191 | 94 |
| Physical-road/direction unique final and completeness | **NOT_VERIFIED** | **NOT_VERIFIED** |
| Android validation / production catalog | NOT_RUN / BLOCKED | NOT_RUN / BLOCKED |

**Totals:** 392 previously missing observations, **59 additional original
A native terminal GraphIds** discovered; 107 formerly uncovered source
observations acquire an association with an existing or new terminal
candidate, and **285 remain**. The 107 are *root observations*, not 107
unique physical roads. The 59 additions are verified original **graph-local
terminal candidates**, not 59 verified cross-region connections.
Six newly found A candidates have a native permitted B continuation (10
original B directed option references). All 774 older A final-candidate
GraphIds, their exact X, original mode permissions, and their prior native
B option identities remain **unchanged**; A source-root coverage references
are appended in memory only when supported by exact compiled topology.
No archived source artifact, prior output, graph file or installed app was
overwritten.

The two-hop audit intentionally does NOT inspect original native continuations
from the remaining 285 observations any further: this would turn a bounded
source check into another road-tracing discovery architecture. Their exact
original source root identities, unverified restrictions/hierarchy and
potential genuine branches remain available for subsequent targeted work,
not silently discarded.

## Local SHA-bound, read-only evidence on Legion

All generated files under
`~/RoadPilotGraphStudio/diagnostics/f8-production/20261109/`:

- `italy-ne-to-austria-missing-root-recovery-v2.json.gz`: SHA-256
  `6b973065d8a3b1a894d16f812565e20909358bb493bf6a72b192272a52bb455e`,
  95,024 bytes, original A graph checksum from source evidence, both
  original graph/25-km buffer/index fingerprints retained.
- `austria-to-italy-ne-missing-root-recovery-v2.json.gz`: SHA-256
  `8f5daa91d7f1565ee1438f1a8bc5e2213a6ba681cc424bc21df1afe8c94b882d`,
  50,206 bytes, corresponding original SHA-bound reverse pair.

Both runs each took ~5.3 seconds (161 MiB / 109 MiB approximate peak RSS).
Native Valhalla 3.6.3 source/receiver original compilations were already
verified in the prior PR milestone; the same pinned native reader and
original archived compiled graphs are reused here. The full Python regression
suite and original B matches were rerun at this head. Tests explicitly prove
no full-graph scan, no two-hop reuse duplicates, mode-specific legal
continuity, and fail-closed original edge-identity checks.

## Exact next gate

Retain these source additions and all 285 unresolved root observations
without publishing. Any further work must be *targeted by actual missing
physical connections* from A→X→B native correlation evidence, not a new
cutoff-wide graph walker. The source completeness and actual same-physical-road
identity invariants remain unproven, and RoadPilot Android JNI real journeys
on this exact immutable graph/catalog are **NOT RUN**. PR #127 remains DRAFT,
UNMERGED, and NONPUBLISHING until independent review, exact-head CI and
explicit owner merge authorization.
