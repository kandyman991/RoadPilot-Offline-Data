# PR #127 — bounded native source-final edge proof (9 November 2026)

**Draft source-only increment; D-017 unchanged.** It builds on the
owner-approved paired 25-km outer-buffer source selection in
`F8_PR127_PAIRED_TERMINAL_FIRST_20261109.md`. This is **not** another
connector discovery architecture, a whole-graph census, or source–receiver
matching. All B data used here are the **previously SHA-verified original
buffer footprint and neighboring identity**, never B directed-road lookup.

## Original graph-local source proof

The `--resolve-cut` command now independently reopens **every** relevant
outward/ambiguous cutoff A directed GraphId from the exact same archived
Valhalla 3.6.3 graph through its native `GraphReader`. It verifies the
unaltered GraphId, original end-node GraphId, exact original destination
coordinate X (bounded numeric encoding tolerance), and original automobile
and motorcycle access mask. It recomputes available native terminal modes
from the actual end node's **complete immediate outgoing directed edges and
Valhalla hierarchy-linked peers** (including shortcuts, which MUST NOT be
ignored). Disagreement with the initial streamed original native cut
terminal mask is a hard error. This verifies the **graph-local** last-edge
property for the modes reported, not the physical-road identity across an
unrelated fork or a matched receiver edge.

The stage records a native local terminal proof per distinct A directed
GraphId, along with actual terminal node, X, verified mode mask and the
outgoing GraphIds considered. Candidates with exact identical A GraphIds
are grouped preserving all incoming original A cut-root identities. Edges
with the **same endpoint** or end node but *different* GraphIds are ALWAYS
kept separate and explicitly reported as coincident alternative groups;
never collapse by X, road name, OSM ID, turn angle or road classification.

Each outward-cut root that still has native forward access remains in the
explicit unresolved source evidence, even if one of its car/motorcycle modes
is locally terminal. The only additional source structural proof allowed is
when the compiled original node has **exactly ONE non-shortcut immediate
native outgoing edge**, its original directed GraphId is within the
preselected pair-specific tile ring, and that exact next GraphId has no
outgoing native road edges for **all** previously continuing modes. A
shortcut, distinct ramp, parallel hierarchy continuation, multiple forks,
mode loss or nonterminal next edge **cannot** pass this single-hop gate.

Even in the unambiguous one-hop case the state means
`SINGLE_IMMEDIATE_NATIVE_TERMINAL`, **not** "unique physical-road/direction
proven". It never triggers another hop. All remaining junction alternatives
and nonterminal edges are unchanged and not suppressed. Full physical-road
uniqueness is `NOT_VERIFIED`, Graph B directed matching `NOT_STARTED`, Android
acceptance `NOT_RUN`, publication `BLOCKED`.

## Original compiled graph results — all-region logic, Italy/Austria tests

| Verified source graph property | Italy NE → Austria | Austria → Italy NE |
| --- | ---: | ---: |
| SHA-bound source A tile ring | 72 | 60 |
| Actual original shared cutoff directed edges | 1,520 | 776 |
| Outward/ambiguous root GraphIds independently read back | **820/820** | **422/422** |
| Independently proven *native end-node terminal* source roots | **381/381** | **211/211** |
| Nonterminal original source roots fully retained | 439 | 211 |
| Unambiguous structurally terminal at exactly one native hop | **38** | **20** |
| Roots still needing a physical-road / local branch determination | **401** | **191** |
| One-hop original successor GraphIds inspected (maximum) | 564 | 249 |
| Distinct A local native terminal candidate GraphIds independently proven | **505/505** | **269/269** |
| Duplicate exact native end-node identities among local candidates | 0 | 0 |
| Duplicate exactly equal GPS X among local candidates | 0 | 0 |
| Complete physical-road/direction census | NOT_VERIFIED | NOT_VERIFIED |
| B directed GraphId correlation / RoadPilot Android journeys | NOT_STARTED / NOT_RUN | NOT_STARTED / NOT_RUN |

The 401/191 remaining category is **NOT** a loss or a new discovery task:
there are 141/81 one-outgoing-but-not-terminal roots and 260/110 cases
with two or more original immediate alternatives (including hierarchy,
shortcuts and genuine branching). The 38/20 single-hop roots also remain
**unverified as physical-road identities**, although their original native
local topology is structurally resolved. These counts are for exactly this
shared region pair, not across each region's other neighbors. Actual route
coverage and physical-road completeness cannot be inferred from these
counts.

The original Italy NE historical source GraphId `737868267290` is still
retained as an exact original one-hop native terminal candidate with both
original cutoff-root references intact; no projected crossing coordinate
was introduced. Source A graphs, their package buffers, RoadPilot and
Graph B's native directed graph were not modified or matched.

## Reproducible, read-only Legion evidence

All outputs are **schema v3** and nonpublishing, full original `2026.10.13-1` Valhalla archives,
under `~/RoadPilotGraphStudio/diagnostics/f8-production/20261109/`:

- `italy-ne-to-austria-pair-local-terminal-proof-v5.json.gz`: SHA-256
  `2b88bbc1e7f965380f1d25e6a08f242c15592c58a2c8e405dbf960bd1cb57868`,
  107,624 compressed bytes, 3.85 seconds, 224,944 KiB peak RSS.
- `austria-to-italy-ne-pair-local-terminal-proof-v5.json.gz`: SHA-256
  `40e2ce17dcf767a863c4924651ae9c11d56a4c48870bbd7032153083242587c0`,
  55,065 bytes, 4.43 seconds, 210,356 KiB peak RSS.

Every source-cut seed is reconciled against the independent proof or a
preserved unresolved edge. Every locally terminal candidate has an exact
original A GraphId and mode/node/coordinate proof. Both native candidates
and all nonterminal observations are fingerprint-bound to BOTH original
archives and original buffered GeoJSONs. Tests reject stale or conflicting
root GraphIds, native end nodes, coordinates and terminal masks; preserve
mode-specific results, shortcuts, forks and coincident but distinct GraphIds;
and prohibit recursive continuation, premature physical-road `COMPLETE`,
receiver matches and publication.

## Next bounded gate

The **native graph-local** terminal candidates are now read-back verified;
this does NOT prove which candidate corresponds to each distinct physical
road and direction, especially at multibranch source junctions and level
transitions. The next step is strictly local original A **physical-road
lineage correlation** for the remaining 401/191 difficult source roots,
using retained same-node directed geometry/topology, while keeping
uncertain cases unresolved. It cannot become unbounded graph traversal,
OSM-name/way merging, B matching or per-connection route probing.

Independent review, exact-head CI and owner merge approval are required
before any merge. Source final-road coverage and Android JNI/device parity
remain acceptance blockers; PR #127 stays draft, unmerged, nonpublishing.
