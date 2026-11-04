# M6c / Phase A — Native graph-local terminal and receiving-road evidence

**Status:** First implemented M6c increment, read-only diagnostic only.
Not a production F8 handoff inventory, route-edge certificate, peer-graph
join, Android integration, installer, or routing-archive mutation.
The final physical-road-edge architecture within the approved 25-km overlap
remains binding but **has not yet been fully proven**.

## Problem M6b exposed

M6b measured valid two-leg Valhalla routes that ended 13–66 metres
*before the end of their route-shape-replayed directed Graph A edges*.
Even a perfect route trace would have shown only the last edge of a
particular chosen route, not necessarily the **final retained edge of
that physical road inside the 25-km overlap**. Furthermore, replaying a
route polyline through `trace_attributes(shape_match=edge_walk)` does
not independently establish the original route-service edge IDs.

M6c therefore starts from the **Graph A native end-node and its complete
outgoing directed-edge inventory**, not from the last edge of a chosen
route or from name/OSM-way correlations.

## Implementation

`tools/probe_native_f8_clipped_terminal.py` takes 1–8 explicitly selected
Graph A directed GraphIds. On every exact graph pair, direction and vehicle
mode, it:

1. Verifies both **immutable 2026.10.13-1 graph fingerprints** and
   neighbour-boundary identities. Validates the actual **25.0 km** source
   and neighbour buffer polygons against their own routing manifest
   `source.bufferGeoJsonSha256`. Neither an arbitrary buffer nor a
   different native binary can substitute for the originals.
2. Pins the native extractor to the compiled Valhalla 3.6.3 SHA-256
   `14455ad673c464c3715f2e0b96adfa3aa1f1ecf2a99d347f59920a6a9cc91c6f`,
   using the already-reviewed M6a native build evidence.
3. Extracts the full source directed edge geometry, real `deadend`
   flag, native end node, **all outgoing edges and true outgoing degree**.
   Validates every graph-local identity, access mask and opposing reverse.
   Reports all nonreverse forward mode-accessible road branches; no one
   is silently removed.
4. Reports a **graph-local mode terminal** when the native source edge
   has `deadend=true`, supports the requested mode and has no other
   forward mode-accessible ordinary road edge at that end node.
   This is evidence of how the *source graph* terminates; not proof of
   the physical road's overall final edge.
5. Measures metres to the own retained-buffer polygon outline and
   whether the endpoint is inside the exact neighbour 25-km buffer.
   **Boundary proximity is never an eligibility filter.** A real A22
   source graph terminal was 982 m from the sampled outline, but had
   legitimate B receiving-edge observations and local routes. Arbitrary
   200 m thresholds cannot silently discard it.
6. Calls actual Valhalla 3.6.3 `locate` in **independent Graph B** at the
   source endpoint. Returns every native B directed identity reported
   within the explicitly scoped radius (default 25 m), including reverse
   and inaccessible alternatives. Re-extracts each B native geometry,
   checks identity and measures forward distance remaining.
7. Where that *one* B native edge offers enough local length and mode
   access, requests an A-local route ending on the nominated source
   native endpoint, then a B-local route departing the normalized A
   arrival to a point further on B. Checks route endpoints and costs.
   Other B directions are recorded as **NOT_ATTEMPTED**, not discarded.
   A successful pair of route legs never proves the original route-edge
   identities or a legally traversable cross-graph turn.
8. Every result marks receiver discovery `NOT_VERIFIED_RADIUS_ONLY`,
   physical road continuity, legal seam transfer, complete F8
   discovery, Android JNI parity and production as **NOT_VERIFIED/BLOCKED**.
   A missing B route/geometry is never interpreted as global rejection.

This tool does **not** import retired OSM anchor sampling,
`roadpilot.runtime-connectivity`, connector matrices, or a
name/ref-based road key. GraphIds are interpreted only inside their
own source graph fingerprints.

## Real source-graph results, November 4, 2026

This experiment uses the existing retained Italy Nord-Est/Austria
2026.10.13-1 routing packages and their manifest-bound 25-km buffer
polygons. Five **nominated native source-terminal IDs** were investigated
for both Car and Motorcycle, in both travel directions (10 mode-specific
source observations). The initial IDs came from earlier scratch
*graph-native terminal* diagnostics and are not a complete census.

| Direction | Source road annotation | Graph A directed ID | Distance to own buffer outline | Graph-local mode terminal |
| --- | --- | --- | ---: | --- |
| Italy→Austria | A13 | 364870918424 | 4.0 m | yes, both modes |
| Italy→Austria | A2 | 77309436192 | 89.6 m | yes, both modes |
| Italy→Austria | A2 | 954791387424 | 22.9 m | yes, both modes |
| Austria→Italy | A22 | 2670664376600 | 982.2 m | yes, both modes |
| Austria→Italy | A23 | 5417061081376 | 168.2 m | yes, both modes |

**All five** nominated A native end nodes report no forward
Car/Motorcycle-accessible road continuation besides the opposing
reverse; every endpoint is contained in the peer's manifest-bound
25-km buffer. (Some nodes contain additional native edges without
Car/Motorcycle access; these are retained and reported, not suppressed.)

For each source/mode, Valhalla B locate reported **two directed
receiver candidates**: 20 source/mode-specific B observations total.
Ten selected B forward directions completed the two-leg **local route**
probe; ten other returned B directions were retained with
`NOT_ATTEMPTED_SHORT_OR_INACCESSIBLE_LOCAL_LEG`. No positive result
certifies seam legality or the true physical road lineage. No
F8-wide crossing inventory or global FASTER/SHORTER choice was made.

## Reproduction and evidence

Run from the M6c branch with the installed read-only binaries:

~~~bash
P="$HOME/RoadPilotGraphStudio"
PATH="$HOME/.cache/app.roadpilot.graphstudio/python-env/bin:$PATH" python \
  tools/probe_native_f8_clipped_terminal.py \
  --pair "$P/f8-native/italy-nord-est__austria/e6a10d36f-ee7baac93-43d085-958523/pair.json" \
  --from-manifest "$P/builds/italy-nord-est/italy-nord-est-routing-2026.10.13-1-manifest.json" \
  --to-manifest "$P/builds/austria/austria-routing-2026.10.13-1-manifest.json" \
  --from-buffer "$P/work/italy-nord-est/build/buffer.geojson" \
  --to-buffer "$P/work/austria/build/buffer.geojson" \
  --native-endpoints-binary "$P/diagnostics/m6/pr112-review/native-build-20261104/build/native_f8_directed_endpoints" \
  --direction from-to --mode auto \
  --source-graph-id 364870918424 --source-graph-id 77309436192
~~~

Unpublished raw reports with checksums live **outside Git** at
`~/RoadPilotGraphStudio/diagnostics/m6/20261104/m6c-clipped-terminals-v3/`:
four direction/mode JSON reports, `SHA256SUMS`, `summary.json`.
They can be independently hash checked. No graph archive, Android,
production release or installer was changed.

Tests cover the mandatory true 25-km and SHA-bound buffer, wrong
GraphId/adjacency/mode bits and truncated native outgoing inventory,
one-way/mode-specific semantics, the dangerous boundary-distance filter
regression, all B locate alternatives, wrong B identity, and B-local
route proof's strictly limited meaning.

## Remaining M6c gates

- Prove **physical road-direction continuity** and the single correct
  final retained road edge against the full buffered graph, rather than
  assuming a dead-end node alone proves physical road lineage.
- Prove **original Valhalla route-service edge identity** independently
  of a potentially ambiguous `trace_attributes(edge_walk)` reconstruction.
- Validate actual legal A→B handoffs using the correct mode/direction;
  compare **all** relevant alternatives, both FASTER and SHORTER.
- Perform real Android JNI F8 parity and device tests before any
  precomputed inventory/Android issue #512 publication.

No merge or production publication is authorised merely by these
observations. The next change must preserve the F8 architecture contract
and undergo independent review and exact-head CI.
