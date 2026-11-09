# PR #127 correction — pair-scoped terminal-first source edge selection

**2026-11-09, binding D-017, draft, nonpublishing.** This corrects the older
November 8 `--resolve-cut` implementation, which examined the *whole outer
boundary of A* and recursively followed plausible physical-forward chains.
The former region-wide figures (3,271 and 4,250 traced roots; 1,599 and 2,178
unresolved) **are not the relevant workload for the Italy NE ↔ Austria pair**.
The old native evidence is retained for provenance, but its traversal logic
and 20°/55° straightest-road heuristics are **removed from the production
source extractor**, not expanded. No OSM/road names, arbitrary cut points,
all-graph road traversal, B-side Y or TripLeg route proofs are introduced.

## Corrected production-source selection, still NOT COMPLETE

1. Require **both** original routing manifests, compiled graph indexes and
   25-km buffered GeoJSONs. Verify original archive/index/buffer SHA-256 on
   each side, and reciprocal `boundaries[].sourceId`/fingerprints of the
   actual source pair. Mismatched neighbor metadata or zero shared cutoff
   fails closed; no global or country-specific fallback.
2. Derive only **A's actual outer buffer cutoff inside B's original 25-km
   buffered footprint** via `A.boundary ∩ B.polygon`. B's indexed original
   compiled graph tiles must also touch this shared line. This represents
   potential B coverage, **not evidence that B contains the same road**.
3. Select only original A graph tiles intersecting this pair-specific line,
   plus their immediate native tile neighbors. The native source reader
   checks original directed shapes against the *derived shared line*, not
   the whole A outer boundary. Its exact original GraphIds, terminal node X,
   access modes, hierarchy/node references and genuine branches are retained.
4. Inspect native mode-terminal directed edges **first**, with `deadend`/
   `is_road` as annotations, never sole filters. Preserve every outward or
   ambiguous paired-cut nonterminal edge as an unresolved source observation.
   Check its **immediate native outgoing edges**, including hierarchy peers,
   and inspect eligible original immediate successors **once only** for
   native local-terminal status; **STOP there**. Do not recurse, explore
   forks, discard ramps, rank by angle/class/name, or invent physical-road
   equivalence. Shortcuts and scope-exiting alternatives remain visible as
   evidence. Car and motorcycle native terminal permissions are combined as
   attributes; incomplete mode branches remain unresolved.
5. Group local terminal candidates only by **equal original A directed
   GraphId**, retaining every distinct cut source and one-hop option.
   Historical source original graph fingerprints and B fingerprints bind the
   resulting nonpublishing candidate artifact. Source physical-road
   uniqueness `NOT_VERIFIED`, receiver actual directed match `NOT_STARTED`,
   Android end-to-end acceptance `NOT_RUN`, publication `BLOCKED`.

The `--resolve-cut` CLI requires three additional arguments:
`--receiver-manifest`, `--receiver-graph-index`,
`--receiver-buffer-geojson`. It rejects missing or incompatible pairs.
The exact source side CLI is the existing generic
`tools/extract_f8_region_final_edges.py --resolve-cut`; callers supply the
*original* source/receiver artifacts, with no Italy/Austria assumptions.
The standalone `--cut-only` remains a read-only, explicitly unpaired native
inspection path and **must not be used for production final-edge publication**.

## Real original Valhalla 3.6.3 data — Italy Nord-Est and Austria

Both originals are retained builds `2026.10.13-1`; only **72/60 source tiles**
were selected for the shared boundaries instead of **178/227** for their
entire outer buffer outlines. The native reader examined 1,816,149 and
1,582,070 local directed positions, respectively, not all archive tiles.

| Actual paired stage | Italy NE → Austria | Austria → Italy NE |
| --- | ---: | ---: |
| Pair-specific selected original A tiles | 72 | 60 |
| Directed edges intersecting A's shared outer cutoff | 1,520 | 776 |
| Outward / ambiguous original cut roots | 820 | 422 |
| Native mode-terminal source roots | 381 | 211 |
| Nonterminal source roots — **preserved unresolved** | 439 | 211 |
| Exactly one-hop original neighbor GraphIds inspected | 564 | 249 |
| Additional one-hop terminal-candidate occurrences | 154 | 71 |
| Distinct local terminal candidate GraphIds | **505** | **269** |
| Actual physical-road final uniqueness | NOT_VERIFIED | NOT_VERIFIED |
| Receiving graph B directed road matching | NOT_STARTED | NOT_STARTED |
| Production publication | BLOCKED | BLOCKED |

The Italian historical direct-cut source GraphId `737868267290` is retained
as an original one-hop local terminal candidate; both source-cut node
alternatives `736828079898` and `738136702746` remain linked to it. No
historical projected geometry observation was used as a discovery seed.

Both outputs pass source provenance reconciliation: each paired outward or
ambiguous original cut root is present as a native terminal root or an
explicit unresolved nonterminal observation (mode-specific roots may appear
in both); every local final record has a unique original GraphId, and its
source identities are exact roots in that pair's original cut.

### Retained read-only engineering evidence on the Legion

`~/RoadPilotGraphStudio/diagnostics/f8-production/20261109/`

- `italy-ne-to-austria-pair-terminal-first-v2.json.gz` — SHA-256
  `6b56cde35a8fd0de7044a2739ed296e29dc20328b1656da35518d3a91d5449d3`;
  100,028 compressed bytes; 3.84 s, 224,648 KiB peak RSS.
- `austria-to-italy-ne-pair-terminal-first-v2.json.gz` — SHA-256
  `f0bcae08e206b5c8161186905941cb4c65a74904bc6834479dba72cb1b698154`;
  51,104 compressed bytes; 4.45 s, 210,640 KiB peak RSS.

Run from the root of the checked out PR branch, using actual retained original
source graph files. Example, with variable filenames to avoid geography
hardcoding in software:

```bash
python tools/extract_f8_region_final_edges.py \
  --manifest "$SOURCE_MANIFEST" --graph-index "$SOURCE_GRAPH_INDEX" \
  --buffer-geojson "$SOURCE_ORIGINAL_25KM_BUFFER" \
  --valhalla-config "$SOURCE_VALHALLA_CONFIG" \
  --receiver-manifest "$RECEIVER_MANIFEST" \
  --receiver-graph-index "$RECEIVER_GRAPH_INDEX" \
  --receiver-buffer-geojson "$RECEIVER_ORIGINAL_25KM_BUFFER" \
  --native-binary "$VALHALLA_363_NATIVE_SOURCE_READER" \
  --resolve-cut --output "$NONPUBLISHING_PAIR_SOURCE_CANDIDATES.json.gz"
```

## Remaining required engineering gate (not authorized to bypass)

These **local** terminal edges are not yet certified *one per actual physical
road and direction*. Some cut-intersecting nonterminal roads need more
identification, and real branch identities can differ. Next work must use
narrow, branch-preserving local Valhalla topology or mark the affected road
incomplete; **never reintroduce unbounded outward traversal**. Receiving B
match at the same native A terminal GPS **X** comes only after sufficient
A-side final-edge identity, then RoadPilot Android real A→X→B acceptance
in both directions and car/motorcycle. No catalog or release authorized.
