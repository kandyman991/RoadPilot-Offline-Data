# RoadPilot routing packs v1

RoadPilot routing packs are independently built Valhalla graphs distributed separately from the application APK.

## Production flow

    Geofabrik regional PBFs
            ↓
    merge primary + neighboring source extracts
            ↓
    clip to the primary Geofabrik polygon + border buffer
            ↓
    build Valhalla on the Legion self-hosted runner
            ↓
    validate interior and border-crossing routes
            ↓
    create immutable .tar tile extract
            ↓
    record version + SHA-256 + graph fingerprint
            ↓
    publish to Cloudflare R2
            ↓
    RoadPilot downloads/updates one region at a time

## Independence rule

A routing pack is versioned independently. Updating Austria must not require rebuilding or downloading Italy Nord-Est, Oberbayern, or any other installed region.

Cross-region compatibility is therefore not expressed by requiring all installed graphs to come from one synchronized global build. RoadPilot's cross-region layer remains responsible for joining independently built graphs.

## Border coverage

The nominal Geofabrik polygon defines which region the pack represents.

Before graph construction, the builder expands that polygon by `borderBufferKm` in a local metric projection, merges all configured neighboring Geofabrik extracts, and clips the merged OSM input to that buffered geometry. This ensures roads crossing the nominal border continue into the neighboring area far enough for RoadPilot/Valhalla to prove usable handoffs.

The buffer is part of the manifest and can be changed per region without changing the global architecture.

## Publication gate

A pack is not publishable unless:

1. the Valhalla tile extract contains `index.bin` and at least one `.gph` tile;
2. package size and SHA-256 match the manifest;
3. all configured Valhalla smoke routes succeed;
4. at least one configured route crosses the nominal Geofabrik boundary;
5. the graph fingerprint is the SHA-256 identity of the immutable published tile extract.

Cloudflare publication remains a manual gate. The build must also use the exact Valhalla version declared by the region config; Italy Nord-Est is pinned to Valhalla 3.6.3 to match RoadPilot's current Valhalla Mobile runtime.


## Cloudflare R2 publication

Publishing is a separate manual gate after the build and validation steps. Immutable objects are stored under:

    routing/<region>/<version>/<artifact>
    routing/<region>/<version>/<manifest>
    routing/<region>/<version>/<artifact>.sha256

The publisher writes `routing/<region>/latest.json` only after all immutable versioned objects are present. That pointer is the small object RoadPilot can poll when checking for an update.

The workflow requires these repository secrets only when `publish_r2=true`:

- `CLOUDFLARE_ACCOUNT_ID`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`
- `R2_BUCKET`
- `R2_PUBLIC_BASE_URL`

Versioned objects are never overwritten with different content. Re-running the same publication is safe when the object SHA-256 matches.
