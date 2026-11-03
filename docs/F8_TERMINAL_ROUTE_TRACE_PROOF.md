# F8 terminal handoff directed-route proof (increment 1)

**Status:** Diagnostic, read-only, opt-in. Not a production crossing producer.
**PR #107 review correction:** Matched graph-local traces are **not** a validated inter-graph transition. Previous success labels overstated the proof scope.
**Development owner:** Graph Studio. Source of record: current `main` after PR #106.
**Architecture boundary:** D-017 / PR #105 remains a separate, unmerged
design draft. This increment does not adopt, merge or implement that PR.

## Problem demonstrated on real graph data

A Valhalla route to a terminal GPS coordinate, followed by a route in the
other graph, can succeed **without traversing the nominated source terminal
directed edge**. That invalidates a simple claim of a proven terminal handoff.

With the retained Italy Nord-Est / Austria `2026.10.13-1` graphs and
motorcycle/car test journey:

- Origin `46.501885, 13.592668` (Italy).
- Destination `46.592234, 13.846448` (Austria).
- Nominated Italy source terminal GraphId `546037568058`.
- Nominated Austrian receiving incoming GraphId `548990358074`.
- Terminal coordinate `46.5910664, 13.8283774`.
- The independently traced **last Italy GraphId is `1333151531017`**,
  not the nominated terminal. A GPS match or successful legs must NOT
  be promoted into a verified connection.
- The graph-local endpoints also differ by roughly **5.5 metres**,
  which fails the experimental 1 m exact-endpoint test. This is an
  *unproven* observation, not a globally rejected alternative.

These are graph-local GraphIds; never compare numeric IDs between graphs.

## New opt-in proof command

`tools/probe_native_f8_terminal_handoffs.py` reuses the pre-existing
native graph manifest verifier and actual Valhalla route/trace functions.

It validates retained graph archive SHA-256 against both manifests and
the exact pair fingerprints/boundary identities. It consumes the
checksum-retained receiver topology and native outgoing-edge snapshots
from PR #106, checks receiver-directed identity, and builds a **bounded
journey-scoped candidate order** without overwriting or publishing data.

A selected hypothesis has **matched graph-local route traces for one journey** only when:

1. Graph A's actual route ends at the requested terminal (1 m tolerance).
2. Graph A's **last traced directed edge** equals the nominated source edge.
3. Graph B's actual routed start coincides with the source endpoint (1 m).
4. The traced Graph B route uses an outgoing directed edge of the nominated
   receiving node, or traverses the nominated receiving incoming edge
   immediately followed by a valid outgoing directed edge.
5. Source, receiver incoming, and receiving outgoing edges have the
   appropriate mode-specific forward-access bits.
6. Source terminal and nominated receiver endpoint are within 1 m.
7. Both graph-local route legs successfully reach their requested
   start/destination; nonzero reported offsets, trace failures and
   mismatches remain explicit.

**Scope caution:** The 1 m threshold is an *experimental graph-local trace match gate*, not a
discovery eligibility filter. All unprobed candidates remain unproven.
An existing route starting exactly at the receiving node cannot by
itself prove inter-graph physical continuity or turn restrictions; those remain `NOT_VERIFIED`
even if an individual two-leg trace passes. F8 parity and global
FASTEST/SHORTEST optimality are also unverified.

The earlier Android JNI 512 cap, Kotlin name/ref suppression, historical
OSM sampler, connector matrices and retired multiregion planner are
**not** imported or restored.

## Reproduction on Legion

The retained provisional receiver evidence is located at
`~/RoadPilotGraphStudio/diagnostics/s1/20261103/receiver-directed-v1/`.
From a checkout with this increment:

```bash
python tools/probe_native_f8_terminal_handoffs.py \
  --pair /path/to/f8-native/italy-nord-est__austria/PAIR/pair.json \
  --receiver-audit /path/to/receiver-directed-v1/receiver-directed-audit-v2.json \
  --from-native-adjacency /path/to/receiver-directed-v1/italy-receiver-native-outgoing-v2.jsonl \
  --to-native-adjacency /path/to/receiver-directed-v1/austria-receiver-native-outgoing-v2.jsonl \
  --from-manifest /path/to/italy-nord-est-routing-2026.10.13-1-manifest.json \
  --to-manifest /path/to/austria-routing-2026.10.13-1-manifest.json \
  --direction from-to --mode motorcycle \
  --start-lat 46.501885 --start-lng 13.592668 \
  --end-lat 46.592234 --end-lng 13.846448 \
  --max-probes 6
```

To reproduce the specific *wrong source edge* observation, add:

```text
--focus-source-graph-id 546037568058 --focus-receiver-graph-id 548990358074
```

Output is a single JSON diagnostic report on stdout. Use a scratch file
outside Git if retaining results. No automatic write, publication,
replacement or graph mutation is performed. Explicit selection is still
one of the full catalog's hypotheses; the rest are counted as unprobed.

## Measured bounded journey outcomes (2026-11-03)

| Directed journey | Vehicle | Probed | Positively proven | Unprobed provisional relationships |
|---|---|---:|---:|---:|
| Italy → Austria | Motorcycle | 6 | 0 | 1,336 |
| Italy → Austria | Car | 6 | 0 | 1,336 |
| Austria → Italy | Motorcycle | 6 | 0 | 1,248 |
| Austria → Italy | Car | 6 | 0 | 1,248 |

**Do not interpret these results as no crossings exist.** This is a
bounded, distance-ranked test, not exhaustive proof. Some observations
are near an unrelated route, some have graph-local source-edge mismatches,
and some have source/receiver endpoint location gaps.

The reports are kept outside Git at
`~/RoadPilotGraphStudio/diagnostics/s1/20261103/terminal-proof-*.json`.
Source/pair fingerprints and retention identities are preserved.

## Next architecture and acceptance gates

- True receiver-to-source directed geometrical continuity, including
  differing segment divisions between the independent graphs.
- Bidirectional, mode-specific legal turn continuity across the seam,
  not merely route-at-node simulation.
- Meaningful vehicle journeys, FASTER and SHORTER comparisons,
  branched/carriageway/ramps, multi-hop alternatives, real Android JNI
  parity and terminal-only equivalence evidence.
- Independent architecture/security/data-integrity review, exact-head
  CI, owner-authorized merge. No release or production sidecar.

Until then: `coverage=NOT_VERIFIED`,
`androidF8Parity=NOT_VERIFIED`, `handoffTurnLegality=NOT_VERIFIED`,
`productionPublication=BLOCKED`.


## Review correction after PR #107

The original probe labeled two matching graph-local traces
VALIDATED_FOR_THIS_JOURNEY and set
exactCrossGraphDirectedHandoff=VALIDATED_FOR_THIS_JOURNEY_ONLY.
That was stronger than the evidence: it did not check whether the last
physical road portion in Graph A was present as directed traversable geometry
in Graph B, nor cross-seam turn restrictions.

The corrected diagnostic returns
status=GRAPH_LOCAL_TRACES_MATCHED_FOR_THIS_JOURNEY,
graphLocalDirectedLegTrace=MATCHED_FOR_THIS_JOURNEY_ONLY, and
exactCrossGraphDirectedHandoff=NOT_VERIFIED. Ranking remains explicitly
within successfully *matched graph-local traces*, not among verified
cross-graph routes. Inconclusive route-engine responses remain
INCONCLUSIVE rather than being misclassified as negative proofs.

Physical continuity must be assessed using graph-native directed road geometry,
allowing different node subdivisions inside the two independent graphs.
A matching endpoint within 1 metre must **not** become a production discovery
eligibility rule; all nonmatching/unprobed alternatives remain unresolved.
