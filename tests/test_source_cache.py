"""No-network tests for the shared routing+visual Geofabrik source cache."""
import hashlib
import io
import os
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from tools.source_cache import cached_geofabrik_pbf

URL = "https://download.geofabrik.de/europe/belgium-latest.osm.pbf"


class MockGeofabrik:
    def __init__(self):
        self.content = b"original simulated OSM PBF " * 19
        self.downloads = 0
        self.sidecars = 0
        self.offline = False
        self.corrupt_download = False

    def open(self, request, timeout=None):
        url = request.full_url
        if self.offline:
            raise urllib.error.URLError("network down")
        if url == URL + ".md5":
            self.sidecars += 1
            md5 = hashlib.md5(self.content).hexdigest()
            response = io.BytesIO(f"{md5}  belgium-latest.osm.pbf\n".encode())
        elif url == URL:
            self.downloads += 1
            data = self.content + b"corrupt" if self.corrupt_download else self.content
            response = io.BytesIO(data)
        else:
            raise AssertionError(f"unexpected URL {url}")
        response.headers = {"Content-Length": str(len(response.getvalue()))}
        return response


class SourceCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.destination = Path(self.temp.name) / "shared" / "belgium.osm.pbf"
        self.remote = MockGeofabrik()
        patcher = patch("urllib.request.urlopen", side_effect=self.remote.open)
        patcher.start()
        self.addCleanup(patcher.stop)

    def get(self, **kwargs):
        return cached_geofabrik_pbf(URL, self.destination, **kwargs)

    def test_initial_download_checksum_and_next_region_reuses_one_copy(self):
        self.assertEqual(self.get().read_bytes(), self.remote.content)
        self.assertEqual(self.get().read_bytes(), self.remote.content)
        self.assertEqual(self.remote.downloads, 1)
        self.assertEqual(self.remote.sidecars, 1)
        self.assertTrue(Path(str(self.destination) + ".source.json").is_file())

    def test_refresh_check_only_does_not_redownload_unchanged_bytes(self):
        self.get()
        self.get(check_interval_seconds=0)
        self.assertEqual(self.remote.sidecars, 2)
        self.assertEqual(self.remote.downloads, 1)

    def test_upstream_change_is_detected_and_replaced(self):
        self.get()
        self.remote.content = b"new upstream OSM snapshot" * 19
        self.get(check_interval_seconds=0)
        self.assertEqual(self.destination.read_bytes(), self.remote.content)
        self.assertEqual(self.remote.downloads, 2)

    def test_md5_mismatch_preserves_old_cached_file_and_removes_partial(self):
        original = self.get().read_bytes()
        self.remote.content = b"new snapshot"
        self.remote.corrupt_download = True
        with self.assertRaisesRegex(RuntimeError, "checksum mismatch"):
            self.get(check_interval_seconds=0)
        self.assertEqual(self.destination.read_bytes(), original)
        self.assertFalse(Path(str(self.destination) + ".part").exists())

    def test_offline_reuses_existing_bytes_but_new_region_fails(self):
        original = self.get().read_bytes()
        self.remote.offline = True
        self.assertEqual(self.get(check_interval_seconds=0).read_bytes(), original)
        self.destination.unlink()
        with self.assertRaises(urllib.error.URLError):
            self.get(check_interval_seconds=0)

    def test_different_source_url_must_not_reuse_offline_bytes(self):
        original = self.get().read_bytes()
        self.remote.offline = True
        different_url = URL.replace("belgium", "netherlands")
        with self.assertRaises(urllib.error.URLError):
            cached_geofabrik_pbf(
                different_url, self.destination, check_interval_seconds=0
            )
        self.assertEqual(self.destination.read_bytes(), original)

    def test_explicit_refresh_is_fail_closed_if_offline(self):
        original = self.get().read_bytes()
        self.remote.offline = True
        with self.assertRaisesRegex(RuntimeError, "Cannot refresh"):
            self.get(refresh=True)
        self.assertEqual(self.destination.read_bytes(), original)

    def test_legacy_visual_source_is_hardlinked_not_redownloaded(self):
        legacy = Path(self.temp.name) / "visual" / "cache" / "visual" / "belgium.osm.pbf"
        legacy.parent.mkdir(parents=True)
        legacy.write_bytes(self.remote.content)
        self.assertEqual(self.get(legacy_path=legacy).read_bytes(), self.remote.content)
        self.assertEqual(self.remote.downloads, 0)
        self.assertEqual(legacy.stat().st_ino, self.destination.stat().st_ino)

    def test_mismatched_legacy_data_is_corrected_without_overwriting_original(self):
        legacy = Path(self.temp.name) / "visual" / "cache" / "visual" / "belgium.osm.pbf"
        legacy.parent.mkdir(parents=True)
        legacy.write_bytes(b"old visual PBF")
        self.assertEqual(self.get(legacy_path=legacy).read_bytes(), self.remote.content)
        self.assertEqual(legacy.read_bytes(), b"old visual PBF")
        self.assertEqual(self.remote.downloads, 1)

    def test_invalid_cache_key_and_url_refused(self):
        with self.assertRaises(ValueError):
            cached_geofabrik_pbf("http://invalid/path.osm.pbf", self.destination)
        with self.assertRaises(ValueError):
            self.get(check_interval_seconds=-1)


if __name__ == "__main__":
    unittest.main()
