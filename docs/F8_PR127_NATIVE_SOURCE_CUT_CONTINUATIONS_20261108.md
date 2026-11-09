# PR #127 — historical 2026-11-08 original source cutoff and local continuation experiment

**SUPERSEDED BY THE NOVEMBER 9 OWNER-APPROVED SOURCE-SELECTION CORRECTION.**
The region-wide `--resolve-cut` multi-hop traversal and angle-based physical
continuation logic described here were REMOVED from production code. These
figures are original read-only test evidence only, not current paired
production selection results. See
`docs/F8_PR127_PAIRED_TERMINAL_FIRST_20261109.md` for the replacement.

**8 November 2026 — Source graph A only.** This is a nonpublishing implementation
increment of the owner-approved D-017 five-step contract, not a new candidate
pipeline or replacement for F8. PR #127 remains a draft and must not merge
or publish based on these source-only tests.

## Implemented in the one source-stage producer

- `tools/native-f8-boundary-final/original_buffer_cut.h` reads the same
  SHA-pinned original 25-km buffered GeoJSON from the regional routing build.
  A bounding-box spatial index checks intersections of **original compiled
  Valhalla directed edge geometry** with its true GeoJSON polygon boundary,
  *only inside the previously selected original boundary tiles and immediate
  neighbour ring*. Original directed GraphIds are unchanged. Geometry cut
  classification records `OUTWARD`, `INWARD` or `AMBIGUOUS`; even ambiguous
  native crossing edges remain in the output. No road names, OSM-way keys,
  GPS samples, arbitrary cutoff distances or all-archive directed census.
- The same native GraphReader binary's `--local-continuations` mode accepts
  exact original source directed IDs and returns the edge's immediate outgoing
  directed candidates, including native zero-length hierarchy transitions,
  original directional shape tangents, classification, use, layer,
  bridge/tunnel flags and car/motorcycle access. All genuinely different
  native candidate GraphIds are kept, including forks, ramps and parallel
  levels. This is **not** a Valhalla route query.
- The region-neutral Python source stage follows only *locally unambiguous*
  physical-forward candidates within the source cutoff tile ring. It records
  unresolved class/geometry changes, hierarchy alternatives, genuine branches,
  mode divergences, out-of-scope successors and loops as incomplete. A locally
  aligned branch does not establish a unique physical road. Mode-specific
  paths are attributes of the source record, not duplicate connections.
  Grouping is permitted **only by exactly equal original source-final
  GraphId**, retaining all upstream source-cut and branch evidence.
- The source extractor's explicit `--cut-only` mode emits the same
  original-archive-SHA-bound, nonpublishing candidate format, now containing
  the authoritative original outer-cut orientation. Earlier unfiltered
  evidence remains intact. The native binary protocol is versioned 4 and
  refuses an older binary. No Graph Studio GUI, `.gph`, RoadPilot Android
  runtime, connection catalog or release path was modified.
- **Integrated command:** `tools/extract_f8_region_final_edges.py --resolve-cut`
  executes the exact native cutoff scan and local branch-preserving forward
  resolution in one region-independent, SHA-validated source workflow.
  Its sole output is a versioned **nonpublishing**
  `roadpilot.f8-original-cut-local-final-candidates` candidate artifact,
  containing every original cut edge (including inbound observations), exact
  final-GraphId groups with upstream source lineages, and every unresolved
  original source-cut observation. It never consumes the historical sampling
  ledgers. It refuses to overwrite an existing artifact, does not mutate
  either region and always returns `NOT_VERIFIED`/`BLOCKED`. The lower-level
  `--cut-only` option remains available for source edge inspection alone.


## Real Legion evidence (Valhalla 3.6.3, original `2026.10.13-1` archives)

| Read-only source operation | Italy Nord-Est | Austria |
| --- | ---: | ---: |
| Original cutoff/neighbor tiles scanned | 178 | 227 |
| Examined native directed positions | 4,315,046 | (recorded in retained artifact) |
| Exact original cut-intersecting directed edges | 6,180 | 8,135 |
| Directed outward at cutoff | 2,920 | 3,891 |
| Directed inward at cutoff | 2,909 | 3,885 |
| Ambiguous crossing direction, preserved | 351 | 359 |
| Outward + ambiguous sources traced locally | 3,271 | 4,250 |
| Candidate source roots with a mode-unified local final ID | 1,672 | 2,072 |
| **Distinct exact local final GraphIds** | **1,663** | **2,062** |
| Unresolved seed roots, retained | 1,599 | 2,178 |

Nine Italy source-cut seed pairs and ten Austrian pairs converge on the
same exact local final GraphId. The producer's exact-ID grouping preserves
all source origins. It does **not** claim that distinct GraphIds represent
the same physical road or that unrelated branches may be merged.

The emitted `GRAPH_LOCAL_TERMINAL` status means no further selected native
local road continuation was established; it is **not** yet a verified legal
physical-road final for every road/direction. Some cases have graph-native
outgoing roads that are geometrically/structurally ambiguous, including
junction turns, hierarchy-level shadow edges, ramps and changes of road
classification. A separate terminal on a neighbouring road is not permission
to guess the successor. Unresolved alternatives are never suppressed.

### Retained, immutable local evidence

Local artifact directory on the Legion:
`~/RoadPilotGraphStudio/diagnostics/f8-production/20261108/`

- `italy-nord-est-source-exact-cut-v4.json.gz` — SHA-256
  `64409561b97a3648ea70aaf8795ce5263a97aae33b332daf283ae14762557495`
- `italy-nord-est-local-source-chain-evidence-v1.json` — SHA-256
  `418fce685950fb984ff917d2fd30cd8ab5e6b1226dfd2fa5c7a8204040715870`
- `austria-source-exact-cut-v4.json.gz` — SHA-256
  `58aeb373ac55a0ff6397f70b6220589bed0902fbacf6aa82b3e857f08f16f02a`
- `austria-local-source-chain-evidence-v1.json` — SHA-256
  `571cbbb757c583209c6474173ebcea890a22e914f28890624893b1ffc707aa5d`

**Integrated CLI output (authoritative reproducible source-stage test):**

- `italy-nord-est-integrated-original-cut-local-final-v1.json.gz` — SHA-256
  `6874f4b721ec211216de5a7d5910ebbc10645f10b84a8677446bda859f2edc15`
- `austria-integrated-original-cut-local-final-v1.json.gz` — SHA-256
  `1623ccf6e84f9b99962b93ab0a59900a330284d75385f531254a1bd1cf1fe886`

Both integrated artifacts were checked by independent root-set reconciliation:
all 3,271 Italy or 4,250 Austria `OUTWARD`/`AMBIGUOUS` original cut directed
GraphIds are present **exactly once** as either original candidate lineage or
unresolved source observation. Exact final GraphIds within the candidate
groups are individually unique. Native Valhalla 3.6.3 Release compile passed
on the Legion and **404 Python tests passed** (including new synthetic region
neutrality, original cutoff selection, directed branches/modes/hierarchy,
cycles, cutoff scope, identical ID grouping and fail-closed publication gates).

Run the one-stage command with the paths from **any** original regional build:

```bash
python tools/extract_f8_region_final_edges.py \
  --manifest "$ORIGINAL_ROUTING_MANIFEST" \
  --graph-index "$ORIGINAL_GRAPH_INDEX" \
  --buffer-geojson "$ORIGINAL_25KM_BUFFER_GEOJSON" \
  --valhalla-config "$ORIGINAL_VALHALLA_CONFIG" \
  --native-binary "$NATIVE_F8_BOUNDARY_FINAL_EDGES" \
  --resolve-cut \
  --output "$NONPUBLISHING_SOURCE_CANDIDATES.json.gz"
```

### Historical native-cut discrepancy — explicitly retained

An earlier diagnostic using geometries transformed to EPSG:3035 classified
177 Italy Nord-Est directed edges as *direct cutoff observations*.
The new original-GeoJSON-coordinate source shape intersection finds 176/177.
The one differing original directed GraphId is `737868267290`: its current
compiled shape lies just beyond the straight-segment outer cutoff in the
source GeoJSON's longitude/latitude coordinates, whereas the older projected
geometry classification called it an outward crossing. This is a geometry
representation difference **not permission to delete the directed edge**.
The original native GraphId remains explicitly preserved among the forward
alternative GraphIds for both cutoff seed `736828079898` and cutoff seed
`738136702746`; each ambiguous branch remains unresolved. The same graph
and buffer fingerprints were verified. The earlier TripLeg last-edge witness
is historical evidence, **not** the new producer's per-connection validation
stage. No candidate was silently declared ineligible.

## Remaining acceptance gates

**Source completeness is NOT_VERIFIED.** Resolve the remaining actual native
cut source roads and their uncertain physical-forward continuations without
branch/name collapse. The boundary intersection includes inward and
ambiguous directions explicitly; a real source-final may be beyond the
polygon cutoff and must be reached via its native source-cut continuation.
Prove one genuinely last original directed edge per distinct physical road
and direction, not merely one candidate per matching numeric GraphId.

**Receiving B correlation is NOT_STARTED.** Do not begin it until source-side
physical-road/direction uniqueness is established. Then use the exact
original A final node GPS **X** in B's original directed geometry, including
mid-segment projections, and preserve actual receiving forks and mode
intersection. No B-side Y, no cross-graph GraphId equality, no name/way
matching and no redundant per-connection route probe.

**Android consumption is NOT_RUN.** Actual A→X→B journeys in both directions,
car/motorcycle modes and multi-region alternatives remain the production
acceptance test. Catalog publication and Graph Studio release stay BLOCKED.
