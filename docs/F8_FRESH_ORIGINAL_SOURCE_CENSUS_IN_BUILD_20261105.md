# F8 — newly built ORIGINAL source-graph full-tile census (PR #125)

November 5, 2026. This is the next native production increment in the **normal
Graph Studio regional build queue**, NOT a new F8 routing architecture.

## Contract and on-build execution

The existing graph build queue already produces and validates each original
25-km buffered Valhalla 3.6.3 graph. Its automatic bilateral stage
(`tools/run_f8_bilateral_after_build.py`) now does **both of the following** for
*every* mutually compatible retained graph pair:

1. **Fresh original source scan in each direction**:
   `census_f8_original_source_after_build.original_source_census()`
   assembles original 25-km buffer polygons from each graph build, checks each
   against its manifest SHA, verifies both original archive SHA-256 values,
   and reads the matching cached original peer Geofabrik polygon for
   **annotation only**. It compiles/runs the reviewed Valhalla C++ scanner
   `native_f8_full_source_cut_edges.cpp` against the original source graph
   TAR, not OSM, new GraphIds, a prior F8 catalog or Android JNI scans.
   `GraphReader::GetTileSet()` visits **all original tiles and every original
   directed index**. It retains mode-accessible non-shortcuts near the true
   shared buffer cutoff, without requiring `edge->is_road()`: historically
   accepted original final edges may carry `is_road=false` despite legal
   Valhalla route proofs. The native original road/use and deadend flags
   remain annotations.
2. **Targeted source cut candidate register**:
   the exact original source buffer boundary and the **receiving graph's
   original 25-km buffer** limit candidate records. A source directed
   terminal may lie outside its own cutoff while the receiving nominal
   core excludes it (e.g. graph overlap through Slovenia). It must not be
   excluded just for being outside the receiving country's nominal
   boundary. Real outward cut records and already-beyond-cut records are
   retained separately by original directed GraphId. Native graph-local
   deadends just inside the cutoff are retained only as *unproved* nearby
   hypotheses; unrelated interior road continuations are NOT enumerated
   into a follow-up exploration requirement. No OSM way-name/proximity
   deduplication, mode duplication or first-success edge elimination.

Each original source census has an immutable document under:

`~/RoadPilotGraphStudio/f8-production/source-census/<pairId>/<sourceRegionId>/<original-input-key>/original-source-census.json`

The document contains exact original directed IDs, retained native
metadata, its original archive/config/buffer/polygon/native source+binary
SHA fingerprints, full tile/direct index visit counts and explicit flags:

- `originalValhallaSourceLastTripLegProof = NOT_YET_RUN`;
- `receivingGraphOriginalFirstEdgeProof = NOT_YET_RUN`;
- `allPhysicalRoadPerDirectionFinalEdgesDiscovered = false`;
- `sourceDiscoveryComplete = false`;
- `productionPublication = BLOCKED`.

The producer checks for **actual native full-tile completion**. No partial
stdout, truncated scan, wrong graph TAR, mismatched buffer manifest, invalid
toolchain, stale original pair SHA or duplicated directed GraphId is
accepted as a completed source census.

### One final directed road edge architecture remains unchanged

The source census does not equate every scan row with a distinct physical
road crossing. It is deliberately an inventory of **possible ORIGINAL
source-final directed edges**. A source-final candidate becomes a cross-graph
connection only after proving: the **one retained final edge for that
physical road and direction** (keeping genuinely different directed
branches); the original Valhalla **A-LAST** TripLeg directed GraphId and
mode-specific original native topology; and the receiving graph's true
physical forward directed edge with Valhalla **B-FIRST** TripLeg identity.
Unverified candidates and true branches remain explicit, not silently
dropped. No arbitrary OSM-way continuation traversal or portal matrix
is a prerequisite.

When a compatible retained SHA-bound proof ledger exists, the build stage
also reconciles **every previously verified source-final original GraphId**
as a strict subset of the independently generated original source census.
This *does not use* the historical ledger to discover new source candidates.
Only independently validated verified options enter an Android **test-only
partial cache**, with fall-back discovery retained; no full production
sidecar is published.

When the same step encounters a **newly built graph** with no original
A-LAST/B-FIRST ledger, it still fully enumerates both original source graphs
and records `SOURCE_ALL_TILES_CENSUSED_A_LAST_B_FIRST_PENDING`.
It does not report zero crossings or pretend fresh Valhalla matches exist.

## Real-original-graph acceptance, before PR merge

On the Legion, against original Italy NE and Austria October archives:

- Italy Nord-Est: **367** original GraphReader tiles, **8,764,618**
  original directed graph indexes visited.
- Austria: **338** original GraphReader tiles, **13,790,726**
  original directed graph indexes visited.
- Native source scan captures all **247** distinct source-final GraphIds
  present in the previously separately verified partial A/B ledger,
  including all `is_road=false` finalists, **without those 247 IDs being
  supplied as scan input**.
- Latest targeted stored source-cut candidate register after excluding
  unrelated interior continuations: Italy → Austria **4,125** scoped
  source original directed candidates; Austria → Italy **1,553**.
  **5,678 is a candidate count, not a confirmed number of physical
  crossings, final edges, or Valhalla-proved A/B connections.**
- Full normal post-build replay against **four** mutually compatible original
  graph pairs now returns successful source GraphReader census records for
  **all eight** pair directions: Italy NE↔Austria, Italy NE↔Italy Centro,
  Italy NO↔Austria, Italy NO↔Italy NE. The remaining three pairs properly
  report `SOURCE_ALL_TILES_CENSUSED_A_LAST_B_FIRST_PENDING` instead of
  reading previously verified evidence or claiming zero crossings.
  Log: `~/RoadPilotGraphStudio/diagnostics/f8-production/20261105/f8-automatic-all-original-source-census-all-four-pairs-v4.log`.
- Prior 247/278 A/B proof ledger remains a separate comparator and test-only
  Android cache input. Fresh source census still has no independently
  completed A-LAST/B-FIRST route proof stage.
- Native C++ scanner built from reviewed source on Legion's local
  Valhalla **3.6.3** C++ toolchain (pkg-config source selected explicitly).
  It runs without rebuilding or modifying original source graph tiles.

Live log:
`~/RoadPilotGraphStudio/diagnostics/f8-production/20261105/f8-auto-full-source-italy-austria-v4.log`.

## Explicit next engineering step, not an excuse for unrelated traversal

For fresh graph pairs, take the *outward directed original source-cut
candidates* (not all interior native road continuations), classify true
per-mode native final directed geometry, prove original Valhalla A-LAST, then
scan the complete matching original receiving graph near those candidates,
match physical forward road and direction, and prove original B-FIRST.
Reconcile genuine unproved crossings and distinct ramps/branches only.
Lastly exercise **unrestricted Android A→X→B** for car and motorcycle,
both directions, including runtime behavior and physical device acceptance.

Until those gates pass, do not merge this work as a production F8 catalog,
claim `sourceDiscoveryComplete=true`, or deliver it to RoadPilot as a
complete connection database. The user-level Legion AppImage installed
before this increment does not contain this source scanner; a new PR CI
AppImage is required before GUI acceptance testing of the new hook.
