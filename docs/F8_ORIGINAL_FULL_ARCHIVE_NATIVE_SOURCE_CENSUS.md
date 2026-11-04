# F8 production source census — every original Valhalla tile and directed edge

Date: 2026-11-04. Scope: read-only Italy Nord-Est / Austria ORIGINAL Valhalla 3.6.3 routing archives, package version `2026.10.13-1`. Base: PR #122 merged into `main`.

## Owner-approved nonnegotiable architecture

The production goal remains **one final retained ORIGINAL directed GraphId per actual physical road and travel direction** across the 25-km bilateral overlap. Car/Motorcycle access is an attribute of the same original directed edge, not a reason to mint duplicate handoffs. Preserve every distinct carriageway, ramp, branch, hierarchy transition, shortcut, ferry/nonroad, and mode-specific alternative. Never group by OSM way ID, road name, GPS proximity or numeric GraphId equality across independently built archives. Never accept the first successful route as evidence that other native branches do not exist. Do not correlate receiving graph B before all original source road-direction branches and final edges have been proved.

## Implemented in this milestone

- `tools/native-f8-archive-census/native_f8_archive_census.cpp` is an independent Valhalla 3.6.3 C++ GraphReader extractor. It reads **every** tile returned by `GetTileSet()`, and **every** directed-edge index in each tile's native header. Every edge is inspected including nonroad/shortcut/mode-inaccessible edges, with no OSM/name grouping.
- It emits complete ordered tile headers whose GraphId ranges and edge counts represent **all** original archive directed IDs. For detailed cut geometry, it emits original directed shapes whose geographic envelopes intersect conservative boxes along **every segment of the SHA-verified ORIGINAL source buffer boundary**, expanded by 0.05° on each coordinate. This bbox is a transfer optimization, not a road-selection or bilateral-crossing rule.
- `tools/census_native_f8_original_archive_tiles.py` independently checks tile ID/index/count consistency, source binary, exact immutable region manifest and graph SHA, neighbor boundary fingerprints, actual original 25-km buffer polygon SHA, original geometry and directional intersection in EPSG:3035, and no input mutation. It refuses partial/extra native output and existing output files.
- Zero-length directed geometries encountered by the full archive scan are **preserved by exact original GraphId as unresolved**, never interpreted as valid physical roads or silently dropped.
- `tools/reconcile_native_f8_archive_window_coverage.py` checks all old cut GraphIds against the archive-wide inventory and verifies **every** known predecessor GraphId missing from old window capture was recovered in the new original cut evidence. No receiver-graph lookup, publication, Android change or crossing sidecar.

The older SHA-pinned `tools/native-f8-edge-scan/CMakeLists.txt` was left untouched; its original provenance regression still passes. The new native extractor has its own CMake target.

## Proven native original archive observations

| Original region | All tiles | All original directed GraphIds | Original source-buffer cut geometry | Unresolved zero-length native IDs |
|---|---:|---:|---:|---:|
| Italy Nord-Est | 367 | 8,764,618 | 9,190 | 6 |
| Austria | 338 | 13,790,726 | 11,296 | 0 |
| **Both** | **705** | **22,555,344** | **20,486** | **6** |

Directional source-cut classifications across all other neighbor boundaries, **NOT an Italy/Austria road shortlist**:

| Original region | Outward | Inward | Both endpoints outside | Both endpoints inside |
|---|---:|---:|---:|---:|
| Italy Nord-Est | 4,338 | 4,338 | 216 | 298 |
| Austria | 5,393 | 5,393 | 202 | 308 |

### Comparison against formerly complete *only within windows*

| Original source | Previous window cut observations | Now archive-wide cut observations | Newly recovered original cut GraphIds | Known original beyond-cut predecessor IDs recovered |
|---|---:|---:|---:|---:|
| Italy Nord-Est | 593 | 9,190 | 8,597 | 18 / 18 |
| Austria | 287 | 11,296 | 11,009 | 16 / 16 |
| **Both** | **880** | **20,486** | **19,606** | **34 / 34** |

The 19,606 newly recorded original directed IDs are **not** handoffs or physical-road identities, and may include unrelated boundaries. This is proof that the previous windows were NOT a complete original archive cut inventory.

### Immutable evidence on the authorized Legion

Under `~/RoadPilotGraphStudio/diagnostics/f8-production/20261104/`:

- `original-archive-source-tile-cut-census-v1.json` SHA-256 **`dfd4fe70f75a01bc3c3c44eda0654f31739463daa0f90fbd0823213d525d3dfd`**.
- `original-archive-versus-window-coverage-v1.json` SHA-256 **`43457a1d3a2df3d54c42a361ef106f91a015be23eb2c4c79db5ec5c1a6ac20fb`**.
- Original window cut v3 SHA-256 **`a222a7bfd463d331a125b0e420c6c570cdf8d42431a8ba87536341aaa08d8d46`**; prior reconciliation v1 **`652c3efe77ebf3d60ae3e7be24e7d454279ba5b91ac5c6225d97596db3e68ecf`**.
- Isolated native executable at `/tmp/graphstudio-original-native-archive-census-isolated/native_f8_archive_census`, Valhalla **3.6.3**, SHA-256 **`a59516b38b247682bf90267959894d532a0474ae8d081fdfd5fbeab039b62eaf`**. Rebuilt with independent CMake and independently reproduced exactly the same executable SHA as the original native run.

The original graph SHA fingerprints and buffer polygons are checked at runtime from the immutable pair and regional manifests. Exact SHA and interval identity are stored in the reports; do not replace input archives with a newly rebuilt graph.

## Test, safety and unfinished gates

Full Legion Python regression: **408 / 408 PASS**. New unit gates reject missing/duplicated/malformed tile records, misindexed GraphIds, omitted source cut observations, forged fingerprints, incomplete source predecessor recovery, source mode suppression and false publication claims. Original CMake build-provenance regression remains green. The new Valhalla C++ native build succeeds in Release configuration locally; GitHub CI has no Valhalla 3.6.3 build environment, so GitHub validates Python invariants, not this native build's executable SHA.

**Still NOT_VERIFIED (production blockers):**

1. The archive-wide census includes all neighbors, not just the Italy/Austria bilateral frontier. Locate and SHA-bind the *original* source core/border provenance, isolate the relevant bilateral border cut by exact topology, without assuming OSM way/name equivalence and without excluding legitimate ramps/branches.
2. Build and verify each original **road/direction** lineage from its own core through the now-complete source-cut inventory to **one final retained original directed GraphId**, across all native levels, turns, modes and branches. Six zero-length GraphIds remain explicitly unresolved and cannot be silently classified.
3. Prove the final GraphIds from original Valhalla TripLegs for every mode-specific legal continuation; record all alternatives rather than first-success suppression.
4. **Only after the above source-side proof succeeds** begin original receiving B graph correlation, A→X→B journeys and Android JNI parity.

No source-graph archive, native tile, source core polygon, receiving graph, Android runtime or production connectivity sidecar was modified. Physical-road uniqueness **NOT_VERIFIED**; receiving-graph correlation **NOT_STARTED**; production publication **BLOCKED**. Graph Studio issues #73/#82 and RoadPilot #512 remain open.
