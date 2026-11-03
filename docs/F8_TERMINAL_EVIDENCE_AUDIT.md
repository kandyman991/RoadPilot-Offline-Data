# Native F8 terminal evidence audit — diagnostic recovery gate

Status: **IMPLEMENTED DIAGNOSTIC ONLY**. This is not a handoff generator,
a release approval, or a change to the Graph Studio UI. It is an intentionally
restricted recovery step that prevents terminal-edge assumptions from silently
becoming claimed cross-graph connectivity.

## Why this exists

Graph Studio's currently retained native scanner can enumerate hundreds of
thousands of independently identified Valhalla directed edges. The GUI's
"Discover" diagnostic emits one GPS proposal per receiver edge and its
"Journey Validation" operation probes at most 16 selected candidates. The
regional build queue deliberately does **not** compile production F8 sidecars.

D-017 proposes selecting the terminal directed connection of each genuinely
continuous road path, rather than every buffer-interior edge. The key risk is
that a node which appears to dead-end in one graph can be a normal cul-de-sac,
and proximity to an edge in the neighbour graph is NOT proof of a legal,
exact directed handoff.

## Audit command

`tools/audit_native_f8_terminal_evidence.py` consumes retained read-only
Graph Studio native scans, their pair manifest and scan summary, and the S1
experimental Valhalla `locate` observations from outside this repository.

It does **not** import the retired OSM crossing producer, a connector matrix,
or the legacy candidate-pair schema. It never modifies a graph or saved
evidence. Default output is one structured JSON report on stdout.

Example using the retained Italy Nord-Est/Austria S1 files:

```bash
python tools/audit_native_f8_terminal_evidence.py \
  --pair /path/to/f8-native/pair.json \
  --from-scan /path/to/italy-nord-est-native-full.json \
  --to-scan /path/to/austria-native-full.json \
  --scan-summary /path/to/native-full-summary.json \
  --from-ends /path/to/s1/m3/ends-italy.jsonl \
  --to-ends /path/to/s1/m3/ends-austria.jsonl \
  --from-neighbour-probes /path/to/s1/m3/terminals2-italy.jsonl \
  --to-neighbour-probes /path/to/s1/m3/terminals2-austria.jsonl
```

## Exact native graph-local endpoint extraction (new)

`tools/native-f8-edge-scan/native_f8_directed_endpoints.cpp` compiles alongside
(the existing scanner is unchanged) with the pinned native Valhalla 3.6.3 SDK:

```bash
cmake -S tools/native-f8-edge-scan -B /tmp/native-f8-endpoints-build
cmake --build /tmp/native-f8-endpoints-build --target native_f8_directed_endpoints
/tmp/native-f8-endpoints-build/native_f8_directed_endpoints --version
/tmp/native-f8-endpoints-build/native_f8_directed_endpoints \
  /path/to/exact/pinned/valhalla.json /path/to/one-directed-graph-id-per-line.txt \
  > /tmp/native-f8-directed-endpoints.jsonl
```

The new command fetches each source directed edge by its GraphId from its OWN
archive, then fetches the real end-node GraphId/coordinates and edge attributes.
It reports errors on missing IDs, duplicate input or missing end nodes, and
requires callers to **discard all partial stdout** on a nonzero exit code.
It reads but does not modify `.gph` files; it does not compare source/receiver
GraphIds or independently attest an archive hash.

For the auditor, pass both `--from-exact-endpoints` and
`--to-exact-endpoints` instead of the older `--from-ends`/`--to-ends`
S1 files. The neighbour-side probes remain provisional S1 8 m `locate`
evidence in either mode.

**Retained real-graph result (Legion, Valhalla 3.6.3):** exact source endpoints
were recovered for **323,372/323,372** Italy edges and **334,973/334,973**
Austria edges. The native `deadend` flag was set on **21,652** and **22,565**
edges respectively. S1 had missed 8,160 and 8,371 source endpoints via
`locate`; using native endpoints reduces unresolved source endpoints to zero.
However, the pre-existing neighbour S1 observations cover only the older
21,631 / 22,546 matched local dead ends: **21 Italy and 19 Austria new
native dead-end observations remain unprobed**. The same 871 / 788 old
provisional continuation counts are unchanged and are NOT route proof.

Optional `--include-candidates` returns each distinct *source graph-local*
directed edge and the observed endpoint; the receiving GraphId remains
`null`. The key is never just a road name, reference or OSM way ID.

## Observed S1 replay, 2026-11-03

Source scans: Italy 323,372 edges; Austria 334,973 edges. Endpoints matched
by S1 `locate` to their source GraphId for 315,212 and 326,602 edges.
The audit reports:

| Evidence | Italy source | Austria source |
|---|---:|---:|
| Candidate graph-clip termini (approximate 8 m continuation) | 871 | 788 |
| Unmatched source edge endpoints | **8,160** | **8,371** |
| Own-graph dead-end observations | 21,631 | 22,546 |
| Dead-end neighbour probes missing | 0 | 0 |
| Neighbour also stops | 20,365 | 20,365 |
| Neighbour edge not found within tolerance | 395 | 1,393 |

This is a retrospective audit of Claude's S1 *experimental* data, not an
independent native-GraphReader terminal proof. Scan summary provenance is
`SUMMARY_DECLARED_ONLY_COUNTS_CHECKED`: retained scan bytes were not
cryptographically bound by the historical side-scan summary.
The endpoint and neighbour-locate scratch logs themselves also lack an
independent cryptographic graph binding (`UNBOUND_S1_SCRATCH_LOGS`).
The new exact native endpoint stream still requires independent archive-hash
attestation and a fully graph-native receiving-side directed-edge match.

## Required correctness gates (NOT yet passed)

1. Recover and independently account for unmatched edge endpoints, with
   exact graph identities and source window coverage.
2. Extract genuine directed terminal topology from the pinned immutable
   Valhalla graphs, not an 8 m proximity-only `locate` approximation.
3. Distinguish ordinary cul-de-sacs from graph clips and preserve separate
   branches, motorway carriageways, ramps, access modes, opposite directions
   and multi-hop routes. Do not infer equivalent GraphIds across graphs.
4. Independently route-proof the exact receiving connection with Valhalla
   in both directions and for motorcycle/car. Preserve INCONCLUSIVE results.
5. Compare against real Android JNI F8 captures on identical graph
   fingerprints, accounting for the JNI 512 cap and Kotlin road-key reduction.
6. Validate full start-to-destination FASTER/SHORTER routes, not only a
   successful handoff. Keep F8 as the fallback.

Every report remains `INCOMPLETE`, `NOT_VERIFIED`, proof `NOT_RUN` and
publication `BLOCKED`, even when all observed candidate rows are consumed.

See architecture contract A2/B1/B2/B4, engineering decision D-017 (draft),
Graph Studio issues #73/#82, and Android issue #512.
