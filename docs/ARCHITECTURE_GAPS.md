# Open architecture gaps — not yet proven compliant

These explicitly declared legacy gaps make the contract honest while safeguards are introduced. They are NOT acceptance or approval to make the same mistake again.

| Gap | Present evidence | Required closure | Tracking |
| --- | --- | --- | --- |
| G-F8-01 — Discovery source parity | Graph Studio now includes the PR #75 buffer-overlap OSM seeds from BOTH retained regional inputs (merged at `b0d60d0`), as well as nominal-border seeds. The precomputed OSM candidates are still NOT demonstrated equivalent to the actual Android F8 directed graph-edge scanner. | On identical physical Valhalla graphs, enumerate F8 graph-edge results, compare all candidates, resolve or flag gaps, retain provenance. | https://github.com/kandyman991/RoadPilot-Offline-Data/issues/73 |
| G-F8-02 — Premature route alternative stopping | Multi-region planner currently caps to 20 chains, 64 legs, about 120 seconds and may return a first complete same-graph route. No proof that bound excludes only inferior routes. | Whole-journey alternative comparison with sound pruning, or unambiguously mark route search INCOMPLETE and retain F8 fallback. | https://github.com/kandyman991/RoadPilot-Offline-Data/issues/73 |
| G-F8-03 — Device consumption | Graph Studio sidecars have not been proven installed and used in RoadPilot Android. | Fingerprint verified package ingestion and route equivalence in real Italy/Austria/Germany device tests, with rollback and F8 fallback. | https://github.com/kandyman991/SmartRide-Next/issues/512 |

**Promotion policy:** only close a row with direct tests and evidence linked to the actual graph versions/commit SHA. Passing synthetic CI alone never verifies F8 graph-edge parity or real-device success.
