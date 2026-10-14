# Native F8 graph-edge audit (evidence tier: preparatory)

This is a **read-only comparison harness**, not the native F8 scanner, not an
exhaustive discovery algorithm, and not proof of F8 parity. Graph Studio PR #75
broadens OSM seeds across retained graph buffers, but actual directed Valhalla
graph edges can differ from those seeds. See architecture contract B1–B4 and
[issue #73](https://github.com/kandyman991/RoadPilot-Offline-Data/issues/73).

## What it checks

`tools/audit_f8_graph_edge_parity.py` checks a native RoadPilot
`GraphEndpointNative.scanBoundaryRoadEdges` capture **against the exact
same graph-and-boundary fingerprint pair** present in Graph Studio's existing
`connectivity/<pair>/correlations.json` and `candidates.json`.

It compares **directed graph IDs**, not just road names, OSM way IDs or nearby
coordinates. It reports every observed native edge not represented in the
Graph Studio correlated edges/candidates and every known F8-proven
Graph A → Graph B edge pairing absent from the candidate product. It refuses
mismatched fingerprints, incomplete scan windows, empty proof samples and
silent truncation. It does not mutate the graph, cache, sidecars or downloaded
source PBFs.

If the retained Graph Studio `proofs.json` is available, provide it to audit
**mode-specific, directional exact-edge Valhalla proof**, rather than merely
detecting that a physical candidate pair exists. Without the optional proof
artifact the report explicitly states `graphStudioProofComparison: NOT_RUN`;
a candidate present in `candidates.json` is **not** assumed validated.

The report always says `f8GraphEdgeParity: NOT_VERIFIED`. Even a clean
comparison only matches the supplied observed scan scope; it does **not**
establish that every relevant window was scanned or that the most economical
whole-journey route is chosen.

**Native scanner result cap — verified against RoadPilot code:** Android's
`FrontierGpsRoadDirectionRecovery` requests `MAX_SCAN_RESULTS_PER_WINDOW=4096`,
but `native/on-device-valhalla/builder_jni.cpp::scan_boundary_road_edges`
actually clamps the argument to **512**. Any sample with 512 returned records
must be marked **INCOMPLETE**, even if its capture labels it complete and
untruncated. A smaller requested cap also becomes inconclusive when saturated.
The capture producer cannot infer completeness from its requested 4096 limit.
Offline exhaustive scanning will require actual uncapped graph-edge enumeration,
not blindly accepting the bounded runtime JNI result.

## Inputs and use on Legion

First refresh the exact retained Italy Nord-Est ↔ Austria sidecars with
**Build → Refresh connections**, without redownloading/rebuilding unchanged
region graphs. Preserve original `correlations.json` and `candidates.json`.

The remaining prerequisite is a genuine **native F8 edge capture** on those
same graph versions. Its capture producer MUST use the native
`GraphEndpointNative.scanBoundaryRoadEdges` implementation rather than
relabeling OSM highway sampling as native evidence. Until that exporter exists,
this audit cannot be run as a meaningful real-graph parity check.

Expected JSON envelope (illustrative **schema only**, NOT test evidence):

```json
{
  "schema": "roadpilot.native-f8-edge-scan",
  "version": 1,
  "scanner": "GraphEndpointNative.scanBoundaryRoadEdges",
  "pairId": "italy-nord-est__geofabrik-austria",
  "fromGraph": {"graphFingerprint": "sha256:<actual A graph fingerprint>"},
  "toGraph": {"graphFingerprint": "sha256:<actual B graph fingerprint>"},
  "fromBoundaryFingerprint": "sha256:<actual A boundary fingerprint>",
  "toBoundaryFingerprint": "sha256:<actual B boundary fingerprint>",
  "scans": {
    "from": {
      "complete": false,
      "windows": [{"complete": false, "truncated": false, "maxResults": 4096, "returned": 0}],
      "edges": [{"graphId": 123, "wayId": 10001}]
    },
    "to": {
      "complete": false,
      "windows": [{"complete": false, "truncated": false, "maxResults": 4096, "returned": 0}],
      "edges": [{"graphId": 456, "wayId": 10001}]
    }
  },
  "provenHandoffs": [
    {"fromGraphId": 123, "toGraphId": 456, "mode": "motorcycle", "direction": "from-to"}
  ]
}
```

Never mark `complete:true` unless window enumeration actually completed
without hit-limit truncation, exceptions or missing windows. The
`provenHandoffs` entries must originate from **actual F8 directional
Valhalla-backed proof**, not by assuming every adjacent pair works.
Include both travel directions and Motorcycle/Car evidence when obtainable.

```bash
python3 tools/audit_f8_graph_edge_parity.py \
  --native-scan /path/to/real-native-f8-scan.json \
  --correlations /path/to/connectivity/italy-nord-est__geofabrik-austria/correlations.json \
  --candidates /path/to/connectivity/italy-nord-est__geofabrik-austria/candidates.json \
  --proofs /path/to/connectivity/italy-nord-est__geofabrik-austria/proofs.json \
  --output /path/to/local-evidence/f8-parity-audit.json
```

Return code 0 means **the supplied observed windows matched** and valid
native proven pairs were present; it still does not prove whole-frontier
completeness. Return code 2 means incomplete/uncertain coverage or a missing
native alternative. Invalid/stale identities are fatal. The output is local,
not automatically published.

## Acceptance remaining

- Export authentic native F8 directed-edge snapshots and audited coverage
  for Italy Nord-Est ↔ Austria, Austria ↔ Oberbayern, motorway carriageways,
  one-way/local roads and representative three-region chains.
- Enumerate the entire relevant graph coverage (not a few known success
  coordinates), eliminate false negatives and report unresolved edges.
- Compare all relevant directional/mode-specific Valhalla proofs, plus
  end-to-end FASTER/SHORTER route choices without first-success lock-in or
  unsupported 20-chain optimality claims.
- Verify Android package ingestion, version mismatch/rollback and F8 fallback.

Do **not** change `f8GraphEdgeParity` to VERIFIED or close #73/#512 from
synthetic CI, a small successful sample or this harness alone.
