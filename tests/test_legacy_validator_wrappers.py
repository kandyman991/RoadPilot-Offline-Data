"""Archive compatibility gate for the 11 historical connectivity validators (D-016).

The unchanged implementations live under tools/legacy_archive/connectivity/ and the
original tools/validate_*.py paths are thin wrappers. These tests pin that the CLI
behaviour recorded from the pre-archive tools (baseline.json) is unchanged, that the
archived bytes are identical to the originals, that the wrappers work from any working
directory and from the installed package layout, and that the ten archived legacy
schemas are byte-identical and no longer sit at the top of schemas/.

Synthetic and read-only: no real workspace data is touched. This is not evidence of
native F8 parity or of any historical consumer outside the repository.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = json.loads(
    (ROOT / "tests" / "fixtures" / "legacy-cli-wrapper-golden" / "baseline.json").read_text(encoding="utf-8")
)
VALIDATORS = sorted(GOLDEN["validators"])
ARCHIVE_TOOLS = ROOT / "tools" / "legacy_archive" / "connectivity"
ARCHIVE_SCHEMAS = ROOT / "schemas" / "legacy_archive" / "connectivity"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run(script: Path, args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script), *args], capture_output=True, cwd=str(cwd), timeout=60
    )


def observed(script: Path, scenario: str, cwd: Path) -> dict:
    result = run(script, GOLDEN["scenarios"][scenario], cwd)
    entry = {"exitCode": result.returncode, "stdoutSha256": sha(result.stdout)}
    if scenario == "missing_input":
        lines = [line for line in result.stderr.decode().splitlines() if line.strip()]
        entry["lastStderrLine"] = lines[-1] if lines else ""
    else:
        entry["stderrSha256"] = sha(result.stderr)
    return entry


class ArchivedValidatorWrappers(unittest.TestCase):
    def test_eleven_validators_are_covered(self):
        self.assertEqual(len(VALIDATORS), 11)

    def test_archived_bytes_equal_originals(self):
        for name in VALIDATORS:
            with self.subTest(name=name):
                archived = ARCHIVE_TOOLS / f"{name}.py"
                self.assertTrue(archived.is_file())
                self.assertEqual(sha(archived.read_bytes()), GOLDEN["originalValidatorSha256"][name])

    def test_wrappers_are_thin_and_delegate(self):
        for name in VALIDATORS:
            with self.subTest(name=name):
                text = (ROOT / "tools" / f"{name}.py").read_text(encoding="utf-8")
                self.assertLess(len(text.splitlines()), 30)
                self.assertIn("runpy.run_path", text)
                self.assertIn("legacy_archive", text)
                compile(text, name, "exec")

    def test_cli_behaviour_matches_pre_archive_baseline(self):
        for name in VALIDATORS:
            for scenario in GOLDEN["scenarios"]:
                with self.subTest(name=name, scenario=scenario):
                    self.assertEqual(
                        observed(ROOT / "tools" / f"{name}.py", scenario, Path(tempfile.gettempdir())),
                        GOLDEN["validators"][name][scenario],
                    )

    def test_wrapper_works_with_relative_path_and_repo_cwd(self):
        for name in VALIDATORS:
            with self.subTest(name=name):
                relative = subprocess.run(
                    [sys.executable, f"tools/{name}.py", "--help"],
                    capture_output=True, cwd=str(ROOT), timeout=60,
                )
                self.assertEqual(relative.returncode, 0)
                self.assertEqual(sha(relative.stdout), GOLDEN["validators"][name]["help"]["stdoutSha256"])

    def test_installed_package_layout_still_resolves_the_archive(self):
        # Mirrors graph-studio/src-tauri/tauri.conf.json: ../../tools/ -> pipeline/tools/,
        # ../../schemas/ -> pipeline/schemas/ (subdirectories ship).
        with tempfile.TemporaryDirectory() as temp:
            pipeline = Path(temp) / "pipeline"
            shutil.copytree(ROOT / "tools", pipeline / "tools",
                            ignore=shutil.ignore_patterns("__pycache__", "native-f8-edge-scan"))
            shutil.copytree(ROOT / "schemas", pipeline / "schemas")
            for name in VALIDATORS:
                with self.subTest(name=name):
                    for scenario in GOLDEN["scenarios"]:
                        self.assertEqual(
                            observed(pipeline / "tools" / f"{name}.py", scenario, Path(temp)),
                            GOLDEN["validators"][name][scenario],
                        )

    def test_archived_schemas_are_byte_identical_and_moved(self):
        for stem, digest in GOLDEN["originalSchemaSha256"].items():
            with self.subTest(schema=stem):
                self.assertFalse((ROOT / "schemas" / f"{stem}.schema.json").exists())
                archived = ARCHIVE_SCHEMAS / f"{stem}.schema.json"
                self.assertEqual(sha(archived.read_bytes()), digest)
                self.assertTrue(json.loads(archived.read_text(encoding="utf-8"))["$id"].startswith("https://"))

    def test_current_pair_manifest_schema_is_not_archived(self):
        # roadpilot.cross-region-connectivity is the ACTIVE native F8 pair manifest schema.
        self.assertTrue((ROOT / "schemas" / "cross-region-connectivity.schema.json").is_file())
        self.assertTrue((ROOT / "tools" / "validate_cross_region_connectivity.py").is_file())
        self.assertFalse((ARCHIVE_TOOLS / "validate_cross_region_connectivity.py").exists())

    def test_nothing_else_moved_into_the_archive(self):
        self.assertEqual(
            sorted(p.name for p in ARCHIVE_TOOLS.glob("*.py")),
            sorted(f"{name}.py" for name in VALIDATORS),
        )
        self.assertEqual(len(list(ARCHIVE_SCHEMAS.glob("*.schema.json"))), 10)


if __name__ == "__main__":
    unittest.main()
