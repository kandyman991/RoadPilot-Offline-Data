# M6b — Native F8 journey endpoint and edge-walk replay observations

**Status:** read-only diagnostic, subject to PR #113 review gates. No production routing change, connector matrix, Graph Studio publisher change, Android change or release authorization. The intended native F8 final-road-edge/25-km-overlap contract remains binding and **not yet demonstrated**.

## Source, meaning and limitations

M6b tests selected native F8 GPS proposals by requesting two ordinary Valhalla 3.6.3 graph-local routes: origin→X in Graph A, then A's normalized actual arrival coordinate X→destination in Graph B. The route service provides encoded shapes, endpoint locations and journey metrics.

**Review correction F02:** Directed GraphIds reported here are NOT obtained authoritatively from the route service. Each routed shape is independently sent to `valhalla_service trace_attributes` with `shape_match=edge_walk`. This produces a **reconstructed edge-walk replay** that might differ from the original route's edge choices when multiple directed edges share or closely follow one geometry. A route↔trace fidelity proof for overlapping/ambiguous geometry has **not** been performed.

- `replayedALastDirectedGraphId`, `replayedBFirstDirectedGraphId`, `aEdgeWalkReplayLastIds`, `bEdgeWalkReplayFirstIds` and their SHA-256 digests identify only **edge-walk replay** IDs.
- A replay matching the nominated GPS receiver ID does not independently prove the route service traversed that directed edge.
- `edgeWalkReplayMethod=VALHALLA_TRACE_ATTRIBUTES_EDGE_WALK_OF_ROUTE_SHAPE`.
- `routeEdgeIdentityFidelity=NOT_VERIFIED` and `ambiguousGeometryEdgeIdentity=NOT_VERIFIED`.
- Positive status `BOTH_EDGE_WALK_REPLAYS_MATCH_SELECTED_JOURNEY_SHAPES_ONLY` means the requested A and B route legs arrived within the declared F8 tolerance, and B's *replayed* shape begins with the nominated GPS receiver edge. **Not** a route-edge identity, final-road-edge or seam-legality certificate.

## What the diagnostic does

`tools/probe_native_f8_actual_journey.py`:

1. Verifies original, complete SHA-256-bound native GPS proposal stream and both immutable regional routing package/boundary fingerprints.
2. Probes **1–8 explicitly selected original GPS proposal IDs**, preserving total stream count and the fact that all other crossing alternatives remain unprobed. No road-key or OSM correlation filter.
3. Requests fresh graph-local routes; normalizes B's start to actual A-leg arrival; checks destinations and F8's 25 m local endpoint tolerance and stores real leg costs.
4. Replays each shape using a **separate** Valhalla edge-walk trace. Real route endpoint coordinates are distinguished from replay edge IDs; numeric GraphIds never match across regional graphs.
5. Uses the pinned native Valhalla GraphReader to inspect **replayed** A-last/B-first edge geometry and access flags. Co-location, orientation, `deadend` and remaining distance on the replayed A edge are observations only.
6. **F01:** Missing/unreadable native geometry, timeouts or malformed geometric details are `INCONCLUSIVE` for one selected candidate, allowing the rest of its batch to continue. Wrong, missing or inconsistent native GraphIds/counts are fatal data-integrity failures.
7. **F03:** Calculates the native executable's SHA-256 and checks it against the independently compiled and archived M6a/PR #112 binary, as well as Valhalla version 3.6.3. Mismatch stops the entire run before routing. Each report and candidate row binds `nativeExtractorSha256` and `nativeExtractorProvenance`.

### Archived pinned native extractor

SHA-256: `14455ad673c464c3715f2e0b96adfa3aa1f1ecf2a99d347f59920a6a9cc91c6f`

Build commands, static-library hash and source provenance are in `docs/F8_M6_NATIVE_EXTRACTOR_BUILD_PROVENANCE.md`. A future legitimate rebuild must be independently reviewed and explicitly repinned. The SHA match is not a signing/release attestation.

## Retained Italy Nord-Est ↔ Austria evidence (2026-11-04)

Immutable regional routing packages `2026.10.13-1`, pinned Valhalla 3.6.3. Three original GPS proposal IDs per direction × Car and Motorcycle = **12 selected candidate/mode observations** in four reports. Their original intact streams contain **334,973** Italy→Austria and **323,372** Austria→Italy proposals; all unprobed alternatives remain unknown.

| Direction | Mode | Replay A-last IDs | Replay B-first IDs | Result |
| --- | --- | --- | --- | --- |
| Italy→Austria | Car | 536441000506, 1442471870473, 576605655610 | 542514352698, 404465516553, 568921690682 | 3/3 selected edge-walk replays |
| Italy→Austria | Motorcycle | same | same | 3/3 selected edge-walk replays |
| Austria→Italy | Car | 536441000506, 403425329161, 576605655610 | 542514352698, 1443512057865, 568921690682 | 3/3 selected edge-walk replays |
| Austria→Italy | Motorcycle | same | same | 3/3 selected edge-walk replays |

All 12 newly requested routes reached their destinations with F8 endpoint normalization. The 12 **separately replayed** shapes in B began on the corresponding nominated GPS receiver edge. Replayed A/B native geometries are within one metre of the handoff, strictly a **co-location observation**. Exact original route-edge identities remain **NOT_VERIFIED**.

### Critical final-road-edge gap

For these selected route shapes, the normalized A handoff lies **13.100 m, 27.097 m or 65.573 m** from the end of the **replayed** A directed edge; native `deadend=false`. This does not identify the **final retained physical-road edge inside the approved 25-km overlap**. Even accurate replay could only determine a leg's last edge, not the overall final retained edge. Every result explicitly retains `sourceRoadFinalEdgeIdentity=NOT_VERIFIED_BY_SELECTED_LEG`.

## Archived evidence and regression tests

Fresh, review-corrected raw JSON and checksums are kept **outside Git** at:

`~/RoadPilotGraphStudio/diagnostics/m6/20261104/m6b-pr113-review-shape-replay-v4/`

The directory has four direction/mode JSON reports, `SHA256SUMS` and `summary.json`. Earlier `m6b-actual-journeys-v2/` and
`m6b-reviewed-shape-replay-v3/` raw reports are retained as historical
evidence before the final `replayedEdgeGeometry` field-name correction;
these older formats are not authoritative route-edge identity evidence.

Regressions now include: a mixed batch with recoverable native failure and successful continuation; malformed native geometry; fatal swapped/missing GraphIds; ambiguous edge-walk geometry; SHA pin enforcement even for a fake binary that reports the correct Valhalla version; existing access, direction and arrival controls. Exact-head CI and a fresh independent review remain required.

## Next gate

**M6c must establish the true final retained road edge**, and route-service-to-edge identity fidelity—including ambiguous/overlapping geometries—before treating any edge-walk ID as a definitive directed handoff. Preserve all alternatives, do not restore the retired OSM/connector-matrix pipeline and keep Android F8 unchanged.

Android JNI parity, exhaustive discovery, physical/legal seam transfer, FASTEST/SHORTEST global optimality, multi-hop and production publication remain **NOT_VERIFIED/BLOCKED**. This diagnostic authorizes no merge or release.
