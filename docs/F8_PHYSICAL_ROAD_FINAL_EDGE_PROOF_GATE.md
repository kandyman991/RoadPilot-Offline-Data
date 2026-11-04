# F8 physical-road final-edge proof: first source-complete original-route stage

2026-11-04 · Graph Studio · Italy Nord-Est / Austria routing archives 2026.10.13-1.

**State:** Source-complete terminal ledger and selected authentic Valhalla TripLeg final-edge proofs implemented and validated. Global one-final-edge-per-physical-road/direction remains **NOT VERIFIED**. No connectivity publication or Android update.

## Architecture and provenance

Merged PR #118 fully reconciled 658,345 native graph-local directed edges over 3,623 windows, but an ordinary cul-de-sac is also a graph-local terminal. No proof of a unique physical road can be inferred merely from a dead-end flag, shared OSM way/name, matching GPS coordinates or polygon proximity.

- tools/compile_native_f8_terminal_lineage_proof.py validates pair/boundary fingerprints, the exact retained routing archive SHA-256s, SHA-verified 25-km buffer polygons, original uncapped scans, the complete native terminal census and SHA-256-pinned Valhalla 3.6.3 native binaries before execution.
- Every graph-local Car/Motorcycle terminal is retained individually with its own GraphId, source/end position and verified peer-buffer membership. The distance to the *source* SHA-bound buffer's outer cut is an annotation, not an exclusion rule.
- Separately pinned unbuffered Geofabrik country core polygons support observation of whether a graph terminal lies in its source/receiving region. These polygons are NOT bound to the build manifest; they cannot be treated as authoritative physical-road lineage proof.
- A bounded page chooses cut-line witnesses for expensive original routing, without removing the other source edges. Native GraphReader retrieves the edge's actual directed geometry. A real original Valhalla route runs from its directed start to its end; the same original TripLeg protobuf must have the nominated GraphId as its final edge with both snaps within 1 metre. The full ordered original route GraphIds are retained. Failed/different-edge routes stay UNPROVEN.
- tools/reconcile_native_f8_terminal_proof_pages.py rechecks graph identity, source-complete terminal arrays and every prioritized page. Missing, duplicated, reordered, spoofed or stale witness results fail closed. The compact summary retains every unproven identity.
- All inputs are hashed before/after the native proof, and output is written immutably to a previously nonexistent file. Neither tool rewrites graph tiles, Android files, historical evidence nor any production manifest.

**No name/way/GPS-based physical-road deduplication, cross-graph numeric GraphId matching, geometry-based eligibility rejection, connector matrix, first-success short circuit, or abandoned OSM sampler is introduced.**

## Original real-data results

| Native graph / travel direction | Mode | Graph-local terminals retained | Prioritized within 20 m of verified source outer cut and receiving core | Original last TripLeg GraphId matches |
| --- | --- | ---: | ---: | ---: |
| Italy Nord-Est to Austria | Car | 21,500 | 45 | 45 |
| Italy Nord-Est to Austria | Motorcycle | 21,468 | 45 | 45 |
| Austria to Italy Nord-Est | Car | 22,439 | 13 | 12 |
| Austria to Italy Nord-Est | Motorcycle | 22,407 | 13 | 12 |
| Total mode-specific observations | | 87,814 | **116** | **114** |

The same Austrian directed GraphId 4636807666 failed the original route proof for both modes. It is **NOT VERIFIED, NOT REMOVED**. The original route executor did not yield the required TripLeg edge inventory for a local start-to-end probe; this is not proof of road illegality.

## Exact immutable evidence on the Legion

Directory: ~/RoadPilotGraphStudio/diagnostics/f8-production/20261104/

- Full PR #118 native census: full-native-census-v3.json SHA256 2eddf560fe544724297794ece1e8b3e20fa54d2b10ab884b9b45ec38dd659a0b.
- Complete ledger + original route witness page 0–24: physical-directed-terminal-lineage-page-0-24-v2.json SHA256 18fab3789c02bd1c6abd7f65a0433045f0f7f97ae8d0269280e947d1f1e63dd3.
- Complete ledger + original route witness page 24–48: physical-directed-terminal-lineage-page-24-48-v3.json SHA256 7e66ecb4ef29c69bda16381723a6ee5fb1b0e600783b177457e4c59122741a41.
- Source-complete page reconciliation: physical-directed-terminal-prioritized-witness-reconciliation-v1.json SHA256 4791ef0ef0261d0d2cb70107117fe47a5f83816b398cfcf1b9970248a44f0ebb.
- Italy original routing archive sha256:e6a10d36f8622ac0e47dc3d17a8295f60b144f9a2ad478e1b5f6ef2dbea75953. Austria original routing archive sha256:ee7baac93b639d0c2fefab8f90540d26d03fd28a283c73bff516a1d8bdc2bc7b.
- Original native GraphReader endpoint executable sha256:14455ad673c464c3715f2e0b96adfa3aa1f1ecf2a99d347f59920a6a9cc91c6f; original Valhalla route-edge executable sha256:e955677e56278b53cee0d39ca6d94efa1557e1439da81859f330ffb4b8dbe776.

Every prioritized witness was accounted for **exactly once** across the immutable pages. The ledger retains all other source terminals even though their routes were not probed.

## Remaining hard blockers before the requested global milestone

1. Native graph-local dead ends are not unique physical-road equivalence classes. The 45/13 cut-line selection is **not** an exhaustive set of legally drivable physical crossings; all unprobed source terminals, branch successors and mode-stranded non-deadends remain unresolved.
2. Original Valhalla witness routes here begin at the nominated directed edge's start, **not** inside the source unbuffered region. They prove the graph-local last-edge ID for that one route, not that the entire road lineage travels from the original region core to that endpoint.
3. Graph-native road polyline/topology continuity must establish unique and complete road-direction lineages without merging separate motorway carriageways, ramps or branches. The actual receiving B graph may subdivide the same physical road into several original directed edges and must be verified independently. The two graphs' numeric GraphIds are never compared for equivalence.
4. Genuine source-region A to X and X to destination B original Valhalla TripLeg edge sequences must prove usable forward directions, mode-specific legality, full arrival and whole-journey costs. This work must reconcile with the now lossless Android JNI/Kotlin F8 candidate stream on exactly the same graph archives.
5. Multi-hop Austria–Germany and actual physical Android installation, fingerprinted package/rollback and optimal FASTER/SHORTEST alternative selection remain open. Do not call this a production-complete handoff catalog or publish connectivity while these gates are missing.

**Next production increment:** construct true branch-aware directed physical-road lineage from native geometry and topology through the verified overlap, record all ambiguous branches, verify original Valhalla routes originating inside the source *core* and ending on the true last source GraphId, then independently validate matching geometry and B first-route GraphIds. Preserve all alternatives and keep unresolved cases explicit.

Architecture contract preserved: A1–A3, B1–B4, C1–C3, D1–D4. Open work tracked in Graph Studio issues #73/#82 and RoadPilot Android issue #512.
