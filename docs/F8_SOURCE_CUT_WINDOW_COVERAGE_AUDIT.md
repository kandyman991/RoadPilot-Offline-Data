# F8 original source cut — overlap-window coverage audit (PR #122)

Date: 2026-11-04. Scope: read-only **original source graphs only**,
Italy Nord-Est / Austria, Valhalla 3.6.3, routing packages `2026.10.13-1`.
Base: merged PR #121; development branch PR #122. This is **NOT a complete
physical-road inventory**, receiver correlation or a publishable seam.

## What the interrupted session finished

Recovered two uncommitted implementation/test files on the Legion:
`tools/census_native_f8_original_source_cut_edges.py` and
`tests/test_native_f8_original_source_cut_census.py`. The extractor
reads **every GraphId retained in the complete 3,623-window original
overlap scan**, obtains each original native full directed geometry,
intersects the source's **SHA-verified own graph-build 25-km buffer cut**
and records direction without omitting any captured ID for road name,
OSM way, GPS proximity, mode, or first-success. It is NOT a scan of every
GraphReader tile in the entire original graph archive.

Already existing, immutable Legion evidence:
`~/RoadPilotGraphStudio/diagnostics/f8-production/20261104/all-original-directed-source-cut-census-v3.json`;
SHA-256 `a222a7bfd463d331a125b0e420c6c570cdf8d42431a8ba87536341aaa08d8d46`.
Version 2 is byte-identical; version 1 was a preceding differently shaped
forensic audit, not silently substituted for the canonical v3 record.

| Direction (original graph) | Window-scan original directed IDs | Source-buffer cut observations |
|---|---:|---:|
| Italy Nord-Est → Austria | 323,372 | 593 |
| Austria → Italy Nord-Est | 334,973 | 287 |
| **Total** | **658,345** | **880** |

These are geometrical cut observations on original directed GraphIds, not
880 certified physical roads or valid handoffs. Both-end-inside and
both-end-outside intersection classes remain explicit.

## New fail-closed reconciliation

`tools/reconcile_native_f8_source_cut_coverage.py` pins input reports
and compares the untouched v3 cut census against the original Valhalla
TripLeg last-edge proofs and every beyond-cut predecessor path from PR #122.
It checks exact same-source GraphIds, matching original graph manifests,
native executable, fingerprints and mode-specific TripLeg identity.
Missing previously verified direct-final cut GraphIds, duplicates,
incorrect predecessor-path endpoints or mutated inputs are hard failures.
The native original-graph predecessor topology itself is provided by the
preexisting SHA-pinned branch-evidence report; this reconciliation does
not claim independently to recompute native adjacency.

Immutable evidence:
`~/RoadPilotGraphStudio/diagnostics/f8-production/20261104/source-cut-coverage-reconciliation-v1.json`;
SHA-256 `652c3efe77ebf3d60ae3e7be24e7d454279ba5b91ac5c6225d97596db3e68ecf`.

| Original source | Proved direct final IDs at cut | Beyond-cut final IDs | Cut IDs linked to known direct/predecessor witness | Unlinked window cut IDs | Source-cut predecessor IDs absent from window scan |
|---|---:|---:|---:|---:|---:|
| Italy Nord-Est | 177 | 33 | 237 | 356 | 18 |
| Austria | 74 | 16 | 94 | 193 | 16 |
| **Total** | **251** | **49** | **331** | **549** | **34** |

The 34 exact native predecessor GraphIds genuinely occur in the
SHA-bound original beyond-cut route evidence, but were **not present**
in the 658,345-ID common-overlap window scan. It is wrong to say that
the latter exhausts all original graph archive road edges intersecting
the source's own buffer cut. They must be retained as a concrete
coverage deficit, not silently treated as rejected roads. The 549
unlinked cut observations include inward/outward/ambiguous/otherwise
unresolved segments; **159 are outward** (98 Italy and 61 Austria).
None is automatically an eligible final physical-road edge.

Two beyond-cut candidates still have depth-bounded unresolved predecessor
branches. A successful route for one candidate does not exclude its
other native alternatives. All candidate GraphIds remain graph-local,
and each region's numeric GraphId namespace remains independent.

## Production gate before receiving-B correlation

1. Enumerate every original **native graph tile and directed road edge**
   from the SHA-verified graph archives, e.g. GraphReader `GetTileSet()`,
   instead of treating only the complete overlap-window capture as
   complete full-archive coverage. Prove where the 34 known missing IDs
   live; preserve all newly discovered cut roads. Narrow the actual
   bilateral overlap with authoritative original boundary provenance,
   not arbitrary geographical/OSM proximity prefilters.
2. For each original directed physical-road branch and travel direction,
   follow graph-native ordered continuations/hierarchy to its **one
   last retained original directed edge**, keeping independent
   ramps, carriageways, mode restrictions and ambiguous links.
   Reconcile all observed cut IDs against that inventory without
   declaring unrelated or incoming edges to be a crossing.
3. Verify original Valhalla last TripLeg identities and exhaust each
   branch/mode without first-success exclusion. **Only after the
   physical-road/direction uniqueness and coverage gate is proved**
   begin receiving-B graph correlation, legal A→X→B journeys,
   Android JNI parity and eventual release review.

No graph archives, graph tiles, producer or Android runtime changed.
Graph Studio issues #73/#82 and RoadPilot issue #512 remain open.
Global physical-road completeness **NOT_VERIFIED**.
Receiving graph correlation **NOT_STARTED**.
Production publication **BLOCKED**.
