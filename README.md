# RoadPilot Offline Data

Public build and distribution repository for RoadPilot offline datasets.

This repository is intentionally separate from the private RoadPilot application source. Generated regional datasets are **not** bundled in the APK and are **not** committed to Git. They are built from public upstream data, validated, described by versioned manifests, and published as downloadable release assets.

## Responsibilities

RoadPilot-Offline-Data owns the production and publication of offline data consumed by RoadPilot, including:

- Overture Places regional search sidecars;
- future downloadable map packs;
- future prebuilt routing/data artifacts where appropriate;
- versioned region metadata and manifest schemas;
- validation tooling and reproducible data-build workflows.

The RoadPilot app remains responsible for downloading, verifying, activating, updating, and deleting installed datasets.

## First dataset

The first published dataset is the Overture Places sidecar for `italy-nord-est`.

The existing RoadPilot runtime contract is preserved:

- manifest schema: `1`
- database schema: `roadpilot-overture-v1`
- database file: `italy-nord-est-v1.sqlite`
- manifest file: `italy-nord-est-v1.json`
- validation target: SARP
- coverage: longitude `10.40..13.40`, latitude `44.50..46.80`

The generated SQLite database and manifest are published as assets on the `roadpilot-overture-packs` release.

First successful public build:

- 378,234 searchable places
- SQLite size: 108,879,872 bytes
- SARP regression validation: passed
- pack version: `main-3-eb7be85c`

## Repository layout

```text
.github/workflows/       build / validation / publication automation
config/regions/          source-of-truth regional dataset configuration
schemas/                 machine-readable manifest/config contracts
tools/                   deterministic builders and validators
dist/                    generated output (ignored by Git)
```

## Distribution rule

Application CI must never download Overture source data or embed regional place databases in the APK. RoadPilot downloads published regional packs independently and verifies size, SHA-256, schema, region identity, and record count before activation.

## Routing transition generation

RoadPilot keeps independently built regional Valhalla graphs, then generates cross-graph topology as a post-build artifact.

The production pipeline is intentionally split into two stages:

1. **Discovery** scans the entire shared frontier of a neighboring graph pair and retains every spatially plausible motorized edge pair. OSM way IDs, road names, refs, road class and heading are evidence only; heading is never a hard pre-Valhalla rejection.
2. **Proof/binding** lets Valhalla/Thor prove the legal travel direction and reachability on each graph before a candidate can be promoted into an app-consumable bound transition artifact.

The first reference pair is `geofabrik-austria <-> geofabrik-oberbayern`. Its regression anchors require the Kufstein motorway corridor to survive discovery in both directions even though the road changes from A12 to A93 and may use different OSM way IDs across the border.

Current tooling:

- `tools/build_routing_transition_candidates.py` builds a deterministic, fingerprint-bound candidate catalog from two full boundary-edge inventories.
- `tools/validate_routing_transition_candidates.py` validates the generated catalog.
- `config/routing-pairs/` owns pair-specific discovery limits and regression corridors.
- `schemas/routing-*` defines the build-time contracts.

Candidate catalogs are **not** safe to ship directly to RoadPilot. They are deliberately pre-proof artifacts; exact Valhalla validation must succeed before a crossing is promoted.

The complete production path is now:

```text
finished Graph A + fingerprint A
finished Graph B + fingerprint B
        ↓
Geofabrik exact polygons
        ↓
continuous shared-frontier scan windows
        ↓
roadpilot-boundary-inventory on Graph A and Graph B
        ↓
exhaustive directional candidate pairing
        ↓
roadpilot-transition-probe
  A: interior → seam on normalized outbound DirectedEdge
  B: seam → interior on stored inbound DirectedEdge
        ↓
Thor proves both local directed routes
        ↓
≤5 m exact projected seam check
        ↓
roadpilot.bound-cross-graph-transitions
        ↓
RoadPilot learned-chain runtime / exact regional Thor legs
```

The host native tools compile against the same Valhalla source revision used by RoadPilot Mobile: `e2f017b16080f49203de245a211b09efab09cf72`. The pair build entry point is `tools/build_pair_routing_transitions.py`.

For a directed A → B transition, the boundary inventory scanner records edges as boundary → interior. The proof stage deliberately normalizes Graph A to its opposing DirectedEdge (interior → seam) and leaves Graph B on its stored DirectedEdge (seam → interior). The packaged transition can therefore replay as STORED/STORED, matching the successfully validated F8-learned runtime representation.

The Austria ↔ Oberbayern reference build is not considered complete until a real graph run proves and packages the A12/A93 Kufstein motorway corridor in both directions. The fixed coordinate in the pair config is a regression assertion only; it is never injected as a transition.
