# F8 crossing-only discovery and Android route acceptance — 2026-11-05

**Architecture remains unchanged:** Identify the **final original source-graph directed road edge**, find the same physical forward road/direction in the original receiver graph, prove original Valhalla A-last/B-first routing in each graph, retain one source-final connection record per genuine road/direction and all distinct physical receiver branches, then deliver a SHA-verified catalog to RoadPilot.

**Scope correction:** General native graph junction traversal, OSM way-ID changes, and unrelated road branches are NOT a stand-alone requirement for finishing F8. They are not evidence of missing cross-region crossings. This increment examines only **original source buffer-cut outbound car/motorcycle road edges with real directed geometry touching the paired receiving region's nominal core**, and only carries those through actual original A/B Valhalla route verification.

## 1. Reproducible original graph crossing inventory

Tools:
- `tools/audit_f8_actual_bilateral_crossings.py` — full-source-archive original outward directed cut candidate filter; SHA-pinned inputs; original Geofabrik receiving core intersection; **no names/way grouping or junction traversal**.
- `tools/reconcile_f8_only_real_outward_missing_crossings.py` — only candidate directed source GraphIds previously marked `NO_VALHALLA_VERIFIED_FORWARD_RECEIVING_ROAD`. Require existing original source A LAST TripLeg mode proof, actual native A source terminal in each mode, search every original receiving tile's actual directed shape, match physical forward continuation, verify original B FIRST TripLeg. The exact native B directed edge terminal may be used when an interior probe on a short B edge does not snap. Unverified modes, source continuations and other candidates remain unresolved.

Retained source archive cut rows: Italy→Austria 9,190 and Austria→Italy 11,296 all original directed observations. After original mode, road/not-shortcut, OUTWARD, and **actual receiving nominal-core geometry** filters:

| Direction | Outbound candidate road/direction GraphIds touching receiver core | Already exact matched on those cut GraphIds | Previously unresolved cut candidates |
|---|---:|---:|---:|
| Italy→Austria | 259 | 77 | 182 |
| Austria→Italy | 114 | 41 | 73 |
| **Total** | **373** | **118** | **255** |

**These are candidates; do not call the 255 unresolved GraphIds 255 known legitimate missing roads.** Only 106 of the 255 had the prior source A LAST proof but lacked exact receiving B FIRST; 25 of those are additionally independently verified by this increment (17 forward, 8 reverse). Changed native turns, source edges without original A-last proof and failed original receiver routes remain explicit unresolved evidence, not false claims or extra data.

## 2. Verified result and original evidence

Full original source+receiving-graph evidence: **247** distinct verified source-final directed GraphIds and **278** separately verified original receiver-directed options, from the existing 222/253 plus 25/25. Source IDs: 156 Italy→Austria, 91 Austria→Italy. B options: **169 forward**, **109 reverse**, both CAR and MOTORCYCLE where original source and receiver route proofs passed.

Reproducible immutable evidence from portable original files:
- Crossing-only inventory: `~/RoadPilotGraphStudio/diagnostics/f8-production/20261105/f8-actual-bilateral-outward-crossings-portable-v2.json`, SHA256 `6313d42fa1d6490b841de3b2e43dd3e554308df049f99e34939b505cbdb7ad5c`.
- Exact original A-LAST and B-FIRST targeted correlation ledger: `~/RoadPilotGraphStudio/diagnostics/f8-production/20261105/f8-bilateral-crossing-targeted-portable-v16.json`, SHA256 `647cc2027c8e7266128b208d34f861ce59162f43cfd4eb71ba01842241950533`.
- Derived **verified-only, test-only** RoadPilot Android cache: `~/RoadPilotGraphStudio/diagnostics/f8-production/20261105/f8-bilateral-crossing-portable-android-v17.json`, SHA256 `c2225f447c0c3de093eed66ed1d70805efa01dcafb612f546053ad2b57ed6e17`, about 2.76 MB.

Every result is **partial**; no producer may set `sourceDiscoveryComplete=true` or `productionPublication=READY` based on these counts. No original tiles, Android release, or graph data were changed.

## 3. Android production F8 acceptance: two distinctly separate gates

Device: Legion's Android Studio emulator, ARM64 native library translation with the *original* Italy NE and Austria Valhalla regional tiles installed.

**Gate A — exact JNI route + full chain planner with precomputed catalog, live discovery isolated:** PASS. For the 247/278 catalog, Android ingested **169 Italy→Austria and 109 Austria→Italy** receiver options, routed **4/4 exact original native GraphId two-leg car/motorcycle journeys**, and invoked the **real `FrontierMultiRegionChainPlanner`** on the verified 364870918424→229076132120 source/receiver pair. The planner returned a full **Italy→Austria CAR A→X→B** journey with two legs, one handoff, exact directed A-LAST/B-FIRST, approximately **0.902m** seam, and approximately **119.96 km** total. That test uses `F8_RUN_FULL_PLANNER=catalog` to isolate route planning from live discovery. It does NOT prove unrestricted runtime discovery or every route.

**Gate B — unrestricted device `ManagedFrontierChainRoutingRuntime.plan` including live discovery:** FAIL/NOT_ACCEPTED. Even using the earlier 222/253 catalog, the first full Android runtime journey exceeded its explicit **90,000ms** acceptance timeout; source evidence is `~/RoadPilotGraphStudio/diagnostics/f8-production/20261105/full-F8-android-production-planner-failed-evidence-v1.json`, SHA256 `216843f269dd2659eec9328c541d3eb3c4ede5d810fe9cfff7a331bb00bb7d25`. All four JNI exact two-leg journeys in that run passed; the timeout is therefore **in the full runtime/discovery path**, not proof of a bad crossing.

The exact SHA-bound replay of Gate A for `v17` passed on the Android emulator. Device evidence:
`~/RoadPilotGraphStudio/diagnostics/f8-production/20261105/f8-final-edge-android-emulator-route-v5-1793862184382.json`, SHA-256 `4c076d8193351b6d2a67a23b9d64319a516cbb6b51e835e3d3bdbb355ca19aba`.
The companion RoadPilot PR #542 contains the instrumentation and reproducible runner. Full physical-device acceptance remains NOT RUN.

## 4. Next action

**Do not return to general graph-continuation traversal.** For the specifically relevant candidate roads still lacking proof, classify actual A-last / B-first route failures and repair only recoverable real crossing omissions. Separately isolate and fix the **full F8 runtime discovery latency** on Android while preserving discovery of genuinely different crossing roads/branches. Rerun actual unrestricted Android F8 planner plus physical-device acceptance before any release.

Both PRs remain draft, unmerged; publication BLOCKED and fallback discovery stays enabled.
