# Graph Studio P4-B — legacy CLI compatibility evidence (baseline)

**Recorded:** 2026-11-01  
**Status:** IN PROGRESS — evidence collection only; **NO REMOVAL AUTHORIZED**.  
**Tracking:** [issue #89](https://github.com/kandyman991/RoadPilot-Offline-Data/issues/89), [Phase 4 audit](GRAPH_STUDIO_PHASE4_DEPENDENCY_AUDIT.md).  
**Last functional Graph Studio source independently inspected on Legion:** `265eab5` (same functional source as merged PR #92).  
**Documentation audit merged:** PR #95, merge `c555dc9e45e2642433affeb5bfb97355f10ce391`.

## P4-B follow-up: actual operational workspace and positive fixture (2026-11-01)

The initial baseline below searched tracked repository roots and the desktop application-data directory, but **not** the application's actual operational workspace at `~/RoadPilotGraphStudio` (approximately 53 GiB of builds and diagnostics). The follow-up [real-fixture and consumer evidence report](GRAPH_STUDIO_PHASE4B_REAL_FIXTURE_EXTERNAL_CONSUMER_EVIDENCE.md) corrects that coverage gap and records one genuine historical-format `roadpilot.frontier-road-inventory` version-1 artifact. Its **empty** `roads` list passes **both source and installed Debian validator**, exit 0 and identical output, with checksummed copy/original unchanged. This does **not** establish populated road-record compatibility. The other ten historical positive formats remain not found in the bounded scan; external consumers remain UNKNOWN. All eleven legacy validators **RETAIN**. This addendum supersedes any earlier assertion that *no* genuine v1 legacy artifact had been located.

## What was actually verified

1. The 11 legacy validators are **Git-tracked**, and the installed Debian package `road-pilot-graph-studio` **version 0.1.0** includes all 11 under `/usr/lib/RoadPilot Graph Studio/pipeline/tools/`. Each installed Debian script is byte-identical to its corresponding file in the inspected Legion functional checkout; no candidate-path mismatch was reported by `dpkg --verify`.
2. The installed `~/Applications/RoadPilot-Graph-Studio-Linux.AppImage`, SHA-256 `54bac0a760fb4de98c0a083b78c34147f8c8a4ae27606520cb88deeab84dcb75`, contains all 11 script paths (verified via `unsquashfs -ll -o 944632`, **read-only**, without extracting or executing the application). These are real installed-package entry points, **not** merely unused project source.
3. Each source CLI returns **exit 0** and includes a `usage:` line when invoked with `--help`. Ten expose required `--artifact`; `validate_frontier_road_inventory.py` exposes required `--inventory`. All eleven validators explicitly check historical `roadpilot.*` schema identity and `version == 1`.
4. An exact-filename/stem scan of **Git-tracked executable/config/workflow code**, excluding the scanner's own self-references, detected **zero literal callers** for each of the eleven. An additional bounded filename-only search within `/home/mircea/projects` for these names (excluding `.git`, `node_modules`, `.venv`, `build`, `dist`, `target`) returned no matches outside the source being examined; it is **not** an audit of all shell history, installers, cron jobs, user scripts or external systems.
5. The new reproducible `devtools/audit_legacy_validator_dependencies.py` reports tracked literal references, script SHA-256, Git HEAD, whether tracked worktree files are dirty, and Tauri wildcard packaging presence. The output uses a portable repository identifier rather than leaking an absolute home-directory path. `--probe-help` **executes script code** (even when the arguments are only `--help`); it now requires explicit `--acknowledge-cli-execution` and a clean committed tracked worktree. It is not inherently side-effect free; run it only on a trusted checkout, never against unknown code or personal artifacts. It does not pretend to detect runtime-computed callers. `tests/test_legacy_validator_dependency_audit.py` confirms deterministic output, tracked-only resolution, and exclusion of symlinks outside the repository. Verified on a **temporary shallow checkout** of this P4-B branch on Legion: **3/3 tests passed**, all 11 optional `--help` probes passed, no local source checkout mutation.
6. Ten corresponding `schemas/<name>.schema.json` files are tracked, but **`schemas/region-connector-refresh-plan.schema.json` was not found** for `validate_region_connector_refresh_plan.py`. This is an investigation item, **not proof that the validator cannot read its historic inputs** or permission to invent a replacement schema.

## Per-CLI baseline — no retirement approvals

| Historical CLI (`tools/`) | Existing required input | Expected schema (version 1) | Tracked JSON schema | Source/installed package | External CLI consumers | Historical real fixture | Decision |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `validate_connectivity_chain_plan.py` | `--artifact` | `roadpilot.connectivity-chain-plan` | Present | Source, .deb, AppImage | UNKNOWN | NOT_INSPECTED | RETAIN |
| `validate_connectivity_refresh_plan.py` | `--artifact` | `roadpilot.connectivity-refresh-plan` | Present | Source, .deb, AppImage | UNKNOWN | NOT_INSPECTED | RETAIN |
| `validate_crossing_candidates.py` | `--artifact` | `roadpilot.crossing-candidates` | Present | Source, .deb, AppImage | UNKNOWN | NOT_INSPECTED | RETAIN |
| `validate_crossing_proofs.py` | `--artifact` | `roadpilot.crossing-proofs` | Present | Source, .deb, AppImage | UNKNOWN | NOT_INSPECTED | RETAIN |
| `validate_frontier_road_correlations.py` | `--artifact` | `roadpilot.frontier-road-correlations` | Present | Source, .deb, AppImage | UNKNOWN | NOT_INSPECTED | RETAIN |
| `validate_frontier_road_inventory.py` | `--inventory` | `roadpilot.frontier-road-inventory` | Present | Source, .deb, AppImage | UNKNOWN | NOT_INSPECTED | RETAIN |
| `validate_hierarchical_connectivity_plan.py` | `--artifact` | `roadpilot.hierarchical-connectivity-plan` | Present | Source, .deb, AppImage | UNKNOWN | NOT_INSPECTED | RETAIN |
| `validate_region_connector_inventory.py` | `--artifact` | `roadpilot.region-connector-inventory` | Present | Source, .deb, AppImage | UNKNOWN | NOT_INSPECTED | RETAIN |
| `validate_region_connector_matrix.py` | `--artifact` | `roadpilot.region-connector-matrix` | Present | Source, .deb, AppImage | UNKNOWN | NOT_INSPECTED | RETAIN |
| `validate_region_connector_refresh_plan.py` | `--artifact` | `roadpilot.region-connector-refresh-plan` | **No matching tracked schema JSON** | Source, .deb, AppImage | UNKNOWN | NOT_INSPECTED | RETAIN |
| `validate_runtime_connectivity.py` | `--artifact` | `roadpilot.runtime-connectivity` | Present | Source, .deb, AppImage | UNKNOWN | NOT_INSPECTED | RETAIN |

### Repeatable, safe checks

Run from the repository root:

```bash
PYTHONDONTWRITEBYTECODE=1 python devtools/audit_legacy_validator_dependencies.py > /tmp/graph-studio-p4b-tracked-dependencies.json
PYTHONDONTWRITEBYTECODE=1 python devtools/audit_legacy_validator_dependencies.py --probe-help --acknowledge-cli-execution > /tmp/graph-studio-p4b-cli-help.json
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p test_legacy_validator_dependency_audit.py -v
```

The static/default mode prints to stdout, **does not execute validator scripts**, and does not write reports or change installed/user data; shell redirection above writes only the explicitly chosen temporary evidence file. Optional `--probe-help` executes the 11 tracked scripts from a **clean trusted checkout** after explicit acknowledgment; allowlisting the script names alone does not guarantee those scripts are free from side effects. It does not accept arbitrary user-supplied command paths, and the optional probes do not supply historical artifacts. The scanner's zero-literal-reference observation is **not** evidence of no dynamic, externally launched or manually executed caller.

Installed Debian evidence can be repeated using `dpkg -L road-pilot-graph-studio` and `dpkg --verify road-pilot-graph-studio`; AppImage contents can be inspected without extraction using its `--appimage-offset` and `unsquashfs -ll -o <offset>`. These are read-only checks. This report deliberately omits personal user-workspace contents.

## Installed packaging guard (independent review R05)

The Tauri `../../tools/` resource wildcard automatically includes every file under `tools/` in installed Debian and AppImage packages. A Git-dependent diagnostic originally located there would inadvertently alter the shipped CLI surface and fail to operate outside a source checkout. The dependency audit tool is therefore stored only under `devtools/`, **outside the shipped resources**, and a regression test rejects accidental reintroduction to `tools/`. No Graph Studio installed runtime or legacy validator was changed. This is a review correction, not a reason to relax the wildcard compatibility gate.

## Independent review and expanded compatibility evidence (2026-11-01)

**Independent code review of original P4-B head `a30d917`:** all three GitHub workflows (`architecture-contract`, `validate`, `linux`) completed **SUCCESS** on that head. Review R01 found that an optional `--help` execution was being described too strongly as read-only; corrected with explicit opt-in, clean tracked-checkout requirement, explicit execution-risk warning and Python bytecode/user-site restrictions. R02 found unnecessary absolute checkout path disclosure and insufficient exact-revision provenance; corrected with portable output, Git HEAD and dirty tracked-worktree marker. Fresh CI must be evaluated on the **corrected** head, not inferred from the prior success.

**Installed CLI behavior / data-integrity comparison:** using a dedicated automatically removed temporary directory, tested 11 fixed validators from the read-only Legion source checkout against their installed Debian copies with a **synthetic invalid-schema JSON**, not a real historical artifact. For all **11/11** the help stdout/stderr/exit result was an exact match; for **11/11** the invalid-schema rejection exit (code 1), stdout and final error diagnostic matched. SHA-256 of the input remained unchanged and the temporary directory held only the original fixture afterward. This is a **negative/error-path compatibility baseline**, not positive legacy schema acceptance. The regression suite now includes an isolated synthetic-invalid-schema nonrewrite assertion for all 11 names.

**Historical fixture search (bounded; no user artifact contents emitted):** parsed non-symlink JSON files up to 4 MB, excluding source-control directories, build outputs, caches and dependency folders. In the Graph Studio repository **31** JSON documents were parsed, in the local SmartRide-Next repository **4**, and in Graph Studio's standard desktop application data directory **0**. **No document matched one of the 11 historical `roadpilot.*` schema markers.** This does *not* establish that no historical fixture exists elsewhere, e.g. user-selected workspaces, remote artifact storage or old installed backups. All eleven positive-fixture cells remain **NOT_VERIFIED**.

**Cross-repository and operational caller search (bounded):** the local `SmartRide-Next` Git-tracked tree had no exact validator-name matches for any of the eleven; read-only literal-string scans of accessible `/etc/systemd/system`, `/etc/cron.d`, `/etc/cron.daily`, `~/.config/systemd/user` and `~/.local/bin` found no matches. A check of the user's crontab found no matching names. These observations do **not** cover other accounts, historical packages, unexamined scripts, dynamically constructed command names or network/CI systems. The external-consumer classification remains **UNKNOWN**.

**Missing schema provenance:** the current tracked `schemas/` folder and available local Git history contain no `schemas/region-connector-refresh-plan.schema.json`; a source-content search found the marker `roadpilot.region-connector-refresh-plan` in the validator itself but not other current application source. Accessible history does show the validator was introduced (commit `dd2c083`, 2026-10-07). Whether a separately published schema or external historical consumer ever existed remains **UNVERIFIED**. **Do not invent a schema or remove the validator based on this.**

## Outstanding P4-B gates (blocking any removal)

- **External callers:** inspect known systemd/cron/manual maintenance scripts, older installed package manifests, non-repository automation and operational procedures, without sweeping private user data. Record scope, owner and evidence for each candidate. An unsearchable or unknown consumer stays **UNKNOWN**, not `UNUSED`.
- **Historical artifacts:** locate sanitized representative **real** files for each claimed schema version, copy them into an isolated temporary fixture workspace, checksum originals, and compare validation exit code, stdout/stderr, and read-only behavior across the old installed version and candidate changes. Absence must be documented rather than filled with invented samples. Do not import raw private data into the repo.
- **Missing schema question:** determine whether `region-connector-refresh-plan` was intentionally validator-only, whether a historical schema existed elsewhere, and whether the missing schema file affects actual consumers. No speculative new format.
- **Compatibility envelope:** document every CLI's arguments, output, exit statuses, failure handling, generated/modified files (if any), and historical schema expectations. Retain an existing entry point or a tested, explicitly approved versioned deprecation path for any unresolved user.
- **Acceptance and safety:** byte-identical retained `handoffs/`, `transitions/`, `connectivity/`, `connector-matrices/`, `imports/`, graph/PMTiles/POI/manifests and immutable source caches; proof with checksum inventory and rollback against **isolated copies** before proposing a separate implementation PR. The installed real workspace must not be used for destructive rollback tests.
- **Independent review / CI:** exact-head `architecture-contract`, `validate`, `linux` (this PR touches `tools/`) plus architecture/security/data-integrity review. No merge or release authorized for this development PR; no F8 scanner parity or Android device acceptance is claimed.

**Current decision:** **P4-B OPEN; 11/11 VALIDATORS RETAIN.** Initial installed-path and static dependency evidence is complete, but external usage and real historical fixture compatibility are NOT_VERIFIED. Issue #89 remains open. Native F8 graph-edge parity/Android publication remains blocked under the accepted architecture contract.
