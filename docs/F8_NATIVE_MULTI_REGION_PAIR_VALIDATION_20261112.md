# Graph Studio D-017: native A → exact X → B generalization check

**Date:** 2026-11-12. **Status:** local real-graph validation, source changes pending PR review. **Architecture:** retains the original A final-directed-GraphId → its native terminal GPS X → the original B matching directed physical-road geometry at X. Preserves distinct branches, Car/Motorcycle permissions and 25-km independent graph buffers; B outgoing-turn availability is not an acceptance condition for B road identity. No graph rebuilding, legacy OSM road discovery, arbitrary second GPS point, whole-graph native scanner, runtime Android change or publication.

## Previously observed gap and scoped correction

Previous source-root selection rightly included only the original A tiles at the shared 25-km cutoff plus the immediate neighbor ring. On Italy Centro ↔ Italy Sud, however, that subset did **not** cover every original A tile whose bounds intersected the eligible B-outside-A terminal endpoint area. The existing correct fail-closed check stopped the attempted full native catalog:

- Italy Centro → Italy Sud: original selected source cutoff **52 tiles**, missing **28** original A indexed tiles covering the eligible B-outside-A endpoint domain.
- Italy Sud → Italy Centro: original selected cutoff **67 tiles**, missing **18** indexed endpoint tiles. The existing Valhalla `GetOpposingEdgeId` coverage check then found **one additional exact original A incoming-edge owning tile**, outside the expanded selection.

The **same** native Graph Studio source/receiving matcher now:

1. Selects only the additional original **SHA-256-indexed** source A tiles intersecting the B-outside-A endpoint domain, keeping the original source-cut root scope intact. Rejects a request equivalent to an entire original graph scan.
2. Uses native Valhalla 3.6.3 reader **protocol `roadpilot.f8-native-source-11`**. It exposes distinct original incoming-edge owning **tile** IDs from the already performed `GetOpposingEdgeId` checks at eligible terminal nodes. At most one bounded retry reads those exact indexed owner tiles. If any other owner remains missing, reject rather than mark source enumeration complete.
3. Independently rereads each retained original A final GraphId, verifies original native endpoint/mode/adjacency, and applies the existing original B directed-geometry/topology match at **exact X**. No B outgoing-turn gate or physical-road identity inference is introduced.
4. Records source cut tiles, added original indexed tiles, added native incident-owner tile IDs, source scope and `wholeGraphCensusPerformed=false`. Existing outer terminal/long-edge checks remain required. All catalogs remain **`productionPublication=BLOCKED`**.

## Real original Valhalla evidence on Legion

The six directional runs below all completed their original source stage and original A→X→B matching, without modifying source graph archives. All pairs have independently versioned 2026-10-13 regional graph artifacts, Valhalla **3.6.3**, SHA-256-verified source manifest/index/25-km buffer/immutable original graph TAR, and separate A/B original numeric GraphIds.

| Directed pair | Source cutoff tiles | Extra indexed endpoint tiles | Extra native owner tiles | Eligible original A exterior finals | Original B directed matches at exact X | Unmatched B incoming at exact X | Independent strict audit |
|---|---:|---:|---:|---:|---:|---:|---|
| Italy Nord-Est → Austria | 72 | 0 | 0 | **454** | **454** | **0** | PASS, BLOCKED |
| Austria → Italy Nord-Est | 60 | 0 | 0 | **253** | **253** | **0** | PASS, BLOCKED |
| Italy Nord-Est → Italy Nord-Ovest | 75 | 0 | 0 | **716** | **716** | **0** | PASS, BLOCKED |
| Italy Nord-Ovest → Italy Nord-Est | 88 | 0 | 0 | **779** | **779** | **0** | PASS, BLOCKED |
| Italy Centro → Italy Sud | 52 | **28** | 0 | **257** | **256** | **1** | BLOCKED: no B physical-direction proof |
| Italy Sud → Italy Centro | 67 | **18** | **1** | **299** | **298** | **1** | BLOCKED: no B physical-direction proof |

On the reversed Centro/Sud pair, the expanded native owners yielded **350** total graph-local A candidate IDs versus **348** before the correction, including two additional native terminal records; no earlier ID was suppressed. Nonterminal/cut-root physical lineage remains unverified for all six runs.

The two exact original A exceptions are retained without fabricating B road identity:

- `italy-centro → italy-sud`: A GraphId `136975291698`, X = `42.2845844, 13.6598531`; no independently matched B incoming directed edge at X.
- `italy-sud → italy-centro`: A GraphId `15407561506`, X = `41.7707842, 13.0063595`; no independently matched B incoming directed edge at X.

Neither is proof of a physically missing road: mismatched native cut, graph version/way partition, local dead-end topology, or an unresolved physical correspondence remain possible. These exceptions require targeted read-only Graph B investigation before this pair can be claimed complete. **No coordinate-only substitute, name match, inferred continuation or source exclusion is permitted.**

## Independently verified automatic catalogs

The approved existing D-017 audit, preflight and automatic catalog generator, unchanged in their routing/matching choices, successfully produced these two new nonpublishing test artifacts:

- `italy-nord-est__italy-nord-ovest`: **716 A finals / 716 original incoming B directed roads**, `BLOCKED_TEST_ONLY`.
- `italy-nord-ovest__italy-nord-est`: **779 A finals / 779 original incoming B directed roads**, `BLOCKED_TEST_ONLY`.

The previously verified Italy Nord-Est ↔ Austria pair independently regenerated at the same **454 / 253** original terminal final edges and corresponding original B roads, so that source pair does not regress. The strict independent audit succeeded for all four fully matched directed runs, but not for either Centro/Sud run because one original A final per direction lacks a proven corresponding B directed road.

All original directed A/B GraphIds, each native X, graph hashes, source/receiver buffer and graph-index identities, independent proof SHA, vehicle modes, unresolved source-lineage observations and distinct B branch options remain retained. An audit reaching the BLOCKED test-only stage is **not** proof of all physical-road lineages or Android JNI parity.

## Verification and evidence limits

- Real C++ reader built and run with local Valhalla 3.6.3 static development library. Native source `--version` and `--protocol` checked. Two-direction source/receiver runs performed for three independent adjacent regional pairs.
- Focused tests for source selector, native original source protocol, immutable SHA-bound input, independent physical-road/branch audit and malformed/fabricated evidence. Complete Python test run: **502/502 passed** in Graph Studio's Legion Python environment (before final documentation cleanup; repeat at PR exact HEAD).
- Actual diagnostic outputs are **outside Git** at `~/RoadPilotGraphStudio/diagnostics/f8-production/20261112-multiregion-acceptance/`, including `v11-verified/`, six `*-native-receiver-evidence.json.gz` files, SHA-bound `*-connections-BLOCKED.json`, two new `*-preflight-BLOCKED.json`, two `*-auto-catalog-BLOCKED_TEST_ONLY.json`, logs and independent audits. Original source archives and user-managed overrides untouched.
- **NOT VERIFIED:** one true unique final edge per **physical** road/direction globally; complete source-root lineage across all continuation contexts; B matching for the two Centro/Sud exceptions; real RoadPilot normal Android A→X→B journeys for these **new** pairs; multi-hop alternative optimality; Android JNI reader parity on exact packages; owner production sign-off and signed release fingerprint pin. All READY publication remains **BLOCKED**. No production release requested.

**Next gate:** independent review + exact-HEAD CI on this incremental code, then targeted native B discrepancy checks for the two unmatched Centro/Sud GraphIds and physical-road lineage audit. Do **not** mark Graph Studio's native connectivity production-ready simply because synthetic tests, a source candidate list or a B incoming road projection passes.


---

## Subsequent original-native exception closure (12 November 2026)

Both unmatched Italy Centro ↔ Italy Sud B-directed approaches were
**false negatives** from a 1 m minimum directed overlap applied to genuine
shorter compiled original Valhalla final segments. The same matcher with a
strict native-geometry exception and independent disposition correction
now yields 257/257 and 299/299 source finals with corresponding B roads,
preserving **300** distinct incoming B matches in the reverse direction.

All six real region directions were independently rerun/audited and yield
2,758/2,758 matched original directed source finals; six production
preflights and six BLOCKED_TEST_ONLY auto catalogs passed. This does not
establish global semantic physical-road lineage or Android production
acceptance. Full details:
F8_NATIVE_TWO_SUBMETRE_EDGE_EXCEPTIONS_20261112.md.
