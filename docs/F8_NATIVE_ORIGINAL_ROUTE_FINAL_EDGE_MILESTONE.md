# Native F8: original route IDs, retained terminal edges, and Android parity

2026-11-04 · Production F8-native work from merged main after PR #116.
**Original Valhalla route-edge identity: verified for selected graph-local
legs. Selected native terminal paths: 10/10 real samples proved.
Global road uniqueness, Android JNI parity and publication: NOT VERIFIED.**

## PR #117 independent review corrections (same production architecture)

The original PR head `9b507e3` received an independent security,
data-integrity and architecture review. Findings were corrected in
place on the PR branch, without changing native GPS discovery or
production connectivity:

1. **Native executable trust preflight — P1:** The opt-in
   `--native-route-edges-binary` executed `--version` *before*
   hashing the file. Arbitrary native code can run at that point.
   Both the direct F8 CLI, the Graph Studio shared command engine,
   and the native terminal verifier now **require** the matching
   owner-reviewed `--expected-native-route-sha256`; invalid,
   substituted or symlinked executables fail **before execution**.
   Source/compiled binary/dependency and build recipe hashes are
   recorded in
   `docs/F8_PR117_ORIGINAL_NATIVE_BUILD_PROVENANCE.json`.
2. **Route-edge completeness — P2:** The C++ extractor previously
   skipped absent node-edge records, potentially converting a
   corrupted/incomplete original TripLeg into plausible IDs.
   Valhalla 3.6.3's terminal node must have no outgoing edge,
   and every preceding native node must contain exactly its
   original directed edge. The C++ and Python adapters now
   fail closed on any missing/extra original edge. The native
   stdin request also has an actual **32-KiB bounded read**,
   not an unbounded allocation followed by a size check.
3. **Android parity audit scaling — P2:** Repeatedly iterating
   every native GraphReader edge for every window scales poorly
   with hundreds of thousands of edges. The audit now indexes
   all original native node latitudes **once** and uses a binary
   interval search plus inclusive longitude bounds per window.
   Exact boundary and same-way directed-edge regression tests
   ensure it does not silently drop or coalesce alternatives.
   The output still says **JNI_PARITY=NOT_VERIFIED**; no actual
   Android capture or publication is authorized.
4. **Review provenance gate — P2:** Hosted GitHub CI cannot claim
   to compile the pinned C++ Valhalla 3.6.3 target when the retained
   local static library is absent. The exact Legion binary, source,
   CMake, libvalhalla static archive, pkg-config and CMakeCache
   SHA-256s are now bound in a committed provenance record;
   architecture CI verifies the source/build recipe checksums
   against that record. Eight corrected real-graph reports with
   `SHA256SUMS` were rerun using the reviewed binary at
   `~/RoadPilotGraphStudio/diagnostics/f8-production/20261104/pr117-independent-review-v3/`.
   This is reproducible **Legion evidence**, not a hosted
   native build or authenticated physical Android JNI proof.

**Reviewed native executable pin:**
`sha256:e955677e56278b53cee0d39ca6d94efa1557e1439da81859f330ffb4b8dbe776`.
Pass it using
`--expected-native-route-sha256 sha256:e955677e56278b53cee0d39ca6d94efa1557e1439da81859f330ffb4b8dbe776`
alongside every explicit `--native-route-edges-binary`
invocation. Older experimental reports remain archived but do
not satisfy this reviewed pre-execution trust gate.

## Architecture contract

Preserve independent Valhalla graphs, the 25-km overlap, and the original
GraphReader receiver-side GPS discovery path. No OSM way/name matching,
connector matrices, first-success stopping, cross-region GraphId equality,
geometric rejection, or candidate suppression. No Android, graph archive,
installed app or production connectivity package change is made.

## Authoritative original route-edge identity

Native `tools/native-f8-edge-scan/native_f8_route_edges.cpp` uses the pinned
Valhalla 3.6.3 `tyr::actor_t::route` **once**. It reads native directed edge
IDs from the SAME calculation's original
`Api.trip().routes(0).legs(0).node(n).edge().id()` protobuf, with original
way IDs, original encoded shape, and genuine route duration and distance
from the same serialized `trip.summary`. It never uses the independently
re-matched `trace_attributes(shape_match=edge_walk)`.

New `tools/native_f8_original_route.py` validates graph-local
identity provenance, the original ordered edge list, real route geometry,
snap offsets, costs, pinned Valhalla version and executable SHA-256.

Production `tools/probe_native_f8_journey.py` and shared
`tools/graph_studio_f8_workspace.py` support explicit
`--native-route-edges-binary` in the existing F8 two-leg prover.
Each local route must start on the original B GraphId of its receiver
candidate, or that candidate remains UNPROVEN even if a different B edge
routes successfully. The new label
`TWO_GRAPH_LOCAL_LEGS_ORIGINAL_ROUTE_EDGE_MATCH_ONLY` proves original
IDs **inside each graph**, never a shared cross-graph edge or legal
F8 transfer.

The earlier separate edge_walk replay status stays distinguishable,
and neither status becomes a misleading validated handoff map pin.
Default behavior is unchanged unless the native binary is explicitly
supplied; CI and packaging do not automatically publish that binary.

## Final retained directed edge per selected physical path

Production proof gate `tools/verify_native_f8_original_road_terminal.py`
examines explicitly selected native source edges **without changing the
original F8 GPS proposal inventory**. It checks immutable routing archive,
neighbour/boundary fingerprints and both 25-km buffer GeoJSON SHA-256s,
complete native outgoing node inventory (including nonroad/shortcut
edges and opposing reverse), requested Car/Motorcycle access and the
real original Valhalla route to the exact native source endpoint.

An edge passes only when the original source route's **last GraphId**
equals the nominated native GraphId, actual endpoints snap within
1 metre, native deadend and all mode-usable forward continuations confirm
that this is the graph-local final directed edge, and the point lies
inside the verified **receiving-region** buffer.

**Real immutable Italy Nord-Est ↔ Austria 2026.10.13-1:**

| Direction | Original native final GraphId | Car | Motorcycle |
| --- | --- | --- | --- |
| Italy→Austria | `364870918424` | PASS | PASS |
| Italy→Austria | `77309436192` | PASS | PASS |
| Italy→Austria | `954791387424` | PASS | PASS |
| Austria→Italy | `2670664376600` | PASS | PASS |
| Austria→Italy | `5417061081376` | PASS | PASS |

**10/10** original native route terminal observations passed. The
original route last-edge GraphId exactly matched the source native
edge in every observation; endpoint snap deviations were 0–0.08 m.

An important real-data discrepancy: **all ten** graph-local terminal
endpoints are outside the separately retained source-buffer polygon
but are genuinely present and routable within the source immutable
GraphReader archive and inside the verified other-region buffer.
Own-buffer polygon proximity is therefore diagnostic only. Using it
as a candidate rejection would violate F8 architecture.

These examples establish **selected graph-local final directed edges**,
not a complete inventory of every actual physical road, nor globally
unique last edges. Distinct GraphIds and same-way alternatives remain
distinct; never group by name/way ID to manufacture uniqueness.
`globalAllPhysicalRoadCoverage` and
`physicalRoadUniqueFinalEdgeAcrossGraph` remain NOT_VERIFIED.

## Real original two-leg F8 receiver-edge checks

Native receiver streams remain 334,973 Italy→Austria and 323,372
Austria→Italy directed edge proposals.

| Direction | Mode | Two source ordinals tested | Original B edge identity |
| --- | --- | --- | --- |
| Italy→Austria | Car | 218029–218030 | 1 matched, 1 unproven |
| Italy→Austria | Motorcycle | 218029–218030 | 1 matched, 1 unproven |
| Austria→Italy | Car | 180725–180726 | 1 matched, 1 unproven |
| Austria→Italy | Motorcycle | 180725–180726 | 1 matched, 1 unproven |

Original B route GraphIds rather than shape-matched surrogates identify
the actual B first edge. The second proposal in each two-item batch
routes onto a *different* original B edge and remains UNPROVEN as that
native receiver candidate. All other alternatives remain in the
unchanged native receiver proposal stream.

Full original per-leg ID lists, actual snap positions, route metrics
and SHA-verified JSON reports are outside Git:

- `~/RoadPilotGraphStudio/diagnostics/f8-production/20261104/original-route-protobuf-v2/`

No physical road global completeness, cross-graph turn legality,
route-optimality or package publication is claimed by these checks.

## JNI parity: current Android limitations and new audit

Current Android `SmartRide-Next/main` at
`e8652717d69d2fffc3136cbe0138cacb993345cc`:
`native/on-device-valhalla/builder_jni.cpp` still clamps native scan
`maxResults` to **512**, even when the caller asks for 4096, and
uses family quotas after sorting. `FrontierRouteLocalRecovery.kt`
still reduces different native receiver GraphIds via
`.groupBy { it.edge.receiverRoadKey() }` before F8 proof.
These can lose valid crossings, including same-name carriageways,
ramps and separate physical crossing positions.

The new `tools/audit_native_f8_android_jni_parity.py` compares raw
Android JNI window-level directed IDs and post-Kotlin grouping IDs
against **fingerprint-bound native GraphReader source scans**, reports
the 512 saturation, distinct missing/extra directed IDs and grouping
losses, and rejects stale graphs and invalid duplicate IDs.
Synthetic regressions reproduce 515 native edges capped to 512 and
the road-key grouping loss.

**Real Android JNI parity is NOT VERIFIED.** No actual same-graph
on-device JNI capture with independent provenance has been supplied
or executed; synthetic or host-simulated agreement cannot fill that
gap. The tool always records the capture-authentication limitation and
`f8GraphEdgeParity=NOT_VERIFIED`, never publishing connectivity.

## Remaining engineering and release gates

1. Exhaustive final retained edge **per actual physical road/direction**
   within all relevant overlapping native graphs, with legitimate
   branches and distinct road paths preserved.
2. Real same-installed-graph Android JNI scanner captures, window and
   grouping parity, cap and missing-alternative resolution.
3. Full mode-specific legal GPS handoffs, all relevant alternatives,
   multi-hop journeys and full FASTER/SHORTER cost comparisons.
4. Versioned production sidecar and Android #512 ingestion with
   atomic rollback and retained original generalized F8 fallback.
5. Independent review, exact-head CI, physical device acceptance and
   explicit owner permission before merge or release.

This PR introduces no production crossing record or retired architecture.
