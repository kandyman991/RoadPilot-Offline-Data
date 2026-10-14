# ChatGPT continuity workflow — RoadPilot Graph Studio / Offline Data

**At start:** Read `AGENTS.md`, `CHAT_HANDOFF.md`, relevant decision/failure notes and `ROADMAP.md` if present. Verify live GitHub head, open PRs, CI and released artifacts. Treat `handoff/state.json` as historical until independently checked.

**At milestone/PR finish:** Capture the issue/PR, changed SHA, tests/run URLs, what is actually merged, platform/device proof, failed hypotheses and one exact next action in `CHAT_HANDOFF.md`. Record any new durable decision or rejected experiment without erasing old evidence.

**Across repos:** For graph/package/runtime interface work check both `kandyman991/SmartRide-Next` and `kandyman991/RoadPilot-Offline-Data`. Avoid propagating experimental ideas as validated implementation.

**Resources:** Do not launch expensive work for docs-only changes; `[skip ci]` avoids workflows but may leave generated Git snapshots out of date. Never rely on GitHub Actions artifact storage. Keep secrets out of markdown.

**Limit:** ChatGPT does not automatically copy every chat into Git. Important decisions must be written explicitly in the repo during a development session.

## Architecture drift prevention

Before implementing routing/discovery work, re-read docs/ARCHITECTURE_CONTRACT.md, review the current open gaps in docs/ARCHITECTURE_GAPS.md, identify the F8 source of truth, and include contract clause IDs in the PR. When implementation direction differs, stop and request user approval, do not replace the proven algorithm for ease of delivery. Run tests/test_f8_architecture_regressions.py locally or in CI. Set/check the required branch-ruleset status architecture-contract; CODEOWNERS alone does not require approval without a repository ruleset.
