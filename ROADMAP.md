# RoadPilot Offline Data & Graph Studio Roadmap

_Last updated: 2026-10-06_

This is the canonical working roadmap for the RoadPilot offline-data pipeline and Graph Studio. It records the target architecture, what is already implemented, what is active, and what should be built next.

## Target architecture

~~~
Geofabrik / Overture source data
            |
            v
     RoadPilot Graph Studio
            |
    +-------+--------+
    |       |        |
    v       v        v
 Routing  Visual   Search
 Valhalla PMTiles  SQLite
 graph    map      POI DB
    |       |        |
    +-------+--------+
            |
       validate
       version
       checksum
            |
            v
      Cloudflare R2
            |
            v
       RoadPilot users
   download/update regions
       independently
~~~

Core rule: regional artifacts are independent. Rebuilding Austria must not force Italy Nord-Est, Oberbayern, or Schwaben to be rebuilt or re-downloaded unless their own data changed.

Each region is intended to expose independently versioned routing, visual, and search artifacts. Cross-region compatibility belongs in RoadPilot-owned metadata/override layers, not by modifying Valhalla graph files or requiring all regions to share one synchronized world build.

## Status summary

| Phase | GitHub | Status | Result |
|---|---|---|---|
| Independent routing-pack foundation | #7 | Done foundation | Regional Valhalla build/validate/package workflow |
| Hosted routing preflight | #8 | Done | GitHub-hosted CI validates tooling/config/discovery |
| Installable Graph Studio | #9 | Done | Linux Tauri app, AppImage + Debian packaging |
| Region editor + Geofabrik discovery | #10 / PR #18 | Merged | Region creation/editing, buffer preview, automatic source discovery |
| Standard Valhalla route planner | #12 / PR #19 | Merged | Normal routing, costing controls, route geometry, maneuvers, search expansion |
| Border inspector + manual crossings | #11 / PRs #20-#23 | Merged | A/B road diff, manual/automatic/learned handoffs, validation, stale detection, diagnostics export |
| Exact graph/boundary diffing | #13 / PRs #24-#25 | Merged | Deterministic graph/boundary fingerprints plus retained-build road-level diffing |
| Build-time cross-region connectivity | #26 | Complete | Fingerprint-bound pair manifests, discovery/proof/runtime pipeline, multi-hop composition, F8 fallback |
| Regional connector matrices | #35 | Complete | Exact graph-bound entry→exit matrices, sparse hierarchical ranking, Graph Studio inspection and lifecycle refresh |
| Cloudflare R2 publication manager | #14 | Active | Safe immutable release contract, R2 publication, latest/history/rollback in Graph Studio |
| Visual map production/inspection | #16 | Planned | Lightweight RoadPilot offline vector-map artifact |
| POI/search production/inspection | #17 | Planned | Overture/SQLite offline search artifact |
| Scheduled updates + retention | #15 | Later | Rebuild only changed regions and retain prior versions |

## Completed

### Independent regional routing packs

RoadPilot uses independently built regional Valhalla graphs rather than a monolithic phone-side world graph.

~~~
Geofabrik regional PBF
        ↓
Graph Studio / build tooling
        ↓
regional Valhalla graph
with usable border coverage
        ↓
validation
        ↓
version + SHA-256 + manifest
        ↓
distribution
~~~

Regional versions are independent.

### Graph Studio workstation

Graph Studio is installable on Linux and is intended to become the complete RoadPilot map-production workstation.

Current capabilities include local build workspace, build queue/cancellation, toolchain checks, graph rendering/inspection, build history/comparison foundation, Linux AppImage and Debian packaging, and hosted CI validation.

### Region editor and automatic Geofabrik discovery

Merged in PR #18.

Implemented:
- create new RoadPilot regions;
- edit existing regional definitions;
- choose exact Geofabrik leaf extracts;
- configure border-buffer distance;
- display nominal and buffered coverage;
- automatically discover neighboring Geofabrik extracts intersecting the buffer;
- validate before save;
- keep editable configs in the Graph Studio workspace;
- live hosted smoke-test against the current Geofabrik catalog.

### Standard Valhalla route planner

Merged in PR #19.

Implemented:
- select a built regional graph;
- click start/end points or enter exact coordinates;
- motorcycle, auto, bicycle and pedestrian costing;
- highway/toll/ferry preference controls for RoadPilot-relevant vehicle costing;
- standard Valhalla route calculation;
- route geometry, distance, duration and maneuvers;
- route calculation timing;
- optional native Valhalla route-search expansion overlay;
- expansion edge count/timing.

This gives us a clean diagnostic baseline:

~~~
standard Valhalla succeeds/fails
             ↓
then inspect RoadPilot cross-region behavior
~~~

## Completed — Border Inspector (#11)

Issue #11 is complete across PRs #20-#23.

Implemented:
- independent Graph A/B overlays;
- manual two-sided crossing selection and strict Valhalla validation;
- common/A-only/B-only road comparison using stable OSM-way identity;
- automatic candidate, accepted/bound, learned F8 and manual handoff overlays;
- graph-fingerprint stale detection;
- JSON + Markdown diagnostics export.

## Completed — Exact graph and boundary diffing (#13)

Issue #13 is complete across PRs #24-#25.

Implemented:
- deterministic per-`.gph` tile hashes and graph-tile fingerprint;
- internal-only fingerprint;
- conservative per-neighbor boundary/overlap fingerprints;
- per-neighbor REFRESH/UNCHANGED decisions;
- retained Build A/B graph loading through Valhalla;
- added/removed/changed/unchanged boundary-road classification using stable OSM identity, canonicalized geometry and supported road/access attributes;
- changed boundary-tile and changed-road map visualization;
- graph-local edge ids are not treated as durable cross-build identity.

## Completed — Build-time cross-region connectivity metadata (#26)

Issue #26 is complete across PRs #27-#34. PR #27 established the fingerprint-bound region-pair
contract and the later milestones carry that stable physical identity through Valhalla proof,
runtime metadata, multi-hop composition, route-style ranking, surgical refresh and Graph Studio inspection.

The architecture separates expensive stable physical discovery from optional exact graph-local
bindings. Internal-only graph rebuilds can therefore retain physical connectivity evidence when
the relevant boundary is unchanged, while graph-local bindings can be regenerated cheaply.

### Delivery milestones

This removes expensive first-route F8 discovery from phones wherever current validated metadata exists.

Milestones:
- fingerprint-bound region-pair manifest and validator — merged in PR #27;
- stable OSM frontier-road inventory using real geometry and no graph-local ids — merged in PR #28;
- independent Graph A/B Valhalla correlation of stable anchors — merged in PR #29;
  - all usable locate candidates retained;
  - same-OSM-way identity is ranking evidence, not a hard filter;
  - A/B coordinates may differ;
  - OSM frontier heading is evidence only, never inferred journey direction.
- physical crossing candidate generation — merged in PR #30;
  - retain the complete Graph A × Graph B candidate product per frontier road;
  - rank by evidence only; never filter by heading/access/direction here;
  - emit explicit `UNPROVEN` state until Valhalla route proof;
- plain-Valhalla motorcycle/auto direction proofs — merged in PR #31;
  - prove each graph's local approach/exit leg independently; never route A-snap→B-snap inside both graphs;
  - prove A→B and B→A independently for motorcycle and auto;
  - require successful route geometry to trace back onto the exact candidate DirectedEdge graphId;
  - route proof overrides pre-proof heading/access metadata; those remain diagnostics only;
- compact validated connectivity artifact for RoadPilot — merged in PR #32;
  - promote only PROVEN candidates;
  - copy only actually supported mode/direction capabilities;
  - bind exact A/B anchors to graph + boundary fingerprints;
  - omit rejected/inconclusive diagnostics and pre-proof access guesses;
- multi-hop region-chain composition — merged in PR #33;
  - compose only validated neighboring-pair runtime artifacts;
  - enforce exact intermediate-region graph identity;
  - use proven mode/direction support as directed adjacency;
  - preserve all crossing alternatives per hop without Cartesian expansion;
- final connectivity lifecycle completion — merged in PR #34;
  - rank crossing alternatives and complete simple region chains for FASTER/SHORTER using only post-proof Valhalla distance/time metrics;
  - classify connectivity CURRENT/STALE against exact graph and relevant boundary fingerprints;
  - graph-only change → REBIND_GRAPH while preserving stable physical discovery;
  - relevant boundary change → REDISCOVER_BOUNDARY only for the affected neighboring pair;
  - expose generated UNPROVEN candidates and VALIDATED runtime crossings in Graph Studio with CURRENT/STALE state.

Runtime target:

~~~
origin region
    ↓
precomputed connectivity layer
    ↓
validated region chain
    ↓
local Valhalla detailed routing
~~~

F8 remains the fallback when metadata is missing, stale or ambiguous.

## Next

### 1. Regional connector matrices (#35)

Add a sparse hierarchical routing layer on top of completed #26 connectivity.

Milestones:
- M1 — deterministic graph-bound connector anchor inventories — merged in PR #36;
- M2 — Motorcycle/Car entry→exit Valhalla matrices with exact start/end DirectedEdge proof — merged in PR #37;
- M3 — matrix-backed sparse hierarchical chain composition — merged in PR #38;
- M4 — Graph Studio matrix/topology/freshness inspection and final lifecycle integration — active.

M3 rules:
- cross-border edges come only from VALIDATED #26 runtime connectivity;
- intermediate-region edges come only from `REACHABLE` exact-edge matrix cells;
- `UNREACHABLE` and `INCONCLUSIVE` matrix cells are never assigned heuristic penalties;
- border proof probe distance/time is not treated as journey cost;
- FASTER/SHORTER score only proven traversal through intermediate regions at build time;
- score scope is explicit: actual origin→first-exit and last-entry→destination legs remain query-time Valhalla work;
- retain multiple sparse candidate chains for detailed Valhalla final selection;
- missing/stale matrices mean the precomputed chain is unavailable; F8 remains fallback.

Do not reintroduce fixed seams, F6, hard heading/separation filters, or graph-local ids as cross-build identity.
### 2. Cloudflare R2 publication manager (#14)

Publish validated region artifacts with immutable history and a small mutable latest pointer.

Milestones:
- M1 — credential-free publication contract and local object-store safety proof — merged in PR #40;
- M2 — R2 credential configuration/test plus plan-backed S3-compatible upload/verification — merged in PR #41;
- M3 — Graph Studio local-vs-published status, progress, history and rollback — active.

M1 contract:
- validate the routing pack before a publication plan can exist;
- publish immutable payload objects under artifact-kind / region / version keys;
- include graph index when the routing manifest contains it;
- create immutable `release.json` only after payload objects are confirmed;
- advance mutable `latest.json` only after the release is confirmed;
- exact retries are idempotent;
- same immutable key with different bytes is refused;
- failed/partial publication never changes `latest.json`;
- rollback moves only `latest.json` to an existing confirmed release and never deletes historical versions.

The contract is provider-independent so the same safety rules can be tested locally before real R2 credentials are configured.

M2 adds:
- environment-only R2 credentials: account ID, access key, secret key and bucket;
- a non-mutating credential/connection test;
- publication-plan-backed R2 upload;
- upload progress events for Graph Studio;
- post-upload HEAD verification of object size and SHA-256 metadata;
- conditional immutable release creation;
- conditional latest-pointer update so concurrent publishers cannot silently clobber each other;
- remote immutable release listing;
- verified deletion-free latest-pointer rollback;
- the legacy direct routing publisher now delegates to the publication-plan path.

M3 integrates the publisher into Graph Studio:
- private local credential storage outside the repository with Unix mode 0600;
- only masked credential status is exposed to the frontend;
- non-mutating credential test from the UI;
- retained local-build selection and local-versus-latest comparison;
- asynchronous publication with per-object progress;
- remote immutable release history;
- verified latest-pointer rollback controls.

Cloudflare R2 is not connected to a real bucket yet; live credentials have not been supplied or tested.
## Additional artifact pipelines

### Visual map layer (#16)

Produce the exact lightweight offline visual map RoadPilot users will receive.

Target content:
- motorways;
- primary/secondary/local roads;
- road names and route numbers;
- cities/towns/villages;
- water;
- major boundaries;
- useful mountain/pass/terrain labels.

A visual-map update must not force a routing-graph update.

Graph Studio should allow online-reference vs RoadPilot-offline-map comparison plus overlays with Valhalla edges, routes and handoffs.

### POI/search database (#17)

Integrate the existing RoadPilot Overture/SQLite search pipeline into Graph Studio.

Planned inspection includes:
- exact and partial names;
- category searches;
- location/proximity ranking;
- typo tolerance where supported;
- map POI overlays;
- search-result details;
- deterministic regression tests;
- comparison between search builds.

A POI/search update must not force routing or visual artifacts to be downloaded again.

## Final production workflow

~~~
                    GRAPH STUDIO
                         |
            source update detection
                         |
          +--------------+--------------+
          |              |              |
       ROUTING         VISUAL          SEARCH
       Valhalla        PMTiles         SQLite
          |              |              |
          +--------------+--------------+
                         |
                  validation suite
                         |
             boundary/connectivity proof
                         |
               version + fingerprint
                         |
                   SHA-256
                         |
                  Cloudflare R2
                         |
             regional latest manifests
                         |
                     RoadPilot
                         |
         download only artifacts that changed
~~~

## Definition of production ready

The offline-data system is production ready when Graph Studio can, without hand-editing repository files:

1. create/select a region;
2. discover required neighboring source data;
3. build its routing graph;
4. build its visual package;
5. build its search database;
6. inspect all three artifacts;
7. validate ordinary routes;
8. validate border connectivity;
9. manually repair a crossing when necessary;
10. detect whether a rebuild invalidates border metadata;
11. version and checksum every artifact;
12. publish immutable artifacts to Cloudflare;
13. update region catalog/latest pointers;
14. let RoadPilot download only individual regional artifacts that actually changed.

## Immediate execution order

~~~
finish #11 border diff / candidates / reports
        ↓
#13 exact build + boundary fingerprints
        ↓
build-time connectivity manifests / F8 seeds
        ↓
#35 regional entry→exit connector matrices
        ↓
#14 Cloudflare R2 publication
        ↓
#16 visual map layer
        ↓
#17 POI/search layer
        ↓
#15 scheduled updates + retention
        ↓
production hardening / RoadPilot integration
~~~

Update this document whenever a milestone is merged, split, reordered, or materially changed.
