# Graph Studio P4-B6 G1 follow-up — full local JSON and Git-ref inventory

**Recorded:** 2026-11-02. **Parent:** merged PR #101. **Issue:** #89. Scope is read-only evidence and developer-only tooling; no shipped-code changes or CLI retirement authorized.

## Full large-JSON inspection in the genuine Legion workspace

The already installed developer read-only inventory was re-run with a 96 MiB per-file cap:

    python3 devtools/audit_historical_fixture_inventory.py --root "$HOME/RoadPilotGraphStudio" --max-file-bytes 100663296

Results: **85 JSON files inspected; 0 oversize, 0 unreadable/invalid, 0 truncated**. This includes the previous four excluded JSON files (approximately 20.47, 22.16, 71.88 and 74.41 MiB), which until this pass were inspected by header only. Exactly one matching eleven-family v1 document exists: a genuine saved roadpilot.frontier-road-inventory with **roads: []**, matching the previously pinned SHA-256 87a1cbf59546cd42644577185a2fd5c4f5155e536f05018ebcdf24ce9add261e.

**No genuinely populated legacy v1 validator artifact was recovered** from this operational workspace. Originals were not modified. This says nothing about other storage locations, inaccessible backups or non-JSON representations.

## Reachable JSON Git objects across locally fetched refs

New developer-only read-only tool: devtools/audit_historical_git_legacy_blobs.py. It inspects only JSON filenames visible through git rev-list --objects --all and counts allowlisted legacy schema names only when the document has integer version 1, never printing private paths, contents, identifiers, coordinates or operator data. It does not execute validators, change data or fetch from the network. The per-blob default cap is 32 MiB; the per-run unique JSON blob cap is 10,000; truncation and unreadable/oversized items are disclosed. Historical fixture path names are categorized as TEST_FIXTURE rather than operational provenance.

To reproduce in an authorized local repository:

    python3 devtools/audit_historical_git_legacy_blobs.py --repo-root /path/to/checkout

Fresh Legion checkout anchored at main 48f5e794d12898d93b2d2c212c33a84cfbbbe7ca:

| Evidence in locally fetched repo refs | Observed |
| --- | ---: |
| Reachable commits | 867 |
| Remote-tracking branches | 91 |
| All Git object records surfaced by rev-list | 3,654 |
| JSON paths | 162 |
| Distinct JSON blobs parsed | 162 |
| Skipped, truncated, unreadable | 0 |
| Legacy v1 schema matches | 11 |
| Matched JSON blobs bearing historical test-fixture paths | 11 |
| Matched JSON blobs with non-test paths | 0 |

The eleven known schemas match the earlier **synthetic reconstructed CI** test fixtures (one frontier inventory, ten others); this does not establish recovered operational data. Nested formats may have material data without any of the specifically named top-level arrays.

Important limits: only currently reachable, locally fetched named Git objects; no dangling/pruned objects, other repositories, unfetched remote branches, expired Actions artifacts, backups, old device installations, private exports, or files without JSON names. Object path classification is indicative, not a production/nonproduction proof. No absence claim about external/manual consumers.

## Remain-open G1 gates and decisions

| Requirement | Status |
| --- | --- |
| Full JSON set within genuine Legion operational workspace | Complete, no nonempty v1 |
| Existing historical F8 workspaces and archive header investigation from PR #101 | Bounded negative evidence only |
| Locally fetched historical Git JSON ref objects | Complete, test-path matches only |
| True historical populated v1 operational inputs from trusted backups | NOT RECOVERED |
| External/manual/dynamic/off-machine CLI consumers | UNKNOWN |
| Explicit operator attestation, CLI flags, installed versions and support window | NOT PROVIDED |
| Real operational nonempty v1 source/installed validator parity | NOT VERIFIED |

Owner/operators can contribute **only** validator filenames, flags, expected stdout/stderr/exit behavior, installed version, approximate last use, support window and whether consented backups exist. Never publish secrets, private shell histories, source road records or proprietary user data to public PRs. Genuine files, if authorized, must be checked on temporary checksum-guarded copies under the existing opt-in parity tool.

**All eleven shipped legacy CLIs remain RETAIN.** G1 is incomplete; G2 wrapper, G3 deprecation and G4 destructive retirement are blocked. Native directed F8 graph crossing discovery and Android route behavior are unchanged. Issue #89 stays open. This non-release evidence PR requires exact-head CI, separate review and explicit owner merge authorization.
