## Architectural impact (required for protected routing changes)

Architecture decision: PRESERVES
Contract clauses: A1, A2, B1, B2, B3, B4, C1, C2, C3, D1, D2, F
F8 reference inspected: app/src/main/java/com/kandyman991/smartridenext/routing/FrontierRouteLocalRecovery.kt
Discovery coverage: NOT_VERIFIED
Device validation: NOT_RUN
Evidence: https://github.com/kandyman991/RoadPilot-Offline-Data/issues/73
Known gaps: https://github.com/kandyman991/RoadPilot-Offline-Data/issues/73

Explain what changes, which implementation actually runs, and what is NOT yet proven. Keep only relevant clauses. If altering the accepted architecture, STOP: change Architecture decision to CHANGE_REQUESTED, link an explicit owner-approved superseding decision in docs/ENGINEERING_DECISIONS.md and identify the approval issue/PR. No change proceeds based on convenience alone.

## F8 invariants checklist (complete these for protected routing changes)

- [ ] F8 remains the Android runtime foundation; Graph Studio producer uses boundary final edges only
- [ ] First successful or cached crossing never hides alternative crossings
- [ ] Same physical road and direction are matched from native compiled graph geometry/topology
- [ ] One original source final GraphId per physical road/direction with modes and distinct branches
- [ ] Exact graph/buffer fingerprints and incomplete/ambiguous scope are retained honestly
- [ ] No producer all-tile directed census or per-connection Valhalla route proof
- [ ] Actual cross-region Android journeys are required before production release

## Verification / route evidence

Explain test names and observed results, exact commit/graph versions if known, missing acceptance coverage, and any fallback. Do not confuse a successful build with actual F8 parity or Android consumption.

## Other changes

For PRs that do not touch protected routing/architecture files, remove the architecture impact and checklist if irrelevant. The automatic gate only requires these when its protected file patterns change.
