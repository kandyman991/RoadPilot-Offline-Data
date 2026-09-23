# RoadPilot Offline Data

Public build and distribution repository for RoadPilot offline datasets.

This repository is intentionally separate from the private RoadPilot application source. Generated regional datasets are **not** bundled in the APK and are **not** committed to Git. They are built from public upstream data, validated, described by versioned manifests, and published as downloadable release assets.

## Responsibilities

RoadPilot-Offline-Data will own the production and publication of offline data consumed by RoadPilot, including:

- Overture Places regional search sidecars;
- future downloadable map packs;
- future prebuilt routing/data artifacts where appropriate;
- versioned region metadata and manifest schemas;
- validation tooling and reproducible data-build workflows.

The RoadPilot app remains responsible for downloading, verifying, activating, updating, and deleting installed datasets.

## First dataset

The first published dataset is the Overture Places sidecar for `italy-nord-est`.

The existing RoadPilot runtime contract is preserved:

- manifest schema: `1`
- database schema: `roadpilot-overture-v1`
- database file: `italy-nord-est-v1.sqlite`
- manifest file: `italy-nord-est-v1.json`
- validation target: SARP
- coverage: longitude `10.40..13.40`, latitude `44.50..46.80`

The generated SQLite database and manifest will be published as assets on the `roadpilot-overture-packs` release.

## Repository layout

```text
.github/workflows/       build / validation / publication automation
config/regions/          source-of-truth regional dataset configuration
schemas/                 machine-readable manifest/config contracts
tools/                   deterministic builders and validators
dist/                    generated output (ignored by Git)
```

## Distribution rule

Application CI must never download Overture source data or embed regional place databases in the APK. RoadPilot downloads published regional packs independently and verifies size, SHA-256, schema, region identity, and record count before activation.
