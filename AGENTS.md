# RoadPilot Graph Studio / Offline Data — repository agent instructions

## Resumption
1. Read `CHAT_HANDOFF.md` and `AGENTS.md`, plus `ROADMAP.md` when present.
2. Read relevant decisions in `docs/ENGINEERING_DECISIONS.md` and known bad approaches in `docs/FAILED_APPROACHES.md`.
3. Inspect `handoff/state.json` as a **possibly stale snapshot** only. Verify current main SHA, branches, open PRs, issues, CI and releases on GitHub before any change.
4. Distinguish planned, merged, CI-tested and device/desktop-tested features. Read code and tests when documents disagree.
5. Resume the curated **next exact action** only after checking current live evidence.

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
