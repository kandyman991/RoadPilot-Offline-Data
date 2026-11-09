# Open architecture gaps — not yet proven compliant

These explicitly declared legacy gaps make the contract honest while safeguards are introduced. They are NOT acceptance or approval to make the same mistake again.

| Gap | Present evidence | Required closure | Tracking |
| --- | --- | --- | --- |
| G-F8-01 — Discovery source parity | The old OSM buffered-overlap/correlation producer executable files are already absent from tracked Graph Studio source; retained historical inspection/validation readers are separate. Historical OSM outputs are NOT equivalent to actual Android F8 directed graph-edge discovery. The uncapped native graph scanner remains an independent port, not Android reference proof. | On identical physical Valhalla graphs, enumerate F8 graph-edge results, compare all candidates, resolve or flag gaps, retain provenance. | https://github.com/kandyman991/RoadPilot-Offline-Data/issues/73 |
| G-F8-02 — Premature route alternative stopping | The obsolete bounded multi-region planner executable file is already absent from tracked Graph Studio source; whole-journey multi-hop ranking still needs a new F8-compliant implementation. Previous capped-search success did not prove an optimal result. | Whole-journey alternative comparison with sound pruning, or unambiguously mark route search INCOMPLETE and retain F8 fallback. | https://github.com/kandyman991/RoadPilot-Offline-Data/issues/73 |
| G-F8-03 — Device consumption | Graph Studio sidecars have not been proven installed and used in RoadPilot Android. | Fingerprint verified package ingestion and route equivalence in real Italy/Austria/Germany device tests, with rollback and F8 fallback. | https://github.com/kandyman991/SmartRide-Next/issues/512 |

| G-F8-05 — Ordered proof scheduling is not road-completeness evidence | Production F8 proof scheduling can now process adjacent immutable receiver-GPS ledger ordinals without repeating the same ranked sample and without first-success lock-in. Each successful B receiver ID is still from an independent `trace_attributes(edge_walk)` replay, not authoritative original route-edge identity. The full physical last-retained-road-edge rule and cross-graph transfer are unverified; each batch is intentionally incomplete. | Preserve the unfiltered F8 receiver source for completeness, then prove final retained physical road edges and mode-specific legal handoffs without a connector matrix, name/way collapse or geometric rejection. Compare Android JNI actual scanner and full journeys before any published package. | https://github.com/kandyman991/RoadPilot-Offline-Data/issues/82 ; https://github.com/kandyman991/SmartRide-Next/issues/512 |

| G-F8-06 — Global final physical-road-edge inventory | Pinned native 3.6.3 original-route GraphIds prove 10/10 selected Italy–Austria Car/Motorcycle mode-local terminal paths are truly the final **graph-local** retained directed edge and are within the other region's SHA-verified 25-km buffer. Native GraphReader's true source edges extend outside the separately retained source-buffer GeoJSON, so polygon proximity cannot disqualify roads. This is NOT a full directed road census or proof of one unique terminal per actual physical road. | Enumerate all eligible native directed road paths and demonstrate uniqueness/completeness of each final retained physical road/direction without way/name grouping, geometric exclusion or first-success lock-in; preserve legitimate distinct branches/ramps. Validate real legal A/B GPS handoff at destination. | https://github.com/kandyman991/RoadPilot-Offline-Data/issues/73 ; https://github.com/kandyman991/RoadPilot-Offline-Data/issues/82 |
| G-F8-07 — Actual Android JNI parity | New per-window F8 JNI parity audit identifies the 512-result native cap and Kotlin receiverRoadKey grouping as potential alternative losses. Synthetic tests prove cap/grouping loss cases. No raw actual JNI scan from physical Android on precisely matching immutable graph bytes or verified on-device provenance has been captured. | Capture reference JNI results and post-Kotlin candidates for representative matching windows in both region directions, each vehicle mode, and Italy/Austria/Germany motorways and local roads; reconcile all missing GraphIds and validate complete original F8 journeys before sidecar ingestion. | https://github.com/kandyman991/RoadPilot-Offline-Data/issues/73 ; https://github.com/kandyman991/SmartRide-Next/issues/512 |

**2026-11-04 production evidence for G-F8-06 (still OPEN):** Full verified 3,623-window Italy Nord-Est/Austria native topology pass reconciled **658,345** distinct source directed GraphIds and their complete graph-local node adjacency (323,372 Italy; 334,973 Austria); graph-local Car/Motorcycle terminal evidence and ambiguous mode-stranded paths are retained independently in an immutable SHA-256-bound Legion report. This is exhaustive *native graph-local topology over the retained scan grid*, **not** globally unique physical-road/direction lineage, validated cross-graph transfer, original Valhalla proof for every terminal, or Android JNI parity. No candidate was removed. See `docs/F8_FULL_NATIVE_TERMINAL_CENSUS_ANDROID_PARITY_GATE.md`. G-F8-06/G-F8-07 and Android #512 remain OPEN; publication BLOCKED.

**Status clarification (2026-11-01, Phase 4 PR #95):** Removed producer/planner file status is a tracked-source observation, not proof of F8 parity, Android adoption, completion, or safe removal of historical readers. The acceptance gaps below remain OPEN.

**Promotion policy:** only close a row with direct tests and evidence linked to the actual graph versions/commit SHA. Passing synthetic CI alone never verifies F8 graph-edge parity or real-device success.


**2026-11-04 after PR #121 (G-F8-06 STILL OPEN):** An independent source-only
Valhalla native mode-stop census retains all 658,345 original directed source
edges and their 68,784 distinct graph-local Car/Motorcycle endpoint candidates,
including previously count-only mode-stranded nondeadends. All original
hierarchy-outgoing alternatives stay unresolved, not suppressed. Source original
full directed geometry identifies 251 last-edge shapes directly intersecting
the SHA-bound source 25-km cut and 49 more original final edges wholly beyond
that cut with original cut-crossing native predecessor paths. The 300 bounded
source-cut candidate GraphIds have 600/600 mode-specific exact original
Valhalla TripLeg last-edge matches (both Car and Motorcycle), with one tiny
Austria last edge verified from its immediate native original predecessor.
Two beyond-cut branches reached the configured predecessor depth cap, and
global physical-road/direction equivalence and correct bilateral frontier
completeness remain **NOT_VERIFIED**. Original receiving B correlation
**NOT_STARTED**, production publication **BLOCKED**. See
`docs/F8_SOURCE_FINAL_EDGE_IDENTIFICATION_PROGRESS.md`. Not a license for
way/name grouping, intermediate connectors, entire-core route requirements,
retired producers or fallback removal.


**2026-11-08 PR #127 source cutoff implementation (G-F8-06 STILL OPEN):**
The new original compiled-geometry outer-cut filter ran on Italy Nord-Est
and Austria using their exact SHA-bound original 25-km polygons and selected
boundary tiles. Native immediate topology/hierarchy and geometry-following
produced 1,663 and 2,062 distinct exact local-final candidate GraphIds,
respectively, retaining all original directed branch evidence. 1,599 Italy
and 2,178 Austrian outward/ambiguous source seeds remain unresolved; even the
locally resolved GraphIds are NOT globally proved unique per physical road
and travel direction. No receiving B correlation, Android parity or release.
See `docs/F8_PR127_NATIVE_SOURCE_CUT_CONTINUATIONS_20261108.md`; do not
close G-F8-06/G-F8-07 or present source candidates as real cross-graph links.


**2026-11-09 PR #127 correction (F8 source gap remains OPEN):** Replaced
region-wide November 8 source-cut traversal with **pair-specific original
buffer shared cutoff + native terminal-first, maximum one native successor
hop**. 72/60 original source tiles and 1,520/776 original directed cut
edges for Italy NE→Austria / Austria→Italy NE; 439/211 outward-source
nonterminal roots remain explicitly unresolved, original ramps/hierarchy
alternatives retained. Candidate source GraphIds 505/269 are not globally
proven one-per-physical-road and cannot publish. Previous 1,599/2,178
unresolved numbers applied to entire region outlines across *all neighbors*,
not this pair. No B road matched, no Android parity. See
`docs/F8_PR127_PAIRED_TERMINAL_FIRST_20261109.md`.
