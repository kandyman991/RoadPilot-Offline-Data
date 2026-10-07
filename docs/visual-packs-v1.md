# RoadPilot visual packs v1

RoadPilot visual map packages are independent from routing graphs and POI/search databases.

## Artifact format

The visual artifact is one PMTiles v3 file containing Mapbox Vector Tiles (MVT). The first profile is intentionally lightweight:

- `transportation`
- `transportation_name`
- `place`
- `water`
- `waterway`
- `boundary`
- `mountain_peak`

Dense building and POI layers are intentionally excluded. POI/search production remains a separate artifact pipeline.

## Pinned toolchain

The production profile is under `visual/tilemaker/`.

`toolchain.json` pins:
- tilemaker version;
- source release tag;
- exact upstream Git commit.

The builder verifies the reported tilemaker version before generating a pack. Hosted CI compiles the exact pinned source commit and uses that binary for both reproducibility builds. Graph Studio/production may use an installed native tilemaker binary only when it reports the pinned version.

## Build

```bash
python -m pip install -r requirements-visual.txt

python tools/build_visual_region.py \
  --config config/regions/italy-nord-est.json \
  --pbf /path/to/nord-est-latest.osm.pbf \
  --version 2026.10.07-1 \
  --output-dir /path/to/output
```

The builder uses the region's configured primary Geofabrik source identity and writes:

- `<region>-visual-<version>.pmtiles`
- `<region>-visual-<version>.pmtiles.sha256`
- `<region>-visual-<version>-manifest.json`

## Manifest fingerprints

The visual manifest has three independent fingerprints:

- `visualFingerprint` — exact SHA-256 of the generated PMTiles file;
- `profileFingerprint` — SHA-256 over the tilemaker config, Lua process profile, and pinned toolchain contract;
- `sourceFingerprint` — SHA-256 over the exact source descriptor, including PBF SHA-256 and size.

This lets RoadPilot distinguish source changes, visual-profile changes, and final artifact changes without tying visual versions to routing graph versions.

## Validation

```bash
python tools/validate_visual_pack.py \
  --manifest /path/to/<region>-visual-<version>-manifest.json \
  --package /path/to/<region>-visual-<version>.pmtiles \
  --expect-current-profile
```

Validation:
- checks the JSON schema;
- rehashes the exact PMTiles artifact;
- verifies size/checksum/fingerprint consistency;
- opens the PMTiles v3 header and metadata;
- requires MVT tile type;
- verifies tile count, zoom range and bounds against the manifest;
- decodes real tile payloads and confirms required layers are present;
- rejects building/POI layers in the v1 lightweight profile;
- rejects truncated or malformed archives.

## Determinism

Hosted CI builds the same tiny OSM fixture twice with the pinned toolchain and requires the resulting PMTiles files to be byte-identical. It also verifies that all seven intended v1 layers are present in decoded tiles and that a truncated archive is rejected.

## Next milestones

M2 will turn this artifact contract into the real regional production pipeline with retained builds, source download/cache integration, road-content validation and rebuild lifecycle.

M3 will make Graph Studio display and compare the exact PMTiles files RoadPilot downloads.

M4 will publish visual packs through the independent immutable R2 publication path.

## Regional production lifecycle

The regional production command is:

```bash
python tools/build_visual_region_pack.py \
  --config config/regions/italy-nord-est.json \
  --package-version 2026.10.07-1 \
  --tilemaker-bin /path/to/tilemaker
```

It owns the full lifecycle:

1. validate the region config;
2. cache the configured primary visual PBF and nominal Geofabrik polygon;
3. build/canonicalize the PMTiles artifact;
4. extract source major/border roads from the same PBF;
5. prove those OSM way IDs are present in the PMTiles transportation layer;
6. attach the road-index SHA/counts to the visual manifest;
7. validate the complete package again;
8. atomically retain it under `dist/visual/<region>/<version>/`.

Retained version directories are immutable. Reusing the same package version is refused.

### Road coverage validation

Each production visual pack has a `roadpilot-visual-road-index` containing the configured major road classes plus all source highways intersecting a configurable corridor around the nominal region boundary.

The build fails when any required source road is missing from the generated visual PMTiles. The index is bound to both `sourceFingerprint` and `visualFingerprint`.

### Refresh planning

`tools/plan_visual_refresh.py` compares a retained build with the current source/profile/config and chooses the cheapest safe action:

- `NONE` — source, profile and road-validation criteria still match;
- `REVALIDATE_ROADS` — PMTiles can be retained but road-validation criteria changed or the road index is missing;
- `REBUILD_PROFILE` — the tilemaker visual profile/toolchain changed;
- `REBUILD_SOURCE` — the source PBF bytes/identity changed.

Source changes outrank profile changes, which outrank road-only revalidation.
