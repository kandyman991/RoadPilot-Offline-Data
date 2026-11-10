# PR #127 — D-017 M1: independently reconciled native boundary dispositions

**10 November 2026 · original immutable Valhalla 3.6.3 graphs · PR #127 DRAFT · not a production catalog.** This is a **read-only proof/disposition extension of the existing A → exact X → B matcher**, not another discovery/tracing/classification architecture. The producer's existing `--match-receiver` behavior, source terminal IDs, B legal branches, 25-km pair overlap and 2026.10.13-1 compiled graph archives are unchanged.

## What is independently established

For Italy Nord-Est ↔ Austria, the already selected original 72/60 source pair-cut tiles and their existing indexed pair-endpoint domain contain **707 eligible native original A outer terminal directed GraphIds**. The native source inventory additionally attests **39/39 and 29/29** original tile-index bounds over the endpoint domain and **zero** outside-selected-tile origin owners among 1,063/541 original incoming directed references inspected; this was proven by the existing v10 original Valhalla `GraphReader`, **not** a new scan.

The independent Python verifier `tools/audit_f8_physical_road_evidence.py` now rejects mismatches in the native long-edge origin proof, terminal ID inventory, all source-cut roots/counts, original A source road attributes and permitted modes, **every** original directed B incoming geometry match (including source exceptions), the original B incoming directed GraphIds, every legal B successor and each mode's native costing status. If two different A terminal IDs claim the same native B incoming directed GraphId, it fails rather than silently deduplicating roads.

**Native directed correspondence up to X:** All **707/707** eligible source A terminal identities have exact original X and a corresponding original **directed B incoming road** whose directed approach geometry overlaps A in forward travel direction at X, with matching original layer/bridge/tunnel native structure. There are **707 distinct B incoming GraphIds for 707 A terminal GraphIds** on these two real graph pairs; no duplicate incoming identity was assigned to two A sources. Maximum native B X projection gap in the underlying full evidence is **0.068 m** (Italy→Austria) / **0.067 m** (reverse). This **proves native directed physical approach correspondence up to X**, not semantic same-road identity beyond X.

## Per-original-source final exact disposition

| Original source A terminal status (motorized checked context) | Italy NE → Austria | Austria → Italy NE | Both |
|---|---:|---:|---:|
| Original B native legal outgoing branch(es), without other native unknowns | 244 | 155 | **399** |
| Original B legal outgoing branch(es), with further conditional/hierarchy unknowns | 16 | 5 | **21** |
| No original B statically permitted outgoing turn, no recorded unknown | 148 | 71 | **219** |
| No original B statically permitted outgoing turn, only conditional/path/hierarchy unknowns | 46 | 22 | **68** |
| **Independently audited eligible A final directed GraphIds** | **454** | **253** | **707** |
| Distinct original B statically legal outgoing options, *all retained* | 401 | 245 | **646** |

The **219** are **not fake physical-road connections**, and they are **not globally proven permanent cul-de-sacs**. They have a matching physical directed original B incoming approach but no confirmed natively legal B outgoing successor **in the checked default costing context**. Their precise original A GraphId, X, native B predecessor(s), source/receiver attributes and explicit `NO_ORIGINAL_B_NATIVE_ALLOWED_FORWARD_CONTINUATION` reason are retained.

The **68** have their original A physical approach at X matched but **only unresolved original B costing alternatives**. These are **not proven disconnections**. Their original native B predecessor/receiver directed GraphIds and exact car/motorcycle statuses are retained as explicit exceptions; neither car nor motorcycle is silently approved.

Among the **21** otherwise matched source finals, **28 further B status records** remain conditionally unresolved; 111 such records belong to unmatched sources: **139 conditional records total**, some overlapping an already legal branch for another mode. In particular **8 native B directed options are already ALLOWED for motorcycle while car is path/time-context UNKNOWN**. Those motorcycle-original GraphIds already remain among the 646 legal B options, and the original conditional car status remains explicit. The audit now fails closed if either the motorcycle allowed bit is lost or car is falsely promoted.

The 646 native legal outgoing B edges are retained with the actual directed GraphId, native predecessor IDs, exact X and mode-specific native permissions. **451** have identical native predecessor/branch class/use/structure; **195** differ in at least one. Identical attributes are **not sufficient proof** of semantic road identity. Changed class/use/structure must **not discard genuine ramps, turns, junctions or vehicle-specific branches**.

## The 285 source-cut roots are not 285 missing physical roads

The existing source-root evidence accounts independently for **1,242** original pair-cut outward/ambiguous roots: Italy→Austria **820 = 322** associated with receiver-positive native terminal candidates + **307** associated with a native terminal lacking a positive B successor + **191** without a terminal association in the deliberately bounded two-hop root check. Reverse **422 = 196 + 132 + 94**. Hence **191 + 94 = 285** roots have no proven *short root→terminal lineage*.

These are observations at the A-cut, **not distinct proven physical roads**, nor new native terminal GraphIds. The complete independent A outer terminal inventory and its long-edge owner-tile attestation are different evidence, and exhaustively cover eligible terminals **within this pair/B-covered endpoint domain** whether or not a particular older source root was traced through several predecessors. The verifier compares the **complete 1,242 native root IDs/statuses and existing references**, detects altered/missing roots, and never equates an unlinked root to an invented missing cross-region connection. Full origin-to-terminal *semantic road lineage* remains unverified.

## Exact reproducibility and provenance

The existing audit now optionally writes a non-overwriting, deterministic, **nonpublishing** JSON file via `--disposition-output`, schema `roadpilot.f8-pr127-bounded-physical-road-dispositions` version 1. It contains **all 707 source final GraphIds with one disposition each**, their original A/B incoming identities, X, original B legal branches, conditional status lists, plus **all 1,242 source-root observations** and bounded statuses. The tool rehashes BOTH original compiled immutable TAR files before writing; a mismatch fails closed. It does not rerun source discovery, walk extra edges, create another handoff X/Y, match road names/OSM IDs or invoke Valhalla TripLeg proofs.

Local nonpublished evidence:

- `~/RoadPilotGraphStudio/diagnostics/f8-production/20261109/italy-ne-to-austria-M1-final-dispositions-20261110.json`
- `~/RoadPilotGraphStudio/diagnostics/f8-production/20261109/austria-to-italy-ne-M1-final-dispositions-20261110.json`
- Paired independent audit summary: `*-physical-road-dispositions-audit-20261110.json`

Original archive SHA-256: Italy NE `e6a10d36f8622ac0e47dc3d17a8295f60b144f9a2ad478e1b5f6ef2dbea75953`; Austria `ee7baac93b639d0c2fefab8f90540d26d03fd28a283c73bff516a1d8bdc2bc7b`. The check also compares original indexed/buffer/reciprocal boundary fingerprints.

Example:

```sh
python3 tools/audit_f8_physical_road_evidence.py \
  --catalog /path/to/italy-ne-to-austria-connection-candidates-v2.json \
  --evidence /path/to/italy-ne-to-austria-catalog-evidence-v2.json.gz \
  --from-archive /path/to/italy-nord-est-routing-2026.10.13-1.tar \
  --to-archive /path/to/austria-routing-2026.10.13-1.tar \
  --output /path/to/nonpublishing-audit.json \
  --disposition-output /path/to/new-nonpublishing-dispositions.json
```

## Acceptance boundary — do not confuse two different proofs

**PASS in the bounded original pair domain:** original A directed final terminal inventory identity, long-edge source-origin owner coverage, one-to-one original B directed incoming physical approach matching at exact X, preservation of every native legal B outgoing branch and motorized access mask, explicit evidence-backed per-source exceptions and source-cut root disposition. Proven by read-only inspection of existing original native Valhalla evidence and independently verified actual archive SHA, plus real RoadPilot PR #543 test-only installed-graph native A→X→B Android journeys.

**STILL NOT VERIFIED:** semantic one-per-*physical-road lineage* over the source cut (distinct from native terminal inventory); unknown native conditional B legality for specific path/time/hierarchy state; whether each B outgoing branch is the *same* road after the junction (a real turn/ramps is not supposed to be silently rejected); **production-ready catalog and ordinary user-visible RoadPilot UI acceptance**, and independent external reviewer signoff. These require actual separate evidence, not ticking the two unchecked PR architectural-invariant boxes to make CI green.

**No premature acceptance or merge:** `physicalRoadIdentityAcceptance=NOT_VERIFIED`, `productionPublication=BLOCKED`. The existing PR architecture policy gate's two physical-road completeness checkboxes remain unchecked because this work demonstrates the **precise bounded scope and residual ambiguity**, not global semantic road identity. The report is a reproducible **answer for every original A GraphId**, *not* a READY catalog or second architecture. PR #127 remains DRAFT/UNMERGED, and owner approval is required before merging.
