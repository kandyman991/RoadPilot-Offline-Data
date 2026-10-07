#!/usr/bin/env python3
"""Shared RoadPilot PMTiles visual-pack inspection helpers."""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any

import mapbox_vector_tile
from pmtiles.reader import MmapSource, Reader, all_tiles
from pmtiles.tile import Compression, TileType


class VisualPackError(RuntimeError):
    pass


def _decompress_tile(raw: bytes, compression: Compression) -> bytes:
    if compression == Compression.NONE:
        return raw
    if compression == Compression.GZIP:
        return gzip.decompress(raw)
    raise VisualPackError(
        f"Unsupported PMTiles tile compression for RoadPilot visual validation: {compression.name}"
    )


def metadata_layer_ids(metadata: dict[str, Any]) -> list[str]:
    layers = metadata.get("vector_layers")
    if not isinstance(layers, list):
        return []
    result: list[str] = []
    for item in layers:
        if isinstance(item, dict):
            layer_id = item.get("id")
            if isinstance(layer_id, str) and layer_id:
                result.append(layer_id)
    return sorted(set(result))


def inspect_pmtiles(
    path: Path,
    *,
    required_layers: set[str] | None = None,
    max_tiles_to_decode: int = 5000,
) -> dict[str, Any]:
    if not path.is_file():
        raise VisualPackError(f"PMTiles artifact does not exist: {path}")
    if path.stat().st_size <= 127:
        raise VisualPackError(f"PMTiles artifact is too small: {path}")

    required_layers = set(required_layers or ())
    observed_layers: set[str] = set()
    decoded_tiles = 0

    try:
        with path.open("rb") as handle:
            source = MmapSource(handle)
            reader = Reader(source)
            header = reader.header()
            metadata = reader.metadata()
            if header["tile_type"] != TileType.MVT:
                raise VisualPackError(
                    f"PMTiles tile type is {header['tile_type'].name}, expected MVT"
                )

            metadata_layers = set(metadata_layer_ids(metadata))
            for _, raw_tile in all_tiles(source):
                if decoded_tiles >= max_tiles_to_decode and required_layers <= observed_layers:
                    break
                payload = _decompress_tile(raw_tile, header["tile_compression"])
                try:
                    decoded = mapbox_vector_tile.decode(payload)
                except Exception as exc:
                    raise VisualPackError(
                        f"Could not decode MVT tile #{decoded_tiles + 1}: {exc}"
                    ) from exc
                if not isinstance(decoded, dict):
                    raise VisualPackError("Decoded MVT tile was not a layer object")
                observed_layers.update(str(name) for name in decoded.keys())
                decoded_tiles += 1
                if required_layers and required_layers <= observed_layers and decoded_tiles >= 8:
                    break

            if header["addressed_tiles_count"] <= 0:
                raise VisualPackError("PMTiles archive contains no addressed tiles")
            if decoded_tiles <= 0:
                raise VisualPackError("PMTiles archive contained no decodable MVT tiles")
            missing = sorted(required_layers - observed_layers)
            if missing:
                raise VisualPackError(
                    "Required layers were not observed in decoded PMTiles tiles: "
                    + ", ".join(missing)
                )

            min_lng = header["min_lon_e7"] / 10_000_000.0
            min_lat = header["min_lat_e7"] / 10_000_000.0
            max_lng = header["max_lon_e7"] / 10_000_000.0
            max_lat = header["max_lat_e7"] / 10_000_000.0
            if not (-180 <= min_lng <= max_lng <= 180):
                raise VisualPackError("PMTiles longitude bounds are invalid")
            if not (-90 <= min_lat <= max_lat <= 90):
                raise VisualPackError("PMTiles latitude bounds are invalid")
            if not (0 <= header["min_zoom"] <= header["max_zoom"] <= 24):
                raise VisualPackError("PMTiles zoom range is invalid")

            return {
                "version": int(header["version"]),
                "tileType": header["tile_type"].name,
                "tileCompression": header["tile_compression"].name,
                "tileCount": int(header["addressed_tiles_count"]),
                "tileEntries": int(header["tile_entries_count"]),
                "tileContents": int(header["tile_contents_count"]),
                "minZoom": int(header["min_zoom"]),
                "maxZoom": int(header["max_zoom"]),
                "bounds": {
                    "minLat": min_lat,
                    "maxLat": max_lat,
                    "minLng": min_lng,
                    "maxLng": max_lng,
                },
                "metadataLayers": sorted(metadata_layers),
                "observedLayers": sorted(observed_layers),
                "decodedTileCount": decoded_tiles,
                "metadata": metadata,
            }
    except VisualPackError:
        raise
    except Exception as exc:
        raise VisualPackError(f"Could not inspect PMTiles archive {path}: {exc}") from exc


def load_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VisualPackError(f"Could not read {label} {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise VisualPackError(f"{label} must be a JSON object")
    return value
