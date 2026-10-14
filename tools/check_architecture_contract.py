#!/usr/bin/env python3
"""PR policy gate for accepted RoadPilot F8 routing architecture.

Run on the PR HEAD with changed-files supplied from the trusted Git diff.
No network or GitHub write permission. Tests cover bypass attempts.
CODEOWNERS+required status ruleset are needed to prevent workflow edits from
bypassing this check; a workflow in an unprotected repo is not a merge lock.
"""
from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

INVARIANTS = (
    "F8 remains the reference algorithm; no unproven narrower replacement scanner",
    "First successful or cached crossing never hides alternative crossings",
    "No pre-Valhalla heading/road-class/separation rejection of potentially valid handoffs",
    "Directed mode-specific Valhalla proof and exact graph fingerprints are preserved",
    "Discovery/route completeness is reported truthfully, including budgets and unverified parity",
    "CI regression evidence is supplied; real-device/F8 parity remains unverified until actually tested",
)

POLICY_FILES = {
    "AGENTS.md",
    "docs/ARCHITECTURE_CONTRACT.md",
    "docs/ARCHITECTURE_GAPS.md",
    "docs/ENGINEERING_DECISIONS.md",
    ".github/CODEOWNERS",
    ".github/pull_request_template.md",
    ".github/workflows/architecture-contract.yml",
    "tools/check_architecture_contract.py",
    "tests/test_f8_architecture_regressions.py",
}
ROUTING_FILES = re.compile(
    r"^(?:"
    r"tools/[^/]*(?:routing|route|frontier|crossing|connectivity|connector|multiregion|valhalla)[^/]*[.]py"
    r"|graph-studio/src-tauri/src/lib[.]rs"
    r"|graph-studio/src/main[.]ts"
    r"|tests/test_(?:connectivity|graph_studio_multiregion|f8)[^/]*[.]py"
    r"|native/[^/]*(?:valhalla|routing|frontier)[^/]*"
    r")$"
)
CHECKED = re.compile(r"^\s*-\s*\[[xX]\]\s*(.*?)\s*$", re.MULTILINE)
URL = re.compile(r"https://github[.]com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/(?:issues|pull)/\d+")
CLAUSE = re.compile(r"\b[ABCD][1-4]\b")


def protected(paths: list[str]) -> list[str]:
    return [path for path in paths
            if path in POLICY_FILES or bool(ROUTING_FILES.fullmatch(path))]


def field(body: str, name: str) -> str:
    found = re.search(rf"(?im)^\s*{re.escape(name)}\s*:\s*(.*?)\s*$", body)
    return found.group(1).strip() if found else ""


def section(body: str, heading: str) -> str:
    found = re.search(
        rf"(?im)^##\s+{re.escape(heading)}\s*\n(.*?)(?=^##\s+|\Z)",
        body,
        flags=re.MULTILINE | re.DOTALL,
    )
    return found.group(1).strip() if found else ""


def validate(body: str, files: list[str]) -> list[str]:
    impacted = protected(files)
    if not impacted:
        return []
    errors = []
    impact = section(body, "Architectural impact (required for protected routing changes)")
    checks = section(body, "F8 invariants checklist (complete these for protected routing changes)")
    verification = section(body, "Verification / route evidence")
    if not impact:
        errors.append("Missing ## Architectural impact (required for protected routing changes).")
    if not checks:
        errors.append("Missing ## F8 invariants checklist (complete these for protected routing changes).")
    if not verification or len(verification) < 80:
        errors.append("Provide >=80 characters of actual test results and limitations in ## Verification / route evidence.")
    if any(x in body.lower() for x in (
        "explain what changes, which implementation actually runs",
        "explain test names and observed results",
        "keep only relevant clauses",
    )):
        errors.append("PR template instructions must be replaced with actual architecture/evidence text.")

    decision = field(body, "Architecture decision")
    if decision == "CHANGE_REQUESTED":
        errors.append(
            "Architecture changes are NOT automatically permitted. Stop and obtain "
            "an explicit user-approved superseding decision and code-owner review first."
        )
    elif decision != "PRESERVES":
        errors.append("Architecture decision must be PRESERVES; no implied approval for a new design.")

    if not CLAUSE.search(field(body, "Contract clauses")):
        errors.append("List affected contract clause IDs (e.g., A2, B1, C1).")
    inspected = field(body, "F8 reference inspected")
    if not any(name in inspected for name in (
        "FrontierRouteLocalRecovery.kt", "ManagedFrontierChainRoutingRuntime.kt",
        "FrontierMultiRegionChainPlanner.kt"
    )):
        errors.append("Cite the actual Android F8 source inspected (FrontierRouteLocalRecovery.kt etc.).")

    coverage = field(body, "Discovery coverage")
    if coverage not in {"NOT_VERIFIED", "SOURCE_EXHAUSTED", "GRAPH_EDGE_PARITY_VERIFIED"}:
        errors.append("Discovery coverage must state NOT_VERIFIED / SOURCE_EXHAUSTED / GRAPH_EDGE_PARITY_VERIFIED.")
    if coverage == "GRAPH_EDGE_PARITY_VERIFIED" and "F8 parity evidence:" not in body:
        errors.append("F8 graph-edge parity claims require an explicit F8 parity evidence link/report.")
    device = field(body, "Device validation")
    if device not in {"NOT_RUN", "PASSED", "FAILED"}:
        errors.append("Device validation must say NOT_RUN, PASSED or FAILED.")
    if device == "PASSED" and "Device test evidence:" not in body:
        errors.append("Device PASS requires explicit route, device, graph/version and test evidence.")

    if not URL.search(field(body, "Evidence")):
        errors.append("Evidence must link to an issue or PR describing test evidence.")
    gap = field(body, "Known gaps")
    if not gap or gap.strip().lower() in {"none", "n/a", "tbd", "todo"}:
        errors.append("Known gaps require a tracked issue link or an explicit evidence-backed explanation.")
    if not URL.search(gap):
        errors.append("Known gaps must link to a tracked GitHub issue/PR.")

    checked = set(CHECKED.findall(checks))
    for item in INVARIANTS:
        if item not in checked:
            errors.append("Unchecked F8 invariant: " + item)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--changed-files", type=Path, required=True)
    parser.add_argument("--pr-body-env", default="PR_BODY")
    args = parser.parse_args()
    paths = args.changed_files.read_text(encoding="utf-8").splitlines()
    body = os.environ.get(args.pr_body_env, "")
    blocked = protected(paths)
    print(f"F8 architecture gate: {len(blocked)} protected path(s)")
    for file in blocked:
        print(f"  {file}")
    problems = validate(body, paths)
    if problems:
        for error in problems:
            print("ARCHITECTURE POLICY FAILURE:", error)
        return 1
    print("F8 architecture PR policy: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
