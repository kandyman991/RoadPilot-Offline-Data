"""Build-triggered F8: pair only reciprocal original region buffers by graph SHA.

No old GPS proposal/portal discovery, no one-way name-based matches, and no
production output from a partial original A-last / B-first road catalog.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from run_f8_bilateral_after_build import (
    listed_manifests, select_compatible_pairs, find_best_native_ledger,
    run_after_build, pair_fingerprint_key
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, sort_keys=True) + "\n")


def create_region(workspace: Path, region: str, version: str, primary: str,
                  other: str | None, other_primary: str | None,
                  *, graph_bytes: bytes | None = None):
    base = workspace / "builds" / region
    base.mkdir(parents=True, exist_ok=True)
    graph_bytes = graph_bytes or ("ORIGINAL GRAPH " + region).encode()
    archive_name = region + "-routing-" + version + ".tar"
    graph = base / archive_name
    graph.write_bytes(graph_bytes)
    boundary = ("sha256:" + digest((region + other).encode())) if other else None
    index_name = region + "-routing-" + version + "-graph-index.json"
    index = {
        "schema": "roadpilot-graph-index", "schemaVersion": 1,
        "regionId": region, "boundaries": (
            [{"sourceId": other_primary,"fingerprint": boundary}]
            if other else []),
    }
    write_json(base / index_name,index)
    manifest_name = region + "-routing-" + version + "-manifest.json"
    manifest = {
        "schema": "roadpilot-routing-pack", "schemaVersion": 1,
        "regionId": region, "packageVersion": version,
        "graphFingerprint": "sha256:" + digest(graph_bytes),
        "source": {"primaryGeofabrikId": primary,"borderBufferKm":25.0},
        "artifact": {"fileName": archive_name, "sha256": digest(graph_bytes)},
        "graphIndex": {
            "fileName": index_name,
            "sha256":digest((base/index_name).read_bytes()),
        },
    }
    write_json(base / manifest_name, manifest)
    return base / manifest_name


def original_ledger(pair: dict, workspace: Path) -> dict:
    parent=workspace/"f8-native"/pair["pairId"]/"source-SHA-evidence"/"pair.json"
    write_json(parent,pair)
    a,b = pair["fromRegionId"],pair["toRegionId"]
    gid=125
    option=400
    return {
        "schema":"roadpilot.f8-final-directed-connections","version":1,
        "pairId":pair["pairId"],
        "graphFingerprints":{
            "from":pair["fromGraphFingerprint"],
            "to":pair["toGraphFingerprint"],
        },
        "originalSourceFinalTopologyInputSHA256":{"candidateCatalog":"sha256:"+"c"*64},
        "originalReceivingFullArchiveCensus":{"from":{},"to":{}},
        "originalImmutableInputSHA256":{"pair":"sha256:"+digest(parent.read_bytes())},
        "forwardSourceParentEvidenceSHA256":{"catalog":"sha256:"+"2"*64},
        "productionPublication":"BLOCKED",
        "sourceDiscoveryComplete":False,
        "physicalRoadPerDirectionGlobalUniqueness":"NOT_VERIFIED",
        "connections":[{
            "sourceRegionId":a,"receiverRegionId":b,
            "sourceFinalDirectedGraphId":gid,
            "sourceValhallaProvedModes":["auto","motorcycle"],
            "originalSourceValhallaTripLeg":{
                mode:{"verified":True,"originalNativeLastGraphId":gid,
                      "originalNativeTripLegDirectedGraphIds":[gid],
                      "startSnapMeters":0.02,"endSnapMeters":0.12}
                for mode in ("auto","motorcycle")},
            "originalSourceFinalTopologyProof":{
                mode:{"status":"NO_OTHER_NATIVE_PHYSICAL_FORWARD_CONTINUATION"}
                for mode in ("auto","motorcycle")},
            "receiverOptions":[{
                "receiverFirstDirectedGraphId":option,
                "travelModes":["auto","motorcycle"],
                "directedPhysicalGeometry":{"status":"FORWARD_CONTINUOUS"},
                "originalReceiverValhallaTripLeg":{
                    mode:{"verified":True,"actualFirstDirectedGraphId":option,
                          "originalTripLegDirectedGraphIds":[option,404]}
                    for mode in ("auto","motorcycle")},
            }],
        }],
        "unresolvedSourceFinalEdges":[{
            "sourceRegionId":a,"sourceFinalDirectedGraphId":129,
            "mustNotCreateConnection":True,
            "status":"NO_VALHALLA_VERIFIED_FORWARD_RECEIVING_ROAD",
        }],
    }


class AfterBuildBilateralF8Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="f8-auto-build-test-")
        self.addCleanup(self.tmp.cleanup)
        self.workspace=Path(self.tmp.name)
        self.version="2026.10.13-1"
        self.italy=create_region(self.workspace,"italy-nord-est",self.version,
                                 "italy/nord-est","austria","austria")
        self.austria=create_region(self.workspace,"austria",self.version,
                                   "austria","italy-nord-est","italy/nord-est")
        self.manifests=listed_manifests(self.workspace/"builds")

    def compatible_pair(self):
        pairs=select_compatible_pairs(
            self.manifests,{("italy-nord-est",self.version)})
        self.assertEqual(len(pairs),1)
        return pairs[0][2]

    def test_tauri_queue_invokes_f8_after_regional_validation(self):
        code=(Path(__file__).resolve().parents[1]/"graph-studio"/"src-tauri"/
              "src"/"lib.rs").read_text()
        start=code.index("fn run_build_queue(")
        end=code.index("fn start_build_queue(",start)
        body=code[start:end]
        regional=body.index("tools/build_routing_region.py")
        validated=body.index("tools/validate_routing_pack.py")
        f8=body.index("tools/run_f8_bilateral_after_build.py")
        self.assertLess(regional,validated)
        self.assertLess(validated,f8)
        self.assertIn('f8.arg("--built-region").arg(region_id)',body)
        self.assertNotIn("tools/discover_native_f8_crossings.py",body)
        self.assertNotIn("tools/graph_studio_f8_workspace.py",body)


        pair=self.compatible_pair()
        self.assertEqual(pair["pairId"],"italy-nord-est__austria")
        again=select_compatible_pairs(self.manifests,{("austria",self.version)})
        self.assertEqual(again[0][2],pair)
        self.assertEqual(len(pair_fingerprint_key(pair)),64)

    def test_no_crossing_pair_when_source_graphs_do_not_share_boundary(self):
        solo=create_region(self.workspace,"belgium",self.version,
                           "belgium",None,None)
        paths=listed_manifests(self.workspace/"builds")
        self.assertEqual(select_compatible_pairs(paths,{("belgium",self.version)}),[])

    def test_multiple_retained_peer_graph_versions_are_not_suppressed(self):
        create_region(self.workspace,"austria","2026.10.19-3",
                      "austria","italy-nord-est","italy/nord-est",
                      graph_bytes=b"AUSTRIA DIFFERENT ORIGINAL GRAPH")
        manifests=listed_manifests(self.workspace/"builds")
        pairs=select_compatible_pairs(manifests,{("italy-nord-est",self.version)})
        self.assertEqual(len(pairs),2)
        self.assertEqual(len({pair_fingerprint_key(p) for _,_,p in pairs}),2)

    def test_wrong_source_pair_boundary_sha_never_reuses_ledger(self):
        pair=self.compatible_pair()
        ledger=self.workspace/"diagnostics"/"f8-production"/"test"/"f8-original-native-verified.json"
        raw=original_ledger(pair,self.workspace)
        raw["originalImmutableInputSHA256"]["pair"]="sha256:"+"0"*64
        write_json(ledger,raw)
        result=run_after_build(self.workspace,{("italy-nord-est",self.version)})
        self.assertEqual(result["pairs"][0]["stage"],
                         "PENDING_ORIGINAL_SOURCE_FINAL_EDGE_DISCOVERY")
        self.assertEqual(result["pairs"][0]["verifiedReceivingDirectedOptions"],0)

    def test_one_sided_graph_overlap_must_not_silently_pass(self):
        # Austria says Italy overlaps but Italy index no longer declares
        # Austria; this is an invalid reciprocal pair, not 'zero crossings'.
        m=json.loads(self.italy.read_text())
        index=self.italy.parent/m["graphIndex"]["fileName"]
        data=json.loads(index.read_text())
        data["boundaries"]=[]
        write_json(index,data)
        m["graphIndex"]["sha256"]=digest(index.read_bytes())
        write_json(self.italy,m)
        scan=listed_manifests(self.workspace/"builds")
        with self.assertRaisesRegex(ValueError,"Only one original"):
            select_compatible_pairs(scan,{("austria",self.version)})

    def test_when_both_original_graphs_ready_without_source_proof_records_pending(self):
        result=run_after_build(
            self.workspace,{("austria",self.version)})
        self.assertEqual(result["count"],1)
        row=result["pairs"][0]
        self.assertEqual(row["stage"],"PENDING_ORIGINAL_SOURCE_FINAL_EDGE_DISCOVERY")
        self.assertFalse(row["sourceDiscoveryComplete"])
        self.assertEqual(row["productionPublication"],"BLOCKED")
        self.assertFalse(row["oldGpsPortalDiscoveryInvoked"])
        again=run_after_build(
            self.workspace,{("italy-nord-est",self.version)})
        self.assertEqual(again["pairs"],result["pairs"])

    def test_exact_original_proof_is_automatically_validated_and_ingested(self):
        pair=self.compatible_pair()
        raw=original_ledger(pair,self.workspace)
        ledger=self.workspace/"diagnostics"/"f8-production"/"test"/"f8-original-native-verified.json"
        write_json(ledger,raw)
        result=run_after_build(
            self.workspace,{("austria",self.version),
                            ("italy-nord-est",self.version)})
        self.assertEqual(result["count"],1)
        x=result["pairs"][0]
        self.assertEqual(x["stage"],"PARTIAL_ORIGINAL_DIRECTED_ROAD_CONNECTIONS_VERIFIED_ONLY")
        self.assertEqual(x["verifiedSourceFinalDirectedGraphIds"],1)
        self.assertEqual(x["verifiedReceivingDirectedOptions"],1)
        self.assertEqual(x["unresolvedOriginalCandidateIds"],1)
        self.assertEqual(x["productionPublication"],"BLOCKED")
        self.assertFalse(x["sourceDiscoveryComplete"])
        self.assertFalse(x["originalSourceTripLegRerunDuringAutomaticStage"])
        cache_path=Path(x["verifiedOnlyAndroidTestCache"])
        self.assertLessEqual(cache_path.stat().st_size,3_000_000)
        cache=json.loads(cache_path.read_text())
        self.assertEqual(cache["originalUnpublishedFullNativeUnresolvedCount"],1)
        self.assertEqual(cache["connections"][0]["receiverOptions"][0]
                         ["receiverFirstDirectedGraphId"],400)
        self.assertFalse(cache["sourceDiscoveryComplete"])
        self.assertEqual(cache["productionPublication"],"BLOCKED")
        duplicate=run_after_build(
            self.workspace,{("austria",self.version)})
        self.assertEqual(duplicate["pairs"][0],x)

    def test_wrong_graph_sha_rejects_reusing_old_pair(self):
        pair=self.compatible_pair()
        ledger=self.workspace/"diagnostics"/"f8-production"/"test"/"f8-original-native-verified.json"
        write_json(ledger,original_ledger(pair,self.workspace))
        m=json.loads(self.italy.read_text())
        package=self.italy.parent/m["artifact"]["fileName"]
        package.write_bytes(b"CORRUPTED ORIGINAL GRAPH")
        with self.assertRaisesRegex(ValueError,"Original graph archive changed"):
            run_after_build(self.workspace,{("italy-nord-est",self.version)})

    def test_false_receiving_first_graphid_and_source_terminal_fails_closed(self):
        pair=self.compatible_pair()
        ledger=self.workspace/"diagnostics"/"f8-production"/"test"/"f8-original-native-verified.json"
        raw=original_ledger(pair,self.workspace)
        raw["connections"][0]["receiverOptions"][0]["originalReceiverValhallaTripLeg"][
            "auto"]["actualFirstDirectedGraphId"]=999
        write_json(ledger,raw)
        with self.assertRaisesRegex(ValueError,"not proved"):
            run_after_build(self.workspace,{("austria",self.version)})

    def test_duplicate_B_branch_not_suppressed_by_way_or_name(self):
        pair=self.compatible_pair()
        ledger=self.workspace/"diagnostics"/"f8-production"/"test"/"f8-original-native-verified.json"
        raw=original_ledger(pair,self.workspace)
        raw["connections"][0]["receiverOptions"].append(
            deepcopy(raw["connections"][0]["receiverOptions"][0]))
        with self.assertRaisesRegex(ValueError,"Repeated native receiver branch"):
            write_json(ledger,raw)
            run_after_build(self.workspace,{("austria",self.version)})

    def test_incomplete_evidence_cannot_claim_production_ready(self):
        pair=self.compatible_pair()
        ledger=self.workspace/"diagnostics"/"f8-production"/"test"/"f8-original-native-verified.json"
        raw=original_ledger(pair,self.workspace)
        raw["sourceDiscoveryComplete"]=True
        write_json(ledger,raw)
        with self.assertRaisesRegex(ValueError,"falsely claims"):
            run_after_build(self.workspace,{("austria",self.version)})


if __name__=="__main__":
    unittest.main()
