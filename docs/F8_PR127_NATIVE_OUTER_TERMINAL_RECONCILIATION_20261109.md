# PR #127 — A→exact X→B: reconcile ORIGINAL outer-cutoff terminal edges

**9 November 2026; owner-directed D-017 work; original Valhalla 3.6.3
archives; PR remains DRAFT, UNMERGED, NONPUBLISHING.**

## Why this closes the previous apparent candidate gap more directly

The earlier A→X→B producer preserved **285** original cutoff *observations*
(191 Italy NE→Austria, 94 reverse) without a terminal source A edge found
within its deliberately short local successor checks. These were **never**
285 proven missing physical roads. Extending a source-root walk by another
arbitrary number of hops would violate the owner's rejection of a separate
all-path lineage/traversal discovery architecture.

On the exact same original 25-km buffers, a decisive invariant is visible:
**all 418 previously identified source edges with permitted original B
continuations end OUTSIDE their own source A 25-km buffered polygon**. The
129 recorded A terminal candidates with endpoints INSIDE their own buffered
polygon have zero confirmed B continuation. These observations suggested
directly enumerating the **actual terminal edges** already retained in
Graph A's *previously selected boundary tiles*, rather than tracing the
285 original source approach observations as if each were a missing road.

## What changed — the SAME native source reader and A→X→B command

The *existing* original Valhalla 3.6.3 C++
`tools/native-f8-boundary-final/native_f8_boundary_final_edges.cpp` reader
adds a versioned v9 option `--outer-terminal-candidates`.

For the **same** pair-specific original A outer-cutoff tile IDs already
SHA-verified and selected by the existing producer, it emits only true
**graph-local terminal directed A edges** whose original directed endpoint
X lies **outside** A's original 25-km polygon. It recomputes terminal mode
masks from the original Valhalla end-node and immediate hierarchy peers,
retaining mode bits, actual GraphId, directed geometry, road use/class,
bridge/tunnel/layer, and end-node identity. This is a terminal-edge predicate
within the already selected cutoff tiles, **not** a network traversal,
road-name/OSM equivalence, arbitrary handoff, exhaustive archive scan or
per-connection route. Edges within A's polygon or continuing in A remain
excluded from this additional terminal set. The receiving B buffered
footprint further restricts whether each original X is eligible.

The existing Python `--match-receiver` command adds an **optional**
`--reconcile-outer-terminal-edges` flag (composable with its earlier bounded
missing-root recovery). It validates the original A/B archived graph,
buffer and index SHA fingerprints before and after the run, and:

1. Uses the graph-index **tile bounds only** to verify that every original
   source graph tile whose geographic bounds intersect the region
   `receiver buffered footprint MINUS source buffered footprint` is already
   in the accepted cutoff-tile ID set. There is no extra graph-edge scan to
   perform this check. **This proves endpoint-domain tile metadata coverage,
   not that every possible long native edge originated within those tiles.**
2. Reads the new source terminal-only mode of the SAME native reader,
   validates its explicit `outerTerminalOnlyApplied` marker, pair-selected
   cutoff tile list, Valhalla version, original X outside A, and exact
   original directed GraphId/modes. It filters X to actual B buffered
   coverage. No GPS X is fabricated, shifted or projected onto unrelated B.
3. Intersects the resulting original A GraphIds with the previously
   independently verified source terminal candidates. For an existing ID,
   the original terminal mode proof, X, access and native end-node must
   agree exactly; it cannot be duplicated or overwritten. A genuinely
   missing source terminal ID is independently re-read from the original
   A compiled tile and its local terminal mask recomputed.
4. Runs every additional A terminal through the **same existing** native
   original Graph B indexed directed-shape matching at exact X, including
   correct oriented incoming geometry, bridge/tunnel/layer, and native
   immediate B outgoing car/motorcycle costing. All real B branches remain
   separate. Original A→X→B records and modes are unchanged.

The stage still exports explicit `sourcePhysicalRoadDirectionCompleteness=
NOT_VERIFIED`, `nativeLongEdgeOriginCoverage=NOT_VERIFIED`, Android
`NOT_RUN`, and `productionPublication=BLOCKED`. The 285 previously
unresolved **source-root lineage observations stay in the evidence**; they
are NOT silently relabeled as complete or collapsed into any terminal.

## Real-original 2026.10.13-1 Italy NE/Austria results

| Original source / receiver metric | Italy NE → Austria | Austria → Italy NE |
|---|---:|---:|
| Pair-specific original A source cutoff tiles scanned | 72 | 60 |
| Original A graph-index tiles intersecting X endpoint domain (all selected) | **39/39** | **29/29** |
| Original A directed edges inspected inside those approved boundary tiles | 1,816,149 | 1,582,070 |
| Native graph-local terminal A edges whose X is outside source A polygon | 608 | 349 |
| Of these, exact X also inside original B buffered coverage | **454** | **253** |
| Already independently verified in previous original A terminal register | 452 | 252 |
| **Additional original A terminal GraphIds found** | **2** | **1** |
| Original A outside-buffer terminal X with at least one B allowed outgoing | **260** | **160** |
| Newly found A terminals with B allowed outgoing | 1 | 1 |
| Newly found A terminals with unresolved B conditional/hierarchy context | 1 | 0 |
| Eligible B-candidate A finals with duplicate exact native X | 0 | 0 |
| Existing nonpublishing candidate record count (including A interior/unmatched) | 550 | 286 |
| Original A cut-root lineage observations still without a short local terminal relation | 191 | 94 |
| Full proof of all physical roads/directions, long-edge origin coverage | NOT_VERIFIED | NOT_VERIFIED |
| Android real A→X→B / catalog publication | NOT_RUN / BLOCKED | NOT_RUN / BLOCKED |

**Total:** 707 eligible native A external graph-local terminal GraphIds
in the original selected boundary tiles, **704 previously captured and just
3 additional** (not 285). Across these, **420 original A terminal candidates
have at least one native Valhalla B outgoing option** (260+160). Their total
statically permitted original B directed option references are **646**
(401+245; some source finals legitimately have multiple outgoing branches).
All source candidates have their own original GraphId and exact terminal X;
car/motorcycle permissions on every B option are retained separately.

These 707 are the complete **graph-local endpoint terminal inventory within
the approved pair cutoff tiles**. The geographic domain metadata check
covers 39/29 of 39/29 eligible original A tiles. But an exceptionally long
native directed edge could be owned by an origin tile outside the selected
boundary tile set, and the physical identity of each branch is not fully
established by geometry alone. Therefore do NOT elevate this to a complete
per-physical-road/direction proof or automatically publish a catalog.

### Three exact additional original source cases

- Italy NE→Austria A original `61746485498`, X
  `(47.2733638, 11.8681338)`: original B native outgoing GraphIds
  `89529555194`, `89563109626`, both car/motorcycle bit set. Distinct
  branches retained, no best-turn selection.
- Austria→Italy NE A original `14166266370`, X
  `(46.5623603, 12.1315422)`: original B directed GraphIds
  `226867810818`, `226901365250`, both car/motorcycle permitted.
- Italy NE→Austria original `273743375322`, X
  `(47.1352745, 10.9316853)`: aligned original B predecessor
  `348435540954` found, but native outgoing legality remains partially
  unresolved. **NOT a confirmed handoff.**

The previously recorded 833 A terminal candidate GraphIds (704 external plus
129 internal, including the 59 recovered by the bounded two-hop source
check), their exact native X, permissions and B options all remain
unchanged. The new total is 836 original graph-local candidates including
non-handoff interior records; 707 have terminal X in the approved A-exterior
B-covered region. There are no duplicate exact X coordinates among those
707 eligible terminal GraphIds.

## Immutable Legion evidence and regression gates

Original read-only matched outputs:

- `~/RoadPilotGraphStudio/diagnostics/f8-production/20261109/italy-ne-to-austria-outer-terminal-match-v2.json.gz`
  SHA-256 `af1c5985f673bc6075fe0ca600204bc797d6d9e964c44343859786cb1ff6e357`
  (98,829 bytes); matching runtime ~8.05 seconds, ~278,176 KiB peak RSS.
- `~/RoadPilotGraphStudio/diagnostics/f8-production/20261109/austria-to-italy-ne-outer-terminal-match-v2.json.gz`
  SHA-256 `821c7c5140b9c865bd3df48e343e249b3e538fc4db615e03e1d5b5554f611634`
  (52,145 bytes); runtime ~8.67 seconds, ~267,780 KiB peak RSS.

**Native C++ Valhalla 3.6.3 Release build PASS**. **419 Python tests PASS**
including new original A terminal identity, no duplicate candidate,
metadata domain coverage and failure-closed original terminal mode tests.
The two real original A/B pair evaluations reconcile exactly: no earlier
original GraphId/X/vehicle-mode/B-option changes or losses, no source root
silently removed. No RoadPilot APK, mobile JNI compatibility, full journey,
Graph Studio published catalog or release was tested or changed.

## Next acceptance gates — NO architecture change

The A→X→B stage now produces a complete match/candidate account **for
all graph-local A terminal edges within the selected pair-cut source tiles**.
Before D-017 can be marked complete, determine whether actual original A
long edges owned in neighboring tiles can end in the verified endpoint
domain, resolve any native physical-road branch ambiguity that changes
handoff identity, verify Android ingestion/actual cross-region journeys on
matching graph fingerprints, and wire the validated versioned adapter into
the standard graph-build workflow. Do not reintroduce OSM sampling,
independent B-side Y coordinates, entire-graph road census, per-connection
Valhalla route proofs, route preference or a new discovery pipeline.
Keep PR #127 DRAFT and UNMERGED pending independent review, exact-head CI,
and owner authorization. Android publication remains BLOCKED.
