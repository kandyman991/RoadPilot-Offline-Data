# F8-native ordered proof batches — production pipeline increment

**Status:** first production-facing *proof scheduling* increment, from
Graph Studio's merged `main` at `437afd6`. Not a handoff publisher, final
road-edge inventory, finished offline preprocessing engine or Android build.

The accepted algorithm is still Android's generalized multi-region F8:
independent immutable 25-km-buffered Valhalla regional graphs; receiver-side
directed native GPS proposals; real Graph A→X and X→Graph B Valhalla legs;
actual arrival checks; all potential roads/directions/ramp alternatives;
Android fallback. D-014 and D-015's retired OSM candidate producer,
paired-anchor model, connector matrices, legacy planner and shared GraphIds
remain prohibited.

## Gap this change addresses

The original `probe_native_f8_journey.py` selects up to 32 geographically
ranked and diversified candidates. Repeating that same probe for the same
journey may return the **same** proposals, even though hundreds of thousands
of other GPS proposals exist. That is safe as a *diagnostic sample*, but
cannot incrementally account for the full original native F8 source.

The new `ordered-native-ledger` selection mode is a **production-safe
building block** for a future complete proof scheduler:

1. Read the exact original `discover_native_f8_crossings.py` manifest and
   SHA-256-verified `from-to.jsonl.gz` or `to-from.jsonl.gz`. Graph Studio
   revalidates immutable package, boundary and neighbour-source fingerprints
   against both installed regional archives before running routes.
2. Read the **full** retained compressed GPS proposal stream, fail closed
   on duplicate GraphIds, duplicate proposal IDs, malformed coordinates,
   wrong direction, missing IDs, truncated stream or manifest/count mismatch.
   Every source proposal ID must also equal the deterministic
   SHA-256 identity of its pair fingerprints, direction and receiver
   GraphId, even if the stream and manifest were tampered together.
   Do not filter by OSM way/name, Graph A geometry, B proximity, heading,
   mode access, physical peer or any M6c forensic road-continuity result.
3. Process an explicit **contiguous ordinal page** (at most 32 proposals
   per invocation). Even identical-way physical roads, multiple positions,
   directions, on/offramps and no-peer native edges are eligible.
4. For every selected proposal, attempt the unchanged F8 two-leg Valhalla
   route sequence: origin→receiver GPS in Graph A, normalize to A's
   actual endpoint, then that coordinate→destination in independent B.
   Check both ends and real route costs. **Never stop on first success.**
5. Give the caller the exact `orderedBatchStartOrdinal`,
   `orderedBatchEndExclusive` and `nextOrderedStartOrdinal`; the next
   invocation can advance to the next source page on the *same* original
   fingerprint-bound input ledger.
6. The caller can separately compare both FASTER and SHORTER **within
   each selected page** using both complete Valhalla leg metrics.
   Neither best-of-page choice nor the cursor's reaching the end proves
   global optimum, Android scanner parity, the physical final-road-edge
   rule, or legal cross-graph handoff. `otherBatchCoverage` remains
   `NOT_VERIFIED_NO_CUMULATIVE_PROOF_LEDGER`. No global proof aggregator
   or production connection catalogue is created.
7. If the graph-local B leg's starting GraphId can be reproduced by
   independently replaying the shape via
   `trace_attributes(shape_match=edge_walk)`, call the result
   `TWO_GRAPH_LOCAL_LEGS_B_EDGE_WALK_REPLAY_MATCHED_ONLY`.
   That method **does not return authoritative original route-service
   edge identities** and cannot certify physical edge continuity or
   cross-graph legal transfer. The existing historical ranked-probe
   status is unchanged for compatibility, but every new report and
   candidate row now declares its replay provenance and unverified
   route-edge identity.

A graph-local mode-specific route attempt that fails or snaps elsewhere
is not a global rejection of a road or crossing. All unselected proposals
remain in the original immutable catalog. The ordered mode is explicitly
opt-in; the existing ranked GUI probe remains functional by default.

## Commands

Graph Studio's existing command engine accepts new options, so the same
source can be used from the installed app command path or automation:

~~~bash
P="$HOME/RoadPilotGraphStudio"
python tools/graph_studio_f8_workspace.py probe \
  --workspace "$P" \
  --from-manifest "$P/builds/italy-nord-est/italy-nord-est-routing-2026.10.13-1-manifest.json" \
  --to-manifest "$P/builds/austria/austria-routing-2026.10.13-1-manifest.json" \
  --direction from-to --mode motorcycle \
  --start-lat 46.501885 --start-lng 13.592668 \
  --end-lat 46.592234 --end-lng 13.846448 \
  --probe-selection ordered-native-ledger \
  --start-ordinal 218029 --max-probes 2
~~~

The engine writes a **new, exclusive, atomic, uniquely timestamped**
JSON receipt in the same fingerprint-bound `journey-probes/` directory
used by the existing F8 command. No previous proof or source catalogue
is overwritten. The direct CLI
`tools/probe_native_f8_journey.py` also accepts
`--selection ordered-native-ledger --start-ordinal N --max-probes M`
with a caller-supplied output file that refuses overwrite.

To continue sequential work, use `nextOrderedStartOrdinal` from the
previous receipt **only with the same pair graph/boundary fingerprints,
same mode, direction, start and destination**. Other modes/directions
require independent receipts. The stream is read/validated in full
before any selected routes run. Positive or failed routes do not
change the next cursor.

## Exact real-graph evidence (Legion, 2026-11-04)

Unchanged Valhalla 3.6.3 Italy Nord-Est and Austria
`2026.10.13-1` graph archives and exact neighbour-boundary fingerprints.

| Direction | Mode | Original native ledger size | Ordinal page | Replay matches |
| --- | --- | ---: | --- | ---: |
| Italy→Austria | Car | 334,973 | [218029, 218031) | 1/2 |
| Italy→Austria | Motorcycle | 334,973 | [218029, 218031) | 1/2 |
| Austria→Italy | Car | 323,372 | [180725, 180727) | 1/2 |
| Austria→Italy | Motorcycle | 323,372 | [180725, 180727) | 1/2 |

All four rows were computed with fresh two-leg Valhalla route requests.
Each has one matching B-first **shape replay** and one unproven selected
candidate. All four retain incomplete source coverage and `BLOCKED`
production publication. The original receiver ledgers remain untouched.

Raw fingerprint-bound JSON receipts, `SHA256SUMS` and a summary are
retained **outside Git** at:

`~/RoadPilotGraphStudio/diagnostics/f8-production/20261104/ordered-batch-reviewed-v2/`

Synthetic tests also cover full contiguous coverage across repeated
batches, same-way/no-peer directed-edge preservation, later faster
route candidates, both travel directions, duplicate/stale input,
forged receiver ID after rehash, invalid cursor and stream truncation.
Workspace regressions verify exact cursor forwarding and ensure
replay-only receipts never become validated map-handoff buttons. The architecture-contract CI
runs these regressions on the exact PR head.

## What remains

This is **not** an instruction to route hundreds of thousands of
redundant points to create a new connector matrix. The complete native
GPS source inventory is retained for F8 correctness and equivalence;
the next production increment must prove the owner's **one final
retained edge per real road/direction inside the 25-km overlap**
requirement and establish sound, non-destructive proof prioritization,
rather than replacing F8 candidate discovery with unproven OSM-way
or proximity filters.

Original Android JNI scanner parity, genuine route-edge identity,
source-road final-edge lineage, completeness/optimality of the
connection inventory, multi-hop road legality, safe package schema
and Android #512 ingestion remain **NOT_VERIFIED**. No merge, release or
production publication is authorized by this incremental scheduler.
