# RoadPilot search packs

RoadPilot search packs keep the physical SQLite database contract `roadpilot-overture-v1` so
currently released Android builds can continue to install and query newly generated packs.
The first eight columns of `places` remain unchanged:

`id, name, name_norm, address, address_norm, latitude, longitude, confidence`.

## M1 compatibility foundation

M1 added retained immutable builds, exact Overture source identity, deterministic pack
validation and replay of the current Android `android-overture-place-search-v1` query/ranking
contract. The current SARP regression remains the compatibility gate.

## M2 enrichment

M2 adds structured fields without renaming or removing any v1 field. Enriched packs declare
`roadpilot-search-enrichment-v2` and the additional `roadpilot-search-v2` runtime capability.

To keep the mobile sidecar compact, only small per-place references are appended to `places`.
Repeated data is normalized into companion tables:

- `address_contexts` retains postcode, locality, region and country while `places` retains freeform;
- `search_categories` stores each Overture category once;
- `place_categories` links a place row to basic/hierarchy/alternate taxonomy membership and hierarchy order;
- `search_sources` stores repeated provider/resource/version identity once while `places` retains the source record id;
- `places` also retains operating status plus direct basic/primary category references.

Category relations use SQLite integer row ids internally; RoadPilot's public Overture place id remains
unchanged in the v1 `places.id` column.

September 2026 Overture data uses `basic_category` and `taxonomy`; the removed legacy
`categories` object is accepted only as an input fallback for reproducible older-source rebuilds.

The enhanced runtime supports explicit category filtering and optional location-aware ranking.
Category-only queries can therefore drive Graph Studio POI overlays in M3. When an origin is
provided, nearby candidates receive a bounded proximity score; strong exact/prefix text matches
remain authoritative rather than being displaced by distance alone. Permanently closed records
are excluded from the enhanced runtime.

## Manifest compatibility

The manifest remains schema version 1 for Android compatibility. M2 packs additionally publish
optional `capabilities` and `enrichment` sections with the enhanced runtime contract and exact
categorized/structured-address/source-identified record counts. M1 manifests without those
sections remain valid.

Every enriched pack is validated twice:

1. the Android v1 runtime regression is replayed unchanged against the enriched database;
2. the enhanced category/proximity runtime is executed against a real categorized record in the
   retained SQLite file.

This makes enrichment additive: an M2 failure cannot silently replace the established Android
search behavior.
