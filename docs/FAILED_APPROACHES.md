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

