# F8 receiver-directed topology and adjacency — diagnostic evidence

**2026-11-03 — draft PR #106, read-only on the Legion. NOT an approved production crossing algorithm.**

## Purpose and architecture boundary

Continue the terminal-edge hypothesis from draft D-017 without restoring discarded
OSM-first anchor sampling, cross-region connector matrices, normalized-road-key
suppression, or a catalog of all overlapping intermediate edges.

This is a sequence of *evidence collectors*, not a new authority for Android:
1. The retained uncapped native scanner provides per-graph directed edge identities.
2. The native 3.6.3 GraphReader endpoint extractor finds each edge's actual
   end-node GraphId and coordinate in **that same immutable graph**.
3. `tools/audit_native_f8_receiver_topology.py` compares source dead-end
   endpoints against nearby receiver-graph incoming endpoints. It reports
   every source dead-end, all nearby receiver incoming GraphIds (including
   unrelated-way and ambiguous observations), and distinguishes same-OSM-way
   non-dead-end receiver observations **without promoting them to proof**.
4. An optional `--continuations` mode of the native endpoint extractor
   reads each shortlisted receiver incoming edge's **actual end-node adjacency**
   from Valhalla, including the opposing directed edge and *all* outgoing
   directed IDs, their access bits, and whether they are road/shortcut edges.
5. `tools/verify_native_f8_receiver_adjacency.py` strictly cross-checks
   these exact receiver IDs against the provisional correlation evidence.
   It reports access-bit-compatible non-opposing *structural* continuations
   separately for car and motorcycle. It does **not** evaluate turn
   restrictions, routing cost, legal cross-graph path proof or arrival.

The 8 m vicinity in step 3 is a **diagnostic query radius only**, never a
production rejection threshold. Same-way matching labels observations; it
does **not** silently declare other-way candidates invalid. Distinct directed
GraphIds, positions and carriageways remain distinct, including cases sharing
one road name or OSM way. No GraphId values are compared between graphs.

## Real Italy Nord-Est / Austria findings

The native endpoints were read from matching **Valhalla 3.6.3** configs using
the archived graph packs from version `2026.10.13-1`. Both archive SHA-256
values were independently computed and equal their retained routing manifests:

| Source graph | Complete directed endpoints | Source native dead-end flags |
|---|---:|---:|
| Italy Nord-Est | 323,372 / 323,372 | 21,652 |
| Austria | 334,973 / 334,973 | 22,565 |

Directional classification from the native endpoint/receiver audits:

| Measurement | Italy → Austria | Austria → Italy |
|---|---:|---:|
| Source native dead-end observations | 21,652 | 22,565 |
| Provisional same-way receiver non-dead-end observations | 860 | 786 |
| Source edges with multiple provisional receiver incoming edges | 456 | 448 |
| Distinct captured receiver incoming GraphIds | 1,334 | 1,246 |
| Source edges with non-opposing structural car access | **794** | **735** |
| Source edges with non-opposing structural motorcycle access | **796** | **737** |
| Full directional Valhalla route-leg proofs | NOT_RUN | NOT_RUN |
| Exact cross-graph continuity and Android F8 parity | NOT_VERIFIED | NOT_VERIFIED |

The provisional counts differ from the earlier S1 `locate` observations of
871 / 788. This discrepancy remains unresolved; neither count is a proven
complete terminal inventory. Some observations refer only to ordinary
cul-de-sacs replicated in both graphs. This analysis is explicitly restricted
to **source edges flagged deadend**; valid F8 alternatives outside that class
have not been ruled out.

The `motorcycleBit` and `autoBit` indicators come from native Valhalla
`forwardaccess()` flags (1024 and 1). **They do not prove traversability
after turn restrictions, costing, connected legs, or exact arrival.** An
opposing directed edge is removed only from the *forward-continuation
diagnostic count*, not from the evidence itself.

## Reproduction and provenance

All generated inputs and results remain outside Git, under:
`~/RoadPilotGraphStudio/diagnostics/s1/20261103/receiver-directed-v1/`.
The directory includes native endpoint JSONL streams, receiver-directed
observation catalog and summary, exact neighbour-node captures, structural
adjacency summary, and `SHA256SUMS`. Its original source scans/graph packs
are retained at their existing paths and never rewritten.

An example sequence (after separately preparing the pinned full scan pair,
both input GraphId lists and exact GraphReader endpoint captures):

```bash
python tools/audit_native_f8_receiver_topology.py \
  --pair /path/to/existing/f8-native/pair.json \
  --from-scan /path/to/italy-nord-est-native-full.json \
  --to-scan /path/to/austria-native-full.json \
  --scan-summary /path/to/native-full-summary.json \
  --from-native-endpoints /path/to/italy-endpoints.jsonl \
  --to-native-endpoints /path/to/austria-endpoints.jsonl \
  --observations-output /new/scratch/receiver-audit.json

native_f8_directed_endpoints /path/to/italy/valhalla.json \
  /path/to/italy-receiver-incoming-ids.txt --continuations \
  > /new/scratch/italy-receiver-adjacency.jsonl

native_f8_directed_endpoints /path/to/austria/valhalla.json \
  /path/to/austria-receiver-incoming-ids.txt --continuations \
  > /new/scratch/austria-receiver-adjacency.jsonl

python tools/verify_native_f8_receiver_adjacency.py \
  --receiver-audit /new/scratch/receiver-audit.json \
  --italy-native-adjacency /new/scratch/italy-receiver-adjacency.jsonl \
  --austria-native-adjacency /new/scratch/austria-receiver-adjacency.jsonl
```

ID lists are the **complete distinct receiverDirectedGraphIds** in the
provisional `nearbyReceiverIncoming` records for which `sameWay=true` and
`receiverDeadend=false`; sort them numerically and never cap the list.
Receiver adjacency capture validation fails closed on a missing, duplicated,
extra or conflicting receiver GraphId, missing opposing edge or spoofed
vehicle access bit. CLI output is incomplete evidence; native failures may
have partial stdout and require discarding it. Output files are opt-in,
create-only scratch artifacts, never published packages.

## Remaining gates

1. Independently review and approve/supersede D-017 terminology in PR #105.
2. Prove or reject directed *physical continuity across two independent
   graphs*, not merely native adjacency within the receiver graph.
3. Exercise remaining alternatives, including non-dead-end source edges,
   incompatible way IDs, branching, ramps, motorway carriageways and
   multi-hop; show why no required F8 alternatives disappear.
4. Execute full bidirectional motorcycle/car **Valhalla leg proofs** and
   actual FASTER/SHORTER end-to-end journey ranking.
5. Capture genuine matching-version Android JNI F8 with its 512-result
   truncation and Kotlin reduction explicitly accounted for.
6. Design a separately reviewed production handoff artifact and safe
   Android adapter with existing generalized F8 fallback. Never publish
   or install from these diagnostics.

**Status: INCOMPLETE / Android parity NOT_VERIFIED / route proofs NOT_RUN /
production publication BLOCKED.**
