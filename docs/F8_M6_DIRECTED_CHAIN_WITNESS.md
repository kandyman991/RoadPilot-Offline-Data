# M6a — Native directed receiver-chain witness across independently split graphs

**Status:** Read-only, opt-in development diagnostic only. No Android routing, `.gph` mutation, Graph Studio production discovery/publisher, artifact schema, release, or installed application change. Base: merged M5 and the binding D-014/D-015 F8 architecture.

## Problem and diagnostic boundary

One long source road edge in Graph A can correspond to multiple differently subdivided directed edges in Graph B. Looking at one B edge or coincident positions is insufficient to prove a crossing. M5 showed that valid B-local turns may coexist with a full-journey Graph A route that never uses the nominated A final edge.

M6a examines **one explicitly nominated A final directed edge and one explicitly nominated chain of 2–16 B directed edges**. No frontier-wide inventory, pruning, or old OSM anchor/connector-matrix pipeline is involved. No observation removes any native F8 candidate; the source is **nominated**, not independently certified as the last edge of a particular completed journey.

## Code and checks

- `tools/probe_native_f8_directed_chain.py` checks exact retained routing archive, graph and neighbor-boundary fingerprints and requires pinned Valhalla 3.6.3.
- The pinned native GraphReader extractor's `--continuations` mode now records `nativeOutgoingDegree`. The diagnostic verifies complete degrees, all outgoing native IDs and mode/access flags, matching successor identity and exact Graph B node adjacency **for every selected B edge, including its final edge**. It preserves all nonselected branches, reverse edges and mode-inaccessible edges as evidence. Each selected successor now explicitly reports `selectedNextIsOpposingReverse` (true/false, or null for the terminal selected edge) and the report counts selected immediate reverse links. This is an observation, not an exclusion or a forward-turn proof. Malformed native input fails closed as a diagnostic error, never a global handoff rejection.
- After graph-native adjacency verification, the selected directed B geometry is concatenated. The final 20 metres of Graph A's nominated directed source edge are compared against the full B chain, allowing different native road splits. One-metre sample alignment, opposed direction and ambiguity are **observations**, not cross-graph legal turn proofs or eligibility filters.
- A separate real B-local Valhalla route is checked for the complete exact consecutive selected B directed GraphId sequence, plus snapped start/end within 2 metres. A matched path proves only **that B graph-local route**, not an A→B seam.
- Output always includes `crossGraphPhysicalContinuity=NOT_VERIFIED`, `crossSeamTurnLegality=NOT_VERIFIED`, `androidF8Parity=NOT_VERIFIED`, `discoveryCoverage=NOT_VERIFIED`, `routeOptimality=NOT_VERIFIED` and `productionPublication=BLOCKED`.

## Reproduction on Legion

Run from the M6 branch, with the existing, immutable Italy Nord-Est/Austria graph pair:

~~~bash
P="$HOME/RoadPilotGraphStudio"
PATH="$HOME/.cache/app.roadpilot.graphstudio/python-env/bin:$PATH" python \
  tools/probe_native_f8_directed_chain.py \
  --pair "$P/f8-native/italy-nord-est__austria/e6a10d36f-ee7baac93-43d085-958523/pair.json" \
  --from-manifest "$P/builds/italy-nord-est/italy-nord-est-routing-2026.10.13-1-manifest.json" \
  --to-manifest "$P/builds/austria/austria-routing-2026.10.13-1-manifest.json" \
  --native-endpoints-binary "$P/diagnostics/m6/native-directed-chain-build/native_f8_directed_endpoints" \
  --direction from-to --mode auto \
  --source-graph-id 1482679618 \
  --receiver-edge-id 754343470402 --receiver-edge-id 669954073922
~~~

The native endpoint extractor was independently compiled against the installed pinned Valhalla 3.6.3 library, without modifying any immutable graph archives.

## Actual focused results — November 4, 2026

Both exact retained regional graph packages: 2026.10.13-1. GraphIds are always interpreted graph-locally.

| Direction | Mode | Source A nominated | B selected directed sequence | Native B adjacency | A tail/B sample | B-local Valhalla |
| --- | --- | --- | --- | --- | --- | --- |
| Italy→Austria | Car | 1482679618 | 754343470402 → 669954073922 | confirmed | aligned | exact chain traced |
| Italy→Austria | Motorcycle | 1482679618 | 754343470402 → 669954073922 | confirmed | aligned | exact chain traced |
| Italy→Austria | Car | 1482679618 | 754343470402 → 669987628354 | confirmed | aligned | exact chain traced |
| Italy→Austria | Motorcycle | 1482679618 | 754343470402 → 669987628354 | confirmed | aligned | exact chain traced |
| Italy→Austria | Car | 1482679618 | 754343470402 → 670054737218 | confirmed | ambiguous | INCONCLUSIVE |
| Austria→Italy | Car | 754343470402 | 1482679618 → 1012917570 | confirmed | ambiguous | INCONCLUSIVE |
| Austria→Italy | Motorcycle | 754343470402 | 1482679618 → 1012917570 | confirmed | ambiguous | INCONCLUSIVE |

**PR #112 independent review correction:** Three selected B links were
actual native immediate opposing reverses: the Italy→Austria Car sample
ending `670054737218`, and both Austria→Italy samples ending `1012917570`.
The latter have only one B outgoing edge, namely that reverse. These
are now explicitly identified in each output; the previous generic
native-adjacency label alone did not distinguish them from a non-opposing
continuation. No result is filtered or promoted because of this distinction.

**Native build assurance:** The standalone C++ extractor was freshly compiled
against pinned Valhalla 3.6.3, and the changed diagnostic was re-run on all
seven exact graph-backed samples. See
[`F8_M6_NATIVE_EXTRACTOR_BUILD_PROVENANCE.md`](F8_M6_NATIVE_EXTRACTOR_BUILD_PROVENANCE.md)
for the actual compiler/CMake commands, linked library and binary SHA-256,
compile commands, archive integrity and smoke records. Hosted Linux CI
checks the app and Python regressions but does **not** compile this native
tool; the SHA-bound Legion native build plus real-graph smoke is the
review's accepted evidence alternative.

None of these results proves a legal physical A→B crossing or an actual **completed** A-to-B journey. Positive evidence is strictly B-local. Negative/inconclusive observations do not disqualify alternative roads or chains.

Unpublished raw JSON and `SHA256SUMS` are retained outside Git at `~/RoadPilotGraphStudio/diagnostics/m6/directed-chain-20261104/`. No Android, installer, release, graph mutation or R2 publication occurred.

## Acceptance and follow-up

New deterministic regressions verify split B edges, accurate native adjacency degree, preserved branches, wrong/duplicate edges, forged mode masks, geometry gaps/opposed direction, different numeric IDs per graph, snaps, and incomplete route traces. The full Graph Studio Python suite is rerun.

**M6b next gate:** Find a *meaningful real journey* for which the actual last Graph A directed edge and exact Graph B first/continuation edge sequence agree, then test physical directed seam continuity and route-specific legality with Valhalla for both travel directions and Car/Motorcycle. Android JNI parity, exhaustive alternatives, FASTEST/SHORTEST and multi-hop remain separate unverified gates. Never publish M6a data as a native F8 production package.
