# Graph Studio P4-B3 — populated historical artifact and external CLI evidence

**Recorded:** 2026-11-01  
**Status:** Non-destructive investigation; **NOT permission to remove any CLI**.  
**Tracking:** [issue #89](https://github.com/kandyman991/RoadPilot-Offline-Data/issues/89). Earlier gates: [P4-B](GRAPH_STUDIO_PHASE4B_CLI_COMPATIBILITY.md) and [P4-B2 real fixture audit](GRAPH_STUDIO_PHASE4B_REAL_FIXTURE_EXTERNAL_CONSUMER_EVIDENCE.md).

## Executive findings

1. **Genuine populated v1 inputs for the 11 retained legacy validators: still NOT_FOUND in bounded audited roots.** This is an absence *within those limits*, not proof of global nonexistence.
2. **Real empty frontier-road-inventory remains present:** `roadpilot.frontier-road-inventory` v1 with `roads: []`, SHA-256 `87a1cbf59546cd42644577185a2fd5c4f5155e536f05018ebcdf24ce9add261e`. P4-B2 proved that source and installed Debian validators both accept an unchanged temporary copy (exit 0 and identical stdout/stderr). Empty roads do **not** exercise populated record rules.
3. **Historical direct consumers confirmed:** pre-#84 `.github/workflows/validate.yml` directly invoked **all 11** validators. The retired `tools/refresh_graph_connectivity.py` orchestrated **seven** of these entry points. New code cannot assume that absence of *current* direct references means the CLIs were never used.
4. **No retained GitHub Actions artifacts:** an authenticated, read-only repository query `GET /repos/kandyman991/RoadPilot-Offline-Data/actions/artifacts?per_page=100` returned `total_count: 0` on 2026-11-01. This establishes *currently downloadable artifact availability*, not that historic workflows never generated/used artifact files. Historical `validate.yml` directly constructed JSON fixtures inside runner temp directories and did not include an `actions/upload-artifact` step in the inspected pre-#84 revision.
5. **Three *historical committed* tests/fixtures recovered in Git history have different schemas**, and must not be passed off as positive legacy-validator coverage: `tests/fixtures/austria-boundary-inventory.json` (`roadpilot.boundary-edge-inventory`, two edges), `tests/fixtures/oberbayern-boundary-inventory.json` (same schema, three edges), and `tests/fixtures/austria-oberbayern-proof-results.json` (`roadpilot.transition-proof-results`, four results). These are genuine retained test fixture bytes, but **not** the `roadpilot.frontier-road-inventory`, `roadpilot.crossing-proofs`, or other eleven legacy schemas.
6. **Current external callers remain UNKNOWN.** Limited scans of the authorized Legion's runner scripts, owner Bash history, scheduled jobs, SmartRide-Next current source and other checked worktrees found no matching direct script filename. Default-branch GitHub code search under the owner's account for `validate_frontier_road_inventory.py` and `validate_region_connector_refresh_plan.py` returned only references in this repository's audit/docs/tests (not another current repository), subject to code search indexing and query limits. Old CI automation and shipped Debian/AppImage entry points remain real compatibility obligations.

## Reproducible on-device inventory — avoid manual interpretation

Added **development-only** `devtools/audit_historical_fixture_inventory.py`. It does not execute scripts, import user artifacts into Git, write files, or print private content, paths, coordinates or identifiers. The caller must explicitly nominate roots using `--root`. JSON files are scanned under size/file/depth limits, with symlinks and common dependency trees excluded. The output contains only allowlisted schema IDs, versions, SHA-256, byte length, and top-level payload list **counts**, including a precise `frontier_roads_populated` flag. SHA-256 is proof of file identity, **not** content sanitization or validation. Missing results never authorize deletion.

On the author's connected Legion, a temporary clone of the P4-B3 branch used:

```bash
PYTHONDONTWRITEBYTECODE=1 python devtools/audit_historical_fixture_inventory.py \
  --root "$HOME/RoadPilotGraphStudio" \
  --root "$HOME/roadpilot-f8-stage5-audit" \
  --root "$HOME/roadpilot-f8-learned-replay" \
  --root "$HOME/roadpilot-f8-cleanup"
```

### Actual bounded audit counts

| Explicit root (user home relative) | JSON files checked | Over 16 MiB, skipped | Matching v1 legacy schemas | Genuine nonempty legacy payloads |
| --- | ---: | ---: | ---: | ---: |
| `RoadPilotGraphStudio/` (operational workspace, ~53 GiB overall) | **85** | **4** | **1** (`frontier-road-inventory`, zero roads) | **0** |
| `roadpilot-f8-stage5-audit/` | **137** | **0** | **0** | **0** |
| `roadpilot-f8-learned-replay/` | **137** | **0** | **0** | **0** |
| `roadpilot-f8-cleanup/` | **137** | **0** | **0** | **0** |

All four root reports had `truncated: false` at the explicit **20,000 JSON files, 16 MiB per file, 18 directory levels** limits, although the four oversized workspace JSON files are **not classified**. The scanner deliberately includes generated `work/*/build/` directories; a regression check protects that coverage. `tests/`, dependency and build output outside these four roots and other accounts/volumes/backups are not included. Previous P4-B2 bounded user-home/Android scans found no additional matching schema. Only *current* archived content was visible; there is no guarantee historic outputs still exist.

**Security caveats:** The inventory is read-only and non-executing, but scans authorized directories supplied by the operator. It is not a filesystem security sandbox, historical restore engine or user-data scrubber. It reports metadata only; full file contents remain at their original locations. Never put personal artifact bytes into a public repository. All tests use synthetic data, and cannot be counted as genuine positive historical fixture proofs.

## Historical consumer chronology and availability

- **Historical pre-#84 source:** `git grep` at `661a23a^` or `2b16d2b^` reveals direct old validation jobs in `.github/workflows/validate.yml` for **all eleven** validator names. The old `tools/refresh_graph_connectivity.py` tool pipeline had direct or stage-resolved invocations of seven. Those are confirmed **past** program consumers, not assumptions.
- **Modern checked source:** no exact literal calls to the 11 legacy CLI names from Graph Studio's tracked executable/workflow files. The current Rust `run_r2_json_script` dynamic helper's two call sites select **fixed R2 scripts** (`test_r2_connection.py`, `inspect_r2_publication.py`), not a general selection of these legacy validator names. No active direct invocation was established.
- **Archived CI:** GitHub Actions runs for October 1–16, 2026 still have metadata (historical run list queried); **zero retained/downloadable repository Actions artifacts** were returned. The earlier workflow created example JSON under temp roots, but those bytes are not available in the repository artifact index. Do not invent or recreate them and call them originals.
- **Other current repository code:** scoped account-wide GitHub code search for exact two validator filenames surfaced only audit/documentation references in `RoadPilot-Offline-Data`. This cannot establish that separate automation, older checked-out branches, shell aliases, external devices, or manually invoked CLI tools no longer use them.

## Tests and safety decisions

- `tests/test_historical_fixture_inventory.py` covers **six** deterministic synthetic tests: empty vs populated frontier roads flagged separately without private values; exact allowlisted 11 schema names and rejection of unrelated historical formats; symlink traversal exclusion; file-count/size caps and truncation; depth-cap disclosure; **generated `work/*/build/` outputs included**.
- No application runtime/package, `tools/` validator, graph, Android integration, installation or user artifact was edited. No historical private fixture data was copied into GitHub.
- Verify exact-head Python tests and the two path-applicable GitHub checks (`architecture-contract`, `validate`) after review/correction. Final Linux packaging is path-filtered for `devtools/`, `tests/`, `docs/` and `CHAT_HANDOFF.md`.
- Keep [issue #89](https://github.com/kandyman991/RoadPilot-Offline-Data/issues/89) **OPEN** and all **11/11 validators RETAIN**. Real populated schema acceptance, currently active external/manual consumers, graph-edge parity and Android device acceptance remain **NOT_VERIFIED**. Later deletion or deprecation must be proposed separately, with explicit owner approval, staged wrappers/compatibility contract, data checksums and reversible tests using isolated copies.

**Conclusion:** evidence strengthens the case that current local F8 workflows no longer directly call the old stack, while proving that all eleven CLIs had historical CI consumers. The absence of genuine populated original schema files and unbounded external usage remains a **blocking gap for removal**, not an excuse to delete.
