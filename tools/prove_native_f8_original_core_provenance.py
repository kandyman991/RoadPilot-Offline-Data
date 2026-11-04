#!/usr/bin/env python3
"""Prove the retained ORIGINAL region cores generated the exact graph buffers.

Reconstruct the build's 25km-source GeoJSON *byte-for-byte* from archived .poly
bytes and compare against the routing manifests. The nominal region cores can
OVERLAP and have noncoincident boundaries; this evidence NEVER picks a road,
a physical frontier, a connector or a last directed edge.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile

from pyproj import CRS, Transformer
from shapely.geometry import mapping
from shapely.ops import transform

from native_f8_inputs import parse_poly
from census_native_f8_original_archive_tiles import SCHEMA as ARCHIVE_SCHEMA

SCHEMA = "roadpilot.f8-original-source-core-buffer-byte-provenance"
VERSION = 1
SIDES = ("from-to", "to-from")


def sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def checked(path: Path, expected: str) -> dict:
    if (not isinstance(expected, str) or len(expected) != 71
            or not expected.startswith("sha256:")):
        raise ValueError("Original source evidence must have explicit SHA256 pin")
    raw = path.read_bytes()
    if sha(raw) != expected:
        raise ValueError("SHA-verified original source archive census changed")
    result = json.loads(raw)
    if not isinstance(result, dict):
        raise ValueError("Missing original graph archive census")
    return result


def reproduce_original_buffer(poly: Path, km: float) -> tuple[bytes, object]:
    """Use EXACT unmodified build_routing_region.py polygon/buffer recipe."""
    if type(km) not in (float, int) or km != 25.0:
        raise ValueError("Original region build requires the authorized 25km buffer")
    nominal = parse_poly(poly)
    if nominal.is_empty or not nominal.is_valid or nominal.geom_type not in ("Polygon", "MultiPolygon"):
        raise ValueError("Invalid original nominal Geofabrik core polygon")
    center = nominal.centroid
    local_crs = CRS.from_proj4(
        f"+proj=aeqd +lat_0={center.y} +lon_0={center.x} +datum=WGS84 +units=m +no_defs"
    )
    forward = Transformer.from_crs("EPSG:4326",local_crs,always_xy=True).transform
    backward = Transformer.from_crs(local_crs,"EPSG:4326",always_xy=True).transform
    buffered = transform(
        backward, transform(forward, nominal).buffer(km * 1000.0))
    feature = {
        "type":"Feature",
        "properties":{"borderBufferKm":float(km)},
        "geometry":mapping(buffered),
    }
    # The original source build writes exactly this serialization.
    result = json.dumps(feature,separators=(",",":")).encode("utf-8")
    return result,nominal


def inspect(archive: dict, manifests: dict, inputs: dict) -> dict:
    """Check complete archive->routing manifests->core polygon byte identity."""
    if (archive.get("schema") != ARCHIVE_SCHEMA or archive.get("version") != 1
            or archive.get("originalGraphArchiveTileInventory") !=
            "ALL_GRAPHREADER_GETTILESET_TILES_ENUMERATED"
            or archive.get("productionPublication") != "BLOCKED"):
        raise ValueError("Unverified original full archive source inventory")
    fingerprints = archive.get("sourceGraphFingerprints")
    provenance = archive.get("immutableOriginalSourceSHA256")
    if not isinstance(fingerprints,dict) or not isinstance(provenance,dict):
        raise ValueError("Missing original graph fingerprint provenance")
    for key in ("from-to","to-from"):
        if key not in (archive.get("directions") or {}):
            raise ValueError("Missing original source direction in archive census")
    proofs = {}
    cores = {}
    for direction,side,manifest_key in (("from-to","from","from-manifest"),
                                       ("to-from","to","to-manifest")):
        original = manifests.get(side)
        details = inputs.get(side)
        if not isinstance(original,dict) or not isinstance(details,dict):
            raise ValueError("Missing original regional graph build provenance")
        manifest_bytes = details["manifest"].read_bytes()
        source = original.get("source")
        if (sha(manifest_bytes) != provenance.get(manifest_key)
                or not isinstance(source,dict)
                or original.get("schema")!="roadpilot-routing-pack"
                or original.get("schemaVersion") != 1
                or original.get("valhallaVersion") != "3.6.3"
                or original.get("graphFingerprint") != fingerprints.get(side)):
            raise ValueError("Original graph build archive/manifest provenance changed")
        saved_buffer = details["buffer"].read_bytes()
        expected_buffer_sha = source.get("bufferGeoJsonSha256")
        if (not isinstance(expected_buffer_sha,str) or
                sha(saved_buffer) != "sha256:"+expected_buffer_sha.removeprefix("sha256:")):
            raise ValueError("Retained original 25km buffer fingerprint changed")
        if sha(saved_buffer) != provenance.get(side+"-buffer"):
            raise ValueError("Original archive census/retained buffer SHA mismatch")
        recreated, core = reproduce_original_buffer(details["core"],source.get("borderBufferKm"))
        if recreated != saved_buffer:
            raise ValueError("Original core .poly does not reproduce graph buffer byte-for-byte")
        cores[side]=core
        proofs[direction]={
            "originalRegionId": original["regionId"],
            "originalGraphArchiveSHA256": original["graphFingerprint"],
            "originalNominalCorePolySHA256":sha(details["core"].read_bytes()),
            "originalNominalCorePolygonSourceURL":source["polygonUrl"],
            "originalBufferSha256":sha(saved_buffer),
            "originalBufferReproducedExactlyFromCore":True,
            "reconstructionByteCount":len(recreated),
            "coreMustNotSelectPhysicalRoadDirection":True,
        }
    from shapely.ops import transform as shapely_transform
    from probe_native_f8_clipped_terminal import CRS as PROJECT
    a=shapely_transform(PROJECT.transform,cores["from"])
    b=shapely_transform(PROJECT.transform,cores["to"])
    overlap=a.intersection(b)
    boundary_overlap=a.boundary.intersection(b.boundary)
    return {
        "schema":SCHEMA,"version":VERSION,
        "pairId":archive["pairId"],
        "sourceArchiveGraphFingerprints":fingerprints,
        "directions":proofs,
        "originalCoreOverlapSquareKilometres":round(overlap.area/1e6,3),
        "exactCoincidentOriginalCoreBoundaryKilometres":round(
            boundary_overlap.length/1e3,3),
        "geofabrikNominalCoreBorderIsUniquePhysicalFrontier":"NOT_VERIFIED",
        "allSourceRoadDirectionsMappedToOneFinalOriginalGraphId":"NOT_VERIFIED",
        "receivingGraphCorrelation":"NOT_STARTED",
        "productionPublication":"BLOCKED",
    }


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive",type=Path,required=True)
    p.add_argument("--expected-archive-sha256",required=True)
    for x in ("from","to"):
        for name in ("core","buffer","manifest"):
            p.add_argument("--"+x+"-"+name,type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    if a.output.exists() or a.output.is_symlink():
        raise ValueError("Refuse to overwrite immutable original core provenance")
    archive=checked(a.archive,a.expected_archive_sha256)
    inputs={region:{kind:getattr(a,region+"_"+kind)
                    for kind in ("core","buffer","manifest")}
            for region in ("from","to")}
    original={region:json.loads(data["manifest"].read_text(encoding="utf-8"))
              for region,data in inputs.items()}
    document=inspect(archive,original,inputs)
    document["immutableOriginalSourceSHA256"]={
        "archive":a.expected_archive_sha256,
        **{region+"-"+kind:sha(path.read_bytes())
           for region,files in inputs.items() for kind,path in files.items()}
    }
    # Rechecking prevents stale/change-in-place provenance during computation.
    for region,files in inputs.items():
        for kind,path in files.items():
            if sha(path.read_bytes()) != document["immutableOriginalSourceSHA256"][region+"-"+kind]:
                raise ValueError("Original source core/buffer/manifest changed during verification")
    if sha(a.archive.read_bytes()) != a.expected_archive_sha256:
        raise ValueError("Original full source archive census changed during verification")
    a.output.parent.mkdir(parents=True,exist_ok=True)
    staged=None
    try:
        with tempfile.NamedTemporaryFile("w",encoding="utf8",delete=False,
                                         prefix=".f8-core-provenance-",
                                         dir=a.output.parent) as f:
            staged=Path(f.name)
            json.dump(document,f,indent=2,allow_nan=False)
            f.write("\n")
        if a.output.exists() or a.output.is_symlink():
            raise ValueError("Concurrent original core source proof publication")
        os.link(staged,a.output)
    finally:
        if staged: staged.unlink(missing_ok=True)
    print("Exact original buffered source bytes reproduced; nominal core overlap",
          document["originalCoreOverlapSquareKilometres"],"km2;",
          "original physical border uniqueness NOT_VERIFIED.")
    return 0


if __name__=="__main__":
    try: raise SystemExit(main())
    except (OSError,ValueError,KeyError,TypeError,IndexError) as e:
        raise SystemExit("F8_ORIGINAL_CORE_PROVENANCE_ERROR: "+str(e)[:400])
