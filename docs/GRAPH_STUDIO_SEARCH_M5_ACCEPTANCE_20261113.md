# Graph Studio Search/POI — issue #17 M5 implementation and acceptance

13 November 2026. This is Graph Studio's missing local producer/import
milestone. The earlier M1–M4 already supplied the RoadPilot-compatible Overture
SQLite builder, V1/V2 search runtime, Search inspector/map overlays, comparison
and independently versioned Search-only R2 publication logic. Do not replace
those implementations.

## Native desktop changes

- The Region Editor can enable/disable Search independently, use the actual
  Geofabrik country ancestor's ISO alpha-2 country, retain existing Overture
  coverage and filenames, and configure a deterministic expected place/query
  plus optional address fragments. No generated region may claim successful
  Search validation without an explicit actual regression target.
- Search / POI inspector has an independent Build Search action and a deliberate
  Import validated Search action. The new commands use the existing Graph
  Studio BuildState to prevent concurrent conflicting operations. Build
  supports the existing build progress/Cancel control; successful build/import
  refreshes the retained Search catalog and Search publication selector.
- The bundled graph_studio_search_producer.py is a thin orchestration layer
  around the existing canonical build_search_region_pack.py, not another
  database or ranking engine. It validates region configs, fingerprints and
  retained pack files with existing validators.
- Blank source path resolves the Overture STAC latest data release and
  downloads geojsonseq for the region bbox with the pinned overturemaps==1.0.2
  tool. An owner-supplied local GeoJSONSeq path and actual data-release string
  provide reproducibility for offline/regression builds.
- Original generated Search packs are immutable within
  ~/RoadPilotGraphStudio/search-builds/<region>/<version>/.
  Import revalidates existing manifest, original SQLite content, checksums,
  config-specific runtime search targets, then copies and revalidates before
  atomic promotion into the separate Search root. Invalid or duplicate
  packages are rejected. Routing and Visual builds are not touched.
- Geofabrik catalog returns countryIsoAlpha2 from the actual ISO metadata
  on the containing country ancestor, including subregions, rather than
  inferring country codes from place names.
- Python source dependency is pinned in requirements-search.txt.
  Graph Studio CI verifies new producer regression tests and bundled
  AppImage/DEB resources in the existing desktop packaging jobs.

## Real Overture Austria evidence, 13 November 2026

Official pinned Overture download client 1.0.2, STAC data release
2026-10-21.0. Acquired the complete bounded source envelope
minLng=9.3,maxLng=17.3,minLat=46.3,maxLat=49.2, about 2.0 GB
and 1,534,139 raw Overture Places records. Country-filtering by AT
produced 573,842 actual Austrian SQLite POIs; 562,094 with category
enrichment; all 573,842 retained structured-address/source metadata.

The resulting validated Austria v1 SQLite package is approximately 249 MB
and has SHA-256
54d88e3ae951bff3e1dfd306ae05737bfcc3aaf9bf6f35fd1ba58c15962ccda5.

Explicit original-country source test target: Wiener Staatsoper, Opernring 2
in Wien. Android-compatible v1 runtime search ranked it #1. In the
RoadPilot enhanced v2 runtime, the exact query Wiener Staatsoper ranked it
first near the tested map center 48.2033,16.3696, offset 3.76 metres,
score 8498. A real restaurant category query returned local place
coordinates, distances, classification and scores.

The new import action revalidated the real 249 MB Austrian SQLite and
manifest, replayed the mandatory runtime target, and retained immutable
copies successfully. Existing R2 plan generator + local-only publication
backend successfully prepared and applied the Search-only latest pointer at
search/austria/latest.json. It did not create or alter any Routing or Visual
latest pointer. The real Cloudflare R2 bucket was not touched.

All live source, retained Search pack, import and local publication evidence
are outside Git under the Legion directory:
~/RoadPilotGraphStudio/diagnostics/search-m5-20261113/

## Automated regression evidence

The existing Italy Nord-Est SARP fixture and a second Austria Wien Fuel
fixture each exercised the new producer CLI, source release, immutable
manifest/SQLite/checksum, runtime query validation, full import replay,
tamper rejection, duplicate-version refusal, missing validation target,
unsafe version and symlink rejection. Python suite at the feature commit
base passed 518 out of 518 tests. Graph Studio TypeScript and Vite compiled
successfully on Legion. The GitHub Linux CI additionally compiles Tauri,
builds the AppImage and Debian package, and checks bundled producer resources.

## Completion distinction

Source/workflow acceptance is established by the real Austria data and
regressions above. For final issue closure, issue #17 additionally requests
verification using the newly packaged/installed Graph Studio desktop UI:
select/configure a region, Search-only build or validated import, run an
actual SQLite query/map overlay, compare retained versions, and confirm
restart persistence. Installed-app evidence must be recorded separately:
a successful Python script or CI does not prove a new AppImage has been
installed and manually exercised. No RoadPilot Android validation is needed
for this private Graph Studio milestone.
