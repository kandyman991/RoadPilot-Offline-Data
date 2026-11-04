# PR #120 follow-up technical review — actual Valhalla hierarchy reachability

2026-11-04. Stacked draft on PR #119. Read-only proof hardening; no production release.

## Finding F8-120-R1 — corrected

The earlier branch-aware journey validator accepted an original-route successor whenever its directed GraphId occurred in any serialized hierarchy-node outgoing inventory. Transition membership and physical-node coordinates were checked, but an actual graph-level transition path from the incoming edge's end node to that outgoing edge's node was not reconstructed. An incomplete or malformed inventory could have manufactured a successful native hierarchy hop.

Fix: compare the root outgoing and hierarchy root outgoing GraphIds, endpoint identities, access masks and road/shortcut attributes; bounded BFS from the actual native terminal over original GraphReader hierarchy transitions; require each serialized node to be reachable with its actual shortest transition depth; store the exact node transition path for each original route hop. Disconnected successors, bad depths and mismatching edge attributes now fail closed. All source branches, ramps, opposing arcs, shortcuts, and mode-dependent alternatives are still retained, not deduplicated.

## Verification on Legion

- Two additional deterministic tests cover disconnected original successor ownership, wrong hierarchy depth, and source/hierarchy edge-attribute mismatch.
- 348/348 entire Python test suite passes using the installed Graph Studio Python environment on PATH.
- Revalidated all eight real original Valhalla route witnesses from the saved 2026-11-04 original-branched-core-to-core-eight-brenner-v3.json with the tightened pure topology validator: 8/8 passes, 5404 exact direct native hops and 52 reachable hierarchy hops.
- The old immutable 21.7 MB source evidence was read-only, not regenerated. Its stored hop records do not acquire the new per-hop path until a future original native recapture.
- No native graph, original binary, Android runtime, region package, historical source or connectivity publisher was changed.

## Explicit remaining gates

Independent review and exact-head GitHub CI for the corrected PR #120; native binary rebuild/attestation not covered by this Python review. Entire 25-km physical-road/direction terminal uniqueness, B-side original multi-edge road geometry, cross-graph turn legality, all alternate routes and Android complete-journey JNI parity remain NOT_VERIFIED. PR #119 and #120 remain stacked open drafts, and production publication stays BLOCKED.
