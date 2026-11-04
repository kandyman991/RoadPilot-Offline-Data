# M6b — Actual F8 A-last / B-first directed route evidence

**Status:** read-only diagnostic implementation with real-graph evidence;
no production connectivity package, graph archive, Android or publisher
changes. This milestone advances the native F8 **last-edge / 25-km-overlap**
architecture without resurrecting any OSM sampler, candidate-pair/matrix
producer or hard portal. PR #112 (M6a) is merged.

## Why M6b differs from M5/M6a

M5 used nominated A/B directed graph IDs, and the real Italy→Austria
journeys did not use the proposed A terminal. M6a then validated the
topology, geometry and local Valhalla traces of nominated B edge chains.
Neither proved that a real A-origin-to-B-destination journey actually
used those A and B edges.

**M6b now traces the exact A-last and B-first directed GraphIds used by
Valhalla for a complete F8 two-leg journey.** It begins with the original
validated-hash **native GPS proposal stream** and probes selected existing
candidate IDs, rather than fabricating new crossing identities.

## Diagnostic: tools/probe_native_f8_actual_journey.py

1. Verify original Graph Studio F8 GPS proposal manifest and the complete
   compressed candidate-file SHA-256. Check exact graph package fingerprints
   and both neighbour-boundary identities before routing.
2. Select **explicit existing native GPS proposal IDs** (1–8 per diagnostic),
   preserving original stream count. Never select just one per road/ref, never
   treat the bounded selection as exhaustive, and never exclude unprobed
   crossings. No new production artifact is written.
3. Route origin→proposal X in Graph A, normalize X to Graph A's **actual**
   Valhalla endpoint, then route actual X→destination on independent Graph B.
   Check first/final route endpoints, F8's 25 m route-local tolerance,
   destination arrival and complete two-leg Valhalla distance/time.
4. Trace **actual** directed edge IDs from both returned Valhalla leg
   geometries: actual last Graph A edge and actual first Graph B edge.
   Compare B's first edge with the candidate's original Graph B ID.
   Trace identities are **scoped to their own graph fingerprints**;
   never compare numeric GraphIds across the independent archives.
5. Independently extract the *actual* two directed native geometries with
   pinned Valhalla 3.6.3 GraphReader. Check native forward vehicle mode access,
   calculate each local edge's handoff projection, geometric gap and directed
   tangents. Co-location is an observation, **not** proof of cross-graph
   physical transfer or legal turn. Native/trace identity mismatch fails closed.
6. Distinguish `aLastEdgeMeaning=ACTUAL_LAST_DIRECTED_EDGE_OF_THIS_A_ROUTE_ONLY`
   from `sourceRoadFinalEdgeIdentity=NOT_VERIFIED_BY_SELECTED_LEG`.
   Report metres remaining from handoff to **the end of that A directed
   edge**, plus the Valhalla native `deadend` flag, with no inference that
   the route's last edge is the final retained road edge 25 km inside the
   neighbour graph.
7. Failures, other traced B entry, missing geometry or invalid mode are
   scoped to this selected journey; no unsuccessful proposal eliminates
   a road, receiver alternative, direction or position.

Every report retains `crossGraphPhysicalContinuity=NOT_VERIFIED`,
`crossSeamTurnLegality=NOT_VERIFIED`,
`sourceDiscoveryCoverage=NOT_VERIFIED`,
`androidF8Parity=NOT_VERIFIED`, `wholeJourneyOptimality=NOT_VERIFIED`
and `productionPublication=BLOCKED`.

## Real graph results — 2026-11-04

Validated against **the same immutable 2026.10.13-1** Italy Nord-Est
and Austria Valhalla 3.6.3 packages and boundary fingerprints. A new
route is calculated by Valhalla for every selected candidate/mode;
the historical native journey JSON is used only to identify worthwhile
existing native proposal IDs to test, **not** as a substitute for a
fresh route or trace.

Original candidate streams contain **334,973** GPS proposals in
Italy→Austria direction and **323,372** in Austria→Italy direction.
M6b probes **3 distinct original candidates** for each of Car and
Motorcycle in each direction, **12 selected candidate/mode results**
total. It never suppresses or ranks away the remaining proposals.

| Direction | Mode | A actual last directed edges | Graph B actual first directed edges | Route-local directed trace / arrival / native geometry |
| --- | --- | --- | --- | --- |
| Italy→Austria | Car | `536441000506`, `1442471870473`, `576605655610` | `542514352698`, `404465516553`, `568921690682` | 3/3 matched |
| Italy→Austria | Motorcycle | same three | same three | 3/3 matched |
| Austria→Italy | Car | `536441000506`, `403425329161`, `576605655610` | `542514352698`, `1443512057865`, `568921690682` | 3/3 matched |
| Austria→Italy | Motorcycle | same three | same three | 3/3 matched |

For all 12, the actual A leg endpoint and actual B starting coordinate
are co-located (recorded 0.0 m after polyline6 rounding); the B first
traced edge matches the native GPS proposal, and actual A-last/B-first
geometries are within 1 m of the handoff. Arrival is verified at the
requested destination. These are **real F8 two-leg graph-local observations**,
not new production crossings or proof that there is a cross-graph edge.

### Important unresolved final-edge requirement

The selected actual A-last edges were **not** proven to be the *final
retained edge of their physical roads* inside the 25-km overlap:

- The actual route handoff point is **13.100 m**, **27.097 m** or
  **65.573 m** before the end of the corresponding A directed edge.
- Each of those native A edges reports `deadend=false`.
- Accordingly all twelve reports explicitly retain
  `sourceRoadFinalEdgeIdentity=NOT_VERIFIED_BY_SELECTED_LEG`.

This is a **critical limitation**, not a newly proposed hard filter:
the demonstrated route-local handoffs cannot be silently substituted
for the owner's intended final-road-edge F8-native catalog. That next
proof must identify authentic final retained road-edge termini, confirm
25-km overlap coverage and verify a full journey using that same
terminal, without reconstructing multiple candidate edges for the
same physical road.

## Reproduction

For one original Italy→Austria motorcycle GPS proposal:

~~~bash
P="$HOME/RoadPilotGraphStudio"
ROOT="$P/f8-native/italy-nord-est__austria/e6a10d36f-ee7baac93-43d085-958523"
PATH="$HOME/.cache/app.roadpilot.graphstudio/python-env/bin:$PATH" python \
  tools/probe_native_f8_actual_journey.py \
  --pair "$ROOT/pair.json" \
  --proposal-dir "$ROOT/gps-proposals" \
  --from-manifest "$P/builds/italy-nord-est/italy-nord-est-routing-2026.10.13-1-manifest.json" \
  --to-manifest "$P/builds/austria/austria-routing-2026.10.13-1-manifest.json" \
  --native-endpoints-binary "$P/diagnostics/m6/pr112-review/native-build-20261104/build/native_f8_directed_endpoints" \
  --direction from-to --mode motorcycle \
  --candidate-id nf8gps-787b30fb74b5ff363d16e61d \
  --start-lat 46.501885 --start-lng 13.592668 \
  --end-lat 46.592234 --end-lng 13.846448
~~~

Raw results and SHA256SUMS are **outside Git**, preserved at
`~/RoadPilotGraphStudio/diagnostics/m6/20261104/m6b-actual-journeys-v2/`.
M6b's Python test suite is also invoked by the F8 architecture-contract
workflow. No native extractor modification was necessary after PR #112,
which already built the pinned 3.6.3 executable and archived build hashes.

## Next gate

**M6c: authentic F8 terminal source.** Identify the exact last
retained road edge and its directed endpoint within the approved
buffer/overlap architecture, then verify that the *actual* first graph
leg ends on **that nominated final terminal edge** and the B leg
continues legally at that handoff to the requested destination.
Preserve every alternative road/crossing as distinct and all
unknown/inconclusive evidence. Only after this scope is complete
should Android JNI parity, completeness, precomputed publication,
and Android #512 ingestion be considered.
