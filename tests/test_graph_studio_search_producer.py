"""Graph Studio #17 M5: actual canonical independent build/import and fail-closed tests."""
from __future__ import annotations
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tools import graph_studio_search_producer as producer

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/graph_studio_search_producer.py"


def config(region: str, name: str, country: str) -> dict:
    return {
        "schemaVersion": 1, "id": region, "name": name,
        "overture": {
            "enabled": True, "country": country,
            "databaseSchema": "roadpilot-overture-v1",
            "fileName": region + "-v1.sqlite",
            "manifestFileName": region + "-v1.json",
            "coverage": {"minLat": 45.0 if country == "IT" else 47.0,
                         "maxLat": 49.0, "minLng": 10.0, "maxLng": 17.0},
            "validation": [{"nameEquals": "SARP" if country == "IT" else "Wien Fuel",
                            "query": "SARP Food Technologies" if country == "IT" else "Wien Fuel",
                            "addressContainsAny": ["Colombara"] if country == "IT" else ["Wien"],
                            "limit": 8}]
        }
    }


def place(place_id: str, name: str, country: str, lat: float, lng: float) -> dict:
    city = "San Martino di Lupari" if country == "IT" else "Wien"
    street = "Via Colombara 10" if country == "IT" else "Mariahilfer Strasse 3"
    return {"type": "Feature", "id": place_id,
            "properties": {"id": place_id, "names": {"primary": name},
                           "addresses": [{"freeform": street, "locality": city,
                                          "country": country}],
                           "confidence": .96, "operating_status": "open",
                           "basic_category": "gas_station" if country == "AT" else "manufacturer",
                           "taxonomy": {"primary": "gas_station" if country == "AT" else "industrial_manufacturer",
                                        "hierarchy": ["services_and_business"], "alternates": []},
                           "sources": [{"provider": "Synthetic", "resource": "fixture",
                                        "record_id": place_id, "version": "1", "confidence": .96}]},
            "geometry": {"type": "Point", "coordinates": [lng, lat]}}


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)],
                          text=True, capture_output=True, cwd=ROOT, timeout=55)


class SearchLocalProductionTest(unittest.TestCase):
    def test_italy_and_austria_create_independent_immutable_search_packs(self):
        with tempfile.TemporaryDirectory() as t:
            base = Path(t)
            for region, name, country, poi_name, lat, lng in (
                ("italy-nord-est", "Italy North East", "IT", "SARP", 45.645, 11.793),
                ("austria", "Austria", "AT", "Wien Fuel", 48.2, 16.36),
            ):
                with self.subTest(region=region):
                    region_config = base / (region + "-config.json")
                    region_config.write_text(json.dumps(config(region, name, country)))
                    data_file = base / (region + "-source.geojsonseq")
                    data_file.write_text(json.dumps(place("fixture-" + region, poi_name,
                                                         country, lat, lng)) + "\n")
                    # Generate via same CLI the Graph Studio GUI invokes.
                    output = run_cli("build", "--config", region_config, "--input", data_file,
                                     "--source-release", "synthetic-2026-11-13",
                                     "--pack-version", "v1", "--dist-dir", base/"retained",
                                     "--work-dir", base/"work")
                    self.assertEqual(output.returncode, 0, output.stdout + output.stderr)
                    self.assertIn("SEARCH_RESULT", output.stdout)
                    dest = base/"retained"/region/"v1"
                    manifest = dest/(region+"-v1.json")
                    info = json.loads(manifest.read_text())
                    self.assertEqual(info["regionId"], region)
                    self.assertTrue(info["validation"]["passed"])
                    self.assertEqual(info["recordCount"], 1)
                    self.assertEqual(info["source"]["dataRelease"], "synthetic-2026-11-13")
                    self.assertTrue((dest/(region+"-v1.sqlite.sha256")).is_file())
                    again = run_cli("build", "--config", region_config, "--input", data_file,
                                    "--source-release", "synthetic-2026-11-13",
                                    "--pack-version", "v1", "--dist-dir", base/"retained",
                                    "--work-dir", base/"work")
                    self.assertNotEqual(again.returncode, 0)
                    self.assertIn("already exists", again.stderr)
                    # Revalidate imported actual SQL and manifest via producer itself.
                    imported = run_cli("import", "--config", region_config,
                                       "--manifest", manifest,
                                       "--dist-dir", base/"imports")
                    self.assertEqual(imported.returncode, 0, imported.stdout + imported.stderr)
                    self.assertEqual((base/"imports"/region/"v1"/(region+"-v1.sqlite")).read_bytes(),
                                     (dest/(region+"-v1.sqlite")).read_bytes())
                    repeat = run_cli("import", "--config", region_config,
                                     "--manifest", manifest, "--dist-dir", base/"imports")
                    self.assertNotEqual(repeat.returncode, 0)
                    self.assertIn("overwrite", repeat.stderr)
                    # Tampering with SQLite must not import despite the existence of a manifest.
                    corrupt_dir = base/("bad-"+region)
                    corrupt_dir.mkdir()
                    for file in dest.iterdir():
                        if file.is_file():
                            (corrupt_dir/file.name).write_bytes(file.read_bytes())
                    (corrupt_dir/(region+"-v1.sqlite")).write_bytes(b"invalid sqlite")
                    bad = run_cli("import", "--config", region_config,
                                  "--manifest", corrupt_dir/(region+"-v1.json"),
                                  "--dist-dir", base/"bad-imports")
                    self.assertNotEqual(bad.returncode, 0)
                    self.assertFalse((base/"bad-imports"/region/"v1").exists())
            # Independent artifacts: no routing/ or visual/ files were created.
            self.assertFalse((base/"retained"/"routing").exists())
            self.assertFalse((base/"retained"/"visual").exists())
            self.assertTrue((base/"retained"/"austria"/"v1").exists())
            self.assertTrue((base/"retained"/"italy-nord-est"/"v1").exists())

    def test_missing_regression_is_refused_and_creates_no_published_pack(self):
        with tempfile.TemporaryDirectory() as t:
            base=Path(t)
            region="austria"
            cfg=config(region,"Austria","AT")
            cfg["overture"]["validation"][0]["nameEquals"]="Not Present"
            cfgfile=base/"config.json";cfgfile.write_text(json.dumps(cfg))
            data=base/"places.geojsonseq"
            data.write_text(json.dumps(place("wien","Wien Fuel","AT",48.2,16.36))+"\n")
            result=run_cli("build","--config",cfgfile,"--input",data,
                           "--source-release","synthetic","--pack-version","v1",
                           "--dist-dir",base/"dist","--work-dir",base/"work")
            self.assertNotEqual(result.returncode,0)
            self.assertFalse((base/"dist"/region/"v1").exists())

    def test_missing_config_and_unsafe_components_fail_before_download(self):
        with tempfile.TemporaryDirectory() as t:
            base=Path(t)
            cfg=config("austria","Austria","AT")
            cfile=base/"config.json"
            cfg["overture"]["enabled"]=False
            cfile.write_text(json.dumps(cfg))
            with self.assertRaisesRegex(ValueError,"disabled"):
                producer.build(cfile,base/"dist",base/"work","1.0")
            cfg["overture"]["enabled"]=True
            cfg["overture"]["validation"]=[]
            cfile.write_text(json.dumps(cfg))
            with self.assertRaisesRegex(ValueError,"validation"):
                producer.build(cfile,base/"dist",base/"work","1.0")
            cfg["overture"]["validation"]=config("austria","Austria","AT")["overture"]["validation"]
            cfile.write_text(json.dumps(cfg))
            with self.assertRaisesRegex(ValueError,"Unsafe pack version"):
                producer.build(cfile,base/"dist",base/"work","../v1")

    def test_source_acquisition_pins_exact_stac_release_in_both_attempts(self):
        with tempfile.TemporaryDirectory() as t:
            base = Path(t)
            cfg = config("austria", "Austria", "AT")
            requested = base / "places.geojsonseq"
            commands = []
            from types import SimpleNamespace

            def download_command(args, check=False):
                commands.append(list(args))
                if len(commands) == 2:
                    requested.write_text("some nonempty original source")
                return SimpleNamespace(returncode=0 if len(commands) == 2 else 1)

            # No network: patch subprocess execution and the CLI existence
            # probe, then assert both attempts use the exact STAC release.
            with patch.object(producer, "require_pinned_client", return_value="1.0.2"), (
                 patch.object(producer, "latest_release", return_value="2026-10-21.0")), (
                 patch.object(producer.subprocess, "run", side_effect=download_command)), (
                 patch.object(producer.sys, "executable",
                              str(Path(__file__).resolve().parents[2] /
                                  "diagnostics/test-missing-virtualenv/bin/python"))):
                # Use the existing executable from the local environment,
                # but fake only the executable-file existence probe.
                with patch.object(producer.Path, "is_file", return_value=True):
                    self.assertEqual("2026-10-21.0",
                                     producer.download(cfg, cfg["overture"], requested))
            self.assertEqual(2, len(commands))
            for command in commands:
                self.assertIn("--release", command)
                self.assertEqual(command[command.index("--release")+1], "2026-10-21.0")
                self.assertIn("--bbox=10.0,47.0,17.0,49.0", command)
            self.assertNotIn("--no-stac", commands[0])
            self.assertIn("--no-stac", commands[1])

    def test_import_refuses_manifest_symlink(self):
        with tempfile.TemporaryDirectory() as t:
            base=Path(t)
            cfg=base/"cfg.json";cfg.write_text(json.dumps(config("austria","Austria","AT")))
            fake=base/"original.json";fake.write_text("{}")
            symlink=base/"link.json";symlink.symlink_to(fake)
            with self.assertRaisesRegex(ValueError,"regular local"):
                producer.import_pack(cfg,symlink,base/"imports")


if __name__ == "__main__":
    unittest.main()
