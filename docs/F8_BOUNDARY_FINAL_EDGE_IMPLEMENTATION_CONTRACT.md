# F8 build-time final-edge connection contract — OWNER APPROVED

**Decision:** D-017, November 5, 2026. **Status:** binding design, **not yet implemented**.
**Scope:** the F8 cross-region connection producer in RoadPilot Graph Studio.
**Reference:** `docs/ARCHITECTURE_CONTRACT.md`; this document specifies its
new boundary-only build implementation and supersedes conflicting legacy
requirements for a full-edge census and per-connection routing proofs.

## The only production workflow — owner reconfirmed 2026-11-06

1. **Graph A:** Identify the final retained directed GraphId for each physical road and travel direction.
2. **GPS X:** Retrieve that edge's exact directed destination node coordinates from the original compiled Valhalla graph.
3. **Graph B:** At the **same GPS location X**, identify the corresponding physical road and directed GraphId in the same travel direction.
4. **Catalog:** Store `A final GraphId → X → B directed GraphId`, with native car/motorcycle permissions and genuine separate branches.
5. **RoadPilot:** Test real cross-region A→X→B journeys in both directions and supported modes.

**Keep the existing 25-km graph overlap.** Do not change its size without explicit owner approval. **No arbitrary crossing points, road-name matching, exhaustive graph scans, or redundant per-connection Valhalla routing verification.** No architectural change without explicit owner approval.

The detailed rules below implement these five steps; they do not authorize additional producer stages.

**All-region implementation invariant (owner clarification, 2026-11-06):** This is
one reusable Graph Studio producer for **every configured region**, not an
Italy Nord-Est producer. Region IDs, native graph tiles, graph versions, the
actual 25-km buffered boundary and neighboring graph identity are always
read from that region's existing build artifacts; no hardcoded geography,
OSM road names or country-specific special cases. Italy Nord-Est and Austria
are **real test inputs only**. A success on those regions alone does not
prove production completeness for other regions.

The first source-only increment (`tools/extract_f8_region_final_edges.py`)
reads the indexed tiles along any region's original buffered cutoff and
its immediate native neighbours, retaining native mode-terminal candidates
and separately reporting unresolved junction-directed edges. It **does not
claim complete final physical-road identification**, receiving correlation,
Android compatibility or publication until the following stages actually
implement those steps. This clarification does not authorize a new
all-graph scan or diagnostic system.

**November 8 source-stage geometry increment (draft PR #127, nonpublishing):**
The native region-independent reader now includes the *directed approach
vertex* from the same compiled source edge shape that ends at X, plus
original road use and shape orientation. This is native source geometry,
not an inferred second receiving coordinate Y, a cross-region name/way
match, or authorization to declare physical-road identity. Its versioned
protocol fails closed against older binaries, and absent/degenerate
geometry is represented as unavailable instead of fabricated. Every
native local continuation remains unresolved until the actual physical
road and receiver are identified; the catalog remains blocked.

**November 8 native cutoff/continuation increment (draft PR #127):**
The same source stage now optionally filters original directed shapes to the
exact original 25-km buffered polygon cutoff and traces only their local
native physical-forward candidates, including immediate hierarchy peers,
car/motorcycle modes and branch alternatives. It can group identical final
source GraphIds without inferring equivalence between *different* GraphIds.
This is NOT a certification of every physical road/direction: ambiguous
forward cases remain unresolved, receiving matching has not started and no
catalog is publishable. See
`docs/F8_PR127_NATIVE_SOURCE_CUT_CONTINUATIONS_20261108.md` for actual
Italy/Austria evidence and the retained near-cut geometry discrepancy.

**November 9 owner correction — pair-scoped, terminal-first original source stage:**
The prior entire-region `--resolve-cut` selection and recursive angle-based
continuation walker are superseded and removed. Source identification MUST
first restrict A's original 25-km outer cutoff to the actual pair-specific
shared buffer coverage with graph B (both retained original graphs,
indexes, buffer footprints and reciprocal identities verified), then inspect
native mode-terminal directed edges first. At an unresolved source-cut node,
only immediate original directed incident edges, hierarchy peers and their
one-hop terminal candidates may be inspected; never recurse or infer same
physical road based on angle or road name. Maintain all nonterminal directed
edge/branch observations as explicitly unverified evidence. A locally
terminal directed GraphId is NOT proof of one physical-road final or a
corresponding B road. See
`docs/F8_PR127_PAIRED_TERMINAL_FIRST_20261109.md` for read-only real pair
results, incomplete statuses, and source candidate provenance.

**November 9 source-only graph-local terminal proof increment:**
The original cutoff stage now independently verifies *every* paired-cut
root's exact original A directed GraphId, native end-node GraphId, terminal
GPS X and vehicle access. It recomputes native terminal modes from immediate
compiled A node/hierarchy outgoing edges (including shortcuts), and records
one-hop terminal proof only if there is a sole eligible outgoing directed
edge; all other root alternatives remain unresolved. Multiple candidate
GraphIds sharing native X or an end-node are flagged, NEVER merged. These
read-back original A topological proofs are not complete physical-road
identity evidence and do not authorize B road matching, route probes,
catalog publication or a `COMPLETE` status. See
`docs/F8_PR127_BOUNDED_SOURCE_LOCAL_PROOF_20261109.md`.

**November 9 native immediate-costing experiment, source-only:**
The source stage can call Valhalla's original 3.6.3 car/motorcycle
`Allowed` costing on exactly the immediately incident A-directed edges at
already identified shared-cut source end nodes. With no preceding route
history or requested date/time, hierarchy/shortcut/conditional restrictions
are flagged `UNRESOLVED`, never guessed. A legal immediate turn does **not**
prove same physical road or final-edge completeness, and all original native
alternatives remain preserved without choosing the best route. No receiving B
native road, extra coordinate or multi-step Valhalla route is involved.
See `docs/F8_PR127_NATIVE_IMMEDIATE_COSTING_20261109.md`.

**November 9 exact original source native branch evidence:**
Only already selected original A source cut junctions are inspected. The
reader exposes each immediate outgoing edge's **actual native owning
from-node GraphId**, original directed departure geometry, end-node and
class/use/layer, alongside per-vehicle Valhalla 3.6.3 one-step legality.
Where multiple statically legal outgoing original edges have different
native end nodes and divergent original shape departure points, record
DISTINCT native geometric branches, preserving ALL alternatives. A single
legal next edge is only a legal immediate continuation; neither outcome
identifies the same physical road or proves complete final-edge coverage.
Unknown shortcut, hierarchy, timed/complex and physical-road identities
remain unresolved, not discarded. No road-name/way/heading heuristics,
Graph B native matching, new coordinate or production publication are
allowed by this evidence. See
`docs/F8_PR127_EXACT_NATIVE_SOURCE_BRANCH_TOPOLOGY_20261109.md`.

**November 9 owner-directed A→X→B implementation gate:**
The owner authorized moving directly to matching the original previously
verified source A terminal directed GraphIds at their exact native endpoint
X against the corresponding B original compiled road, **with bounded source
completeness reconciliation alongside it**, instead of more generalized
source classification. The same producer uses Valhalla 3.6.3 original B
spatial bins only at X, requires exact forward-shape approach overlap,
original native layer/bridge/tunnel evidence, and handles B incoming edges
that terminate at X through their exact same-node original B directed
successors (car/motorcycle allowed turns). All distinct legal original B
branches are preserved, shortcuts/conditional/hierarchy cases stay
unresolved, and A source road coverage is NOT yet proven. No B Y, names/OSM
identities, graph-wide scans, prefer-the-best-route logic, source graph
rebuild, or release is authorized. These are D-017 steps 2–3, not a new
architecture. See `docs/F8_PR127_NATIVE_A_X_B_MATCHING_20261109.md`.

**November 9 narrowly bounded source-missing Step 1:**
The owner directed recovery of actual missing source A final edges from the
392 existing original cutoff observations not represented by a final within
one hop, before any broader discovery. In the SAME original D-017 A→X→B
producer, an **optional** targeted mode reopens only those missing roots'
original native statically permitted immediate successors and at most ONE
additional original incident edge. Original A terminal and directed identity
are independently verified and corresponding B native candidates checked
at the SAME X, with all legitimate alternatives preserved. No recursive
road walk, new architecture, global census, heading/OSM/name/proximity
identity, or catalog publication is authorized. Existing 774 original A
candidates remain identical; 59 further A graph-local terminals were found,
6 having B native permitted options, and 285 cutoff observations still lack
a proven native terminal within the strictly bounded scope. These do not
prove distinct physical-road identity or full coverage; D-017 acceptance,
RoadPilot Android real routing and publication remain BLOCKED. See
`docs/F8_PR127_BOUNDED_MISSING_SOURCE_RECOVERY_20261109.md`.

**November 9 original outer-terminal A→X→B reconciliation:**
Without changing D-017, the owner-directed stage identifies every original
**graph-local native terminal directed A edge** with X outside A original
25-km buffer and inside B coverage **within the already selected pair
buffer-cutoff tiles**. The SAME native reader, using exact source tile
GraphIds, end-node topology and mode masks, now exposes those local finals
even when their whole edge is outside the cutoff polyline (and thus not
among earlier root edges). No network walk, extra GPS, whole-region graph
scan, new producer or B name/way association is added. Existing A finals
and B branch options are independently verified and retained. Original
Italy NE/Austria pair reads: 707 exterior local finals, 704 previously
registered plus three new; two of three match native B allowed outgoing
roads. Exact source tile-index bounds covering the B-minus-A endpoint
region are included (39/39 and 29/29). However full long-native-edge
origin coverage and physical-road identity are NOT verified, so catalog
and Android publication remain BLOCKED. This is evidence under Step 1,
not authorization to declare the complete D-017 invariant. See
`docs/F8_PR127_NATIVE_OUTER_TERMINAL_RECONCILIATION_20261109.md`.

**November 9 original incoming-edge owner-tile check (v10, D-017
unchanged):** The same original A native pair-cut reader now verifies the
origin tile of every eligible incoming directed A GraphId via Valhalla's
native immediate opposing-edge reference at exact A exterior X within B
coverage; one-way reverse orientations included. Both original regional
Italy NE/Austria pair directions proved **ZERO** eligible incoming edges
owned outside the selected pair source boundary tile set (1,063 and 541
incoming refs). The previous 707 external graph-local terminals and 420
B-allowed candidate endpoints are unchanged. This closes the native
long-edge owner coverage gate for THESE two original pairs, **not** the
separate physical-road/direction uniqueness or Android full-trip acceptance
requirements. No new discovery architecture, graph-wide scans, coordinate
Y, route-name matching or per-connection Valhalla proof. See
`docs/F8_PR127_NATIVE_OUTER_TERMINAL_RECONCILIATION_20261109.md`.

**November 9 source-to-receiver nonpublishing catalog milestone (D-017
unchanged):** The existing A-final-GraphId→exact-X→native B directed matching
reader now optionally emits a versioned, fingerprint-verified candidate plus
exception catalog, one source final original GraphId with all truly distinct
B statically allowed outgoing directed GraphIds and car/motorcycle mode bits.
For the 707 original Italy NE/Austria source exterior terminal finals, 420
have 646 B native candidate branches; 287 are explicitly unresolved
(219 no positive static B outgoing, 68 additional native restriction/time/
hierarchy unknowns). Original B successor *starts at X* to within 0.07m
on the original graphs; B predecessor/successor original class, use,
bridge/tunnel/layer divergence is recorded but **not** treated as proof of
physical-road sameness or a reason to discard genuine branches. Schema
`roadpilot.f8-final-directed-connection-candidates` v1; production BLOCKED,
physical road identity NOT_VERIFIED, Android acceptance NOT_RUN. This
is the same architecture and existing producer; does not authorize
per-connection TripLeg routes, guessed coordinates, names/way matching,
new discovery stages, direct Android installation or production publication.
See `docs/F8_PR127_NATIVE_FINAL_CONNECTION_CATALOG_20261109.md`.

### 0. Trigger and graph identity

The existing regional build queue invokes a single F8 post-build producer
once both relevant **validated original Valhalla graphs** are available.
The same command must be callable from the GUI, command line and automation.
Pair regions through the existing reciprocal graph-boundary index, and bind
every result to **both immutable graph archive SHA-256 values**, the original
25-km buffer geometry fingerprints and the two regional identities.

Never compare numeric GraphIds across independent graphs; they are local
identities and may change with a rebuild. Regenerate the catalog if either
graph or buffer changes. Do not touch the original graph tiles.

### 1. Source graph A — select the actual FINAL retained edge

1. Read the original 25-km buffered graph footprint from the SHA-bound build
   manifest. Its **outer cutoff** is the target; it is **not** the nominal
   Geofabrik border between countries.
2. From the already built graph's tile index (tile bounds and hierarchy),
   select only tiles intersecting the outer cutoff **where graph A and graph B
   have overlapping retained road coverage**. Follow immediate native
   end-node/incident-edge references into a neighboring tile when necessary
   to read the full directed edge and its actual destination; a long edge
   whose origin is in an adjacent tile must not be dropped. Do **not** iterate
   every directed edge in every source graph tile.
3. For each locally relevant compiled **directed** edge, read its original
   Valhalla GraphId, end-node GraphId, directed geometry, access bits,
   hierarchy links and outgoing incident edges. The native `deadend` and
   `is_road` flags are **hints, not sole eligibility filters**: earlier real
   source finals include `deadend=false` and `is_road=false`.
4. Establish the **last retained directed edge** of each actual physical road
   and travel direction by following **only its local physical-forward native
   continuations at the cutoff**, accounting for each allowed mode and
   hierarchy level. An earlier edge with the same road continuing in A is
   not final. A branch with its own truly different physical continuation is
   a distinct road/direction, not a duplicate. This is EDGE IDENTIFICATION
   USING COMPILED TOPOLOGY, not a second Valhalla route calculation.
5. Keep one candidate for each distinct physical road/direction final edge.
   Car and motorcycle access are attributes of that candidate, **not two
   copies**. Never collapse real lanes, carriageways or ramps because they
   share an OSM way ID, name, road reference or nearby coordinates.

A normal road dead-end merely near the buffer boundary is **not itself
a handoff**. It becomes a connection only if a matching receiving directed
road exists under step 2. Do not substitute a general network traversal.

### 2. Receiving graph B — correlate the same directed physical road

For every source final `A.finalGraphId`, define **one physical handoff X**
as its exact original directed terminal coordinate. **X is the single GPS
location used by both regional route legs**, matching the previously working
F8 normalized-handoff approach. Do **not** fabricate or independently select
a second receiving-graph handoff Y: an older coordinate-relay / A-B nearby
point correlation approach has already been tried and was not reliable.
The receiving graph may segment or represent that physical road differently;
this changes which B directed GraphId contains X, **not the intended handoff
location**. Any native locator snapping of X in B must still remain on that
same actual directed physical road, not an arbitrarily nearest road.

1. Look up **only the relevant B graph tiles near X and the shared
   buffer overlap**. Use original compiled B directed geometries, node
   topology and mode bits; B's chosen edge may **contain X within its
   geometry** rather than start precisely at X.
2. Identify the B directed GraphId describing **the same physical road
   continuing in the same travel direction** through/after X. Compare
   directed local geometry and actual native road continuity, not cross-
   region GraphId equality. **Do not match by road name, OSM way ID, road
   reference, or approximate GPS proximity.**
3. Preserve all **genuinely separate** B roads/ramps/forward branches. Do not
   accept an opposing direction, unrelated nearby parallel road, or
   duplicate native hierarchy representation as the same connection.
   **When multiple receiving edges occupy the same GPS location, Graph Studio
   uses Valhalla's native directed geometry, road topology, classification,
   bridge/tunnel and layer information to identify the corresponding physical
   road. It must not select a different road based only on GPS proximity.**
   Classification and bridge/layer attributes aid disambiguation; they are not
   hard equality requirements that discard a real corresponding road.
4. Determine which directed B segment contains or can represent the **same
   physical handoff X** in its graph-local geometry. Do not treat a projection
   onto a different nearby road as an equivalent second handoff point.
5. Read vehicle permissions **already stored by Valhalla**. The usable
   modes on an option are the intersection of A and B access; if the
   intersection is empty it is not an option. These are fields used
   DURING matching, **not a later per-connection verification stage**.

If the corresponding B physical direction is unclear, **do not guess or
pick the nearest**. Leave that original source final unpaired and mark the
pair's build status incomplete. Keep searching for other distinct source
finals; never stop after the first successful correlation.

### 3. Write the catalog

Emit **one source record per physical road and travel direction** and
store its actual original `sourceFinalDirectedGraphId`.

Each record has:
- source and receiver region IDs, graph/buffer fingerprints (catalog level);
- exact original source-final directed GraphId and handoff X (lat/lon);
- its car/motorcycle access set;
- an array of distinct original **receiving directed GraphIds**, each with
  its own car/motorcycle access subset. X is one shared geographic handoff
  reference; **no independently generated B-side Y coordinate** or
  coordinate-relay connection is stored.

**Cardinality:** one final-source record per actual physical road/direction;
one receiving option for each genuinely different valid directed branch;
one vehicle-mode set per record/option. Never manufacture a separate source
record for every probe, overlap coordinate, trip, mode or receiving branch.

Serialize to the **existing RoadPilot Android consumption format** using
a versioned adapter where needed; do not silently introduce an incompatible
schema. Mark the catalog complete only if the in-scope source finals have
been accounted for and their receiving correlations are unambiguous.
Unresolved candidates must not silently disappear. Publication remains
blocked if completeness/Android compatibility is not established.

### 4. Test the actual finished product in RoadPilot

Run the Android consumer on the **exact same retained original graph versions**
and emitted catalog. Test A→X→B journeys, in both directions, with car and
motorcycle where access permits. Include motorway carriageways, ramps,
local roads and a multi-region journey. Confirm correct navigation to the
actual destination and retention of useful alternative crossings, including
FASTER/SHORTER behavior.

These real **full-journey** tests are the only requested routing proof here.
Do not issue an extra Valhalla A-LAST or B-FIRST route for every generated
connection: the directed GraphIds are extracted from original compiled
graphs, not inferred from an arbitrary routing probe. Ordinary Valhalla
route calculation inside Android remains the way each actual trip works.

## Explicit prohibitions (not optional)

- **No all-tile/all-directed-edge census** as a production dependency. The
  full-archive `native_f8_full_source_cut_edges.cpp` workflow from draft
  PR #125 is **superseded**; do not merge it as this producer.
- **No separate per-connection Valhalla route / TripLeg A-last/B-first
  verification** during Graph Studio graph building.
- No OSM-first sampler, portal matrix, GPS probe generator, separate A/B
  coordinate-relay endpoints, all-path lineage exploration or intermediate
  source-edge connector catalog.
- No first-success/cached-success stopping rule; no arbitrary 512 cap.
- No deduplication by road name, way ID, proximity, or mode.
- No added diagnostic/audit pipeline to justify these four normal steps.
- No Android production release from incomplete candidates or CI-only tests.

## Precise acceptance conditions

**Graph Studio:** the standard build automatically produces the above
catalog from two fresh compiled graphs; the build process reads only
buffer-cut-related tiles and immediate edge references, uses original
GraphIds, stores all actual branch/direction options once and does not
perform per-link Valhalla route requests. Rebuilding either graph
invalidates/rebuilds its pair catalog.

**RoadPilot:** real Android routes using this catalog succeed in both
directions and supported modes on the exact graph packages; the runtime
does not lock onto the first cached crossing or hide another useful
physical crossing.

**Current state:** contract approved, implementation NOT COMPLETE.
Draft PR #125 is **not compliant** until its exhaustive all-tile scanner
and ledger-derived producer are replaced by this boundary-only workflow.
It is not authorized to merge or publish merely because its prior CI passed.

**Change control:** any extra discovery phase, producer, per-edge Valhalla
proof pass, or change to these four steps requires the product owner's
explicit agreement before coding. Do not infer authorization from tests,
diagnostics or historical design documents.
