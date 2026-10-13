# Shared Geofabrik sources and repeat-build cache (2026-10-13)

Graph Studio must keep routing, visual and search packages independently
versioned. Source bytes are a separate concern: the same Geofabrik PBF should
not be downloaded again just because a different region or visual map uses it.

## Current implementation

- Routing and visual PBF acquisition share `work/cache/<geofabrik-id>.osm.pbf`
  in the *local Graph Studio workspace*. The existing routing cache layout is
  retained. Old visual PBFs are hardlinked to the shared cache when possible,
  rather than downloading another gigabyte-scale copy.
- Once per 24 hours per source (or when explicitly refreshed), request the
  tiny published `.osm.pbf.md5` sidecar to check if the upstream PBF changed.
  If unchanged, reuse the cached bytes. If changed, download to `.part`,
  stream/verify the checksum and atomically replace the old source.
- The upstream MD5 is a *file-change/integrity check*, not a security signature.
  Retained routing and visual manifests continue using SHA-256 of the PBF bytes.
  If a source is unreachable and a cached copy already exists, the default
  build may reuse it while warning the console that freshness is unverified.
  Explicit force-refresh fails closed and never deletes the old good copy.
- Routing builds retain `work/<region>/build/buffered.osm.pbf` and Valhalla
  `admins.sqlite`/`timezones.sqlite` with an input fingerprint capturing every
  source SHA-256, the exact 25 km (or configured) clip polygon and the Valhalla
  version. A subsequent build with byte-identical inputs validates the retained
  products by SHA-256 and skips the expensive full-source merge, extraction
  and admin preprocessing. Any changed input or corrupt file invalidates reuse.
- The giant, transient `merged.osm.pbf` input is discarded after
  `valhalla_build_admins` has successfully used it. The buffered data remains.
- The Build menu includes **Force source re-download**, unchecked by default.
  It preserves the existing `--refresh-sources` CLI semantics.

## Important scope limitation

Geofabrik distributes complete downloadable extracts; the builder **still
downloads each required full neighboring leaf PBF on its first uncached use**.
It cannot HTTP-range download a geographic 25 km strip: byte ranges in a PBF
do not correspond to geographic polygons.

On the *first* build, creating the Valhalla admin database requires a broad,
reference-complete administrative context. Do **not** naively replace this
step with individually cropped border slices: doing so may truncate OSM
relations and silently change routing/admin semantics. The current supported
optimization retains the verified buffered result so **repeat builds no longer
reprocess full neighbors**.

A further source-cutting milestone can use reference-complete tagged admin
context (if proven against whole-source baseline with exact OSM/Valhalla
regression fixtures) and reusable smaller border strips. Do not label this
untested optimization production-ready. Separate mirror/differential Geofabrik
updates would need their own version/fingerprint contract.

## Desktop acceptance tests

1. Build a small cross-border region once; record PBF downloads and source
   manifest SHA-256. The first build must still pass normal osmium/Valhalla
   integrity and real route checks.
2. Build the same region with a *new immutable package version* and unchanged
   PBFs. Confirm logs say `shared source cache hit` and `skipping full-source
   merge/extract`; avoid unnecessary visual/search rebuilds.
3. Build an adjacent region using one overlapping source; confirm shared PBF
   file is not downloaded again.
4. Force-refresh, or inject changed synthetic PBF and polygon inputs in tests,
   and confirm prepared-source invalidation.
5. Disconnect network; verify cached reuse emits an explicit freshness warning.
6. Do not remove existing retained routing manifests/tiles during this work.

Tests in CI exercise cache use, change detection, atomic writes, old visual PBF
migration, offline behavior, source SHA/buffer/Valhalla invalidation. They are
**not** a substitute for a real device Valhalla build.
