# Graph Studio Phase 4 / P4-C — archive of the legacy connectivity validators and schemas

**Date:** 2026-11-03 · **Decision:** D-016 · **Status:** draft PR, stacked on the retirement-record PR; not merged.
**Base audit:** `docs/GRAPH_STUDIO_PHASE4_DEPENDENCY_AUDIT.md` (P4-A/P4-B), `docs/GRAPH_STUDIO_PHASE4B_CLI_COMPATIBILITY.md`.

## What changed

| Item | Before | After |
|---|---|---|
| 11 validators `tools/validate_*.py` (chain plan, refresh plan, crossing candidates, crossing proofs, frontier road correlations, frontier road inventory, hierarchical plan, region connector inventory, region connector matrix, region connector refresh plan, runtime connectivity) | implementation at `tools/` | implementation unchanged at `tools/legacy_archive/connectivity/`; **wrapper** at the original path |
| 10 legacy schemas (all of the above except the refresh-plan validator, which never had one) | `schemas/<name>.schema.json` | `schemas/legacy_archive/connectivity/<name>.schema.json`, byte-identical, `$id` unchanged |

Moved with `git mv`, so file history follows the files.

## Wrapper contract

A wrapper contains no logic: it runs the archived file with `runpy.run_path(..., run_name="__main__")`. `sys.argv[0]` stays the wrapper path, so argparse usage text is unchanged; arguments, standard streams and exit codes pass through; `SystemExit` propagates. Wrappers resolve the archive relative to their own location, so they work from any working directory and from the installed layout.

## Evidence (all synthetic, run on this branch)

- Existing gates unchanged and passing against the wrappers: the byte-exact positive and invalid-schema checks for all 11 validators (`tests/test_historical_legacy_positive_fixtures.py`, stdout/stderr SHA-256 and exit codes), `tests/test_legacy_fixture_parity.py`, `tests/test_legacy_validator_dependency_audit.py`, `tests/test_historical_frontier_populated.py`.
- New `tests/test_legacy_validator_wrappers.py` (9 tests), with a baseline captured from the pre-archive tools (`tests/fixtures/legacy-cli-wrapper-golden/baseline.json`): `--help`, no-arguments and missing-input behaviour for each validator; archived bytes equal the original bytes; wrapper size and delegation; relative-path and repo-cwd invocation; the same checks in a temporary copy that mirrors the packaged `pipeline/tools` and `pipeline/schemas` layout; archived schemas byte-identical and absent from the old paths; the active pair-manifest schema and validator not archived.
- A missing-input run prints a machine-specific traceback, so that scenario is compared by exit code and final error line, not whole stderr.
- Full Python suite: 151 tests, OK (1 skipped).

## What is not proven

- External, manual, out-of-tree and other-device callers of the old paths remain **UNKNOWN** (P4-B6), not zero. Wrappers protect the validator CLIs; they cannot protect a reader of the old schema file paths.
- `devtools/verify_legacy_fixture_parity.py` compares a source script's hash with an installed one. Against an already-installed older package the hashes now differ by design.
- Installed AppImage and .deb behaviour, the `linux` packaging workflow, and the Legion GUI Legacy tab are P4-D acceptance items and have **not** been exercised here. The packaged-layout test is a simulation of the Tauri resource mapping, not a package build.
- Native F8 parity, exhaustive discovery, Android ingestion and publication are unaffected and remain NOT_VERIFIED / BLOCKED.

## Rollback

Revert the PR. No data, workspace, Android or published artifact is touched.
