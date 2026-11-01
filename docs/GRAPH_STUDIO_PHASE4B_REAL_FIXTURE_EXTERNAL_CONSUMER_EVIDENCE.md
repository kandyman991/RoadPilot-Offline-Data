# Graph Studio P4-B — genuine legacy fixture and external CLI consumer evidence

**Date:** 2026-11-01  
**Status:** INVESTIGATION / NO RETIREMENT AUTHORIZED.  
**Related:** [Phase 4 dependency audit](GRAPH_STUDIO_PHASE4_DEPENDENCY_AUDIT.md), [P4-B CLI compatibility baseline](GRAPH_STUDIO_PHASE4B_CLI_COMPATIBILITY.md), [issue #89](https://github.com/kandyman991/RoadPilot-Offline-Data/issues/89).

## 1. Actual Graph Studio workspace located and searched

The native Linux Graph Studio application uses `~/RoadPilotGraphStudio` for operational builds, inputs and diagnostics (the desktop app-data directory `~/.local/share/app.roadpilot.graphstudio` inspected during the previous audit is *not* the same thing). On the owner's connected Legion, the real workspace was approximately **53 GiB** according to `du -sh` (`53G`). Its first two directory levels include `handoffs/`, `transitions/`, `connectivity/`, `connector-matrices/`, `imports/`, `f8-native/`, `diagnostics/`, `builds/`, `visual-builds/` and `work/`. **No data was modified or deleted.**

A read-only, non-symlink JSON-content inspection within the actual workspace parsed **81 JSON files** below 8 MiB each, skipped **4** larger files, and found **one exact `roadpilot.*` legacy-validator schema**. The other documents included modern `roadpilot.native-f8-*`, `roadpilot.graph-studio-*`, graph-index and routing-pack schemas; these are not silently reclassified as old formats. A separate bounded first-16-KiB/64-KiB JSON-header scan examined relevant workspace and owner's project/data directories (including `Documents/`, `Downloads/`, `Desktop/`, `dev-data/`, `Android/`, and the known F8 audit worktrees); it found no other matching historical-validator schema marker. Large or out-of-scope artifacts and external storage **remain unverified**.

### Genuine historical-format artifact

- Owner-workspace-relative path: `diagnostics/f8-italy-austria-validation/frontier-nominal-diagnostic.json` (under `~/RoadPilotGraphStudio/`).
- Actual schema: `roadpilot.frontier-road-inventory`, version **1**.
- Generator metadata: `roadpilot-osm-frontier-inventory`, version **1**.
- Size: **1,006 bytes**; source SHA-256 `87a1cbf59546cd42644577185a2fd5c4f5155e536f05018ebcdf24ce9add261e`; filesystem modified time `2026-10-14T19:08:31.777855Z`.
- **Coverage limitation:** `roads` is an **empty array**. This is a genuine saved operational/diagnostic artifact that exercises version-1 envelope/empty-list acceptance, **not** representative evidence of populated road-record compatibility, production frontier completeness, Android F8 graph-edge parity, or positive acceptance for the other ten schema types.

For the actual file, both the **read-only functional source validator** `tools/validate_frontier_road_inventory.py` and the installed Debian script `/usr/lib/RoadPilot Graph Studio/pipeline/tools/validate_frontier_road_inventory.py` returned **exit 0**, the same stdout SHA-256 `4ad609f0d072e29295a44a022a191061fca4148a5a39fef397523eaf7b48028e`, and empty stderr. Input and isolated-copy SHA-256 stayed unchanged, and no output files were created. The installed Debian script and source version were previously confirmed byte-identical in the P4-B baseline.

The P4-B2 developer-only verifier `devtools/verify_legacy_fixture_parity.py` was also run on **a fresh temporary checkout of this branch** using that actual original file, with the explicit `--acknowledge-execution` flag, and reported `positive_parity: true`, `original_unchanged: true`, no new files from either CLI, and exactly the source SHA-256 above. **It never passes the original artifact path to a validator; both programs receive disposable copies.** The tool reports hashes/statuses rather than private input contents or absolute source filenames.

**Important safety note:** The verifier invokes real Python scripts. Its temporary copies protect the fixture from direct overwrites, but neither temporary directories nor script allowlisting sandbox malicious code or prevent unexpected external side effects. Run only with trusted installed/source programs after explicit operator acknowledgment. It rejects symlinked/nonregular nominated fixtures, wrong schema/version, and inputs over 64 MiB. It is excluded from shipped `tools/` resources by living under `devtools/`.

Repeatable owner-controlled command (runs trusted Python code and does not install/modify Graph Studio):

```bash
cd /path/to/RoadPilot-Offline-Data
PYTHONDONTWRITEBYTECODE=1 python devtools/verify_legacy_fixture_parity.py \
  --validator validate_frontier_road_inventory.py \
  --fixture "$HOME/RoadPilotGraphStudio/diagnostics/f8-italy-austria-validation/frontier-nominal-diagnostic.json" \
  --acknowledge-execution
```

## 2. Complete evidence matrix (11 historical CLI surfaces)

| Retained legacy validator | Found genuine v1 input | Positive tested against source and installed Debian | Remaining gap |
| --- | --- | --- | --- |
| `validate_frontier_road_inventory.py` | Yes — original diagnostic, zero road rows | **PASS / identical** | Populated roads, Android F8 parity |
| `validate_connectivity_chain_plan.py` | Not in scanned roots | NOT_VERIFIED | Real historical positive fixture |
| `validate_connectivity_refresh_plan.py` | Not in scanned roots | NOT_VERIFIED | Real historical positive fixture |
| `validate_crossing_candidates.py` | Not in scanned roots | NOT_VERIFIED | Real historical positive fixture |
| `validate_crossing_proofs.py` | Not in scanned roots | NOT_VERIFIED | Real historical positive fixture |
| `validate_frontier_road_correlations.py` | Not in scanned roots | NOT_VERIFIED | Real historical positive fixture |
| `validate_hierarchical_connectivity_plan.py` | Not in scanned roots | NOT_VERIFIED | Real historical positive fixture |
| `validate_region_connector_inventory.py` | Not in scanned roots | NOT_VERIFIED | Real historical positive fixture |
| `validate_region_connector_matrix.py` | Not in scanned roots | NOT_VERIFIED | Real historical positive fixture |
| `validate_region_connector_refresh_plan.py` | Not in scanned roots | NOT_VERIFIED | Real historical positive fixture; old generator retired |
| `validate_runtime_connectivity.py` | Not in scanned roots | NOT_VERIFIED | Real historical positive fixture |

All **11/11 remain RETAIN**. The previously proven identical `--help` and deliberately invalid-schema rejection contracts for 11/11 validators do not substitute for positive-schema historical fixtures. A generator formerly producing `roadpilot.region-connector-refresh-plan` v1 was traced in Git history to retired `tools/plan_region_connector_refresh.py` (commit `dd2c083`, removed around #84); no standalone tracked schema JSON was found for that type. It must not be regenerated or declared unused on speculation.

## 3. External/manual/operational consumer searches

Read-only *literal-name* scans were run for all **11 complete validator script stems**. A result of zero matches is **not** proof of no users; dynamically constructed script names, older releases, cloud automation, other accounts, archives and manual/offline invocation are not conclusively covered.

| Scope scanned | Evidence |
| --- | --- |
| Git-tracked Graph Studio/Offline-Data executable source and workflows | 0 direct literal callers; static scanner in merged PR #96, restricted to tracked executable/config files |
| Local `SmartRide-Next` Git-tracked repository | 0 matching validator names |
| Accessible system units and jobs: `/etc/systemd/system`, `/etc/cron.d`, `/etc/cron.daily`, `~/.config/systemd/user`, `~/.local/bin`, current crontab | 0 matching validator names in bounded search |
| Owner's local Bash-history file | 0 matching validator names, checked by exact script-name membership without printing command contents |
| `actions-runner/` and `actions-runner-legionremote/` selected script/config/log/text files | 298 inspected files, 0 matching names; excludes runner working directories and external workflow service logs |
| `roadpilot-runner-hooks/`, `roadpilot-f8-stage5-audit/`, `roadpilot-f8-cleanup/`, `roadpilot-f8-learned-replay/`, `LegionBridge/`, `legionbridge-worktrees/` selected script/config/log/text files | 1,827 inspected files in aggregate, 0 matching names; excludes dependency/build directories, binary content and larger files |
| Installed Debian `road-pilot-graph-studio` version 0.1.0 and installed Graph Studio AppImage | **11/11 tools shipped**; packaged CLI entry points are *confirmed* compatibility obligations even without discovered internal callers |

For local script/config scans, scope intentionally restricted file extensions to `.sh`, `.py`, `.yml`, `.yaml`, `.json`, `.toml`, `.service`, `.timer`, `.bash`, `.zsh`, `.log`, `.txt`, `.md`, `.ini`; files over 4 MiB, build/dependency/output directories, symlinks and unvisited external resources were not searched. No personal shell-history or user-artifact contents were copied to GitHub.

## 4. Reproducible test and review gates

- New developer verifier is **not bundled into the Linux application**, because Tauri packages `tools/` via wildcard. Existing 11 CLIs and Android/F8 logic are unchanged.
- `tests/test_legacy_fixture_parity.py` covers: success on isolated copies; refusal without operator acknowledgment; rejection of wrong schema, symlink and oversize; mismatch on different validator output; detection of extra files created in temporary workspace; no personal input path leaked.
- First temporary clean checkout of the new branch on Legion: **118/118 Python tests passed** (`114` prior + `4` new), **real saved v1 artifact matched both validators**, with original and copy integrity preserved.
- Required prior to considering this PR merge-ready: **independent architecture/security/data-integrity review**, correction of findings, then **exact corrected-head** GitHub architecture contract and repository validation workflows. Linux packaging is path-filtered because only `devtools/`, `tests/` and `docs/`/handoff change; no runtime build success should be invented for a path-filtered PR.

## 5. Outstanding gates — blocking cleanup

1. Locate **genuine nonempty historical artifacts** for the original 11 schemas (including a populated frontier-road inventory), possibly from historical operator export archives or previous graph-generation snapshots. Locate with authorization and validate only on isolated, checksummed copies; no fictional fixtures.
2. Obtain responsible maintainer/operator evidence for potential CLI users outside the scanned repositories/directories and assess installed-version support/deprecation contracts. Existing installed entry points remain reachable and cannot be silently removed.
3. Before *any* behavior-changing cleanup proposal, prove no retained `handoffs/`, `transitions/`, `connectivity/`, `connector-matrices/`, `imports/`, graph/PMTiles/POI or immutable cache data changes; use isolated copies, checksums and rollback checks. Do **not** operate destructively on `~/RoadPilotGraphStudio`.
4. Maintain the F8 architecture contract; graph-edge parity and Android device ingestion remain **NOT_VERIFIED** by this historical CLI exercise. No publication authorization follows from this work.

**Decision:** one genuine but **empty-road-list** historical format passes real positive input parity; **10/11** genuine positive fixtures remain unavailable in the bounded scan. **All 11 validators RETAIN; issue #89 OPEN; no deletion, F8 change or release authorized.**
