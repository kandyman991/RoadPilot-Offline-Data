# Rejected / Unsafe Approaches — RoadPilot Graph Studio / Offline Data

These are engineering guardrails, **not claims that all were experimentally tested**. Add confirmed failures with exact reproduction, links, observed results and reconsideration criteria. Do not confuse a historical proposal with validated implementation.

## Guardrail 1

Rejoining separately built .gph files by copying raw graph IDs/tiles is not a production seam fix.

Reconsider only with an explicit new hypothesis, tests and evidence; record the superseding decision.

## Guardrail 2

A crossing chosen only from name, heading or proximity is not VALID until proven by normal Valhalla routing.

Reconsider only with an explicit new hypothesis, tests and evidence; record the superseding decision.

## Guardrail 3

Do not restore region-specific hard-coded motorway/portal fixes or duplicate Android runtime logic in the builder.

Reconsider only with an explicit new hypothesis, tests and evidence; record the superseding decision.

## Guardrail 4

Do not claim a stale handoff's named milestone is still active without checking live code, PRs and CI.

Reconsider only with an explicit new hypothesis, tests and evidence; record the superseding decision.


## Confirmed failure — overlapping Geofabrik inputs treated as a single normal OSM snapshot (2026-10-13)

Observed: Austria configured with 18 intersecting extracts, including Austria, DACH, Alps and neighboring leaves; `osmium merge` succeeded but `osmium extract` failed with `Node ID twice in input`. Mixed snapshot versions can remain after `osmium merge` even when identical versions deduplicate. Do not call `osmium sort` a fix: Osmium sort explicitly does **not** remove duplicate objects, and it has high memory requirements.

Fix in PR #64: select geographically necessary sources using exact polygon coverage; normalize merged versions with streaming `osmium time-filter` before extracting a normal current snapshot; keep reference validation and graph-backed border proof. CI validated the former failure and corrected behavior with actual Osmium on synthetic mixed-version fixtures. User's full Austria build still needs repeat testing.

Source: https://github.com/kandyman991/RoadPilot-Offline-Data/pull/64

## Confirmed failure — OSM buffered-overlap sampling is not F8 (2026-10-14)

Real retained Italy Nord-Est/Austria graphs completed exhaustive read-only
native graph scans (7,246 window executions) but the separately invoked
OSM-way anchor stage produced over 250,000 redundant candidates and aborted,
leaving zero published native F8 crossings. Nominal-only polygon boundary
intersection yielded a zero-length MultiPoint and incorrectly accepted an
exhausted empty inventory. Raising the limit or resampling the border would
not establish graph-directed F8 parity. Source: issue #82. Retire this system;
do not re-enable it or classify old VALIDATED sidecars as source-exhaustive F8.

## Historical experiment — nominal-polygon OSM inventory cannot establish F8 frontier coverage
- **Status:** SUPERSEDED; the inventory restriction was demonstrated in source audit, but exact unobserved physical routes must not be invented.
- **Recorded:** 2026-10-24; original review 2026-10-14.
- **Objective / hypothesis:** Enumerate roadways intersecting *both nominal source polygons* and their exact shared boundary, correlate them per graph, then prove candidate pairs with Valhalla.
- **Observed limitation:** `tools/build_frontier_road_inventory.py::build_inventory()` restricted eligible OSM roads to this narrow geometry. `tools/build_crossing_candidates.py` retained combinations only from that reduced source; downstream proving cannot restore F8 alternatives omitted at inventory time. Synthetic CI passing did not prove completeness against Android's broader graph-edge/GPS frontier discovery.
- **Evidence:** [issue #73, verified implementation gap](https://github.com/kandyman991/RoadPilot-Offline-Data/issues/73), [PR #71](https://github.com/kandyman991/RoadPilot-Offline-Data/pull/71), and `docs/ARCHITECTURE_CONTRACT.md` B1–B4.
- **Decision:** Retire OSM-only nominal-boundary sampling as authoritative F8 discovery, retain any historical output for forensic use, and prove parity from actual directed native graph-edge scans on identical physical graphs. No direct cross-build GraphId equivalence.
- **Reconsider only if:** Full native F8 reference parity with exact fingerprints, motorway/one-way/local/alternate crossings, and both directions/modes is demonstrated; arbitrary OSM filters must not silently exclude graph-valid options.

## Historical experiment — capped multi-region candidate search presented without proof of whole-journey optimality
- **Status:** SUPERSEDED as production architecture; **not** a claim that a specific superior real-world route was measured and missed.
- **Recorded:** 2026-10-24; audited design as of 2026-10-14.
- **Objective / hypothesis:** Bound route-planner expense while ranking candidate graph handoff chains.
- **Implementation evidence:** [issue #73](https://github.com/kandyman991/RoadPilot-Offline-Data/issues/73) identifies PR #72 `tools/plan_multiregion_route.py` using `MAX_CHAINS=20`, 64 cached leg results and a 120-second budget. It ranked intermediate-region estimates before detailed origin and destination legs, and returned the first successful same-graph route without eligible cross-graph comparison.
- **Why unsuitable as proof:** These are legitimate **bounded diagnostic** search strategies; they cannot guarantee globally best FASTER/SHORTER journey without sound admissible pruning or a visible INCOMPLETE flag.
- **Decision:** Compare actual full start-to-destination Valhalla journey metrics across eligible alternatives, preserve completeness provenance, and keep Android F8 as fallback until [issue #73](https://github.com/kandyman991/RoadPilot-Offline-Data/issues/73) closes with real evidence.
- **Reconsider only if:** A verified cost bound and regression showing a second (not first) faster/shorter crossing, plus real Italy–Austria and multi-region results, prove correctness or explicitly label the result as budget-truncated.

## Evidence addendum — 2026-10-14 native scan completed, OSM anchor stage failed
- **Status:** CONFIRMED_FAILURE of OSM anchor generation; NOT a failure of the exhaustive read-only native graph-edge scan.
- **Evidence:** [issue #82](https://github.com/kandyman991/RoadPilot-Offline-Data/issues/82) records Valhalla 3.6.3, 3,623 shared-buffer windows per region (7,246 executions), 323,372 Italy Nord-Est and 334,973 Austria unique eligible directed edges, and 316,563 physically matching directed edge occurrences (IDs never compared as globally equivalent). The subsequent separate `build_frontier_road_inventory.py` invocation refused over 250,000 anchors and published no native F8 connection sidecars. Locally retained diagnostics: `~/RoadPilotGraphStudio/diagnostics/f8-italy-austria-validation/` (historic path, not accessible evidence in this session).
- **Root cause:** Sampling broad shared-buffer OSM road fragments every 1,500 m created massive unrelated candidates; arbitrary cap increases or nominal-polygon shortcuts could not establish directed F8 equivalence.
- **Decision:** Retain authentic read-only directed graph scan work; retire the OSM buffered-overlap/correlation producer. Separate completion tiers: scan completed does not mean correlation/proofs, Android F8 parity, end-to-end ranking or Android consumption verified.
- **Reconsider only if:** Direct matched-fingerprint F8 graph-edge comparison and full directional Valhalla proof demonstrate complete finite frontier extraction. See `docs/F8_NATIVE_PARITY_AUDIT.md` and `docs/ARCHITECTURE_GAPS.md`.
