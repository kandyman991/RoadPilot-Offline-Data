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
## D-005 — One-click routing setup with graph-backed validation (2026-10-13)

PR #62 adopts the user workflow *Geofabrik selection → automatic configuration → build → Valhalla proof*. Manual GPS coordinates must not be a prerequisite to start region creation. A new routing-only config can use `routing.validationMode=auto` with zero manually supplied routes; it is **not** considered validated until the freshly built graph returns a routed line crossing the nominal Geofabrik polygon boundary. The routing manifest/pack remains unpublished on proof failure. Keep the decoded road geometry checks; do not turn mere polygon-normal samples into accepted routes. Allow optional map pins for manual start/end placement and retain existing user-authored region configs. Routing, visual and search artifacts remain separate.

Source: https://github.com/kandyman991/RoadPilot-Offline-Data/pull/62 (merged, CI verified; full regional device build still to be tested).
