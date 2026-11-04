# M6c Phase B — Native A-terminal → B-incoming → B-outgoing continuity evidence

**Status:** M6c continuation; deliberately read-only, **not** a production F8 handoff publisher.

The accepted architecture remains: independently built Valhalla graphs with
25-km buffered overlap; discover one real **final retained road edge** as a
handoff source, retain all physical roads/directions/alternatives, compute
A→X and X→destination with original F8, and use real Valhalla direction/mode
and endpoint evidence. This phase does not reintroduce the retired
OSM correlation, arbitrary road portals, connector matrices or regional
route planner. There are **no** graph, Android, routing-package, sidecar,
publisher, or GUI changes.

## The specific new evidence

M6c Phase A (PR #114) found native graph-local directed end nodes in Graph A
and two B locate directed edges per node. The B edges had different roles:

- The **B incoming overlap edge** ends at A's final native terminal. Its
  native directed geometry overlaps the last 20 metres of the Graph A
  terminal road. It can have different graph-local IDs and segmentation.
- A different **B outgoing edge** starts at that node and continues further
  into Graph B. In the examples, the incoming and outgoing are connected
  by **Graph B's actual native end-node adjacency**. They are not a
  cross-graph GraphId match.
- The opposing native B reverse edge and any other branches remain in
  the report, even if inaccessible or not route-probed.

Previously M6b had traced the last edge of one arbitrary A route and
found the GPS stopping *mid-edge*. M6c instead inspects a **real native A
end-node**, independently reconstructs the B incoming overlap and
connected B outgoing inventory, and requests a **B-local** turn.

## Implementation

`tools/probe_native_f8_road_continuity.py`:

1. Verifies both exact archived regional graph fingerprints, neighbor
   boundary fingerprints and both **25.0-km buffer GeoJSON hashes** from
   their immutable routing manifests. Checks SHA-256 of the previously
   compiled Valhalla **3.6.3** native extractor before using it.
2. Accepts **1–8 explicitly nominated A native directed edges**, not a
   global sampling or discovery procedure. The source native
   `deadend`/all-outgoing-mode inventory is reverified through
   `check_source_terminal`; this is graph-local source evidence.
3. Invokes Valhalla B `locate` within a declared radius, retains **every**
   returned B directed ID, and fetches all actual B native geometries.
   A missing/duplicated/mismatched native GraphId or count fails closed.
4. Observes the last 20 m of A against **each** returned B directed
   geometry. Identifies only a *nominated diagnostic B-incoming* when
   its native end node is within 2 m of A's end and at least two
   sampled positions agree in directed order. **A full 20-m overlap
   is not required**; B may split the same physical road differently.
   Unmatched/partially observed candidates remain unknown, not rejected
   or excluded from future F8 discovery.
5. For nominated B-incoming edges, retrieves and validates the **full
   native B outgoing degree, all directed branch IDs, access masks,
   shortcuts, nonroad and opposing-reverse identities**, and their actual
   native geometries. B IDs never get compared to A IDs.
6. For each B outgoing branch, checks native geometry join distance,
   sampled A-tail overlap and direction (observations only), and runs
   a **bounded Valhalla B-only local turn route**. Replays that route's
   shape separately with `trace_attributes(shape_match=edge_walk)`.
   A positive label only says the **edge-walk replay** contains the
   nominated B incoming→outgoing sequence and endpoint/snapping checks
   succeeded on that B-only route. It does **not** establish the
   route service's authoritative edge IDs, a physical road identity
   certificate, or legally transferable A→B cross-graph traffic.
7. Keeps even unprobed branches explicitly marked
   `NOT_PROBED_BUDGET`; a successful first candidate never terminates
   discovery. Native road `wayId` equality is **annotation only**,
   never a required selector or graph correlation rule.

**Reviewability/integrity:** unknown B incoming geometry, split-edge
coverage and non-selected B locate records are not global negative road
evidence. Mismatched identities/counts are fatal; failed B-only routing
is inconclusive for its sample. `originalRouteEdgeIdentity` and
`crossGraphLegalTransfer` remain `NOT_VERIFIED` throughout.
`productionPublication=BLOCKED`.

## Legion real-graph replay — November 4, 2026

Same immutable **Italy Nord-Est ↔ Austria 2026.10.13-1** packages,
manifest-bound 25-km buffers, and SHA-reviewed native Valhalla 3.6.3
extractor as M6a/M6b/M6c Phase A.

Five explicitly nominated A terminal directed IDs, sampled in both
Car and Motorcycle modes (ten source-mode observations), generated
the following receiving-native directed chains:

| Direction | A terminal directed ID | B incoming overlap directed ID | B outgoing directed ID |
| --- | --- | --- | --- |
| Italy→Austria | `364870918424` | `228740587800` | `229076132120` |
| Italy→Austria | `77309436192` | `1911730233632` | `1912569094432` |
| Italy→Austria | `954791387424` | `7458042962208` | `7457908744480` |
| Austria→Italy | `2670664376600` | `365776888088` | `1066561200408` |
| Austria→Italy | `5417061081376` | `415034794272` | `415101903136` |

For **each** nominated A terminal:
- B locate returned two directed edges, both retained in the report.
- One **incoming B edge** matched the A terminal's 20-m tail at **11/11
  sampled positions**, with ordered directed geometry.
- Graph B's native adjacency confirmed the outgoing edge as a
  **non-opposing** continuation from the incoming B edge's native end node,
  and retained its mode-inaccessible opposing reverse.
- The native B incoming/outgoing geometric join gap was **0.0 m**.
- Both Car and Motorcycle B-only local route shapes had a
  **matching edge-walk replay** of the incoming→outgoing B directed IDs.
- All ten reports are **sample-specific**, not a global census,
  complete candidate inventory, or F8 correctness certificate.

Important subtlety: on the real data the B incoming edge already ends
at the exact A terminal, but the B outgoing edge extends beyond that
terminal. Picking only the B outgoing edge as an overlap match fails to
observe the actual incoming road segment. The full native B
incoming→outgoing topology matters.

Raw JSONs and SHA256SUMS are stored **outside Git**:
`~/RoadPilotGraphStudio/diagnostics/m6/20261104/m6c-native-continuity-v2/`.
They include every B locate result and native outgoing branch.

## Reproduce one native observation

~~~bash
P="$HOME/RoadPilotGraphStudio"
PATH="$HOME/.cache/app.roadpilot.graphstudio/python-env/bin:$PATH" python \
  tools/probe_native_f8_road_continuity.py \
  --pair "$P/f8-native/italy-nord-est__austria/e6a10d36f-ee7baac93-43d085-958523/pair.json" \
  --from-manifest "$P/builds/italy-nord-est/italy-nord-est-routing-2026.10.13-1-manifest.json" \
  --to-manifest "$P/builds/austria/austria-routing-2026.10.13-1-manifest.json" \
  --from-buffer "$P/work/italy-nord-est/build/buffer.geojson" \
  --to-buffer "$P/work/austria/build/buffer.geojson" \
  --native-endpoints-binary "$P/diagnostics/m6/pr112-review/native-build-20261104/build/native_f8_directed_endpoints" \
  --direction from-to --mode motorcycle \
  --source-graph-id 364870918424
~~~

## Remaining implementation gates

- **Source physical final-road identity and complete coverage:** These
  native terminal examples do not prove that every relevant road's
  actual last retained edge has been discovered. A native deadend
  cannot by itself establish the full physical road lineage; never
  silently deduplicate by OSM wayId/road name.
- **Authoritative route-edge fidelity:** The independent
  `trace_attributes(edge_walk)` method may choose another edge on
  overlapping/ambiguous geometry. Compare the original Valhalla
  route-service *native* edges with the replay rather than claiming
  true route GraphIds from a shape.
- **Legal handoff:** B-native node adjacency is only within B.
  Independent A→X and X→destination success plus a B-only local turn
  does **not** create a legal A-node→B-node graph edge. Preserve the
  working F8 GPS handoff and every alternative, and prove actual
  mode-specific transfer on device.
- **Exact JNI parity, completeness, global FASTER/SHORTER alternatives,
  multihop and Android #512** remain outstanding.

No merge or production enablement is authorized by this diagnostic.
