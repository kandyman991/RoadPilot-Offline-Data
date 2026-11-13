#!/usr/bin/env python3
"""Owner-local GUI bridge for the existing, independently proven D-017 producer.

This tool DOES NOT discover roads, change graph files, infer physical lineage or
issue any RoadPilot Android public READY artifact. It consumes retained original
SHA-bound native A→exact X→directed B evidence and regenerates the canonical
audit/dispositions, blocked preflight and GRAPH_STUDIO_PRIVATE_READY catalog.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_SCHEMA = ROOT / "schemas/f8-graph-studio-native-private-catalog.schema.json"
TOKEN = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,95}\Z")
SHA = re.compile(r"sha256:[a-f0-9]{64}\Z")
SUFFIX = "-connections-BLOCKED.json"
NATIVE = "-native-receiver-evidence.json.gz"
SCHEMA_NAME = "roadpilot.f8-graph-studio-private-validated-catalog"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read(path: Path) -> dict:
    obj = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(obj, dict), f"Expected JSON object: {path.name}")
    return obj


def digest(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(4 * 1024 * 1024), b""):
            sha.update(block)
    return "sha256:" + sha.hexdigest()


def retained(manifest: Path) -> tuple[str, str, Path, dict]:
    require(manifest.is_file() and not manifest.is_symlink(), "Retained routing manifest missing or symlinked")
    obj = read(manifest)
    require(obj.get("schema") == "roadpilot-routing-pack", "Not a retained original routing pack")
    region = str(obj.get("regionId", ""))
    version = str(obj.get("packageVersion", ""))
    require(TOKEN.fullmatch(region) is not None and ".." not in region, "Invalid source region")
    require(TOKEN.fullmatch(version) is not None and ".." not in version, "Invalid source version")
    artifact = obj.get("artifact") or {}
    filename = str(artifact.get("fileName", ""))
    require(TOKEN.fullmatch(filename) is not None and ".." not in filename,
            "Unsafe original graph archive filename")
    sha = artifact.get("sha256")
    require(isinstance(sha, str) and SHA.fullmatch("sha256:"+sha.replace("sha256:","")) is not None,
            "Retained original archive fingerprint missing")
    sha = "sha256:"+sha.replace("sha256:", "")
    require(obj.get("graphFingerprint") == sha, "Original archive fingerprint disagrees with manifest")
    tar = manifest.parent / filename
    require(tar.is_file() and not tar.is_symlink(), "Original graph archive missing or symlinked")
    return region, version, tar, obj


def validate_identity(a: dict, b: dict, original: dict, evidence: dict) -> None:
    require(original.get("pairId") == f"{a['regionId']}__{b['regionId']}",
            "Native A→B candidate belongs to a different directed pair")
    expected = {"from": a["graphFingerprint"], "to": b["graphFingerprint"]}
    require(original.get("graphFingerprints") == expected, "Native pair archive identity is stale")
    require(evidence.get("sourceRegionId") == a["regionId"]
            and evidence.get("receiverRegionId") == b["regionId"],
            "Native original edge evidence belongs to another directed pair")
    require(evidence.get("sourceGraphFingerprint") == expected["from"] and
            evidence.get("receiverGraphFingerprint") == expected["to"],
            "Native original A/B graph fingerprint mismatch")
    for key, manifest, evidence_key in (("source", a, "sourceBufferFingerprint"),
                                        ("receiver", b, "receiverBufferFingerprint")):
        expected_buffer = str((manifest.get("source") or {}).get("bufferGeoJsonSha256") or "")
        require(bool(re.fullmatch(r"[a-f0-9]{64}", expected_buffer))
                and evidence.get(evidence_key) == "sha256:" + expected_buffer,
                f"{key} graph original 25-km buffer mismatch")
    for manifest, key in ((a,"sourceIndexFingerprint"), (b,"receiverIndexFingerprint")):
        ind = manifest.get("graphIndex") or {}
        require(evidence.get(key) == "sha256:"+str(ind.get("sha256","")),
                "Original graph index SHA mismatch")


def locate_evidence(workspace: Path, pair: str, explicit: Path | None) -> tuple[Path,Path] | None:
    """Bounded discovery of existing evidence paths, never new road scanning."""
    if explicit:
        roots = [explicit]
    else:
        roots = [workspace / "f8-native-evidence",
                 workspace / "diagnostics" / "f8-production"]
    candidates: list[tuple[float,Path,Path]]=[]
    for root in roots:
        if not root.is_dir():
            continue
        # Only original packed native evidence in owner-controlled files.
        # Do not walk the huge graph/toolchain/workspace trees.
        for folder in [root, *[p for p in root.iterdir() if p.is_dir() and not p.is_symlink()]]:
            for catalog in folder.glob(pair+"*"+SUFFIX):
                base=catalog.name[:-len(SUFFIX)]
                native=folder/(base+NATIVE)
                if catalog.is_symlink() or native.is_symlink():
                    continue
                if not catalog.is_file() or not native.is_file():
                    continue
                candidates.append((max(catalog.stat().st_mtime, native.stat().st_mtime),
                                   catalog,native))
    if not candidates:
        return None
    _,original,native=max(candidates, key=lambda x:(x[0],str(x[1])))
    return original,native


def prerequisites(a_manifest: Path, b_manifest: Path, a: dict, b: dict) -> tuple[dict,dict]:
    source_workspace = a_manifest.parents[2]
    require(source_workspace == b_manifest.parents[2],
            "Original retained A/B manifests are not from the same Graph Studio workspace")
    retained_inputs = []
    for manifest, obj in ((a_manifest,a),(b_manifest,b)):
        region = obj["regionId"]
        directory = source_workspace / "work" / region / "build"
        valhalla = directory/"valhalla.json"
        buffer = directory/"buffer.geojson"
        index_name = str((obj.get("graphIndex") or {}).get("fileName") or "")
        require(TOKEN.fullmatch(index_name) is not None and ".." not in index_name,
                "Retained graph index filename is invalid")
        index = manifest.parent/index_name
        require(valhalla.is_file() and buffer.is_file() and index.is_file()
                and not valhalla.is_symlink() and not buffer.is_symlink() and not index.is_symlink(),
                f"Original native configuration, buffer or graph index missing for {region}")
        require(digest(buffer) == "sha256:"+obj["source"]["bufferGeoJsonSha256"],
                f"Original 25-km buffer no longer matches the graph archive of {region}")
        require(digest(index) == "sha256:"+obj["graphIndex"]["sha256"],
                f"Original graph index no longer matches retained {region}")
        require(obj.get("valhallaVersion") == "3.6.3",
                "Current native final-edge generator requires the original Valhalla 3.6.3 archive")
        retained_inputs.append({"manifest":manifest,"index":index,"buffer":buffer,
                                "valhalla":valhalla,"region":region})
    return retained_inputs[0],retained_inputs[1]


def native_reader(workspace: Path) -> Path:
    """Build the EXISTING pinned D-017 original-native reader, not a new matcher."""
    build_dir=workspace/"toolchain"/"native-f8-final-reader"
    binary=build_dir/"native_f8_boundary_final_edges"
    if not binary.is_file():
        source=ROOT/"tools"/"native-f8-boundary-final"
        require((source/"CMakeLists.txt").is_file(),
                "Original D-017 native reader source is absent from the packaged pipeline")
        build_dir.mkdir(parents=True,exist_ok=True)
        env=os.environ.copy()
        possible_prefixes=[
            Path.home()/".local/opt"/"valhalla-3.6.3-native"/"lib/pkgconfig",
            workspace/"toolchain"/"valhalla-3.6.3"/"lib/pkgconfig",
            Path.home()/".local/lib/pkgconfig",
        ]
        pkg_paths=[str(p) for p in possible_prefixes
                   if (p/"libvalhalla.pc").is_file()]
        if pkg_paths:
            env["PKG_CONFIG_PATH"]=os.pathsep.join(
                pkg_paths+([env["PKG_CONFIG_PATH"]] if env.get("PKG_CONFIG_PATH") else []))
        version=subprocess.run(["pkg-config","--modversion","libvalhalla"],env=env,
                               capture_output=True,text=True)
        require(version.returncode==0 and version.stdout.strip()=="3.6.3",
                "Original Valhalla 3.6.3 native developer package is missing. Install/build it before a fresh native catalog; previous verified evidence remains importable.")
        print("F8 | Compiling version-pinned original native final-edge reader",flush=True)
        subprocess.run(["cmake","-S",str(source),"-B",str(build_dir),
                        "-DCMAKE_BUILD_TYPE=Release"],env=env,check=True)
        subprocess.run(["cmake","--build",str(build_dir),"-j","4",
                        "--target","native_f8_boundary_final_edges"],env=env,check=True)
    for flag, expected in (("--version","3.6.3"),
                           ("--protocol","roadpilot.f8-native-source-11")):
        actual=subprocess.run([str(binary),flag],check=True,capture_output=True,text=True,timeout=25)
        require(actual.stdout.strip()==expected,
                "Installed native reader protocol/Valhalla version differs from the original archives")
    return binary


def generate_native_evidence(workspace: Path, a_manifest: Path, b_manifest: Path,
                             a_archive: Path, b_archive: Path,
                             a: dict, b: dict, directory: Path) -> tuple[Path,Path]:
    """Run the single owner-approved original A-final→X→B native extractor."""
    first,second=prerequisites(a_manifest,b_manifest,a,b)
    reader=native_reader(workspace)
    pair=a["regionId"]+"__"+b["regionId"]
    cut=directory/(pair+"-original-source-cut.json.gz")
    original=directory/(pair+SUFFIX)
    evidence=directory/(pair+NATIVE)
    configs=[]
    for item,archive in ((first,a_archive),(second,b_archive)):
        config=read(item["valhalla"])
        require(isinstance(config.get("mjolnir"),dict),
                "Original native Valhalla configuration is missing mjolnir settings")
        config["mjolnir"]["tile_extract"]=str(archive)
        # Deliberately point to a non-existing tile directory: use only the
        # exact original retained TAR, never stale loose .gph in work/.
        config["mjolnir"]["tile_dir"]=str(directory/("unused-tiles-"+item["region"]))
        path=directory/("original-"+item["region"]+"-valhalla.json")
        path.write_text(json.dumps(config,sort_keys=True)+"\n",encoding="utf-8")
        configs.append(path)
    common=["--manifest",str(first["manifest"]),
            "--graph-index",str(first["index"]),
            "--buffer-geojson",str(first["buffer"]),
            "--valhalla-config",str(configs[0]),
            "--receiver-manifest",str(second["manifest"]),
            "--receiver-graph-index",str(second["index"]),
            "--receiver-buffer-geojson",str(second["buffer"]),
            "--native-binary",str(reader)]
    print(f"F8 | Original native terminal evidence: {pair}",flush=True)
    run("extract_f8_region_final_edges.py",*common,
        "--resolve-cut","--output",str(cut))
    print(f"F8 | Original native B directed road matches at exact X: {pair}",flush=True)
    run("extract_f8_region_final_edges.py",*common,
        "--receiver-valhalla-config",str(configs[1]),
        "--source-evidence",str(cut),
        "--match-receiver","--bounded-missing-source-recovery",
        "--reconcile-outer-terminal-edges",
        "--output",str(evidence),"--catalog-output",str(original))
    require(original.is_file() and evidence.is_file(),
            "Original-native extraction returned no matched candidate and readback files")
    return original,evidence


def output_root(workspace: Path, a: dict, b: dict) -> Path:
    # Keep all private artifacts inside the owner's actual workspace.
    # Existing parent symlinks must not redirect staging or promotion.
    base = workspace.resolve(strict=True) / "f8-private-catalogs"
    pair = base / (a["regionId"]+"__"+b["regionId"])
    root = pair / (a["graphFingerprint"][7:23]+"_"+b["graphFingerprint"][7:23])
    for path in (base, pair, root):
        require(not path.is_symlink(), "Private catalog output contains a symlinked directory")
    return root


def check_private(path: Path, a: dict, b: dict) -> dict:
    value=read(path)
    require(value.get("schema")==SCHEMA_NAME
            and value.get("publication")=="GRAPH_STUDIO_PRIVATE_READY"
            and value.get("notForRoadPilotRuntime") is True
            and value.get("sourcePhysicalRoadDirectionCompleteness")=="NOT_VERIFIED"
            and value.get("originalGraphArchives")=={
                "from":a["graphFingerprint"],"to":b["graphFingerprint"]},
            "Retained private catalog has stale graph identity or unsafe release status")
    Draft202012Validator(read(PRIVATE_SCHEMA)).validate(value)
    return value


def summary(a: dict, b: dict, status: str, *, evidence: tuple[Path,Path] | None,
            catalog: Path | None = None, content: dict | None = None,
            why: str | None = None) -> dict:
    counts = (content or {}).get("counts") or {}
    rows = (content or {}).get("connections") or []
    points = []
    for row in rows[:12]:
        x = row.get("exactX") or {}
        if isinstance(x,dict) and isinstance(x.get("lat"),(int,float)) and isinstance(x.get("lng"),(int,float)):
            points.append({"sourceGraphId":row.get("sourceFinalDirectedGraphId"),
                           "latitude":x["lat"],"longitude":x["lng"],
                           "receiverGraphIds":[v.get("receiverDirectedGraphId")
                                               for v in row.get("receiverDirectedRoadsAtX",[])],
                           "modes":row.get("sourceModes")})
    return {"pairId":a["regionId"]+"__"+b["regionId"],
            "fromVersion":a["packageVersion"],"toVersion":b["packageVersion"],
            "fromGraphFingerprint":a["graphFingerprint"],"toGraphFingerprint":b["graphFingerprint"],
            "status":status, "publication":(content or {}).get("publication"),
            "sourceConnections":counts.get("sourceConnections",0),
            "receiverIncomingRoads":counts.get("receiverIncomingRoads",0),
            "sourcePhysicalRoadDirectionCompleteness":"NOT_VERIFIED",
            "catalogPath":str(catalog) if catalog else None,
            "evidencePath":str(evidence[0].parent) if evidence else None,
            "reason":why,"samplePoints":points,
            "notForRoadPilotRuntime":True}


def run(*args: str) -> None:
    print("F8 | "+" ".join([str(x) for x in args[:2]]), flush=True)
    subprocess.run([sys.executable, "-u", str(ROOT/"tools"/args[0]), *args[1:]], check=True)


def execute(action: str, workspace: Path, from_manifest: Path,
            to_manifest: Path, evidence_directory: Path | None) -> dict:
    a_id,a_version,a_tar,a=retained(from_manifest)
    b_id,b_version,b_tar,b=retained(to_manifest)
    require(a_id!=b_id, "Graph A and B must be separate regions")
    require(a_version and b_version, "Both original versions are required")
    pair=a_id+"__"+b_id
    root=output_root(workspace,a,b)
    catalog=root/(pair+"-GRAPH_STUDIO_PRIVATE_READY.json")
    for path in (catalog, root/"proof.json", root/"original-directed-preflight.json"):
        require(not path.is_symlink(), "Private catalog output contains a symlinked file")
    evidence=locate_evidence(workspace,pair,evidence_directory)
    if evidence is not None and evidence_directory is None:
        # A newly compiled region may share its pair name with retained
        # diagnostics from older graph archives. Never accidentally promote
        # stale proof or make a new build unusable because of that cache.
        # Explicit user-selected evidence, by contrast, must fail loudly.
        import gzip
        try:
            previous=read(evidence[0])
            with gzip.open(evidence[1],"rt",encoding="utf-8") as stream:
                native=json.load(stream)
            validate_identity(a,b,previous,native)
        except (OSError,ValueError,KeyError,EOFError,json.JSONDecodeError):
            evidence=None
    # A matching evidence fingerprint alone does not prove that the retained
    # original index, buffer and native configuration still exist unchanged.
    # Check those prerequisites even when reusing a previously ready catalog.
    if evidence is not None or catalog.exists():
        prerequisites(from_manifest,to_manifest,a,b)
    if catalog.exists():
        data=check_private(catalog,a,b)
        proof=read(root/"proof.json")
        require(proof.get("privateCatalogSha256")==digest(catalog)
                and proof.get("preflightSha256")==digest(root/"original-directed-preflight.json")
                and proof.get("fromArchiveSha256")==digest(a_tar)
                and proof.get("toArchiveSha256")==digest(b_tar),
                "Private catalog or original archive has changed since its immutable native validation")
        original_readback=Path(str(proof.get("nativeEvidence") or ""))
        require(original_readback.is_file() and not original_readback.is_symlink(),
                "Original native receiving evidence is missing or symlinked")
        require(proof.get("sourceEvidenceSha256")==digest(original_readback),
                "Original native receiving evidence was modified after private proof")
        return summary(a,b,"GRAPH_STUDIO_PRIVATE_READY",evidence=evidence,
                       catalog=catalog,content=data)
    if evidence is None and action=="status":
        try:
            prerequisites(from_manifest,to_manifest,a,b)
            return summary(a,b,"READY_TO_GENERATE_NATIVE_EVIDENCE",evidence=None,
                           why="The original Valhalla pair is available; build will run the approved source-final → exact X → directed B extractor, independent audit and private catalog validator.")
        except (OSError,KeyError,ValueError) as exc:
            return summary(a,b,"NATIVE_EVIDENCE_REQUIRED",evidence=None,
                           why="Cannot build an original native catalog without matching historical source data: "+str(exc))
    if evidence is not None:
        original_path,native_path=evidence
        import gzip
        original=read(original_path)
        with gzip.open(native_path,"rt",encoding="utf-8") as f:
            native=json.load(f)
        validate_identity(a,b,original,native)
        if action == "status":
            return summary(a,b,"READY_TO_VALIDATE_NATIVE_EVIDENCE",evidence=evidence,
                           why="The original graph identities match retained A-final and directed B evidence; Build will independently audit and validate the private catalog.")
    require(action=="build", "Unsupported private Graph Studio action")
    # Authoritative original TAR checks BEFORE any private-ready artifact
    # or immutable publication-status file is produced.
    for name,archive,manifest in (("A",a_tar,a),("B",b_tar,b)):
        print(f"F8 | Verifying original Graph {name} SHA-256",flush=True)
        require(digest(archive)==manifest["graphFingerprint"],
                f"Original Graph {name} archive was modified since its retained manifest")
    if root.exists():
        raise ValueError("Private catalog output already exists, but did not validate; refusing overwrite")
    root.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=root.parent,prefix=".native-private-stage-") as tmp:
        stage=Path(tmp)
        generated=False
        if evidence is None:
            original_path,native_path=generate_native_evidence(
                workspace,from_manifest,to_manifest,a_tar,b_tar,a,b,stage)
            evidence=(original_path,native_path)
            generated=True
            import gzip
            original=read(original_path)
            with gzip.open(native_path,"rt",encoding="utf-8") as f:
                native=json.load(f)
            validate_identity(a,b,original,native)
        audit=stage/"independent-native-audit.json"
        dispositions=stage/"original-directed-dispositions.json"
        preflight=stage/"original-directed-preflight.json"
        result=stage/(pair+"-GRAPH_STUDIO_PRIVATE_READY.json")
        run("audit_f8_physical_road_evidence.py",
            "--catalog",str(original_path),"--evidence",str(native_path),
            "--from-archive",str(a_tar),"--to-archive",str(b_tar),
            "--output",str(audit),"--disposition-output",str(dispositions))
        run("preflight_f8_approved_directed_catalog.py",
            "--catalog",str(original_path),"--native-evidence",str(native_path),
            "--dispositions",str(dispositions),"--from-archive",str(a_tar),
            "--to-archive",str(b_tar),"--output",str(preflight))
        run("build_f8_native_auto_catalog.py",
            "--catalog",str(original_path),"--native-evidence",str(native_path),
            "--dispositions",str(dispositions),"--from-archive",str(a_tar),
            "--to-archive",str(b_tar),"--preflight",str(preflight),
            "--output",str(result),"--graph-studio-private-ready")
        value=check_private(result,a,b)
        proof={"schema":"graph-studio-private-catalog-local-proof-v1",
               "pairId":pair,
               "sourceCatalog":str(root/original_path.name) if generated else str(original_path),
               "nativeEvidence":str(root/native_path.name) if generated else str(native_path),
               "originalFromManifest":str(from_manifest),
               "originalToManifest":str(to_manifest),
               "fromArchiveSha256":digest(a_tar),
               "toArchiveSha256":digest(b_tar),
               "sourceEvidenceSha256":digest(native_path),
               "preflightSha256":digest(preflight),
               "privateCatalogSha256":digest(result),
               "notForRoadPilotRuntime":True}
        (stage/"proof.json").write_text(json.dumps(proof,indent=2)+"\n",encoding="utf-8")
        # No overwrite, no R2 or Android pointer. Atomic same-filesystem
        # directory promotion after independent native preflight and schema.
        stage.rename(root)
    if generated:
        evidence=(root/original_path.name,root/native_path.name)
    return summary(a,b,"GRAPH_STUDIO_PRIVATE_READY",evidence=evidence,
                   catalog=catalog,content=value)


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["status","build"])
    p.add_argument("--workspace",required=True,type=Path)
    p.add_argument("--from-manifest",required=True,type=Path)
    p.add_argument("--to-manifest",required=True,type=Path)
    p.add_argument("--evidence-directory",type=Path)
    args=p.parse_args()
    require(args.workspace.is_dir(), "Graph Studio workspace is not available")
    if args.evidence_directory:
        require(args.evidence_directory.is_absolute() and args.evidence_directory.is_dir()
                and not args.evidence_directory.is_symlink(),
                "Evidence directory must be an existing real absolute directory")
    result=execute(args.action,args.workspace,args.from_manifest,args.to_manifest,
                   args.evidence_directory)
    print("F8_RESULT "+json.dumps(result,sort_keys=True),flush=True)


if __name__=="__main__":
    try:
        main()
    except (OSError,ValueError,KeyError,subprocess.CalledProcessError,json.JSONDecodeError) as exc:
        print("F8_ERROR "+str(exc),file=sys.stderr,flush=True)
        raise SystemExit(1)
