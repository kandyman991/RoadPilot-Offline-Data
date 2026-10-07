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
- exact Docker image digest;
- source release tag.

The builder verifies the reported tilemaker version before generating a pack. A matching native tilemaker binary may be supplied explicitly; otherwise the pinned container is used.

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
