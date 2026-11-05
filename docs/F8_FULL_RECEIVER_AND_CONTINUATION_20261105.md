# F8 original receiver full-archive and conservative source continuation — 2026-11-05

**Development branch:** Graph Studio PR #125. **Status:** independent source/destination original native evidence; **NOT** full physical-road/direction coverage or a production release. Existing Graph Studio architecture contract is unchanged.

## Native receiving-graph archive census

`tools/native-f8-edge-scan/native_f8_full_receiver_nearpoint.cpp` is a read-only, Valhalla-3.6.3-native tool. It uses the original build's `GraphReader::GetTileSet()`, visits **every directed edge and every routable non-shortcut road shape** in all original tiles, and finds directed shapes whose *segments* pass within the original source-final endpoint's candidate search radius. It does not require a receiving edge's **start node** to lie near the original source endpoint. It neither mutates tiles nor equates the different graphs' numeric GraphIds.

Native tool built on the Legion with its installed original Valhalla 3.6.3 toolchain using a **separate** `tools/native-f8-full-receiver/CMakeLists.txt`, preserving the SHA-reviewed `tools/native-f8-edge-scan/CMakeLists.txt` unmodified. The native tool built from both the initial and separate recipe is byte-identical: SHA-256 `ccc68dfb4ac4816a99e2aec2f7d2ebbb051d21455ea051bf5cc6f7257bf6c7ca`.

Rebuild without disturbing earlier native build provenance:

```bash
PKG_CONFIG_PATH=$HOME/.local/opt/valhalla-3.6.3-native/lib/pkgconfig:$PKG_CONFIG_PATH cmake -S tools/native-f8-full-receiver -B /tmp/f8-original-full-receiver-build -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build /tmp/f8-original-full-receiver-build --target native_f8_full_receiver_nearpoint -j2
```

Original graph archive identities unchanged:

- Italy Nord-Est: `sha256:e6a10d36f8622ac0e47dc3d17a8295f60b144f9a2ad478e1b5f6ef2dbea75953`
- Austria: `sha256:ee7baac93b639d0c2fefab8f90540d26d03fd28a283c73bff516a1d8bdc2bc7b`

Census of the **222 previously verified original source-final directed GraphIds**:

| Original receiving graph | Actual original tiles | All directed GraphIds examined | Original routable road shapes |
|---|---:|---:|---:|
| Austria | 338 | 13,790,726 | 5,505,266 |
| Italy Nord-Est | 367 | 8,764,618 | 3,954,471 |

The native search radius of 4m is a **prefetch**, not an eligibility test. The existing independent exact-geometry acceptance remains **source endpoint ≤3m from original B directed shape, physically forward with non-retracing bearing, and the actual original Valhalla B-FIRST TripLeg GraphId** for each accepted mode.

All original 249 verified B directed options were found in the complete receiver archive, with no losses. Five additional original B forward-shape alternatives were examined. Four had short receiver segments (approximately 8–13m) and initially exceeded the 3m original TripLeg terminal-snap limit solely because the diagnostic probe targeted the interior of the short edge. The producer now retries the actual **native directed B edge terminal** (not a guessed coordinate). Four alternatives passed the exact FIRST GraphId and unmodified ≤3m snap checks in both vehicle modes. The fifth 4.5m edge returned a native invalid-route-metrics failure and remains unverified, **not accepted**.

Result: **222 original source-final directed records, 253 exact original receiving B directed options** — 152 Italy→Austria, 101 Austria→Italy. The receiver-archive shape search is exhaustive **for those 222 source final endpoints**, but this does NOT prove every legitimate source road/direction was enumerated.

### Immutable audit

Full native source/B correlation (including unverified lineage and receiver alternatives):
`~/RoadPilotGraphStudio/diagnostics/f8-production/20261105/f8-full-original-receiver-archive-short-edge-correlated-v12.json` SHA-256 `10d1859bfd588b6fe3182537d1758469d7f77197d3982a86bf8e979320f8eaff`.

## Continuation resolution without arbitrary traversal depth

`tools/resolve_f8_source_native_capped_paths.py` resumes the previous **716 mode-specific source-road paths** that stopped at 20 edges. It deduplicates native route states by actual **(source seed, mode, directed edge GraphId)** rather than suppressing source final identities by name, coordinate, way or first route success. It follows physically forward **same original OSM-way** continuations to their native end, without another hop-count cutoff. Any changed OSM way, ambiguous native branch, degenerate short graph edge, or leaving the authoritative bilateral 25km overlap is explicitly recorded as **unresolved** — a way-ID difference is NEVER taken as proof the source road ended.

This stricter evidence scanned 878 native source/mode states and 490 same-way forward transitions. It preserved 506 changed-way transitions and 538 ambiguous native outgoing observations for independent physical-road identity decisions; 12 paths leave the verified bilateral overlap. Forty-four native source-final/mode candidates reached a possible last edge, but **none** passed all additional A-route/B-route requirements as a *new* source-final A/B connection. Thus source-final records stay **222**; there is no false completeness claim.

Fail-closed native zero-length successors stay unresolved rather than crashing the source audit or being silently discarded.

Combined immutable original source/receiver audit:
`~/RoadPilotGraphStudio/diagnostics/f8-production/20261105/f8-full-receiver-and-source-conservatively-resumed-v13.json` SHA-256 `55b0548bc42daff14e187fef20fee36717167cd399bd7d7c8e4045f226d0209e`.

## Exact Android consumer check

`tools/emit_f8_verified_android_test_catalog.py` derives a **verified-only** partial Android test cache from that complete, unpublished original ledger. Unverified original sources remain in the Graph Studio evidence. Android F8 runtime discovery stays on for all missing roads and directions.

Input cache:
`~/RoadPilotGraphStudio/diagnostics/f8-production/20261105/f8-verified-original-full-receiver-android-test-v14.json`, SHA-256 `534dc12680f7ea9c16967ecccaadaaf62339d67dba89d92641fb45ed279aa013`, 2,699,173 bytes.

The RoadPilot PR #542 acceptance runner installed this exact cache on the Legion's Android emulator, parsed **152 Italy→Austria** and **101 Austria→Italy** directed options, and passed all four original native ARM64-JNI GraphId-constrained A-LAST→B-FIRST **two-leg** tests, car and motorcycle in both directions.

Device evidence:
`~/RoadPilotGraphStudio/diagnostics/f8-production/20261105/f8-final-edge-android-emulator-route-v5-1793859963591.json`, SHA-256 `38515492a23bee0dc43f0ea1db3d4a12b4ebf0d943a9de143776a92aa29dbae1`.

**Do not merge or release yet:** Native full original-source physical road lineage is not complete across way-ID transitions and ambiguous branches. Complete RoadPilot high-level cross-region planner journeys and physical Android acceptance have not yet run. Keep `sourceDiscoveryComplete=false`, `physicalRoadPerDirectionGlobalUniqueness=NOT_VERIFIED`, `productionPublication=BLOCKED`. This remains a **verified partial connection cache**, not every legitimate road/direction.
