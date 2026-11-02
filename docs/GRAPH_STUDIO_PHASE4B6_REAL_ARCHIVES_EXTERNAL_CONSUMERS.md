# Graph Studio P4-B6 — Historical artifacts and external/manual CLI consumers

**Audit date:** 2026-11-02. **Base:** merged PR #100, followed by a handoff-only commit. **Tracking:** GitHub issue #89.

**Decision:** G1 remains OPEN. All eleven legacy validators and their shipped CLI filenames, flags, v1 schemas, exit statuses and output contracts remain RETAIN. This is evidence work, not authorization for a compatibility wrapper, deprecation, deletion, Android/F8 behavior change, rebuild or release.

## 1. Genuine historical artifacts: bounded recovery on Legion

The established read-only, schema-allowlisted devtools/audit_historical_fixture_inventory.py was executed again, against only the four named existing workspaces. Output is limited to counts, schema IDs and hashes; no original data is committed.

| Scoped root | JSON checked | Over 16 MiB (unparsed) | Genuine legacy matches | Genuine populated |
| --- | ---: | ---: | --- | ---: |
| Graph Studio operational workspace | 85 | 4 | 1 frontier inventory v1, roads: [] | 0 |
| Historical F8 stage-5 audit | 137 | 0 | 0 | 0 |
| Historical F8 learned-replay | 137 | 0 | 0 | 0 |
| Historical F8 cleanup | 137 | 0 | 0 | 0 |

No root hit its depth or file-count limit. The only genuine v1 source inventory has the **same SHA-256** as documented in P4-B3 (87a1cbf59546cd42644577185a2fd5c4f5155e536f05018ebcdf24ce9add261e). **It contains zero roads.** Synthetic populated fixtures from P4-B4/P4-B5 do not constitute recovered operational records.

### Existing archive screening

The named Graph Studio workspace contained 12 normal TAR archives, approximately 8.9 GiB total. A **non-extracting TAR-header inventory** examined 5,162 member entries; **none had a JSON filename extension**. No member-count truncation or TAR errors occurred. Six GZIP archives from the workspace and two from Downloads were checked only at the first 4,096 decompressed bytes for a JSON schema header; **0/8** matched. No archive content was committed and no user map files were modified.

These are negative findings **only within the defined inspection**. Renamed JSON files, interior GZIP data, full contents of the four oversized JSON files, backups on unavailable devices, older exports and external accounts are NOT VERIFIED. The four oversized workspace JSON files were independently screened at only their first 8 KiB; none had a recognizable allowlisted legacy v1 schema field in that prefix. This bounded header screen is not full JSON validation.

## 2. Reproducible external/manual consumer audit

New development-only tool: devtools/audit_legacy_cli_external_consumers.py. It accepts **explicitly nominated script/configuration directories**, scans only allowlisted source suffixes and records **aggregate per-validator literal filename/stem mentions**, never absolute source paths, commands, arguments, private values or host identifiers. It executes no legacy validators and makes no network requests.

Safety and scope: maximum 10,000 eligible files per root, 512 KiB per file, 12 directory levels; no followed symlinks, FIFOs or dependency/build directories. It reports skipped/oversized files, unreadable subdirectories and truncation; inaccessible trees must never be silently interpreted as empty. A literal mention is not an established execution consumer; zero matches does not prove that external or dynamic/manual consumers are absent. Output explicitly says manual_and_dynamic_consumers = UNKNOWN.

Example for an operator-authorized script directory only:

    PYTHONDONTWRITEBYTECODE=1 python3 devtools/audit_legacy_cli_external_consumers.py --root /path/to/authorized-scripts

Actual Legion root scan (only directory categories disclosed, not private filenames):

| Scoped category | Eligible files | Literal CLI references |
| --- | ---: | ---: |
| User local executable scripts | 0 | 0 |
| User Applications folder | 559 | 0 |
| User systemd units | 6 | 0 |
| System systemd units | 5 | 0 |
| System cron.d and cron.daily | 0 | 0 |
| Historical F8 stage-5 worktree | 33 | 0 |
| Historical F8 learned-replay worktree | 34 | 0 |
| Historical F8 cleanup worktree | 36 | 0 |
| **Total** | **673** | **0** |

All nine scopes were nontruncated. This updates earlier P4-B2/B3 bounded Bash-history and owner-indexed GitHub observations. The historical pre-#84 CI calling **all 11** and retired orchestration invoking **seven** remain confirmed former consumers; the installed Debian/AppImage shipping all eleven still creates a compatibility obligation. Other devices, manual use, third-party integrations and dynamically assembled commands remain UNKNOWN.

New tests/test_legacy_cli_external_consumers.py has seven synthetic regression tests for positives, private-output suppression, symlink and FIFO exclusion, unreadable directory disclosure, file/byte/depth limits, binary handling and the UNKNOWN interpretation. Add its invocation to hosted repository CI. The new tool stays under devtools, not installed wildcard tools/.

## 3. Operator evidence request — NOT an attestation

These items must be answered **by actual operators**, not inferred from a source search:

| Question | Current evidence |
| --- | --- |
| Is any old validate_*.py CLI used in manual maintenance, cron, CI or third-party scripts? | UNKNOWN |
| Exact validator filenames and flags | NOT PROVIDED |
| Installed Graph Studio version and approximate last-use time | NOT PROVIDED |
| Maintainer/operator and required compatibility window | NOT PROVIDED |
| Are genuine populated v1 operational artifacts retained in backups? | NOT VERIFIED |
| Can the owner approve limited metadata or checksummed temporary-copy verification? | NOT AUTHORIZED |

Do not request secrets, full history, unredacted logs or private original road/connector records in a public issue. With explicit owner permission, existing devtools/verify_legacy_fixture_parity.py can test a trusted locally installed/source validator against **temporary copies only**, recording SHA and result metadata without committing original bytes. Mere absence of a reply cannot be recorded as a negative attestation.

## 4. Gates

- **G1 INCOMPLETE:** P4-B4/B5 established positive *synthetic* schema compatibility for all eleven CLI families, but neither genuine populated saved operational artifacts nor external/manual operator attestations have been recovered.
- **G2 BLOCKED:** no wrapper or migration proposed; preserve existing shipped CLI behavior.
- **G3/G4 BLOCKED:** no deprecation warnings, hidden telemetry, removal or package cleanup approved.
- **Native F8/Android UNCHANGED:** this evidence is not graph-edge parity, full discovery enumeration or routing release acceptance.
- **Issue #89 OPEN:** prior UI audit marked UI-01 to UI-13 done; #89 remains a Phase 4 dependency/cleanup tracking gate, not evidence of new UI regressions.
- **PR approval gate:** separate security/data-integrity review, exact-head CI, and explicit owner authorization before merging this non-release audit PR.

**Next:** locate consented offline backups or older operator exports, check the four previously excluded large JSON files safely if warranted, and request real operator version/flags/support-window declarations. All eleven existing validators remain available until separately authorized policy changes.
