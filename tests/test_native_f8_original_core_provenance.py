"""Byte-exact original Geofabrik core->25km buffered native graph provenance."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from prove_native_f8_original_core_provenance import (
    inspect, reproduce_original_buffer, sha,
)

POLY_A = """Synthetic core A
1
 11.00 47.00
 11.20 47.00
 11.20 47.20
 11.00 47.20
END
END
"""
POLY_B = """Synthetic core B
1
 11.10 47.10
 11.30 47.10
 11.30 47.30
 11.10 47.30
END
END
"""
SOURCE_FINGERPRINTS = {"from":"sha256:"+"a"*64,
                       "to":"sha256:"+"b"*64}


class OriginalCoreByteProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.inputs={}
        self.manifests={}
        self.arch={
            "schema":"roadpilot.f8-all-original-source-archive-tile-cut-census",
            "version":1,
            "pairId":"it-at",
            "productionPublication":"BLOCKED",
            "originalGraphArchiveTileInventory":
                "ALL_GRAPHREADER_GETTILESET_TILES_ENUMERATED",
            "sourceGraphFingerprints":dict(SOURCE_FINGERPRINTS),
            "directions":{"from-to":{},"to-from":{}},
            "immutableOriginalSourceSHA256":{},
        }
        for side,region,poly in (("from","italy-nord-est",POLY_A),
                                 ("to","austria",POLY_B)):
            region_dir=self.root/side
            region_dir.mkdir()
            core=region_dir/"original-core.poly"
            core.write_text(poly,encoding="utf8")
            buffer=region_dir/"original-buffer.geojson"
            buffer.write_bytes(reproduce_original_buffer(core,25.0)[0])
            original={
                "schema":"roadpilot-routing-pack",
                "schemaVersion":1,
                "regionId":region,
                "graphFingerprint":SOURCE_FINGERPRINTS[side],
                "valhallaVersion":"3.6.3",
                "source":{
                    "borderBufferKm":25,
                    "polygonUrl":f"https://example.invalid/{region}.poly",
                    "bufferGeoJsonSha256":sha(buffer.read_bytes()).removeprefix("sha256:"),
                },
            }
            manifest=region_dir/"manifest.json"
            manifest.write_text(json.dumps(original),encoding="utf8")
            self.inputs[side]={"core":core,"buffer":buffer,"manifest":manifest}
            self.manifests[side]=original
            self.arch["immutableOriginalSourceSHA256"][side+"-manifest"]=sha(manifest.read_bytes())
            self.arch["immutableOriginalSourceSHA256"][side+"-buffer"]=sha(buffer.read_bytes())

    def test_exact_generated_bytes_bind_both_source_cores_and_archive_manifests(self):
        result=inspect(self.arch,self.manifests,self.inputs)
        self.assertEqual(result["productionPublication"],"BLOCKED")
        self.assertEqual(result["receivingGraphCorrelation"],"NOT_STARTED")
        self.assertGreater(result["originalCoreOverlapSquareKilometres"],0)
        self.assertEqual(result["allSourceRoadDirectionsMappedToOneFinalOriginalGraphId"],
                         "NOT_VERIFIED")
        for side in ("from-to","to-from"):
            self.assertTrue(result["directions"][side][
                "originalBufferReproducedExactlyFromCore"])
            self.assertEqual(len(result["directions"][side][
                "originalNominalCorePolySHA256"]),71)

    def test_nominal_core_edits_rejected_instead_of_assumed_same_border(self):
        path=self.inputs["from"]["core"]
        path.write_text(path.read_text().replace("11.20","11.21"),encoding="utf8")
        with self.assertRaisesRegex(ValueError,"does not reproduce"):
            inspect(self.arch,self.manifests,self.inputs)

    def test_corrupted_original_buffer_bytes_rejected(self):
        path=self.inputs["to"]["buffer"]
        path.write_bytes(path.read_bytes()+b" ")
        with self.assertRaisesRegex(ValueError,"buffer fingerprint changed"):
            inspect(self.arch,self.manifests,self.inputs)

    def test_manifest_metadata_or_original_sha_mismatch_rejected(self):
        bad=copy.deepcopy(self.arch)
        bad["immutableOriginalSourceSHA256"]["from-manifest"]="sha256:"+"c"*64
        with self.assertRaisesRegex(ValueError,"provenance changed"):
            inspect(bad,self.manifests,self.inputs)
        bad=copy.deepcopy(self.arch)
        bad["sourceGraphFingerprints"]["to"]="sha256:"+"c"*64
        with self.assertRaisesRegex(ValueError,"provenance changed"):
            inspect(bad,self.manifests,self.inputs)

    def test_wrong_valhalla_version_rejected(self):
        bad=copy.deepcopy(self.manifests)
        bad["from"]["valhallaVersion"]="3.5.0"
        with self.assertRaisesRegex(ValueError,"provenance changed"):
            inspect(self.arch,bad,self.inputs)

    def test_buffer_must_be_exact_25km(self):
        with self.assertRaisesRegex(ValueError,"25km"):
            reproduce_original_buffer(self.inputs["from"]["core"],20)
        bad=copy.deepcopy(self.manifests)
        bad["from"]["source"]["borderBufferKm"]=20
        with self.assertRaisesRegex(ValueError,"25km"):
            inspect(self.arch,bad,self.inputs)

    def test_any_claim_of_source_release_eligibility_fails(self):
        bad=copy.deepcopy(self.arch)
        bad["productionPublication"]="READY"
        with self.assertRaisesRegex(ValueError,"Unverified"):
            inspect(bad,self.manifests,self.inputs)


if __name__=="__main__":
    unittest.main()
