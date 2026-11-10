# PR #127 — A→exact X→B: reconcile ORIGINAL outer-cutoff terminal edges

**9 November 2026; owner-directed D-017 work; native reader v10; original Valhalla 3.6.3
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
adds a versioned v10 option `--outer-terminal-candidates` with the exact original receiving B footprint as a read-only attestation input.

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
   not by itself proof about long native edge origins. Those origins are now
   checked independently using exact Valhalla native opposing edges at the
   B-covered exterior A destination nodes, as described below.**
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
NOT_VERIFIED`, `nativeLongEdgeOriginCoverage=
VERIFIED_FOR_ORIGINAL_PAIR_ENDPOINT_DOMAIN`, Android `NOT_RUN`, and
`productionPublication=BLOCKED`. The 285 previously
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
| Eligible native B-covered exterior A end nodes independently inspected | **1,023** | **629** |
| Original incoming native edge references at those nodes verified | **1,063** | **541** |
| Eligible A incoming GraphIds owned by unselected origin tiles | **0** | **0** |
| Long-edge origin ownership coverage in exact B-covered exterior A domain | VERIFIED | VERIFIED |
| Per-physical-road/direction final-edge identity and Android acceptance | NOT_VERIFIED | NOT_VERIFIED |
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
covers 39/29 of 39/29 eligible original A tiles. Native v10 independently
verifies the original incoming edge GraphId owning tiles for all B-covered
exterior A end nodes using Valhalla's exact opposing-directed-edge links,
including one-way-inaccessible reverse edges. **No eligible long source
edge origin was missed in either pair.** Physical identity of each fork
and RoadPilot Android consumption are still not established by this
native adjacency proof; do NOT automatically publish a catalog.

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
  Original v9 output SHA-256 `af1c5985f673bc6075fe0ca600204bc797d6d9e964c44343859786cb1ff6e357`
  (98,829 bytes). **Current attested v10** output:
  `italy-ne-to-austria-outer-terminal-match-v3.json.gz`, SHA-256
  `b9f00d91aa11e68b58fc1ab9c03ab1f2cd64835dd643d05967a9e2af6eeef399`
  (98,925 bytes); ~9.01 seconds, ~278,020 KiB peak RSS.
- `~/RoadPilotGraphStudio/diagnostics/f8-production/20261109/austria-to-italy-ne-outer-terminal-match-v2.json.gz`
  Original v9 output SHA-256 `821c7c5140b9c865bd3df48e343e249b3e538fc4db615e03e1d5b5554f611634`
  (52,145 bytes). **Current attested v10** output:
  `austria-to-italy-ne-outer-terminal-match-v3.json.gz`, SHA-256
  `0eeacdcac1c8e2b552a15ec2f18d761a71091fd9635de8280b8346ea3db2efa7`
  (52,225 bytes); ~9.98 seconds, ~267,908 KiB peak RSS.

**Native C++ Valhalla 3.6.3 Release build PASS**. **420 Python tests PASS**
including new original A terminal identity, no duplicate candidate,
metadata domain coverage and failure-closed original terminal mode tests.
The two real original A/B pair evaluations reconcile exactly: no earlier
original GraphId/X/vehicle-mode/B-option changes or losses, no source root
silently removed. No RoadPilot APK, mobile JNI compatibility, full journey,
Graph Studio published catalog or release was tested or changed.


## v10 additional original native opposing-edge completeness proof

The previous v9 metadata-only tile coverage left open a possibility of a
long original A edge **ending in** the A-exterior/B-covered area but
**starting from a source tile outside the approved cutoff tile set**.
Native `GraphReader::GetOpposingEdgeId` closes that specific gap without
changing the architecture or scanning additional source tiles. At every
original pair-selected A node X geographically outside A original 25-km
buffer and inside B original 25-km coverage, the SAME native boundary
reader iterates that node's immediate incident outgoing edges. It
reverses each through Valhalla's exact native opposing directed GraphId,
verifies the corresponding incoming original A directed edge really ends
at THIS node, checks original car/motorcycle access, and confirms the
incoming edge's **owning graph tile** belongs to the original selected
pair-cut tile IDs. Crucially, even inaccessible opposite orientations of
one-way roads are checked, so a true one-way incoming road is not missed.

**Legion original A native evidence:**

| Original native check | Italy NE → Austria | Austria → Italy NE |
| --- | ---: | ---: |
| Eligible original A exterior nodes inside B coverage | 1,023 | 629 |
| Eligible incoming A original directed edge references checked | 1,063 | 541 |
| Eligible incoming A edge origin tiles NOT in original pair-selected cutoff | **0** | **0** |
| Native terminal A candidates/allowed B branches changed | 0 / 0 | 0 / 0 |

An additional *read-only, broader* scratch check originally saw three
Italy NE source incoming original GraphIds whose origin was outside the
selected pair-cut source tiles: `770986434114`, `774241214018`,
`775650500162`. All their exact end X were **outside Austria's original
receiving footprint**, so they are not eligible Italy NE→Austria A→X→B
handoffs. The B-covered production-native check records zero missing
eligible origin identities, both directions.

The v10 native stream includes explicit native opposing-edge-check
acknowledgment and original node/reference/missed-origin counts. The
Python producer **fails closed** if these fields are missing, malformed,
or if any eligible long native incoming A GraphId is owned by an
unselected source tile. No extra tile is silently read or published.
This validates all original source endpoint **origin tiles** for the
scoped A-exterior/B-covered area; it does not certify that every native
terminal is the final edge of a **distinct physical road and direction**
or that an Android route can traverse its receiving branches. The
v10 attested outputs preserve *exactly* all prior A/B candidate contents.

## Next acceptance gates — NO architecture change

The A→X→B stage now produces a complete match/candidate account **for
all graph-local A terminal edges within the selected pair-cut source tiles**.
The exact B-covered exterior endpoint native long-edge owning-tile check is
now **VERIFIED** on the original two graph pairs. Before D-017 can be marked
complete, resolve any native physical-road fork/branch ambiguity that changes
handoff identity, verify Android ingestion/actual cross-region journeys on
matching graph fingerprints, and wire the validated versioned adapter into
the standard graph-build workflow. Do not reintroduce OSM sampling,
independent B-side Y coordinates, entire-graph road census, per-connection
Valhalla route proofs, route preference or a new discovery pipeline.
Keep PR #127 DRAFT and UNMERGED pending independent review, exact-head CI,
and owner authorization. Android publication remains BLOCKED.
