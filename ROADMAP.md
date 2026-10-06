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
| Border inspector + manual crossings | #11 / PR #20 | Core merged | Dual graph overlay, manual A/B edge snapping, validation, fingerprints, stale detection |
| Exact graph/boundary diffing | #13 | Next | Internal-vs-boundary change detection and per-neighbor fingerprints |
| Cloudflare R2 publication manager | #14 | Planned | Publish validated immutable packs and manage latest pointers |
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

## Active — Border Inspector refinement

Issue #11 remains active. Border Inspector core was merged in PR #20.

Core now merged into `main`:
- choose Graph A and Graph B;
- overlay both independent Valhalla graphs;
- manually select the intended crossing edge in A and in B;
- snap each selection through Valhalla locate;
- retain correlated coordinates, OSM way identity, percent-along, heading, directed-edge metadata and graph identity;
- allow A and B crossing coordinates to differ;
- validate the crossing using plain Valhalla;
- test both graphs, both travel directions and motorcycle/auto costing;
- refuse to save a crossing as VALID when proofs fail;
- save crossings in a RoadPilot-owned manual handoff layer;
- bind overrides to both regional graph fingerprints;
- automatically mark overrides STALE after either graph changes;
- revalidate an existing override in place;
- delete overrides.

Still remaining to fully close issue #11:
- visualize overlap/common roads versus A-only/B-only roads;
- render automatically discovered candidate handoffs;
- render learned RoadPilot handoffs;
- distinguish manual/automatic/learned handoffs on the map;
- export/share a compact border diagnostics report;
- polish pair-focused map fitting and inspection.

## Next

### 1. Finish Border Inspector (#11)

Goal:

~~~
Graph A + Graph B
       ↓
common / unique roads
       ↓
automatic + learned + manual handoffs
       ↓
Valhalla proof
       ↓
VALID / FAILED / STALE
~~~

### 2. Exact graph and boundary diffing (#13)

This is critical for independent regional updates.

For every rebuild, Graph Studio should answer:
- did internal routing change?
- did a specific border/overlap change?
- does cross-region metadata need refresh for that neighbor?

Planned work:
- deterministic graph fingerprint;
- per-neighbor boundary/overlap fingerprint;
- added/removed/changed edge detection where deterministic;
- internal-road changes separated from boundary changes;
- visualization of changed border roads;
- invalidate/rebuild only compatibility metadata affected by a changed boundary.

### 3. Build-time cross-region connectivity metadata

This is the key step for removing expensive first-route F8 discovery from phones.

During graph production, Graph Studio should derive compact RoadPilot connectivity metadata using stable real-world references wherever possible:
- OSM way/node identity;
- correlated GPS position;
- direction;
- road class/ref/name;
- validated motorcycle/auto access;
- regional graph fingerprints;
- region-pair identity.

Runtime target:

~~~
origin region
    ↓
precomputed connectivity layer
    ↓
region chain
    ↓
local Valhalla detailed routing
~~~

F8 remains the fallback when metadata is missing, stale or ambiguous.

### 4. Cloudflare R2 publication manager (#14)

Required behavior:
- immutable versioned objects;
- SHA-256 verification;
- no accidental overwrite;
- update latest pointer only after immutable files are confirmed;
- show local vs published version;
- upload progress;
- rollback latest pointer without deleting historical builds.

The publisher should ultimately support routing, visual and search artifacts independently.

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
