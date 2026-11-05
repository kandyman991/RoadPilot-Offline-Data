# F8 auto-bilateral after regional graph builds — first integration increment

2026-11-05 · Draft Graph Studio PR #125 · **not a production catalog generator yet**

## Architectural contract

After a region's **real** OSM + Valhalla graph archive has been built,
validated and packaged, Graph Studio now automatically runs a separate
**F8 original-graph bilateral stage**. It discovers **compatible retained
graph pairs** by the original regions' *reciprocal* boundary identifiers
and SHA-256 graph/boundary fingerprints, never by approximate geographic
proximity, road names, OSM way IDs, or successful-first-route selection.

The source-final algorithm remains the one we agreed:
**one final original source directed edge per legitimate physical road and
direction**, independently match **all distinct physical forward receiving
directed edges** and prove **original Valhalla A-LAST/B-FIRST TripLeg IDs**.
Never suppress a genuine branch. Auto and motorcycle are attributes, not
duplicate source-edge records.

## Implemented in this increment

- The Tauri build queue calls `tools/run_f8_bilateral_after_build.py`
  **after** all requested regional packages are built and validated, including
  optional visual-pack processing. This is the same command-line entry point
  available to an AI agent and headless scripted jobs; no separate UI-only
  logic. F8 progress and summary appear in the existing build log.
- Original graph packages and their indexes must exist and have matching
  retained SHA-256 checksums. Every compatible pair must be **mutually**
  declared by the two region graph indexes. One-sided nominal/buffer
  adjacency is an explicit error, not an empty crossing inventory.
- It retains every distinct original graph pair/region version fingerprint,
  not only one currently installed peer or the first successful match.
  Graph/boundary identities deterministically identify immutable per-pair
  workspaces.
- An existing **complete-source-ledger-shaped** original F8 evidence file
  can be selected only if both original graph SHA-256 values, both original
  boundary SHA-256 values (via the original retained pair-manifest SHA)
  and the native source/receiver topology and directed first-edge evidence
  match. Competing proof ledgers must be monotonic supersets of all previous
  **directed source/receiver/mode** options; otherwise selection fails.
- Only independently checked source-final/receiver-first options from
  that exact graph's **retained original source ledger** enter an
  **immutable, verified-only, test-only** cache. It is compact JSON with a
  strict 3 MB maximum for the existing Android native parser. Previously
  retained noncompact diagnostic evidence is never overwritten. The unresolved original
  candidate ledger remains in Graph Studio, with its SHA-256 linked to the
  derived test cache. The native original A-LAST proofs from previous
  ledgers are **not reexecuted** in this integration stage.
- If a newly built graph pair has **no original source-final proof ledger**,
  it automatically receives the explicit immutable status
  `PENDING_ORIGINAL_SOURCE_FINAL_EDGE_DISCOVERY` instead. There is no old
  native GPS proposal generation, no portal matrix, and no substituted
  guessed edge matches. There is never an Android production sidecar release
  from this stage.

Outputs appear under:
`~/RoadPilotGraphStudio/f8-production/auto-pairs/<pairId>/<graph-and-boundary-identity>/`.

### Executable reproduction on the Legion

```bash
cd ~/graphstudio-f8-final-edge-matching
~/.cache/app.roadpilot.graphstudio/python-env/bin/python \
    tools/run_f8_bilateral_after_build.py \
    --workspace ~/RoadPilotGraphStudio \
    --built-region italy-nord-est \
    --built-region austria \
    --package-version 2026.10.13-1
```

### Real retained Italy/Austria graph replay

Replayed against original 2026-10-13 regional Valhalla archives and
original immutable Graph Studio evidence (no graph rebuild necessary).
The automatic stage found **four compatible original graph pairs**:

| Original graph pair | Automatic stage | Native proof result |
|---|---|---|
| Italy Nord-Est ↔ Austria | `PARTIAL_ORIGINAL_DIRECTED_ROAD_CONNECTIONS_VERIFIED_ONLY` | **247 source-final original directed GraphIds; 278 distinct verified receiving options** |
| Italy Nord-Est ↔ Italy Centro | `PENDING_ORIGINAL_SOURCE_FINAL_EDGE_DISCOVERY` | No SHA-compatible native source/receiver proof yet |
| Italy Nord-Ovest ↔ Austria | `PENDING_ORIGINAL_SOURCE_FINAL_EDGE_DISCOVERY` | No SHA-compatible native source/receiver proof yet |
| Italy Nord-Ovest ↔ Italy Nord-Est | `PENDING_ORIGINAL_SOURCE_FINAL_EDGE_DISCOVERY` | No SHA-compatible native source/receiver proof yet |

The verified Italy/Austria partial catalog is **the previously proven**
original A-LAST/B-FIRST connection set, automatically recognized and
frozen for this exact graph pair, **not new discovery performed by this
hook**. Its unresolved candidate count remains retained and publication
is BLOCKED. All other pairs are correctly classified as pending, not as
zero legitimate crossings.

Reproducible log:
`~/RoadPilotGraphStudio/diagnostics/f8-production/20261105/f8-buildqueue-bilateral-autostage-real-graphs-v3-compact.log`.
The generated compact verified-only Android test cache is **2,759,964 bytes**
with SHA-256 `c2225f447c0c3de093eed66ed1d70805efa01dcafb612f546053ad2b57ed6e17`,
byte-identical to the previously Android-emulator-accepted `v17` test cache.
This reproduction did **not** rerun unrestricted Android F8 navigation.

### CI and regression scope

`tests/test_f8_auto_bilateral_after_build.py` checks:
reciprocal buffer/graph fingerprints, one-sided boundary rejection,
no unrelated pairs, preserving distinct original peer graph versions,
exact original graph archive SHA-256, original retained pair SHA,
verified-only cache with every distinct receiver branch, direct
native first-edge mismatch rejection, duplicate branch rejection,
idempotent reruns, and the impossibility of marking an incomplete
catalog production-ready. Included in the existing F8 architecture CI.

No legacy source code is deleted in this increment. The old GPS
proposal workflow is **not called** from normal graph builds.

## Explicit remaining production work

The major production work is **not** finished merely because the hook
executes. To make a brand-new pair of graph builds independently discover
*every* relevant source-final edge, the build-stage producer still needs
an actual exhaustive **original SOURCE graph** directed road/direction
census within the bilateral 25-km cut, source last-edge certification,
all-original-receiver geometry correlation, actual native Valhalla A-LAST /
B-FIRST route-edge proof, and explicit global completeness gate. This must
operate on **new SHA-pinned graph archives**, not reuse the October evidence
for a different graph. Mode-dependent legitimate branches must remain
visible throughout; unrelated intersections must not become work items.

After that: complete real RoadPilot A→X→B journeys (car/motorcycle, both
directions), unrestricted Android F8 runtime and device performance.
**Production publication is BLOCKED**, `sourceDiscoveryComplete=false`,
and both PRs remain draft/unmerged until independent review, exact-head
CI and owner acceptance. The already-installed Legion AppImage at
`e0586fb` predates this new hook; this increment requires a new
installer build before it appears inside the installed application.
