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
