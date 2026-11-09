# PR #127 — source-only native immediate edge costing (9 November 2026)

**Draft and NONPUBLISHING; D-017 unchanged.** This increment does not build
new crossing discovery, route all journeys, or inspect any receiving B
**directed road**. It operates on exactly the previously verified A cut roots
and their incident edges from the pair's original Valhalla 3.6.3 archive.
Graph B participates *only* through its SHA-verified 25-km coverage polygon
and pair identity, as already required for selecting the shared A cutoff.

## Why native costing was tested

The previous 401/191 structurally ambiguous source roots could not safely
be assigned a unique physical forward road from same-node geometry alone.
We examined the exact native `AutoCost::Allowed` and
`MotorcycleCost::Allowed` implementations in Valhalla **3.6.3**; they
already implement mode access, U-turn exclusions, immediate simple turn
restrictions, surface and vehicle restrictions, and other costing rules.
But a *normal route* picks a preferred path and can omit other valid forks.
Neither its preferred route nor a legal turn establishes **same physical
road** identity or proves all crossings. Do **NOT** use either as a complete
road-lineage proof.

## Implementation, strictly bounded to ONE junction

The existing native C++ source reader (`tools/native-f8-boundary-final`)
adds a versioned **v6** optional mode when reading the already selected
source edge and its immediate original directed incident edges:
`--local-continuations <original-config> <original-source-ids>
--evaluate-native-costing`. It constructs the original predecessor
`EdgeLabel` and calls the real Valhalla default car and motorcycle
`Allowed()` methods for **same-node, direct, one-edge transitions only**,
without running a route search or traversing another graph edge.

For every original immediate incident GraphId and vehicle mode the reader
reports one of:

- `ALLOWED_NATIVE_IMMEDIATE`: Valhalla's default **one-step** costing
  returns allowed *without* an identified missing special path/time context.
- `DENIED_NATIVE_IMMEDIATE`: Valhalla one-step costing denies this turn.
- `NO_MODE_ACCESS`: either source or next directed original edge lacks
  this mode's native access bit.
- `UNRESOLVED_SHORTCUT`: a compiled shortcut may represent another
  original/underlying edge; never equate it to a physical-road terminal.
- `UNRESOLVED_HIERARCHY_CONTEXT`: the next edge is accessible through a
  native hierarchy-peer transition, not a same-level directed turn.
- `UNRESOLVED_PATH_OR_TIME_CONTEXT`: complex turn restrictions, conditional
  access, destination-only or other path/time-dependent state requires a
  real route history or clock, which the bounded one-node view does not have.

The costing is from **default costing options with `current_time=0` and
without a prior full route history**. It is NOT an all-date, all-profile,
full-path legal route certificate. A positive result means only that the
*immediate static context* is allowed by the actual Valhalla costing rules;
it does not assert actual later routing success, source road identity, or
that a valid crossing exists in graph B. Conservatively unknown cases are
never silently treated as allowed or denied.

The Python source extractor records `nativeImmediateCosting` under
**every** original immediate outgoing option. It validates the v6 native
reader protocol, recognizes only the declared statuses and fails closed
if a requested legal assessment is missing. It **does not delete, merge,
rank or prefer any edge based on the new status**: real ramps, hierarchy
alternatives, mode-specific permissions and original GraphIds remain intact.
The catalog still says `sourcePhysicalRoadDirectionCompleteness=NOT_VERIFIED`,
`receiverCorrelation=NOT_STARTED`, `androidFullJourneyValidation=NOT_RUN`,
`productionPublication=BLOCKED` (nonpublishing schema version 4).

## Original compiled source graph observations

Original archive versions `2026.10.13-1`, both directions; original
Valhalla 3.6.3 native release binary compiled and all candidate records
reconciled on Legion. Costs count **immediate incident edges**, not distinct
physical roads. The observed native car and motorcycle statuses happened
to match for this selected pair; they remain separate fields.

| A source-side result | Italy NE → Austria | Austria → Italy NE |
| --- | ---: | ---: |
| Original pair-shared cutoff A tiles | 72 | 60 |
| Original outward/ambiguous source root GraphIds | 820 | 422 |
| Nonterminal roots with native costings inspected | 439 | 211 |
| Total preserved immediate incident alternatives | 706 | 327 |
| `ALLOWED_NATIVE_IMMEDIATE` per mode | 527 | 251 |
| `UNRESOLVED_HIERARCHY_CONTEXT` per mode | 71 | 33 |
| `UNRESOLVED_SHORTCUT` per mode | 47 | 33 |
| `UNRESOLVED_PATH_OR_TIME_CONTEXT` per mode | 61 | 10 |
| Confirmed `DENIED_NATIVE_IMMEDIATE` per mode | 0 | 0 |
| Roots with exactly one positive immediate option | 146 | 79 |
| Roots with **two or more** positive immediate options | **188** | **84** |
| Roots without any positive immediate option (may be unknown) | 105 | 48 |
| Distinct proven *graph-local terminal* A GraphIds | 505 | 269 |
| Unique one-hop structurally terminal roots (unchanged) | 38 | 20 |
| True unique final physical-road/direction proof | NOT_VERIFIED | NOT_VERIFIED |

The many multi-positive junctions demonstrate that **Valhalla's legal-turn
costing cannot, by itself, identify one unique physical road per direction**.
Selecting the best-scoring edge or treating a missing context as a dead end
would be architecturally incorrect. There is no count reduction merely
for passing a legal turn: all 439/211 source nonterminals and all 505/269
native terminal candidates remain retained. No source network traversal,
Graph B directed matching or RoadPilot Android acceptance was performed.

### Reproducible nonpublishing evidence

Read-only generated original outputs under the Legion directory:
`~/RoadPilotGraphStudio/diagnostics/f8-production/20261109/`.

- `italy-ne-to-austria-native-legal-source-v2.json.gz`
  SHA-256 `ec481a2aa6309b26347bd63d8324a8761eb93c2b869112f4fd455875c132a495`,
  108,093 compressed bytes, 3.89s, 226,000 KiB peak RSS.
- `austria-to-italy-ne-native-legal-source-v2.json.gz`
  SHA-256 `0c846fb07bec8cf7b78f92110a5870e97d182d2289fe712f32cbaf343258e2e4`,
  55,354 bytes, 4.43s, 211,368 KiB peak RSS.

The new unit regression covers unknown, allowed, denied and no-access
statuses, preservation of separate forks, the strict status schema and the
explicit failure of native protocol mismatch. The original 407+ Python
suite, Valhalla native C++ compilation, actual original A node read-back
and paired source-only real-graph runs are the relevant verification gates.

## Exact next step

Keep PR #127 **DRAFT and UNMERGED**. Use the new local legal-turn evidence
only to distinguish known illegal edges from possible local continuity and
to locate the actual still-ambiguous source junctions; retain hierarchy,
conditional and history-dependent cases as unresolved. Any identification of
same physical road/direction must still use authoritative original A directed
geometry, local topology and branch identity, not prefer Valhalla's best
route or a geographic-nearest road. Prove source coverage before introducing
**any** Graph B directed-road matching, catalog publishing or Android parity
claim. Independent review and exact-head CI are required.
