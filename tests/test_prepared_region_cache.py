"""Deterministic source preparation cache invalidation, no OSM downloads."""
import tempfile
import unittest
from pathlib import Path

from tools.prepared_region_cache import (
    RETAINED_FILES, prepare_key, record_source_preparation, source_preparation_ready,
)


class PreparedRegionCacheTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.records = [
            {"id": "belgium", "url": "https://download.geofabrik.de/europe/belgium-latest.osm.pbf",
             "sha256": "a" * 64, "sizeBytes": 100},
            {"id": "netherlands/zuid-holland",
             "url": "https://download.geofabrik.de/europe/netherlands/zuid-holland-latest.osm.pbf",
             "sha256": "b" * 64, "sizeBytes": 50},
        ]
        self.key = prepare_key(self.records, "buffer-sha", "3.6.3")
        for filename in RETAINED_FILES:
            (self.root / filename).write_bytes(b"region preparation source " + filename.encode())

    def test_records_verified_inputs_for_rebuild(self):
        self.assertFalse(source_preparation_ready(self.root, self.key))
        record_source_preparation(self.root, self.key)
        self.assertTrue(source_preparation_ready(self.root, self.key))

    def test_changed_neighbor_or_buffer_or_valhalla_invalidates(self):
        record_source_preparation(self.root, self.key)
        updated = [dict(item) for item in self.records]
        updated[1]["sha256"] = "c" * 64
        self.assertFalse(source_preparation_ready(
            self.root, prepare_key(updated, "buffer-sha", "3.6.3")))
        self.assertFalse(source_preparation_ready(
            self.root, prepare_key(self.records, "another-buffer", "3.6.3")))
        self.assertFalse(source_preparation_ready(
            self.root, prepare_key(self.records, "buffer-sha", "3.7.0")))

    def test_changed_or_missing_buffered_input_blocks_reuse(self):
        record_source_preparation(self.root, self.key)
        target = self.root / "buffered.osm.pbf"
        target.write_bytes(b"modified, still non-empty")
        self.assertFalse(source_preparation_ready(self.root, self.key))
        record_source_preparation(self.root, self.key)
        target.unlink()
        self.assertFalse(source_preparation_ready(self.root, self.key))

    def test_truncated_or_missing_admin_db_blocks_reuse(self):
        record_source_preparation(self.root, self.key)
        (self.root / "admins.sqlite").write_bytes(b"")
        self.assertFalse(source_preparation_ready(self.root, self.key))

    def test_corrupted_metadata_does_not_bypass_integrity(self):
        (self.root / "source-preparation.json").write_text("{bad json", encoding="utf-8")
        self.assertFalse(source_preparation_ready(self.root, self.key))


if __name__ == "__main__":
    unittest.main()
