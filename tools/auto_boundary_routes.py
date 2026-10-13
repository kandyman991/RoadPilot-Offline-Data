"""Discover real nominal-border road crossings using a freshly built Valhalla graph.

No coordinates are fabricated into configs. A candidate only passes if normal
Valhalla routing returns a drivable trip whose decoded road geometry actually
crosses the nominal Geofabrik boundary. Failure blocks package publication.
"""
from __future__ import annotations

import json
import math
import subprocess

from pyproj import CRS, Transformer
from shapely.geometry import LineString, Point
from shapely.ops import transform


def decode_polyline6(encoded: str) -> list[tuple[float, float]]:
    """Valhalla precision-6 shape: return (longitude, latitude) tuples."""
    positions = []
    latitude = longitude = 0
    index = 0
    while index < len(encoded):
        values = []
        for _ in range(2):
            shift = result = 0
            while True:
                if index >= len(encoded):
                    raise ValueError("Truncated encoded Valhalla shape")
                byte = ord(encoded[index]) - 63
                index += 1
                if byte < 0 or shift > 35:
                    raise ValueError("Invalid encoded Valhalla shape")
                result |= (byte & 31) << shift
                if not byte & 32:
                    break
                shift += 5
            values.append(~(result >> 1) if result & 1 else result >> 1)
        latitude += values[0]
        longitude += values[1]
        positions.append((longitude / 1_000_000, latitude / 1_000_000))
    return positions


def boundary_candidates(nominal, buffer_km: float, neighbor_geometries=(),
                        maximum: int = 160):
    """Metric-normal samples spanning the real polygon; no guess about roads.

    Prefer outside points inside a known adjoining Geofabrik extract, avoiding
    coastal segments where a vehicle route cannot exist. Geographic points
    are candidates only; Valhalla must prove every accepted crossing.
    """
    center = nominal.centroid
    local = CRS.from_proj4(
        f"+proj=aeqd +lat_0={center.y} +lon_0={center.x} +datum=WGS84 +units=m +no_defs"
    )
    forward = Transformer.from_crs("EPSG:4326", local, always_xy=True).transform
    backward = Transformer.from_crs(local, "EPSG:4326", always_xy=True).transform
    metric = transform(forward, nominal)
    outline = metric.boundary
    if outline.is_empty or outline.length == 0:
        return
    neighbors = [transform(forward, other) for other in neighbor_geometries if not other.is_empty]
    # Step around even very large regions, bounded to protect probe time.
    segments = min(maximum, max(24, math.ceil(outline.length / 8500)))
    # Three alternatives for sparse rural road networks, still within the
    # configured border buffer on the outside.
    for offset in (900.0, 2500.0):
        if offset > buffer_km * 1000 * 0.65:
            continue
        for i in range(segments):
            d = (i + 0.5) * outline.length / segments
            p0 = outline.interpolate(max(0, d - 25))
            p1 = outline.interpolate(min(outline.length, d + 25))
            dx, dy = p1.x - p0.x, p1.y - p0.y
            length = math.hypot(dx, dy)
            if length < 0.000001:
                continue
            nx, ny = -dy / length, dx / length
            p = outline.interpolate(d)
            first = Point(p.x + nx * offset, p.y + ny * offset)
            second = Point(p.x - nx * offset, p.y - ny * offset)
            first_inside = metric.covers(first)
            second_inside = metric.covers(second)
            if first_inside == second_inside:
                continue
            inside, outside = (first, second) if first_inside else (second, first)
            if neighbors and not any(g.covers(outside) for g in neighbors):
                continue
            lng_a, lat_a = backward(inside.x, inside.y)
            lng_b, lat_b = backward(outside.x, outside.y)
            yield ({"lat": lat_a, "lng": lng_a},
                   {"lat": lat_b, "lng": lng_b})


def prove_crossing(response: dict, nominal, start: dict, end: dict) -> bool:
    trip = response.get("trip")
    if not isinstance(trip, dict) or trip.get("status", 0) not in (0, None):
        return False
    legs = trip.get("legs")
    if not isinstance(legs, list) or not legs:
        return False
    road = []
    try:
        for leg in legs:
            piece = decode_polyline6(leg.get("shape", ""))
            if len(piece) < 2:
                return False
            road.extend(piece[1:] if road else piece)
    except (ValueError, TypeError, AttributeError):
        return False
    if len(road) < 2:
        return False
    line = LineString(road)
    # Reject a distant snapped road or a long detour that happens to cross
    # some other piece of this boundary. Both projected endpoints must stay
    # within five km of the proposed border point.
    for actual, requested in [(road[0], start), (road[-1], end)]:
        km = math.hypot((actual[0] - requested["lng"]) * 111.3 *
                        math.cos(math.radians(requested["lat"])),
                        (actual[1] - requested["lat"]) * 111.3)
        if km > 5:
            return False
    summary = trip.get("summary") or {}
    if isinstance(summary, dict) and float(summary.get("length", 0)) > 80:
        return False
    # Check the actual routed road, not merely the requested coordinates.
    if not line.intersects(nominal.boundary):
        return False
    start_inside = nominal.covers(Point(float(start["lng"]), float(start["lat"])))
    end_inside = nominal.covers(Point(float(end["lng"]), float(end["lat"])))
    if start_inside == end_inside:
        return False
    # Routing may snap away from requested positions: require correlated road
    # endpoints to occupy the same respective nominal sides.
    actual_start_inside = nominal.covers(Point(*road[0]))
    actual_end_inside = nominal.covers(Point(*road[-1]))
    return actual_start_inside == start_inside and actual_end_inside == end_inside


def discover_border_route(config_path, nominal, buffer_km, neighbor_geometries=(),
                          max_probes: int = 96, run_service=None) -> dict:
    """Return first Valhalla-proved crossing or raise a diagnostic error."""
    if run_service is None:
        def run_service(request):
            output = subprocess.run(
                ["valhalla_service", str(config_path), "route",
                 json.dumps(request, separators=(",", ":"))],
                capture_output=True, text=True, check=False,
            )
            if output.returncode != 0:
                return None
            # pyvalhalla sometimes writes an informational launcher line.
            cleaned = "\n".join(line for line in output.stdout.splitlines()
                                if not line.startswith("[INFO] Running "))
            try:
                return json.loads(cleaned.strip())
            except ValueError:
                return None

    attempts = 0
    for inside, outside in boundary_candidates(nominal, buffer_km, neighbor_geometries):
        if attempts >= max_probes:
            break
        attempts += 1
        if attempts % 12 == 0:
            print(f"auto border discovery: checked {attempts} actual Valhalla routes…",
                  flush=True)
        request = {
            "locations": [
                {"lat": inside["lat"], "lon": inside["lng"], "radius": 2000},
                {"lat": outside["lat"], "lon": outside["lng"], "radius": 2000},
            ],
            "costing": "motorcycle",
            "directions_options": {"units": "kilometers"},
        }
        result = run_service(request)
        if isinstance(result, dict) and prove_crossing(result, nominal, inside, outside):
            print(f"auto border route: Valhalla proved a road crossing in {attempts} probes",
                  flush=True)
            return {
                "name": "auto-valhalla-border",
                "kind": "border",
                "costing": "motorcycle",
                "start": inside,
                "end": outside,
                "passed": True,
                "source": "automatic-valhalla-proof",
                "probes": attempts,
                "summary": result["trip"].get("summary", {}),
            }
    raise RuntimeError(
        f"Automatic road-border discovery found no Valhalla-proved crossing "
        f"after {attempts} probes. Built tiles remain available locally; use "
        f"the map's Start/End pins to specify an actual crossing and retry. "
        f"No unvalidated routing package was published."
    )
