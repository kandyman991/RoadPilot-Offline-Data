# F8 original source final-edge correlation and Android delivery — November 5, 2026

**Status: partial verified native connections delivered to Android emulator. Full all-road completion NOT_VERIFIED. No merge or release authorized.**

This is the **existing F8 one final retained directed edge for each physical road/direction** model, not a portal matrix or unrelated sampling architecture. It preserves genuinely distinct original road branches and vehicle modes.

## Source and receiver: original routing graph identities

Italy Nord-Est and Austria original Valhalla 3.6.3 graph `tiles.tar` archives are unchanged: SHA-256 `e6a10d36f8622ac0e47dc3d17a8295f60b144f9a2ad478e1b5f6ef2dbea75953` and `ee7baac93b639d0c2fefab8f90540d26d03fd28a283c73bff516a1d8bdc2bc7b`.

Graph Studio source cut census examined **all 367 Italy source tiles** and **338 Austria source tiles**, not only the former 3,623-window scan. Across the original archive source buffer cut it found 9,190 and 11,296 native directed road-cut observations respectively. The extra native original source local-terminal ledger contains 21,500 Italy and 22,439 Austria *window-scanned local terminal edges* (the latter scan is not exhaustive of the full archives).

The legacy 300 previously routed source A-LAST directed IDs were a **partial input**, not every physical road. The broader cut/terminal scan only nominates original A edge IDs; actual original Valhalla A-LAST TripLeg identity, precise source-native outgoing hierarchy and physical-forward geometry, original receiving B FIRST TripLeg and supported mode are separate mandatory checks. Neither numeric GraphId equality across different graphs nor matching OSM way ID or road name is proof.

## Corrected native source-final catalog

**Do not ship** `full-archive-directed-cross-graph-connections-v3.json`: the original A-LAST local routing proof did not ensure the source edge was physically terminal. It had 375 plausible A/B linked source IDs and 412 B receiver options, but the source native lineage audit identified 170 A sources with further source-side continuations or ambiguous branches.

The independently SHA-pinned strict source-terminal inventory is

`~/RoadPilotGraphStudio/diagnostics/f8-production/20261105/f8-source-terminal-verified-connections-v4.json`

SHA-256 `c38853344965eee535ce20bc2dae1a73644687ea2dd97cbe96b907424b4d3b8a`. It contains:

| Original source | Source native terminal IDs with A/B route proof | Original receiver directed options |
|---|---:|---:|
| Italy Nord-Est | 127 | 136 |
| Austria | 78 | 96 |
| **Total** | **205** | **232** |

**170** intermediate/ambiguous A sources were explicitly deferred, including their previously matched receiving peers as *non-terminal* evidence. The original ~165 previously unmatched candidates remain visible, not promoted to connections. Across the broader source-cut/terminal audit many native original terminal edges inside the overlap have no matching receiving-graph physical forward continuation or cannot be routed. These are **not** inserted into Android's verified directed connection cache. No first-success, OSM-name, way-ID or position group deduplication is performed on the verified receiver option list.

The `tools/gate_f8_source_final_native_topology.py` program reads actual original source graph `--lineage` via a hash-pinned Valhalla GraphReader, and rejects a source A-LAST GraphId if any additional mode-accessible physically forward original source edge exists or if another original same-intersection branch is ambiguous. Genuine different car and motorcycle branches are checked independently.

## RoadPilot test delivery proved

The Android draft PR #542 consumer accepts this strict catalog. It verifies both installed original graph tile-archive SHA-256s, native directed last/first GraphIds, Valhalla modes, distinct receiver branches, physical shape and Valhalla proof; ordinary F8 discovery remains active for all missing edges.

Run on authorized Legion:

`F8_TEST_CATALOG_PATH=~/RoadPilotGraphStudio/diagnostics/f8-production/20261105/f8-source-terminal-verified-connections-v4.json ./tools/run_f8_arm64_emulator_acceptance.sh`

The emulator had original Italy (367 tiles) and Austria (338 tiles) installed, loaded **136 Italy → Austria CAR and 96 Austria → Italy MOTORCYCLE** verified options from the new on-device file, and ran **4/4 exact JNI A-LAST/B-FIRST native two-leg route tests successfully**, both directions in CAR and MOTORCYCLE, with ~0.9m exact seam gap. Test evidence:

`~/RoadPilotGraphStudio/diagnostics/f8-production/20261105/f8-final-edge-android-emulator-route-v5-1793835977492.json`

SHA256 `e623b7466a38e48c79d2645eadcb36a537cd69599696d2c022668705f906e003`.

This is a real Android emulator JNI consumption result, **not** a claim that the whole F8 high-level planner has passed. The native ARM64 JNI library is test-injected from an existing pinned build using the emulator's ARM native bridge, without committing the binary or modifying normal Android production ABI selection.

## Remaining blockers for an actual final production sidecar

- Prove every **physical road/direction lineage from its original source core to its last directed edge**; intermediate/ambiguous native source branches and their terminal descendants are not presumed complete merely because a local route returns a LAST directed ID.
- Prove full receiving-graph original directed edge coverage; the retained 323,372/334,973 overlap-window scans are a subset, and some original full-archive directed edges were demonstrably outside these captured IDs.
- Resolve or explicitly classify every genuinely relevant source mode/physical branch, and prevent one first successful route from suppressing others.
- Rebuild the complete catalog using the corrected source-final producer and test **complete RoadPilot A→X→B planner navigation** on Android with that exact catalog, followed by independent code review, exact-head CI and physical-device acceptance.

Until then, keep `sourceDiscoveryComplete=false`, `physicalRoadPerDirectionGlobalUniqueness=NOT_VERIFIED`, `receiverCandidateCensusComplete=false` and `productionPublication=BLOCKED`. This partial catalog is for the verified Android emulator test; it is **not** a signed-off all-crossings product artifact.

## Continuation trace and latest reproducible emulator-delivered cache

Following the initial 170 deferred matched source edges,
`tools/trace_f8_original_source_to_last_edge.py` walked *all* mode-allowed native physical-forward continuations and hierarchy transitions in the source graph. The original source cut→final routing probe requires the starting *original directed seed GraphId*, ending *terminal directed GraphId*, and the ordered exact native chain as a subsequence of the Valhalla TripLeg. Every original receiving B edge must separately start the B TripLeg in the same mode. Other original forks are preserved, not grouped by OSM way/name.

Immutable full traced ledger:
`~/RoadPilotGraphStudio/diagnostics/f8-production/20261105/f8-original-source-forward-traced-and-receiver-matched-v7.json`
SHA-256 `e771add67eb8a6d62bd654795670ba29b06c608cbb9ed2e9d5ae6dc52e8c3405`. It preserves **222** verified final directed A source records and **249** original B directed options: Italy source 139 / receiver 148; Austria source 83 / receiver 101. Compared with the first strict terminal v4, this is **17 new unique source IDs and 17 additional distinct original receiving B directed options**, with no loss of the previous 232 verified options.

The trace walked 6,625 original directed source states, retained 3,348 ambiguous branch observations and 30 loop paths, and conservatively deferred 716 depth-capped paths. It attempted 946 original A source→terminal directed TripLeg routes and 116 original B FIRST mode routes. Those unresolved alternatives prove that all-road/direction completeness remains **NOT_VERIFIED**. Native route success does not override a missing physical road lineage or unresolved original branch.

Android's original partial-source client cache is a separate, SHA-bound *projection* produced by
`tools/emit_f8_verified_android_test_catalog.py`. Its exact input is the full v7 SHA-pinned ledger; unverified source identities stay in the original Graph Studio evidence and are excluded from Android's <3 MB verified-only cache without disabling ordinary F8 discovery.

Native Android emulator input:
`~/RoadPilotGraphStudio/diagnostics/f8-production/20261105/f8-verified-terminal-android-consumption-v8.json`
SHA-256 `8c40accec06d2b5253c0e1e36b27fc9ad59c83c8f607572f1ac5a83982159fc8` (2,375,226 bytes). Android parsed all 148 Italy→Austria and 101 Austria→Italy CAR/MOTORCYCLE receiving options from this file. **4/4 exact native JNI two-leg routes passed** in both directions and modes. Evidence:
`~/RoadPilotGraphStudio/diagnostics/f8-production/20261105/f8-final-edge-android-emulator-route-v5-1793837014901.json`
SHA-256 `88623e319f2a18fe0ef4d165e0da3fb4c6e9e22f833e47e103d4e82cc55a08f9`.

**Still not a production-distributable F8 sidecar:** local original terminal root inventory and peer-directed full archive census require complete coverage proof, ambiguous mode branches are unresolved, the native original receiver scan is limited to recorded overlap windows, and the **whole cross-region planner** was not exercised on Android. Keep PRs draft, all routes discovering other crossings as usual, and publication BLOCKED.
