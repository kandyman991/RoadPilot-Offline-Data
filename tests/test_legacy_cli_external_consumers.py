"""P4-B6: privacy, safety, and scope limits for external CLI evidence scanning."""
from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from devtools.audit_legacy_cli_external_consumers import audit_root, main
from devtools.audit_legacy_validator_dependencies import CANDIDATES


class ExternalConsumerAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / "consumer-scope"
        self.root.mkdir()
        self.v1, self.v2 = CANDIDATES[:2]

    def put(self, name: str, contents: str) -> Path:
        target = self.root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(contents, encoding="utf-8")
        return target

    def test_literal_candidates_count_per_file_and_no_private_text(self) -> None:
        first = self.put("jobs/maintenance.sh",
                         f"python {self.v1} --artifact /private/sensitive.json\n"
                         f"python {self.v1} --artifact /private/secret.json\n"
                         f"# {self.v2} SECRET_NEVER_PRINT_THIS")
        second = self.put("system/check.service", "ExecStart=/usr/bin/python "
                          + self.v1.removesuffix(".py") + " --artifact /secret")
        report = audit_root(self.root)
        self.assertEqual(report["matching_files"], 2)
        self.assertEqual(report["validator_literal_file_counts"][self.v1], 2)
        self.assertEqual(report["validator_literal_file_counts"][self.v2], 1)
        self.assertEqual(len(report["validator_literal_file_counts"]), 11)
        serialized = json.dumps(report)
        self.assertNotIn("SECRET_NEVER_PRINT_THIS", serialized)
        self.assertNotIn(str(self.root), serialized)
        self.assertNotIn("/private/sensitive.json", serialized)
        self.assertIn("LITERAL_ONLY", self.capture_main())
        self.assertEqual(first.read_text().count(self.v1), 2)
        self.assertTrue(second.is_file())

    def capture_main(self) -> str:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(["--root", str(self.root)]), 0)
        return output.getvalue()

    def test_binary_and_non_source_suffix_ignored(self) -> None:
        self.put("note.txt", f"{self.v1}")
        self.put("config.yml", f"comment {self.v2}")
        binary = self.root / "binary.service"
        binary.write_bytes(b"\x00"+self.v1.encode())
        report = audit_root(self.root)
        self.assertEqual(report["matching_files"], 1)
        self.assertEqual(report["validator_literal_file_counts"][self.v1], 0)
        self.assertEqual(report["validator_literal_file_counts"][self.v2], 1)

    def test_symlink_file_and_directory_are_not_followed(self) -> None:
        outside = self.root.parent / "outside"
        outside.mkdir()
        (outside / "secret.sh").write_text(self.v1, encoding="utf-8")
        (self.root / "linked.sh").symlink_to(outside / "secret.sh")
        (self.root / "linked-dir").symlink_to(outside, target_is_directory=True)
        report = audit_root(self.root)
        self.assertEqual(report["symlinks_skipped"], 2)
        self.assertEqual(report["matching_files"], 0)
        with self.assertRaisesRegex(ValueError, "not a symlink"):
            audit_root(self.root / "linked-dir")

    @unittest.skipUnless(hasattr(os, "mkfifo"), "POSIX FIFO only")
    def test_fifo_cannot_block_on_read(self) -> None:
        os.mkfifo(self.root / "named-pipe.service")
        report = audit_root(self.root)
        self.assertEqual(report["files_checked"], 1)
        self.assertEqual(report["non_regular_skipped"], 1)
        self.assertEqual(report["matching_files"], 0)

    def test_limits_and_root_coverage_are_explicit(self) -> None:
        self.put("one.sh", self.v1)
        self.put("two.sh", self.v2)
        capped = audit_root(self.root, max_files=1)
        self.assertEqual(capped["files_checked"], 1)
        self.assertTrue(capped["truncated"])
        small = audit_root(self.root, max_file_bytes=3)
        self.assertEqual(small["oversize_skipped"], 2)
        self.assertEqual(small["matching_files"], 0)
        for arguments in ({"max_files": 0}, {"max_file_bytes": 0}, {"max_depth": -1}):
            with self.assertRaises(ValueError):
                audit_root(self.root, **arguments)
        self.put("sub/inner.sh", self.v1)
        depth_limited = audit_root(self.root, max_depth=0)
        self.assertTrue(depth_limited["truncated"])
        self.assertEqual(depth_limited["matching_files"], 2)
        complete = audit_root(self.root)
        self.assertEqual(complete["matching_files"], 3)

    def test_unreadable_subtree_is_reported_not_silently_ignored(self) -> None:
        def inaccessible_walk(_path, *, followlinks, onerror):
            self.assertFalse(followlinks)
            onerror(PermissionError("private path must not print"))
            return iter([])
        with mock.patch(
            "devtools.audit_legacy_cli_external_consumers.os.walk",
            side_effect=inaccessible_walk,
        ):
            report = audit_root(self.root)
        self.assertEqual(report["unreadable_directories"], 1)
        self.assertEqual(report["files_checked"], 0)
        self.assertNotIn("private path", json.dumps(report))

    def test_machine_readable_report_makes_no_absence_claim(self) -> None:
        report = json.loads(self.capture_main())
        self.assertEqual(report["root_results"][0]["matching_files"], 0)
        self.assertEqual(report["manual_and_dynamic_consumers"], "UNKNOWN")
        self.assertTrue(report["missing_matches_do_not_prove_no_external_consumers"])
        self.assertFalse(report["limits"]["contents_or_absolute_paths_reported"])
        self.assertEqual(len(report["validators_to_retain"]), 11)


if __name__ == "__main__":
    unittest.main()
