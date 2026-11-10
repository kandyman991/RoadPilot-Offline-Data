# PR #127 — Original A → exact X → B candidate and exception catalog

**9 November 2026; owner-authorized D-017 increment, nonpublishing.** The owner asked to finish the existing matching work inside PR #127: validate the existing receiver options, account for the 287 original A exterior terminal edges without confirmed original B outgoing continuations, and produce the versioned connection catalog **without another discovery architecture, source-road classifier, or arbitrary road walks**.

## What is implemented

The **existing region-independent** `tools/extract_f8_region_final_edges.py --match-receiver --bounded-missing-source-recovery --reconcile-outer-terminal-edges` now optionally emits **two independent SHA-bound artifacts in the same original A/B native run**:

1. `--output <read-only-native-evidence.json.gz>`: full prior original paired A/B directed-edge correlation evidence, source terminal/end-node and vehicle-mode readback, B predecessor geometry, B same-node original permitted directed successors, and full native coverage/uncertainty record; and
2. `--catalog-output <blocked-connection-candidates.json>`: a **strict, versioned D-017 data-only catalog**, schema `roadpilot.f8-final-directed-connection-candidates`, version `1`. The contract is in `schemas/f8-final-directed-connection-candidates.schema.json`.

Only an independently validated **graph-local A final edge whose exact native X is outside A's original 25-km buffered region and inside original B coverage** can enter the catalog. No invented Y, closest-road assumption, OSM way/name equivalence, per-connection Valhalla TripLeg route, previous full-graph census, or new road-tracing pipeline.

Every eligible original A terminal directed GraphId occurs **exactly once** in one of two arrays:

- `connectionCandidates`: one original A final directed GraphId with exact native X and native graph fingerprints. Every original native Graph B **permitted** directed successor at X is retained beneath the same source record, with original car/motorcycle modes, original B predecessor GraphId, road class/use, bridge/tunnel/layer and native junction evidence. The existence of one or more allowed turns is **not** certification of the same physical road or an actual Android journey.
- `unresolvedSourceFinalEdges`: one original A final directed GraphId with exact X, *no generated connection*, reason `NO_ORIGINAL_B_NATIVE_ALLOWED_FORWARD_CONTINUATION` or `ORIGINAL_B_CONDITIONAL_HIERARCHY_OR_PATH_CONTEXT_UNRESOLVED`, any existing B predecessor IDs and native uncertain alternatives. Each has `mustNotCreateConnection: true`. An unavailable/default-time immediate `Allowed` result is **not** incorrectly reported as a physical dead end.

The separate `unresolvedOriginalCutRootLineageGraphIds` retains the **285** older cut-root observations without a bounded native root→terminal relationship, *distinct from* the 287 unmatched **outer terminal GraphIds**. These 285 are NOT asserted to be 285 additional roads, missing edges or connections. All original records and branch alternatives remain retained in the full native evidence.

**Catalog status is always** `productionPublication=BLOCKED`, `physicalRoadIdentityAcceptance=NOT_VERIFIED`, `sourceDiscoveryComplete=false`, `receiverMatchingComplete=false`, `androidFullJourneyAcceptance=NOT_RUN`, and `noDistinctSourceOrReceiverBranchSuppressed=true`. A false proof/status, corrupt original B mode mask, missing reciprocal SHA-bound boundary identity, repeated original directed GraphId, changed X, wrong B start node, or missing native source terminal inventory fails closed. No `READY`, Android injection or installable sidecar is generated.

### Native physical correspondence safeguards

Original Valhalla 3.6.3 source/receiver archive fingerprints, source/receiver graph-index and 25-km buffer fingerprints, and reciprocal pair boundary identities are bound to the catalog. Original A terminal GraphIds, native modes and exact X were re-read; native B uses the indexed original directed geometry corresponding to the A *approach* with the same direction, original layer/bridge/tunnel, and **exact B predecessor end node**. Native `Allowed()` handles immediate car/motorcycle restrictions and retains unknown path/time/hierarchy cases.

The producer now additionally verifies every permitted B **successor actually STARTS at X** (max native quantized offset less than 0.07 m on both real pairs; fail closed above 0.75 m), not simply that a nearby edge passes through X. It retains original B predecessor→successor metadata in three descriptive categories:

- **Consistent original B predecessor and successor class, use, layer/bridge/tunnel**: eligible native transition, not certified same physical road;
- **Original B road class or use changes**: possible ramp or distinct branch; retain and mark physical identity UNVERIFIED;
- **Original B bridge/tunnel/layer changes**: possible legitimate grade transition or unrelated road; retain and mark physical identity UNVERIFIED. It is **not** automatically accepted as a proven continuous physical road.

This is evidence labeling, **not a new discovery or angle/straightest-road ranking algorithm**. No genuinely distinct B directed option is suppressed merely due to road-use/class or layer differences.

## Actual 2026.10.13-1 original Valhalla 3.6.3 bilateral results

| Original A → X → B result | Italy NE → Austria | Austria → Italy NE | Combined |
|---|---:|---:|---:|
| All eligible original A exterior graph-local terminal GraphIds | 454 | 253 | **707** |
| Original A final GraphIds with ≥1 permitted B native successor | 260 | 160 | **420** |
| Original B permitted directed successors, branches preserved | 401 | 245 | **646** |
| B successor original class/use/structure all match its B predecessor | 280 | 171 | **451** |
| B successor class/use differs, structure matches | 90 | 63 | **153** |
| B successor original bridge/tunnel/layer differs | 31 | 11 | **42** |
| Original A final GraphIds with **no** B statically permitted outgoing | 148 | 71 | **219** |
| Original A final GraphIds with only unresolved conditional/hierarchy/path B outgoing | 46 | 22 | **68** |
| **All unmatched A exterior final GraphIds recorded (zero silently dropped)** | **194** | **93** | **287** |
| Existing cut-root observations with no ≤2-hop native link (separate measure) | 191 | 94 | 285 |
| Native A incoming long-edge origin outside selected B-covered A endpoint tiles | **0** | **0** | **0** |

**Modes:** 634 B options have *both* original car and motorcycle allowed; 12 have motorcycle only. Modes remain per B original directed GraphId and are never copied from a different branch.

Important limitations: **420 are native B-allowed candidate source endpoints, not 420 certified physical-road identities or usable Android connections.** 451 consistent predecessor/successor attribute sets still cannot prove every physical road (distinct roads can share road use/class and meet at X). The 153+42 attribute differences may include legitimate ramps/grade changes and stay available, *not falsely converted into definitive same-road matches*. The unresolved 219/68 are retained, not guessed as dead ends or forced into the catalog's valid-connection list.

## Output locations and checks

On the authorized Legion:
`~/RoadPilotGraphStudio/diagnostics/f8-production/20261109/`:

- `italy-ne-to-austria-connection-candidates-v2.json` — SHA-256 `c1914321fad678e450aa59d8a7ec40102662dbfa3fe237592b3107c234da2b53`, 613,196 bytes.
- `austria-to-italy-ne-connection-candidates-v2.json` — SHA-256 `5a8b5b9182938ffe57d9e1e979e797707ef7e4b6213fd1a229206e99430b567b`, 355,759 bytes.
- Source evidence, same exact run: `<direction>-catalog-evidence-v2.json.gz`.

Both real catalogs independently **PASS JSON Schema Draft 2020-12 validation** with the bundled versioned schema. Both original A/B graph runs passed, and all **425 Python tests passed**, including fail-closed corrupt/duplicated native IDs, B branch/mode/grade evidence, archive and buffer fingerprints, native adjacency at X, missing/forged completeness claims, immutable catalog output and preservation of all unresolved exception identities. Original C++ native reader remains version 10 and its Valhalla 3.6.3 Release build passed in the previous milestone; no new C++ changes in this catalog increment.

## Next engineering and actual acceptance boundary

The Graph Studio **data-only A→X→B candidate/exception catalog producer is implemented** for all regions using native fingerprints and existing region-independent build inputs. It is not a production-activated routing sidecar and has **not** been automatically installed in RoadPilot. The older experimental Android `F8FinalEdgeConnectionCatalog` consumer requires **per-connection TripLeg proofs**, which directly conflicts with the owner-approved D-017 **no redundant per-connection route proofs** requirement; this v1 candidate schema must NOT be fed to that older reader as if it were already compatible.

Before declaring **production D-017 complete**: adapt/test the active RoadPilot Android consumer to this original-directed A→exact X→B contract **without** the older per-connection proof architecture; validate real two-region journeys in both directions and car/motorcycle mode, and only then enable versioned standard Graph Studio post-build catalog packaging with verified source physical-road/direction coverage and independently reviewed CI. The source-to-B physical-road identity of alternatives currently remains `NOT_VERIFIED`; publication and PR merge are NOT authorized merely because a native turn is allowed or the catalog JSON is structurally valid.

PR #127 stays **DRAFT, OPEN, UNMERGED and NONPUBLISHING**. Existing two architecture-contract acceptance checkboxes remain unchecked; do not falsify CI to make them green.
