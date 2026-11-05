#!/usr/bin/env python3
"""Full ORIGINAL Valhalla source archive census at the exact 25-km F8 seam.

All source GraphReader tiles/directed indexes are visited by the native C++
scanner. It emits all mode-usable original road edges that intersect a
conservative seam band; Python tests exact original source cutoff / receiving
nominal polygon and records EVERY candidate original GraphId separately.

Not an A-LAST route proof, B peer match, road name dedup, or release catalog.
No traversal of unrelated road continuations is performed.
"""
from __future__ import annotations
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import tempfile
import threading

from pyproj import Transformer
import shapely
from shapely.geometry import Point, box
from shapely.prepared import prep

from build_routing_region import parse_poly
from probe_native_f8_clipped_terminal import verified_buffer

SCHEMA = "roadpilot.f8-source-original-all-tile-cut-final-candidate-census"
SCOPE_VERSION = 4
NATIVE_SCHEMA = "roadpilot.f8-original-source-all-tiles-near-cut"
GRID_DEGREES = 0.01
BAND_METRES = 5000.0
MAX_CELLS = 200_000
MAX_ROWS = 1_000_000
MAX_LINE_BYTES = 100_000
MODES = {"auto": 1, "motorcycle": 1024}
SOURCE_DIR = Path(__file__).resolve().parent / "native-f8-full-receiver"
METRIC = Transformer.from_crs("EPSG:4326","EPSG:3035",always_xy=True)
LATLON = Transformer.from_crs("EPSG:3035","EPSG:4326",always_xy=True)


def digest(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise ValueError("Missing or symlinked source graph/native census input")
    with path.open("rb") as source:
        return "sha256:" + hashlib.file_digest(source, "sha256").hexdigest()


def build_native_binary(workspace: Path, *, supplied: Path | None = None) -> tuple[Path,dict]:
    """Reproducibly build from reviewed source on a Valhalla-3.6.3 dev host.

    If no compiler/libvalhalla-dev is installed this cannot silently fall
    back to a Python OSM-way scan or a previously successful Android route.
    """
    sources=[SOURCE_DIR/"CMakeLists.txt",SOURCE_DIR/"native_f8_full_source_cut_edges.cpp"]
    code_id=hashlib.sha256(
        b"".join(path.read_bytes() for path in sources)).hexdigest()
    root=workspace/"toolchain"/"native-f8-source-census"/code_id[:20]
    binary=supplied or root/"native_f8_full_source_cut_edges"
    if supplied is None and not binary.is_file():
        if not shutil.which("cmake"):
            raise RuntimeError("Native Valhalla 3.6.3 CMake toolchain unavailable")
        env=os.environ.copy()
        # Standard externally installed libvalhalla-dev is preferred.
        # The Legion's owner-controlled native 3.6.3 build is a fallback.
        leg=Path.home()/"valhalla-3.6.3-dev"/"build-native-ninja"
        if (leg/"libvalhalla.pc").is_file():
            env["PKG_CONFIG_PATH"]=str(leg) + (
                ":"+env["PKG_CONFIG_PATH"] if env.get("PKG_CONFIG_PATH") else "")
        root.mkdir(parents=True,exist_ok=True)
        def run(args):
            outcome=subprocess.run(args,env=env,stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT,text=True,timeout=180)
            if outcome.returncode:
                raise RuntimeError("Native source census compile failed: "+
                                   outcome.stdout[-600:])
        run(["cmake","-S",str(SOURCE_DIR),"-B",str(root),
             "-DCMAKE_BUILD_TYPE=Release"])
        run(["cmake","--build",str(root),"--target",
             "native_f8_full_source_cut_edges","-j","2"])
    if not binary.is_file() or binary.is_symlink() or not os.access(binary,os.X_OK):
        raise RuntimeError("Original source native census executable missing")
    verified=subprocess.run([str(binary),"--version"],capture_output=True,
                            text=True,timeout=10)
    if verified.returncode or verified.stdout.strip()!="3.6.3":
        raise ValueError("Native source graph scanner must use Valhalla 3.6.3")
    return binary,{"nativeSourceScannerSHA256":digest(binary),
                   "nativeScannerSourceSHA256":"sha256:"+code_id,
                   "nativeValhallaVersion":"3.6.3"}


def buffered_seam_cells(source_buffer, receiver_buffer) -> list[tuple[int,int]]:
    """Conservative grid of actual original 25km cut within peer core.

    A cell may be a superset of the exact band; never a positive proof.
    Interpolate original native shapes at <=0.004 degree to avoid lost
    long segments whose endpoints lie outside this band.
    """
    cut=source_buffer["polygon"].boundary
    # Use the overlap of ORIGINAL 25-km graph buffers. Some physically valid
    # Italy/Austria handoffs occur through Slovenia and never touch the peer's
    # nominal national border; the nominal core must NOT be a candidate filter.
    target=cut.buffer(BAND_METRES).intersection(
        receiver_buffer["polygon"].buffer(BAND_METRES))
    if target.is_empty:
        return []
    wgs=shapely.transform(target,LATLON.transform,interleaved=False)
    prepared=prep(wgs)
    low_x,low_y,high_x,high_y=wgs.bounds
    first_y=math.floor(low_y/GRID_DEGREES)
    last_y=math.floor(high_y/GRID_DEGREES)
    first_x=math.floor(low_x/GRID_DEGREES)
    last_x=math.floor(high_x/GRID_DEGREES)
    area=(last_x-first_x+1)*(last_y-first_y+1)
    if area>2_000_000:
        raise ValueError("Original seam scope too large for bounded census grid")
    cells=[]
    for la in range(first_y,last_y+1):
        for lo in range(first_x,last_x+1):
            if prepared.intersects(box(lo*GRID_DEGREES,la*GRID_DEGREES,
                                       (lo+1)*GRID_DEGREES,(la+1)*GRID_DEGREES)):
                cells.append((la,lo))
                if len(cells)>MAX_CELLS:
                    raise ValueError("Unbounded original 25km seam grid cells")
    return cells


def classify_near_cut(row: dict, own_buffer, peer_buffer, peer_core_metric) -> dict | None:
    """All real original edge/directions retained, no OSM way-name grouping."""
    gid=row.get("originalDirectedGraphId")
    if type(gid) is not int or gid<=0:
        raise ValueError("Malformed original source directed GraphId")
    start=row.get("directedStart")
    end=row.get("directedEnd")
    if (not isinstance(start,list) or len(start)!=2
            or not isinstance(end,list) or len(end)!=2
            or any(type(z) not in (int,float) or not math.isfinite(z)
                   for z in start+end)):
        raise ValueError("Invalid original directed source endpoints")
    pt=Point(METRIC.transform(end[1],end[0]))
    # All source finals already proven in the 25-km Italy/Austria ledger
    # are inside this true geometry scope, including non-deadend terminals.
    if (own_buffer["polygon"].boundary.distance(pt) > BAND_METRES
            or not peer_buffer["polygon"].covers(pt)):
        return None
    if (type(row.get("nativeDeadend")) is not bool or
            type(row.get("nativeIsRoad")) is not bool or
            type(row.get("nativeUse")) is not int):
        raise ValueError("Missing original source native road/use/topology flags")
    mask=row.get("forwardAccess")
    if type(mask) is not int or mask<0:
        raise ValueError("Missing original Valhalla forward access")
    mode=[m for m,bit in MODES.items() if mask & bit]
    if not mode:
        raise ValueError("Native full source candidate missing mode access")
    origin=Point(METRIC.transform(start[1],start[0]))
    start_inside=own_buffer["polygon"].covers(origin)
    end_inside=own_buffer["polygon"].covers(pt)
    if not end_inside:
        travel=("OUTWARD_CROSSING_OWN_SOURCE_25KM_CUT" if start_inside
                else "ALREADY_BEYOND_OWN_SOURCE_25KM_CUT")
    else:
        # Do NOT turn the tens of thousands of unrelated internal road
        # continuations into discovery obligations. Preserve only a nearby
        # original graph-local terminal as a separate, unproved hypothesis.
        if not row["nativeDeadend"] or (
                own_buffer["polygon"].boundary.distance(pt)>1000.0):
            return None
        travel="NEAR_SOURCE_CUT_INSIDE_NATIVE_TERMINAL_UNPROVED"
    return {
        "originalDirectedGraphId":gid,
        "originalEndNodeGraphId":row["originalEndNodeGraphId"],
        "originalWayIdAnnotationOnly":row["originalWayIdAnnotationOnly"],
        "originalDirectedStart":{"lat":start[0],"lng":start[1]},
        "originalDirectedEnd":{"lat":end[0],"lng":end[1]},
        "nativeOriginalGraphDeadend":row["nativeDeadend"],
        "nativeOriginalIsRoadAnnotationOnly":row["nativeIsRoad"],
        "nativeOriginalUseAnnotationOnly":row["nativeUse"],
        "insideReceivingNominalCoreAnnotationOnly":peer_core_metric.covers(pt),
        "insideReceivingOriginal25kmBuffer":True,
        "travelModes":mode,
        "outwardSourceCutClassification":travel,
        "originalSourceEndpointDistanceToCutMeters":round(
            own_buffer["polygon"].boundary.distance(pt),2),
        "nativeSourceLastTripLeg":"NOT_YET_PROVED",
        "nativeSourceModeFinalTopology":"NOT_YET_PROVED",
        "receiverFirstTripLeg":"NOT_YET_PROVED",
        "physicalRoadPerDirectionIdentity":"NOT_YET_ESTABLISHED",
        "noCandidateSuppressedByWayOrName":True,
    }


def scan_original_source(original_config: Path, cells: list[tuple[int,int]],
                         native: Path, own_buffer, peer_buffer, peer_core,
                         work: Path) -> dict:
    """Complete original GraphReader tiles FIRST, then accept no partial rows."""
    if not cells:
        return {"nativeTilesExhaustivelyRead":False,
                "status":"NO_25KM_BILATERAL_BUFFER_CUT",
                "allOriginalDirectedIdsVisited":0,"allScopedRoadEndpoints":[]}
    grid=work/"exact-seam-cells.txt"
    grid.write_text("".join(f"{la} {lo}\n" for la,lo in cells))
    prepared_core=shapely.transform(peer_core,METRIC.transform,interleaved=False)
    selected={}
    counts={"originalRoadsNearSeamNative":0,
            "originalRoadsWithSourceEndInActualPeerGraphOverlapWithin5kmOfSourceCut":0}
    native_complete=None
    proc=subprocess.Popen([str(native),str(original_config),str(grid)],
                          stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                          text=True,bufsize=1024*256)
    # A corrupt tile or GraphReader deadlock cannot hold an on-build scan
    # indefinitely; a killed/partial scan has no completion marker and may
    # never be committed as exact original directed-edge source evidence.
    watchdog=threading.Timer(900,proc.kill)
    watchdog.daemon=True
    watchdog.start()
    try:
        assert proc.stdout is not None
        for text in proc.stdout:
            if len(text)>MAX_LINE_BYTES:
                raise ValueError("Original source native census line oversized")
            row=json.loads(text)
            if row.get("type")=="complete":
                if native_complete is not None:
                    raise ValueError("Duplicate native archive completion record")
                native_complete=row
                continue
            if native_complete is not None or row.get("type")!="edge":
                raise ValueError("Unexpected native scanner record or incomplete stream")
            counts["originalRoadsNearSeamNative"]+=1
            if counts["originalRoadsNearSeamNative"]>MAX_ROWS:
                raise ValueError("Original source seam prefilter exceeded native bound")
            candidate=classify_near_cut(row,own_buffer,peer_buffer,prepared_core)
            if candidate:
                gid=candidate["originalDirectedGraphId"]
                if gid in selected:
                    raise ValueError("Duplicate original source directed GraphId in native tiles")
                selected[gid]=candidate
                counts["originalRoadsWithSourceEndInActualPeerGraphOverlapWithin5kmOfSourceCut"]+=1
        try:
            error=proc.stderr.read(2000) if proc.stderr else ""
            exitcode=proc.wait(timeout=20)
        except BaseException:
            proc.kill();proc.wait();raise
    except BaseException:
        proc.kill();proc.wait();raise
    finally:
        watchdog.cancel()
    if (exitcode!=0 or native_complete is None or
            native_complete.get("schema")!=NATIVE_SCHEMA or
            native_complete.get("valhallaVersion")!="3.6.3" or
            native_complete.get("allGraphReaderTilesExhaustivelyRead") is not True or
            native_complete.get("originalDirectedEdgesInsideSeamPrefilter")
              !=counts["originalRoadsNearSeamNative"]):
        raise ValueError("Original Valhalla native tile-source census incomplete: "+
                         error[-300:])
    return {"nativeTilesExhaustivelyRead":True,
            "status":"ALL_ORIGINAL_GRAPHREADER_DIRECTED_IDS_SCANNED",
            "allOriginalDirectedIdsVisited":native_complete[
                "allOriginalDirectedGraphIdsVisited"],
            "allOriginalRoadDirectedIdsVisited":native_complete[
                "routableRoadDirectedEdgesVisited"],
            "originalTileCount":native_complete["originalSourceTileCount"],
            "originalSeamGridCells":len(cells),
            "counts":counts,
            "allScopedRoadEndpoints":[selected[k] for k in sorted(selected)]}


def prepare_graph_reader_config(manifest_path: Path, work: Path,
                                temp: Path) -> tuple[Path,dict]:
    """Read exact MANIFEST graph TAR, never accidentally use stale work TAR."""
    manifest=json.loads(manifest_path.read_text())
    region=manifest["regionId"]
    graph=manifest_path.parent/manifest["artifact"]["fileName"]
    if digest(graph)!=manifest["graphFingerprint"]:
        raise ValueError("Retained original source graph TAR SHA changed")
    original=work/"work"/region/"build"/"valhalla.json"
    if not original.is_file() or original.is_symlink():
        raise ValueError("Missing Valhalla 3.6.3 GraphReader reference configuration")
    config=json.loads(original.read_text())
    if not isinstance(config.get("mjolnir"),dict):
        raise ValueError("Malformed Valhalla 3.6.3 routing configuration")
    config["mjolnir"]["tile_extract"]=str(graph)
    tiles=temp/"empty-original-tile-dir"
    tiles.mkdir()
    config["mjolnir"]["tile_dir"]=str(tiles)
    path=temp/"original-source-graphreader.json"
    path.write_text(json.dumps(config,separators=(",",":"))+"\n")
    return path,{"originalSourceGraphManifestSha256":digest(manifest_path),
                 "originalGraphTARSHA256":digest(graph),
                 "originalValhallaConfigTemplateSHA256":digest(original)}


def original_source_census(
    workspace: Path, source_manifest: Path, receiver_manifest: Path,
    pair: dict, side: str, *, native_binary: Path | None = None
) -> dict:
    """Census is immutable per graph+original buffered seam+peer core+tool SHA."""
    source=json.loads(source_manifest.read_text())
    peer=json.loads(receiver_manifest.read_text())
    source_region=source["regionId"]
    receiver_region=peer["regionId"]
    if (pair[side+"RegionId"]!=source_region or
            pair[("to" if side=="from" else "from")+"RegionId"]!=receiver_region):
        raise ValueError("Source-native census pair direction mismatch")
    bufferfile=workspace/"work"/source_region/"build"/"buffer.geojson"
    peer_buffer_file=workspace/"work"/receiver_region/"build"/"buffer.geojson"
    source_buffer=verified_buffer(bufferfile,source)
    receiver_buffer=verified_buffer(peer_buffer_file,peer)
    # The nominal peer Geofabrik polygon is retained by the SAME original
    # graph-index builder. No network requests or new OSM source data.
    peer_src_id=peer["source"]["primaryGeofabrikId"]
    poly=workspace/"work"/"cache"/("graph-index__"+peer_src_id.replace("/","__")+".poly")
    if poly.is_symlink() or not poly.is_file():
        raise ValueError("Missing retained ORIGINAL graph-index peer nominal core")
    core=parse_poly(poly)
    if core.is_empty or not core.is_valid:
        raise ValueError("Invalid original receiving core polygon")
    native,provenance=build_native_binary(workspace,supplied=native_binary)
    native_inputs={
        "sourceRegionId":source_region,"receiverRegionId":receiver_region,
        "sourceOriginalArchiveSHA256":source["graphFingerprint"],
        "receiverOriginalArchiveSHA256":peer["graphFingerprint"],
        "scopeVersion":SCOPE_VERSION,
        "source25kmBufferSHA256":digest(bufferfile),
        "receiver25kmBufferSHA256":digest(peer_buffer_file),
        "peerNominalCorePolygonSHA256":digest(poly),
        "originalSourceBoundaryFingerprint":pair[side+"BoundaryFingerprint"],
        "originalReceiverBoundaryFingerprint":pair[
            ("to" if side=="from" else "from")+"BoundaryFingerprint"],
        **provenance,
    }
    input_key=hashlib.sha256(json.dumps(native_inputs,sort_keys=True).encode()).hexdigest()
    dest=(workspace/"f8-production"/"source-census"/pair["pairId"]/
          source_region/input_key/"original-source-census.json")
    if dest.is_file() and not dest.is_symlink():
        present=json.loads(dest.read_text())
        if present.get("immutableOriginalSourceCensusInputs")!=native_inputs:
            raise ValueError("Stale source cut census fingerprint")
        return present
    cells=buffered_seam_cells(source_buffer,receiver_buffer)
    with tempfile.TemporaryDirectory(prefix="f8-full-original-source-census-") as folder:
        temp=Path(folder)
        config,config_prov=prepare_graph_reader_config(source_manifest,workspace,temp)
        print("F8_SOURCE_ALL_TILES_SCAN_START",source_region,"to",receiver_region,
              "original 25km seam grid cells",len(cells),flush=True)
        scan=scan_original_source(config,cells,native,source_buffer,receiver_buffer,core,temp)
    # The mutable original TAR, buffer and peer core must not have changed.
    if (digest(source_manifest.parent/source["artifact"]["fileName"])!=
            source["graphFingerprint"] or
            digest(native)!=native_inputs["nativeSourceScannerSHA256"] or
            digest(bufferfile)!=native_inputs["source25kmBufferSHA256"] or
            digest(peer_buffer_file)!=native_inputs["receiver25kmBufferSHA256"] or
            digest(poly)!=native_inputs["peerNominalCorePolygonSHA256"]):
        raise ValueError("Original graph, 25km cutoff or peer nominal core changed")
    candidate=scan.get("allScopedRoadEndpoints",[])
    data={"schema":SCHEMA,"version":4,"pairId":pair["pairId"],
          "sourceCensusArtifact":str(dest),
          "direction":"from-to" if side=="from" else "to-from",
          "immutableOriginalSourceCensusInputs":native_inputs,
          "originalValhallaGraphReaderConfigProvenance":config_prov,
          **scan,
          "allPhysicalRoadPerDirectionFinalEdgesDiscovered":False,
          "originalValhallaSourceLastTripLegProof":"NOT_YET_RUN",
          "receivingGraphOriginalFirstEdgeProof":"NOT_YET_RUN",
          "unrelatedNativeRoadContinuationsDevelopmentRequired":False,
          "sourceDiscoveryComplete":False,"productionPublication":"BLOCKED"}
    # Atomic no-overwrite durable result; no native partial output can commit.
    from run_f8_bilateral_after_build import immutable_json
    immutable_json(dest,data)
    print("F8_SOURCE_ALL_TILES_CENSUS",source_region,"to",receiver_region,
          "all original IDs",data.get("allOriginalDirectedIdsVisited"),
          "near-cut exact road/direction candidates",len(candidate),
          "source final still UNVERIFIED",flush=True)
    return data
