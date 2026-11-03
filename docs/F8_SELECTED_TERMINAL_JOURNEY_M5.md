# M5 — F8 selected terminal + receiving-turn journey diagnostic

**Status:** implementation/test evidence only, read-only and opt-in. Stacked
on PR #110 (receiving-graph turn diagnostic), PR #109 (directed geometry), and
PR #108 (accurate graph-local proof labels). This does not change routing,
production discovery, Android, graphs, published packages, or the UI.

## Why this increment exists

PR #110 proved some Graph B local directed turns with actual Valhalla route
traces, but a B-only turn is not a valid transfer from an independent Graph A.
PR #108 independently proved or disproved nominated A-terminal and B-entry
trace evidence **for a selected full journey**. M5 now evaluates both existing
proofs under the *same* explicit A-final-edge/B-incoming-edge hypothesis and
exact graph manifests. The results remain separate; no stronger cross-graph
proof is inferred from their coincidence.

One nominated source-final directed edge is inspected, not a cloud of
intermediate edges within the 25 km overlap. B's exact native incoming edge
and **all** immediate outgoing graph-local directed edges are retained.
No road name, OSM way ID, graph-local ID coincidence, heading, proximity, or
first-success match filters discovery. The nominated source may not be a true
terminal: its identity is explicitly marked nominated, not exhaustive.

## Tool

`tools/probe_native_f8_selected_journey.py`:

1. Checks SHA-256 and exact graph/boundary identity through the established
   Graph Studio retained-archive verifier and Valhalla 3.6.3 native extractor.
2. Reads one explicit source edge, one nominated receiver incoming edge, and
   the **complete native B outgoing edge list**, fail-closing on invalid,
   duplicate, malformed, or excessive native evidence.
3. Reuses PR #110's bounded local B turn probe; each tested outgoing directed
   edge is compared to the **actual consecutive** Valhalla traced edge IDs.
   Unprobed B alternatives remain explicit NOT_PROBED_BUDGET entries.
4. Reuses PR #108's selected-journey trace check: Graph A must route to the
   exact selected terminal with that exact **last directed GraphId**, and
   Graph B must actually start at the normalized handoff, follow a valid
   nominated local entry/continuation, and reach the destination.
5. Reports the results **separately** as `bLocalTurnObservation` and
   `twoGraphJourneyObservation`. Even if both match, the physical
   cross-graph seam, legal directed transfer, Android JNI parity, completeness,
   and global route optimality stay NOT_VERIFIED; publication remains BLOCKED.

This is **not** a production connection generator, exhaustive scanner,
legacy matrix replacement, or a positive/negative F8 handoff catalog.
An unsuccessful or inconclusive selected journey never excludes its road or
other directed alternatives from future discovery.

## Real retained-graph reproduction

Run from this branch on the Legion with the existing, immutable
Italy Nord-Est/Austria 2026.10.13-1 archives, pair manifest and native binary:

~~~bash
P="$HOME/RoadPilotGraphStudio"
PATH="$HOME/.cache/app.roadpilot.graphstudio/python-env/bin:$PATH" python \
  tools/probe_native_f8_selected_journey.py \
  --pair "$P/f8-native/italy-nord-est__austria/e6a10d36f-ee7baac93-43d085-958523/pair.json" \
  --from-manifest "$P/builds/italy-nord-est/italy-nord-est-routing-2026.10.13-1-manifest.json" \
  --to-manifest "$P/builds/austria/austria-routing-2026.10.13-1-manifest.json" \
  --native-endpoints-binary "$P/diagnostics/s1/20261103/m5-native-build/native_f8_directed_endpoints" \
  --direction from-to --mode auto \
  --source-graph-id 1482679618 --receiver-incoming-graph-id 754343470402 \
  --start-lat 46.501885 --start-lng 13.592668 \
  --end-lat 46.592234 --end-lng 13.846448 \
  --max-turn-probes 16
~~~

The native C++ binary can be compiled with `tools/native-f8-edge-scan/CMakeLists.txt`
against the separate local, pinned Valhalla 3.6.3 development library.
The example paths are local test artifacts, not repository or release assets.

### Real November 3 evidence

Focused evidence from the same two immutable graph archives and
journey coordinates (the reverse trip swaps origin/destination):

| Travel direction | Mode | B-local turns traced | Selected whole journey |
| --- | --- | ---: | --- |
| Italy→Austria | Car | 3/4 | **UNPROVEN** — Graph A route did not succeed |
| Italy→Austria | Motorcycle | 3/4 | **UNPROVEN** — Graph A route did not succeed |
| Austria→Italy | Car | 0/1 | **UNPROVEN** — actual Graph A last edge differed from nominated terminal |
| Austria→Italy | Motorcycle | 0/1 | **UNPROVEN** — actual Graph A last edge differed from nominated terminal |

The IDs used for Italy→Austria are A `1482679618`, B `754343470402`;
the reverse investigation swaps those nominated identities. All results
remain separate mode/direction and graph-local observations. None proves
that the corresponding handoff is impossible in another journey or at
another terminal.

Raw JSON/checksums are stored outside Git at
`~/RoadPilotGraphStudio/diagnostics/s1/20261103/selected-journey-m5-v1/`.
No real Android JNI, multi-region FASTER/SHORTER, or cross-seam turn
acceptance evidence exists for this increment.

## Tests and acceptance status

The new synthetic tests include both graph-local proofs matching without
cross-seam promotion, A-last-edge mismatch, B-entry mismatch, snap-away,
mode access, all B alternatives retained under an explicit probe budget,
fraudulent B native adjacency, same numeric GraphId across independent
graphs, and invalid data. The full repository Python suite is also run.

Next work: physical cross-graph directed equivalence across differing
regional graph segmentation (without suppressing another crossing),
route-exact A-final/B-first evidence in a complete relevant journey,
real Android JNI scan parity, both vehicle modes/directions, all crossing
alternatives, and final-route quality. Nothing here closes #73, #82 or
Android #512, and none is authorization to merge or publish.
