# Native F8 full scan topology census — 2026-11-04

**Evidence tier:** actual retained native Valhalla 3.6.3 GraphReader topology,
Italy Nord-Est ↔ Austria package `2026.10.13-1`.
**This is an exhaustive *graph-local adjacency* census over the native
overlap-window scan; it is NOT a global physical-road uniqueness proof, a
cross-graph handoff producer, Android JNI parity or approval for publication.**

## Exact inputs and validation

- Input: immutable identity-only `italy-nord-est__austria` pair, both
  independently SHA-256-checked original routing archives, manifests and
  25-km buffer polygons, retained uncapped native source scans and their
  metadata. No graph tile was rebuilt, unpacked, written or modified.
- Independently reconstructed all **3,623** intersecting 0.025° scan windows
  from both manifest-bound 25-km polygons, then proved the source catalogs
  were identical to the complete reconstructed grid. This is window-catalog
  coverage, not a claim that Android agrees with the scanner.
- `tools/census_native_f8_final_directed_edges.py` hashes a required pinned
  Valhalla 3.6.3 directed-endpoints executable *before running it*. It checks
  the exact source edges in sorted GraphId order, and validates native
  end nodes, opposing directed edges, full native outgoing adjacency, shortcut
  and nonroad continuations, mode access and absence of missing/extra rows.
- Every native directed edge is checked. No 512 cap, no successful-route
  stopping, no OSM way/name grouping, no branch/ramp exclusion, no output
  record promoted to a handoff or persisted into a release package.
- Source scans, buffers and native executable are hashed before/after
  execution to detect replacement. All output is written atomically to a
  previously nonexistent report path. A partial or corrupt native stream
  fails closed.

## Real Italy–Austria native results

| Source graph / travel direction | GraphIds reconciled | Native deadend-flagged edges | Car graph-local terminal edges | Motorcycle graph-local terminal edges | Car inside receiving 25-km polygon | Motorcycle inside receiving 25-km polygon |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Italy Nord-Est → Austria | 323,372 | 21,652 | 21,500 | 21,468 | 21,091 | 21,059 |
| Austria → Italy Nord-Est | 334,973 | 22,565 | 22,439 | 22,407 | 21,020 | 20,988 |

Total **658,345 actual source GraphIds**, one strictly validated native adjacency
record per identity. Native flags also show **12,216/12,252** mode-stranded
non-deadends in Italy (Car/Motorcycle) and **12,550/12,587** in Austria.
These are explicitly unresolved graph-local mode endpoint diagnostics;
they cannot be silently dropped, converted to unique crossing points or
declared Valhalla-legal handoffs.

**Do not interpret 21,500 or 22,439 as physical roads crossing the border.**
These numbers include ordinary physical cul-de-sacs, local edge endpoints,
buffer intersections and potentially different graph-level representations.
The full census retains distinct terminal GraphIds even where OSM way IDs
or displayed positions are shared. Filtering these by name, way, polygon,
proximity or geometry would revive the architecture we rejected.

Real output: retained only on the Legion, outside Git, at
`RoadPilotGraphStudio/diagnostics/f8-production/20261104/full-native-census-v3.json`.
Report SHA-256: `2eddf560fe544724297794ece1e8b3e20fa54d2b10ab884b9b45ec38dd659a0b` (28,078 KiB). The JSON contains the SHA-bound pair identity, all mode-terminal GraphIds,
real coordinates, source hashes, exact window coverage, counts and explicit
`NOT_VERIFIED` fields. Earlier `v1` report is a superseded immutable
diagnostic; only `v2` and `v3` include input-stability checks; `v3` also rechecks routing archives after the run.

## Why the requested one-per-physical-road milestone is still open

Native graph-local endpoints are **not** a globally established equivalence
relation identifying unique physical roads/directions. A road can be divided
into multiple directed GraphIds, span intersections and graph levels, or have
mode-dependent continuation. Conversely, separate road branches and ramps
must not be collapsed merely because they share a name, way ID or snap
location. Every terminal requires a rigorous physical-road lineage and
original Valhalla route-edge check before asserting one unique last retained
edge for that actual road/direction. PR #117's 10 selected real original-route
proofs remain valid but cannot establish global uniqueness.

The next production increment must bind each real directional road lineage
to its final source GraphId using full native geometries/topology and the
**original** TripLeg edge IDs, then reconcile true cross-graph B receiver
roads and actual legal mode-specific A→X / X→B legs. Ambiguous lineage must
remain separately represented and `NOT_VERIFIED`; it is not safe to hard
reject any source candidate to make the inventory look complete.

## Real Android JNI acceptance gate

On 2026-11-04 the Legion was online, but `adb devices -l` returned
**zero connected physical Android devices**. The Android SDK's AVD list is
not physical-device evidence. No same-graph raw Android JNI capture was
available. Real JNI parity therefore **was not executed** and stays
`NOT_VERIFIED`.

Android baseline: `SmartRide-Next/native/on-device-valhalla/builder_jni.cpp`
clamps the native scanner to 512 results per call; Kotlin
`FrontierRouteLocalRecovery.kt` groups distinct receiver candidates by
`receiverRoadKey()`. Both behaviors can suppress legitimate F8 alternatives.

Device acceptance requires, in order:

1. Physical Android connected and authorized for ADB; record device/OS and
   exact installed native engine/JNI/app commit, and hash installed extracted
   Valhalla graph archives **on the device** against the manifest-bound
   Italy–Austria source archives.
2. Instrument the **actual shipped JNI call** and the Kotlin reduction to
   capture raw returned *directed* GraphIds, exact requested bounding boxes
   and requested/returned counts, plus after-grouping GraphIds, separately
   per source/receiver graph, mode and direction. Do not substitute a
   host reimplementation, synthetic fixture or independent
   `trace_attributes(edge_walk)`.
3. Run `tools/audit_native_f8_android_jni_parity.py` against those exact
   reference windows and the same preserved native graph scan hashes.
   Reconcile all missing/extra IDs, per-window cap saturation and road-key
   grouping losses. Repeat with 512-cap and road-key losses addressed *without*
   deleting F8 alternatives.
4. Verify real A/B Valhalla original-route IDs, destination arrival and
   FASTER/SHORTER route-choice equivalence for Car and Motorcycle in both
   directions, including one-way, ramp, motorway and local-road alternatives.
   Add Austria–Germany and multi-hop cases before production acceptance.
5. Independent security, data-integrity and architecture review, exact-head
   CI, device evidence, owner merge/release authorization and an atomic
   rollback path preserving generalized Android F8 fallback.

Until these gates pass: `globalOneFinalRetainedEdgePerPhysicalRoadDirection`
and `f8GraphEdgeParity` remain `NOT_VERIFIED`; production publication is
`BLOCKED`. No retired OSM/correlation/matrix producer was restored.
