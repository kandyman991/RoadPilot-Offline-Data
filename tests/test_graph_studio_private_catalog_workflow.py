"""Native private Graph Studio catalog GUI bridge: fail closed, preserve SHA identity."""
from __future__ import annotations
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import graph_studio_private_catalog_workflow as producer


def sha(data:bytes)->str:
    return "sha256:"+hashlib.sha256(data).hexdigest()


def setup_workspace(tmp:Path):
    output=[]
    for region in ("region-a","region-b"):
        build=tmp/"builds"/region
        build.mkdir(parents=True)
        payload=(region+" original compiled archive").encode()
        (build/"graph.tar").write_bytes(payload)
        idx=(region+" index").encode()
        (build/"index.json").write_bytes(idx)
        work=tmp/"work"/region/"build"
        work.mkdir(parents=True)
        buffer=(region+" 25 km approved region buffer").encode()
        (work/"buffer.geojson").write_bytes(buffer)
        (work/"valhalla.json").write_text('{"mjolnir":{"tile_extract":"unused"}}')
        content={
            "schema":"roadpilot-routing-pack",
            "regionId":region,
            "packageVersion":"2026.10.13-1",
            "valhallaVersion":"3.6.3",
            "graphFingerprint":sha(payload),
            "artifact":{"fileName":"graph.tar","sha256":sha(payload)},
            "source":{"bufferGeoJsonSha256":sha(buffer)[7:]},
            "graphIndex":{"fileName":"index.json","sha256":sha(idx)[7:]},
        }
        manifest=build/"manifest.json"
        manifest.write_text(json.dumps(content))
        output.append(manifest)
    return output


class PrivateNativeGraphStudioBridgeTest(unittest.TestCase):
    def test_exact_original_graph_pair_is_generation_ready(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            a,b=setup_workspace(root)
            result=producer.execute("status",root,a,b,None)
            self.assertEqual(result["status"],"READY_TO_GENERATE_NATIVE_EVIDENCE")
            self.assertTrue(result["notForRoadPilotRuntime"])
            self.assertEqual(result["sourcePhysicalRoadDirectionCompleteness"],"NOT_VERIFIED")
            self.assertIsNone(result["catalogPath"])
            self.assertFalse((root/"f8-private-catalogs").exists())

    def test_matching_retained_native_evidence_is_ready_for_private_audit(self):
        import gzip
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            a,b=setup_workspace(root)
            a_obj=json.loads(a.read_text())
            b_obj=json.loads(b.read_text())
            evidence_dir=root/"diagnostics/f8-production/proof"
            evidence_dir.mkdir(parents=True)
            pair="region-a__region-b"
            native={
                "sourceRegionId":"region-a","receiverRegionId":"region-b",
                "sourceGraphFingerprint":a_obj["graphFingerprint"],
                "receiverGraphFingerprint":b_obj["graphFingerprint"],
                "sourceBufferFingerprint":"sha256:"+a_obj["source"]["bufferGeoJsonSha256"],
                "receiverBufferFingerprint":"sha256:"+b_obj["source"]["bufferGeoJsonSha256"],
                "sourceIndexFingerprint":"sha256:"+a_obj["graphIndex"]["sha256"],
                "receiverIndexFingerprint":"sha256:"+b_obj["graphIndex"]["sha256"]
            }
            candidate={"pairId":pair,"graphFingerprints":{
                "from":a_obj["graphFingerprint"],"to":b_obj["graphFingerprint"]}}
            (evidence_dir/(pair+producer.SUFFIX)).write_text(json.dumps(candidate))
            with gzip.open(evidence_dir/(pair+producer.NATIVE),"wt") as out:
                json.dump(native,out)
            result=producer.execute("status",root,a,b,None)
            self.assertEqual(result["status"],"READY_TO_VALIDATE_NATIVE_EVIDENCE")
            self.assertEqual(result["evidencePath"],str(evidence_dir))
            self.assertTrue(result["notForRoadPilotRuntime"])
            self.assertFalse((root/"f8-private-catalogs").exists())

    def test_stale_automatically_discovered_evidence_regenerates_but_explicit_fails(self):
        import gzip
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            a,b=setup_workspace(root)
            directory=root/"diagnostics/f8-production/old"
            directory.mkdir(parents=True)
            pair="region-a__region-b"
            (directory/(pair+producer.SUFFIX)).write_text(json.dumps({
                "pairId":pair,"graphFingerprints":{
                    "from":"sha256:"+"a"*64,"to":"sha256:"+"b"*64}}))
            with gzip.open(directory/(pair+producer.NATIVE),"wt") as handle:
                json.dump({"sourceRegionId":"region-a","receiverRegionId":"region-b",
                           "sourceGraphFingerprint":"sha256:"+"a"*64,
                           "receiverGraphFingerprint":"sha256:"+"b"*64},handle)
            autodiscovered=producer.execute("status",root,a,b,None)
            self.assertEqual(autodiscovered["status"],"READY_TO_GENERATE_NATIVE_EVIDENCE")
            self.assertIsNone(autodiscovered["evidencePath"])
            with self.assertRaisesRegex(ValueError,"archive identity is stale"):
                producer.execute("status",root,a,b,directory)

    def test_retained_native_evidence_rechecks_original_buffer_and_index(self):
        import gzip
        for filename in ("buffer.geojson", "index.json"):
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as folder:
                root=Path(folder)
                a,b=setup_workspace(root)
                aa=json.loads(a.read_text());bb=json.loads(b.read_text())
                pair="region-a__region-b"
                evidence_dir=root/"diagnostics"/"f8-production"/"original"
                evidence_dir.mkdir(parents=True)
                original={"pairId":pair,"graphFingerprints":{
                    "from":aa["graphFingerprint"],"to":bb["graphFingerprint"]}}
                native={
                    "sourceRegionId":"region-a","receiverRegionId":"region-b",
                    "sourceGraphFingerprint":aa["graphFingerprint"],
                    "receiverGraphFingerprint":bb["graphFingerprint"],
                    "sourceBufferFingerprint":"sha256:"+aa["source"]["bufferGeoJsonSha256"],
                    "receiverBufferFingerprint":"sha256:"+bb["source"]["bufferGeoJsonSha256"],
                    "sourceIndexFingerprint":"sha256:"+aa["graphIndex"]["sha256"],
                    "receiverIndexFingerprint":"sha256:"+bb["graphIndex"]["sha256"],
                }
                (evidence_dir/(pair+producer.SUFFIX)).write_text(json.dumps(original))
                with gzip.open(evidence_dir/(pair+producer.NATIVE),"wt") as out:
                    json.dump(native,out)
                ready=producer.execute("status",root,a,b,None)
                self.assertEqual(ready["status"],"READY_TO_VALIDATE_NATIVE_EVIDENCE")
                target=(root/"work"/"region-a"/"build"/filename
                        if filename.endswith(".geojson") else a.parent/filename)
                target.write_bytes(b"changed after original native evidence generation")
                with self.assertRaisesRegex(ValueError,"no longer matches"):
                    producer.execute("status",root,a,b,None)

    def test_existing_private_catalog_rechecks_retained_inputs(self):
        # An existing catalog must not return PRIVATE_READY before validating
        # the original current index/buffer; even a cached catalog is unsafe.
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);a,b=setup_workspace(root)
            aa=json.loads(a.read_text());bb=json.loads(b.read_text())
            output=producer.output_root(root,aa,bb)
            output.mkdir(parents=True)
            (output/"region-a__region-b-GRAPH_STUDIO_PRIVATE_READY.json").write_text("{}")
            (root/"work"/"region-a"/"build"/"buffer.geojson").unlink()
            with self.assertRaisesRegex(ValueError,"missing"):
                producer.execute("status",root,a,b,None)

    def test_retained_private_ready_requires_original_native_readback(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);a,b=setup_workspace(root)
            aa=json.loads(a.read_text());bb=json.loads(b.read_text())
            output=producer.output_root(root,aa,bb)
            output.mkdir(parents=True)
            catalog=output/"region-a__region-b-GRAPH_STUDIO_PRIVATE_READY.json"
            catalog.write_text("{}")
            preflight=output/"original-directed-preflight.json"
            preflight.write_text("{}")
            proof={
                "privateCatalogSha256":producer.digest(catalog),
                "preflightSha256":producer.digest(preflight),
                "fromArchiveSha256":producer.digest(a.parent/"graph.tar"),
                "toArchiveSha256":producer.digest(b.parent/"graph.tar"),
                "nativeEvidence":str(output/"missing-original-native.json.gz"),
                "sourceEvidenceSha256":"sha256:"+"a"*64,
            }
            (output/"proof.json").write_text(json.dumps(proof))
            with patch.object(producer,"check_private",return_value={"counts":{},"connections":[]}):
                with self.assertRaisesRegex(ValueError,"evidence is missing"):
                    producer.execute("status",root,a,b,None)

    def test_private_output_rejects_parent_and_leaf_symlinks(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);a,b=setup_workspace(root)
            outside=root/"outside";outside.mkdir()
            (root/"f8-private-catalogs").symlink_to(outside,target_is_directory=True)
            with self.assertRaisesRegex(ValueError,"symlinked directory"):
                producer.execute("status",root,a,b,None)
            self.assertEqual(list(outside.iterdir()),[])
            (root/"f8-private-catalogs").unlink()
            aa=json.loads(a.read_text());bb=json.loads(b.read_text())
            output=producer.output_root(root,aa,bb)
            output.mkdir(parents=True)
            (output/"region-a__region-b-GRAPH_STUDIO_PRIVATE_READY.json").symlink_to(
                outside/"absent.json")
            with self.assertRaisesRegex(ValueError,"symlinked file"):
                producer.execute("status",root,a,b,None)

    def test_absent_original_configuration_fails_readiness(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            a,b=setup_workspace(root)
            (root/"work"/"region-a"/"build"/"buffer.geojson").unlink()
            result=producer.execute("status",root,a,b,None)
            self.assertEqual(result["status"],"NATIVE_EVIDENCE_REQUIRED")
            self.assertIn("missing",result["reason"])
            self.assertFalse((root/"f8-private-catalogs").exists())

    def test_original_buffer_and_index_tampering_fail_closed(self):
        for name,folder_name in (("buffer.geojson","region-a"),
                                 ("index.json","region-a")):
            with self.subTest(file=name),tempfile.TemporaryDirectory() as folder:
                root=Path(folder);a,b=setup_workspace(root)
                target=(root/"work"/folder_name/"build"/name if name.endswith("geojson")
                        else root/"builds"/folder_name/name)
                target.write_bytes(b"tampered")
                result=producer.execute("status",root,a,b,None)
                self.assertEqual(result["status"],"NATIVE_EVIDENCE_REQUIRED")
                self.assertIn("no longer matches",result["reason"])

    def test_original_archive_fingerprint_disagrees_with_manifest(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);a,b=setup_workspace(root)
            data=json.loads(a.read_text());data["graphFingerprint"]="sha256:"+"a"*64
            a.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,"fingerprint disagrees"):
                producer.execute("status",root,a,b,None)

    def test_duplicate_same_region_or_unsafe_archive_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);a,b=setup_workspace(root)
            with self.assertRaisesRegex(ValueError,"separate regions"):
                producer.execute("status",root,a,a,None)
            data=json.loads(a.read_text());data["artifact"]["fileName"]="../unsafe"
            a.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,"Unsafe original"):
                producer.execute("status",root,a,b,None)

    def test_evidence_discovery_only_matches_exact_pair_and_ignores_symlinks(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);folder_path=root/"diagnostics/f8-production"/"approved"
            folder_path.mkdir(parents=True)
            proper=folder_path/("region-a__region-b"+producer.SUFFIX)
            native=folder_path/("region-a__region-b"+producer.NATIVE)
            proper.write_text("{}");native.write_bytes(b"gzip-bytes")
            pair=producer.locate_evidence(root,"region-a__region-b",None)
            self.assertEqual(pair,(proper,native))
            proper.unlink()
            forged=folder_path/("region-c__region-b"+producer.SUFFIX)
            forged.write_text("{}")
            proper.symlink_to(forged)
            self.assertIsNone(producer.locate_evidence(root,"region-a__region-b",None))

    def test_private_schema_never_accepts_roadpilot_ready_or_graph_mismatch(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);a,b=setup_workspace(root)
            _,_,_,a_content=producer.retained(a)
            _,_,_,b_content=producer.retained(b)
            sample={
                "schema":producer.SCHEMA_NAME,
                "publication":"READY",
                "notForRoadPilotRuntime":False,
                "sourcePhysicalRoadDirectionCompleteness":"VERIFIED",
                "originalGraphArchives":{
                    "from":a_content["graphFingerprint"],
                    "to":b_content["graphFingerprint"]},
                "counts":{},
            }
            path=root/"unsafe.json";path.write_text(json.dumps(sample))
            with self.assertRaisesRegex(ValueError,"unsafe release"):
                producer.check_private(path,a_content,b_content)

if __name__ == "__main__":
    unittest.main()
