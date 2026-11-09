# PR #127 — original graph A → exact X → native graph B matching

**9 November 2026, draft/nonpublishing engineering increment.** Product-owner
approved moving directly to A→X→B using the independently verified original
A terminal candidates and only bounded source coverage checks, rather than
building another source-road classification/discovery architecture. This
implements the **receiver look-up and native candidate-correlation portion**
of D-017, NOT a complete publishable cross-region catalog. No Android
packages, source/receiver graph archives, 25-km overlap footprints or legacy
producers are modified.

## Exact D-017 sequence implemented

1. **A:** Reuse the original `--resolve-cut` candidate evidence (source schema
   v5) from the two SHA-verified original regional Valhalla **3.6.3** archives.
   Every original terminal-candidate A GraphId, end-node identity, X and
   modes is independently re-read through the same native `GraphReader`.
   Recompute the A graph-local terminal modes and original complete native
   end-node adjacency; reject stale/false `VERIFIED` claims and fingerprint
   mismatches. No new or exhaustive source census occurs.
2. **X:** Pass exactly the A final candidate's original native terminal GPS
   (lat, lon). **No second GPS Y** is generated, shifted, or stored.
3. **B at X:** New v8 `--receiver-at-x` native reader uses Valhalla's own
   spatial bin/index `CandidateGridQuery::RangeQuery` at X, with a **4-metre
   candidate radius only**. Native bins include original long B directed
   edges even when their originating tile differs from the tile containing X.
   Explicitly inspect both original directed orientations; no whole-graph
   enumeration, graph-ID equality comparison, road-name/OSM ID matching,
   shortest-route preference or arbitrary coordinate relay.
4. **Reject unrelated B directions:** The original A last distinct approach
   vertex and exact X must both lie within **0.75 metres** of the same
   *oriented* original B directed geometry, in **forward order** by at least
   1 metre, with no opposing directed travel. Original native layer,
   bridge/tunnel information must not conflict for an unambiguous match;
   road class/use differences are **retained as attributes**, not used as
   a strict identity equality. An unrelated nearby parallel or intersecting
   road, a reversed edge, or missing source approach cannot be accepted as
   an established directed geometric overlap.
5. **B may end its incoming edge at X:** In actual compiled archives,
   a B edge geometrically corresponding to the last A approach often ends
   at X, even though a different B directed edge starts at X. The producer
   therefore reopens **only** those geometrically verified original B
   predecessor GraphIds through the existing native `--local-continuations`
   command. It validates their original native B endpoint node and X,
   then reads **immediate** same-node directed outgoing B GraphIds. Valhalla
   `AutoCost::Allowed` and `MotorcycleCost::Allowed` supply the native static
   legal turn status per mode. Each positive B original directed GraphId is
   retained; distinct ramps/branches are **not** ranked, merged by GPS,
   collapsed or suppressed. Shortcuts/hierarchy, conditional/complex
   restrictions or missing path/time context stay explicitly unresolved.
6. **Coverage in the same step:** Reconcile all 820/422 original outward or
   ambiguous source-cut roots to the existing source terminal-candidate
   associations and detected native B options. Roots lacking any final
   candidate within the approved one-source-hop scope remain explicit;
   missing/uncorrelated source roots are NOT excluded from completion gates.

The `--match-receiver` action is on the **same** region-independent
`tools/extract_f8_region_final_edges.py` source/receiver producer. It accepts
`--source-evidence` from `--resolve-cut`, the six original A/B SHA-bound
manifest/index/buffer paths, both Valhalla configs, the version-pinned
native binary, and a nonpublishing `--output`. It refuses a stale A source
artifact, mismatched original B archive, repeated directed GraphIds,
incomplete native output, inconsistent A end-node/terminal modes, wrong B
node ownership, or any attempt to overwrite evidence. All retained output
is bound to BOTH original graph/index/buffer fingerprints and the exact
source-evidence SHA-256.

**Important meaning of a native B option:** The last A road segment overlaps
B's original *incoming* road segment in the same direction and Valhalla
permits a B original **outgoing** edge at the same original B node X.
This establishes a plausible static **A→X→B directed handoff** with native
GraphIds and vehicle permissions. A turn at a complex fork does not on its
own establish that every outgoing branch is the *same physical road* as A.
Therefore the catalog remains blocked until full source final/direction
coverage, any physical-branch identity ambiguities, and Android consumption
are resolved. No best-route ranking is used.

## Real original Valhalla 3.6.3 Legion graph results

Immutable archive version `2026.10.13-1`, Italy Nord-Est/Austria in BOTH
travel directions. The same region-independent algorithm is used; no Italy-
or Austria-specific matching cases or hardcoded coordinates.

| Original graph evidence | Italy NE → Austria | Austria → Italy NE |
|---|---:|---:|
| Verified original A graph-local terminal candidates matched at X | 505 | 269 |
| Original B geometrically overlapping predecessors re-read | 505 | 269 |
| Source candidates with ≥1 original permitted B directed successor | **257** | **155** |
| Source candidates with 2+ permitted B outgoing options (ALL preserved) | 128 | 79 |
| Total original B directed successor options | 395 | 237 |
| Candidates with native B options and no unresolved costing context | 241 | 150 |
| Candidates with no confirmed original B outgoing continuation | 203 | 92 |
| Candidates with at least some unresolved B context | 61 | 27 |
| All outward/ambiguous original A-cut roots accounted for | 820 | 422 |
| Source roots associated with ≥1 terminal candidate with native B options | 302 | 175 |
| Source roots with local terminal candidate but no proven B option | 255 | 118 |
| Source roots with no identified terminal candidate in bounded one-hop view | **263** | **129** |
| Actual unique physical-road/direction source completeness | **NOT_VERIFIED** | **NOT_VERIFIED** |
| Android A→X→B JNI parity / release | NOT_RUN / BLOCKED | NOT_RUN / BLOCKED |

**The last 263/129 observations are not automatically 392 different roads.**
They can include different approach observations, unfinished source
continuations and branches. The exact original source roots and every
existing terminal candidate remain retained. Both A and B archives were
read only, and original A/B GraphIds are never compared as numerical
identities. The original B alternatives include B classes, use, native
layer/bridge/tunnel, original vehicle permissions and the exact predecessor
node chain at X, but do not introduce B-side GPS coordinates as handoff
locations.

Example original source A GraphId `6307642`, X = (46.7547812,
13.7585482): independent original Austria graph native spatial lookup
found the same **oriented incoming road geometry at X**. After original
B predecessor GraphId `6307642` (the numeric equality is coincidental and
**not** used for matching), native B same-node legal continuation returned
**two** directed original receiver GraphIds `408960826` and `442515258`,
car/motorcycle mode mask `1025` on both. Both are retained rather than
picking Valhalla's preferred route. Another source candidate in reverse
Austria→Italy NE (source original A GraphId `67502073`) has two original
B successor options with different original vehicle masks, `1024` and
`1025`, which are preserved separately.

## Reproducible nonpublishing original data

All generated outputs are immutable **read-only, local evidence** on Legion:
`~/RoadPilotGraphStudio/diagnostics/f8-production/20261109/`.

- `italy-ne-to-austria-receiver-at-x-v4.json.gz` — SHA-256
  `40121e8f9c1c5a9be89335f0a3d60180e57030e77680b6a005dd4d4812364cac`,
  original 505 A final candidates and 820 source-cut roots, 85,619 bytes,
  4.35 seconds, ~158,084 KiB peak RSS.
- `austria-to-italy-ne-receiver-at-x-v4.json.gz` — SHA-256
  `f6947903a74ff03c69d08b4658d5736192c208ffcf4b81e99f024fd307aec5df`,
  original 269 A candidates and 422 source-cut roots, 46,420 bytes,
  3.97 seconds, ~108,220 KiB peak RSS.

Both were reproduced using the approved region-independent `--match-receiver`
CLI, original manifest-bound A and B archived `.tar` graphs, matching original
index and original 25-km buffer GeoJSON. Native C++ Valhalla 3.6.3 Release
build and **414 Python tests** PASSED; synthetic regressions reject
opposite direction, proximity-only parallel/crossing edges, grade-separated
layer, fake source-native terminal masks, node mismatches and unauthorized
mode access. No Android journey, GUI build acceptance or source physical-road
completeness proof is claimed.

## Next exact engineering gate

**No new source classification framework.** Focus only on source-root
observations that do not yet have a final retained A edge, and the B native
junction/mode ambiguities that affect actual candidate connections. Respect
the already approved bounded local topology and preserve genuinely distinct
roads/ramps and all unconfirmed alternatives. Do not expand into full-graph
traversal, route-preference matching, extra handoff coordinate Y or
per-connection proof routes. Only after complete source coverage and real
RoadPilot Android A→X→B journeys on identical original fingerprints may the
catalog/publisher be considered for acceptance. PR #127 remains DRAFT,
UNMERGED, and NONPUBLISHING pending independent review, exact-head CI and
owner merge authorization.
