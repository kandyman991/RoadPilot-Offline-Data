# Engineering Decisions — RoadPilot Graph Studio / Offline Data

Durable design intent. This is not evidence that each item is implemented and merged. Supersede decisions with dates and links rather than deleting their history.

## D-001 — Independent routing/visual/search artifacts

Version and validate each region's Valhalla routing, visual-map and SQLite search packs separately; never force unrelated rebuilds.

Source: `CHAT_HANDOFF.md` / repository roadmap and architecture (reverify against live implementation).

## D-002 — Valhalla graph identity and crossings

Never mutate raw .gph to repair seams; RoadPilot-owned transitions require directional, mode and exact fingerprint compatibility backed by Valhalla leg proof.

Source: `CHAT_HANDOFF.md` / repository roadmap and architecture (reverify against live implementation).

## D-003 — Graph Studio owns the production pipeline

Android consumes verified packages; Graph Studio builds/inspects connectivity and artifact manifests. F8 is the runtime correctness fallback.

Source: `CHAT_HANDOFF.md` / repository roadmap and architecture (reverify against live implementation).

## D-004 — Publication is explicit

Distinguish implemented R2 publisher functions from credentials, configured destinations, or a successfully published production release; verify live config before claiming any live distribution.

Source: `CHAT_HANDOFF.md` / repository roadmap and architecture (reverify against live implementation).

## D-900 — Cross-chat continuity (2026-10-10)

Keep `CHAT_HANDOFF.md` as the curated next-action source; use GitHub live state for actual PR/CI status and a generated `handoff/state.json` only as a hint. Record decisions and failed experiments explicitly.
## D-005 — One-click routing setup with graph-backed validation (2026-10-13)

PR #62 adopts the user workflow *Geofabrik selection → automatic configuration → build → Valhalla proof*. Manual GPS coordinates must not be a prerequisite to start region creation. A new routing-only config can use `routing.validationMode=auto` with zero manually supplied routes; it is **not** considered validated until the freshly built graph returns a routed line crossing the nominal Geofabrik polygon boundary. The routing manifest/pack remains unpublished on proof failure. Keep the decoded road geometry checks; do not turn mere polygon-normal samples into accepted routes. Allow optional map pins for manual start/end placement and retain existing user-authored region configs. Routing, visual and search artifacts remain separate.

Source: https://github.com/kandyman991/RoadPilot-Offline-Data/pull/62 (merged, CI verified; full regional device build still to be tested).

## D-006 — Shared, checksum-aware Geofabrik source cache (2026-10-13)

PR #63 consolidates routing/visual PBF acquisition into the stable routing workspace cache. Periodically check Geofabrik `.osm.pbf.md5` sidecars rather than downloading large source files merely to detect updates. Verify downloads before atomic replacement; keep SHA-256 input fingerprints in manifests and cached source preparation metadata. Existing buffered regional OSM and *full-context* Valhalla admin/timezone results can be reused only if every PBF SHA-256, exact buffer polygon hash and engine version match and prepared output checksums verify. Temporary large `merged.osm.pbf` must not be retained after successfully preparing admin DBs.

Explicitly do **not** treat arbitrary PBF HTTP byte ranges as geographic border extracts. The first uncached neighboring source still requires complete PBF transfer with current Geofabrik endpoints. Do not crop admin relations before proving replacement context equivalent to full-source data in a real validation fixture. Routing/visual/search distribution packs remain independently versioned.

Source: https://github.com/kandyman991/RoadPilot-Offline-Data/pull/63 (merged, CI green; Legion full build validation pending). See `docs/geofabrik-shared-cache.md`.

## D-007 — Normalize overlapping OSM object versions before graph extraction (2026-10-13)

Geofabrik country/thematic aggregates may overlap smaller regional leaves. Select the smallest exact .poly sources that genuinely add coverage within the buffer, preserving the primary extract. Never select source PBFs merely because an index polygon intersects the buffer without checking redundant coverage. **Independently refreshed OSM extracts may contain different versions of the same type/ID**: pass the low-memory `osmium merge` stream through `osmium time-filter` to generate a normal current snapshot, not through `osmium sort` (which retains duplicates). Continue requiring `osmium check-refs` and existing Valhalla route proof. Do not hard-code DACH, Alps, motorway or border exceptions.

PR #64 merged after synthetic actual-Osmium CI passed; full on-device Austria rebuild not yet verified. https://github.com/kandyman991/RoadPilot-Offline-Data/pull/64

## D-008 — Shared, read-only AI inspection before AI operations (2026-10-13)

Graph Studio must be operable and verifiable by authorized AI tools without
duplicating its core behavior. Start with a versioned **Rust command engine**
used by the Tauri UI and headless CLI alike; `capabilities` and `inspect`
are deliberately read-only and never imply running build state when outside
the process. Do not introduce an HTTP listener or automatic mutating agent
in the first milestone. Inspect only allowlisted routing config/manifest fields,
never R2 credentials or raw logs. Future local bridges require user opt-in and
narrow permissions; any mutation must be explicitly authorized and tested.

## D-009 — Evidence-graduated AI diagnosis (2026-10-13)

Expose retained **manifest-recorded** Valhalla route outcomes and existing
exported border reports through a bounded, read-only AI diagnostic command.
Never describe manifest presence as an independently rerun route or report
existence as proof of freshness. At build completion, write one sanitized latest
outcome using stable stage/error categories rather than persisting potentially
sensitive subprocess stderr. The diagnostic inspector itself writes nothing and
must operate without launching the desktop UI or requiring a network service.
No graph or publication operations are authorized by this interface.

## D-010 — Explicit and bounded AI route probes (2026-10-13)

AI route verification is a narrowly scoped **explicit** Valhalla operation,
not a scheduler or an automatically granted external agent. The local CLI and
Tauri command use the same Rust engine and share the application's request
validation and polyline decoder. Accept only a safe region id, two finite
locations and an allowlisted travel mode. Bound wall time and output, discard
raw stderr and return structured result metadata. Never modify routing packs,
publish, infer cross-region seam validity, or claim a retained package is the
running graph. The Tauri invocation refuses probes while the application is
building. Headless callers must ensure no separate build is active.
