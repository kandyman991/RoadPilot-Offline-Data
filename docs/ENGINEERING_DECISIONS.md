# Engineering Decisions — RoadPilot Graph Studio / Offline Data

Durable design intent. This is not evidence that each item is implemented and merged. Supersede decisions with dates and links rather than deleting their history.

## D-001 — Independent routing/visual/search artifacts

Version and validate each region's Valhalla routing, visual-map and SQLite search packs separately; never force unrelated rebuilds.

Source: `CHAT_HANDOFF.md` / repository roadmap and architecture (reverify against live implementation).

## D-002 — Valhalla graph identity and crossings

Never mutate raw .gph to repair seams; RoadPilot-owned transitions require directional, mode and exact fingerprint compatibility backed by Valhalla leg proof.

Source: `CHAT_HANDOFF.md` / repository roadmap and architecture (reverify against live implementation).

## D-003 — Graph Studio owns the production pipeline

Android consumes verified packages; Graph Studio builds/inspects connectivity and artifact manifests. F8 is the runtime correctness fallback.

Source: `CHAT_HANDOFF.md` / repository roadmap and architecture (reverify against live implementation).

## D-004 — Publication is explicit

Distinguish implemented R2 publisher functions from credentials, configured destinations, or a successfully published production release; verify live config before claiming any live distribution.

Source: `CHAT_HANDOFF.md` / repository roadmap and architecture (reverify against live implementation).

## D-900 — Cross-chat continuity (2026-10-10)

Keep `CHAT_HANDOFF.md` as the curated next-action source; use GitHub live state for actual PR/CI status and a generated `handoff/state.json` only as a hint. Record decisions and failed experiments explicitly.