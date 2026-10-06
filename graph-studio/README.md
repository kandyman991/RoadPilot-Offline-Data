# RoadPilot Graph Studio

RoadPilot Graph Studio is the Linux workstation for producing RoadPilot's independently versioned Valhalla routing packs.

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
5. Detailed graph-to-graph diffing, including boundary fingerprints.
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


## Handoff artifact overlay

The Border Inspector can normalize and display RoadPilot handoff evidence from the local Graph Studio
workspace. It recognizes:

- `roadpilot.transition-candidates` — automatic offline candidate pairs;
- `roadpilot.bound-cross-graph-transitions` — Valhalla-proven, graph-bound transitions;
- `roadpilot.cross-graph-transitions` — F8-learned physical proof artifacts;
- Graph Studio manual overrides.

Generated transition artifacts belong under:

```text
~/RoadPilotGraphStudio/transitions/
```

Artifacts copied from a device or another workstation can be placed under:

```text
~/RoadPilotGraphStudio/imports/handoffs/
```

Graph Studio compares every artifact's region-pair graph fingerprints against the latest local
routing builds and marks it CURRENT/VALID or STALE. Graph-local IDs are never compared between
independent graphs.
