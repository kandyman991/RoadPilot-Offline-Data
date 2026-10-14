# Native, uncapped Valhalla graph-edge capture — preparatory evidence

## Scope

This tool is a **read-only Graph Studio C++ port** of RoadPilot's Android F8
`native/on-device-valhalla/builder_jni.cpp::scan_boundary_road_edges`
enumeration predicates. It deliberately removes the Android JNI's **512-result
window cap**. It inspects the same retained Valhalla graph packages used by the
existing sidecars and exports every eligible **directed GraphId**, preserving
one-way carriageways, ramps, separate positions and vehicle access masks.

**Critical:** this is NOT an actual capture from the Android F8 JNI function.
It is a separately compiled port with independent scanner identity
`GraphStudio.nativeUncappedRoadEdges`. It is not automatically semantically
equivalent to F8; the auditor reports `f8GraphEdgeParity: NOT_VERIFIED` and
`scanStatus: INCOMPLETE` even if all its exported windows are complete.
The filtered raw graph edges can be a superset of useful F8 handoffs.
Its real-world C++ compile, ABI compatibility and route correctness must be
validated on the Legion. Synthetic CI tests are not real graph evidence.

## Build on Legion (no graph rebuild)

Prerequisites: the **same compatible Valhalla C++ headers and library** as
the graph generator, CMake, compiler with C++17, `pkg-config` with
`libvalhalla.pc`, and the existing Python Graph Studio dependencies. Check
`pkg-config --modversion libvalhalla` before proceeding. The C++ executable
now exposes the **compile-time linked libvalhalla version** via
`native_f8_edge_scan --version`. Capture refuses to scan unless this equals
**both** `valhallaVersion` fields in the retained graph manifests; no silent
3.9-to-3.6 graph mismatches. The binary hash and declared version are written
to the evidence JSON. This is a **version/provenance check**, not definitive
proof of a compatible C++ ABI or F8 route correctness.

```bash
cmake -S tools/native-f8-edge-scan -B /tmp/roadpilot-f8-native
cmake --build /tmp/roadpilot-f8-native -j 2
/tmp/roadpilot-f8-native/native_f8_edge_scan --version  # must equal both retained graph valhallaVersion fields
```

If Valhalla development headers/pkg-config are absent, do not replace the
scanner with an OSM-only approximation. Install a matching development package
or build against the same Valhalla release; do not modify the retained graphs.

Inputs are the **existing retained** two regional manifests, buffered polygon
GeoJSONs and pair `correlations.json`. For a pair such as
`italy-nord-est__geofabrik-austria`:

```bash
python3 tools/capture_native_f8_graph_windows.py \
  --correlations /path/to/connectivity/italy-nord-est__geofabrik-austria/correlations.json \
  --from-manifest /path/to/italy-nord-est/routing/manifest.json \
  --to-manifest /path/to/geofabrik-austria/routing/manifest.json \
  --from-buffer /path/to/italy-nord-est/build/buffer.geojson \
  --to-buffer /path/to/geofabrik-austria/build/buffer.geojson \
  --scanner-binary /tmp/roadpilot-f8-native/native_f8_edge_scan \
  --output /path/to/local-evidence/italy-austria-native-port.json
```

The manifest paths in this example are **illustrative**. Use the actual
retained routing manifest paths that Graph Studio's existing
`refresh_graph_connectivity.py` uses; do not assume a layout or redownload.

`capture_native_f8_graph_windows.py` verifies the manifests' graph package
SHA-256s and neighbor-boundary fingerprints **before** scanning. It computes
the full intersection of the two retained graph buffer polygons and divides
that entire region into small rectangular windows (default 0.025°).
A window is not omitted because an earlier crossing worked. Output windows
contain scan bounds and per-window visited-node/tile counts. Every directed
graph ID remains independently visible. A scan failure aborts without
publishing the new capture; the original routing artifacts remain unchanged.

Each C++ invocation reopens a reader and scans one window. That is correct
but not yet performance-optimized; a future batched graph reader may avoid
repeat startup. Windows intersecting the overlap **by area** are exhaustive
over that polygon, but rectangular scans intentionally retain nearby extra
edges and cannot by themselves prove a valid intergraph crossing.

## Optional first-pass comparison (NOT reference parity)

```bash
python3 tools/audit_f8_graph_edge_parity.py \
  --native-scan /path/to/local-evidence/italy-austria-native-port.json \
  --correlations /path/to/connectivity/italy-nord-est__geofabrik-austria/correlations.json \
  --candidates /path/to/connectivity/italy-nord-est__geofabrik-austria/candidates.json \
  --proofs /path/to/connectivity/italy-nord-est__geofabrik-austria/proofs.json \
  --output /path/to/local-evidence/italy-austria-port-audit.json
```

The audit **intentionally returns exit code 2** for a Graph Studio native-port
capture. Missing edges, mode/direction evidence and fingerprints are still
reported, but only an actual capture from
`GraphEndpointNative.scanBoundaryRoadEdges` can be reference parity evidence.
A reference Android capture is additionally bounded at 512/window, so
saturated Android windows are incomplete. On identical retained versions,
compare representative motorway/one-way/local-road scans and F8-proven route
pairs, recover missing alternative handoffs, and keep the gate open until
actual Android/native evidence exists.

## Remaining acceptance gaps

1. Build and run this CLI on the Legion's real, matching Valhalla versions.
2. Export true reference Android F8 directed scanner results (both modes and
   travel directions) for the same graph versions.
3. Explain or recover missing F8 alternatives, including distinct crossings
   of the same named road and multi-region chains.
4. Optimize window scan startup only after parity evidence is captured.
5. Keep **F8 parity NOT_VERIFIED**, Android ingestion NOT_RUN, and no
   production completeness/optimality claim until the architecture contract
   evidence tiers are satisfied. See issue #73.

## Real retained-graph compile and sample checks (2026-10-14)

The following **window-level** tests were completed on the Legion's Ubuntu 26.04
with the exact tagged Valhalla **3.6.3** source, GCC 15 and the existing
unmodified Italy Nord-Est and Austria routing archives. This is new evidence
beyond synthetic CI, **not** Android F8 parity or complete discovery.

- Development lib: pinned Valhalla tag `3.6.3` (Git
  `e2f017b16080f49203de245a211b09efab09cf72`); compiled against
  the installed protobuf/lz4 dependencies with data tools, HTTP services and
  Python bindings disabled. GCC 15 requires disabling obsolete
  `ENABLE_SINGLE_FILES_WERROR` for the 3.6.3 compatibility build.
- The standalone scanner compiled and ran with **C++20**, required by the
  Valhalla 3.6.3 headers; its stdout remained clean JSON after directing
  Valhalla logging to stderr.
- Both graph archives' actual SHA-256 hashes matched their manifest values:
  Italy `e6a10d36f8622ac0e47dc3d17a8295f60b144f9a2ad478e1b5f6ef2dbea75953`
  and Austria `ee7baac93b639d0c2fefab8f90540d26d03fd28a283c73bff516a1d8bdc2bc7b`.
- **Tarvisio/Coccau**, lat 46.48–46.52, lon 13.56–13.65:
  **1,788** distinct directed eligible graph edges per regional graph,
  **224** motorcycle one-way directional edges per graph,
  all edges motorcycle/auto eligible.
- **Brenner**, lat 46.98–47.02, lon 11.48–11.55:
  **472** distinct directed eligible edges per regional graph,
  **240** motorcycle one-way directional edges per graph,
  all edges motorcycle/auto eligible.
- In both areas, 3.6.3 compile-version compatibility, uncapped
  `complete=true` / `truncated=false`, unique directed GraphIds **within
  each separate region**, JSON parsing, and `scan_window` Python checks
  passed. GraphIds across **different regions were not compared**.
- Shared buffered polygon intersection yields **3,623 window cells per graph**
  at the default 0.025° grid: **7,246 native scans** for full coverage. Only
  **four window executions** were performed in this validation run.
- Local full evidence: Graph Studio data directory
  `diagnostics/f8-native-validation-20261014.json`; four raw window captures
  next to it. Scanner binary SHA-256:
  `dc7b625c1341df9a950614d33cf1280e7fd1b9a96af726323de64f376ea24cc2`.

**Still NOT VERIFIED:** exhaustive 7,246-window discovery, native Android
F8 reference scan/identity matching, correlation/crossing sidecars
(`connectivity/` had no candidate/proof products), cross-graph directed
Valhalla leg proofs, fastest/shortest whole-journey comparison, Android
ingestion. Neither a successful window nor matching raw counts from two
regions makes their graph-local GraphIds equivalent or proves a crossing.
See issue #73.
