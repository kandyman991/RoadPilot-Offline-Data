# RoadPilot Graph Studio

RoadPilot Graph Studio is the Linux workstation for producing and inspecting RoadPilot's independently versioned routing, visual-map and Search/POI packs.

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
  builds/         immutable routing TARs, manifests and checksums
  visual-builds/  immutable PMTiles visual versions, manifests, checksums and road indexes
  search-builds/  immutable Search/POI SQLite versions, manifests and checksums
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

## AI-operable inspection foundation

Milestone 1 adds a versioned, allowlisted, read-only Rust command engine shared
by the Tauri frontend and installed binary's `--ai-inspect` /
`--ai-capabilities` headless interface. It inventories configured regions
and retained routing manifests without launching a GUI, rebuilding graphs,
exposing credentials or starting a local listener.
See [AI Control](docs/AI_CONTROL.md) for its contract, limitations and tests.
M2 adds `--ai-diagnose` with recorded Valhalla route evidence, retained border
report summaries and sanitized build outcome categories (no raw logs or route replays).

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

The R2 publication panel can switch between **Routing graph**, **Visual PMTiles** and **Search / POI SQLite** without sharing mutable release state.

- routing uses `routing/<region>/<version>/...` plus `routing/<region>/latest.json`;
- visual uses `visual/<region>/<version>/...` plus `visual/<region>/latest.json`;
- search uses `search/<region>/<version>/...` plus `search/<region>/latest.json`;
- visual publication revalidates the exact PMTiles and its zero-missing-road index before a plan can be created;
- upload progress, immutable history and verified rollback use the same safe publication backend;
- Search publication revalidates the exact retained SQLite, checksum, manifest and runtime regressions before upload;
- changing or rolling back any routing, visual or search pointer cannot move either of the other two.

Real Cloudflare credentials remain local to Graph Studio app data and are not committed to this repository.

## AI Valhalla verification (M3)

The installed binary supports `--ai-verify-route REGION START_LAT START_LNG END_LAT END_LNG COSTING`
and the trusted GUI may call `ai_verify_route`. Both use the shared Rust Valhalla
request/geometry functions. Only an explicitly requested local, bounded route
probe is run: it neither builds nor publishes graphs. See
[AI Control](docs/AI_CONTROL.md) for evidence semantics and safety limits.

## Automatic F8-derived graph connectivity production

After **Build selected** completes a region's routing and optional visual packs,
Graph Studio runs `tools/refresh_graph_connectivity.py` against the locally
retained routing manifests, buffered OSM and cached nominal Geofabrik polygons.
It discovers locally available, mutually adjacent independent graphs by their
per-neighbor boundary fingerprints. For each pair affected by a newly rebuilt
graph, it runs the existing production sequence:

1. fingerprint-bound pair manifest;
2. frontier road inventory from the existing buffered OSM;
3. independent Valhalla correlation of each side;
4. exhaustive unproven candidate construction (no heading/separation cuts);
5. directional car/motorcycle Valhalla proof for each candidate;
6. validated runtime connectivity, followed by regional connector inventory
   and exact-entry/exit route matrix.

All stages use their existing schema validators. Products are first generated
in a temporary workspace. Previously validated runtime metadata is never
replaced with unproven candidates; a failed refresh leaves earlier artifacts
on disk, but stale graph/boundary fingerprints prevent using them as current.
Only pairs whose exact graph/boundary fingerprints changed are regenerated.
Regional connector matrices reuse matching source-inventory SHA and graph
fingerprint, preventing redundant many-to-many routing.

The **Refresh connections** button in the Build tool scans all currently
retained neighboring graphs and performs connectivity production without
rebuilding or redownloading routing graphs. For direct CLI use:

```bash
python tools/refresh_graph_connectivity.py \
  --dist-dir ~/RoadPilotGraphStudio/builds \
  --work-dir ~/RoadPilotGraphStudio/work \
  --connectivity-dir ~/RoadPilotGraphStudio/connectivity \
  --connector-matrix-dir ~/RoadPilotGraphStudio/connector-matrices
```

Local artifacts are stored under `connectivity/<regionA>__<regionB>/`
and `connector-matrices/<region>/`, visible in the Border Inspector.
They are not automatically uploaded to R2 or installed on Android.
Real Italy–Austria–Germany graph and Android integration validation
remain a separate, required on-device gate.

If either region's source polygon or buffered OSM has not been retained,
the stage **fails explicitly** rather than using fabricated data, invoking a
new map build, or downloading new extracts. Region packs already validated
remain intact; check the Build console to see which connectivity stage failed.
A `VALIDATED` connectivity artifact with zero proven crossings is an honest
negative result and requires RoadPilot's established F8 runtime fallback.

## Multi-region Route Planner (F8-derived, read-only)

The Route Planner now has **Single graph** and **Multi-region** modes.
Multi-region automatically locates the requested origin and destination
within the nominal/buffered coverage of each current installed local
Valhalla graph. It verifies the selected graph's exact working tile extract
matches the retained routing manifest SHA, and excludes unmatched graphs.

With multiple graphs, the planner loads only `VALIDATED` runtime connectivity
artifacts matching both current graph and boundary fingerprints, plus current
regional connector inventories and fingerprint-matched matrices. It invokes
the existing `compose_hierarchical_connectivity.py` for multiple directed,
mode-specific candidate chains. No fixed portals, 30-degree heading filter
or arbitrary handoff separation cutoff is introduced.

For each candidate, local Valhalla computes a detailed route leg inside
each graph, from the requested origin to the proven exit anchor, from each
subsequent entry to exit, and from the final entry to destination. Actual
route endpoints are verified within 150 m **after Valhalla**, and full
journeys are ranked by their actual summed detailed time (FASTER) or
distance (SHORTER), not by incomplete precomputed estimates.

Rendered geometry is `MultiLineString` (one separate line per graph),
**not** a line artificially bridging differing graph-correlated handoff
coordinates. The UI displays graph sequence, independent handoff gaps,
each leg's Valhalla cost and endpoint deviation, and final arrival proof.
Routes that fail endpoint verification are reported as incomplete or
unavailable, never as successful. If a complete same-graph route exists,
the mode can use it directly; if that graph stops short, it tries validated
cross-graph candidates.

The query is local and read-only with a bounded candidate/probe budget
(20 chains per source/destination pair, 64 distinct detailed legs, around
120 seconds), no graph rebuilding and no publication. It supports
Motorcycle and Car. Search expansion and turn-by-turn maneuver merging
are not yet available in this mode. The existing Single graph mode is
unchanged. Android F8 remains the operational fallback until sidecar
installation and on-device integration are proven (SmartRide-Next #512).

**Real-device acceptance:** install a release that contains this feature,
produce and validate Italy Nord-Est/Austria connectivity on the Legion,
then run Trento → Innsbruck in Multi-region mode. Verify *both* graph legs,
the actual handoff gap and arrival, or capture a structured failure; do
not claim success merely because this code passed synthetic CI tests.

## F8 discovery foundation: overlap candidate coverage (in development)

RoadPilot Android's working generalized F8 scans **directed graph road edges**
in windows over reachable-route corridors and available shared-boundary
segments. Earlier Graph Studio candidate generation only included OSM roads
that intersect both *nominal* region polygons. This can miss many usable
handoffs in the independently buffered graph overlap.

The overlap-discovery implementation runs on the Legion during the existing
connectivity refresh: it scans both retained buffered OSM extracts, keeps
nominal border intersections, and adds all distinct OSM way fragments inside
the **intersection of the two actual build buffer polygons**. Long fragments
are sampled at approximately 1500m spacing. It never groups candidates by
road name/ref, selects a single known crossing, or rejects candidates using
pre-Valhalla heading, proximity, road class or motorcycle access thresholds.
Both graphs still correlate candidates independently; directed Valhalla
route proofs decide which options are usable.

Scope/provenance is explicitly embedded in the frontier inventory and
propagated to compiled runtime connectivity metadata:

- `discovery.scope = OSM_BUFFER_OVERLAP`: both retained OSM sources and both
  graph coverage polygons were completely scanned, with no silent truncation
- `discovery.sourceExhausted = true`: the required source scans finished;
  failure/timeout/250000-anchor guard aborts publication instead
- `discovery.f8GraphEdgeParity = NOT_VERIFIED`: **this is not yet proven to
  be the full set of the Android F8 graph-edge scanner's candidates**

Old nominal-only products are no longer accepted as current by
`refresh_graph_connectivity.py`; a refresh regenerates them. A previous
working runtime is not overwritten if re-enumeration or Valhalla proof fails.

**Required next step before product-complete claims:** compare the
overlap inventory with the actual Android `FrontierGpsRoadDirectionRecovery`
graph-edge scanner on real Italy Nord-Est/Austria and Austria/Germany
Valhalla graphs. Record every F8 graph edge absent from the precomputed
coverage and resolve it, including motorway direction and long overlapping
ways; run enough combinations to show that the *best* candidate is not
discarded by planner candidate/probe budgets. Use issue #73 as the
acceptance contract. Do not mark the F8 parity field VERIFIED until proven.
