# RoadPilot Graph Studio

RoadPilot Graph Studio is the Linux workstation for producing and inspecting RoadPilot's independently versioned routing and visual map packs.

## Current milestone

The first installable milestone provides:

- region catalog loaded from the production RoadPilot offline-data configs;
- multi-region build selection and sequential build queue;
- live Python/Osmium/Valhalla logs;
- cancellation;
- CPU/load, RAM, disk-free and thermal monitoring;
- local build history and basic build comparison;
- MapLibre inspection workspace;
- direct rendering of Valhalla graph MVT layers through a custom MapLibre protocol;
- click-to-inspect graph feature properties;
- deep `locate` inspection using the exact locally built graph;
- AppImage and Debian package generation on GitHub-hosted CI.

Graph Studio bundles the canonical `config/`, `schemas/`, `tools/` and `requirements-routing.txt` files from this repository. The desktop UI does not maintain a second routing pipeline.

## Local workspace

At runtime Graph Studio uses:

```text
~/RoadPilotGraphStudio/
  work/       cached Geofabrik sources + unpacked build workspace
  builds/     immutable routing TARs, manifests and checksums
  visual-builds/ immutable PMTiles visual versions, manifests, checksums and road indexes
```

The Python virtual environment is stored in the application cache directory and prepared automatically on first build.

## Host requirements

The Legion still needs the native graph toolchain on `PATH`:

- Python 3 + venv
- osmium
- Valhalla 3.6.3:
  - `valhalla_build_config`
  - `valhalla_build_timezones`
  - `valhalla_build_admins`
  - `valhalla_build_tiles`
  - `valhalla_build_extract`
  - `valhalla_service`

The production build script refuses to build with a Valhalla version different from the version declared by the region config.

## Development

```bash
cd graph-studio
npm install
npm run tauri dev
```

Tauri v2 on Debian/Ubuntu requires WebKitGTK 4.1 development packages and the standard Linux build dependencies.

## Inspector architecture

MapLibre GL JS supports custom resource protocols. Graph Studio registers `roadpilot-graph://` and resolves requested vector tiles through the Tauri backend. The backend uses Valhalla's one-shot `tile` action against the region's retained `valhalla.json`.

This deliberately avoids exposing a local HTTP server or relying on browser CORS configuration.

## Next milestones

1. Production region catalog and build queue — implemented in this milestone.
2. Region-detail editor and neighbor/source auto-discovery.
3. Dedicated border-pair inspector with A/B graph overlays and two-sided route probes.
4. Route-search/expansion visualization.
5. Detailed graph-to-graph diffing and boundary fingerprints — active.
6. Cloudflare R2 credential setup, publish confirmation and rollback/latest-pointer management.
7. Automatic update/build scheduling and retained-build cleanup policies.


## Border road diff

When two locally built neighboring graphs are loaded in the Border Inspector, Graph Studio compares
the currently loaded graph-tile window using Valhalla's stable `edge.osm_id` attribute.

The overlay deliberately does **not** compare Valhalla graph-local edge ids across independent
graphs.

- green — the OSM way identity is present in both graphs;
- red — the OSM way identity is present only in Graph A;
- blue — the OSM way identity is present only in Graph B.

The inspector reports unique OSM-way counts, loaded edge counts, and any edges that do not expose
an OSM identity. This is a way-level diagnostic view; exact geometry/boundary fingerprint diffing
is a separate roadmap milestone.


## Build and boundary diffing

New routing builds emit a deterministic graph-index sidecar next to the immutable routing pack.
The index records SHA-256 identity for each Valhalla `.gph` tile, a whole-graph tile fingerprint,
an internal-only fingerprint, and conservative fingerprints for each configured neighboring
Geofabrik source intersecting the buffered overlap.

Build Comparison can therefore distinguish internal changes from boundary changes and answer which
neighbor compatibility metadata needs to be refreshed. Changed boundary tiles are drawn on the map.
Builds created before this index exists remain usable, but they must be rebuilt before detailed
comparison is available.

Build Comparison now also loads the retained Build A and Build B routing packs through Valhalla
inside changed boundary tiles. Roads are grouped by stable OSM way identity and compared using
canonicalized rendered geometry plus supported access/use/speed/surface/structure attributes.
The map classifies boundary ways as added, removed, changed, or unchanged without treating
graph-local edge IDs as durable identity.

## Connectivity and handoff artifact overlay

The Border Inspector normalizes and displays both the current build-time connectivity pipeline
and older RoadPilot handoff evidence from the local Graph Studio workspace.

Current connectivity schemas:

- `roadpilot.crossing-candidates` — generated `UNPROVEN` Graph A × Graph B candidate pairs;
- `roadpilot.runtime-connectivity` — compact `VALIDATED` crossings promoted only after exact-edge plain-Valhalla proof.

Legacy/debug schemas remain inspectable for development history:

- `roadpilot.transition-candidates`;
- `roadpilot.bound-cross-graph-transitions`;
- `roadpilot.cross-graph-transitions` (F8-learned physical proofs);
- Graph Studio manual overrides.

Generated connectivity artifacts belong under:

```text
~/RoadPilotGraphStudio/connectivity/
```

Artifacts copied from another machine/device can be placed under:

```text
~/RoadPilotGraphStudio/imports/connectivity/
```

Legacy transition/handoff imports remain supported under `transitions/` and `imports/handoffs/`.

For current connectivity artifacts, Graph Studio compares both exact regional graph fingerprints
and the relevant per-neighbor boundary fingerprints against the latest local builds. It shows
`UNPROVEN` vs `VALIDATED` separately from `CURRENT` vs `STALE`. Graph-local ids are trusted only
inside artifacts bound to their exact graph fingerprints and are never used as cross-build identity.
## Border diagnostics report

The Border Inspector can export a compact development report for the currently selected regional
graph pair.

Reports are written under:

```text
~/RoadPilotGraphStudio/reports/
```

Each export produces both JSON and Markdown and records:

- the exact Graph A and Graph B package versions/fingerprints;
- the currently loaded common / A-only / B-only OSM-way counts;
- loaded graph-edge counts and edges without OSM identity;
- candidate, accepted/bound, learned and manual handoff counts with CURRENT/VALID vs STALE state;
- a bounded list of notable handoffs;
- the currently selected manual crossing's full eight-probe Valhalla validation when present.

Changing either selected graph clears the previous pair's road-diff/report state before another
report can be exported.


## Exact RoadPilot visual PMTiles inspector

Graph Studio builds visual packs immediately after routing validation for regions with `visual.enabled`.
Visual versions are retained separately under the Graph Studio workspace so routing and visual
artifacts can evolve independently.

The Visual map inspector reads the exact retained `.pmtiles` file through bounded Tauri byte
ranges and the official PMTiles browser decoder. It does not unpack or regenerate a debug tile tree.

The inspector provides:
- RoadPilot's lightweight offline visual map;
- the online OpenFreeMap style as an optional reference;
- independent toggles for the visual map, reference map, Valhalla edges/nodes/shortcuts/access
  restrictions, border buffer, Graph A/B overlays, calculated route, route expansion and handoffs;
- package version, size, tile count, zoom/coverage, SHA-256, source/profile fingerprints and
  major/border-road validation counts;
- retained visual Build A/B comparison using original OSM feature IDs embedded by tilemaker,
  classifying roads in the currently loaded map window as unchanged, removed, added or changed.

The exact visual package remains independent from the routing pack and from the future POI/search
artifact.

## Independent R2 publication

The R2 publication panel can switch between **Routing graph** and **Visual PMTiles** without sharing mutable release state.

- routing uses `routing/<region>/<version>/...` plus `routing/<region>/latest.json`;
- visual uses `visual/<region>/<version>/...` plus `visual/<region>/latest.json`;
- visual publication revalidates the exact PMTiles and its zero-missing-road index before a plan can be created;
- upload progress, immutable history and verified rollback use the same safe publication backend;
- changing or rolling back the visual pointer cannot move the routing pointer, and vice versa.

Real Cloudflare credentials remain local to Graph Studio app data and are not committed to this repository.
