# Rejected / Unsafe Approaches — RoadPilot Graph Studio / Offline Data

These are engineering guardrails, **not claims that all were experimentally tested**. Add confirmed failures with exact reproduction, links, observed results and reconsideration criteria. Do not confuse a historical proposal with validated implementation.

## Guardrail 1

Rejoining separately built .gph files by copying raw graph IDs/tiles is not a production seam fix.

Reconsider only with an explicit new hypothesis, tests and evidence; record the superseding decision.

## Guardrail 2

A crossing chosen only from name, heading or proximity is not VALID until proven by normal Valhalla routing.

Reconsider only with an explicit new hypothesis, tests and evidence; record the superseding decision.

## Guardrail 3

Do not restore region-specific hard-coded motorway/portal fixes or duplicate Android runtime logic in the builder.

Reconsider only with an explicit new hypothesis, tests and evidence; record the superseding decision.

## Guardrail 4

Do not claim a stale handoff's named milestone is still active without checking live code, PRs and CI.

Reconsider only with an explicit new hypothesis, tests and evidence; record the superseding decision.


## Confirmed failure — overlapping Geofabrik inputs treated as a single normal OSM snapshot (2026-10-13)

Observed: Austria configured with 18 intersecting extracts, including Austria, DACH, Alps and neighboring leaves; `osmium merge` succeeded but `osmium extract` failed with `Node ID twice in input`. Mixed snapshot versions can remain after `osmium merge` even when identical versions deduplicate. Do not call `osmium sort` a fix: Osmium sort explicitly does **not** remove duplicate objects, and it has high memory requirements.

Fix in PR #64: select geographically necessary sources using exact polygon coverage; normalize merged versions with streaming `osmium time-filter` before extracting a normal current snapshot; keep reference validation and graph-backed border proof. CI validated the former failure and corrected behavior with actual Osmium on synthetic mixed-version fixtures. User's full Austria build still needs repeat testing.

Source: https://github.com/kandyman991/RoadPilot-Offline-Data/pull/64
