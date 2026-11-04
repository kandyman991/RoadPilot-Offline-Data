# F8 direct original final-edge connections — implementation

2026-11-04. The owner discarded PR #124's archive research. It was **closed unmerged**. This branch implements the actual F8 requirement: ORIGINAL source final directed road edge → corresponding forward ORIGINAL receiver directed road → Valhalla first/last edge proofs → one connection record per source road/direction (distinct branches retained).

## What now runs

`tools/build_f8_final_edge_connections.py` operates against the two unmodified SHA-pinned October 13 Valhalla 3.6.3 original graph archives and their original native directional edge scans. It uses each already identified source final edge's **original A last TripLeg ID**, checks the true geometry of each plausible receiving B directed edge for forward physical continuation (rejects a reversal on the same physical road), and routes from the handoff to a point ahead in B to confirm the **actual original B first TripLeg directed GraphId**, including Car and Motorcycle modes.

There is no matching on OSM way/name, identical numeric GraphIds across independent regions, or first-success truncation. The JSON has exactly one record per source original final directed GraphId and preserves separately verified receiving branches under `receiverOptions`. Each mode is attached to that directed option, not a duplicate connection. Unknown, reverse-only, inaccessible or ambiguous candidates are retained in `unresolvedSourceFinalEdges` and **never published as verified**. Exact original graph and native executable SHA-256s are checked.

## Live original graph results

| Direction | Source final candidates inspected | Source records with genuine forward B TripLeg | Independently verified receiving B options | Explicitly unresolved |
|---|---:|---:|---:|---:|
| Italy Nord-Est → Austria | 210 | 86 | 90 | 124 |
| Austria → Italy Nord-Est | 90 | 49 | 61 | 41 |
| **Total** | **300** | **135** | **151** | **165** |

Immutable source catalog: `~/RoadPilotGraphStudio/diagnostics/f8-production/20261104/direct-final-edge-connections-v1.json`, SHA-256 `ed6ccf266627f66d2f5a7c62ae8b73e902a8c1a87c1d7b01f41404b35cc0c23e`.

Actual two-region A→X→B local Valhalla journeys using core coordinates near Brenner: 80 tested (40 in each direction, Car and Motorcycle); **20** had exact source LAST GraphId and receiving FIRST GraphId, successful full regional legs and **0m** seam-gap. A sample that routes by another road is not evidence that a separately verified handoff is invalid. Report: `direct-final-A-X-B-core-journey-test-v1.json`, SHA-256 `bbaacc49d99f769369c32c9318e25a7d78a788e0863b167679b0057286de5041`.

## Android consumption

RoadPilot Android source is maintained separately in `kandyman991/SmartRide-Next`. The Graph Studio JSON is read in the application only if both exact **original graph archive SHA-256s** match the installed graph metadata. RoadPilot's historical metadata-derived `graphFingerprint` is NOT equivalent to the original tiles.tar SHA. The Android dynamic Geofabrik region ID also need not equal the Graph Studio routing region ID. The partial catalog must be combined with ordinary F8 discovery, never replace it and freeze undiscovered alternatives. The consumer is tested independently in Android.

This intermediate result is **NOT the complete per-physical-road source census**. The 300 source finals are those already found in previous real native evidence; 165 remain unresolved, and other relevant final roads may exist outside that set. No Android production sidecar, original .gph modifications or release is authorized. Complete road/direction coverage, further hard turning branches and on-device full journey routing are subsequent acceptance gates.