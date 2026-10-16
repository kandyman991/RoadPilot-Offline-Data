# Native F8 directed GPS crossing proposals — graph-backed discovery foundation

Status (2026-10-16): **implemented and real-data tested, not complete graph-pair handoff discovery**. This is a preparatory native-F8 stage, NOT a production connectivity package or replacement for RoadPilot's on-device F8 fallback.

## Behavior / architecture

`tools/discover_native_f8_crossings.py` derives the complete GPS proposal stream for each direction from the existing **uncapped native GraphReader directed edge scanner**, not buffered OSM road samples. It follows the Android F8 reference `FrontierGpsRoadDirectionRecovery.discover`: take the **receiver graph's interior GPS coordinate**, then have independent Valhalla graphs correlate and prove actual A→X and X→B route legs. Exact OSM way/start/inner matches on the opposite graph are optional supporting evidence; neither matching roads nor graph IDs, heading, separation, named-road keys, classes, access masks or a prior successful route can exclude a directed receiver edge at proposal enumeration time. Every scanned candidate remains visible; opposing physical directed edges and candidates without any physical way peer are retained.

Input: fingerprint/boundary-bound `roadpilot.cross-region-connectivity` **UNPROVEN** pair manifest; either the standalone native capture or both retained native side scans with their summary; optionally matching physical-peer evidence. Source scan alignment and typed edges are checked by `build_native_f8_pair_evidence.source_scans`. A retained 2026-10-14 side scan's graph SHA is **summary-declared only**, not cryptographically attested to each side JSON. No graph files, old local sidecars or Android files are modified.

New atomic output (no overwrite): `manifest.json`, `from-to.jsonl.gz`, `to-from.jsonl.gz`. Gzip is deterministic (`mtime=0`, no embedded filename). Manifests include counts/sha256 for every complete stream, exact graph+boundary fingerprints and `proposalSourceCoverage=ALL_RETAINED_DIRECTED_NATIVE_SCAN_EDGES`. That assertion is restricted to **the retained scan**, not actual Android JNI window parity or every possible graph-overlap/corridor. `completeGraphOverlapCoverage=NOT_VERIFIED`, `crossRegionRouteProof=NOT_RUN`, `androidF8ScannerParity=NOT_VERIFIED`, `publicationState=BLOCKED`.

`tools/probe_native_f8_journey.py` separately performs **bounded, journey-scoped** route proofs for Motorcycle or Car, Italy→Austria or reverse. It ranks a sampling budget of GPS proposals by straight-line journey lower-bound and spatial diversity, **without deleting or excluding** other proposals; it reports the unprobed count as incomplete. For each tested seed: normal Valhalla A origin→GPS; normalize GPS to the actual decoded Graph A end; normal Valhalla B normalized GPS→destination; check actual start/end deviations, real cross-graph seam geometry gap and receiver graph-local traced starting GraphId. It checks every sampled alternative rather than accepting the first and reports only `bestOfProbedOnly` for FASTER and SHORTER using the **full sum of both detailed Valhalla legs**. Rejection/error remains distinct from route success. Every result always says `INCOMPLETE_BOUNDED_JOURNEY_PROBES`; no claimed regional graph-pair completeness, global optimality, Android parity or production package.

This is *not* the finished offline preprocessing engine: remaining steps are native graph-wide frontier correlation and safe proof scheduling without repeatedly routing hundreds of thousands of interior points; native Android F8 reference scanner comparison on identical graphs; all mode/direction proofs and alternatives; multi-hop full-journey route choice; on-device packaging and rollback. First valid handoff is not a completeness argument.

## Real Italy Nord-Est ↔ Austria evidence

Source: unchanged Valhalla **3.6.3**, package `2026.10.13-1`, Italy archive SHA-256 `e6a10d36f8622ac0e47dc3d17a8295f60b144f9a2ad478e1b5f6ef2dbea75953`, Austria `ee7baac93b639d0c2fefab8f90540d26d03fd28a283c73bff516a1d8bdc2bc7b`. All 3,623 native windows per side reported complete.

| Stage | Italy→Austria | Austria→Italy |
| --- | ---: | ---: |
| GPS receiver directed edges retained | **334,973** | **323,372** |
| With exact physical peer evidence | 316,563 | 316,563 |
| Without exact way/geometry peer, **not excluded** | 18,410 | 6,809 |
| Real motorcycle tested/proven, selected-only | **3/6** | **3/6** |
| Real auto tested/proven, selected-only | **3/6** | **3/6** |

Journey A→B: `46.501885,13.592668 → 46.592234,13.846448`; reverse for B→A. The three valid per-mode journey proofs include independently traced receiver graph IDs, decoded local Valhalla endpoints, and complete two-leg route metrics. Remaining candidate proposals have **not** been checked; no best global route claim. Real test results and locally retained JSON are under `~/RoadPilotGraphStudio/diagnostics/f8-italy-austria-validation/`, `native-f8-gps-crossing-proposals-v2-deterministic/` and `native-f8-journey-*.json`. No GitHub Actions artifacts uploaded.

## Local reproduction

```bash
# Uses existing local files, no graph rebuild or OSM-way frontier extraction.
python tools/discover_native_f8_crossings.py \
  --pair-manifest /path/to/pair.json \
  --from-scan /path/to/italy-nord-est-native-full.json \
  --to-scan /path/to/austria-native-full.json \
  --scan-summary /path/to/native-full-summary.json \
  --output-dir /path/to/new-gps-proposal-inventory

# Scoped validation only; each direction + mode must be tested independently.
python tools/probe_native_f8_journey.py \
  --pair-manifest /path/to/pair.json \
  --proposal-dir /path/to/new-gps-proposal-inventory \
  --from-manifest /path/to/italy-nord-est-routing-manifest.json \
  --to-manifest /path/to/austria-routing-manifest.json \
  --direction from-to --mode motorcycle \
  --start-lat 46.501885 --start-lng 13.592668 \
  --end-lat 46.592234 --end-lng 13.846448 \
  --max-probes 6 --output /path/to/new-sample-journey-report.json
```

**Acceptance gates remain closed:** `F8_PARITY_VERIFIED=NO`, `DEVICE_VERIFIED=NO`, `PRODUCTION_READY=NO`. Do not wire these diagnostics into Android or auto-refresh as if they were complete connections. Track [Graph Studio #73](https://github.com/kandyman991/RoadPilot-Offline-Data/issues/73), [#82](https://github.com/kandyman991/RoadPilot-Offline-Data/issues/82), [Android #512](https://github.com/kandyman991/SmartRide-Next/issues/512).
