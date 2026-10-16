# RoadPilot Graph Studio / Offline Data — repository agent instructions

## Resumption
1. Read `CHAT_HANDOFF.md` and `AGENTS.md`, plus `ROADMAP.md` when present.
2. Read relevant decisions in `docs/ENGINEERING_DECISIONS.md` and known bad approaches in `docs/FAILED_APPROACHES.md`.
3. Inspect `handoff/state.json` as a **possibly stale snapshot** only. Verify current main SHA, branches, open PRs, issues, CI and releases on GitHub before any change.
4. Distinguish planned, merged, CI-tested and device/desktop-tested features. Read code and tests when documents disagree.
5. Resume the curated **next exact action** only after checking current live evidence.

## Binding architecture contract and stop rule
- Before touching discovery, routing, connector matrices, caching, publication or Android ingestion, **read docs/ARCHITECTURE_CONTRACT.md and docs/ARCHITECTURE_GAPS.md**. The working F8 scanner is the behavioral reference, not just a source of inspiration.
- Preserve **all useful crossing alternatives**. Successful/learned first handoff is never permission to stop discovery. Never claim fully discovered or optimal results from capped scans without proof; mark real F8 graph-edge parity NOT_VERIFIED until the required Legion comparison passes.
- A narrower OSM-only/frontier-only substitute is NOT automatically equivalent to F8 graph-edge discovery, however many generated candidates pass Valhalla.
- Every protected PR must satisfy the checklist in .github/pull_request_template.md and the architecture-contract CI job with functional regressions and explicit known-gap evidence.
- **STOP before implementing any deviation** from an accepted clause. Explain the conflict to the user and obtain explicit approval recorded as a superseding decision; do not silently change this contract. No CI success can replace real graph-edge parity or device evidence.
- Contract changes need a project-owner review under .github/CODEOWNERS, plus GitHub branch rulesets with architecture-contract as a required check.
- Historical PR #75 merged but was superseded by the native-F8 retirement cleanup; do not restore its OSM-only generator or claim issue #73 complete on synthetic CI alone.

## Native F8 cleanup checkpoint (2026-10-16)
- The OSM buffered-overlap frontier producer, legacy correlated crossing / proof / matrix pipeline and old multi-region planner are retired from executable Graph Studio paths. Do not call, recreate, or restore them to "fix" missing F8 handoffs. Git history preserves the code if forensic review is needed.
- The independent read-only native GraphReader scanner remains the entry foundation; use the identity-only `--pair-manifest` path, not legacy `correlations.json`. Actual native Android F8 scan parity remains NOT_VERIFIED, and production sidecar publication stays disabled until all proof tiers pass.
- The Border Inspector may still read historical artifacts. Those are NOT current F8-complete connections. Do not invalidate/delete installed graph packages or old local scan evidence as part of source-code cleanup.

## Project-specific guardrails
- Version and validate each region's Valhalla routing, visual-map and SQLite search packs separately; never force unrelated rebuilds.
- Never mutate raw .gph to repair seams; RoadPilot-owned transitions require directional, mode and exact fingerprint compatibility backed by Valhalla leg proof.
- Android consumes verified packages; Graph Studio builds/inspects connectivity and artifact manifests. F8 is the runtime correctness fallback.
- Distinguish implemented R2 publisher functions from credentials, configured destinations, or a successfully published production release; verify live config before claiming any live distribution.
- Maintain project boundaries: RoadPilot Android code and Graph Studio production artifacts have separate ownership.
- Avoid unnecessary expensive builds, CI cloud resources, and GitHub Actions artifact uploads. Use `[skip ci]` for documentation-only commits when appropriate.
- Never commit credentials, local paths with secrets, private chats, passwords or signing keys.

## After a PR or milestone
Update `CHAT_HANDOFF.md` (what changed, verified SHA/PR/CI, test evidence and next exact step) and add/supersede material decisions or failed tests in the registers. The automated GitHub state snapshot **cannot** recover chat-only engineering decisions. See `docs/CONTINUITY_PLAYBOOK.md`.

**Resume:** “Resume RoadPilot Graph Studio / Offline Data” means read these records and verify GitHub. It does not authorize bypassing review, tests or device validation.
