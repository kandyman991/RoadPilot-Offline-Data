# F8 terminal-edge handoff model (D-017)

Status: documented design, **equivalence NOT_RUN**, no implementation change.

## Model
Consider a road connecting Italy and Austria.

1. The Italian graph extends roughly 25 km into Austria.
2. The Austrian graph contains the same physical road within that overlap.
3. Graph Studio identifies the final suitable directed edge of the road in the overlapping area.
4. That edge has an exact corresponding road connection in the Austrian graph.
5. RoadPilot routes to that point using the Italian graph and continues using the Austrian graph.

Each leg is proven by Valhalla. F8 on Android remains the correctness fallback. All valid alternatives are kept (carriageways, ramps, both directions, separate locations on one named road, multi-hop chains).

## Why the old wording was wrong
The documented scan kept every directed edge of the overlap (323,372 Italy / 334,973 Austria edges on the Italy-NE / Austria pair). Almost all are interior edges that cannot be a handoff, because both graphs continue past them. That scope is inherited from the retired buffered-overlap sampler (D-014).

## Measurement (read-only, 2026-11-03)
Definition: an edge that dead-ends in its own graph where the other graph has a non-dead-end directed edge ending within about 8 m.

| | Italy-NE | Austria |
|---|---|---|
| Scan edges | 323,372 | 334,973 |
| Dead-end edges queried | 21,631 | 22,546 |
| Clip termini (neighbour continues) | 871 | 788 |
| Road class 0-2 | 25 | 15 |
| Class 6-7 | 743 | 688 |
| End within 100 m of own outline | 85 | 32 |
| End 25 km or more inside own outline | 287 | 395 |

Graphs were extracted with osmium `complete_ways`; a road's last edge can therefore lie at or beyond the nominal outline. The rule is "where the graph's network ends".

## Open gates
- Equivalence with the Android F8 graph-edge results on the same exact graph versions (contract A2, B4): NOT_RUN.
- Unmatched ~2.5% of edges; border-weaving roads; parallel carriageways; the 8 m tolerance; neighbour coverage beyond the outline: UNVERIFIED.
- Proof workload (previously 1,316,690 cells, about 22 h single worker) must be re-estimated from the terminal set.
- Android JNI 512-edge cap and road-key reduction: re-evaluate once terminal sets are the scan target.
- Issue #82 wording to be updated on the issue itself after owner confirmation.
