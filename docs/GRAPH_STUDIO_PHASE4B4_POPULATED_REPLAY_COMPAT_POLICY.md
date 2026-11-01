# Graph Studio P4-B4 — populated historical replay and legacy CLI compatibility policy

**Audit:** 2026-11-01. **Related:** [P4-B3 inventory](GRAPH_STUDIO_PHASE4B3_HISTORICAL_POPULATED_FIXTURES_CONSUMERS.md), [P4-B2 evidence](GRAPH_STUDIO_PHASE4B_REAL_FIXTURE_EXTERNAL_CONSUMER_EVIDENCE.md), [issue #89](https://github.com/kandyman991/RoadPilot-Offline-Data/issues/89).

**Decision:** RETAIN all 11 legacy validators and their installed CLI entry points. The tests below are migration/compatibility evidence, **not** removal approval, native-F8 graph-edge proof, or an Android release gate.

## 1. Populated road-record compatibility — historically reconstructed, not recovered production

Historical pre-#84 revision **`661a23a^`** contains two executable CI stages in `.github/workflows/validate.yml`:

1. `Smoke-test connectivity pair manifest` creates synthetic `region-a` and `region-b` graph manifests and builds a stable physical pair manifest.
2. `Smoke-test stable frontier road inventory` creates two adjacent synthetic square polygons, a tiny synthetic OSM document with three ways, and runs the then-current `build_frontier_road_inventory.py`, followed by `validate_frontier_road_inventory.py`. CI asserted road ways **100** (`CROSSING`, road `ref=A1`) and **102** (`FRONTIER_OVERLAP`, positive overlap length). Way 101 remains outside the frontier results.

These stages were independently replayed on the owner's connected Legion in an **auto-removed `/tmp` directory**, extracting only historical `tools/` using `git archive 661a23a^`. Existing local `osmium`, `shapely`, `pyproj` and Python were used; no live Graph Studio workspace or installed binaries were modified. Both historical CI stages exited **0**.

**Reconstructed v1 output:**
- `schema = roadpilot.frontier-road-inventory`, `version = 1`, generator `roadpilot-osm-frontier-inventory`.
- **Two populated `roads` records**: `CROSSING` and `FRONTIER_OVERLAP`. `discovery.f8GraphEdgeParity = NOT_VERIFIED`, `scope = NOMINAL_ONLY`.
- Reconstructed raw artifact SHA-256 **`65686c0af5d5536650ef0599ee9708b0e47862c0a2350efb238a640c73a6d0ab`**. This is a newly generated artifact, *not* a saved production/historical CI artifact.
- Three-way **positive validation** of this new two-row artifact passed: the historical `tools/validate_frontier_road_inventory.py`, the current repo source `tools/validate_frontier_road_inventory.py`, and the actually installed Debian script at `/usr/lib/RoadPilot Graph Studio/pipeline/tools/validate_frontier_road_inventory.py`. All three returned exit code **0**, **identical stdout SHA-256** `25ea77691c632dc8fd5a056fe9102cca49b4b1ca10f6aa8c0b01c64129d0bf2a`, empty stderr. All three script SHA-256 values are the same: `ec9aaf917eaae7cdd704c006a05efa47a632dd9522b76e453a7fd06e2ce6110c`.

### Durable, nonprivate, positive fixture

`tests/fixtures/historical-frontier-v1-populated-synthetic.json` is the **semantically identical** canonicalized JSON snapshot of the reproduced CI artifact. Its canonicalized committed-file SHA-256 is **`14ea1c5422f34dfcb92f67309ce04fae9416419d59420ca59fe9fd12930c2eee`**; the different raw-replay SHA above reflects JSON reserialization/ordering, not altered data. The regression suite pins this canonical file hash. A second complete historical replay reconstructed the two roads and confirmed **JSON structural equality** against the committed test fixture. It contains exclusively historical CI's invented coordinates/way IDs (`region-a`, `region-b`, tiny synthetic OSM), **no original user data** or actual operating-road observations.

`tests/test_historical_frontier_populated.py` adds:
- Accepted **nonempty** v1 frontier inventory (two roads) via the current CLI, with no writes to the copied artifact or temporary directory.
- Rejection of invalid latitude / crossing-kind mutations, checking the invalid input is not rewritten.
- Explicit synthetic provenance / `NOMINAL_ONLY` / `NOT_VERIFIED` guard.

**Coverage boundary:** populated schema and validator compatibility is now PROVEN for this specific **synthetic historical CI case**, not for genuine operational road records, every v1 payload variant, 10 other legacy validator schema families, graph-edge parity, or Android route ingestion. The real saved operational inventory from P4-B2 still has `roads: []` and remains unchanged.

## 2. External, historical and manually invoked CLI consumers

| Surface | Evidence | Confidence / interpretation |
| --- | --- | --- |
| Historical GitHub Actions, `661a23a^` pre-#84 | `.github/workflows/validate.yml` directly calls **all 11** validators; some steps generated populated synthetic JSON in ephemeral runner locations | **CONFIRMED past automation callers** |
| Historical `tools/refresh_graph_connectivity.py` | Direct/stage-dispatched **seven** legacy validator tools, including frontier, candidates, proofs and runtime connectivity | **CONFIRMED past orchestrator caller** |
| Current tracked Graph Studio Rust/JS/Python and GitHub workflows | No direct literal names of these 11 scripts as runtime call sites. Dynamic Rust R2 dispatcher selects specific R2 tools, not legacy validators | Current direct calls **NOT_FOUND in scoped tracked source** |
| Owner's current indexed GitHub default-branch repositories | Owner-scoped search of each of the **11 full validator filenames** returned hits only under `RoadPilot-Offline-Data`, not a second indexed repo | No second indexed owner repo found; **not global absence** |
| Known Legion Bash history, accessible cron/systemd/user-bin, actions runners, SmartRide-Next and F8/LegionBridge worktrees | Earlier P4-B2 bounded exact script-name scans returned no current caller references | Current direct callers **NOT_FOUND in scanned paths**, dynamic/manual/old records unverified |
| Installed .deb/AppImage | All 11 legacy validators remain shipped; installed Debian validator successfully executed the reconstructed **two-road** fixture | **CONFIRMED public filesystem CLI surfaces**, even without runtime UI use |
| GitHub Actions archive | Repository artifact index returned **0** retained artifacts; no saved old populated original inputs available through that index | CI provenance exists, original archived bytes **NOT_RECOVERED** |
| Real stored operational artifacts | Only a saved v1 `frontier-road-inventory` document with **zero** roads found in the checked Graph Studio workspace; other 10 real positive fixture families missing | Genuine populated production compatibility **NOT_VERIFIED** |

**Manual-use uncertainty cannot be converted to a negative result.** No inferred “zero external consumers” may be claimed from current code search. Explicit old-to-new interface compatibility is prudent until usage evidence and owner policy say otherwise. Never silently alter the 11 CLI names, required flags, exit codes, stdout/stderr semantics, or JSON v1 acceptance.

## 3. Proposed safe compatibility/deprecation policy — staged, reversible, with owner gates

### Contract baseline — enforce now

- Treat the **11 shipped Python CLI entry points** as public compatibility surfaces for existing installs and tooling: preserve filenames, `--inventory` for frontier validator, `--artifact` for ten others, `--help` behavior, positive/negative exit status and stdout/stderr contract. Keep v1 JSON accept/reject semantics for fixtures; do not modify F8 discovery.
- Maintain legacy validators in packages and source without any “deprecated” stderr output or forced telemetry. Emitting warnings to stderr would violate existing exact-output parity and could break automated consumers.
- Keep the positive synthetic two-road regression test, original empty-road real-file parity evidence, 11/11 `--help` and invalid-schema parity, historic Git commit references and checksummed metadata. Explicitly mark that only **one of eleven** validator families has a populated historical replay.
- Developer-only auditing tools remain outside app resources; never scan or upload owner artifact content without explicit approval. No hidden background tracking or network collection.

### Gate G1 — identify consumers and meaningful positive fixtures

- Document potential users: current GUI command paths, Android compatibility, CI, systemd/cron, external scripts, owner/manual usage, supported older installed releases, maintenance partners.
- Ask responsible operators whether any older `validate_*.py` entry point is invoked outside tracked source; request *command name/flag and version*, not logs/secrets. Absence of replies is `UNKNOWN`, **not** an attestation of no use.
- Seek **consented** copies of historical saved nonempty road/connector/crossing artifacts, if they exist in owner backups/old installed workspaces. Run only checksum-protected **temporary-copy** validation and do not commit private/real data.
- For remaining 10 formats, selectively reconstruct exact committed historical CI synthetic input generation in isolated environments when feasible and label it **RECONSTRUCTED**, not genuine production data.

### Gate G2 — compatibility bridge (separate owner-approved PR)

Only if owner decides to retire the *internal implementation*, propose a wrapper with exactly the same CLI filename/flags, exit and output behavior calling the supported validator engine. Evaluate:
- Old and new wrappers on positive and negative fixtures; source and packaged .deb/AppImage parity, including intentionally invalid inputs and file-integrity checks.
- No shell injection, unexpected writes, network access or data egress.
- Same help contract; no changed default output format. No warning sent on stderr by default.
- Exact-head CI, independent architecture/security/data-integrity review, isolated install/uninstall acceptance and rollback.

A same-name wrapper can preserve external compatibility while reducing the number of maintained implementations, but is **not** automatically safe and is not part of this PR.

### Gate G3 — explicit versioned deprecation (owner policy decision)

Only after G1 and G2, owner may approve an **opt-in**, documented deprecation window. Recommended minimum: **two published application versions / release cycles** in which legacy CLI paths remain executable, with verified replacement and rollback. This is a **proposal**, not existing policy. Place notices in release notes and user/maintainer documentation first; never add unsolicited CLI output unless compatibility testing explicitly permits it.

### Gate G4 — separate destructive cleanup authorization

Retire binaries or scripts **only** after:
- Demonstrable positive and negative compatibility for affected supported data schemas (or explicit owner-approved unresolved exceptions);
- Known consumer inventory and an explicit owner acceptance of external/manual unknowns;
- Alternative execution path and backwards-compatibility commitment published and tested;
- Real Graph Studio saved data checksummed; no `~/RoadPilotGraphStudio` deletion/rewrites; F8 architecture contract, Android compatibility and install/uninstall gates independently accepted;
- Separate deletion PR, independent review, exact-head CI, rollback plan and **explicit approval to merge that deletion**.

### Immediate disposition

| Area | Status |
| --- | --- |
| Nonempty reconstructed frontier v1 CLI sample | **PASS** historical/current/installed; nominal-only synthetic |
| Genuine saved nonempty production artifacts | **UNKNOWN / NOT_RECOVERED** |
| Ten other populated v1 schema families | **NOT_VERIFIED** |
| Past automation consumers | **CONFIRMED (11 CI, 7 orchestrator)** |
| Active out-of-tree / manual callers | **UNKNOWN** |
| Remove / disable validators | **BLOCKED** |
| F8 routing and Android graph parity | **NOT_VERIFIED** by this effort |

**All eleven validators RETAIN. Keep [issue #89](https://github.com/kandyman991/RoadPilot-Offline-Data/issues/89) open.** Issue #89 also tracks the Graph Studio UI Phase 4 cleanup and must not be closed solely because this evidence PR merges.
