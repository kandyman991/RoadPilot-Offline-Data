# F8 S1 — Directed terminal road geometry observation (read-only)

**State:** DEVELOPMENT DIAGNOSTIC, not an approved crossing algorithm.
**Dependencies:** PR #107 graph-local trace tests and PR #108 semantics correction.
**Graph pair:** exact retained Italy Nord-Est / Austria Valhalla 3.6.3 archives,
package 2026.10.13-1. No graph rebuild and no Android changes.

## Why this phase exists

The source road's final directed edge may lie well inside the other
region's buffered graph without the two independent Valhalla graphs placing
a node at exactly the same location. Matching source/receiver *end nodes*
is not a complete test of directed physical road continuity.

This increment extracts full, graph-native, directed edge polylines via the
existing read-only native GraphReader endpoint utility, newly supporting
--geometry. It tests selected source-terminal geometry against EVERY
explicitly supplied receiver directed edge, including alternative
carriageways, opposite directions, differing way IDs, and nodes split at
different positions. It does not generate a matrix of all edges in the
overlap, does not take a cached first-success shortcut, and never compares
the two graphs' numeric GraphIds to infer identity.

The Python observation command checks the exact retained graph archive
SHA-256 fingerprints against the pair manifests before extracting
geometry directly from those archives. It requires the separately built
Valhalla 3.6.3 native extractor and never accepts premanufactured
geometry JSONL as a source of routing authority.

The full directed geometry is sampled over at most the *last 20 m of the
selected source edge*. Every sample is compared to every selected B edge's
polyline. Reported distance (within 1 m) is an observation threshold,
not a candidate-generation or route rejection filter. A B node can be
farther away while the A terminal lies on the B road segment.

Mode access bits, source/receiver OSM way equality and locally observed
directional tangent are annotations only. None substitutes for Valhalla
routing, node-level turn restrictions, full road-to-road topology, or
complete Android F8 alternative discovery.

## Independent real-archive reproduction

First build the native GraphReader tool on the Legion using the existing
pinned Valhalla 3.6.3 local library. One example:

~~~bash
export PKG_CONFIG_PATH=$HOME/.local/opt/valhalla-3.6.3-native/lib/pkgconfig:$PKG_CONFIG_PATH
cmake -S tools/native-f8-edge-scan -B /tmp/roadpilot-f8-geometry-build -DCMAKE_BUILD_TYPE=Release
cmake --build /tmp/roadpilot-f8-geometry-build --target native_f8_directed_endpoints
/tmp/roadpilot-f8-geometry-build/native_f8_directed_endpoints --version
~~~

Then run this *selected-hypothesis* example, from a checkout containing
this phase, without retaining or replacing any installed graph data:

~~~bash
P=$HOME/RoadPilotGraphStudio
python tools/probe_native_f8_terminal_geometry.py \
  --pair "$P/f8-native/italy-nord-est__austria/e6a10d36f-ee7baac93-43d085-958523/pair.json" \
  --from-manifest "$P/builds/italy-nord-est/italy-nord-est-routing-2026.10.13-1-manifest.json" \
  --to-manifest "$P/builds/austria/austria-routing-2026.10.13-1-manifest.json" \
  --native-endpoints-binary /tmp/roadpilot-f8-geometry-build/native_f8_directed_endpoints \
  --direction from-to --mode motorcycle \
  --source-graph-id 546037568058 \
  --receiver-graph-id 546037568058 \
  --receiver-graph-id 548990358074
~~~

These are **three graph-local IDs**: one from Italy and two independently
looked up in Austria. The numeric equality of the Italy source ID and one
Austrian receiver ID is incidental and is never used as a matching rule.

## Measured Italy to Austria observations (2026-11-03)

Selected Italy source terminal: approximately 46.591066, 13.828377.
Both selected Austria directed edges are on OSM way 1123364112.

| Selected Austria directed ID | Distance to Austrian edge end node | Distance to full directed polyline | Local directed tangent cosine |
|---|---:|---:|---:|
| 546037568058 | 0 m | 0 m | +1.0 |
| 548990358074 | 5.605 m | 0 m | -1.0 |

The source's entire final directed edge was within the sampled 20 m and
all four terminal samples lay on selected Austrian geometry within 1 m.

**Interpretation:** A 1 m *end-node* rule would discard the second Austrian
edge even though it contains the source terminal as physical geometry.
The two Austrian directions are distinct: the reverse direction
cannot be silently promoted into an admissible forward handoff.

The reverse Austria to Italy focused auto-mode observation, source Austrian
directed ID 548990358074 against the two corresponding Italian directed IDs,
also returned 4/4 tail samples geometrically co-located and the same two
tangent cosine values (+1.0 and -1.0, assigned to the opposite IDs).
It likewise remains NOT_VERIFIED as a legal crossing.

This is not yet a positively proven graph crossing: the PR #107 example
journey's traced Graph A final directed edge was *different* from the
nominee, and cross-seam legal turns were not independently verified.

## Correctness and provenance limits

- A single selected A terminal is tested against explicit B directed
  IDs supplied by the caller. The receiver IDs are not claimed to be
  exhaustive; a diagnostic batch above 2,048 IDs fails explicitly rather
  than dropping alternatives. This is unrelated to the Android JNI
  512-result window truncation.
- Full A/B geometry is read from immutable, manifest-verified native
  archives. The extractor itself is a separately compiled port and not
  an attested Android F8 JNI execution.
- A local geometrical coincidence is not proof of same directed physical
  connection across independent graph topology. Road-name equality or
  way ID is never a proof criterion or discovery filter.
- Route legality, U-turn restrictions, turn cost, route closure,
  FASTER/SHORTER ranking, JNI parity, nonterminal alternatives,
  multi-hop chains and coverage remain NOT_VERIFIED.
- The output always states productionPublication=BLOCKED. No GUI,
  producer, Android runtime, sidecar, release or graph archive is changed.

## Next gates

Add graph-native, node-preserving directed segment equivalence over all
F8-relevant terminal alternatives, including multiple B segments forming
one A terminal segment. Compare real Valhalla turn costs and actual
travelled direction, then route entire both-graph journeys in both
vehicle modes and travel directions with Android F8 reference parity.
No terminal-only shortcut is permitted until its equivalence to F8 is
demonstrated without loss of alternatives.
