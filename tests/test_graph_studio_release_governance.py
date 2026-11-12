"""Issue #123: prevent CI events from publishing the Graph Studio rolling release.

These are intentionally dependency-free source contract tests so they run on
fresh GitHub Actions runners before installing the Tauri toolchain.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CI_WORKFLOW = ROOT / ".github/workflows/graph-studio.yml"
RELEASE_WORKFLOW = ROOT / ".github/workflows/graph-studio-release.yml"
RELEASE_TAG = "roadpilot-graph-studio-linux"
RELEASE_ENVIRONMENT = "graph-studio-linux-release"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class GraphStudioReleaseGovernanceTests(unittest.TestCase):
    def test_normal_pr_and_main_builds_are_read_only(self) -> None:
        ci = read(CI_WORKFLOW)
        self.assertRegex(ci, r"(?m)^  pull_request:\s*$")
        self.assertRegex(ci, r"(?m)^  push:\s*$")
        self.assertIn("branches: [main]", ci)
        self.assertIn("contents: read", ci)
        self.assertNotIn("contents: write", ci)
        self.assertNotIn("gh release", ci)
        self.assertNotIn(RELEASE_TAG, ci)
        self.assertNotIn("git/refs/tags", ci)
        self.assertNotIn("Publish rolling", ci)
        self.assertIn("Build AppImage and Debian packages", ci)
        self.assertIn("Verify Graph Studio packages", ci)

    def test_release_workflow_is_manual_only(self) -> None:
        release = read(RELEASE_WORKFLOW)
        self.assertRegex(release, r"(?m)^on:\s*$")
        self.assertRegex(release, r"(?m)^  workflow_dispatch:\s*$")
        for forbidden_event in ("pull_request", "push", "schedule", "workflow_call"):
            self.assertNotRegex(release, rf"(?m)^  {forbidden_event}:\s*$")

    def test_explicit_confirmation_and_exact_head_required(self) -> None:
        release = read(RELEASE_WORKFLOW)
        self.assertIn('test "$GITHUB_EVENT_NAME" = "workflow_dispatch"', release)
        self.assertIn('test "$GITHUB_REF" = "refs/heads/main"', release)
        self.assertIn('test "$CONFIRMATION" = "PUBLISH_GRAPH_STUDIO_LINUX"', release)
        self.assertIn('[[ "$REQUESTED_SHA" =~ ^[0-9a-f]{40}$ ]]', release)
        self.assertIn('test "$REQUESTED_SHA" = "$CURRENT_MAIN"', release)
        self.assertIn('echo "source_sha=$REQUESTED_SHA" >> "$GITHUB_OUTPUT"', release)

    def test_publish_job_requires_distinct_environment_approval(self) -> None:
        release = read(RELEASE_WORKFLOW)
        self.assertIn("needs: authorize", release)
        self.assertRegex(release, rf"(?m)^    environment: {RELEASE_ENVIRONMENT}$")
        self.assertRegex(release, r"(?m)^permissions:\n  contents: read$")
        self.assertRegex(release, r"(?m)^    permissions:\n      contents: write$")
        self.assertIn("cancel-in-progress: false", release)
        self.assertIn("persist-credentials: false", release)

    def test_pinned_source_and_provenance_guards(self) -> None:
        release = read(RELEASE_WORKFLOW)
        self.assertIn("ref: ${{ needs.authorize.outputs.source_sha }}", release)
        self.assertGreaterEqual(release.count('test "$(git rev-parse HEAD)" = "$APPROVED_SHA"'), 2)
        self.assertGreaterEqual(release.count('test "$CURRENT_MAIN" = "$APPROVED_SHA"'), 2)
        self.assertIn("approval_environment=graph-studio-linux-release", release)
        self.assertIn("sha256sum RoadPilot-Graph-Studio-Linux.AppImage RoadPilot-Graph-Studio-Linux.deb", release)
        self.assertIn("sha256sum --check", release)
        self.assertIn("Verify remote release asset hashes and source", release)

    def test_no_publication_during_test_jobs(self) -> None:
        ci = read(CI_WORKFLOW)
        release = read(RELEASE_WORKFLOW)
        self.assertIn("tests -p 'test_graph_studio_release_governance.py'", ci)
        self.assertIn('.github/workflows/graph-studio-release.yml', ci)
        self.assertIn("TAG=roadpilot-graph-studio-linux", release)
        self.assertIn("Revalidate approved main HEAD before changing any release", release)
        self.assertIn("Publish explicitly approved rolling Linux prerelease", release)


if __name__ == "__main__":
    unittest.main()
