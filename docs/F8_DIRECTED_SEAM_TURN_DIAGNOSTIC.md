# S1 / M4 — F8 selected terminal, directed segment and native B-turn evidence

**Development-only diagnostic, opt-in, read-only.** This milestone extends
PR #109 and depends on PR #108. No Graph Studio production discovery,
Android routing or graph archive is changed. No cross-region handoff is
approved for publication.

## Architecture boundary

The only source A identity is the **final directed edge of the selected road**
in the existing 25 km overlap, as requested in the accepted owner design.
Graph B is independently built. Its **nominated incoming directed edge**
and every immediate native outgoing edge at its end node are evaluated.
This is a one-terminal, one-receiver-node, finite local diagnostic, not a
buffer-wide database of multiple intermediate edges on every road.

No numeric GraphId equality between A/B establishes physical identity.
The native directed edge identities are only meaningful in their own
manifest-fingerprint-verified regional Valhalla graph. Neither a common
OSM way ID nor a nearby node is sufficient to validate a crossing.

The accepted F8 design in docs/ARCHITECTURE_CONTRACT.md (A2–A3, B1–B4,
C1–C3, D1–D4) remains authoritative. The currently operating Android
routing entrypoint includes ManagedFrontierChainRoutingRuntime.kt;
FrontierRouteLocalRecovery.kt describes older receiver reduction and cannot
be silently adopted as a complete reference. D-017 in PR #105 remains
an unapproved design proposal.

## What this increments

The opt-in tool tools/probe_native_f8_directed_turn.py:

1. Validates SHA-256-identical retained graph archives using both routing
   manifests and the exact pair/boundary fingerprints before any probe.
2. Reads the single nominated A terminal edge, B nominated incoming edge,
   and **all** immediate B outgoing edges from Valhalla 3.6.3 GraphReader.
   This includes native reverse-edge, non-road and mode-inaccessible
   observations. It fails closed if its 256-edge count or 250,000-vertex aggregate
   safety bounds are exceeded, identities mismatch or the native capture is
   incomplete.
3. Uses graph-native full directed polylines to annotate whether the A
   edge's sampled final portion and the nominated B incoming edge share
   consistent forward progression, opposite progression, or insufficient
   evidence. This is **not a filter** and cannot rule out another B edge
   or a split B geometry. The 1-metre geometry threshold is a reporting
   tolerance only, never a production discovery criterion.
4. Builds an explicit B-local Valhalla route from *inside* the B incoming
   edge to *inside* each B outgoing edge. A turn is recorded as
   B_GRAPH_DIRECTED_TURN_TRACED_FOR_THIS_LOCAL_ROUTE **only when the real
   route's directed trace includes the exact two consecutive B GraphIds**,
   with snapped endpoint offsets within 2 m.
5. Continues through every outgoing edge within the user-specified
   diagnostic probe budget; unprobed edges are retained and explicitly
   marked NOT_PROBED_BUDGET. An alternative route, snap away, route failure
   or truncated trace never means the candidate is legally impossible.
   Limits are **not** Android's 512-result JNI cap, a production
   crossing gate, or a frontier completeness statement.

A B-local routed turn is evidence for *that graph and vehicle mode*,
not for transferring from independent graph A into B. A full cross-graph
handoff still needs physical topology proof, exact journey A-edge
termination, a coherent B forward entry and actual final destination.
A trace through an unrelated B edge or a merely successful Valhalla route
is not a proof. Cross-seam restrictions are explicitly NOT_VERIFIED.

Output is a single JSON diagnostic on stdout. Temporary files are
created under a disposable scratch directory. No package, sidecar,
database, installed app, connectivity artifact or graph file is written.

## Reproduction on Legion — real archived graphs

Use the native GraphReader extractor from PR #109, compiled and verified
against pinned local Valhalla 3.6.3, then from a checkout containing
this increment:

~~~bash
P="$HOME/RoadPilotGraphStudio"
python tools/probe_native_f8_directed_turn.py \
  --pair "$P/f8-native/italy-nord-est__austria/e6a10d36f-ee7baac93-43d085-958523/pair.json" \
  --from-manifest "$P/builds/italy-nord-est/italy-nord-est-routing-2026.10.13-1-manifest.json" \
  --to-manifest "$P/builds/austria/austria-routing-2026.10.13-1-manifest.json" \
  --native-endpoints-binary /tmp/roadpilot-f8-geometry-build/native_f8_directed_endpoints \
  --direction from-to --mode auto \
  --source-graph-id 1482679618 \
  --receiver-incoming-graph-id 754343470402 \
  --max-turn-probes 16
~~~

Both source/receiver values are separate **graph-local** IDs. Other
regions/versions require their own retained matching manifests and
fresh source/receiver GraphIds. Both travel directions and both car and
motorcycle modes are supported, but only explicitly tested journeys
have evidence. Never promote a sample to exhaustive F8 parity.

### Measured focused outcomes — November 3, 2026

Same unchanged Italy Nord-Est/Austria 2026.10.13-1 graph packages,
independent fixed Valhalla 3.6.3 binaries:

| A terminal / B incoming (GraphIds) | Selected mode | B outgoing probed | Exact directed B turn traced | Other results |
|---|---|---:|---:|---|
| 1482679618 / 754343470402 | car | 4 of 4 | **3** | 1 inconclusive |
| 1482679618 / 754343470402 | motorcycle | 4 of 4 | **3** | 1 inconclusive |
| 754343470402 / 1482679618 (reverse) | car | 1 of 1 | 0 | 1 inconclusive |
| 754343470402 / 1482679618 (reverse) | motorcycle | 1 of 1 | 0 | 1 inconclusive |
| 100837375794 / 111172140850 | car | 4 of 4 | 0 | 3 unproven, 1 inconclusive |
| 40338757882 / 53961857274 | car | 5 of 5 | 0 | 5 unproven |

For the first two forward-mode samples, source-tail and B incoming geometry displayed
**aligned sampled directed order**. For the other two the sampled
directed order was **opposed**, but no production candidate was excluded
and every B outgoing edge remained visible. The tests do not determine
whether another B entering edge or separate Graph B subdivision permits
an F8 crossing in those locations.

The complete raw JSONs plus SHA256SUMS are retained **outside Git** at
~/RoadPilotGraphStudio/diagnostics/s1/20261103/directed-turn-m4-v1/.
Earlier focused Tarvisio/Coccau-style sample source 546037568058, B
incoming 546037568058 (motorcycle) returned 0/4 B-local traced turns;
B incoming 548990358074 (car) returned 0/1. Native point snapping
made those short-edge test routes unproven. This is *not* a declaration
that either crossing is invalid.

## Verification tiers, gaps and next gate

Local synthetic tests cover consecutive vs nonconsecutive B directed
edges, mismatching mode, alternative route, snapped-away endpoints,
missing traces, multiple outbound choices, budget transparency, opposite
geometry, split-geometry uncertainty and corrupted native captures.
CI architecture contract gate includes this suite.

**Always reported:** crossGraphDirectedPhysicalContinuity=NOT_VERIFIED;
crossSeamTurnLegality=NOT_VERIFIED; androidF8Parity=NOT_VERIFIED;
discoveryCoverage=NOT_VERIFIED; routeOptimality=NOT_VERIFIED;
productionPublication=BLOCKED.

Next acceptance gate is **graph-native directional physical equivalence**
across independently segmented A/B roads (not just matching a few
geometry samples), route-exact source last-edge and B first-edge
confirmation in *the same meaningful end-to-end journey*, mode-specific
cross-seam turn checks, and real Android JNI F8 graph-edge parity.
Test both travel directions, car and motorcycle, major carriageways,
ramps, alternative candidates, FASTER/SHORTER and multi-hop.
Keep discovery open until every F8-relevant alternative is accounted for.
