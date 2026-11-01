# Graph Studio P4-B — legacy CLI compatibility evidence (baseline)

**Recorded:** 2026-11-01  
**Status:** IN PROGRESS — evidence collection only; **NO REMOVAL AUTHORIZED**.  
**Tracking:** [issue #89](https://github.com/kandyman991/RoadPilot-Offline-Data/issues/89), [Phase 4 audit](GRAPH_STUDIO_PHASE4_DEPENDENCY_AUDIT.md).  
**Last functional Graph Studio source independently inspected on Legion:** `265eab5` (same functional source as merged PR #92).  
**Documentation audit merged:** PR #95, merge `c555dc9e45e2642433affeb5bfb97355f10ce391`.

## What was actually verified

1. The 11 legacy validators are **Git-tracked**, and the installed Debian package `road-pilot-graph-studio` **version 0.1.0** includes all 11 under `/usr/lib/RoadPilot Graph Studio/pipeline/tools/`. Each installed Debian script is byte-identical to its corresponding file in the inspected Legion functional checkout; no candidate-path mismatch was reported by `dpkg --verify`.
2. The installed `~/Applications/RoadPilot-Graph-Studio-Linux.AppImage`, SHA-256 `54bac0a760fb4de98c0a083b78c34147f8c8a4ae27606520cb88deeab84dcb75`, contains all 11 script paths (verified via `unsquashfs -ll -o 944632`, **read-only**, without extracting or executing the application). These are real installed-package entry points, **not** merely unused project source.
3. Each source CLI returns **exit 0** and includes a `usage:` line when invoked with `--help`. Ten expose required `--artifact`; `validate_frontier_road_inventory.py` exposes required `--inventory`. All eleven validators explicitly check historical `roadpilot.*` schema identity and `version == 1`.
4. An exact-filename/stem scan of **Git-tracked executable/config/workflow code**, excluding the scanner's own self-references, detected **zero literal callers** for each of the eleven. An additional bounded filename-only search within `/home/mircea/projects` for these names (excluding `.git`, `node_modules`, `.venv`, `build`, `dist`, `target`) returned no matches outside the source being examined; it is **not** an audit of all shell history, installers, cron jobs, user scripts or external systems.
5. The new reproducible `tools/audit_legacy_validator_dependencies.py` reports tracked literal references, script SHA-256 and Tauri wildcard packaging presence; `--probe-help` optionally records help exit status and hashes without touching user workspaces. It does not pretend to detect runtime-computed callers. `tests/test_legacy_validator_dependency_audit.py` confirms deterministic output, tracked-only resolution, and exclusion of symlinks outside the repository. Verified on a **temporary shallow checkout** of this P4-B branch on Legion: **3/3 tests passed**, all 11 optional `--help` probes passed, no local source checkout mutation.
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
PYTHONDONTWRITEBYTECODE=1 python tools/audit_legacy_validator_dependencies.py > /tmp/graph-studio-p4b-tracked-dependencies.json
PYTHONDONTWRITEBYTECODE=1 python tools/audit_legacy_validator_dependencies.py --probe-help > /tmp/graph-studio-p4b-cli-help.json
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p test_legacy_validator_dependency_audit.py -v
```

The tool prints to stdout and **does not write a report or change installed/user data**; shell redirection above writes only the explicitly chosen temporary evidence file. `--probe-help` invokes fixed repository-tracked CLI programs, never arbitrary user-provided commands or historical artifacts. The scanner's zero-literal-reference observation is **not** evidence of no dynamic, externally launched or manually executed caller.

Installed Debian evidence can be repeated using `dpkg -L road-pilot-graph-studio` and `dpkg --verify road-pilot-graph-studio`; AppImage contents can be inspected without extraction using its `--appimage-offset` and `unsquashfs -ll -o <offset>`. These are read-only checks. This report deliberately omits personal user-workspace contents.

## Outstanding P4-B gates (blocking any removal)

- **External callers:** inspect known systemd/cron/manual maintenance scripts, older installed package manifests, non-repository automation and operational procedures, without sweeping private user data. Record scope, owner and evidence for each candidate. An unsearchable or unknown consumer stays **UNKNOWN**, not `UNUSED`.
- **Historical artifacts:** locate sanitized representative **real** files for each claimed schema version, copy them into an isolated temporary fixture workspace, checksum originals, and compare validation exit code, stdout/stderr, and read-only behavior across the old installed version and candidate changes. Absence must be documented rather than filled with invented samples. Do not import raw private data into the repo.
- **Missing schema question:** determine whether `region-connector-refresh-plan` was intentionally validator-only, whether a historical schema existed elsewhere, and whether the missing schema file affects actual consumers. No speculative new format.
- **Compatibility envelope:** document every CLI's arguments, output, exit statuses, failure handling, generated/modified files (if any), and historical schema expectations. Retain an existing entry point or a tested, explicitly approved versioned deprecation path for any unresolved user.
- **Acceptance and safety:** byte-identical retained `handoffs/`, `transitions/`, `connectivity/`, `connector-matrices/`, `imports/`, graph/PMTiles/POI/manifests and immutable source caches; proof with checksum inventory and rollback against **isolated copies** before proposing a separate implementation PR. The installed real workspace must not be used for destructive rollback tests.
- **Independent review / CI:** exact-head `architecture-contract`, `validate`, `linux` (this PR touches `tools/`) plus architecture/security/data-integrity review. No merge or release authorized for this development PR; no F8 scanner parity or Android device acceptance is claimed.

**Current decision:** **P4-B OPEN; 11/11 VALIDATORS RETAIN.** Initial installed-path and static dependency evidence is complete, but external usage and real historical fixture compatibility are NOT_VERIFIED. Issue #89 remains open. Native F8 graph-edge parity/Android publication remains blocked under the accepted architecture contract.
