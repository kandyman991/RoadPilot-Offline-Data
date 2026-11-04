# F8 native original graph branch lineage and real A→X→B route evidence

2026-11-04 · RoadPilot Graph Studio · *stacked development after draft PR #119*.

**Result:** Authentic Valhalla 3.6.3 original TripLeg identities and native GraphReader graph-level branch topology are verified on EIGHT scoped Italy Nord-Est ↔ Austria regional-core journeys (Car/Motorcycle in each direction). Two journeys also have locally aligned source/receiver directed tangents; six have opposed tangents and remain unproven as physical handoffs. **This does not establish a complete unique-final-edge-per-physical-road/direction catalog or a generally legal cross-region transfer.** No connectivity publisher or Android code was changed.

## What was actually implemented

1. The native Valhalla 3.6.3 GraphReader read-only endpoint executable now supports an **opt-in** --lineage command. For each nominated original TripLeg directed GraphId it emits the actual graph-local end node, original opposing reverse, every direct outgoing edge (including road branches, ramps, nonroad and shortcuts, with original mode-access masks), and every reachable Valhalla hierarchy-level transition node plus that node's **complete** outgoing inventory. Graph level transitions are traversed without mistaking them for physical driving edges or performing OSM name/way grouping. The old --continuations and --geometry behaviors remain intact.
2. tools/prove_native_f8_original_core_journeys.py takes an explicit, SHA-verified *bounded list* of route hypotheses. Every source-final GraphId must be present in PR #119's **source-complete unfiltered** native terminal ledger. Origins are within the pinned unbuffered source country core, destinations within the pinned unbuffered receiving core. Graph archive, immutable census-page, buffer, core-polygon and native binary identities are checked before execution, graph archives and inputs checked again afterward. Native binaries must be SHA-pinned **before** invoking --version or any route.
3. Valhalla routes source-core → exact native A terminal X, using the **original** TripLeg protobuf directed GraphIds. The *last* A edge must be the nominated GraphId with actual terminal snap within 1 m. For the complete original A route, GraphReader must prove each successive directed edge is present in the end node's **actual outgoing arcs**, directly or via a real graph hierarchy transition; edge mode-access masks are checked, and every alternative branch is retained in the evidence. A missing/false transition or another final GraphId remains **UNPROVEN**, never an exclusion from discovery.
4. The actual A route endpoint is the F8-normalized B start. Valhalla then routes that position inside the **independent original receiving graph** to a real receiving-core destination. Its original first B GraphId comes from the original B TripLeg, independently validated against GraphReader and checked throughout the full B route's branch/hierarchy sequence. A and B GraphId numeric values are **never compared to one another** as identity.
5. Only a locally observed source-final/B-first **directed tangent match** (cosine at least 0.85 with native shapes, handoff/snap within 1 m and correct A/B mode bits), plus all original topology and endpoint checks, gives the scoped label TWO_ORIGINAL_GRAPH_LOCAL_LEGS_AND_DIRECTED_SEAM_GEOMETRY_ALIGNED_ONLY. Opposed/ambiguous cases remain TWO_ORIGINAL_GRAPH_LOCAL_LEGS_BUT_TRANSFER_UNPROVEN. These labels are *observations*, not legal cross-region turns, optimal routes, final physical-road unique equivalence classes, or publishable sidecars.

## SHA-verifiable original native provenance

- Source archive Italy Nord-Est 2026.10.13-1: sha256:e6a10d36f8622ac0e47dc3d17a8295f60b144f9a2ad478e1b5f6ef2dbea75953.
- Source archive Austria 2026.10.13-1: sha256:ee7baac93b639d0c2fefab8f90540d26d03fd28a283c73bff516a1d8bdc2bc7b.
- Full PR #119 source-complete terminal ledger page: sha256:18fab3789c02bd1c6abd7f65a0433045f0f7f97ae8d0269280e947d1f1e63dd3.
- Original Valhalla TripLeg route executable: sha256:e955677e56278b53cee0d39ca6d94efa1557e1439da81859f330ffb4b8dbe776.
- New local hierarchy GraphReader executable: sha256:74ed43ecff2cbffbffeb737381646561615d764c1468153f36c9ee8fc1f5f372. Exact C++ source sha256:af7534f5555112978d950cd08a2caf99a5631660fe8dfef2edbe6d9dbae1f3e3. Reviewable build recipe, libvalhalla static archive and compile cache details: docs/F8_PR120_ORIGINAL_BRANCH_BUILD_PROVENANCE.json. This is a **Legion local native binary**, not a hosted-GitHub native build or independent third-party review.
- Full original real proof report (21.7 MB, retained outside Git, *immutable*):
  ~/RoadPilotGraphStudio/diagnostics/f8-production/20261104/original-branched-core-to-core-eight-brenner-v3.json
  SHA-256: **5a570d50cf31abf4d2a8c331529aa8e84b1b7fcaf2db5a7e30feae0be8e031c0**.
- Original explicit eight-case input:
  ~/RoadPilotGraphStudio/diagnostics/f8-production/20261104/original-core-to-core-eight-case-brenner-witnesses.json.
- Start/end sample area: **Bolzano** (inside original Italy core) and **Innsbruck** (inside original Austria core), in both directions. Route metrics are Valhalla's real per-leg duration/distance, summed as observed two-leg cost **only**, not a global optimality comparison.

## Results from original graph-local journeys

| Original source direction | Mode | Nominated A final GraphId | Original B first GraphId | Full native topology and destination | Directed seam observation |
| --- | --- | ---: | ---: | --- | --- |
| Italy → Austria | Car | 364870918424 | 229076132120 | Pass | Aligned tangent (+1.0), scoped witness |
| Italy → Austria | Motorcycle | 364870918424 | 229076132120 | Pass | Aligned tangent (+1.0), scoped witness |
| Italy → Austria | Car | 1329097370602 | 1642965527530 | Pass | Opposed tangent (−1.0), unresolved |
| Italy → Austria | Motorcycle | 1329097370602 | 1642965527530 | Pass | Opposed tangent (−1.0), unresolved |
| Austria → Italy | Car | 4636807666 | 1497473487346 | Pass | Opposed tangent (−1.0), unresolved |
| Austria → Italy | Motorcycle | 4636807666 | 1497473487346 | Pass | Opposed tangent (−1.0), unresolved |
| Austria → Italy | Car | 1549799922 | 1487574929906 | Pass | Opposed tangent (−1.0), unresolved |
| Austria → Italy | Motorcycle | 1549799922 | 1487574929906 | Pass | Opposed tangent (−1.0), unresolved |

**Every one of these eight explicitly nominated core→A terminal and X→receiving-core route pairs succeeded with original TripLeg IDs.** All original route-edge pairs are native GraphReader-contiguous (counting hierarchy transitions): **5,404 direct node arcs + 52 true Valhalla hierarchy-level arcs**, zero missing/mode-inaccessible route arcs, and **2,484 visited mode-accessible branch observations** recorded (branch counts repeat across cases/modes; do not call them unique physical junctions). Original Valhalla B first directed edge, both original route costs and end arrival are included per case. Handoff A→B actual coordinate gaps were 0 m for all eight.

**Critical false-negative recovery:** Austria GraphId **4636807666** had failed PR #119's isolated short edge-start→terminal route test for both modes. A *real original route from Austria's country core to the same final GraphId* succeeded for both Car and Motorcycle, with the correct final original TripLeg edge and complete native branch topology. The earlier negative witness did **not** prove it was an unusable road; the source-complete ledger correctly kept it.

### Limitations that prohibit declaring a physical crossing finished

- The two aligned cases demonstrate native directed **local tangents** and original independent legs, not continuous one-to-one *physical road geometry*: the source-final 20-m tail is **not entirely covered by the selected B first directed segment** (20 m maximum tail gap in the scoped report), and a matching original B route may need more receiving edges or a different subdivision. Original A/B road-to-road identity is **not globally established**.
- Six completed two-leg journeys have opposed directed seam tangents. Their successful Valhalla routes and 0-m coordinate gaps **do not establish physically legal forward transfers**; no vehicle should treat them as a verified handoff.
- These journeys use a small *explicit nominated* sample, not every branch, every native final road/direction, every source-core entry, every receiver alternative, Austria–Germany/multi-hop, or global FASTER/SHORTEST best-route comparison.
- The source and receiving unbuffered Geofabrik core polygon files are explicitly hash-pinned but not tied by the graph's immutable build manifest to a source-border snapshot. This is still a data provenance gap.
- **No actual Android end-to-end journey was tested** in this Graph Studio increment. Android PRs #540/#541 provided scoped JNI/Kotlin **candidate set parity**, not these eight complete journey/route cost results on a physical phone. Graph Studio #73/#82 and Android #512 remain OPEN.
- No cross-graph turn legality is considered proven solely by two separate routing engines. Full physical-road directional lineage with branches and per-mode transfer evidence needs source→seam geometric equivalence and B multi-edge coverage before sidecar production.

## Next hard production gates

1. Establish **complete** branch-aware physical-road/direction classes for the **entire 25-km shared area**, not merely selected core-to-terminal journeys, preserving distinct ramps, separate carriageways and mode-stranded native edges. Avoid grouping by road names/way IDs or requiring identical graph subdivision.
2. For every actual crossing, prove the original A→X final GraphId and the B-side *ordered chain* of original directed edges across the same physical road, with consistent heading **through** the overlapping segment, including graph-level transitions, legal turn restrictions, both vehicle modes and both travel directions. Report ambiguous or unproved candidates rather than discarding them.
3. Verify full A→X→B journey arrival, all plausible alternatives and both FASTER/SHORTER full-route metrics on exact matching graph packages, then instrument actual Android JNI/native routes on emulator **and physical Android** against the same immutable graph bytes.
4. Only after independent review, exact-head CI, source and Android parity, fingerprint-bound package ingestion/rollback and explicit owner release approval may Graph Studio publish connectivity. No existing F8 fallback is modified by this PR.

**Architecture preserved:** independent regional graphs, original Valhalla TripLeg IDs, full F8 GPS candidate stream, zero first-success lock-in or region-cross GraphId equality, no legacy OSM/connector/matrix producer, all remaining work marked NOT_VERIFIED / BLOCKED.
