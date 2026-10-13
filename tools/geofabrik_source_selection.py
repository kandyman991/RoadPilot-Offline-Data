"""Select only Geofabrik source PBFs adding real regional buffer coverage.

Geofabrik includes overlapping thematic umbrella extracts (e.g. Alps, DACH)
alongside individual region leaves. Selecting every intersecting extract
needlessly downloads/merges huge duplicate OSM snapshots. Decide coverage with
exact .poly polygons, never by names or hard-coded country exceptions.
"""
from __future__ import annotations

from shapely.geometry.base import BaseGeometry


def choose_buffer_sources(pbfs: list[dict], primary_id: str,
                          nominal: BaseGeometry, buffered: BaseGeometry,
                          geometries: dict[str, BaseGeometry]) -> tuple[list[dict], list[str]]:
    """Pick primary plus the smallest source polygons needed to cover buffer.

    A source is discarded only if its exact polygon contributes no meaningful
    NEW coverage inside the buffered region. Prefer smaller source geometries,
    so giant overlapping umbrella PBFs are skipped when adjacent leaves cover
    the same geography. The tiny numerical tolerance addresses polygon
    floating-point slivers; it is intentionally < 1e-8 of buffer area.
    """
    primary = [item for item in pbfs if item["id"] == primary_id]
    if len(primary) != 1:
        raise ValueError("Exactly one primary Geofabrik PBF is required.")
    candidates = [item for item in pbfs if item["id"] != primary_id]
    clipped: dict[str, BaseGeometry] = {}
    for item in candidates:
        source_id = item["id"]
        geometry = geometries[source_id]
        clipped[source_id] = geometry.intersection(buffered)
    candidates.sort(key=lambda item: (
        geometries[item["id"]].area, item["id"]
    ))
    coverage = nominal.intersection(buffered)
    selected = list(primary)
    skipped = []
    # Use an extremely small tolerance so legitimate narrow boundary coverage
    # remains included; numeric slivers alone may be safely ignored.
    min_area = max(buffered.area * 1e-10, 1e-13)
    for item in candidates:
        source_id = item["id"]
        new_coverage = clipped[source_id].difference(coverage)
        if new_coverage.is_empty or new_coverage.area <= min_area:
            skipped.append(source_id)
            continue
        selected.append(item)
        coverage = coverage.union(clipped[source_id])
    return selected, skipped
