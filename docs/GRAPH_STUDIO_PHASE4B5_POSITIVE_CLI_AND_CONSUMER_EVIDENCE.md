# Graph Studio P4-B5 — Historical positive CLI parity and external-consumer gate

**Recorded:** 2026-11-01. **Related:** [P4-B4 policy](GRAPH_STUDIO_PHASE4B4_POPULATED_REPLAY_COMPAT_POLICY.md), [P4-B3 audit](GRAPH_STUDIO_PHASE4B3_HISTORICAL_POPULATED_FIXTURES_CONSUMERS.md), [issue #89](https://github.com/kandyman991/RoadPilot-Offline-Data/issues/89).

**Decision: RETAIN all eleven legacy validators and their shipped v1 CLI contracts.** This is development-only evidence, not approval to deprecate/remove or publish a release.

## 1. Reconstructed positive historical CI evidence

- **Historical source:** pre-#84 committed workflow at full SHA 9c95ca37ef763f3e3d123fb3c77f2c9b25ab0be3 (parent of 661a23a), and historical tools extracted via Git archive into disposable temporary directories.
- **Twelve historical stages replayed, 12/12 PASS:** directed connectivity pair; frontier road inventory; independent frontier correlations; crossing candidates; mocked local Valhalla crossing proofs; compact runtime connectivity; multi-hop composition; regional connector inventories; exact-edge matrices; hierarchical composition; region connector refresh and surgical connectivity refresh. The selected stages were inspected for network, install and privileged commands before execution.
- **Forty outputs / eleven validator families:** 40 synthetic v1 JSON artifacts. All 40 were accepted by the historical source validator, current source validator and installed Debian validator with identical return code, stdout and stderr. All eleven validator script triplets were byte-identical in this audit.
- **Material nonempty examples:** 2 frontier road records, 2 correlations, 18 candidates, 18 crossing proofs (8 proven, 10 rejected), 8 runtime crossings, plus nonempty chain/anchor/plan samples. Region connector matrix and refresh plan use meaningful nested objects rather than top-level arrays; counting only top-level lists would misclassify them.
- **Safety and provenance:** each replayed output was reconstructed from synthetic CI data. None is an archived GitHub Actions artifact or a recovered real operational file. Scripts ran only in disposable directories. The replay did not modify installed applications, the live Graph Studio workspace, private user data, the native F8 engine or Android.

### Durable ten-family regression corpus

The directory tests/fixtures/historical-legacy-v1-synthetic contains ten canonical synthetic v1 samples (one per formerly unverified validator family) and a SHA-256 manifest, pinned to the full historical source commit. The earlier frontier fixture remains covered separately by P4-B4. The new corpus totals approximately 216 KiB, is invented historical CI data only, and is marked **RECONSTRUCTED_SYNTHETIC_HISTORICAL_CI_NOT_PRODUCTION** with **f8GraphEdgeParity NOT_VERIFIED**.

The new tests/test_historical_legacy_positive_fixtures.py asserts the ten fixed validator/schema identities, pinned fixture hashes and sizes, original provenance and v1 schemas. It runs ten positive validations on temporary artifact copies and ten negative invalid-schema validations; both outcomes preserve the copy hashes and create no new files. Hosted repository CI now invokes the new regression test on PR heads.

**Hosted CI verifies current-source validators only.** The installed Debian and historical-source parity checks were separately executed on the Legion, not in GitHub Actions.

## 2. Genuine historic production artifacts

**NOT RECOVERED.** Earlier P4-B2/B3 bounded scans of the actual Graph Studio workspace and three historical F8 worktrees found one genuine v1 frontier inventory with **roads: []**, but no genuinely populated artifacts for the eleven validator families. This audit verified the known workspace remains present and checked relevant diagnostic filenames, but did not repeat the full contents scan, search other peoples' accounts, access old external disks, or recover operator backups. The historical CI snapshots in this PR **do not** fill this provenance gap.

If an owner/operator supplies consented backup/export samples, use metadata and checksum-protected temporary copies with the existing developer-only parity verifier. Never commit genuine or private inputs.

## 3. Consumer inventory

| Consumer surface | Evidence | Status |
| --- | --- | --- |
| Pre-#84 GitHub Actions | Direct calls to all eleven validators in committed historical workflow; replayed | **CONFIRMED former use** |
| Retired refresh_graph_connectivity orchestrator | Previously traced seven validator invocations | **CONFIRMED former use** |
| Current checked-in executable source/workflows | Fresh scoped scan of 169 tracked files: no direct literal legacy-validator filename calls in runtime/workflow sources | **NOT FOUND in scoped scan** |
| Installed Debian and AppImage | All eleven scripts remain shipped; installed Debian validators passed historical synthetic parity | **CONFIRMED shipped CLI surfaces** |
| Other GitHub accounts, old installed versions, partner scripts, maintenance automation, manual shells | Previous bounded local and owner-indexed searches cannot attest to absence | **UNKNOWN** |

**Manual use questionnaire remains unanswered.** Obtain only the CLI filename, flags, installed version, maintainer and required support window from possible users/operators. Do not request secrets, unredacted logs or artifact contents. Absence of a response is not evidence of zero consumers.

## 4. Outstanding approval gates

- **G1 remains INCOMPLETE:** synthetic compatibility for all eleven families established for reconstructed historical CI samples; genuine populated user data and external/manual consumer attestations remain unavailable.
- **G2 compatibility wrappers, G3 versioned deprecation and G4 removal** remain blocked pending separate owner-authorized proposals, review, exact-head CI, source/installed parity and rollback tests. No deprecation warnings or telemetry may be added silently.
- **F8 boundaries preserved:** no replacement of native directed graph crossing discovery, candidate enumeration, evidence or Valhalla journey proof; no claim of Android route parity from these synthetic schemas.
- **Issue #89 stays OPEN**, including outstanding Graph Studio UI tasks. No package publication, destructive cleanup or production release is authorized.
