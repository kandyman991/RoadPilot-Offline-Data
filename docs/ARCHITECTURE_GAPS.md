# Open architecture gaps — not yet proven compliant

These explicitly declared legacy gaps make the contract honest while safeguards are introduced. They are NOT acceptance or approval to make the same mistake again.

| Gap | Present evidence | Required closure | Tracking |
| --- | --- | --- | --- |
| G-F8-01 — Discovery source parity | The older OSM buffered-overlap/correlation producer is retired from Graph Studio (cleanup pending merge); its historical outputs are NOT equivalent to actual Android F8 directed graph-edge discovery. The uncapped native graph scanner remains an independent port, not Android reference proof. | On identical physical Valhalla graphs, enumerate F8 graph-edge results, compare all candidates, resolve or flag gaps, retain provenance. | https://github.com/kandyman991/RoadPilot-Offline-Data/issues/73 |
| G-F8-02 — Premature route alternative stopping | The obsolete bounded multi-region planner is retired from Graph Studio (pending cleanup merge); whole-journey multi-hop ranking still needs a new F8-compliant implementation. Previous capped-search success did not prove an optimal result. | Whole-journey alternative comparison with sound pruning, or unambiguously mark route search INCOMPLETE and retain F8 fallback. | https://github.com/kandyman991/RoadPilot-Offline-Data/issues/73 |
| G-F8-03 — Device consumption | Graph Studio sidecars have not been proven installed and used in RoadPilot Android. | Fingerprint verified package ingestion and route equivalence in real Italy/Austria/Germany device tests, with rollback and F8 fallback. | https://github.com/kandyman991/SmartRide-Next/issues/512 |

**Promotion policy:** only close a row with direct tests and evidence linked to the actual graph versions/commit SHA. Passing synthetic CI alone never verifies F8 graph-edge parity or real-device success.
